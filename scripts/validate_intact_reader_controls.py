#!/usr/bin/env python3
"""Execute only invented MITAB controls through the pinned official Java reader.

This runner checks projections and diagnostics, not biology. Cell interpretation
belongs to JAMI; Python checks framing, explicit format literals and observations.
No IntAct development or reserved reference input is accepted by this command.
"""
from __future__ import annotations

import argparse
from collections import Counter
from copy import deepcopy
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
from types import SimpleNamespace

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from biograph_steward.client import digest, utcnow  # noqa: E402

CONTROLS = ROOT / "tests/fixtures/intact_reader/controls.json"
EXPECTED_CONTROLS_SHA256 = "de2e90ac9ec81c04bd0257f8a589ce9c750dcb0b4e13c7bab4adf595984e212f"
BRIDGE = ROOT / "tools/intact_reader/src/main/java/org/biograph/IntactReader.java"
POM = ROOT / "tools/intact_reader/pom.xml"
FORMAT = "biograph-steward.intact-reader-controls-result.v1"
FIELD_COLUMNS = {
    "primary_ids_a": 1, "primary_ids_b": 2,
    "alternative_ids_a": 3, "alternative_ids_b": 4,
    "detection_methods": 7, "publication_ids": 9,
    "taxa_a": 10, "taxa_b": 11, "interaction_types": 12,
    "source_databases": 13, "evidence_ids": 14, "complex_expansion": 16,
    "biological_roles_a": 17, "biological_roles_b": 18,
    "experimental_roles_a": 19, "experimental_roles_b": 20,
    "interactor_types_a": 21, "interactor_types_b": 22,
    "interaction_annotations": 28, "host_taxa": 29,
    "identification_methods_a": 41, "identification_methods_b": 42,
}
MULTIVALUE_FIELDS = {
    "multiple_unique_identifiers": "primary_ids_a",
    "multiple_participant_taxa": "taxa_a",
    "multiple_biological_roles": "biological_roles_a",
    "multiple_experimental_roles": "experimental_roles_a",
    "multiple_interactor_types": "interactor_types_a",
    "multiple_detection_methods": "detection_methods",
    "multiple_interaction_types": "interaction_types",
    "multiple_hosts": "host_taxa",
    "multiple_expansion_methods": "complex_expansion",
    "multiple_identification_methods": "identification_methods_a",
}
MULTIVALUE_EXPECTED = {
    "multiple_unique_identifiers": ("id", ["P12345-2", "P12346"]),
    "multiple_participant_taxa": ("taxid", [9606, 10090]),
    "multiple_biological_roles": ("mi_id", ["MI:0499", "MI:0684"]),
    "multiple_experimental_roles": ("mi_id", ["MI:0496", "MI:0498"]),
    "multiple_interactor_types": ("mi_id", ["MI:0326", "MI:0327"]),
    "multiple_detection_methods": ("mi_id", ["MI:0006", "MI:0001"]),
    "multiple_interaction_types": ("mi_id", ["MI:0914", "MI:0190"]),
    "multiple_hosts": ("taxid", [4932, 9606]),
    "multiple_expansion_methods": ("mi_id", ["MI:1060", "MI:1061"]),
    "multiple_identification_methods": ("mi_id", ["MI:0102", "MI:0002"]),
}
INVALID_CALLBACKS = {
    "onInvalidSyntax", "onInvalidOrganismTaxid", "onInvalidPosition",
    "onInvalidRange", "onInvalidStoichiometry", "bridge_reader_error",
    "bridge_close_error", "bridge_source_field_error",
    "bridge_source_field_trailing_input", "bridge_invalid_column_count",
}


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def write_json(path, value):
    Path(path).write_text(json.dumps(value, indent=2, ensure_ascii=True,
                                    allow_nan=False) + "\n", encoding="utf-8")


def runtime_bindings(classes, classpath_file, java="java"):
    """Return exact local code/dependency/runtime bindings for a later gate."""
    classes, classpath_file = Path(classes).resolve(), Path(classpath_file).resolve()
    compiled = {str(path.relative_to(classes)): sha(path)
                for path in sorted(classes.rglob("*.class")) if path.is_file()}
    if not classes.is_dir() or not compiled:
        raise ValueError("Compile the official-reader bridge before validation.")
    dependencies = []
    for entry in classpath_file.read_text(encoding="utf-8").strip().split(os.pathsep):
        path = Path(entry).resolve()
        if not entry or not path.is_file() or path.suffix != ".jar":
            raise ValueError("Resolved classpath entries must be existing local JAR files.")
        dependencies.append({"path": str(path), "sha256": sha(path), "bytes": path.stat().st_size})
    executable = shutil.which(str(java))
    if not executable:
        raise ValueError("The requested Java executable was not found.")
    executable = str(Path(executable).resolve())
    version = subprocess.run([executable, "-version"], capture_output=True, text=True,
                             timeout=20, check=False)
    if version.returncode:
        raise ValueError("Java could not report its runtime version.")
    return {
        "classes_directory": str(classes), "classes_sha256": compiled,
        "classpath_file": str(classpath_file), "classpath_file_sha256": sha(classpath_file),
        "dependency_jars": dependencies,
        "bridge_source": {"path": str(BRIDGE), "sha256": sha(BRIDGE)},
        "pom": {"path": str(POM), "sha256": sha(POM)},
        "java": {"executable": executable, "version_stdout": version.stdout,
                 "executable_sha256": sha(executable),
                 "version_stderr": version.stderr, "version_returncode": version.returncode},
    }


def _diagnostics(row):
    result = list(row.get("diagnostics") or [])
    for field in (row.get("source_fields") or {}).values():
        result.extend(field.get("diagnostics") or [])
    return result


def assess_reader_row(row):
    """Conservative framing/literal/invalid-reader gate, independent of eligibility.

    Warnings about lossy model objects are retained separately. Full official
    source-field lists can preserve those values without repairing the model.
    """
    cells = row.get("raw_cells")
    reasons = []
    if not isinstance(cells, list) or len(cells) != 42:
        reasons.append("column_count_not_42")
    literal = cells[35] if isinstance(cells, list) and len(cells) >= 36 else None
    valid_literal = isinstance(literal, str) and literal in {"true", "false", "-"}
    if not valid_literal:
        reasons.append("negative_literal_invalid")
    counts = Counter(item.get("callback") for item in _diagnostics(row))
    if counts["onInvalidStoichiometry"]:
        reasons.append("reader_invalid_stoichiometry")
    if counts["onInvalidSyntax"]:
        reasons.append("reader_invalid_syntax")
    if any(count and isinstance(name, str)
           and (name.startswith("onInvalid") or name in INVALID_CALLBACKS)
           and name not in {"onInvalidSyntax", "onInvalidStoichiometry", "bridge_invalid_column_count"}
           for name, count in counts.items()):
        reasons.append("reader_invalid_diagnostic")
    if any(field.get("status") == "invalid" for field in (row.get("source_fields") or {}).values()):
        reasons.append("source_field_invalid")
    if isinstance(cells, list) and len(cells) == 42 and row.get("parsed_count") != 1:
        reasons.append("reader_did_not_return_one_interaction")
    return {
        "quarantined": bool(reasons), "quarantine_reasons": sorted(set(reasons)),
        "column_count": len(cells) if isinstance(cells, list) else None,
        "negative_literal": literal,
        "negative_origin": "mitab27_default_false" if literal == "-" else
                           "explicit" if valid_literal else "invalid",
        "negative_value": literal == "true" if valid_literal else None,
        "expansion_annotation_supplied": cells[15] != "-" if isinstance(cells, list) and len(cells) == 42 else None,
        "binary_origin": "unknown",
    }


def _term_id(value):
    return (value or {}).get("mi_id")


def observed_aliases(row):
    """Map only official-reader JSON objects to the fixture's conceptual aliases."""
    value = row.get("interaction") or {}
    by_side = {item.get("side"): item for item in value.get("participants") or []}
    participants = [by_side.get("A", {}), by_side.get("B", {})]
    return {
        "negative": value.get("negative"),
        "detection_method_id": _term_id(value.get("detection_method")),
        "interaction_type_id": _term_id(value.get("interaction_type")),
        "host_taxid": value.get("host_taxid"),
        "participant_taxids": [item.get("taxid") for item in participants],
        "participant_type_ids": [_term_id(item.get("interactor_type")) for item in participants],
        "experimental_role_ids": [_term_id(item.get("experimental_role")) for item in participants],
        "biological_role_ids": [_term_id(item.get("biological_role")) for item in participants],
        "participant_stoichiometry": [None if item.get("stoichiometry") is None else
             [item["stoichiometry"].get("min"), item["stoichiometry"].get("max")] for item in participants],
        "participant_identification_method_ids": [[_term_id(term) for term in item.get("identification_methods") or []]
                                                    for item in participants],
        "expansion_mi_ids": [_term_id(item.get("topic")) for item in value.get("annotations") or []
                             if _term_id(item.get("topic")) in {"MI:1060", "MI:1061"}],
        "participant_annotation_texts": [[item.get("value") for item in participant.get("annotations") or []]
                                         for participant in participants],
    }


def check_case(case, rows, raw_bytes):
    """Check the immutable fixture contract against observations, without parsing cells."""
    checks = []
    def check(name, actual, expected):
        checks.append({"name": name, "passed": actual == expected,
                       "expected": deepcopy(expected), "observed": deepcopy(actual)})
    lines = raw_bytes.decode("utf-8").splitlines()
    check("physical_row_accounting", len(rows), len(lines))
    for index, (line, row) in enumerate(zip(lines, rows), 1):
        prefix = "line_" + str(index) + "."
        raw_cells = line.split("\t")
        check(prefix + "line_number", row.get("line_number"), index)
        check(prefix + "raw_line", row.get("raw_line"), line)
        check(prefix + "raw_cells", row.get("raw_cells"), raw_cells)
        check(prefix + "parsed_count_consistent", row.get("parsed_count"), len(row.get("interactions") or []))
        interactions = row.get("interactions") or []
        check(prefix + "singular_interaction_consistent", row.get("interaction"), interactions[0] if len(interactions) == 1 else None)
        gate = assess_reader_row(row)
        if case.get("application_expected", {}).get("must_be_quarantined"):
            check(prefix + "required_quarantine", gate["quarantined"], True)
        for reason in case.get("application_expected", {}).get("quarantine_reasons", []):
            check(prefix + "quarantine." + reason, reason in gate["quarantine_reasons"], True)
        check(prefix + "no_binary_origin_inference", gate["binary_origin"], "unknown")
        if len(raw_cells) != 42:
            # The official reader still observes other versions; protocol
            # eligibility is independently stricter than reader acceptance.
            check(prefix + "framing_quarantine", gate["quarantined"], True)
            expected_count = case.get("reader_expected", {}).get("interaction_count")
            if expected_count is not None:
                check(prefix + "official_reader_count", row.get("parsed_count"), expected_count)
            continue
        fields = row.get("source_fields") or {}
        check(prefix + "source_field_inventory", sorted(fields), sorted(FIELD_COLUMNS))
        for name, column in FIELD_COLUMNS.items():
            field = fields.get(name) or {}
            check(prefix + name + ".column", field.get("column"), column)
            check(prefix + name + ".raw", field.get("raw"), raw_cells[column - 1])
            if raw_cells[column - 1] == "-":
                check(prefix + name + ".missing_status", field.get("status"), "missing")
                check(prefix + name + ".missing_values", field.get("values"), [])
                check(prefix + name + ".missing_diagnostics", field.get("diagnostics"), [])
            elif name in case.get("application_expected", {}).get("expected_invalid_source_fields", []):
                invalid = field.get("status") == "invalid" or any(
                    item.get("callback") in INVALID_CALLBACKS for item in field.get("diagnostics") or [])
                check(prefix + name + ".invalid_or_diagnosed", invalid, True)
            else:
                check(prefix + name + ".official_values_present", bool(field.get("values")), True)
                check(prefix + name + ".not_invalid", field.get("status") != "invalid", True)
        if case["id"] in MULTIVALUE_FIELDS:
            field = fields.get(MULTIVALUE_FIELDS[case["id"]]) or {}
            check(prefix + "full_source_multivalue_retained", len(field.get("values") or []), 2)
            key, exact_values = MULTIVALUE_EXPECTED[case["id"]]
            check(prefix + "full_source_multivalue_exact", [item.get(key) for item in field.get("values") or []], exact_values)
        expected = case.get("reader_expected", {})
        if expected.get("interaction_count") is not None:
            check(prefix + "interaction_count", row.get("parsed_count"), expected["interaction_count"])
        observed = observed_aliases(row)
        counts = Counter(item.get("callback") for item in row.get("diagnostics") or [])
        for name, value in expected.items():
            if name == "interaction_count":
                continue
            if name == "listener_exact_counts":
                check(prefix + name, dict(counts), value)
            elif name == "listener_minimum_counts":
                for callback, count in value.items():
                    check(prefix + callback + ".minimum_count", counts[callback] >= count, True)
            elif name == "participant_annotation_text_contains":
                for side, text in enumerate(value):
                    if text is not None:
                        check(prefix + name + "." + str(side), text in observed["participant_annotation_texts"][side], True)
            else:
                if name not in observed:
                    raise ValueError("Unhandled fixture expectation: " + name)
                check(prefix + name, observed[name], value)
        semantics = case.get("source_semantics", {})
        for name in ("negative_literal", "negative_origin", "expansion_annotation_supplied"):
            if name in semantics:
                check(prefix + "source_semantics." + name, gate[name], semantics[name])
        if "participant_id_values" in semantics:
            observed_ids = [(fields.get("primary_ids_" + side) or {}).get("values", []) for side in ("a", "b")]
            check(prefix + "exact_primary_identifiers", [[item.get("id") for item in side] for side in observed_ids],
                  [[value] for value in semantics["participant_id_values"]])
    return checks


def supplemental_controls(inventory):
    """Freeze extra invented recovery checks without editing the original 30."""
    base = [inventory["baseline_columns_1based"][str(index)] for index in range(1, 43)]
    broken_quote = base.copy()
    broken_quote[4] = 'unknown:"unterminated'
    trailing = base.copy()
    trailing[6] += "UNCONSUMED_SUFFIX"
    definitions = [
        ("supplemental_row_local_lexical_recovery", [base, broken_quote, base],
         [{}, {"must_be_quarantined": True}, {}]),
        ("supplemental_field_trailing_suffix", [trailing],
         [{"must_be_quarantined": True, "expected_invalid_source_fields": ["detection_methods"]}]),
    ]
    result = []
    for identifier, rows, applications in definitions:
        raw = ("\n".join("\t".join(row) for row in rows) + "\n").encode("utf-8")
        case = {"id": identifier, "input_tsv": identifier + ".tsv", "synthetic": True,
                "supplemental": True, "sha256": hashlib.sha256(raw).hexdigest(),
                "source_line_count": len(rows), "raw_column_counts": [42] * len(rows),
                "line_contracts": [{"id": identifier + "." + str(index),
                    "reader_expected": {"interaction_count": None if application else 1},
                    "application_expected": application}
                    for index, application in enumerate(applications, 1)]}
        result.append((case, raw))
    return result


def check_supplemental(case, rows, raw):
    """Use the same observation checks, preserving original physical attribution."""
    lines = raw.decode("utf-8").splitlines()
    checks = [{"name": "physical_row_accounting", "passed": len(rows) == len(lines),
               "expected": len(lines), "observed": len(rows)}]
    for index, (row, line, contract) in enumerate(zip(rows, lines, case["line_contracts"]), 1):
        # check_case expects a single line numbered1. Rebase only the copied
        # observation for that local check; the stored source_rows stay exact.
        rebased = deepcopy(row)
        rebased["line_number"] = 1
        local = check_case(contract, [rebased], (line + "\n").encode("utf-8"))
        for check in local:
            check["name"] = "physical_line_" + str(index) + "." + check["name"]
        checks.extend(local)
        checks.append({"name": "physical_line_" + str(index) + ".original_attribution",
                       "passed": row.get("line_number") == index,
                       "expected": index, "observed": row.get("line_number")})
    return checks


def run_controls(classes, classpath_file, output, java="java"):
    output = Path(output).absolute()
    if output.exists() or output.is_symlink():
        raise ValueError("Choose a new controls output directory; previous outcomes are immutable.")
    inventory_bytes = CONTROLS.read_bytes()
    if hashlib.sha256(inventory_bytes).hexdigest() != EXPECTED_CONTROLS_SHA256:
        raise ValueError("The original 30-control inventory changed; preserve and version any replacement.")
    inventory = json.loads(inventory_bytes)
    if inventory.get("synthetic_only") is not True or inventory.get("candidate_reference_rows_accessed") is not False:
        raise ValueError("This runner accepts only the repository's synthetic controls.")
    bindings = runtime_bindings(classes, classpath_file, java)
    inputs = []
    seen_ids, seen_names = set(), set()
    for case in inventory["cases"]:
        name = case["input_tsv"]
        if (not re.fullmatch(r"[A-Za-z0-9_-]{1,80}", case["id"])
                or case["id"] in seen_ids or name in seen_names
                or Path(name).name != name or not name.endswith(".tsv") or case.get("synthetic") is not True):
            raise ValueError("Only isolated local synthetic TSV basenames are allowed.")
        seen_ids.add(case["id"]); seen_names.add(name)
        raw = (CONTROLS.parent / name).read_bytes()
        if hashlib.sha256(raw).hexdigest() != case["sha256"]:
            raise ValueError("Frozen synthetic fixture changed: " + name)
        if (len(raw.splitlines()) != case["source_line_count"]
                or [len(line.split(b"\t")) for line in raw.splitlines()] != case["raw_column_counts"]):
            raise ValueError("Synthetic fixture framing differs from its frozen inventory: " + name)
        inputs.append((case, raw))
    inputs.extend(supplemental_controls(inventory))
    output.mkdir(parents=True, exist_ok=False)
    frozen, results = output / "frozen_inputs", output / "cases"
    frozen.mkdir(); results.mkdir()
    (frozen / "controls.json").write_bytes(inventory_bytes)
    (frozen / "IntactReader.java").write_bytes(BRIDGE.read_bytes())
    (frozen / "pom.xml").write_bytes(POM.read_bytes())
    (frozen / "classpath.txt").write_bytes(Path(classpath_file).read_bytes())
    for case, raw in inputs:
        (frozen / case["input_tsv"]).write_bytes(raw)
    report = {"format": FORMAT, "created_at": utcnow(), "status": "running",
              "runtime_bindings": bindings, "runner_sha256": sha(__file__),
              "controls_inventory_sha256": hashlib.sha256(inventory_bytes).hexdigest(),
              "reference_rows_accessed": False, "synthetic_only": True,
              "model_calls": 0, "source_calls": 0, "graph_changes": False,
              "original_control_count": len(inventory["cases"]),
              "supplemental_controls": [case for case, _ in inputs if case.get("supplemental")],
              "cases": [], "all_checks_passed": False,
              "scope": "Official-reader synthetic behavior and framing/literal checks, not scientific accuracy or complete PSI-MI conformance."}
    write_json(output / "preparation.json", report)
    classpath = os.pathsep.join([str(Path(classes).resolve()),
                                *(item["path"] for item in bindings["dependency_jars"])])
    try:
        for case, raw in inputs:
            if runtime_bindings(classes, classpath_file, java) != bindings:
                raise ValueError("Reader/runtime/dependency bindings changed after controls freeze.")
            command = [bindings["java"]["executable"], "-cp", classpath,
                       "org.biograph.IntactReader", str(frozen / case["input_tsv"])]
            timeout_error = None
            try:
                observed = subprocess.run(command, capture_output=True, timeout=60, check=False)
            except subprocess.TimeoutExpired as error:
                timeout_error = error
                observed = SimpleNamespace(returncode=None, stdout=error.stdout or b"",
                                           stderr=error.stderr or b"")
            stdout = results / (case["id"] + ".jsonl")
            stderr = results / (case["id"] + ".stderr.txt")
            stdout.write_bytes(observed.stdout); stderr.write_bytes(observed.stderr)
            entry = {"id": case["id"], "fixture_sha256": case["sha256"],
                     "returncode": observed.returncode, "stdout_sha256": sha(stdout),
                     "stderr_sha256": sha(stderr), "source_rows": [], "checks": []}
            report["cases"].append(entry)
            entry["checks"].append({"name": "java_exit_success", "passed": observed.returncode == 0,
                                    "expected": 0, "observed": observed.returncode})
            if timeout_error is not None:
                entry["timeout_seconds"] = 60
                raise ValueError("Official-reader control timed out; partial streams preserved: " + case["id"])
            try:
                rows = [json.loads(line) for line in observed.stdout.decode("utf-8").splitlines()]
                entry["source_rows"] = rows
                entry["checks"].extend(check_supplemental(case, rows, raw) if case.get("supplemental")
                                       else check_case(case, rows, raw))
                entry["application_gates"] = [assess_reader_row(row) for row in rows]
            except (ValueError, KeyError, TypeError, UnicodeError) as error:
                entry["checks"].append({"name": "readable_complete_observations", "passed": False,
                                        "error": str(error)})
        if runtime_bindings(classes, classpath_file, java) != bindings or sha(__file__) != report["runner_sha256"]:
            raise ValueError("Executable bindings changed during validation.")
        checks = [check for case in report["cases"] for check in case["checks"]]
        report["all_checks_passed"] = bool(checks) and all(check["passed"] for check in checks)
        report["status"] = "passed" if report["all_checks_passed"] else "failed"
        report["check_counts"] = {"total": len(checks), "passed": sum(check["passed"] for check in checks),
                                  "failed": sum(not check["passed"] for check in checks)}
    except (ValueError, OSError, subprocess.SubprocessError) as error:
        report["status"] = "failed"
        report["error"] = str(error)
    report["content_sha256"] = digest(report)
    write_json(output / "report.json", report)
    return report


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--classpath-file", type=Path, required=True)
    parser.add_argument("--classes", type=Path, default=ROOT / "tools/intact_reader/target/classes")
    parser.add_argument("--java", default="java")
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args(argv)
    try:
        report = run_controls(args.classes, args.classpath_file, args.output, args.java)
    except (ValueError, OSError, subprocess.SubprocessError) as error:
        parser.exit(2, str(error) + "\n")
    print(json.dumps({"status": report["status"], "report": str(args.output / "report.json"),
                      "check_counts": report.get("check_counts"), "error": report.get("error")}))
    return 0 if report["all_checks_passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
