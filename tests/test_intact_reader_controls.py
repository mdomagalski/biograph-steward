"""Orchestration/gate controls; these mocks are not JAMI execution results."""
from copy import deepcopy
import json
from pathlib import Path
from types import SimpleNamespace
import tempfile
import unittest
from unittest.mock import patch

from scripts.validate_intact_reader_controls import (
    assess_reader_row, observed_aliases, run_controls, runtime_bindings,
    supplemental_controls, CONTROLS,
)


def row(negative="false", diagnostics=None):
    cells = ["-"] * 42
    cells[35] = negative
    return {"raw_cells": cells, "parsed_count": 1,
            "diagnostics": diagnostics or [], "source_fields": {},
            "interaction": {"negative": False}}


class ReaderGateTests(unittest.TestCase):
    def test_negative_default_does_not_supply_binary_origin(self):
        default = assess_reader_row(row("-"))
        self.assertFalse(default["quarantined"])
        self.assertIs(default["negative_value"], False)
        self.assertEqual(default["negative_origin"], "mitab27_default_false")
        self.assertFalse(default["expansion_annotation_supplied"])
        self.assertEqual(default["binary_origin"], "unknown")
        explicit = assess_reader_row(row("false"))
        self.assertEqual(explicit["negative_origin"], "explicit")

    def test_reader_false_cannot_repair_invalid_negative_text(self):
        value = assess_reader_row(row("maybe"))
        self.assertTrue(value["quarantined"])
        self.assertIn("negative_literal_invalid", value["quarantine_reasons"])
        self.assertIsNone(value["negative_value"])

    def test_supported_reader_version_does_not_override_42_column_gate(self):
        value = row()
        value["raw_cells"] = value["raw_cells"][:15]
        self.assertIn("column_count_not_42", assess_reader_row(value)["quarantine_reasons"])

    def test_invalid_diagnostics_in_both_phases_quarantine_recovered_values(self):
        value = row(diagnostics=[{"callback": "onInvalidStoichiometry", "phase": "row_model"}])
        self.assertIn("reader_invalid_stoichiometry", assess_reader_row(value)["quarantine_reasons"])
        value = row()
        value["source_fields"] = {"detection_methods": {
            "status": "parsed_with_diagnostics", "diagnostics": [{"callback": "onInvalidSyntax"}]}}
        self.assertIn("reader_invalid_syntax", assess_reader_row(value)["quarantine_reasons"])
        future = row(diagnostics=[{"callback": "onInvalidFutureReaderValue"}])
        self.assertIn("reader_invalid_diagnostic", assess_reader_row(future)["quarantine_reasons"])

    def test_model_loss_warning_is_retained_without_discarding_full_source_lists(self):
        value = row(diagnostics=[{"callback": "onSeveralCvTermsFound", "phase": "row_model"}])
        value["source_fields"] = {"experimental_roles_a": {
            "status": "parsed", "values": [{"mi_id": "MI:0496"}, {"mi_id": "MI:0498"}], "diagnostics": []}}
        self.assertFalse(assess_reader_row(value)["quarantined"])

    def test_projection_uses_source_side_instead_of_collection_order(self):
        value = row()
        value["interaction"]["participants"] = [
            {"side": "B", "taxid": 10090, "experimental_role": {"mi_id": "MI:0498"},
             "stoichiometry": {"min": 0, "max": 0}},
            {"side": "A", "taxid": 9606, "experimental_role": {"mi_id": "MI:0496"},
             "stoichiometry": None},
        ]
        original = deepcopy(value)
        observed = observed_aliases(value)
        self.assertEqual(observed["participant_taxids"], [9606, 10090])
        self.assertEqual(observed["experimental_role_ids"], ["MI:0496", "MI:0498"])
        self.assertEqual(observed["participant_stoichiometry"], [None, [0, 0]])
        self.assertEqual(value, original)


class RuntimeAndFailureTests(unittest.TestCase):
    def test_dependency_bytes_are_bound_beyond_classpath_text(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            classes = root / "classes"
            classes.mkdir()
            (classes / "IntactReader.class").write_bytes(b"synthetic compiled bytes")
            jar = root / "reader.jar"
            jar.write_bytes(b"synthetic JAR v1")
            classpath = root / "classpath.txt"
            classpath.write_text(str(jar))
            version = SimpleNamespace(returncode=0, stdout="", stderr="synthetic Java version")
            with patch("scripts.validate_intact_reader_controls.shutil.which", return_value="/usr/bin/java"), \
                 patch("scripts.validate_intact_reader_controls.subprocess.run", return_value=version):
                first = runtime_bindings(classes, classpath)
                jar.write_bytes(b"synthetic JAR v2")
                second = runtime_bindings(classes, classpath)
            self.assertEqual(first["classpath_file_sha256"], second["classpath_file_sha256"])
            self.assertNotEqual(first["dependency_jars"], second["dependency_jars"])

    def test_supplemental_rows_are_independently_synthetic_and_frozen(self):
        inventory = json.loads(CONTROLS.read_text())
        extra = supplemental_controls(inventory)
        self.assertEqual(len(extra), 2)
        self.assertEqual([case["source_line_count"] for case, _ in extra], [3, 1])
        for case, raw in extra:
            self.assertTrue(case["synthetic"])
            self.assertEqual([len(line.split(b"\t")) for line in raw.splitlines()], case["raw_column_counts"])

    def test_failed_execution_is_saved_and_cannot_overwrite_an_outcome(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            classpath = root / "classpath.txt"
            classpath.write_text("synthetic classpath")
            output = root / "result"
            bindings = {"dependency_jars": [], "java": {"executable": "/synthetic/java"}}
            failure = SimpleNamespace(returncode=7, stdout=b"", stderr=b"synthetic JVM failure")
            with patch("scripts.validate_intact_reader_controls.runtime_bindings", return_value=bindings), \
                 patch("scripts.validate_intact_reader_controls.subprocess.run", return_value=failure):
                report = run_controls(root / "classes", classpath, output)
            self.assertEqual(report["status"], "failed")
            self.assertFalse(report["all_checks_passed"])
            self.assertEqual(len(report["cases"]), 32)
            self.assertEqual((output / "cases/baseline_explicit_false.stderr.txt").read_bytes(), failure.stderr)
            self.assertTrue((output / "report.json").is_file())
            with self.assertRaises(ValueError):
                run_controls(root / "classes", classpath, output)


if __name__ == "__main__":
    unittest.main()
