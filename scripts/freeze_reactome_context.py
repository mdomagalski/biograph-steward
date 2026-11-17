#!/usr/bin/env python3
"""Seal a separate two-arm execution only after actual native preflight proofs.

The prepared graph is never edited. Missing/stale proofs create no freeze.
"""
from __future__ import annotations

import argparse
import hashlib
import os
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "scripts"))
import run_reactome_context as runner
import score_inmc_comparison as original
from biograph_steward.client import digest, utcnow
from biograph_steward.file_utils import sha

HANDOFF_FILES = ("scripts/freeze_reactome_context.py", "scripts/score_reactome_context.py",
                 "scripts/score_inmc_comparison.py", "scripts/audit_inmc_inputs.py",
                 "biograph_steward/inmc_outcomes.py")


def implementation_bindings():
    return {name: sha(runner.ordinary(ROOT, name)) for name in HANDOFF_FILES}


def runtime_binding(device):
    # Same supported native cache environment as runner._output, also needed
    # when a fresh freeze/scoring process has not created a learner output.
    cache = ROOT / "runs" / "reactome_context_runtime_cache"
    os.environ.setdefault("PYSTOW_HOME", str(cache))
    os.environ.setdefault("PYKEEN_HOME", str(cache / "pykeen"))
    return runner.runtime_binding(device)


def reporting_contract():
    return {"population": "consumed_INMC_development", "primary_eligible_pairs": 1751,
            "primary_detected_pairs": 737, "primary_nondetected_pairs": 1014,
            "primary_metric": "average_precision", "secondary_metric": "roc_auc",
            "score_aggregation": "mean_of_forward_and_reverse",
            "seed_aggregation": "arithmetic_mean", "coverage_only_scores": [0, 1, 2],
            "influence": "descriptive_leave_one_original_gene_out",
            "statistical_significance_claimed": False, "independent_validation": False}


def validate_score_rows(rows, packet):
    expected = [(partition, row) for partition, values in
                (("development", packet["development"]), ("candidate", packet["candidates"])) for row in values]
    if not isinstance(rows, list) or len(rows) != len(expected):
        raise ValueError("Scores omit part of the complete candidate/development population.")
    scores = {}
    for row, (partition, identity) in zip(rows, expected):
        if (not isinstance(row, dict) or set(row) !=
                {"id", "original_genes", "self_pair", "partition", "forward", "reverse", "score"}
                or any(row.get(k) != v for k, v in identity.items()) or row.get("partition") != partition
                or row.get("self_pair") is not identity["self_pair"]):
            raise ValueError("Prediction identity/order differs or contains outcome/reference fields.")
        if not all(original._finite(row[k]) for k in ("forward", "reverse", "score")):
            raise ValueError("Predictions must be complete finite numbers.")
        if row["score"] != (row["forward"] + row["reverse"]) / 2:
            raise ValueError("Prediction is not the exact mean of both orientations.")
        if not runner.math.isclose(row["forward"], row["reverse"], rel_tol=1e-5, abs_tol=1e-5):
            raise ValueError("Symmetric R-GCN orientation scores disagree.")
        if partition == "candidate":
            scores[row["id"]] = row["score"]
    queries = [(a, "interacts", b) for _, row in expected
               for a, b in (row["original_genes"], list(reversed(row["original_genes"])))]
    return scores, digest(queries)


def validate_proof_files(path, *, mode, packet, execution):
    """Verify sealed report bytes AND bound manifest/receipts/score artifacts."""
    path = Path(path)
    if path.name != "report.json":
        raise ValueError("Use the original preflight report.json with its bound artifacts.")
    report, report_sha = original._sealed(path.parent)
    runner.validate_proof(report, mode=mode, packet=packet, execution=execution)
    files = report["files"]
    manifest = original._bound_json(path.parent, files, "manifest.json")
    expected = {"mode": mode, "profile": runner.profile(), "execution": report["execution"],
                "implementation_sha256": runner.implementation_bindings()}
    if mode == "resource_check":
        expected["graph_bindings"] = packet["graph_bindings"]
    if any(manifest.get(k) != v for k, v in expected.items()):
        raise ValueError("Preflight manifest differs from its proof/runtime/code.")
    for receipt in report["arms"]:
        prefix = f'{receipt["arm"]}_{receipt["seed"]}'
        if original._bound_json(path.parent, files, prefix + "_receipt.json") != receipt:
            raise ValueError("Preflight inline/file run receipts differ.")
        if mode == "synthetic_check":
            name = prefix + "_scores.json"
            if receipt.get("scores_file") != name:
                raise ValueError("Synthetic proof score artifact differs.")
            _, query_sha = validate_score_rows(original._bound_json(path.parent, files, name), runner.synthetic_fixture())
            if receipt.get("query_sha256") != query_sha:
                raise ValueError("Synthetic proof query fingerprint differs.")
    if mode == "resource_check" and any(name.endswith(("_scores.json", "_state.pt")) for name in files):
        raise ValueError("Resource proof must contain no predictions or model checkpoints.")
    raw = path.read_bytes()
    if hashlib.sha256(raw).hexdigest() != report_sha:
        raise ValueError("Preflight proof changed while being authenticated.")
    return raw, report


def validate_freeze(packet, folder, execution):
    frozen = runner.validate_execution(packet, folder, execution)
    if (frozen.get("handoff_implementation_sha256") != implementation_bindings()
            or frozen.get("reporting_contract") != reporting_contract()):
        raise ValueError("Frozen handoff implementation or reporting contract differs.")
    return frozen


def freeze_comparison(graph, synthetic_check, resource_check, output, *, device):
    packet = runner.validate_packet(graph)
    execution = runtime_binding(device)
    code = implementation_bindings()
    synthetic_raw, _ = validate_proof_files(synthetic_check, mode="synthetic_check", packet=packet, execution=execution)
    resource_raw, _ = validate_proof_files(resource_check, mode="resource_check", packet=packet, execution=execution)
    frozen = {"format": runner.EXECUTION_FORMAT, "created_at": utcnow(), "fully_frozen": True,
              "graph_bindings": packet["graph_bindings"], "profile": runner.profile(),
              "implementation_sha256": runner.implementation_bindings(), "execution": execution,
              "scorer": {"path": runner.SCORER, "sha256": code[runner.SCORER]},
              "outcome_adapter_sha256": code["biograph_steward/inmc_outcomes.py"],
              "handoff_implementation_sha256": code, "reporting_contract": reporting_contract(),
              "candidate_outcomes_loaded": False, "scientific_predictions_generated": False,
              "proofs": {mode: {"path": "validation/" + mode + ".json",
                                "sha256": hashlib.sha256(raw).hexdigest()}
                         for mode, raw in (("synthetic_check", synthetic_raw), ("resource_check", resource_raw))}}
    frozen["content_sha256"] = digest(frozen)
    # Revalidate source/code just before publishing a new immutable directory.
    if runner.validate_packet(graph)["graph_bindings"] != packet["graph_bindings"] or implementation_bindings() != code:
        raise ValueError("Graph/source or handoff implementation changed during freeze.")
    out = runner._output(output, graph, Path(synthetic_check).parent, Path(resource_check).parent)
    (out / "validation").mkdir()
    for mode, raw in (("synthetic_check", synthetic_raw), ("resource_check", resource_raw)):
        (out / "validation" / (mode + ".json")).write_bytes(raw)
    runner._write(out / "execution.json", frozen)
    validate_freeze(packet, out, execution)
    return frozen


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ("graph", "synthetic-check", "resource-check", "output-dir"):
        parser.add_argument("--" + name, type=Path, required=True)
    parser.add_argument("--device", choices=("cpu", "cuda:0"), required=True)
    args = parser.parse_args()
    try:
        result = freeze_comparison(args.graph, args.synthetic_check, args.resource_check, args.output_dir, device=args.device)
    except (ValueError, OSError, ImportError, RuntimeError) as exc:
        parser.exit(1, str(exc) + "\n")
    print(f"fully_frozen={result['fully_frozen']}: {args.output_dir} ({args.device}; outcomes unopened)")


if __name__ == "__main__":
    main()
