#!/usr/bin/env python3
"""Train the frozen INMC graph comparison with native PyKEEN; never read outcomes.

Resource smoke is permitted before the final freeze and scores development pairs
only. Full execution requires a sealed graph packet and its bound validation
receipts. Scores remain unlabelled; assay materialization is a separate step.
"""
from __future__ import annotations

import argparse
import csv
import gc
import hashlib
import io
import json
import logging
import math
import os
import platform
import re
import resource
import sys
import time
import traceback
from datetime import datetime, timezone
from importlib.metadata import version
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from biograph_steward.client import digest
from biograph_steward.file_utils import new_output, sha

FORMAT = "biograph-steward.inmc-comparison-predictions.v1"
MODEL = {"embedding_dim": 32, "num_layers": 3, "num_bases": 4,
         "activation": "relu", "edge_dropout": 0.0, "self_loop_dropout": 0.0}
TRAINING = {"num_epochs": 20, "batch_size": 4096, "num_negs_per_pos": 16,
            "optimizer": "Adam", "learning_rate": 0.001, "seeds": [17, 43, 101]}
RELATIONS = {"interacts", "reviewed_product_context", "pharos_cc_annotation", "go_is_a"}
REQUIRED = {"protocol.json", "entities.json", "relations.json", "supervision.tsv",
            "development_pairs.json", "candidates.json", "split.json",
            *(f"arms/{name}.tsv" for name in ("scaffold", "baseline", "enriched"))}
HEX = re.compile(r"[0-9a-f]{64}\Z")
GENE = re.compile(r"ENSG[0-9]+\Z")
SCORER = "biograph_steward/inmc_outcomes.py"
ASSAY_CONTRACT = "docs/evaluations/inmc_assay_contract_20261022.json"
PACKAGES = ("pykeen", "torch", "numpy", "scipy", "scikit-learn")


def strict_json(raw: bytes):
    def pairs(items):
        result = {}
        for key, value in items:
            if key in result:
                raise ValueError(f"Duplicate JSON key: {key}")
            result[key] = value
        return result

    def constant(value):
        raise ValueError(f"Nonfinite JSON constant: {value}")

    return json.loads(raw.decode("utf-8"), object_pairs_hook=pairs, parse_constant=constant)


def _write(path: Path, value):
    with path.open("x", encoding="utf-8") as handle:
        json.dump(value, handle, indent=2, sort_keys=True, allow_nan=False)
        handle.write("\n")


def _pair(value):
    if (not isinstance(value, list) or len(value) != 2 or
            any(not isinstance(gene, str) or not GENE.fullmatch(gene) for gene in value)):
        raise ValueError("Pairs must retain two original ENSG identifiers.")
    return tuple(sorted(value))


def _pair_rows(value, name):
    if not isinstance(value, list) or not value:
        raise ValueError(f"{name} must contain a nonempty pair list.")
    output, seen, identifiers = [], set(), set()
    for index, item in enumerate(value):
        if isinstance(item, dict):
            forbidden = {"label", "labels", "score", "scores", "outcome", "outcomes", "freq",
                         "score_assay1", "score_assay2", "score_assay3"}
            if forbidden.intersection(item):
                raise ValueError("Outcome fields are not permitted in prediction inputs.")
            pair = _pair(item.get("original_genes"))
            identifier = item.get("id", f"{name}_{index}")
            if "self_pair" in item and item["self_pair"] is not (pair[0] == pair[1]):
                raise ValueError("Incorrect self-pair flag.")
        else:
            pair, identifier = _pair(item), f"{name}_{index}"
        if not isinstance(identifier, str) or not identifier or identifier in identifiers or pair in seen:
            raise ValueError("Duplicate pair or missing/duplicate pair identifier.")
        output.append({"id": identifier, "original_genes": list(pair), "self_pair": pair[0] == pair[1]})
        identifiers.add(identifier)
        seen.add(pair)
    return output


def _triples(raw: bytes, entities: set[str], relations: set[str]):
    reader = csv.reader(io.StringIO(raw.decode("utf-8"), newline=""), delimiter="\t", strict=True)
    if next(reader, None) != ["subject", "predicate", "object"]:
        raise ValueError("Triple table requires subject, predicate, object columns.")
    result = []
    for row in reader:
        if len(row) != 3 or any(not text or text != text.strip() for text in row):
            raise ValueError("Malformed triple table row.")
        subject, predicate, obj = row
        if subject not in entities or obj not in entities or predicate not in relations:
            raise ValueError("Triple contains an undeclared entity or relation.")
        shapes = {
            "interacts": bool(GENE.fullmatch(subject) and GENE.fullmatch(obj)),
            "reviewed_product_context": bool(GENE.fullmatch(subject) and obj.startswith("UniProtKB:")),
            "pharos_cc_annotation": subject.startswith("UniProtKB:") and obj.startswith("GO:"),
            "go_is_a": subject.startswith("GO:") and obj.startswith("GO:"),
        }
        if not shapes.get(predicate, False):
            raise ValueError("Triple violates the frozen relation endpoint types.")
        result.append(tuple(row))
    if not result or len(result) != len(set(result)):
        raise ValueError("Triple table is empty or has duplicate triples.")
    return sorted(result)


def validate_packet(folder: Path, *, resource_smoke: bool = False):
    """Verify exact bytes and masks before importing ML packages or creating output."""
    folder = Path(folder)
    if folder.is_symlink() or not folder.is_dir():
        raise ValueError("Graph packet must be an ordinary directory.")
    folder = folder.resolve()
    report_path = folder / "report.json"
    if report_path.is_symlink():
        raise ValueError("Packet report cannot be a symlink.")
    report_raw = report_path.read_bytes()
    report = strict_json(report_raw)
    if not isinstance(report, dict) or report.get("content_sha256") != digest(
            {key: value for key, value in report.items() if key != "content_sha256"}):
        raise ValueError("Graph report content seal does not match.")
    files = report.get("files")
    if not isinstance(files, dict) or not REQUIRED.issubset(files):
        raise ValueError("Graph packet lacks required bound files.")
    contents = {}
    for name, expected in files.items():
        if not isinstance(name, str) or not isinstance(expected, str) or not HEX.fullmatch(expected):
            raise ValueError("Malformed packet file inventory.")
        relative = Path(name)
        if relative.is_absolute() or ".." in relative.parts or name == "report.json":
            raise ValueError("Unsafe packet member path.")
        path = folder / relative
        if any((folder / Path(*relative.parts[:i])).is_symlink() for i in range(1, len(relative.parts) + 1)):
            raise ValueError("Packet members cannot traverse symlinks.")
        raw = path.read_bytes()
        if hashlib.sha256(raw).hexdigest() != expected:
            raise ValueError(f"Packet file fingerprint differs: {name}")
        contents[name] = raw
    protocol = strict_json(contents["protocol.json"])
    if not isinstance(protocol, dict) or type(protocol.get("fully_frozen")) is not bool:
        raise ValueError("Protocol must declare a boolean fully_frozen state.")
    if protocol.get("model") != MODEL or protocol.get("training") != TRAINING:
        raise ValueError("Protocol differs from this runner's fixed model/update budget.")
    if not resource_smoke:
        if not protocol["fully_frozen"] or protocol.get("runner_sha256") != sha(Path(__file__)):
            raise ValueError("Full execution requires a frozen protocol bound to this runner.")
        scoring = protocol.get("scoring_implementation")
        root = Path(__file__).resolve().parents[1]
        if scoring != {"path": SCORER, "sha256": sha(root / SCORER)}:
            raise ValueError("Frozen scoring implementation does not match the current outcome adapter.")
        assay_sha = protocol.get("assay_contract_sha256")
        if ("assay_contract.json" not in contents or assay_sha != files["assay_contract.json"] or
                assay_sha != sha(root / ASSAY_CONTRACT)):
            raise ValueError("Frozen assay contract differs from the current declared contract.")
        execution = protocol.get("execution")
        if (not isinstance(execution, dict) or set(execution) != {"device", "python", "packages", "cuda_runtime"} or
                execution.get("device") not in {"cpu", "cuda:0"} or
                not isinstance(execution.get("packages"), dict) or set(execution["packages"]) != set(PACKAGES)):
            raise ValueError("Frozen execution runtime/device binding is incomplete.")
        for name in ("hierarchy_smoke", "resource_smoke"):
            binding = protocol.get(name, {})
            member = f"validation/{name}.json"
            if (not isinstance(binding, dict) or binding.get("status") != "passed" or
                    member not in contents or binding.get("report_sha256") != files[member]):
                raise ValueError(f"Full execution requires the bound {name} receipt.")
            receipt = strict_json(contents[member])
            if receipt.get("status") != "passed":
                raise ValueError(f"{name} receipt did not pass.")
            if name == "resource_smoke":
                if receipt.get("runner_sha256") != sha(Path(__file__)) or receipt.get("resource_smoke") is not True:
                    raise ValueError("Resource smoke does not bind this runner.")
                if receipt.get("graph_input_files") != {
                        key: files[key] for key in REQUIRED if key != "protocol.json"}:
                    raise ValueError("Resource smoke was run against different graph inputs.")
                if receipt.get("execution") != execution:
                    raise ValueError("Frozen execution runtime differs from the resource smoke.")
    entity_rows, relation_rows = (strict_json(contents[name]) for name in ("entities.json", "relations.json"))
    if (not isinstance(entity_rows, list) or not entity_rows or
            any(not isinstance(row, dict) or not isinstance(row.get("id"), str) or
                not row["id"] or not isinstance(row.get("type"), str) for row in entity_rows)):
        raise ValueError("Malformed entity inventory.")
    entities = sorted(row["id"] for row in entity_rows)
    if len(set(entities)) != len(entities):
        raise ValueError("Duplicate entity identifier.")
    if (not isinstance(relation_rows, list) or
            any(not isinstance(row, dict) or not isinstance(row.get("id"), str) for row in relation_rows)):
        raise ValueError("Malformed relation inventory.")
    relations = sorted(row["id"] for row in relation_rows)
    if set(relations) != RELATIONS or len(relations) != len(RELATIONS):
        raise ValueError("Relations differ from the fixed graph projection.")
    tables = {name: _triples(contents[name], set(entities), set(relations))
              for name in ["supervision.tsv", *(f"arms/{arm}.tsv" for arm in ("scaffold", "baseline", "enriched"))]}
    supervision = tables["supervision.tsv"]
    if any(relation != "interacts" for _, relation, _ in supervision):
        raise ValueError("Supervision may contain HuRI interaction pairs only.")
    arms = {arm: tables[f"arms/{arm}.tsv"] for arm in ("scaffold", "baseline", "enriched")}
    if set(arms["scaffold"]) != set(supervision):
        raise ValueError("Scaffold adjacency must equal the shared supervision.")
    for smaller, larger, allowed in (("scaffold", "baseline", {"reviewed_product_context", "pharos_cc_annotation"}),
                                    ("baseline", "enriched", {"go_is_a"})):
        addition = set(arms[larger]) - set(arms[smaller])
        if not set(arms[smaller]).issubset(arms[larger]) or not addition or any(r not in allowed for _, r, _ in addition):
            raise ValueError("Graph arms do not represent the fixed additive comparison.")
    candidates = _pair_rows(strict_json(contents["candidates.json"]), "candidate")
    development = _pair_rows(strict_json(contents["development_pairs.json"]), "development")
    split = strict_json(contents["split.json"])
    if not isinstance(split, dict):
        raise ValueError("Malformed split contract.")
    masked_rows = _pair_rows(split.get("masked_gene_pairs"), "masked")
    masked_pairs = {tuple(row["original_genes"]) for row in masked_rows}
    candidate_pairs = {tuple(row["original_genes"]) for row in candidates}
    dev_pairs = {tuple(row["original_genes"]) for row in development}
    if candidate_pairs & dev_pairs or any(a == b for a, b in dev_pairs):
        raise ValueError("Development overlaps candidates or includes self-pairs.")
    if any(gene not in entities for row in candidates + development for gene in row["original_genes"]):
        raise ValueError("Candidate/development gene absent from union vocabulary.")
    if not (candidate_pairs | dev_pairs).issubset(masked_pairs):
        raise ValueError("Shared-product equivalence mask omits literal held-out pairs.")
    if any(gene not in entities for pair in masked_pairs for gene in pair):
        raise ValueError("Masked-equivalent gene absent from union vocabulary.")
    reserved = masked_pairs
    for rows in [supervision, *arms.values()]:
        if any(tuple(sorted((a, b))) in reserved for a, relation, b in rows if relation == "interacts"):
            raise ValueError("Held-out pair or reverse is present in learner inputs.")
    return {"report": report, "report_sha256": hashlib.sha256(report_raw).hexdigest(),
            "protocol": protocol, "files": files, "entities": entities, "relations": relations,
            "supervision": supervision, "arms": arms, "candidates": candidates, "development": development,
            "masked_gene_pairs": sorted(masked_pairs)}


def check_execution(protocol, execution):
    if protocol.get("execution") != execution:
        raise ValueError("Actual runtime/device differs from the frozen resource-checked execution contract.")


def run(graph: Path, output: Path, *, device: str, resource_smoke: bool = False):
    packet = validate_packet(graph, resource_smoke=resource_smoke)
    for package, expected in {"pykeen": "1.11.1", "torch": "2.6.0"}.items():
        if version(package).split("+")[0] != expected:
            raise ValueError(f"Expected {package} {expected}; found {version(package)}.")
    if device not in {"cpu", "cuda", "cuda:0"}:
        raise ValueError("Choose explicit cpu, cuda or cuda:0 device.")
    import numpy as np
    import torch
    device = "cuda:0" if device in {"cuda", "cuda:0"} else "cpu"
    execution = {"device": device, "python": platform.python_version(),
                 "packages": {name: version(name) for name in PACKAGES}, "cuda_runtime": torch.version.cuda}
    if not resource_smoke:
        check_execution(packet["protocol"], execution)
    if device.startswith("cuda") and not torch.cuda.is_available():
        raise ValueError("CUDA requested but unavailable; no silent CPU fallback.")
    output = new_output(output, graph)
    os.environ.setdefault("PYSTOW_HOME", str(output / "cache"))
    os.environ.setdefault("PYKEEN_HOME", str(output / "cache" / "pykeen"))
    from pykeen.models import ComplEx, RGCN
    from pykeen.predict import predict_triples
    from pykeen.sampling import PseudoTypedNegativeSampler
    from pykeen.sampling.filtering import PythonSetFilterer
    from pykeen.training import SLCWATrainingLoop, TrainingCallback
    from pykeen.triples import TriplesFactory
    from pykeen.utils import set_random_seed

    handler = logging.FileHandler(output / "runtime.log", encoding="utf-8")
    logging.getLogger("pykeen").addHandler(handler)
    torch.set_num_threads(1)
    entity_ids = {name: index for index, name in enumerate(packet["entities"])}
    relation_ids = {name: index for index, name in enumerate(packet["relations"])}

    def factory(rows):
        result = TriplesFactory.from_labeled_triples(np.asarray(rows), entity_to_id=entity_ids,
                relation_to_id=relation_ids, compact_id=False, create_inverse_triples=False)
        if result.entity_to_id != entity_ids or result.relation_to_id != relation_ids:
            raise ValueError("Native factory changed the shared vocabulary.")
        return result

    def mapped(rows):
        return torch.tensor([[entity_ids[a], relation_ids[r], entity_ids[b]] for a, r, b in rows], dtype=torch.long)

    supervision = factory(packet["supervision"])
    blocked_rows = set(packet["supervision"])
    blocked_rows |= {(b, r, a) for a, r, b in packet["supervision"]}
    for a, b in packet["masked_gene_pairs"]:
        blocked_rows.update(((a, "interacts", b), (b, "interacts", a)))
    blocked = mapped(sorted(blocked_rows))
    blocked_set = set(map(tuple, blocked.tolist()))
    positive_set = set(map(tuple, supervision.mapped_triples.tolist()))
    gene_ids = {index for gene, index in entity_ids.items() if GENE.fullmatch(gene)}
    filterer = PythonSetFilterer(mapped_triples=blocked)
    if filterer(negative_batch=blocked).any():
        raise ValueError("Upstream filter failed the held-out exclusion probe.")
    epochs = 1 if resource_smoke else TRAINING["num_epochs"]
    batch_size = min(TRAINING["batch_size"], supervision.num_triples)
    expected_steps = epochs * math.ceil(supervision.num_triples / batch_size)
    seeds = [17] if resource_smoke else TRAINING["seeds"]
    arms = ["rgcn_baseline", "rgcn_enriched"] if resource_smoke else [
        "rgcn_scaffold", "rgcn_baseline", "rgcn_enriched", "complex_scaffold"]
    bindings = {"graph_report_sha256": packet["report_sha256"],
                "graph_input_files": {key: packet["files"][key] for key in REQUIRED if key != "protocol.json"},
                "protocol_sha256": packet["files"]["protocol.json"], "runner_sha256": sha(Path(__file__))}
    started = time.perf_counter()
    manifest = {"format": FORMAT, "started_at": datetime.now(timezone.utc).isoformat(), **bindings,
                "resource_smoke": resource_smoke, "device": device, "python": platform.python_version(),
                "platform": platform.platform(), "packages": execution["packages"], "execution": execution,
                "cuda_runtime": torch.version.cuda, "model": MODEL, "training": TRAINING,
                "effective_epochs": epochs, "effective_batch_size": batch_size, "seeds": seeds,
                "candidate_outcomes_loaded": False, "candidate_pairs_scored": not resource_smoke,
                "loss": "SoftplusLoss", "sampler": None,
                "sampler_note": "Native BatchedSLCWAInstances preserves isolated entities; pinned graph-based sampling can choose zero-degree nodes.",
                "effective_rgcn_edge_dropout": None,
                "dropout_note": "Pinned PyKEEN 1.11.1 draws unused random masks at 0.0; the native None branch disables edge dropout without changing the zero-probability self-loop modules.",
                "automatic_memory_optimization": False, "score_aggregation": "mean_of_forward_and_reverse"}
    _write(output / "manifest.json", manifest)
    _write(output / "vocabulary.json", {"entity_to_id": entity_ids, "relation_to_id": relation_ids})
    results = []
    initial_by_seed, batches_by_seed = {}, {}
    try:
        for seed in seeds:
            for name in arms:
                is_rgcn = name.startswith("rgcn_")
                context = factory(packet["arms"][name.split("_", 1)[1]])
                kwargs = {"triples_factory": context, "embedding_dim": MODEL["embedding_dim"],
                          "random_seed": seed, "loss": "softplus"}
                if is_rgcn:
                    kwargs.update(num_layers=MODEL["num_layers"], decomposition="bases",
                                  decomposition_kwargs={"num_bases": MODEL["num_bases"]},
                                  activation=MODEL["activation"], edge_dropout=0.0, self_loop_dropout=0.0)
                model = (RGCN if is_rgcn else ComplEx)(**kwargs).to(device)
                if is_rgcn:
                    rep = model.entity_representations[0]
                    # v1.11.1 checks `is not None`, so 0.0 still consumes random
                    # numbers in proportion to the arm's adjacency size. Use its
                    # native disabled branch after keeping self-loop Dropout(0).
                    if any(layer.dropout.p != 0.0 for layer in rep.layers):
                        raise ValueError("Self-loop dropout differs from the frozen zero-dropout policy.")
                    rep.edge_dropout = None
                    actual = torch.stack([rep.sources, rep.edge_types, rep.targets], dim=1).cpu()
                    if not torch.equal(actual, context.mapped_triples):
                        raise ValueError("Model adjacency differs from its bound graph arm.")

                class Observe(TrainingCallback):
                    def __init__(self):
                        super().__init__()
                        self.steps = 0
                        self.initial = None
                        self.batches = hashlib.sha256()
                        self.proposals = 0
                        self.filtered = 0

                    def pre_batch(self, **unused):
                        if self.initial is None:
                            fingerprint = hashlib.sha256()
                            for param_name, param in self.model.named_parameters():
                                fingerprint.update(param_name.encode())
                                fingerprint.update(param.detach().cpu().numpy().tobytes())
                            self.initial = fingerprint.hexdigest()

                    def post_batch(self, epoch, batch, **unused):
                        self.steps += 1
                        positives = batch["positives"].detach().cpu()
                        if not set(map(tuple, positives.tolist())).issubset(positive_set):
                            raise ValueError("Training batch contains non-supervision positives.")
                        self.batches.update(positives.numpy().tobytes())
                        masks = batch["masks"]
                        if masks is None:
                            raise ValueError("Negative filtering was not applied.")
                        negatives = batch["negatives"].detach().cpu()
                        mask = masks.detach().cpu()
                        self.proposals += mask.numel()
                        self.filtered += int((~mask).sum())
                        accepted = negatives[mask].tolist()
                        if any(tuple(triple) in blocked_set or triple[0] not in gene_ids or
                               triple[2] not in gene_ids or triple[1] != relation_ids["interacts"]
                               for triple in accepted):
                            raise ValueError("Accepted negative violates reserved-pair or gene-type constraints.")

                observer = Observe()
                loop = SLCWATrainingLoop(model=model, triples_factory=supervision, optimizer="Adam",
                        optimizer_kwargs={"lr": TRAINING["learning_rate"]}, automatic_memory_optimization=False,
                        negative_sampler=PseudoTypedNegativeSampler,
                        negative_sampler_kwargs={"num_negs_per_pos": TRAINING["num_negs_per_pos"], "filterer": filterer})
                set_random_seed(seed)
                if device.startswith("cuda"):
                    torch.cuda.reset_peak_memory_stats()
                    torch.cuda.synchronize()
                before = time.perf_counter()
                losses = loop.train(triples_factory=supervision, num_epochs=epochs, batch_size=batch_size,
                        sampler=None, use_tqdm=False, num_workers=0, pin_memory=False,
                        drop_last=False, checkpoint_directory=output / "checkpoints" / f"{name}_{seed}",
                        callbacks=observer)
                if device.startswith("cuda"):
                    torch.cuda.synchronize()
                elapsed = time.perf_counter() - before
                if losses is None or len(losses) != epochs or not all(math.isfinite(float(v)) for v in losses):
                    raise ValueError("Training did not complete its finite-loss budget.")
                if observer.steps != expected_steps:
                    raise ValueError("Optimizer update count differs from the frozen budget.")
                optimizer_steps = {int(state["step"].item()) for state in loop.optimizer.state.values() if "step" in state}
                if optimizer_steps != {expected_steps}:
                    raise ValueError("Native optimizer state does not match observed updates.")
                if is_rgcn:
                    if seed in initial_by_seed and observer.initial != initial_by_seed[seed]:
                        raise ValueError("Paired R-GCN initial parameter fingerprints differ.")
                    initial_by_seed[seed] = observer.initial
                batch_hash = observer.batches.hexdigest()
                if is_rgcn:
                    if seed in batches_by_seed and batch_hash != batches_by_seed[seed]:
                        raise ValueError("Paired R-GCN positive batch schedules differ.")
                    batches_by_seed[seed] = batch_hash
                prediction_rows = [("development", row) for row in packet["development"]]
                if not resource_smoke:
                    prediction_rows += [("candidate", row) for row in packet["candidates"]]
                query_rows = []
                for _, row in prediction_rows:
                    a, b = row["original_genes"]
                    query_rows.extend(((a, "interacts", b), (b, "interacts", a)))
                queries = mapped(query_rows)
                with torch.inference_mode():
                    scores = predict_triples(model=model, triples=queries, batch_size=1024)
                if not torch.equal(scores.result.cpu(), queries) or not torch.isfinite(scores.scores).all():
                    raise ValueError("Fixed-pair predictions are incomplete, reordered or nonfinite.")
                values = scores.scores.detach().cpu().tolist()
                predictions = []
                for index, (partition, row) in enumerate(prediction_rows):
                    forward, reverse = values[2 * index:2 * index + 2]
                    if is_rgcn and not math.isclose(forward, reverse, rel_tol=1e-5, abs_tol=1e-5):
                        raise ValueError("Symmetric R-GCN decoder returned inconsistent pair orientations.")
                    predictions.append({**row, "partition": partition, "forward": forward,
                                        "reverse": reverse, "score": (forward + reverse) / 2})
                score_name = f"{name}_{seed}_scores.json"
                _write(output / score_name, predictions)
                checkpoint_name = f"{name}_{seed}_state.pt"
                torch.save(model.state_dict(), output / checkpoint_name)
                result = {"arm": name, "seed": seed, "status": "passed", "optimizer_steps": observer.steps,
                          "initial_parameters_sha256": observer.initial, "positive_batch_sha256": batch_hash,
                          "negative_proposals": observer.proposals, "negative_proposals_filtered": observer.filtered,
                          "adjacency_triples": context.num_triples if is_rgcn else None,
                          "supervision_triples": supervision.num_triples, "losses": [float(v) for v in losses],
                          "parameter_count": sum(p.numel() for p in model.parameters()),
                          "training_seconds": elapsed, "scores_file": score_name,
                          "score_rows": len(predictions), "checkpoint": checkpoint_name,
                          "max_cuda_memory_allocated_bytes": torch.cuda.max_memory_allocated() if device.startswith("cuda") else None}
                results.append(result)
                _write(output / f"{name}_{seed}_receipt.json", result)
                print(f"{name} seed {seed}: {observer.steps} updates, {elapsed:.2f}s; unlabelled scores only", flush=True)
                del model, loop, scores, observer, context
                gc.collect()
                if device.startswith("cuda"):
                    torch.cuda.empty_cache()
        handler.flush()
        finished = {"format": FORMAT, "status": "passed", **bindings, "resource_smoke": resource_smoke,
                    "execution": execution,
                    "arms": results, "total_seconds": time.perf_counter() - started,
                    "max_process_rss_native_units": resource.getrusage(resource.RUSAGE_SELF).ru_maxrss,
                    "max_process_rss_unit": "bytes" if sys.platform == "darwin" else "KiB",
                    "candidate_pairs_scored": 0 if resource_smoke else len(packet["candidates"]),
                    "candidate_outcomes_loaded": False, "biological_accuracy_measured": False,
                    "limitations": ["Scores are uncalibrated; no assay labels were opened.",
                        "Equal update budgets do not mean equal runtime or model parameter counts.",
                        "ComplEx uses the same supervision and sampling contract; its exact draws need not match R-GCN.",
                        "Reserved candidate identities filter negatives without using their outcomes.",
                        "R-GCN propagation retains the frozen packet's source-lineage limitations."],
                    "files": {str(p.relative_to(output)): sha(p) for p in sorted(output.rglob("*")) if p.is_file()}}
        finished["content_sha256"] = digest(finished)
        _write(output / "report.json", finished)
        return finished
    except Exception as exc:
        _write(output / "failure.json", {"status": "failed", **bindings, "error": str(exc),
                "traceback": traceback.format_exc(), "candidate_outcomes_loaded": False})
        raise
    finally:
        logging.getLogger("pykeen").removeHandler(handler)
        handler.close()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--graph", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--device", choices=("cpu", "cuda", "cuda:0"), required=True)
    parser.add_argument("--resource-smoke", action="store_true")
    args = parser.parse_args()
    try:
        result = run(args.graph, args.output_dir, device=args.device, resource_smoke=args.resource_smoke)
    except (ValueError, OSError, RuntimeError) as exc:
        parser.exit(1, f"{exc}\n")
    print(json.dumps({"status": result["status"], "resource_smoke": args.resource_smoke,
                      "biological_accuracy_measured": False, "output": str(args.output_dir)}))


if __name__ == "__main__":
    main()
