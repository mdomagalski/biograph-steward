"""Offline overlap CLI dispatch preserves report results and visible failures."""
from contextlib import redirect_stderr, redirect_stdout
from io import StringIO
import json
from pathlib import Path
import sys
import tempfile
import types
import unittest
from unittest.mock import Mock, patch

from biograph_steward.__main__ import main


class EvidenceOverlapCliTests(unittest.TestCase):
    def command(self, *args):
        output, error = StringIO(), StringIO()
        with redirect_stdout(output), redirect_stderr(error):
            code = main([str(arg) for arg in args])
        return code, output.getvalue(), error.getvalue()

    def overlap_api(self, **kwargs):
        module = types.ModuleType("biograph_steward.evidence_overlap")
        module.publish_overlap = Mock(**kwargs)
        module.verify_overlap = Mock(**kwargs)
        return module

    def test_publish_dispatches_saved_paths_and_prints_report_summary(self):
        source, destination = Path("saved-source"), Path("saved-overlap")
        recorded = {"records": 3, "independent_evidence_count": None}
        api = self.overlap_api(return_value={"summary": recorded})
        with patch.dict(sys.modules, {api.__name__: api}), patch(
                "biograph_steward.__main__.PharosClient", side_effect=AssertionError("No network client")):
            code, output, error = self.command("evidence-overlap", "--run", source, "--out", destination)
        self.assertEqual(code, 0, error)
        api.publish_overlap.assert_called_once_with(source, destination)
        api.verify_overlap.assert_not_called()
        printed = json.loads(output)
        self.assertEqual(printed["operation"], "evidence-overlap")
        self.assertEqual(printed["summary"], recorded)
        self.assertEqual(printed["report"], str((destination / "report.json").resolve()))

    def test_verify_dispatches_report_directory_and_prints_verified_summary(self):
        destination = Path("saved-overlap")
        recorded = {"records": 3, "lineage_unknown": 3}
        api = self.overlap_api(return_value={"summary": recorded})
        with patch.dict(sys.modules, {api.__name__: api}), patch(
                "biograph_steward.__main__.PharosClient", side_effect=AssertionError("No network client")):
            code, output, error = self.command("evidence-overlap-verify", "--report", destination)
        self.assertEqual(code, 0, error)
        api.publish_overlap.assert_not_called()
        api.verify_overlap.assert_called_once_with(destination)
        printed = json.loads(output)
        self.assertEqual(printed["operation"], "evidence-overlap-verify")
        self.assertEqual(printed["status"], "evidence_overlap_verified")
        self.assertEqual(printed["summary"], recorded)
        self.assertEqual(printed["report"], str((destination / "report.json").resolve()))

    def test_verification_error_is_visible_without_success_summary(self):
        api = self.overlap_api(side_effect=ValueError("Source binding changed."))
        with patch.dict(sys.modules, {api.__name__: api}):
            code, output, error = self.command("evidence-overlap-verify", "--report", "saved-overlap")
        self.assertEqual(code, 1)
        self.assertEqual(output, "")
        self.assertIn("Source binding changed.", error)

    def test_real_saved_synthetic_attachment_roundtrip_and_tamper_detection(self):
        from biograph_steward.assay_attachment import attach_assay
        from biograph_steward.graph import save_run
        from test_assay_attachment import cohort_snapshot, make_publication

        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp).resolve()
            source, publication, attached, report = [root / name for name in
                ("cohort", "publication", "attached", "overlap")]
            save_run(cohort_snapshot(), source)
            make_publication(publication)
            graph = attach_assay(source, publication, attached)
            original = {p.relative_to(attached).as_posix(): p.read_bytes()
                        for p in attached.rglob("*") if p.is_file()}
            with patch("biograph_steward.__main__.PharosClient", side_effect=AssertionError("No network client")):
                code, output, error = self.command("evidence-overlap", "--run", attached, "--out", report)
                self.assertEqual(code, 0, error)
                published = json.loads(output)
                recorded = json.loads((report / "report.json").read_text())
                self.assertEqual(published["summary"], recorded["summary"])
                self.assertEqual(published["summary"]["workspace_observations"], len(graph["assay_observations"]))
                self.assertEqual(published["summary"]["excluded_observations_retained"], 1)
                self.assertTrue((report / "mappings.sssom.tsv").is_file())
                code, output, error = self.command("evidence-overlap-verify", "--report", report)
                self.assertEqual(code, 0, error)
                self.assertEqual(json.loads(output)["summary"], published["summary"])
                self.assertEqual(json.loads(output)["status"], "evidence_overlap_verified")
                self.assertEqual(original, {p.relative_to(attached).as_posix(): p.read_bytes()
                    for p in attached.rglob("*") if p.is_file()})
                (report / "records.jsonl").write_text("tampered report ledger\n")
                code, output, error = self.command("evidence-overlap-verify", "--report", report)
                self.assertEqual(code, 1)
                self.assertEqual(output, "")
                self.assertIn("changed", error)


if __name__ == "__main__":
    unittest.main()
