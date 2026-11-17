#!/usr/bin/env python3
"""Score the fixed Reactome comparison after authenticating all six predictions.

Uses the original assay adapter and native metrics. This is consumed development
material, never an unseen or independent validation. No fitting occurs here.
"""
from __future__ import annotations

import argparse
import hashlib
import io
from importlib.metadata import version
from pathlib import Path
import sys
import zipfile

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "scripts"))
import run_reactome_context as runner
import freeze_reactome_context as freeze
import score_inmc_comparison as original
from audit_inmc_inputs import identifier_pairs
from biograph_steward import inmc_outcomes
from biograph_steward.client import digest, utcnow
from biograph_steward.file_utils import sha

FORMAT = "biograph-steward.reactome-context-scored.v1"


def validate_predictions(graph, execution_packet, predictions, *, device):
    """All artifact/runtime/completeness gates precede any outcome source read."""
    packet = runner.validate_packet(graph)
    execution = freeze.runtime_binding(device)
    frozen = freeze.validate_freeze(packet, execution_packet, execution)
    report, report_sha = original._sealed(predictions)
    files = report["files"]
    manifest = original._bound_json(predictions, files, "manifest.json")
    bindings = {"mode": "full", "profile": runner.profile(), "execution": execution,
                "implementation_sha256": runner.implementation_bindings(), "graph_bindings": packet["graph_bindings"]}
    for document in (report, manifest):
        if any(document.get(k) != v for k, v in bindings.items()):
            raise ValueError("Full prediction graph/profile/runtime/code bindings differ.")
    settings = runner.schedule(len(packet["supervision"]), mode="full")
    if (report.get("format") != runner.FORMAT or report.get("status") != "passed"
            or report.get("schedule") != settings or report.get("candidate_outcomes_loaded") is not False
            or report.get("biological_accuracy_measured") is not False or report.get("biomedical_inputs_used") is not True
            or report.get("prediction_queries_constructed") is not True
            or report.get("query_pairs_scored") != len(packet["candidates"]) + len(packet["development"])
            or report.get("execution_packet_sha256") != sha(runner.ordinary(execution_packet, "execution.json"))):
        raise ValueError("Full prediction completion, exposure state or execution freeze differs.")
    runner.validate_complete_runs(report.get("arms"), settings)
    entities = {name: i for i, name in enumerate(packet["entities"])}
    relations = {name: i for i, name in enumerate(packet["relations"])}
    adjacency_hashes = {arm: digest(runner.native_factory(rows, entities, relations).mapped_triples.tolist())
                        for arm, rows in packet["arms"].items()}
    scores = {arm: {} for arm in runner.ARMS}
    for receipt in report["arms"]:
        arm, seed = receipt["arm"], receipt["seed"]
        prefix = f"{arm}_{seed}"
        name = prefix + "_scores.json"
        if (receipt.get("scores_file") != name or receipt.get("checkpoint") != prefix + "_state.pt"
                or prefix + "_state.pt" not in files
                or receipt.get("score_rows") != report["query_pairs_scored"]
                or receipt.get("supervision_triples") != len(packet["supervision"])
                or receipt.get("adjacency_triples") != len(packet["arms"][arm])
                or receipt.get("adjacency_sha256") != adjacency_hashes[arm]
                or receipt.get("negative_proposals") != len(packet["supervision"]) * settings["epochs"] * 16
                or type(receipt.get("negative_proposals_filtered")) is not int
                or not 0 <= receipt["negative_proposals_filtered"] <= receipt["negative_proposals"]
                or receipt.get("training_invalidated_cache") is not True):
            raise ValueError("Arm completion, checkpoint, adjacency or fixed training budget differs.")
        if original._bound_json(predictions, files, prefix + "_receipt.json") != receipt:
            raise ValueError("Inline and file arm receipts differ.")
        values, query_sha = freeze.validate_score_rows(original._bound_json(predictions, files, name), packet)
        if receipt.get("query_sha256") != query_sha:
            raise ValueError("Prediction query fingerprint differs.")
        scores[arm][seed] = values
    return packet, scores, {"graph_bindings": packet["graph_bindings"],
            "execution_packet_sha256": report["execution_packet_sha256"], "prediction_report_sha256": report_sha,
            "prediction_manifest_sha256": files["manifest.json"], "execution": execution,
            "handoff_implementation_sha256": frozen["handoff_implementation_sha256"],
            "reporting_contract": frozen["reporting_contract"]}


def _means(metrics):
    return {key: sum(value[key] for value in metrics.values()) / len(metrics) for key in inmc_outcomes.METRICS}


def _native_metrics(rows, scores):
    if {row["label"] for row in rows} != {0, 1}:
        return None
    from sklearn.metrics import average_precision_score, roc_auc_score
    labels = [row["label"] for row in rows]
    values = [scores[row["id"]] for row in rows]
    return {"average_precision": float(average_precision_score(labels, values)),
            "roc_auc": float(roc_auc_score(labels, values))}


def score_fixed(materialized, scores, coverage, *, gene_metadata=None):
    """Same original eligibility/metrics; only reporting aggregation is added."""
    contract = freeze.reporting_contract()
    eligible = [r for r in materialized["rows"] if r["eligible_primary_off_diagonal"]]
    population = {"primary_eligible_pairs": len(eligible),
                  "primary_detected_pairs": sum(r["label"] == 1 for r in eligible),
                  "primary_nondetected_pairs": sum(r["label"] == 0 for r in eligible)}
    if any(contract[k] != v for k, v in population.items()):
        raise ValueError("Original fixed primary denominator/class counts differ; metrics blocked.")
    if (set(scores) != set(runner.ARMS) or any(set(values) != set(runner.TRAINING["seeds"]) for values in scores.values())):
        raise ValueError("Exactly two arms and all three paired seeds are required.")
    result = inmc_outcomes.score_comparison(materialized["rows"], scores,
            baseline_arm=runner.ARMS[0], enriched_arm=runner.ARMS[1], coverage_by_gene=gene_metadata)
    result["means_by_arm"] = {arm: _means(values) for arm, values in result["metrics_by_arm_seed"].items()}
    result["paired_comparison"]["mean_deltas"] = _means(result["paired_comparison"]["deltas_by_seed"])
    expected = {r["id"]: r for r in materialized["rows"]}
    coverage_rows = coverage.get("rows", [])
    if len(coverage_rows) != len(expected) or {r["candidate_id"] for r in coverage_rows} != set(expected):
        raise ValueError("Coverage diagnostic omits or duplicates original candidates.")
    diagnostic = {}
    for row in coverage_rows:
        identity = expected[row["candidate_id"]]
        value = row["covered_endpoint_count"]
        if (row["original_genes"] != identity["original_genes"] or row["self_pair"] is not identity["self_pair"]
                or type(value) is not int or value not in (0, 1, 2) or row["coverage_only_score"] != value):
            raise ValueError("Coverage diagnostic identity or 0/1/2 definition differs.")
        diagnostic[row["candidate_id"]] = value
    result["coverage_only_diagnostic"] = {"trained_arm": False, "ties_preserved": True,
            "eligible_pairs": len(eligible), "metrics": _native_metrics(eligible, diagnostic),
            "definition": "Original gene endpoints with any eligible frozen Reactome membership (0/1/2)."}
    strata = {}
    for count in (0, 1, 2):
        rows = [r for r in eligible if diagnostic[r["id"]] == count]
        valid = {r["label"] for r in rows} == {0, 1}
        value = {"pairs": len(rows), "detected": sum(r["label"] == 1 for r in rows),
                 "nondetected": sum(r["label"] == 0 for r in rows),
                 "status": "scored" if valid else "empty" if not rows else "insufficient_class_support",
                 "metrics_by_arm_seed": None, "paired_deltas_by_seed": None, "mean_deltas": None}
        if valid:
            metrics = {arm: {str(seed): _native_metrics(rows, scores[arm][seed]) for seed in runner.TRAINING["seeds"]}
                       for arm in runner.ARMS}
            deltas = {str(seed): {key: metrics[runner.ARMS[1]][str(seed)][key] - metrics[runner.ARMS[0]][str(seed)][key]
                                  for key in inmc_outcomes.METRICS} for seed in runner.TRAINING["seeds"]}
            value.update(metrics_by_arm_seed=metrics, means_by_arm={arm: _means(v) for arm, v in metrics.items()},
                         paired_deltas_by_seed=deltas, mean_deltas=_means(deltas))
        strata[str(count)] = value
    result.update(reactome_endpoint_coverage_strata=strata, reporting_contract=contract,
                  primary_metric="average_precision", secondary_metric="roc_auc", independent_validation=False)
    return result


def run(graph, execution_packet, predictions, archive, workbook, output, *, device):
    packet, scores, bindings = validate_predictions(graph, execution_packet, predictions, device=device)
    if version("openpyxl") != original.OPENPYXL_VERSION:
        raise ValueError("Workbook adapter requires openpyxl " + original.OPENPYXL_VERSION)
    import openpyxl
    from sklearn.metrics import average_precision_score, roc_auc_score
    runtime = {"python": runner.platform.python_version(), "openpyxl": openpyxl.__version__,
               "et_xmlfile": version("et-xmlfile"), "packages": bindings["execution"]["packages"]}
    contract = original._bound_json(graph, packet["files"], "assay_contract.json")
    candidates = packet["candidates"]
    population = {"candidate_pairs": len(candidates), "self_pairs_separate": sum(r["self_pair"] for r in candidates),
                  "off_diagonal_nominations": sum(not r["self_pair"] for r in candidates),
                  "original_gene_ids": len({g for r in candidates for g in r["original_genes"]})}
    if any(contract["population"].get(k) != v for k, v in population.items()):
        raise ValueError("Frozen candidates differ from original assay population.")
    coverage = original._bound_json(graph, packet["files"], "coverage.json")
    original_coverage = original.coverage(graph, {**packet, "arms": {"baseline": packet["arms"][runner.ARMS[0]]}})
    source_hashes = {"archive_sha256": contract["source_archive_sha256"],
                    "workbook_sha256": contract["author_positive_workbook_sha256"],
                    "panel_member": original.PANEL_MEMBER,
                    "panel_sha256": contract["source_member_sha256"][original.PANEL_MEMBER]}
    archive_raw = original._ordinary(archive).read_bytes()
    workbook_raw = original._ordinary(workbook).read_bytes()
    if (hashlib.sha256(archive_raw).hexdigest() != source_hashes["archive_sha256"]
            or hashlib.sha256(workbook_raw).hexdigest() != source_hashes["workbook_sha256"]):
        raise ValueError("Archive/workbook differs from source fingerprints; labels not decoded.")
    with zipfile.ZipFile(io.BytesIO(archive_raw)) as source:
        matches = [r for r in source.infolist() if r.filename == original.PANEL_MEMBER]
        if len(matches) != 1 or matches[0].is_dir() or matches[0].flag_bits & 1:
            raise ValueError("Archive lacks one ordinary unencrypted declared panel member.")
    out = runner._output(output, graph, execution_packet, predictions, archive, workbook)
    base = {"format": FORMAT, **bindings, "sources": source_hashes, "runtime": runtime,
            "study_status": "consumed_retrospective_development", "independent_validation": False}
    runner._write(out / "gate.json", {**base, "status": "passed", "checked_at": utcnow(),
                  "candidate_outcomes_loaded": False, "scores_fixed_before_access": True, "candidate_population": population})
    runner._write(out / "coverage.json", {"reactome": coverage, "original_context": original_coverage})
    runner._write(out / "exposure_started.json", {**base, "started_at": utcnow(),
                  "status": "consumed_development_access_started_no_score_driven_tuning",
                  "candidate_outcomes_access_started": True, "candidate_outcomes_loaded": "not_yet_confirmed"})
    phase = "panel_member_read"
    try:
        with zipfile.ZipFile(io.BytesIO(archive_raw)) as source:
            panel = source.read(original.PANEL_MEMBER)
        if hashlib.sha256(panel).hexdigest() != source_hashes["panel_sha256"]:
            raise ValueError("Declared panel member fingerprint differs.")
        phase = "panel_identity_check"
        expected_pairs = {tuple(r["original_genes"]) for r in candidates}
        if {tuple(sorted(pair)) for pair in identifier_pairs(panel, panel=True)} != expected_pairs:
            raise ValueError("Full panel identity population differs; author reference unopened.")
        phase = "author_reference_read"
        author_pairs = original._author_pairs(workbook_raw)
        if not {tuple(sorted(pair)) for pair in author_pairs} <= expected_pairs:
            raise ValueError("Author-positive reference contains non-candidate identities.")
        phase = "assay_materialization_and_reference_reconciliation"
        materialized = inmc_outcomes.materialize(panel, candidates, author_pairs)
        runner._write(out / "outcomes.json", materialized)
        phase = "fixed_comparison_scoring"
        metadata = {g: {k: v[k] for k in ("mapping", "context", "training_degree")}
                    for g, v in original_coverage["genes"].items()}
        metrics = score_fixed(materialized, scores, coverage, gene_metadata=metadata)
        runner._write(out / "metrics.json", metrics)
        report = {**base, "status": "passed", "finished_at": utcnow(), "candidate_outcomes_loaded": True,
                  "reference_reconciliation": materialized["reference_reconciliation"],
                  "author_reference_rows": len(author_pairs), "metrics_file": "metrics.json", "outcomes_file": "outcomes.json",
                  "limitations": contract["limitations"] + [
                      "Consumed development panel; no independent validation or formal significance claim.",
                      "Recorded complete-scored assay detection is not general biological truth.",
                      "Coverage and gene-removal results are descriptive; no causal inference or retraining.",
                      "Pharos postdates assays; Reactome import release and study lineage remain unverified."]}
        report["files"] = {p.name: sha(p) for p in sorted(out.iterdir()) if p.is_file()}
        report["content_sha256"] = digest(report)
        runner._write(out / "report.json", report)
        return report
    except BaseException as exc:
        failure = {**base, "status": "failed_after_development_access_started", "phase": phase,
                   "error_type": type(exc).__name__, "error": str(exc), "performance_reporting_allowed": False,
                   "candidate_outcomes_access_started": True,
                   "files": {p.name: sha(p) for p in sorted(out.iterdir()) if p.is_file()}}
        failure["content_sha256"] = digest(failure)
        runner._write(out / "failure.json", failure)
        raise


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ("graph", "execution-packet", "predictions", "archive", "workbook", "output-dir"):
        parser.add_argument("--" + name, type=Path, required=True)
    parser.add_argument("--device", choices=("cpu", "cuda:0"), required=True)
    args = parser.parse_args()
    try:
        result = run(args.graph, args.execution_packet, args.predictions, args.archive, args.workbook, args.output_dir, device=args.device)
    except (ValueError, OSError, RuntimeError, ImportError, zipfile.BadZipFile) as exc:
        parser.exit(1, str(exc) + "\n")
    print(f"{result['status']}: {args.output_dir} (consumed development)")


if __name__ == "__main__":
    main()
