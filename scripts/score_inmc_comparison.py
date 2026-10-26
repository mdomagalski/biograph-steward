#!/usr/bin/env python3
"""Open authenticated INMC labels only after a complete frozen comparison passes.

This I/O gate delegates assay semantics and metrics to the previously frozen
inmc_outcomes module. It never trains, chooses a subset by score, or repairs
source identities. Failed reconciliation leaves an exposure receipt, no metrics.
"""
from __future__ import annotations

import argparse
from collections import Counter, defaultdict
from datetime import datetime, timezone
import hashlib
import io
from importlib.metadata import version
import math
from pathlib import Path
import platform
import sys
import zipfile

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "scripts"))
import run_inmc_comparison as runner
from audit_inmc_inputs import identifier_pairs
from biograph_steward import inmc_outcomes
from biograph_steward.client import digest
from biograph_steward.file_utils import new_output, sha

FORMAT = "biograph-steward.inmc-scored-comparison.v1"
ARMS = ("rgcn_scaffold", "rgcn_baseline", "rgcn_enriched", "complex_scaffold")
PANEL_MEMBER = "PPI-Prediction/Experimental validation/PPI_prediction_validation_result_20210624.xls"
AUTHOR_SHEET = "Fig.6"
AUTHOR_ROWS = 1177
OPENPYXL_VERSION = "3.1.5"


def _now():
    return datetime.now(timezone.utc).isoformat()


def _ordinary(path):
    path = Path(path)
    if any(p.is_symlink() for p in (path, *path.parents)) or not path.is_file():
        raise ValueError("Inputs must be ordinary files without symlink traversal.")
    return path


def _sealed(folder):
    """Authenticate every prediction artifact, including checkpoints, as bytes."""
    folder = Path(folder)
    if any(p.is_symlink() for p in (folder, *folder.parents)) or not folder.is_dir():
        raise ValueError("Predictions must be an ordinary directory.")
    raw = _ordinary(folder / "report.json").read_bytes()
    report = runner.strict_json(raw)
    if not isinstance(report, dict) or report.get("content_sha256") != digest(
            {k: v for k, v in report.items() if k != "content_sha256"}):
        raise ValueError("Prediction report content seal differs.")
    files = report.get("files")
    if not isinstance(files, dict) or "manifest.json" not in files:
        raise ValueError("Prediction report lacks its file inventory.")
    for name, fingerprint in files.items():
        if (not isinstance(name, str) or not isinstance(fingerprint, str) or
                not runner.HEX.fullmatch(fingerprint)):
            raise ValueError("Invalid prediction file inventory.")
        member = Path(name)
        if member.is_absolute() or ".." in member.parts or name == "report.json":
            raise ValueError("Unsafe prediction member.")
        if sha(_ordinary(folder / member)) != fingerprint:
            raise ValueError(f"Prediction file fingerprint differs: {name}")
    return report, hashlib.sha256(raw).hexdigest()


def _finite(value):
    return type(value) in (int, float) and math.isfinite(value)


def _bound_json(folder, files, name):
    raw = _ordinary(Path(folder) / name).read_bytes()
    if hashlib.sha256(raw).hexdigest() != files.get(name):
        raise ValueError(f"Parsed file fingerprint differs: {name}")
    return runner.strict_json(raw)


def validate_predictions(graph, predictions):
    """No archive/workbook argument: all training and score gates precede exposure."""
    packet = runner.validate_packet(Path(graph))
    predictions = Path(predictions)
    report, report_sha = _sealed(predictions)
    files = report["files"]
    manifest = _bound_json(predictions, files, "manifest.json")
    bindings = {"graph_report_sha256": packet["report_sha256"],
                "graph_input_files": {k: packet["files"][k] for k in runner.REQUIRED if k != "protocol.json"},
                "protocol_sha256": packet["files"]["protocol.json"],
                "runner_sha256": packet["protocol"]["runner_sha256"]}
    for document in (report, manifest):
        if (not isinstance(document, dict) or document.get("format") != runner.FORMAT or
                document.get("resource_smoke") is not False or
                document.get("candidate_outcomes_loaded") is not False or
                any(document.get(k) != v for k, v in bindings.items())):
            raise ValueError("Full prediction graph/protocol/runner bindings or exposure state differ.")
        runner.check_execution(packet["protocol"], document.get("execution"))
    if (report.get("status") != "passed" or report.get("biological_accuracy_measured") is not False or
            type(report.get("candidate_pairs_scored")) is not int or
            report["candidate_pairs_scored"] != len(packet["candidates"])):
        raise ValueError("Full prediction completion/population receipt differs.")
    batch = min(runner.TRAINING["batch_size"], len(packet["supervision"]))
    expected_manifest = {"model": runner.MODEL, "training": runner.TRAINING,
                         "effective_epochs": runner.TRAINING["num_epochs"], "effective_batch_size": batch,
                         "seeds": runner.TRAINING["seeds"], "candidate_pairs_scored": True,
                         "loss": "SoftplusLoss", "sampler": None, "effective_rgcn_edge_dropout": None,
                         "automatic_memory_optimization": False, "score_aggregation": "mean_of_forward_and_reverse"}
    if any(k not in manifest or manifest[k] != v for k, v in expected_manifest.items()):
        raise ValueError("Prediction manifest differs from the frozen training/scoring budget.")
    expected = {(partition, row["id"]): row for partition, rows in
                (("candidate", packet["candidates"]), ("development", packet["development"])) for row in rows}
    if len(expected) != len(packet["candidates"]) + len(packet["development"]):
        raise ValueError("Duplicate score identity in frozen population.")
    expected_runs = {(arm, seed) for arm in ARMS for seed in runner.TRAINING["seeds"]}
    receipts = report.get("arms")
    if not isinstance(receipts, list) or len(receipts) != len(expected_runs):
        raise ValueError("All four arms and three seeds must complete before exposure.")
    seen, scores = set(), {arm: {} for arm in ARMS}
    paired = defaultdict(list)
    updates = runner.TRAINING["num_epochs"] * math.ceil(len(packet["supervision"]) / batch)
    for receipt in receipts:
        if not isinstance(receipt, dict) or type(receipt.get("seed")) is not int:
            raise ValueError("Malformed arm receipt.")
        arm, seed = receipt.get("arm"), receipt["seed"]
        key = (arm, seed)
        if key not in expected_runs or key in seen:
            raise ValueError("Duplicate or unexpected arm/seed receipt.")
        seen.add(key)
        prefix = f"{arm}_{seed}"
        for suffix in ("_receipt.json", "_scores.json", "_state.pt"):
            if prefix + suffix not in files:
                raise ValueError("Missing bound arm receipt, scores or checkpoint.")
        if _bound_json(predictions, files, prefix + "_receipt.json") != receipt:
            raise ValueError("Inline and file arm receipts differ.")
        losses = receipt.get("losses")
        adjacency = len(packet["arms"][arm.split("_", 1)[1]]) if arm.startswith("rgcn_") else None
        if (receipt.get("status") != "passed" or receipt.get("optimizer_steps") != updates or
                receipt.get("supervision_triples") != len(packet["supervision"]) or
                receipt.get("adjacency_triples") != adjacency or
                receipt.get("scores_file") != prefix + "_scores.json" or
                receipt.get("checkpoint") != prefix + "_state.pt" or
                receipt.get("score_rows") != len(expected) or not isinstance(losses, list) or
                len(losses) != runner.TRAINING["num_epochs"] or not all(_finite(v) for v in losses)):
            raise ValueError("Arm completion, adjacency or fixed budget differs.")
        fingerprints = tuple(receipt.get(k) for k in ("initial_parameters_sha256", "positive_batch_sha256"))
        if any(not isinstance(v, str) or not runner.HEX.fullmatch(v) for v in fingerprints):
            raise ValueError("Missing initial parameter/batch fingerprints.")
        if arm.startswith("rgcn_"):
            paired[seed].append(fingerprints)
        rows = _bound_json(predictions, files, receipt["scores_file"])
        if not isinstance(rows, list) or len(rows) != len(expected):
            raise ValueError("Scores omit part of the fixed candidate/development population.")
        identities, arm_scores = set(), {}
        for row in rows:
            if not isinstance(row, dict) or set(row) != {"id", "partition", "original_genes", "self_pair", "forward", "reverse", "score"}:
                raise ValueError("Malformed or labelled prediction row.")
            identity = (row["partition"], row["id"])
            if identity in identities or identity not in expected:
                raise ValueError("Duplicate or unknown prediction identity.")
            identities.add(identity)
            original = expected[identity]
            if (row["original_genes"] != original["original_genes"] or
                    row["self_pair"] is not original["self_pair"]):
                raise ValueError("Prediction identity differs from frozen original genes.")
            if not all(_finite(row[k]) for k in ("forward", "reverse", "score")):
                raise ValueError("Prediction scores must be finite numbers.")
            if row["score"] != (row["forward"] + row["reverse"]) / 2:
                raise ValueError("Prediction score is not the exact mean of both orientations.")
            if arm.startswith("rgcn_") and not math.isclose(row["forward"], row["reverse"], rel_tol=1e-5, abs_tol=1e-5):
                raise ValueError("Symmetric R-GCN orientation scores disagree.")
            if row["partition"] == "candidate":
                arm_scores[row["id"]] = row["score"]
        if identities != set(expected):
            raise ValueError("Prediction identity population differs.")
        scores[arm][seed] = arm_scores
    if any(len(values) != 3 or len(set(values)) != 1 for values in paired.values()):
        raise ValueError("Paired R-GCN initialization or batch schedules differ.")
    return packet, scores, {**bindings, "prediction_report_sha256": report_sha,
                           "prediction_manifest_sha256": files["manifest.json"],
                           "scoring_implementation": packet["protocol"]["scoring_implementation"],
                           "assay_contract_sha256": packet["protocol"]["assay_contract_sha256"]}


def coverage(graph, packet):
    """Original-gene coverage, without guessing Pharos resolution from absent GO."""
    genes = {g for row in packet["candidates"] for g in row["original_genes"]}
    split = _bound_json(graph, packet["files"], "split.json")
    pairs = {tuple(sorted((a, b))) for a, _, b in packet["supervision"]}
    degrees = Counter(g for pair in pairs for g in set(pair))
    declared_degree = split.get("training_degree", {})
    if not isinstance(declared_degree, dict) or any(type(v) is not int or v != degrees[g] for g, v in declared_degree.items()):
        raise ValueError("Frozen training-degree metadata disagrees with supervision.")
    mappings = defaultdict(set)
    for a, relation, b in packet["arms"]["baseline"]:
        if relation == "reviewed_product_context":
            mappings[a].add(b)
    known_mapping = set()
    if "source_inventory.json" in packet["files"]:
        inventory = _bound_json(graph, packet["files"], "source_inventory.json")
        known_mapping = set(inventory["panel_gene_ids"])
        declared = defaultdict(set)
        for target in inventory["targets"]:
            for gene in target["panel_gene_ids"]:
                declared[gene].add(target["uniprot_id"])
        if any(declared[g] != mappings[g] for g in known_mapping):
            raise ValueError("Frozen source inventory and graph product mappings differ.")
        if set(inventory["panel_genes_without_confirmed_context"]) != {g for g in known_mapping if not declared[g]}:
            raise ValueError("Frozen unmapped inventory disagrees with its target rows.")
    annotated = {a for a, r, _ in packet["arms"]["baseline"] if r == "pharos_cc_annotation"}
    detailed = {gene: {"mapping": bool(mappings[gene]) if gene in known_mapping or mappings[gene] else None,
                       "context": bool(mappings[gene] & annotated),
                       "training_degree": degrees[gene], "pharos_resolved": None,
                       "reviewed_products": sorted(mappings[gene])} for gene in sorted(genes)}
    return {"genes": detailed, "definitions": {
        "mapping": "At least one reviewed product context link; absence is established only by a frozen complete source inventory.",
        "context": "At least one linked product retains a qualified Pharos GO cellular-component annotation in the frozen baseline.",
        "pharos_resolved": "Unknown: the frozen product inventory does not establish per-gene Pharos resolution; absent GO is not resolution failure.",
        "training_degree": "Distinct retained original-gene HuRI neighbors; a self-interaction counts once, matching the frozen split."}}


def _author_pairs(raw):
    from openpyxl import load_workbook
    workbook = load_workbook(io.BytesIO(raw), read_only=True, data_only=False, keep_links=False)
    try:
        if AUTHOR_SHEET not in workbook.sheetnames:
            raise ValueError("Author workbook lacks the declared Fig.6 sheet.")
        sheet = workbook[AUTHOR_SHEET]
        # Native documented remedy avoids trusting potentially stale dimensions.
        sheet.reset_dimensions()
        rows = iter(sheet.iter_rows())
        header = next(rows, ())
        if [cell.value for cell in header] != ["source", "target"]:
            raise ValueError("Author Fig.6 header differs from source,target.")
        pairs = []
        for row in rows:
            if len(row) != 2 or any(cell.data_type == "f" for cell in row):
                raise ValueError("Author Fig.6 contains a malformed row or formula.")
            values = [cell.value for cell in row]
            if any(not isinstance(g, str) or not inmc_outcomes.GENE.fullmatch(g) for g in values):
                raise ValueError("Author Fig.6 does not retain exact original ENSG identifiers.")
            pairs.append(values)
        if len(pairs) != AUTHOR_ROWS:
            raise ValueError("Author Fig.6 row count differs from pre-inspected metadata.")
        return pairs
    finally:
        workbook.close()


def _runtime(packet):
    execution = packet["protocol"]["execution"]
    actual = {name: version(name) for name in runner.PACKAGES}
    if execution["python"] != platform.python_version() or execution["packages"] != actual:
        raise ValueError("Scoring runtime packages/Python differ from the frozen comparison.")
    if version("openpyxl") != OPENPYXL_VERSION:
        raise ValueError(f"Expected openpyxl {OPENPYXL_VERSION} for the declared workbook adapter.")
    # Import native metric/parser dependencies now, so missing dependencies do
    # not consume the holdout. No model import or execution is needed here.
    import openpyxl
    from sklearn.metrics import average_precision_score, roc_auc_score
    return {"python": platform.python_version(), "packages": actual,
            "openpyxl": openpyxl.__version__, "et_xmlfile": version("et-xmlfile")}


def run(graph, predictions, archive, workbook, output):
    packet, scores, bindings = validate_predictions(graph, predictions)
    coverage_result = coverage(graph, packet)
    runtime = _runtime(packet)
    contract = _bound_json(graph, packet["files"], "assay_contract.json")
    expected_population = contract["population"]
    candidates = packet["candidates"]
    actual_population = {"candidate_pairs": len(candidates),
                         "self_pairs_separate": sum(row["self_pair"] for row in candidates),
                         "off_diagonal_nominations": sum(not row["self_pair"] for row in candidates),
                         "original_gene_ids": len({g for row in candidates for g in row["original_genes"]})}
    if any(expected_population.get(k) != v for k, v in actual_population.items()):
        raise ValueError("Frozen candidates differ from the declared assay population.")
    source_hashes = {"archive_sha256": contract["source_archive_sha256"],
                     "workbook_sha256": contract["author_positive_workbook_sha256"],
                     "panel_member": PANEL_MEMBER, "panel_sha256": contract["source_member_sha256"][PANEL_MEMBER]}
    # Read authenticated containers as opaque bytes only, after all gates. The
    # same bytes are subsequently parsed, avoiding a path replacement race.
    archive_raw = _ordinary(archive).read_bytes()
    workbook_raw = _ordinary(workbook).read_bytes()
    if (hashlib.sha256(archive_raw).hexdigest() != source_hashes["archive_sha256"] or
            hashlib.sha256(workbook_raw).hexdigest() != source_hashes["workbook_sha256"]):
        raise ValueError("Archive/workbook differs from the frozen source fingerprints; labels not decoded.")
    with zipfile.ZipFile(io.BytesIO(archive_raw)) as source:
        matches = [item for item in source.infolist() if item.filename == PANEL_MEMBER]
        if len(matches) != 1 or matches[0].is_dir() or matches[0].flag_bits & 1:
            raise ValueError("Authenticated archive lacks one ordinary unencrypted declared panel member.")
    output = new_output(output, graph, predictions, archive, workbook)
    base = {"format": FORMAT, **bindings, "sources": source_hashes,
            "wrapper_sha256": sha(Path(__file__)), "runtime": runtime,
            "author_sheet": AUTHOR_SHEET, "author_expected_rows": AUTHOR_ROWS}
    runner._write(output / "gate.json", {**base, "status": "passed", "checked_at": _now(),
                  "candidate_outcomes_loaded": False, "scores_fixed_before_exposure": True,
                  "candidate_population": actual_population})
    runner._write(output / "coverage.json", coverage_result)
    # This write precedes the first decompression/semantic access to labels and
    # remains on disk even if parsing, reconciliation, or metrics fails.
    runner._write(output / "exposure_started.json", {**base, "started_at": _now(),
                  "candidate_outcomes_access_started": True, "candidate_outcomes_loaded": "not_yet_confirmed",
                  "status": "holdout_access_started_no_reuse_for_tuning"})
    phase = "panel_member_read"
    try:
        with zipfile.ZipFile(io.BytesIO(archive_raw)) as source:
            panel = source.read(PANEL_MEMBER)
        if hashlib.sha256(panel).hexdigest() != source_hashes["panel_sha256"]:
            raise ValueError("Declared panel member fingerprint differs; materialization blocked.")
        phase = "panel_identity_check"
        expected_pairs = {tuple(row["original_genes"]) for row in candidates}
        if {tuple(sorted(pair)) for pair in identifier_pairs(panel, panel=True)} != expected_pairs:
            raise ValueError("Full panel identity population differs; author-positive reference not opened.")
        phase = "author_reference_read"
        author_pairs = _author_pairs(workbook_raw)
        author_identities = [tuple(sorted(pair)) for pair in author_pairs]
        if not set(author_identities) <= expected_pairs:
            raise ValueError("Author-positive reference contains non-candidate pairs; reconciliation blocked.")
        phase = "assay_materialization_and_reference_reconciliation"
        materialized = inmc_outcomes.materialize(panel, candidates, author_pairs)
        runner._write(output / "outcomes.json", materialized)
        phase = "fixed_comparison_scoring"
        metric_coverage = {g: {k: values[k] for k in ("mapping", "context", "training_degree")}
                           for g, values in coverage_result["genes"].items()}
        result = inmc_outcomes.score_comparison(materialized["rows"], scores, coverage_by_gene=metric_coverage)
        runner._write(output / "metrics.json", result)
        report = {**base, "status": "passed", "finished_at": _now(),
                  "candidate_outcomes_loaded": True, "reference_reconciliation": materialized["reference_reconciliation"],
                  "metrics_file": "metrics.json", "outcomes_file": "outcomes.json",
                  "author_reference_rows": len(author_pairs),
                  "author_reference_unordered_pairs": len({tuple(sorted(p)) for p in author_pairs}),
                  "author_reference_duplicate_or_reverse_rows": len(author_pairs) - len(set(author_identities)),
                  "limitations": contract["limitations"] + [
                      "Retrospective recovery of recorded complete-scored Y2H detection, not universal biological accuracy.",
                      "The holdout has now been accessed; it cannot be relabelled an unseen test for further tuning.",
                      "Openpyxl loads workbook-level shared strings; only Fig.6 is used as the author-positive reference."],
                  "files": {str(p.relative_to(output)): sha(p) for p in sorted(output.rglob("*")) if p.is_file()}}
        report["content_sha256"] = digest(report)
        runner._write(output / "report.json", report)
        return report
    except BaseException as error:
        failure = {**base, "status": "failed_after_holdout_access_started", "failed_at": _now(),
                   "phase": phase, "error_type": type(error).__name__, "error": str(error),
                   "candidate_outcomes_access_started": True,
                   "candidate_outcomes_loaded": True if phase in {"assay_materialization_and_reference_reconciliation", "fixed_comparison_scoring"} else None,
                   "performance_reporting_allowed": False,
                   "files": {str(p.relative_to(output)): sha(p) for p in sorted(output.rglob("*")) if p.is_file()}}
        failure["content_sha256"] = digest(failure)
        runner._write(output / "failure.json", failure)
        raise


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for option in ("graph", "predictions", "archive", "workbook", "output-dir"):
        parser.add_argument("--" + option, type=Path, required=True)
    args = parser.parse_args()
    try:
        report = run(args.graph, args.predictions, args.archive, args.workbook, args.output_dir)
    except (ValueError, OSError, ImportError, zipfile.BadZipFile) as error:
        parser.exit(1, f"{error}\n")
    print(runner.json.dumps({"status": report["status"], "candidate_outcomes_loaded": True,
                             "output": str(args.output_dir)}))


if __name__ == "__main__":
    main()
