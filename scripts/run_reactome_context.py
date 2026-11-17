#!/usr/bin/env python3
"""Fixed, native PyKEEN two-arm Reactome comparison; never read assay outcomes.

The only unfrozen fitting entry points are an invented CPU check and an explicit
one-epoch resource check. Resource checks do not construct prediction queries.
Full fitting requires the separate, source/code/runtime-bound execution packet.
"""
from __future__ import annotations

import argparse
import gc
import hashlib
import importlib
import inspect
import json
import logging
import math
import os
import platform
import sys
import time
import traceback
from copy import deepcopy
from contextlib import contextmanager
from importlib.metadata import version
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(Path(__file__).resolve().parent))
from biograph_steward.client import digest, utcnow
from biograph_steward.file_utils import new_output, sha
from prepare_reactome_context_graphs import ARMS, RELATION, ordinary, validate_prepared_packet
from run_inmc_comparison import GENE, HEX, _pair_rows, _write, strict_json

FORMAT = "biograph-steward.reactome-context-run.v1"
EXECUTION_FORMAT = "biograph-steward.reactome-context-execution.v1"
SCORER = "scripts/score_reactome_context.py"
MODEL = {"embedding_dim": 32, "num_layers": 3, "num_bases": 4,
         "activation": "relu", "edge_dropout": None, "self_loop_dropout": 0.0}
TRAINING = {"num_epochs": 20, "batch_size": 4096, "num_negs_per_pos": 16,
            "optimizer": "Adam", "learning_rate": 0.001, "seeds": [17, 43, 101]}
PACKAGES = ("pykeen", "torch", "numpy", "scipy", "scikit-learn", "networkx")
SOURCE_MODULES = (
    "pykeen.models.base", "pykeen.models.nbase", "pykeen.models.unimodal.rgcn",
    "pykeen.nn.message_passing", "pykeen.nn.representation", "pykeen.nn.init",
    "pykeen.nn.utils", "pykeen.nn.modules", "pykeen.nn.weighting", "pykeen.losses", "pykeen.utils",
    "pykeen.training.training_loop", "pykeen.training.slcwa", "pykeen.training.callbacks",
    "pykeen.triples.triples_factory", "pykeen.triples.instances", "pykeen.predict",
    "pykeen.sampling.pseudo_type", "pykeen.sampling.negative_sampler", "pykeen.sampling.filtering",
    "torch.optim.adam", "torch.utils.data.dataloader", "torch.utils.data.sampler",
    "torch.nn.modules.dropout", "torch.nn.functional", "torch.nn.init",
)
IMPLEMENTATION_FILES = (
    "scripts/run_reactome_context.py", "scripts/run_inmc_comparison.py",
    "scripts/prepare_reactome_context_graphs.py", "scripts/prepare_inmc_graphs.py",
    "scripts/audit_pharos_inventory.py", "scripts/retrieve_pharos_inventory.py",
    "biograph_steward/client.py", "biograph_steward/file_utils.py", "biograph_steward/graph.py",
)
FINGERPRINTS = ("initial_parameters_sha256", "positive_batch_sha256",
                "negative_proposal_sha256", "negative_filter_mask_sha256", "accepted_negative_sha256")


def profile():
    return {"arms": list(ARMS), "model": deepcopy(MODEL), "training": deepcopy(TRAINING),
            "loss": "SoftplusLoss", "decoder": "DistMultInteraction",
            "batching": {"sampler": None, "num_workers": 0, "drop_last": False,
                         "automatic_memory_optimization": False},
            "optimizer_updates_per_arm_seed": 500, "planned_full_runs": 6,
            "planned_total_optimizer_updates": 3000}


def implementation_bindings():
    return {name: sha(ordinary(ROOT, name)) for name in IMPLEMENTATION_FILES}


def runtime_binding(device):
    """Bind installed distribution sources, not possibly different rendered docs."""
    if device not in {"cpu", "cuda:0"}:
        raise ValueError("Choose explicit cpu or cuda:0 device.")
    for name, expected in (("pykeen", "1.11.1"), ("torch", "2.6.0")):
        if version(name).split("+")[0] != expected:
            raise ValueError(f"Expected {name} {expected}; found {version(name)}.")
    import torch
    torch.set_num_threads(1)
    if device == "cuda:0" and not torch.cuda.is_available():
        raise ValueError("CUDA requested but unavailable; no silent CPU fallback.")
    return {"device": device, "python": platform.python_version(),
            "packages": {name: version(name) for name in PACKAGES}, "cuda_runtime": torch.version.cuda,
            "platform": platform.platform(), "machine": platform.machine(), "torch_threads": torch.get_num_threads(),
            "device_name": torch.cuda.get_device_name(0) if device == "cuda:0" else "cpu",
            "installed_sources_sha256": {
                name: sha(Path(inspect.getfile(importlib.import_module(name)))) for name in SOURCE_MODULES}}


def schedule(num_triples, *, mode):
    if type(num_triples) is not int or num_triples <= 0:
        raise ValueError("Supervision must be nonempty.")
    if mode == "synthetic_check":
        epochs, batch_size, seeds = 2, min(8, num_triples), TRAINING["seeds"]
    elif mode in {"resource_check", "full"}:
        if num_triples != 99394:
            raise ValueError("Real supervision denominator differs from the selected 99,394 triples.")
        epochs = 1 if mode == "resource_check" else TRAINING["num_epochs"]
        batch_size = TRAINING["batch_size"]
        seeds = [17] if mode == "resource_check" else TRAINING["seeds"]
    else:
        raise ValueError("Unknown execution mode.")
    updates = epochs * math.ceil(num_triples / batch_size)
    if mode == "full" and updates != 500:
        raise ValueError("Selected real-run budget must be exactly 500 optimizer updates.")
    return {"epochs": epochs, "batch_size": batch_size, "seeds": list(seeds),
            "updates_per_arm_seed": updates, "runs": len(ARMS) * len(seeds),
            "total_updates": len(ARMS) * len(seeds) * updates}


def graph_bindings(folder, packet):
    return {"graph_report_sha256": sha(ordinary(folder, "report.json")),
            "graph_input_files": packet["files"]}


def validate_inputs(packet):
    """Extra learner constraints also used on invented in-memory controls."""
    entities, relations = packet["entities"], packet["relations"]
    if (not entities or len(entities) != len(set(entities)) or
            len(relations) != len(set(relations)) or set(relations) != {
                "interacts", "reviewed_product_context", "pharos_cc_annotation", "go_is_a", RELATION}):
        raise ValueError("Shared ordered union vocabularies are incomplete or duplicated.")
    if set(packet["arms"]) != set(ARMS):
        raise ValueError("Exactly rgcn_baseline and rgcn_reactome are required.")
    candidates = _pair_rows(packet["candidates"], "candidate")
    development = _pair_rows(packet["development"], "development")
    masked = {tuple(r["original_genes"]) for r in _pair_rows(packet["masked_gene_pairs"], "masked")}
    candidate_pairs = {tuple(r["original_genes"]) for r in candidates}
    dev_pairs = {tuple(r["original_genes"]) for r in development}
    if candidate_pairs & dev_pairs or any(a == b for a, b in dev_pairs):
        raise ValueError("Development and candidate identities overlap or development has self-pairs.")
    if not (candidate_pairs | dev_pairs) <= masked or any(g not in entities for pair in masked for g in pair):
        raise ValueError("Candidate/development equivalence masks or union IDs differ.")
    base, added = (set(packet["arms"][arm]) for arm in ARMS)
    delta = added - base
    if not base <= added or not delta or any(r != RELATION for _, r, _ in delta):
        raise ValueError("Forbidden relation delta between the two graph arms.")
    supervision = set(packet["supervision"])
    if not supervision or len(supervision) != len(packet["supervision"]) or not supervision <= base:
        raise ValueError("Supervision is empty, duplicated or absent from an arm.")
    for rows in (packet["supervision"], *packet["arms"].values()):
        if len(rows) != len(set(rows)):
            raise ValueError("Duplicate adjacency triples.")
        for a, r, b in rows:
            shapes = {"interacts": bool(GENE.fullmatch(a) and GENE.fullmatch(b)),
                      "reviewed_product_context": bool(GENE.fullmatch(a) and b.startswith("UniProtKB:")),
                      "pharos_cc_annotation": a.startswith("UniProtKB:") and b.startswith("GO:"),
                      RELATION: a.startswith("UniProtKB:") and b.startswith("REACT:R-HSA-")}
            if a not in entities or b not in entities or not shapes.get(r, False):
                raise ValueError("Adjacency violates frozen relation endpoint types.")
            if r == "interacts" and tuple(sorted((a, b))) in masked:
                raise ValueError("Held-out literal/equivalent pair or reverse occurs in learner inputs.")
    if any(r != "interacts" for _, r, _ in supervision) or any(r == RELATION for _, r, _ in base):
        raise ValueError("Interaction-only supervision or baseline membership exclusion violated.")
    packet.update(candidates=candidates, development=development, masked_gene_pairs=sorted(masked))
    return packet


def validate_packet(graph):
    prepared = validate_prepared_packet(graph)
    selected = prepared["protocol"]
    selected_model = selected["model"]
    if (selected.get("arms") != list(ARMS) or any(selected_model.get(k) != v for k, v in MODEL.items())
            or selected_model.get("loss") != "SoftplusLoss"
            or selected_model.get("version") != "1.11.1" or selected_model.get("torch_version") != "2.6.0"
            or any(selected["training"].get(k) != v for k, v in TRAINING.items())):
        raise ValueError("Selected native model or fixed update budget differs from the adapter.")
    prepared["entities"] = [r["id"] for r in prepared["entities"]]
    prepared["relations"] = [r["id"] for r in prepared["relations"]]
    prepared["development"] = strict_json(ordinary(graph, "development_pairs.json").read_bytes())
    prepared["masked_gene_pairs"] = prepared["split"]["masked_gene_pairs"]
    result = validate_inputs(prepared)
    if len(result["candidates"]) != 3276:
        raise ValueError("Original 3,276 nominations must be preserved; later scoring fixes eligibility.")
    schedule(len(result["supervision"]), mode="full")
    result["graph_bindings"] = graph_bindings(graph, result)
    return result


def verify_seal(value):
    if (not isinstance(value, dict) or value.get("content_sha256") !=
            digest({k: v for k, v in value.items() if k != "content_sha256"})):
        raise ValueError("Receipt content seal does not match.")
    return value


def validate_complete_runs(results, expected_schedule):
    expected = {(arm, seed) for arm in ARMS for seed in expected_schedule["seeds"]}
    if (not isinstance(results, list) or len(results) != len(expected)
            or {(r.get("arm"), r.get("seed")) for r in results} != expected):
        raise ValueError("Incomplete or duplicate arm/seed runs.")
    for row in results:
        if (row.get("status") != "passed" or row.get("optimizer_steps") != expected_schedule["updates_per_arm_seed"]
                or row.get("optimizer_state_steps") != [expected_schedule["updates_per_arm_seed"]]
                or row.get("epochs_completed") != expected_schedule["epochs"]
                or len(row.get("losses", [])) != expected_schedule["epochs"]
                or not all(isinstance(v, (float, int)) and math.isfinite(v) for v in row["losses"])
                or any(not isinstance(row.get(key), str) or not HEX.fullmatch(row[key]) for key in FINGERPRINTS)):
            raise ValueError("Run lacks finite complete native training and audit fingerprints.")
    for seed in expected_schedule["seeds"]:
        pair = [r for r in results if r["seed"] == seed]
        if any(pair[0][key] != pair[1][key] for key in FINGERPRINTS):
            raise ValueError("Paired initialization, positive, negative or filter-mask fingerprints differ.")


def validate_proof(receipt, *, mode, packet=None, execution=None):
    verify_seal(receipt)
    if (receipt.get("format") != FORMAT or receipt.get("status") != "passed" or receipt.get("mode") != mode
            or receipt.get("profile") != profile() or receipt.get("implementation_sha256") != implementation_bindings()
            or receipt.get("candidate_outcomes_loaded") is not False):
        raise ValueError("Proof mode, status, profile or implementation binding differs.")
    runtime = receipt.get("execution", {})
    if (runtime.get("packages", {}).get("pykeen") != "1.11.1"
            or runtime.get("packages", {}).get("torch", "").split("+")[0] != "2.6.0"
            or set(runtime.get("installed_sources_sha256", {})) != set(SOURCE_MODULES)
            or any(not isinstance(v, str) or not HEX.fullmatch(v) for v in runtime["installed_sources_sha256"].values())):
        raise ValueError("Proof does not bind the required installed native runtime.")
    if mode == "synthetic_check":
        proof_packet = synthetic_fixture()
        expected = schedule(len(proof_packet["supervision"]), mode=mode)
        if (runtime.get("device") != "cpu" or receipt.get("biomedical_inputs_used") is not False
                or receipt.get("graph_bindings") != {"synthetic_fixture_sha256": digest(synthetic_fixture())}
                or receipt.get("transport_probe", {}).get("status") != "passed"
                or receipt.get("cache_probe", {}).get("status") != "passed"
                or receipt.get("query_pairs_scored") != len(synthetic_fixture()["candidates"]) + len(synthetic_fixture()["development"])):
            raise ValueError("Synthetic proof is incomplete or used non-invented inputs.")
        # CPU proof may precede a GPU resource check, but must exercise the same
        # PyKEEN implementation. Device/platform differences are allowed here.
        if execution is not None:
            pykeen_sources = {k: v for k, v in runtime["installed_sources_sha256"].items() if k.startswith("pykeen.")}
            actual_sources = {k: v for k, v in execution["installed_sources_sha256"].items() if k.startswith("pykeen.")}
            if pykeen_sources != actual_sources:
                raise ValueError("Synthetic proof installed PyKEEN sources differ from execution runtime.")
    elif mode == "resource_check":
        if packet is None or execution is None:
            raise ValueError("Resource proof requires exact graph and execution bindings.")
        expected = schedule(len(packet["supervision"]), mode=mode)
        proof_packet = packet
        if (receipt.get("graph_bindings") != packet["graph_bindings"] or runtime != execution
                or receipt.get("query_pairs_scored") != 0 or receipt.get("prediction_queries_constructed") is not False):
            raise ValueError("Resource proof graph/runtime differs or constructed prediction queries.")
    else:
        raise ValueError("Only synthetic and resource receipts are accepted as preflight proofs.")
    if receipt.get("schedule") != expected:
        raise ValueError("Proof native update schedule differs.")
    validate_complete_runs(receipt.get("arms"), expected)
    expected_proposals = len(proof_packet["supervision"]) * expected["epochs"] * 16
    for row in receipt["arms"]:
        if (row.get("supervision_triples") != len(proof_packet["supervision"])
                or row.get("adjacency_triples") != len(proof_packet["arms"][row["arm"]])
                or row.get("negative_proposals") != expected_proposals
                or type(row.get("negative_proposals_filtered")) is not int
                or not 0 <= row["negative_proposals_filtered"] <= expected_proposals
                or row.get("training_invalidated_cache") is not True):
            raise ValueError("Proof adjacency, supervision, proposals or cache evidence differs.")
        if mode == "resource_check" and any(k in row for k in ("scores_file", "score_rows", "query_sha256", "checkpoint")):
            raise ValueError("Resource proof contains prediction/checkpoint outputs.")
        if mode == "synthetic_check" and row.get("score_rows") != len(proof_packet["candidates"]) + len(proof_packet["development"]):
            raise ValueError("Synthetic proof lacks complete prediction rows.")
    return receipt


def validate_execution(packet, folder, execution):
    """Validate a separate freeze without editing the prepared graph packet."""
    frozen = verify_seal(strict_json(ordinary(folder, "execution.json").read_bytes()))
    if (frozen.get("format") != EXECUTION_FORMAT or frozen.get("fully_frozen") is not True
            or frozen.get("graph_bindings") != packet["graph_bindings"]
            or frozen.get("profile") != profile() or frozen.get("implementation_sha256") != implementation_bindings()
            or frozen.get("execution") != execution):
        raise ValueError("Execution freeze graph, code, profile or exact runtime differs.")
    scorer = frozen.get("scorer")
    if scorer != {"path": SCORER, "sha256": sha(ordinary(ROOT, SCORER))}:
        raise ValueError("Frozen scorer implementation differs.")
    if frozen.get("outcome_adapter_sha256") != sha(ordinary(ROOT, "biograph_steward/inmc_outcomes.py")):
        raise ValueError("Frozen assay outcome adapter differs.")
    proofs = frozen.get("proofs", {})
    if set(proofs) != {"synthetic_check", "resource_check"}:
        raise ValueError("Execution requires both synthetic and exact-device resource proofs.")
    for mode in ("synthetic_check", "resource_check"):
        path = "validation/" + mode + ".json"
        proof_path = ordinary(folder, path)
        if proofs[mode] != {"path": path, "sha256": sha(proof_path)}:
            raise ValueError("Execution proof file binding differs.")
        validate_proof(strict_json(proof_path.read_bytes()), mode=mode, packet=packet, execution=execution)
    return frozen


def parameter_hash(model):
    result = hashlib.sha256()
    for name, parameter in model.named_parameters():
        result.update(name.encode())
        hash_tensor(result, parameter)
    return result.hexdigest()


def hash_tensor(result, tensor):
    value = tensor.detach().cpu().contiguous()
    result.update(str((str(value.dtype), tuple(value.shape))).encode())
    result.update(value.numpy().tobytes())


def native_factory(rows, entity_ids, relation_ids):
    import numpy as np
    from pykeen.triples import TriplesFactory
    if len(rows) != len(set(rows)) or any(a not in entity_ids or b not in entity_ids or r not in relation_ids for a, r, b in rows):
        raise ValueError("Native conversion would drop unknown IDs or duplicate triples.")
    factory = TriplesFactory.from_labeled_triples(np.asarray(rows), entity_to_id=entity_ids,
            relation_to_id=relation_ids, compact_id=False, create_inverse_triples=False)
    expected = {(entity_ids[a], relation_ids[r], entity_ids[b]) for a, r, b in rows}
    if (factory.entity_to_id != entity_ids or factory.relation_to_id != relation_ids or factory.create_inverse_triples
            or factory.num_triples != len(rows) or set(map(tuple, factory.mapped_triples.tolist())) != expected):
        raise ValueError("Native factory changed union IDs or mapped triple set/count.")
    return factory


def adjacency(model):
    import torch
    rep = model.entity_representations[0]
    return torch.stack([rep.sources, rep.edge_types, rep.targets], dim=1).detach().cpu()


def _fit(packet, output, *, execution, mode):
    """The one native training path used by invented controls and fixed real runs."""
    import torch
    from pykeen.models import RGCN
    from pykeen.predict import predict_triples
    from pykeen.sampling import PseudoTypedNegativeSampler
    from pykeen.sampling.filtering import PythonSetFilterer
    from pykeen.training import SLCWATrainingLoop, TrainingCallback
    from pykeen.utils import set_random_seed

    torch.set_num_threads(1)
    device = execution["device"]
    settings = schedule(len(packet["supervision"]), mode=mode)
    entity_ids = {name: i for i, name in enumerate(packet["entities"])}
    relation_ids = {name: i for i, name in enumerate(packet["relations"])}
    factory = lambda rows: native_factory(rows, entity_ids, relation_ids)
    def mapped(rows):
        return torch.tensor([[entity_ids[a], relation_ids[r], entity_ids[b]] for a, r, b in rows], dtype=torch.long)
    supervision = factory(packet["supervision"])
    blocked_rows = set(packet["supervision"]) | {(b, r, a) for a, r, b in packet["supervision"]}
    for a, b in packet["masked_gene_pairs"]:
        blocked_rows.update(((a, "interacts", b), (b, "interacts", a)))
    blocked = mapped(sorted(blocked_rows))
    blocked_set = set(map(tuple, blocked.tolist()))
    positive_set = set(map(tuple, supervision.mapped_triples.tolist()))
    genes = {index for name, index in entity_ids.items() if GENE.fullmatch(name)}
    filterer = PythonSetFilterer(mapped_triples=blocked)
    if filterer(negative_batch=blocked).any():
        raise ValueError("Native exact filter did not block supervision and both held-out orientations.")

    class Observe(TrainingCallback):
        def __init__(self):
            super().__init__()
            self.steps, self.epochs, self.proposals, self.filtered = 0, 0, 0, 0
            self.initial = None
            self.hashes = {name: hashlib.sha256() for name in FINGERPRINTS[1:]}
            self.seen = set()

        def pre_batch(self, **unused):
            # train() resets parameters: construction-time fingerprints do not prove pairing.
            if self.initial is None:
                self.initial = parameter_hash(self.model)

        def post_batch(self, epoch, batch, **unused):
            positives = batch["positives"].detach().cpu()
            rows = set(map(tuple, positives.tolist()))
            if not rows <= positive_set or self.seen & rows or len(rows) != len(positives):
                raise ValueError("Native minibatch omits/duplicates supervision or contains context positives.")
            self.seen.update(rows)
            negatives = batch["negatives"].detach().cpu()
            mask = batch.get("masks")
            if mask is None or tuple(negatives.shape) != (len(positives), 16, 3):
                raise ValueError("Native sampler did not produce exactly 16 filtered proposals per positive.")
            mask = mask.detach().cpu()
            if tuple(mask.shape) != (len(positives), 16) or not torch.equal(filterer(negative_batch=negatives), mask):
                raise ValueError("Native negative filter mask differs from exact identity exclusions.")
            for a, r, b in negatives.reshape(-1, 3).tolist():
                if a not in genes or b not in genes or r != relation_ids["interacts"]:
                    raise ValueError("Typed proposals contain context entities or relations.")
            if blocked_set.intersection(map(tuple, negatives[mask].tolist())):
                raise ValueError("Accepted negative violates candidate/development/equivalence exclusions.")
            self.steps += 1
            self.proposals += mask.numel()
            self.filtered += int((~mask).sum())
            for name, value in (("positive_batch_sha256", positives), ("negative_proposal_sha256", negatives),
                                ("negative_filter_mask_sha256", mask), ("accepted_negative_sha256", negatives[mask])):
                self.hashes[name].update(str(epoch).encode())
                hash_tensor(self.hashes[name], value)

        def post_epoch(self, **unused):
            if self.seen != positive_set:
                raise ValueError("Native epoch did not visit every supervision triple exactly once.")
            self.epochs += 1
            self.seen.clear()

    results = []
    for seed in settings["seeds"]:
        for arm in ARMS:
            context = factory(packet["arms"][arm])
            model = RGCN(triples_factory=context, embedding_dim=32, num_layers=3, decomposition="bases",
                    decomposition_kwargs={"num_bases": 4}, activation="relu", edge_dropout=0.0,
                    self_loop_dropout=0.0, random_seed=seed, loss="softplus").to(device)
            rep = model.entity_representations[0]
            if (type(model.loss).__name__ != "SoftplusLoss" or type(model.interaction).__name__ != "DistMultInteraction"
                    or len(rep.layers) != 3 or any(layer.fwd.relation_representations.num_bases != 4 for layer in rep.layers)):
                raise ValueError("Native model resolved a different loss, decoder, layer or basis profile.")
            if any(layer.dropout.p != 0.0 for layer in rep.layers):
                raise ValueError("Native self-loop dropout violates the zero-dropout policy.")
            # Supported native disabled branch avoids adjacency-size-dependent RNG at p=0.
            rep.edge_dropout = None
            if not torch.equal(adjacency(model), context.mapped_triples):
                raise ValueError("Native R-GCN adjacency differs from the selected context arm.")
            loop = SLCWATrainingLoop(model=model, triples_factory=supervision, optimizer="Adam",
                    optimizer_kwargs={"lr": 0.001}, automatic_memory_optimization=False,
                    negative_sampler=PseudoTypedNegativeSampler,
                    negative_sampler_kwargs={"num_negs_per_pos": 16, "filterer": filterer})
            observer = Observe()
            set_random_seed(seed)
            if device == "cuda:0":
                torch.cuda.reset_peak_memory_stats()
                torch.cuda.synchronize()
            started = time.perf_counter()
            losses = loop.train(triples_factory=supervision, num_epochs=settings["epochs"],
                    batch_size=settings["batch_size"], sampler=None, use_tqdm=False, num_workers=0,
                    pin_memory=False, drop_last=False, checkpoint_directory=output / "checkpoints" / f"{arm}_{seed}",
                    callbacks=observer)
            if device == "cuda:0":
                torch.cuda.synchronize()
            elapsed = time.perf_counter() - started
            if losses is None or not all(math.isfinite(float(v)) for v in losses):
                raise ValueError("Native training did not finish with finite losses.")
            optimizer_steps = sorted({int(s["step"].item()) for s in loop.optimizer.state.values() if "step" in s})
            if type(loop.optimizer).__name__ != "Adam" or any(group["lr"] != 0.001 for group in loop.optimizer.param_groups):
                raise ValueError("Native optimizer differs from the selected Adam learning rate.")
            if rep.enriched_embeddings is not None or not torch.equal(adjacency(model), context.mapped_triples):
                raise ValueError("Training failed native cache invalidation or changed graph adjacency.")
            result = {"arm": arm, "seed": seed, "status": "passed", "optimizer_steps": observer.steps,
                      "optimizer_state_steps": optimizer_steps, "epochs_completed": observer.epochs,
                      "initial_parameters_sha256": observer.initial,
                      **{name: value.hexdigest() for name, value in observer.hashes.items()},
                      "negative_proposals": observer.proposals, "negative_proposals_filtered": observer.filtered,
                      "losses": [float(v) for v in losses], "adjacency_triples": context.num_triples,
                      "adjacency_sha256": digest(adjacency(model).tolist()), "supervision_triples": supervision.num_triples,
                      "parameter_count": sum(p.numel() for p in model.parameters()), "training_seconds": elapsed,
                      "training_invalidated_cache": True,
                      "max_cuda_memory_allocated_bytes": torch.cuda.max_memory_allocated() if device == "cuda:0" else None}
            # Resource mode does not even build development or candidate query tensors.
            if mode != "resource_check":
                prediction_rows = [("development", row) for row in packet["development"]]
                prediction_rows += [("candidate", row) for row in packet["candidates"]]
                query_rows = [(a, "interacts", b) for _, row in prediction_rows
                              for a, b in (row["original_genes"], list(reversed(row["original_genes"])))]
                queries = mapped(query_rows)
                with torch.inference_mode():
                    predictions = predict_triples(model=model, triples=queries, batch_size=1024)
                if not torch.equal(predictions.result.cpu(), queries) or not torch.isfinite(predictions.scores).all():
                    raise ValueError("Native query identity/order or finite prediction completeness differs.")
                scores = predictions.scores.detach().cpu().tolist()
                rows = []
                for index, (partition, row) in enumerate(prediction_rows):
                    forward, reverse = scores[2 * index:2 * index + 2]
                    if not math.isclose(forward, reverse, abs_tol=1e-5, rel_tol=1e-5):
                        raise ValueError("Native DistMult decoder violates paired orientation symmetry.")
                    rows.append({**row, "partition": partition, "forward": forward, "reverse": reverse,
                                 "score": (forward + reverse) / 2})
                name = f"{arm}_{seed}_scores.json"
                _write(output / name, rows)
                result.update(scores_file=name, score_rows=len(rows), query_sha256=digest(query_rows))
                if not torch.equal(adjacency(model), context.mapped_triples):
                    raise ValueError("Prediction inserted query edges into adjacency.")
            if mode == "full":
                name = f"{arm}_{seed}_state.pt"
                torch.save(model.state_dict(), output / name)
                result["checkpoint"] = name
            results.append(result)
            _write(output / f"{arm}_{seed}_receipt.json", result)
            del model, loop, observer, context, rep
            gc.collect()
            if device == "cuda:0":
                torch.cuda.empty_cache()
    validate_complete_runs(results, settings)
    return results, settings


def synthetic_fixture():
    """Invented ring plus shared pathway, a missing-context gene and isolated node."""
    genes = [f"ENSG{i:011d}" for i in range(1, 8)]
    products = ["UniProtKB:INVENTED1", "UniProtKB:INVENTED2"]
    entities = genes + products + ["GO:9000001", "REACT:R-HSA-9000001", "REACT:R-HSA-9000002"]
    supervision = [(genes[i], "interacts", genes[(i + 1) % 6]) for i in range(6)]
    supervision += [(b, r, a) for a, r, b in supervision]
    baseline = supervision + [(genes[0], "reviewed_product_context", products[0]),
                              (genes[2], "reviewed_product_context", products[1]),
                              (products[0], "pharos_cc_annotation", "GO:9000001")]
    memberships = [(p, RELATION, "REACT:R-HSA-9000001") for p in products]
    candidates = [{"id": "invented_shared_pathway", "original_genes": [genes[0], genes[2]], "self_pair": False},
                  {"id": "invented_missing_context", "original_genes": [genes[1], genes[6]], "self_pair": False}]
    development = [{"id": "invented_development", "original_genes": [genes[1], genes[3]], "self_pair": False}]
    return {"entities": entities, "relations": ["interacts", "reviewed_product_context", "pharos_cc_annotation", "go_is_a", RELATION],
            "supervision": sorted(supervision), "arms": {ARMS[0]: sorted(baseline), ARMS[1]: sorted(baseline + memberships)},
            "candidates": candidates, "development": development,
            "masked_gene_pairs": [r["original_genes"] for r in candidates + development] + [[genes[2], genes[4]]]}


def transport_probe():
    """Controlled positive weights in the selected 32-D/4-basis/3-layer model."""
    import torch
    from pykeen.models import RGCN
    packet = synthetic_fixture()
    entities = {name: i for i, name in enumerate(packet["entities"])}
    relations = {name: i for i, name in enumerate(packet["relations"])}
    contexts = {arm: native_factory(rows, entities, relations) for arm, rows in packet["arms"].items()}
    def controlled(arm, signal):
        model = RGCN(triples_factory=contexts[arm], embedding_dim=32, num_layers=3, decomposition="bases",
                decomposition_kwargs={"num_bases": 4}, activation="relu", edge_dropout=0.0,
                self_loop_dropout=0.0, loss="softplus", random_seed=19).to("cpu")
        rep = model.entity_representations[0]
        rep.edge_dropout = None
        with torch.no_grad():
            for parameter in model.parameters():
                parameter.zero_()
            rep.entity_embeddings._embeddings.weight[entities[signal]] = torch.arange(1, 33, dtype=torch.float)
            for layer in rep.layers:
                layer.self_loop.weight.copy_(torch.eye(32))
                for module in (layer.fwd, layer.bwd):
                    low_rank = module.relation_representations
                    low_rank.base._embeddings.weight[0].copy_(torch.eye(32).reshape(-1))
                    # Isolate the exact product/pathway route from ring-interaction
                    # routes while exercising both native message directions.
                    for relation in ("reviewed_product_context", RELATION):
                        low_rank.weight._embeddings.weight[relations[relation], 0] = 1
        model.post_parameter_update()
        model.eval()
        return model
    observations = {}
    for signal in ("REACT:R-HSA-9000001", "UniProtKB:INVENTED2"):
        models = {arm: controlled(arm, signal) for arm in ARMS}
        if parameter_hash(models[ARMS[0]]) != parameter_hash(models[ARMS[1]]):
            raise ValueError("Controlled transport parameters differ across arms.")
        values = {arm: [] for arm in ARMS}
        for arm, model in models.items():
            hooks = [layer.register_forward_hook(lambda module, args, value, arm=arm: values[arm].append(value.detach().clone()))
                     for layer in model.entity_representations[0].layers]
            with torch.no_grad():
                model.entity_representations[0](indices=None)
            for hook in hooks:
                hook.remove()
        observations[signal] = {}
        for index in range(3):
            layers = index + 1
            delta = {name: float((values[ARMS[1]][index][i] - values[ARMS[0]][index][i]).abs().max()) for name, i in entities.items()}
            required_hops = 2 if signal.startswith("REACT:") else 3
            if (delta["ENSG00000000001"] > 0) is not (layers >= required_hops):
                raise ValueError("Selected native bases model failed exact membership/product-link transport.")
            if signal.startswith("REACT:") and delta["UniProtKB:INVENTED1"] <= 0:
                raise ValueError("Membership relation failed native pathway-to-product message passing.")
            if delta["ENSG00000000007"] != 0 or delta["REACT:R-HSA-9000002"] != 0:
                raise ValueError("Isolated missing-context endpoints unexpectedly received transported signal.")
            observations[signal][str(layers)] = delta
    model = controlled(ARMS[1], "REACT:R-HSA-9000001")
    rep = model.entity_representations[0]
    with torch.no_grad():
        original = rep(indices=None).clone()
        rep.entity_embeddings._embeddings.weight[entities["REACT:R-HSA-9000001"]] *= 2
        model.eval()
        if not torch.equal(original, rep(indices=None)):
            raise ValueError("Native cache behavior differs from the installed-source audit.")
        model.post_parameter_update()
        if rep.enriched_embeddings is not None or not torch.equal(rep(indices=None), 2 * original):
            raise ValueError("Native lifecycle failed cache invalidation after parameter update.")
    return ({"status": "passed", "model": deepcopy(MODEL), "decomposition": "bases",
             "pathway_to_product_to_gene_hops": 2, "other_product_to_pathway_to_product_to_gene_hops": 3,
             "complete_gene_product_pathway_product_gene_hops": 4,
             "three_layers_claim_four_hop_transport": False, "maximum_absolute_differences": observations},
            {"status": "passed", "eval_alone_retains_cache": True, "native_post_parameter_update_invalidates_cache": True})


def _output(output, *inputs):
    # Reject symlink traversal before resolving an output path, including parent dirs.
    path = Path(output).absolute()
    if any(p.is_symlink() for p in (path, *path.parents)):
        raise ValueError("Output cannot traverse symlinks.")
    output = new_output(path, *inputs)
    os.environ.setdefault("PYSTOW_HOME", str(output / "cache"))
    os.environ.setdefault("PYKEEN_HOME", str(output / "cache" / "pykeen"))
    return output


def _report(output, packet, execution, mode, results, settings, **extra):
    report = {"format": FORMAT, "status": "passed", "created_at": utcnow(), "mode": mode,
              "profile": profile(), "execution": execution, "implementation_sha256": implementation_bindings(),
              "graph_bindings": packet["graph_bindings"], "schedule": settings, "arms": results,
              "candidate_outcomes_loaded": False, "biological_accuracy_measured": False,
              "biomedical_inputs_used": mode != "synthetic_check", "prediction_queries_constructed": mode != "resource_check",
              "query_pairs_scored": 0 if mode == "resource_check" else len(packet["candidates"]) + len(packet["development"]),
              "files": {p.name: sha(p) for p in sorted(output.iterdir()) if p.is_file()}, **extra}
    report["content_sha256"] = digest(report)
    _write(output / "report.json", report)
    return report


@contextmanager
def native_logging(output):
    """Retain native warnings with the attempt without flooding terminal output."""
    handler = logging.FileHandler(output / "runtime.log", encoding="utf-8")
    logger = logging.getLogger()
    logger.addHandler(handler)
    try:
        yield
    finally:
        handler.flush()
        logger.removeHandler(handler)
        handler.close()


def run_synthetic(output):
    output = _output(output)
    execution = runtime_binding("cpu")
    packet = validate_inputs(synthetic_fixture())
    packet["graph_bindings"] = {"synthetic_fixture_sha256": digest(synthetic_fixture())}
    try:
        _write(output / "manifest.json", {"mode": "synthetic_check", "execution": execution,
                "profile": profile(), "implementation_sha256": implementation_bindings(), "created_at": utcnow()})
        with native_logging(output):
            transport, cache = transport_probe()
            results, settings = _fit(packet, output, execution=execution, mode="synthetic_check")
        report = _report(output, packet, execution, "synthetic_check", results, settings,
                         transport_probe=transport, cache_probe=cache)
        validate_proof(report, mode="synthetic_check")
        return report
    except Exception as exc:
        _write(output / "failure.json", {"status": "failed", "mode": "synthetic_check", "error": str(exc), "traceback": traceback.format_exc()})
        raise


def run(graph, output, *, device, resource_check=False, execution_packet=None):
    packet = validate_packet(graph)
    if not resource_check and execution_packet is None:
        raise ValueError("Full fitting requires a separate frozen execution packet and exact-device resource proof.")
    output = _output(output, graph, *([execution_packet] if execution_packet else []))
    execution = runtime_binding(device)
    mode = "resource_check" if resource_check else "full"
    try:
        if not resource_check:
            # Late import avoids a module cycle and enforces the scoring handoff
            # before spending the six-fit budget, not only at outcome access.
            from freeze_reactome_context import validate_freeze
            validate_freeze(packet, execution_packet, execution)
        elif execution_packet is not None:
            raise ValueError("Resource mode cannot consume a final execution packet.")
        _write(output / "manifest.json", {"mode": mode, "execution": execution, "profile": profile(),
                "implementation_sha256": implementation_bindings(), "graph_bindings": packet["graph_bindings"], "created_at": utcnow()})
        with native_logging(output):
            results, settings = _fit(packet, output, execution=execution, mode=mode)
        return _report(output, packet, execution, mode, results, settings,
                       execution_packet_sha256=sha(ordinary(execution_packet, "execution.json")) if execution_packet else None)
    except Exception as exc:
        _write(output / "failure.json", {"status": "failed", "mode": mode, "graph_bindings": packet["graph_bindings"],
                "error": str(exc), "traceback": traceback.format_exc(), "candidate_outcomes_loaded": False})
        raise


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    action = parser.add_mutually_exclusive_group(required=True)
    action.add_argument("--validate", type=Path)
    action.add_argument("--synthetic-check", action="store_true")
    action.add_argument("--graph", type=Path)
    parser.add_argument("--output-dir", type=Path)
    parser.add_argument("--device", choices=("cpu", "cuda:0"))
    parser.add_argument("--resource-check", action="store_true")
    parser.add_argument("--execution-packet", type=Path)
    args = parser.parse_args()
    try:
        if args.validate:
            packet = validate_packet(args.validate)
            result = {"status": "validated_no_fitting", "schedule": schedule(len(packet["supervision"]), mode="full"),
                      "graph_bindings": packet["graph_bindings"]}
        elif args.synthetic_check:
            if not args.output_dir or args.device not in (None, "cpu") or args.resource_check or args.execution_packet:
                parser.error("Synthetic check requires --output-dir and uses CPU with invented inputs only.")
            result = run_synthetic(args.output_dir)
        else:
            if not args.output_dir or not args.device:
                parser.error("Graph execution requires --output-dir and --device.")
            result = run(args.graph, args.output_dir, device=args.device, resource_check=args.resource_check,
                         execution_packet=args.execution_packet)
    except (ValueError, OSError, RuntimeError) as exc:
        parser.exit(1, str(exc) + "\n")
    print(json.dumps({"status": result["status"], "mode": result.get("mode", "validate"), "schedule": result["schedule"]}, indent=2))


if __name__ == "__main__":
    main()
