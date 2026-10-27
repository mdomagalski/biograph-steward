#!/usr/bin/env python3
"""Replay the stopped IntAct panel as explicitly consumed development data.

Preparation reads code and declared metadata only. Execution reuses captured
official-reader streams and source bytes, never reruns the historical reserved
runner, and never turns the old stopped result into a final score. The existing
native construction/attachment/answer/export APIs perform the downstream work.
"""
from __future__ import annotations

import argparse
from collections import defaultdict
from copy import deepcopy
import hashlib
import io
import json
from pathlib import Path
import sys
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from biograph_steward.client import ENDPOINT, PharosClient, canonical, digest, utcnow
from scripts.intact_final_common import (AMENDMENT_SHA, PROTOCOL_SHA, RESERVED,
    assess_alignment, load_json, ordinary, output_inventory_checks,
    participant_pair, provenance_audit, save_new, seal, sha, summarize)
from scripts.inspect_intact_development import assess, source_lines
from scripts.inspect_intact_xml_development import assess_development_xml
from scripts.intact_identity_projection import compare_identity_projection
from scripts.validate_intact_xml_provenance import parse_transport
from scripts.evaluate_intact_evidence_fidelity import evaluate_rows, field_groups

FORMAT = "biograph-steward.intact-consumed-flow-freeze.v1"
RESULT_FORMAT = "biograph-steward.intact-consumed-flow-result.v1"
SPLIT = "consumed_reserved_replay"
ORIGIN_SHA = "7c1f59b4696bd5b6f4b7760d22405f04f358fc46dfd7ea5f0464a98de3492788"
COMPONENT_SHA = "87c03d2571b11d927eb104a67ed210036482adfc252a1c27516f725a732a14d5"
SUMMARY_SHA = "2c3752b8923e9e0109e34cbaab9349c65da0873b0a45f1dc011e7809d1482737"
COMPONENT_SUMMARY_SHA = "be69d1d593ae4644326c68495e9bb682ca90667010ac107ba855fed19f47e745"
ARCHIVE_SHA = "1bc2485a061ea21a5c58ccee624131409c7cf45de6c27a2f880f6a0a6cff5324"
ORIGIN = ROOT / "runs/intact_final_reserved_20261027/execution_freeze.json"
SUMMARY = ROOT / "docs/evaluations/intact_final_assessment_20261027_summary.json"
COMPONENT = ROOT / "runs/intact_identity_projection_development_20261027_attempt_02/development_contract.json"
COMPONENT_SUMMARY = ROOT / "docs/evaluations/intact_identity_projection_development_20261027_summary.json"
CAPTURED = ROOT / "runs/intact_final_reserved_20261027/execution"
PROTOCOL = ROOT / "docs/evaluations/intact_fidelity_20261026_protocol.json"
AMENDMENT = ROOT / "docs/evaluations/intact_fidelity_20261026_semantic_amendment.json"
LICENSE = ROOT / "runs/intact_fidelity_preparation_20261026/sources/IntAct_license.md"
SUFFIXES = (".txt", ".xml", "_reader.jsonl", "_xml_reader.jsonl", "_alignment.json", "_http_receipt.json")
LIMITATION = ("Post-exposure consumed development replay of the original stopped panel; "
              "source preservation is not scientific accuracy, independence or biological prediction gain.")


def _encoded(value):
    return (canonical(value) + "\n").encode()


def implementation_paths():
    """Code-only inventory: never discover files below source/run directories."""
    names = ("scripts/replay_intact_consumed_flow.py", "tests/test_intact_consumed_flow.py",
        "tests/test_intact_consumed_publication.py", "tests/test_intact_final_publication.py",
        "tests/test_intact_evidence.py", "tests/test_assay_attachment.py",
        "tests/test_intact_evidence_fidelity.py", "tests/test_intact_final_execution.py",
        "tests/test_cohort_graph.py", "tests/test_lambourne_evidence.py", "tests/test_normalization.py",
        "scripts/intact_identity_projection.py", "scripts/intact_final_common.py",
        "scripts/inspect_intact_development.py", "scripts/inspect_intact_xml_development.py",
        "scripts/validate_intact_xml_provenance.py", "scripts/validate_intact_reader_controls.py",
        "scripts/evaluate_intact_evidence_fidelity.py")
    return [ROOT / name for name in names] + [path for path in sorted((ROOT / "biograph_steward").glob("*"))
        if path.is_file() and path.suffix in {".py", ".js", ".html"}]


def flow_policy(allow_pharos=False):
    return {"captured_inputs_only": True, "new_IntAct_retrieval": False,
        "new_Java_reader_calls": False, "model_calls": False, "GPU_runs": False,
        "allow_fresh_pharos": bool(allow_pharos), "pharos_endpoint": ENDPOINT,
        "pharos_profile": "ppi", "ppi_limit_per_target": 5000, "other_context_limits": 0,
        "maximum_source_eligible_rows": 2, "maximum_pair_batches": 2,
        "maximum_queries_per_batch": 7, "maximum_queries_total": 14,
        "timeout_seconds": 30, "retries": 0, "cache": None,
        "transport": "existing PharosClient HTTPS transport; no replacement or retry strategy",
        "batching": "lexical exact unordered primary UniProt pair, including exact isoforms",
        "failure_policy": "Every source-eligible row stays in the denominator, including downstream failures; no replacement or reselection.",
        "lineage_policy": "Audit all consumed studies; ambiguous dataset lineage stops metrics, without hiding source-eligible rows.",
        "empty_policy": "not_evaluable_not_success", "publication_split": SPLIT,
        "question_template": "qualified_assay_evidence.v1", "question_scope": "all attached observations; all local states; no cap"}


def validate_policy(policy):
    if policy not in (flow_policy(False), flow_policy(True)):
        raise ValueError("The complete fixed consumed-flow policy must be preserved.")
    return policy


def _code_bindings():
    return {str(path): sha(ordinary(path)) for path in implementation_paths()}


def prepare(output, historical_code_receipt, *, allow_pharos=False):
    """Freeze exact captured input hashes from old metadata without opening them."""
    output = Path(output).absolute()
    if output.exists() or output.is_symlink():
        raise ValueError("Choose a new immutable consumed-development directory.")
    if sha(ordinary(ORIGIN)) != ORIGIN_SHA or sha(ordinary(COMPONENT)) != COMPONENT_SHA:
        raise ValueError("Original final freeze or consumed component contract changed.")
    if sha(ordinary(SUMMARY)) != SUMMARY_SHA or sha(ordinary(COMPONENT_SUMMARY)) != COMPONENT_SUMMARY_SHA:
        raise ValueError("Closed original outcome or component diagnostic summary changed.")
    original, summary, component = load_json(ORIGIN), load_json(SUMMARY), load_json(COMPONENT_SUMMARY)
    if (summary.get("all_four_reserved_studies_now_consumed") is not True
            or summary.get("status") != "stopped_on_reference_projection_gate_no_final_score"
            or component.get("status") != "component_diagnostic_passed"
            or component.get("result", {}).get("remaining_reference_projection_errors") != 0):
        raise ValueError("Use only the disclosed stopped, now-consumed panel and passing component diagnostic.")
    historical_code_receipt = ordinary(historical_code_receipt)
    if sha(historical_code_receipt) != ARCHIVE_SHA:
        raise ValueError("The recorded exact historical implementation archive receipt is required.")
    archive = load_json(historical_code_receipt)
    if (archive.get("format") != "biograph-steward.intact-historical-implementation-archive.v1"
            or archive.get("frozen_execution_sha256") != ORIGIN_SHA
            or archive.get("git_commit") != "720beeafdc0be63cca7a2fcce7de7f5cfc203f43"
            or archive.get("count") != 71 or len(archive.get("files", [])) != 71
            or {entry["source_path"]: entry["sha256"] for entry in archive.get("files", [])}
               != original["implementation_sha256"]
            or archive.get("content_sha256") != digest({k: v for k, v in archive.items() if k != "content_sha256"})):
        raise ValueError("The exact archived historical implementation receipt is required.")
    # Archive entries are code, not assay bodies. Verify them before migration replay.
    for entry in archive["files"]:
        archived = Path(entry["archived_path"])
        if not archived.is_absolute():
            archived = ROOT / archived
        if sha(ordinary(archived)) != entry["sha256"]:
            raise ValueError("Historical source archive changed.")
    expected = {str(CAPTURED / (pmid + suffix)) for pmid in RESERVED for suffix in SUFFIXES}
    inputs = {str(ROOT / item["path"]): item["sha256"] for item in summary["artifact_bindings"]
              if str(ROOT / item["path"]) in expected}
    if set(inputs) != expected:
        raise ValueError("Metadata must bind every exact captured source, XML, reader, alignment and HTTP receipt.")
    metadata_paths = [ORIGIN, SUMMARY, COMPONENT, COMPONENT_SUMMARY, historical_code_receipt,
        PROTOCOL, AMENDMENT, LICENSE, ordinary(original["controls_report"]),
        ordinary(original["xml_controls_report"]), ordinary(original["consumed_inventory"]),
        ordinary(ROOT / "runs/intact_final_reserved_access_20261027.json")]
    if sha(PROTOCOL) != PROTOCOL_SHA or sha(AMENDMENT) != AMENDMENT_SHA:
        raise ValueError("Original source eligibility protocol changed.")
    log = io.StringIO()
    suite = unittest.defaultTestLoader.discover(str(ROOT / "tests"), pattern="test_intact_consumed_*.py")
    result = unittest.TextTestRunner(stream=log, verbosity=2).run(suite)
    output.mkdir(parents=True, exist_ok=False)
    (output / "invented_controls.log").write_text(log.getvalue())
    if not result.wasSuccessful() or result.skipped:
        raise ValueError("Consumed-flow invented controls must pass without skips before source access.")
    contract = seal({"format": FORMAT, "created_at": utcnow(), "pre_captured_stream_access": True,
        "assessment_split": SPLIT, "publication_ids": list(RESERVED),
        "origin_reserved_freeze_sha256": ORIGIN_SHA, "component_contract_sha256": COMPONENT_SHA,
        "historical_code_receipt": str(historical_code_receipt),
        "historical_code_receipt_sha256": sha(historical_code_receipt),
        "implementation_sha256": _code_bindings(), "input_sha256": inputs,
        "metadata_sha256": {str(path): sha(path) for path in metadata_paths},
        "python_runtime": {"executable": str(Path(sys.executable).resolve()), "version": sys.version,
                           "sha256": sha(Path(sys.executable).resolve())},
        "source_catalog": deepcopy(original["source_catalog"]),
        "reader_runtime": deepcopy(original["mitab_runtime"]),
        "xml_reader_runtime": deepcopy(original["xml_runtime"]),
        "controls_report": original["controls_report"], "xml_controls_report": original["xml_controls_report"],
        "consumed_inventory": original["consumed_inventory"],
        "flow_policy": flow_policy(allow_pharos),
        "invented_controls": {"status": "passed", "tests_run": result.testsRun,
                              "log_sha256": sha(output / "invented_controls.log")},
        "scientific_accuracy_measured": False, "independent_validation_performed": False,
        "original_final_outcome_changed": False, "interpretation": LIMITATION})
    save_new(output / "consumed_flow_freeze.json", contract)
    return contract


def verify_contract(path, expected_sha):
    """Verify only code/metadata here; captured bytes require an execution marker."""
    path = ordinary(path)
    if sha(path) != expected_sha:
        raise ValueError("Externally recorded consumed-flow contract SHA differs.")
    value = load_json(path)
    if (value.get("format") != FORMAT or value.get("assessment_split") != SPLIT
            or value.get("pre_captured_stream_access") is not True
            or value.get("publication_ids") != list(RESERVED)
            or value.get("origin_reserved_freeze_sha256") != ORIGIN_SHA
            or value.get("scientific_accuracy_measured") is not False
            or value.get("content_sha256") != digest({k: v for k, v in value.items() if k != "content_sha256"})):
        raise ValueError("Invalid explicit consumed-development contract.")
    validate_policy(value["flow_policy"])
    if value["implementation_sha256"] != _code_bindings():
        raise ValueError("Consumed-flow implementation changed after freeze.")
    runtime = {"executable": str(Path(sys.executable).resolve()), "version": sys.version,
               "sha256": sha(Path(sys.executable).resolve())}
    if runtime != value["python_runtime"]:
        raise ValueError("Python runtime changed after consumed-flow freeze.")
    for filename, pin in value["metadata_sha256"].items():
        if sha(ordinary(filename)) != pin:
            raise ValueError("Bound historical metadata changed: " + filename)
    return value


def inspect_captured(contract, output):
    """Reconstitute original complete rows and use corrected alias comparison only."""
    if not (output / "started.json").is_file():
        raise ValueError("An exclusive consumed-development start receipt must precede captured reads.")
    records, ledger, xml_by_study, files, catalog, studies, projection_errors = [], [], {}, {}, [], [], []
    original_catalog = {entry["publication_id"].removeprefix("pubmed:"): entry for entry in contract["source_catalog"]}
    # Read exactly the predeclared paths. Never discover/copy opaque source directories.
    for pmid in RESERVED:
        material = {}
        for suffix in SUFFIXES:
            path = ordinary(CAPTURED / (pmid + suffix))
            raw = path.read_bytes()
            if hashlib.sha256(raw).hexdigest() != contract["input_sha256"][str(path)]:
                raise ValueError("Captured input bytes changed: " + str(path))
            material[suffix] = raw
        raw, reader_raw = material[".txt"], material["_reader.jsonl"]
        entry = original_catalog[pmid]
        if len(raw) != entry["bytes"] or hashlib.sha256(raw).hexdigest() != entry["sha256"]:
            raise ValueError("Captured MITAB bytes no longer match the original source catalog.")
        rows = [json.loads(line) for line in reader_raw.splitlines()]
        lines = source_lines(raw)
        if len(rows) != len(lines):
            raise ValueError("Every physical source row must retain one official reader row.")
        study_refs = []
        for number, (line, row) in enumerate(zip(lines, rows), 1):
            if row.get("line_number") != number or row.get("raw_line") != line or row.get("raw_cells") != line.split("\t"):
                raise ValueError("Captured physical rows, raw fields or source orientation changed.")
            item = {"publication_id": "pubmed:" + pmid, "artifact_sha256": entry["sha256"],
                    "release": "2026-10-17", "source_line": number,
                    "raw_row_sha256": hashlib.sha256(line.encode()).hexdigest(), **assess(row, pmid)}
            wrapper = {"publication_id": item["publication_id"], "artifact_sha256": entry["sha256"],
                       "source_file": "source/" + pmid + ".txt", "reader_file": "reader/" + pmid + ".jsonl",
                       "reader_record": row}
            ledger.append(item); records.append(wrapper)
            study_refs.append({"ledger": item, "reader_record": row})
        xml_rows, xml_summary, _ = parse_transport(material["_xml_reader.jsonl"])
        gate = assess_development_xml(xml_summary, xml_rows, 0)
        if (gate["quarantined"] or xml_summary.get("input_sha256") != hashlib.sha256(material[".xml"]).hexdigest()
                or xml_summary.get("input_bytes") != len(material[".xml"])):
            raise ValueError("Captured official XML reader diagnostics or source fingerprint disagree.")
        comparison = compare_identity_projection(pmid, study_refs, xml_rows)
        if canonical(comparison["raw_v1_comparison"]) != canonical(json.loads(material["_alignment.json"])):
            raise ValueError("Raw v1 comparison no longer reproduces the preserved stopped execution.")
        errors = comparison["join_errors"] + assess_alignment(comparison["development_identity_comparison"], study_refs, xml_rows)
        projection_errors.extend({"publication_id": pmid, **error} for error in errors)
        save_new(output / (pmid + "_identity_projection.json"), comparison)
        xml_by_study[pmid] = xml_rows
        files["source/" + pmid + ".txt"] = raw
        files["reader/" + pmid + ".jsonl"] = reader_raw
        files["provenance/" + pmid + ".xml"] = material[".xml"]
        files["provenance/" + pmid + "_reader.jsonl"] = material["_xml_reader.jsonl"]
        files["provenance/" + pmid + "_http_receipt.json"] = material["_http_receipt.json"]
        catalog.append({"publication_id": "pubmed:" + pmid, "artifact_sha256": entry["sha256"],
            "source_file": "source/" + pmid + ".txt", "reader_file": "reader/" + pmid + ".jsonl",
            "reader_sha256": hashlib.sha256(reader_raw).hexdigest()})
        studies.append({"publication_id": "pubmed:" + pmid, "physical_rows": len(rows),
            "source_evidence_rows": sum(ref["ledger"]["kind"] == "evidence" for ref in study_refs),
            "source_eligible_rows": sum(ref["ledger"]["eligible"] for ref in study_refs),
            "xml_evidence_objects": len(xml_rows), "remaining_projection_errors": len(errors)})
    return records, ledger, xml_by_study, files, catalog, studies, projection_errors


def audit_consumed(xml_by_study, records, previous_inventory):
    """Retain every source-eligible row for engineering, never claim independence."""
    consumed = deepcopy(previous_inventory)
    consumed["publication_ids"] = sorted(set(consumed["publication_ids"]) | set(RESERVED))
    consumed["scope"] += " All four stopped reserved studies are now explicitly consumed."
    audit = provenance_audit(xml_by_study, records, consumed)
    audit.update(assessment_split=SPLIT, retained_for_consumed_engineering_replay=True,
        known_consumed_studies_not_removed_from_source_fidelity_denominator=True,
        independent_reference_qualification=False, study_independence="unverified")
    return audit


class BudgetPharos(PharosClient):
    """Native Pharos client with the frozen per-batch attempt accounting only."""
    def __init__(self, policy, folder, total, *, transport=None):
        validate_policy(policy)
        if policy["allow_fresh_pharos"] is not True:
            raise ValueError("Fresh Pharos access was not authorized in the pre-access policy.")
        self.policy, self.folder, self.total, self.attempt_count = policy, Path(folder), total, 0
        super().__init__(endpoint=policy["pharos_endpoint"], cache_dir=None,
                         timeout=policy["timeout_seconds"], retries=0, transport=transport)

    def execute(self, query, variables=None, *, cache=True):
        if (self.attempt_count >= self.policy["maximum_queries_per_batch"]
                or self.total["attempts"] >= self.policy["maximum_queries_total"]):
            raise ValueError("The fixed fresh Pharos attempt budget is exhausted.")
        self.attempt_count += 1; self.total["attempts"] += 1
        save_new(self.folder / ("pharos_attempt_" + str(self.attempt_count).zfill(2) + ".json"),
                 {"created_at": utcnow(), "endpoint": self.endpoint,
                  "request": {"query": query, "variables": variables or {}},
                  "attempts_per_call": 1, "assessment_split": SPLIT})
        try:
            return super().execute(query, variables, cache=False)
        finally:
            # Successful response bodies remain available even if a later call fails.
            path = self.folder / ("pharos_responses_after_" + str(self.attempt_count).zfill(2) + ".json")
            save_new(path, {"records": deepcopy(self.records), "attempts": self.attempt_count})


def evaluate_missing(references):
    return evaluate_rows(references, [], [], [], [], "", graph_edges=[], columns=field_groups())


def run_batches(references, publication, output, policy, *, construct=None):
    """Failures count as misses for the same all-source-eligible denominator."""
    from biograph_steward.assay_attachment import attach_assay, load_publication
    from biograph_steward.assay_questions import answer_assay_question
    from biograph_steward.construction import run_construction
    from biograph_steward.gold_packet import export_packet, load_packet
    from biograph_steward.questions import save_answer
    from biograph_steward.reviews import read_run
    validate_policy(policy)
    eligible = [ref for ref in references if ref["ledger"]["eligible"]]
    if len(eligible) > policy["maximum_source_eligible_rows"]:
        raise ValueError("Original declared consumed source-eligible row budget exceeded; no reselection.")
    grouped = defaultdict(list)
    for ref in eligible:
        grouped[participant_pair(ref["reader_record"])].append(ref)
    if len(grouped) > policy["maximum_pair_batches"]:
        raise ValueError("Original declared consumed exact-pair budget exceeded.")
    rows, checks, preservation, failures, total = [], [], [], [], {"attempts": 0}
    _, _, publication_files = load_publication(publication)
    for number, pair in enumerate(sorted(grouped), 1):
        refs = grouped[pair]; folder = output / ("batch_" + str(number).zfill(4)); folder.mkdir()
        save_new(folder / "consumed_context.json", {"assessment_split": SPLIT,
            "interpretation": LIMITATION, "source_rows": [ref["ledger"] for ref in refs]})
        try:
            ids = sorted({accession for side in pair for database, accession in side if database == "uniprotkb"})
            request = {"accessions": ids, "focus_uniprot": ids[0], "profile": "ppi", "relations": ["interactions"]}
            save_new(folder / "construction_request.json", {"assessment_split": SPLIT, "request": request})
            if construct is None:
                client = BudgetPharos(policy, folder, total)
                run_construction(client, request, folder / "cohort")
            else:
                # Explicit dependency injection for invented-only controls, never a hidden source fallback.
                construct(request, folder / "cohort")
            graph = attach_assay(folder / "cohort", publication, folder / "attached")
            if read_run(folder / "attached")[2] != graph:
                raise ValueError("Ordinary attached run did not reopen exactly.")
            answer = answer_assay_question(graph, source_run=str(folder / "attached"))
            save_answer(answer, folder / "answer")
            export_packet(folder / "attached", folder / "packet"); load_packet(folder / "packet")
            packet = [json.loads(line) for line in (folder / "packet/assay_observations.jsonl").read_text().splitlines()]
            exported = [json.loads(line) for line in (folder / "answer/assay_evidence.jsonl").read_text().splitlines()]
            expected_cohort = {target["id"] for target in graph["targets"]}
            oracle = [ref for ref in eligible if {"UniProtKB:" + accession for side in participant_pair(ref["reader_record"])
                        for database, accession in side if database == "uniprotkb"} <= expected_cohort]
            checks.extend(output_inventory_checks(oracle, graph["assay_observations"], answer["results"], packet, exported))
            wanted = {tuple(ref["ledger"][key] for key in ("publication_id", "artifact_sha256", "source_line")) for ref in refs}
            chosen = lambda row: tuple(row.get("source", {}).get(key) for key in ("publication_id", "artifact_sha256", "source_line")) in wanted
            observations = [row for row in graph["assay_observations"] if chosen(row)]
            results = [row for row in answer["results"] if chosen(row["source_observation"])]
            edge_ids = {row["graph_edge_id"] for row in observations}
            evaluation = evaluate_rows(refs, observations, results, [row for row in packet if chosen(row)],
                [row for row in exported if chosen(row["source_observation"])], (folder / "answer/report.html").read_text(),
                graph_edges=[edge for edge in graph["edges"] if edge.get("id") in edge_ids], columns=field_groups(),
                answer_bindings={key: answer[key] for key in ("answer_sha256", "graph_basis_sha256", "snapshot_sha256",
                    "assay_publication_sha256", "assay_attachment_sha256", "source_run")})
            for prefix in (folder / "attached/assay_source", folder / "packet/source/assay_source"):
                for name, raw in publication_files.items():
                    preservation.append({"batch": number, "file": str(prefix / name),
                                         "passed": (prefix / name).read_bytes() == raw})
        except Exception as exc:
            failure = {"batch": number, "error_type": type(exc).__name__, "error": str(exc),
                       "source_eligible_rows_retained_in_denominator": len(refs)}
            failures.append(failure); save_new(folder / "failure.json", failure)
            evaluation = evaluate_missing(refs)
        save_new(folder / "evaluation.json", evaluation)
        rows.extend(evaluation["rows"]); checks.extend(evaluation["global_checks"])
    return {"rows": rows, "global_checks": checks}, preservation, failures, total["attempts"]


def execute(contract_path, expected_sha):
    contract_path = ordinary(contract_path)
    contract = verify_contract(contract_path, expected_sha)
    output = contract_path.parent / "execution"; output.mkdir(exist_ok=False)
    save_new(output / "started.json", {"created_at": utcnow(), "assessment_split": SPLIT,
        "consumed_flow_freeze_sha256": expected_sha, "original_reserved_result_changed": False,
        "status": "consumed_development_access_only_not_another_reserved_execution"})
    try:
        result = _execute(contract, contract_path, expected_sha, output)
    except Exception as exc:
        failure = seal({"format": RESULT_FORMAT, "created_at": utcnow(), "status": "stopped_consumed_development_unscored",
            "assessment_split": SPLIT, "error_type": type(exc).__name__, "error": str(exc),
            "original_reserved_result_changed": False, "scientific_accuracy_measured": False,
            "interpretation": LIMITATION})
        save_new(output / "failure.json", failure)
        raise
    save_new(output / "report.json", seal(result))
    return result


def _execute(contract, contract_path, expected_sha, output):
    from biograph_steward.intact_final_publication import publish_material
    records, ledger, xml, files, catalog, studies, errors = inspect_captured(contract, output)
    verify_contract(contract_path, expected_sha)
    references = [{"ledger": item, "reader_record": record["reader_record"]} for item, record in zip(ledger, records)]
    audit = audit_consumed(xml, records, load_json(contract["consumed_inventory"]))
    save_new(output / "provenance_overlap.json", audit)
    accounting = {"physical_rows": len(ledger), "evidence_rows": sum(item["kind"] == "evidence" for item in ledger),
        "source_eligible_rows": sum(item["eligible"] for item in ledger), "source_eligible_rows_removed_for_consumption": 0,
        "assessment_split": SPLIT, "known_consumed_publication_ids": list(RESERVED)}
    save_new(output / "source_accounting.json", accounting)
    base = {"format": RESULT_FORMAT, "created_at": utcnow(), "assessment_split": SPLIT,
        "consumed_flow_freeze_sha256": expected_sha, "origin_reserved_freeze_sha256": ORIGIN_SHA,
        "historical_code_receipt_sha256": contract["historical_code_receipt_sha256"],
        "source_accounting": accounting, "studies": studies,
        "model_calls": 0, "gpu_runs": 0, "new_Java_reader_calls": 0, "new_IntAct_retrievals": 0,
        "scientific_accuracy_measured": False, "independent_validation_performed": False,
        "original_final_outcome_changed": False, "study_independence": "unverified", "interpretation": LIMITATION}
    if errors or audit["ambiguous_dataset_statements"]:
        return {**base, "status": "stopped_reference_or_lineage_gate_consumed_development_unscored",
            "projection_errors": errors, "ambiguous_dataset_statements": audit["ambiguous_dataset_statements"],
            "metrics": None, "source_eligible_denominator_preserved": accounting["source_eligible_rows"],
            "Pharos_calls": 0, "full_flow_completed": False}
    inspection = {"status": "consumed_development_inspected_not_final_score", "publication_ids": list(RESERVED),
        "assessment_split": SPLIT, "studies": studies, "interpretation": LIMITATION,
        "bindings": {"controls_report_sha256": sha(contract["controls_report"]),
            "runtime_bindings": contract["reader_runtime"], "execution_freeze_sha256": expected_sha}}
    files.update({"row_ledger.jsonl": b"".join(_encoded(item) for item in ledger),
        "protocol.json": PROTOCOL.read_bytes(), "semantic_amendment.json": AMENDMENT.read_bytes(),
        "inspection_report.json": _encoded(inspection), "execution_freeze.json": contract_path.read_bytes(),
        "controls_report.json": Path(contract["controls_report"]).read_bytes(),
        "xml_controls_report.json": Path(contract["xml_controls_report"]).read_bytes(),
        "LICENSE.md": LICENSE.read_bytes(), "consumed_provenance_overlap.json": _encoded(audit),
        "origin_execution_freeze.json": ORIGIN.read_bytes(),
        "historical_code_archive_receipt.json": Path(contract["historical_code_receipt"]).read_bytes()})
    bindings = {"assessment_split": SPLIT, "publication_ids": list(RESERVED),
        "execution_freeze_sha256": expected_sha, "origin_reserved_freeze_sha256": ORIGIN_SHA,
        "historical_code_receipt_sha256": contract["historical_code_receipt_sha256"],
        "protocol_sha256": PROTOCOL_SHA, "amendment_sha256": AMENDMENT_SHA,
        "result_sha256": hashlib.sha256(files["inspection_report.json"]).hexdigest(),
        "ledger_sha256": hashlib.sha256(files["row_ledger.jsonl"]).hexdigest(),
        "source_sha256": {entry["publication_id"].removeprefix("pubmed:"): entry["artifact_sha256"] for entry in catalog},
        "reader_sha256": {entry["publication_id"].removeprefix("pubmed:"): entry["reader_sha256"] for entry in catalog},
        "reader_runtime": contract["reader_runtime"], "xml_reader_runtime": contract["xml_reader_runtime"],
        "controls_report_sha256": sha(contract["controls_report"]),
        "xml_controls_report_sha256": sha(contract["xml_controls_report"]), "release": "2026-10-17"}
    publish_material(files, catalog, bindings, inspection, output / "publication")
    verify_contract(contract_path, expected_sha)
    evaluation, preservation, failures, calls = run_batches(references, output / "publication", output, contract["flow_policy"])
    metrics = summarize(evaluation, references, RESERVED)
    verify_contract(contract_path, expected_sha)
    for path, pin in contract["input_sha256"].items():
        if sha(ordinary(path)) != pin:
            raise ValueError("Captured input changed during consumed replay.")
    denominator = accounting["source_eligible_rows"]
    passed = denominator > 0 and not failures and all(item["passed"] for item in evaluation["global_checks"] + preservation) and metrics["strict_fidelity"]["numerator"] == denominator
    return {**base, "status": "passed_consumed_development_only" if passed else "not_evaluable_empty" if not denominator else "failed_consumed_development_only",
        "metrics": metrics, "row_evaluation": evaluation, "source_preservation_checks": preservation,
        "flow_failures": failures, "Pharos_calls": calls, "full_flow_completed": passed,
        "all_source_eligible_rows_retained_in_denominator": metrics["strict_fidelity"]["denominator"] == denominator,
        "implementation_sha256": contract["implementation_sha256"]}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    prepare_parser = sub.add_parser("prepare")
    prepare_parser.add_argument("--output", type=Path, required=True)
    prepare_parser.add_argument("--historical-code-receipt", type=Path, required=True)
    prepare_parser.add_argument("--allow-fresh-pharos", action="store_true")
    run_parser = sub.add_parser("execute")
    run_parser.add_argument("--contract", type=Path, required=True)
    run_parser.add_argument("--expected-sha256", required=True)
    args = parser.parse_args()
    value = prepare(args.output, args.historical_code_receipt, allow_pharos=args.allow_fresh_pharos) if args.command == "prepare" else execute(args.contract, args.expected_sha256)
    print(json.dumps({"status": value.get("status", "consumed_contract_prepared"),
                      "content_sha256": value.get("content_sha256"), "assessment_split": SPLIT}))


if __name__ == "__main__":
    main()
