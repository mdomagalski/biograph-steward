#!/usr/bin/env python3
"""Validate the official PSI-JAMI XML projection using invented controls only.

This is a reader/integration check, not XSD conformance, study-lineage inference
or scientific accuracy. No selected IntAct XML URL is accepted here.
"""
from __future__ import annotations

import argparse
from copy import deepcopy
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from biograph_steward.client import digest, utcnow
from scripts.validate_intact_reader_controls import runtime_bindings as reader_bindings

CONTROLS = ROOT / "tests/fixtures/intact_xml/controls.json"
EXPECTED_INVENTORY_SHA = "eccec60a30e993591bb43ef41ebf29c163a85345564d4f856ab73096aa4a0f62"
AMENDMENT = CONTROLS.parent / "controls_amendment.json"
EXPECTED_AMENDMENT_SHA = "5a9d3652e85fd1cdb1948dac50bbb7d0b460cbc1cabc6e19a54c9781b466a929"
BRIDGE = ROOT / "tools/intact_xml_reader/src/main/java/org/biograph/IntactXmlReader.java"
POM = ROOT / "tools/intact_xml_reader/pom.xml"
FORMAT = "biograph-steward.intact-xml-controls-result.v1"


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def save_new(path, value):
    with Path(path).open("x", encoding="utf-8") as stream:
        json.dump(value, stream, indent=2, ensure_ascii=True, allow_nan=False)
        stream.write("\n")


def runtime_bindings(classes, classpath_file, java="java"):
    """Reuse the tested runtime/JAR binding; bind the separate XML implementation."""
    result = reader_bindings(classes, classpath_file, java)
    result["bridge_source"] = {"path": str(BRIDGE), "sha256": sha(BRIDGE)}
    result["bridge_sources"] = {str(path.resolve()): sha(path) for path in
                                sorted(BRIDGE.parent.glob("*.java"))}
    result["pom"] = {"path": str(POM), "sha256": sha(POM)}
    result["runtime_binding_helper"] = sha(ROOT / "scripts/validate_intact_reader_controls.py")
    return result


def term_id(term):
    return (term or {}).get("mi_id")


def xref_tuple(xref):
    """Keep database, exact ID and qualifier separate; no citation interpretation."""
    return (((xref.get("database") or {}).get("name") or "").lower(),
            xref.get("id"), term_id(xref.get("qualifier")))


def references(obj):
    return list(obj.get("identifiers") or []) + list(obj.get("xrefs") or [])


def parse_transport(stdout):
    rows = [json.loads(line) for line in stdout.decode("utf-8").splitlines()]
    summaries = [row for row in rows if row.get("record_kind") == "file_summary"]
    if len(summaries) != 1 or not rows or rows[-1] is not summaries[0]:
        raise ValueError("Official bridge must emit exactly one final file summary.")
    evidence = [row for row in rows if row.get("record_kind") == "evidence"]
    if len(rows) != len(evidence) + 1:
        raise ValueError("Unknown reader record kind.")
    if any(row.get("format") != "biograph-steward.intact-xml-evidence.v1" for row in rows):
        raise ValueError("Unexpected XML reader transport format.")
    if summaries[0].get("evidence_count") != len(evidence):
        raise ValueError("Terminal evidence count does not account for emitted records.")
    if [row.get("evidence_sequence") for row in evidence] != list(range(1, len(evidence) + 1)):
        raise ValueError("Evidence sequence is missing or duplicated.")
    return evidence, summaries[0], rows


def assess_xml_summary(summary, returncode):
    """Treat reader failure/invalid diagnostics as visible quarantine, not absence."""
    reasons = []
    if returncode != 0 or summary.get("status") not in {"completed", "completed_with_diagnostics"}:
        reasons.append("reader_failed")
    if summary.get("error") is not None:
        reasons.append("reader_error")
    for diagnostic in summary.get("diagnostics") or []:
        callback = diagnostic.get("callback") or ""
        if callback.startswith("onInvalid") or callback in {"bridge_close_failure", "onUnresolvedReference"}:
            reasons.append("invalid_reader_diagnostic")
    return {"quarantined": bool(reasons), "reasons": sorted(set(reasons)),
            "diagnostic_count": len(summary.get("diagnostics") or []),
            "study_independence": "not_determined", "study_reuse": "not_determined"}


def check_case(case, stdout, returncode, raw):
    evidence, summary, _ = parse_transport(stdout)
    expected, checks = case["expected"], []
    def check(name, actual, want):
        checks.append({"name": name, "passed": actual == want,
                       "expected": deepcopy(want), "observed": deepcopy(actual)})
    check("fixture_bytes_bound", hashlib.sha256(raw).hexdigest(), case["sha256"])
    check("input_sha256", summary.get("input_sha256"), hashlib.sha256(raw).hexdigest())
    check("input_bytes", summary.get("input_bytes"), len(raw))
    if "evidence_count" in expected:
        check("evidence_count", len(evidence), expected["evidence_count"])
    security = summary.get("security") or {}
    check("external_entities_disabled", security.get("support_external_entities"), False)
    check("dtd_disabled", security.get("support_dtd"), False)
    check("external_resolver_denied", security.get("external_resolver"), "deny")
    check("no_schema_network_validation", security.get("schema_validation_invoked"), False)
    gate = assess_xml_summary(summary, returncode)
    check("no_study_reuse_inference", gate["study_reuse"], "not_determined")
    check("no_study_independence_inference", gate["study_independence"], "not_determined")
    if expected["status"] in {"failed", "quarantined"}:
        check("failure_visible", gate["quarantined"], True)
        if expected["status"] == "failed":
            check("terminal_failure", summary.get("status"), "failed")
            check("nonzero_failure_exit", returncode != 0, True)
        if expected.get("required_callback"):
            check("required_invalid_callback", expected["required_callback"] in {d.get("callback") for d in summary.get("diagnostics") or []}, True)
        if case.get("security_expected"):
            security_expected = case["security_expected"]
            check("resolver_not_invoked", security.get("resolver_attempt_count"), security_expected["require_resolver_attempt_count"])
            error_text = json.dumps(summary.get("error") or {})
            check("entity_rejected_by_parser", any(s in error_text.lower() for s in ("undeclared general entity", "external xml resource resolution is disabled", "dtd is disabled", "doctype is disabled")), True)
            for error_type in security_expected["forbid_error_types"]:
                check("no_resolution_failure." + error_type, error_type not in error_text, True)
            if expected.get("forbidden_text"):
                check("external_uri_not_accessed", expected["forbidden_text"] not in error_text, True)
        return checks
    check("java_exit", returncode, 0)
    check("reader_accepted", gate["quarantined"], False)
    check("tested_xml_version", summary.get("xml_version"), "v2_5_4")
    check("all_evidence_tested_xml_version", [row.get("xml_version") for row in evidence], ["v2_5_4"] * len(evidence))
    if len(evidence) != 1:
        return checks
    record = evidence[0]["evidence"]
    check("negative", record.get("negative"), expected["negative"])
    check("interaction_type", [term_id(t) for t in record.get("interaction_types") or []], ["MI:0914"])
    experiments = record.get("experiments") or []
    check("full_experiment_count", len(experiments), expected["experiment_count"])
    check("detection_methods", [term_id(exp.get("detection_method")) for exp in experiments], expected["detection_method_ids"])
    check("host_taxids", sorted({host.get("taxid") for exp in experiments for host in exp.get("host_organisms") or []}), expected["host_taxids"])
    for number, exp in enumerate(experiments, 1):
        publication = exp.get("publication") or {}
        check(f"experiment_{number}.publication_identity", publication.get("pubmed_id"), "99000001")
        pub_refs = {xref_tuple(x) for x in references(publication)}
        exp_refs = {xref_tuple(x) for x in references(exp)}
        check(f"experiment_{number}.publication_primary_qualified", ("pubmed", "99000001", "MI:0358") in pub_refs, True)
        check(f"experiment_{number}.experiment_primary_qualified", ("intact", "EBI-SYNTH-EXP" + str(number), "MI:0358") in exp_refs, True)
        typed = expected["typed_provenance"] and number == 1
        check(f"experiment_{number}.publication_see_also_distinct", ("pubmed", "99000002", "MI:0361") in pub_refs, typed)
        check(f"experiment_{number}.experiment_see_also_distinct", ("pubmed", "99000003", "MI:0361") in exp_refs, typed)
        notes = {(term_id(x.get("topic")), x.get("value")) for x in exp.get("annotations") or []}
        check(f"experiment_{number}.relationship_comment", ("MI:0612", "Synthetic primary/subsidiary relationship note; interpretation requires review.") in notes, typed)
        check(f"experiment_{number}.uniprot_export_annotation", any((x.get("topic") or {}).get("name") == "uniprot-dr-export" and x.get("value") == "No" for x in exp.get("annotations") or []), typed)
    interaction_refs = {xref_tuple(x) for x in references(record)}
    check("interaction_primary_identity", ("intact", "EBI-SYNTH-INTERACTION", "MI:0356") in interaction_refs, True)
    check("interaction_imex_primary", ("imex", "IM-SYNTH-1", "MI:0662") in interaction_refs, expected["typed_provenance"])
    check("interaction_generic_see_also", ("intact", "EBI-SYNTH-SEE-ALSO", "MI:0361") in interaction_refs, expected["typed_provenance"])
    check("imex_accessor_preserved", record.get("imex_id"), "IM-SYNTH-1" if expected["typed_provenance"] else None)
    participants = record.get("participants") or []
    check("participant_count", len(participants), 2)
    check("participant_source_order", [p.get("source_index") for p in participants], [1, 2])
    for i, (participant, accession, role) in enumerate(zip(participants, ["P12345-2", "P12346"], ["MI:0496", "MI:0498"]), 1):
        interactor = participant.get("interactor") or {}
        check(f"participant_{i}.source_accession", ("uniprotkb", accession, "MI:0356") in {xref_tuple(x) for x in references(interactor)}, True)
        check(f"participant_{i}.taxon", (interactor.get("organism") or {}).get("taxid"), 9606)
        check(f"participant_{i}.type", term_id(interactor.get("type")), "MI:0326")
        check(f"participant_{i}.biological_role", term_id(participant.get("biological_role")), "MI:0499")
        role_ids = expected.get("experimental_role_ids", [["MI:0496"], ["MI:0498"]])[i - 1]
        check(f"participant_{i}.experimental_role", [term_id(item.get("term")) for item in participant.get("experimental_roles") or []], role_ids)
        if expected.get("role_experiment_ids"):
            check(f"participant_{i}.role_experiment_ids", [[exp.get("xml_id") for exp in item.get("experiments") or []] for item in participant.get("experimental_roles") or []], expected["role_experiment_ids"][i - 1])
    return checks


def inventory():
    if sha(CONTROLS) != EXPECTED_INVENTORY_SHA:
        raise ValueError("Synthetic XML inventory changed; version controls instead of tuning outcomes.")
    value = json.loads(CONTROLS.read_text())
    if value.get("synthetic_only") is not True or value.get("selected_xml_bodies_accessed") is not False:
        raise ValueError("XML controls must be synthetic only.")
    if sha(AMENDMENT) != EXPECTED_AMENDMENT_SHA:
        raise ValueError("Additive XML control amendment changed.")
    amendment = json.loads(AMENDMENT.read_text())
    if amendment.get("original_inventory_sha256") != EXPECTED_INVENTORY_SHA:
        raise ValueError("XML controls amendment does not bind the original six fixtures.")
    value["cases"].extend(amendment["cases"])
    for case in value["cases"]:
        if case["id"] in amendment["strengthen_existing"]:
            case["security_expected"] = amendment["strengthen_existing"][case["id"]]
    seen = set()
    for case in value["cases"]:
        name = case["file"]
        if case.get("synthetic") is not True or Path(name).name != name or not name.endswith(".xml") or name in seen:
            raise ValueError("Only isolated synthetic XML basenames are accepted.")
        seen.add(name)
        path = CONTROLS.parent / name
        if path.is_symlink() or sha(path) != case["sha256"]:
            raise ValueError("Synthetic XML source changed: " + name)
    return value


def verify_controls(report):
    data = deepcopy(report)
    supplied = data.pop("content_sha256", None)
    if supplied != digest(data):
        raise ValueError("XML controls report content seal is invalid.")
    value = inventory()
    if (report.get("format") != FORMAT or report.get("status") != "passed"
            or report.get("all_checks_passed") is not True
            or report.get("runner_sha256") != sha(__file__)
            or report.get("controls_inventory_sha256") != EXPECTED_INVENTORY_SHA
            or report.get("controls_amendment_sha256") != EXPECTED_AMENDMENT_SHA
            or [case["id"] for case in report.get("cases", [])] != [case["id"] for case in value["cases"]]
            or not all(case.get("checks") and all(check.get("passed") is True for check in case["checks"]) for case in report["cases"])):
        raise ValueError("A current complete passing synthetic XML control run is required.")


def run_controls(classes, classpath_file, output, java="java"):
    cases = inventory()
    bindings = runtime_bindings(classes, classpath_file, java)
    output = Path(output).resolve()
    output.mkdir(parents=True, exist_ok=False)
    frozen = output / "frozen_inputs"; frozen.mkdir()
    (output / "cases").mkdir()
    (frozen / "controls.json").write_bytes(CONTROLS.read_bytes())
    (frozen / "controls_amendment.json").write_bytes(AMENDMENT.read_bytes())
    for case in cases["cases"]:
        (frozen / case["file"]).write_bytes((CONTROLS.parent / case["file"]).read_bytes())
        if sha(frozen / case["file"]) != case["sha256"]:
            raise ValueError("Synthetic fixture changed while freezing: " + case["file"])
    report = {"format": FORMAT, "created_at": utcnow(), "status": "running",
              "runtime_bindings": bindings, "runner_sha256": sha(__file__),
              "controls_inventory_sha256": EXPECTED_INVENTORY_SHA,
              "controls_amendment_sha256": EXPECTED_AMENDMENT_SHA,
              "synthetic_only": True, "selected_xml_bodies_accessed": False,
              "model_calls": 0, "network_source_calls": 0, "cases": [], "all_checks_passed": False,
              "scope": "Official-reader provenance/context projection controls, not XSD conformance or scientific accuracy."}
    save_new(output / "preparation.json", report)
    classpath = os.pathsep.join([str(Path(classes).resolve()), *[j["path"] for j in bindings["dependency_jars"]]])
    try:
        for case in cases["cases"]:
            if runtime_bindings(classes, classpath_file, java) != bindings:
                raise ValueError("XML implementation/runtime changed after controls freeze.")
            if sha(frozen / case["file"]) != case["sha256"]:
                raise ValueError("Frozen synthetic fixture changed before official reader execution.")
            command = [bindings["java"]["executable"], "-cp", classpath,
                       "org.biograph.IntactXmlReader", str(frozen / case["file"])]
            stdout = output / "cases" / (case["id"] + ".jsonl")
            stderr = output / "cases" / (case["id"] + ".stderr")
            try:
                result = subprocess.run(command, capture_output=True, timeout=60, check=False)
            except subprocess.TimeoutExpired as error:
                stdout.write_bytes(error.stdout or b""); stderr.write_bytes(error.stderr or b"")
                report["cases"].append({"id": case["id"], "timeout_seconds": 60,
                    "stdout_sha256": sha(stdout), "stderr_sha256": sha(stderr),
                    "checks": [{"name": "reader_completed", "passed": False}]})
                raise ValueError("Synthetic XML reader timed out; partial streams retained: " + case["id"])
            stdout.write_bytes(result.stdout); stderr.write_bytes(result.stderr)
            entry = {"id": case["id"], "fixture_sha256": case["sha256"], "returncode": result.returncode,
                     "stdout_sha256": sha(stdout), "stderr_sha256": sha(stderr), "checks": []}
            report["cases"].append(entry)
            try:
                entry["checks"] = check_case(case, result.stdout, result.returncode, (frozen / case["file"]).read_bytes())
            except (ValueError, KeyError, TypeError, UnicodeError) as error:
                entry["checks"].append({"name": "complete_readable_official_transport", "passed": False, "error": str(error)})
            if sha(frozen / case["file"]) != case["sha256"]:
                raise ValueError("Frozen synthetic fixture changed during official reader execution.")
        if runtime_bindings(classes, classpath_file, java) != bindings or sha(__file__) != report["runner_sha256"]:
            raise ValueError("XML implementation/runtime/validator changed during controls.")
        checks = [check for case in report["cases"] for check in case["checks"]]
        report["all_checks_passed"] = bool(checks) and all(check["passed"] for check in checks)
        report["status"] = "passed" if report["all_checks_passed"] else "failed"
        report["check_counts"] = {"total": len(checks), "passed": sum(c["passed"] for c in checks), "failed": sum(not c["passed"] for c in checks)}
    except (ValueError, OSError, subprocess.SubprocessError) as error:
        report["status"] = "failed"; report["error"] = str(error)
    report["content_sha256"] = digest(report)
    save_new(output / "report.json", report)
    return report


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--classpath-file", type=Path, required=True)
    parser.add_argument("--classes", type=Path, default=ROOT / "tools/intact_xml_reader/target/classes")
    parser.add_argument("--java", default="java")
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args(argv)
    try:
        report = run_controls(args.classes, args.classpath_file, args.output, args.java)
    except (ValueError, OSError, subprocess.SubprocessError) as error:
        parser.exit(2, str(error) + "\n")
    print(json.dumps({"status": report["status"], "report": str(args.output / "report.json"), "check_counts": report.get("check_counts")}))
    return 0 if report["all_checks_passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
