"""Freeze boundaries and interrupted comparison preservation without inference."""
import importlib.util
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from biograph_steward.construction_planning import ConstructionPlanner, fixed_construction_cases

SPEC = importlib.util.spec_from_file_location(
    "evaluate_construction_planner", Path(__file__).resolve().parents[1] / "scripts/evaluate_construction_planner.py")
evaluation = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(evaluation)


def response(plan):
    return {"status": "completed", "model": "test-model", "usage": {"input_tokens": 40, "output_tokens": 15},
            "output": [{"type": "message", "content": [{"type": "output_text", "text": json.dumps(plan)}]}]}


def expected_plan(case):
    if case["expected_request"] is None:
        return {"reason": "Unsupported capability.", "action": "abstain", "tool": None,
                "profile": None, "accessions": [], "focus_uniprot": None, "relations": []}
    return {"reason": "Candidate evidence inspection.", "action": "construct", "tool": "construct_cohort",
            **case["expected_request"]}


class ConstructionPlannerEvaluationTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.output = Path(self.temp.name) / "frozen"
        self.calls = []
        self.cases = fixed_construction_cases()
        def transport(payload):
            self.calls.append(payload)
            return response(expected_plan(self.cases[len(self.calls) - 1]))
        self.planner = ConstructionPlanner(model="test-model", endpoint="http://localhost:9999/v1/responses", transport=transport)

    def prepare(self):
        return evaluation.prepare(self.output, planner=self.planner)

    def test_prepare_records_sanitized_configuration_and_never_calls_model(self):
        self.planner.key = "secret-fixture-value"
        manifest = self.prepare()
        self.assertEqual(self.calls, [])
        self.assertEqual(manifest["case_count"], 12)
        self.assertNotIn("secret-fixture-value", (self.output / "manifest.json").read_text())
        self.assertIn("biograph_steward/construction.py", manifest["implementation_sha256"])
        self.assertIn("biograph_steward/model_transport.py", manifest["implementation_sha256"])
        self.assertIn("Not attested", manifest["expected_runtime"]["verification_status"])
        evaluation.validate_freeze(self.output, planner=self.planner)
        with self.assertRaises(ValueError):
            self.prepare()

    def test_case_tampering_rejected_before_any_model_calls(self):
        self.prepare()
        cases = json.loads((self.output / "cases.json").read_text())
        cases[0]["scope"]["question"] = "Changed request"
        (self.output / "cases.json").write_text(json.dumps(cases))
        with self.assertRaises(ValueError):
            evaluation.run(self.output, planner=self.planner)
        self.assertEqual(self.calls, [])
        self.assertFalse((self.output / "results").exists())

    def test_implementation_drift_rejected_before_any_model_calls(self):
        self.prepare()
        changed = evaluation.implementation_hashes()
        changed["biograph_steward/construction.py"] = "0" * 64
        with patch.object(evaluation, "implementation_hashes", return_value=changed), self.assertRaises(ValueError):
            evaluation.run(self.output, planner=self.planner)
        self.assertEqual(self.calls, [])
        self.assertFalse((self.output / "results").exists())

    def test_model_configuration_drift_rejected_before_any_model_calls(self):
        self.prepare()
        self.planner.model = "different-model"
        with self.assertRaises(ValueError):
            evaluation.run(self.output, planner=self.planner)
        self.assertEqual(self.calls, [])
        self.assertFalse((self.output / "results").exists())

    def test_full_run_preserves_all_traces_usage_and_no_science_claim(self):
        self.prepare()
        result = evaluation.run(self.output, planner=self.planner)
        self.assertEqual(len(self.calls), 12)
        self.assertEqual(result["status"], "completed")
        self.assertEqual(result["summary"]["scope_matches"], 12)
        self.assertEqual(result["summary"]["returned_token_totals"], {"input_tokens": 480, "output_tokens": 180})
        self.assertIsNone(result["summary"]["cost"])
        self.assertFalse(result["summary"]["biological_accuracy_measured"])
        self.assertEqual(len(list((self.output / "results/traces").glob("*.json"))), 12)
        self.assertTrue((self.output / "results/report.html").is_file())
        self.assertNotIn("expected_request", json.dumps(self.calls))
        with self.assertRaises(ValueError):
            evaluation.run(self.output, planner=self.planner)
        self.assertEqual(len(self.calls), 12)

    def test_interruption_keeps_completed_traces_and_marks_pending_case(self):
        self.prepare()
        original = self.planner.plan
        count = 0
        def interrupted(scope):
            nonlocal count
            count += 1
            if count == 3:
                raise KeyboardInterrupt()
            return original(scope)
        with patch.object(self.planner, "plan", side_effect=interrupted), self.assertRaises(KeyboardInterrupt):
            evaluation.run(self.output, planner=self.planner)
        result = json.loads((self.output / "results/comparison.json").read_text())
        self.assertEqual(result["status"], "interrupted")
        self.assertEqual(result["summary"]["completed_cases"], 2)
        self.assertEqual(result["pending_case"], self.cases[2]["id"])
        self.assertEqual(len(list((self.output / "results/traces").glob("*.json"))), 2)
        self.assertIn("in-flight call", (self.output / "results/report.html").read_text())
        with self.assertRaises(ValueError):
            evaluation.run(self.output, planner=self.planner)

    def test_manifest_symlink_rejected_before_model_call(self):
        self.prepare()
        manifest = self.output / "manifest.json"
        saved = self.output / "saved.json"
        manifest.rename(saved)
        manifest.symlink_to(saved)
        with self.assertRaises(ValueError):
            evaluation.run(self.output, planner=self.planner)
        self.assertEqual(self.calls, [])


if __name__ == "__main__":
    unittest.main()
