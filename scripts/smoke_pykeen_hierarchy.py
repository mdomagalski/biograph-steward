#!/usr/bin/env python3
"""Exercise native R-GCN hierarchy reach on invented data, using CPU only.

No biomedical inputs, assay labels, pretrained weights, or network access are
accepted. This is a wiring test, not evidence that GO improves prediction.
"""

from __future__ import annotations

import argparse
import hashlib
import inspect
import json
import math
import os
import platform
import traceback
from datetime import datetime, timezone
from importlib.metadata import version
from pathlib import Path


def write_json(path: Path, value: object) -> None:
    with path.open("x", encoding="utf-8") as stream:
        json.dump(value, stream, indent=2, sort_keys=True, allow_nan=False)
        stream.write("\n")


def digest(value: object) -> str:
    return hashlib.sha256(json.dumps(value, sort_keys=True).encode()).hexdigest()


def fixture() -> dict:
    """All names and edges are invented; both arms share the union vocabulary."""
    entities = {name: i for i, name in enumerate([*(f"gene{i}" for i in range(6)),
                                                "product0", "go_child", "go_parent"])}
    relations = {"interacts": 0, "encodes": 1, "annotated_to": 2, "is_a": 3}
    supervision = [(a, "interacts", b) for i in range(6)
                   for a, b in ((f"gene{i}", f"gene{(i + 1) % 6}"),
                                (f"gene{(i + 1) % 6}", f"gene{i}"))]
    reserved = [(a, "interacts", b) for a, b in (("gene0", "gene2"), ("gene2", "gene0"),
                                               ("gene1", "gene3"), ("gene3", "gene1"))]
    context = [("gene0", "encodes", "product0"), ("product0", "annotated_to", "go_child")]
    hierarchy = [("go_child", "is_a", "go_parent")]
    return {"entities": entities, "relations": relations, "supervision": supervision,
            "reserved_and_development": reserved, "base_adjacency": supervision + context,
            "hierarchy_adjacency": supervision + context + hierarchy}


def parameter_hash(model) -> str:
    result = hashlib.sha256()
    for name, parameter in model.named_parameters():
        result.update(name.encode())
        result.update(parameter.detach().cpu().numpy().tobytes())
    return result.hexdigest()


def run(output: Path) -> dict:
    import numpy as np
    import torch
    from pykeen.models import RGCN
    from pykeen.nn.message_passing import RGCNLayer, RGCNRepresentation
    from pykeen.nn.utils import adjacency_tensor_to_stacked_matrix
    from pykeen.predict import predict_triples
    from pykeen.sampling import PseudoTypedNegativeSampler
    from pykeen.sampling.filtering import PythonSetFilterer
    from pykeen.training import SLCWATrainingLoop, TrainingCallback
    from pykeen.triples import TriplesFactory

    for package, expected in {"pykeen": "1.11.1", "torch": "2.6.0"}.items():
        if version(package) != expected:
            raise RuntimeError(f"Expected {package}=={expected}; found {version(package)}")
    torch.set_num_threads(1)
    data = fixture()
    entities, relations = data["entities"], data["relations"]

    def factory(rows):
        return TriplesFactory.from_labeled_triples(
            np.asarray(rows), entity_to_id=entities, relation_to_id=relations,
            compact_id=False, create_inverse_triples=False,
        )

    supervision = factory(data["supervision"])
    held_out = factory(data["reserved_and_development"]).mapped_triples
    contexts = {arm: factory(data[f"{arm}_adjacency"]) for arm in ("base", "hierarchy")}
    blocked = torch.cat([supervision.mapped_triples, held_out])
    blocked_set = set(map(tuple, blocked.tolist()))
    held_out_set = set(map(tuple, held_out.tolist()))
    for context in [supervision, *contexts.values()]:
        assert context.entity_to_id == entities and context.relation_to_id == relations
        assert not context.create_inverse_triples
        assert not held_out_set.intersection(map(tuple, context.mapped_triples.tolist()))

    def adjacency(model):
        rep = model.entity_representations[0]
        return torch.stack([rep.sources, rep.edge_types, rep.targets], dim=1)

    def controlled(arm, layers, *, modules=("fwd", "bwd")):
        # Native block decomposition allows an exact transport probe. This is
        # separate from the randomly initialized, trained basis models below.
        model = RGCN(triples_factory=contexts[arm], embedding_dim=2, num_layers=layers,
                     decomposition="block", decomposition_kwargs={"num_blocks": 1},
                     edge_dropout=0.0, self_loop_dropout=0.0, use_bias=False,
                     random_seed=19).to("cpu")
        rep = model.entity_representations[0]
        with torch.no_grad():
            for parameter in model.parameters():
                parameter.zero_()
            # Only the parent carries an initial signal. Its directed ontology
            # path must travel backward to reach the gene.
            rep.entity_embeddings._embeddings.weight[entities["go_parent"]] = torch.tensor([1.0, 2.0])
            for layer in rep.layers:
                layer.self_loop.weight.copy_(torch.eye(2))
                for name in modules:
                    blocks = getattr(layer, name).blocks
                    blocks.copy_(torch.eye(2).expand_as(blocks))
        model.post_parameter_update()
        model.eval()
        return model

    transport = {}
    for layers in (1, 2, 3):
        models = {arm: controlled(arm, layers) for arm in contexts}
        assert parameter_hash(models["base"]) == parameter_hash(models["hierarchy"])
        with torch.no_grad():
            representations = {arm: model.entity_representations[0](indices=None).clone()
                               for arm, model in models.items()}
        differences = {name: float((representations["hierarchy"][index] -
                                   representations["base"][index]).abs().max())
                       for name, index in entities.items()}
        assert (differences["gene0"] > 0) == (layers == 3)
        if layers == 1:
            assert differences["go_child"] > 0 and differences["product0"] == 0
        if layers == 2:
            assert differences["product0"] > 0
        transport[str(layers)] = {"maximum_absolute_difference_by_entity": differences,
                                  "parameters_equal_across_arms": True,
                                  "parameters_sha256": parameter_hash(models["base"])}
    module_directions = {}
    for name in ("fwd", "bwd"):
        model = controlled("hierarchy", 3, modules=(name,))
        with torch.no_grad():
            gene = model.entity_representations[0](indices=None)[entities["gene0"]]
        signal = bool(torch.count_nonzero(gene).item())
        # In this pinned implementation A[source,target] @ X sends target to
        # source in `fwd`; `bwd` transposes the edge indices. Names alone are not
        # a reliable guide to actual message direction.
        assert signal == (name == "fwd")
        module_directions[name] = {"parent_signal_reaches_gene": signal,
                                   "observed_message_direction": "target_to_source" if signal else "source_to_target"}

    # PyKEEN caches enriched representations. eval() alone does not invalidate
    # a populated cache. Use the native post_parameter_update lifecycle hook.
    cached_model = controlled("hierarchy", 3)
    rep = cached_model.entity_representations[0]
    with torch.no_grad():
        original = rep(indices=None).clone()
        rep.entity_embeddings._embeddings.weight[entities["go_parent"]] *= 2
        cached_model.eval()
        stale = rep(indices=None).clone()
        assert torch.equal(original, stale)
        cached_model.post_parameter_update()
        assert rep.enriched_embeddings is None
        fresh = rep(indices=None).clone()
        assert torch.equal(fresh, 2 * original)
    cache_check = {"eval_alone_retains_cache": True,
                   "native_post_parameter_update_invalidates_cache": True,
                   "parameter_change_visible_after_invalidation": True}

    filterer = PythonSetFilterer(mapped_triples=blocked)
    assert not filterer(negative_batch=held_out).any()

    class Observe(TrainingCallback):
        def __init__(self):
            super().__init__()
            self.batches = []
            self.negatives = []
            self.initial_parameters_sha256 = None
            self.removed_held_out = 0

        def pre_batch(self, **kwargs):
            if self.initial_parameters_sha256 is None:
                self.initial_parameters_sha256 = parameter_hash(self.model)

        def post_batch(self, epoch, batch, **kwargs):
            rows = sorted(batch["positives"].tolist())
            assert rows == sorted(supervision.mapped_triples.tolist())
            self.batches.append(rows)
            accepted = batch["negatives"][batch["masks"]]
            assert not blocked_set.intersection(map(tuple, accepted.tolist()))
            assert set(accepted[:, [0, 2]].reshape(-1).tolist()) <= set(range(6))
            self.negatives.append(accepted.tolist())
            self.removed_held_out += sum(tuple(row) in held_out_set
                                        for row in batch["negatives"].reshape(-1, 3).tolist())

    trained = {}
    for arm, context in contexts.items():
        model = RGCN(triples_factory=context, embedding_dim=8, num_layers=3,
                     decomposition="bases", decomposition_kwargs={"num_bases": 2},
                     edge_dropout=0.0, self_loop_dropout=0.0, random_seed=17).to("cpu")
        assert torch.equal(adjacency(model), context.mapped_triples)
        observer = Observe()
        loop = SLCWATrainingLoop(
            model=model, triples_factory=supervision, optimizer="Adam",
            optimizer_kwargs={"lr": 0.001}, automatic_memory_optimization=False,
            negative_sampler=PseudoTypedNegativeSampler,
            negative_sampler_kwargs={"num_negs_per_pos": 16, "filterer": filterer},
        )
        torch.manual_seed(17)
        losses = loop.train(triples_factory=supervision, num_epochs=2,
                            batch_size=supervision.num_triples, sampler="schlichtkrull",
                            use_tqdm=False, num_workers=0, pin_memory=False,
                            checkpoint_directory=output / "checkpoints" / arm, callbacks=observer)
        assert len(observer.batches) == 2 and observer.removed_held_out > 0
        assert losses and all(math.isfinite(loss) for loss in losses)
        assert {int(state["step"].item()) for state in loop.optimizer.state.values()
                if "step" in state} == {2}
        assert model.entity_representations[0].enriched_embeddings is None
        before = adjacency(model).clone()
        scores = predict_triples(model=model, triples=held_out, batch_size=2)
        assert torch.equal(scores.result, held_out) and torch.isfinite(scores.scores).all()
        assert torch.equal(before, adjacency(model))
        assert not held_out_set.intersection(map(tuple, adjacency(model).tolist()))
        trained[arm] = {"layers": 3, "adjacency_triples": context.num_triples,
                        "supervision_triples": supervision.num_triples, "optimizer_steps": 2,
                        "initial_parameters_sha256": observer.initial_parameters_sha256,
                        "positive_batches_sha256": digest(observer.batches),
                        "accepted_negatives_sha256": digest(observer.negatives),
                        "reserved_or_dev_negative_proposals_removed": observer.removed_held_out,
                        "losses": losses, "synthetic_scores": scores.scores.tolist(),
                        "adjacency_sha256": digest(before.tolist()),
                        "prediction_did_not_add_query_edges": True,
                        "training_invalidated_cache": True}
    assert trained["base"]["initial_parameters_sha256"] == trained["hierarchy"]["initial_parameters_sha256"]
    assert trained["base"]["positive_batches_sha256"] == trained["hierarchy"]["positive_batches_sha256"]
    source_paths = {name: Path(inspect.getfile(obj)) for name, obj in {
        "rgcn_model": RGCN, "rgcn_representation_and_layer": RGCNRepresentation,
        "training_loop": SLCWATrainingLoop, "prediction": predict_triples,
        "triples_factory": TriplesFactory, "exact_filter": PythonSetFilterer,
        "stacked_adjacency": adjacency_tensor_to_stacked_matrix,
    }.items()}
    return {"format": "biograph-steward.pykeen-hierarchy-smoke.v1", "status": "passed",
            "purpose": "engineering_only", "biomedical_inputs_used": False,
            "biological_quality_measured": False, "device": "cpu", "fixture": data,
            "transport_probe": transport, "module_direction_probe": module_directions,
            "cache_check": cache_check, "trained_arms": trained,
            "accepted_negative_batches_identical": trained["base"]["accepted_negatives_sha256"] ==
                trained["hierarchy"]["accepted_negatives_sha256"],
            "sources": {name: {"path": str(path), "sha256": hashlib.sha256(path.read_bytes()).hexdigest()}
                        for name, path in source_paths.items()},
            "literature_and_official_code": [
                "https://arxiv.org/abs/1703.06103",
                "https://pmc.ncbi.nlm.nih.gov/articles/PMC9680895/",
                "https://raw.githubusercontent.com/pykeen/pykeen/v1.11.1/src/pykeen/nn/message_passing.py",
                "https://github.com/pykeen/pykeen/blob/v1.11.1/src/pykeen/nn/utils.py",
                "https://github.com/pykeen/pykeen/blob/v1.11.1/src/pykeen/models/unimodal/rgcn.py",
            ],
            "limitations": [
                "Three layers provide a receptive field for this exact path; they are not proven optimal.",
                "The transport probe uses controlled identity matrices, zero bias, and a parent-only signal.",
                "The two training arms use identical initialization and supervision, native basis RGCN, and two CPU updates.",
                "Equal seeds do not guarantee equal negative proposals when adjacency changes RNG consumption.",
                "Inverse messages are an encoder mechanism, not inverse biological assertion semantics.",
                "No biological performance, assay reference, protocol freeze, scaling or GPU was evaluated.",
            ]}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-dir", type=Path, required=True)
    args = parser.parse_args()
    args.output_dir.mkdir(parents=True, exist_ok=False)
    os.environ.setdefault("PYSTOW_HOME", str(args.output_dir.resolve() / "cache"))
    os.environ.setdefault("PYKEEN_HOME", str(args.output_dir.resolve() / "cache" / "pykeen"))
    try:
        write_json(args.output_dir / "manifest.json", {
            "started_at": datetime.now(timezone.utc).isoformat(), "python": platform.python_version(),
            "platform": platform.platform(),
            "packages": {package: version(package) for package in ("pykeen", "torch", "numpy")},
            "script_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
            "input": "invented constants in this script only", "device": "cpu",
        })
        report = run(args.output_dir)
        write_json(args.output_dir / "report.json", report)
        print(json.dumps({"status": report["status"], "biological_quality_measured": False,
                          "gene_signal_first_reached_at_layers": 3, "output": str(args.output_dir)}))
    except Exception as error:
        write_json(args.output_dir / "failure.json", {
            "status": "failed", "error": str(error), "traceback": traceback.format_exc(),
        })
        raise


if __name__ == "__main__":
    main()
