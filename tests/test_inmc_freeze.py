"""Invented proof artifacts exercise the immutable protocol-freeze boundary."""
import importlib.util
import json
from pathlib import Path
import tempfile
import unittest

from biograph_steward.client import digest
from biograph_steward.file_utils import sha
from test_inmc_comparison import fixture, seal, write

SPEC = importlib.util.spec_from_file_location(
    "freeze_inmc_comparison", Path(__file__).resolve().parents[1] / "scripts/freeze_inmc_comparison.py")
freeze = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(freeze)


class FreezeTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.graph, self.hierarchy, self.resource = [self.root / name for name in ("graph", "hierarchy", "resource")]
        self.output = self.root / "frozen"
        fixture(self.graph)
        (self.graph / "assay_contract.json").write_bytes(freeze.ASSAY.read_bytes())
        seal(self.graph)
        self.execution = {"device": "cpu", "python": "3.12.invented",
                          "packages": {"pykeen": "1.11.1", "torch": "2.6.0", "numpy": "invented",
                                       "scipy": "invented", "scikit-learn": "invented"}, "cuda_runtime": None}
        write(self.hierarchy / "report.json", {
            "format": "biograph-steward.pykeen-hierarchy-smoke.v1", "status": "passed",
            "purpose": "engineering_only", "biomedical_inputs_used": False,
            "biological_quality_measured": False, "synthetic_test_fixture": True})
        write(self.hierarchy / "manifest.json", {
            "input": "invented constants in this script only", "script_sha256": sha(freeze.HIERARCHY_SCRIPT),
            "packages": {key: self.execution["packages"][key] for key in ("pykeen", "torch", "numpy")}})
        packet = freeze.runner.validate_packet(self.graph, resource_smoke=True)
        self.bindings = {"runner_sha256": sha(Path(freeze.runner.__file__)),
                         "graph_input_files": {key: packet["files"][key] for key in freeze.runner.REQUIRED if key != "protocol.json"},
                         "graph_report_sha256": packet["report_sha256"], "protocol_sha256": packet["files"]["protocol.json"]}
        write(self.resource / "manifest.json", {
            **self.bindings, **self.execution, "resource_smoke": True,
            "candidate_outcomes_loaded": False, "candidate_pairs_scored": False,
            "model": freeze.runner.MODEL, "training": freeze.runner.TRAINING})
        (self.resource / "invented_checkpoint.bin").write_bytes(b"Invented engineering artifact; no weights or assays.")
        self.resource_report = {"format": freeze.runner.FORMAT, "status": "passed", **self.bindings,
                                "resource_smoke": True, "candidate_outcomes_loaded": False,
                                "candidate_pairs_scored": 0, "execution": self.execution,
                                "synthetic_test_fixture": True}
        self.reseal_resource()

    def reseal_resource(self):
        value = {key: item for key, item in self.resource_report.items() if key != "content_sha256"}
        value["files"] = {path.name: sha(path) for path in self.resource.iterdir() if path.is_file() and path.name != "report.json"}
        value["content_sha256"] = digest(value)
        write(self.resource / "report.json", value)
        self.resource_report = value

    def run_freeze(self):
        return freeze.freeze_comparison(self.graph, self.hierarchy / "report.json",
                                        self.resource / "report.json", self.output)

    def test_new_packet_preserves_original_graph_and_binds_full_validation(self):
        original = {path.relative_to(self.graph).as_posix(): path.read_bytes()
                    for path in self.graph.rglob("*") if path.is_file()}
        report = self.run_freeze()
        checked = freeze.runner.validate_packet(self.output)
        self.assertEqual(report["status"], "comparison_frozen")
        self.assertEqual(checked["protocol"]["execution"], self.execution)
        self.assertEqual(checked["protocol"]["scoring_implementation"]["sha256"], sha(freeze.SCORER))
        self.assertEqual(checked["protocol"]["assay_contract_sha256"], sha(freeze.ASSAY))
        self.assertEqual(report["parent_graph_report_sha256"], sha(self.graph / "report.json"))
        for name, raw in original.items():
            self.assertEqual((self.graph / name).read_bytes(), raw)
            if name not in {"protocol.json", "report.json"}:
                self.assertEqual((self.output / name).read_bytes(), raw)
        self.assertEqual((self.output / "validation/resource_runtime.json").read_bytes(),
                         (self.resource / "manifest.json").read_bytes())
        self.assertFalse(report["outcome_values_loaded"])
        self.assertFalse(report["scientific_predictions_generated"])
        self.assertFalse(json.loads((self.graph / "protocol.json").read_text())["fully_frozen"])

    def test_existing_output_is_not_overwritten(self):
        self.run_freeze()
        before = sha(self.output / "report.json")
        with self.assertRaises(ValueError):
            self.run_freeze()
        self.assertEqual(sha(self.output / "report.json"), before)

    def test_resource_file_tampering_is_rejected_even_if_not_runtime_manifest(self):
        (self.resource / "invented_checkpoint.bin").write_bytes(b"changed")
        with self.assertRaisesRegex(ValueError, "fingerprint"):
            self.run_freeze()
        self.assertFalse(self.output.exists())

    def test_changed_report_seal_is_rejected(self):
        self.resource_report["status"] = "passed-but-mutated"
        write(self.resource / "report.json", self.resource_report)
        with self.assertRaises(ValueError):
            self.run_freeze()
        self.assertFalse(self.output.exists())

    def test_graph_or_runner_binding_mismatch_rejected_after_reseal(self):
        for key, changed in [("runner_sha256", "a" * 64), ("graph_input_files", {}),
                             ("protocol_sha256", "a" * 64), ("graph_report_sha256", "a" * 64)]:
            original = self.resource_report[key]
            self.resource_report[key] = changed
            self.reseal_resource()
            with self.subTest(key=key), self.assertRaisesRegex(ValueError, "does not bind"):
                self.run_freeze()
            self.resource_report[key] = original
            self.reseal_resource()
        self.assertFalse(self.output.exists())

    def test_runtime_device_mismatch_and_prior_candidate_scoring_rejected(self):
        self.resource_report["execution"] = {**self.execution, "device": "cuda:0"}
        self.reseal_resource()
        with self.assertRaisesRegex(ValueError, "runtime manifest"):
            self.run_freeze()
        self.resource_report["execution"] = self.execution
        self.resource_report["candidate_pairs_scored"] = 1
        self.reseal_resource()
        with self.assertRaisesRegex(ValueError, "reserved candidate"):
            self.run_freeze()
        self.assertFalse(self.output.exists())

    def test_wrong_hierarchy_script_or_biomedical_smoke_cannot_certify_freeze(self):
        manifest_path = self.hierarchy / "manifest.json"
        manifest = json.loads(manifest_path.read_text())
        manifest["script_sha256"] = "a" * 64
        write(manifest_path, manifest)
        with self.assertRaisesRegex(ValueError, "engineering-only"):
            self.run_freeze()
        manifest["script_sha256"] = sha(freeze.HIERARCHY_SCRIPT)
        write(manifest_path, manifest)
        report_path = self.hierarchy / "report.json"
        report = json.loads(report_path.read_text()); report["biomedical_inputs_used"] = True
        write(report_path, report)
        with self.assertRaisesRegex(ValueError, "engineering-only"):
            self.run_freeze()
        self.assertFalse(self.output.exists())

    def test_missing_or_changed_assay_contract_is_rejected_before_output(self):
        (self.graph / "assay_contract.json").write_text("{}\n")
        seal(self.graph)
        with self.assertRaisesRegex(ValueError, "prespecified assay contract"):
            self.run_freeze()
        self.assertFalse(self.output.exists())

    def test_unsafe_resource_inventory_and_symlink_proof_rejected(self):
        outside = self.root / "outside"
        outside.write_bytes((self.resource / "invented_checkpoint.bin").read_bytes())
        (self.resource / "invented_checkpoint.bin").unlink()
        (self.resource / "invented_checkpoint.bin").symlink_to(outside)
        with self.assertRaisesRegex(ValueError, "symlinks"):
            self.run_freeze()
        self.assertFalse(self.output.exists())


if __name__ == "__main__":
    unittest.main()
