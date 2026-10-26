#!/usr/bin/env python3
"""Check native PyKEEN context adjacency with shared supervision on invented data.

This CPU engineering smoke has no biomedical input or checkpoint option. It
does not measure prediction quality or freeze a biological evaluation protocol.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import os
import platform
import time
import traceback
from datetime import datetime, timezone
from importlib.metadata import version
from pathlib import Path


def write_json(path: Path, value: object) -> None:
    with path.open("x", encoding="utf-8") as stream:
        json.dump(value, stream, indent=2, sort_keys=True, allow_nan=False)
        stream.write("\n")


def run(output: Path) -> dict:
    import numpy as np
    import torch
    from pykeen.models import ComplEx, RGCN
    from pykeen.predict import predict_triples
    from pykeen.sampling import PseudoTypedNegativeSampler
    from pykeen.sampling.filtering import PythonSetFilterer
    from pykeen.training import SLCWATrainingLoop, TrainingCallback
    from pykeen.triples import TriplesFactory

    torch.set_num_threads(1)
    entities = {name: index for index, name in enumerate([*(f"g{i}" for i in range(6)), "c0", "c1"])}
    relations = {"interacts": 0, "member_of": 1, "located_in": 2}
    pairs = [(f"g{i}", f"g{(i + 1) % 6}") for i in range(6)]
    shared = [(a, "interacts", b) for a, b in pairs for a, b in ((a, b), (b, a))]
    reserved = [("g0", "interacts", "g2"), ("g2", "interacts", "g0")]
    development = [("g1", "interacts", "g3"), ("g3", "interacts", "g1")]
    baseline_context = [(f"g{i}", "member_of", f"c{int(i >= 3)}") for i in range(6)]
    extra_context = [("g0", "located_in", "c1"), ("g2", "located_in", "c1"), ("g4", "located_in", "c0")]

    def factory(rows: list[tuple[str, str, str]]) -> TriplesFactory:
        return TriplesFactory.from_labeled_triples(
            np.asarray(rows), entity_to_id=entities, relation_to_id=relations,
            compact_id=False, create_inverse_triples=False,
        )

    supervision = factory(shared)
    held_out = factory(reserved + development).mapped_triples
    blocked = torch.cat([supervision.mapped_triples, held_out])
    blocked_set = {tuple(row) for row in blocked.tolist()}
    held_out_set = {tuple(row) for row in held_out.tolist()}
    adjacency = {
        "rgcn_scaffold": factory(shared),
        "rgcn_context": factory(shared + baseline_context),
        "rgcn_enriched": factory(shared + baseline_context + extra_context),
        "complex_scaffold": factory(shared),
    }
    for item in [supervision, *adjacency.values()]:
        assert item.entity_to_id == entities and item.relation_to_id == relations
        assert not item.create_inverse_triples
        assert not held_out_set.intersection(map(tuple, item.mapped_triples.tolist()))

    # Use the existing exact filter, including reserved identities without labels.
    filterer = PythonSetFilterer(mapped_triples=blocked)
    assert not filterer(negative_batch=held_out).any()
    allowed = torch.tensor([[entities["g0"], relations["interacts"], entities["g3"]]])
    assert filterer(negative_batch=allowed).all()
    probe = PseudoTypedNegativeSampler(
        mapped_triples=supervision.mapped_triples,
        num_entities=len(entities), num_relations=len(relations),
        num_negs_per_pos=256, filterer=filterer,
    )
    assert probe.filterer is filterer
    torch.manual_seed(41)
    negatives, mask = probe.sample(supervision.mapped_triples)
    assert mask is not None
    proposed_held_out = sum(tuple(row) in held_out_set for row in negatives.reshape(-1, 3).tolist())
    assert proposed_held_out > 0
    assert not blocked_set.intersection(map(tuple, negatives[mask].tolist()))
    assert set(negatives[:, :, [0, 2]].reshape(-1).tolist()) <= set(range(6))

    class ObserveBatches(TrainingCallback):
        """Observe the stock trainer without changing its batches or updates."""

        def __init__(self) -> None:
            super().__init__()
            self.batches: list[list[list[int]]] = []
            self.steps = 0
            self.filtered_held_out = 0
            self.initial_parameters_sha256 = None

        def pre_batch(self, **kwargs) -> None:
            if self.initial_parameters_sha256 is None:
                digest = hashlib.sha256()
                for name, parameter in self.model.named_parameters():
                    digest.update(name.encode())
                    digest.update(parameter.detach().cpu().numpy().tobytes())
                self.initial_parameters_sha256 = digest.hexdigest()

        def post_batch(self, epoch: int, batch: dict, **kwargs) -> None:
            self.steps += 1
            rows = sorted(batch["positives"].tolist())
            assert rows == sorted(supervision.mapped_triples.tolist())
            self.batches.append(rows)
            masks = batch["masks"]
            assert not blocked_set.intersection(map(tuple, batch["negatives"][masks].tolist()))
            self.filtered_held_out += sum(
                tuple(row) in held_out_set for row in batch["negatives"].reshape(-1, 3).tolist()
            )

    results = {}
    batch_reference = None
    parameter_reference = None
    for name, context in adjacency.items():
        is_rgcn = name.startswith("rgcn")
        kwargs = {
            "triples_factory": context, "embedding_dim": 8, "random_seed": 17,
        }
        if is_rgcn:
            kwargs.update(num_layers=1, decomposition="bases", decomposition_kwargs={"num_bases": 2},
                          edge_dropout=0.0, self_loop_dropout=0.0)
        model = (RGCN if is_rgcn else ComplEx)(**kwargs).to("cpu")
        if is_rgcn:
            representation = model.entity_representations[0]
            actual_adjacency = torch.stack(
                [representation.sources, representation.edge_types, representation.targets], dim=1,
            )
            assert torch.equal(actual_adjacency, context.mapped_triples)
        observer = ObserveBatches()
        loop = SLCWATrainingLoop(
            model=model, triples_factory=supervision, optimizer="Adam",
            optimizer_kwargs={"lr": 0.001}, automatic_memory_optimization=False,
            negative_sampler=PseudoTypedNegativeSampler,
            negative_sampler_kwargs={"num_negs_per_pos": 16, "filterer": filterer},
        )
        torch.manual_seed(17)
        started = time.perf_counter()
        losses = loop.train(
            triples_factory=supervision, num_epochs=2, batch_size=len(shared),
            sampler="schlichtkrull", use_tqdm=False, num_workers=0,
            checkpoint_directory=output / "checkpoints" / name, callbacks=observer,
            pin_memory=False,
        )
        seconds = time.perf_counter() - started
        assert losses is not None and len(losses) == 2 and all(math.isfinite(loss) for loss in losses)
        assert observer.steps == 2 and observer.filtered_held_out > 0
        optimizer_steps = {int(state["step"].item()) for state in loop.optimizer.state.values() if "step" in state}
        assert optimizer_steps == {2}
        if batch_reference is None:
            batch_reference = observer.batches
        assert observer.batches == batch_reference
        if is_rgcn:
            if parameter_reference is None:
                parameter_reference = observer.initial_parameters_sha256
            assert observer.initial_parameters_sha256 == parameter_reference
        scores = predict_triples(model=model, triples=held_out, batch_size=2)
        assert torch.equal(scores.result, held_out) and torch.isfinite(scores.scores).all()
        by_triple = dict(zip(map(tuple, scores.result.tolist()), scores.scores.tolist(), strict=True))
        pair_scores = []
        for a, _, b in (reserved[0], development[0]):
            forward = by_triple[(entities[a], relations["interacts"], entities[b])]
            reverse = by_triple[(entities[b], relations["interacts"], entities[a])]
            if is_rgcn:
                assert math.isclose(forward, reverse, rel_tol=1e-5, abs_tol=1e-6)
            pair_scores.append({"pair": [a, b], "forward": forward, "reverse": reverse, "mean": (forward + reverse) / 2})
        results[name] = {
            "status": "passed", "adjacency_triples": context.num_triples if is_rgcn else None,
            "supervision_triples": supervision.num_triples, "optimizer_steps": observer.steps,
            "positive_batch_sha256": hashlib.sha256(json.dumps(observer.batches).encode()).hexdigest(),
            "initial_parameters_sha256": observer.initial_parameters_sha256,
            "reserved_or_dev_negative_proposals_removed": observer.filtered_held_out,
            "losses": losses, "synthetic_pair_scores": pair_scores, "training_seconds": seconds,
        }
        print(f"{name}: passed (CPU, invented graph, 2 optimizer steps)", flush=True)
    return {
        "format": "biograph-steward.pykeen-context-smoke.v1", "status": "passed",
        "purpose": "engineering_only", "biomedical_inputs_used": False,
        "biological_quality_measured": False, "device": "cpu",
        "entity_to_id": entities, "relation_to_id": relations,
        "reserved_triples": reserved, "development_triples": development,
        "probe_reserved_or_dev_negative_proposals_removed": proposed_held_out,
        "arms": results,
        "limitations": [
            "Full supervision batch per epoch: verifies identical batch contents, not arbitrary minibatch schedules.",
            "Negative proposals use the same sampler and filter contract; byte-identical draws across arms are not asserted.",
            "Dropout disabled for this wiring smoke; scientific hyperparameters are not selected.",
            "Same optimizer steps do not imply same wall-clock cost: RGCN adjacency sizes differ.",
            "Synthetic scores and losses are engineering diagnostics, not prediction-quality metrics.",
            "No biological scaling, CUDA environment, protocol freeze or dataset evaluation was exercised.",
        ],
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-dir", type=Path, required=True)
    args = parser.parse_args()
    args.output_dir.mkdir(parents=True, exist_ok=False)
    os.environ.setdefault("PYSTOW_HOME", str(args.output_dir.resolve() / "cache"))
    os.environ.setdefault("PYKEEN_HOME", str(args.output_dir.resolve() / "cache" / "pykeen"))
    try:
        for package, expected in {"pykeen": "1.11.1", "torch": "2.6.0"}.items():
            if version(package) != expected:
                raise RuntimeError(f"Expected {package}=={expected}; found {version(package)}")
        write_json(args.output_dir / "manifest.json", {
            "started_at": datetime.now(timezone.utc).isoformat(),
            "python": platform.python_version(), "platform": platform.platform(),
            "packages": {package: version(package) for package in ("pykeen", "torch", "numpy")},
            "script_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
            "input": "invented constants in this script only", "device": "cpu",
        })
        write_json(args.output_dir / "report.json", run(args.output_dir))
    except Exception as error:
        write_json(args.output_dir / "failure.json", {
            "status": "failed", "error": str(error), "traceback": traceback.format_exc(),
        })
        raise


if __name__ == "__main__":
    main()
