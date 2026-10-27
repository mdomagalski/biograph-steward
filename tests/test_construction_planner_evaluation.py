"""Freeze boundaries and interrupted comparison preservation without inference."""
import importlib.util
import io
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


class NemotronToolEvaluationTests(unittest.TestCase):
    def setUp(self):
        from biograph_steward.nemotron_construction import NemotronConstructionPlanner
        from scripts import probe_nemotron_tool_interface as probe
        self.probe = probe
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.output = Path(self.temp.name) / "tool-comparison"
        self.cases, self.calls = fixed_construction_cases(), []
        environment = {"BIOGRAPH_PLANNER_MODEL": probe.MODEL,
            "BIOGRAPH_PLANNER_ENDPOINT": "http://127.0.0.1:8010/v1/chat/completions",
            "BIOGRAPH_PLANNER_API": "nim_chat", "BIOGRAPH_PLANNER_PROMPT_PROFILE": "nemotron_nano_v1",
            "BIOGRAPH_PLANNER_MAX_OUTPUT_TOKENS": "1600", "BIOGRAPH_PLANNER_TIMEOUT": "120",
            "BIOGRAPH_PLANNER_API_KEY": ""}
        self.environment = patch.dict("os.environ", environment, clear=True)
        self.environment.start()
        self.addCleanup(self.environment.stop)
        self.planner = NemotronConstructionPlanner()
        test = self
        class Opener:
            def open(self, request, timeout):
                index = len(test.calls)
                test.calls.append(json.loads(request.data))
                case = test.cases[index]
                content = ("<TOOLCALL>" + json.dumps([{"name":"construct_cohort",
                            "arguments":case["expected_request"]}]) + "</TOOLCALL>"
                           if case["expected_request"] else "No call. This text has not been semantically evaluated.")
                raw = {"model": probe.MODEL, "usage": {"prompt_tokens":20,"completion_tokens":10},
                       "choices":[{"finish_reason":"stop", "message":{"role":"assistant","content":content}}]}
                return io.BytesIO(json.dumps(raw).encode())
        self.network = patch.object(probe, "build_opener", return_value=Opener())
        self.network.start()
        self.addCleanup(self.network.stop)

    def prepare(self):
        return evaluation.prepare(self.output, planner=self.planner)

    def test_full_run_separates_supported_agreement_from_plain_text_no_call(self):
        manifest = self.prepare()
        self.assertEqual(manifest["interface"], "nemotron_tool_v1")
        self.assertEqual(manifest["format"], evaluation.TOOL_FORMAT)
        self.assertEqual(len(manifest["request_files"]), 12)
        self.assertEqual(self.calls, [])
        result = evaluation.run(self.output, planner=self.planner)
        summary = result["summary"]
        self.assertEqual(summary["supported_exact_matches"], 4)
        self.assertEqual(summary["scope_matches"], 4)
        self.assertEqual(summary["unsupported_no_call_text"], 8)
        self.assertEqual(summary["unsupported_explicit_abstentions"], 0)
        self.assertEqual(summary["unsupported_requests_constructed"], 0)
        self.assertEqual(len(self.calls), 12)
        self.assertNotIn("expected_request", json.dumps(self.calls))
        self.assertNotIn("expected_action", json.dumps(self.calls))
        self.assertIn("absence of a call alone is not semantic task success", (self.output/'results/report.html').read_text())
        for i, case in enumerate(self.cases, 1):
            self.assertEqual(self.calls[i-1], json.loads((self.output/f'requests/{i:02d}_{case["id"]}.json').read_text()))
        with self.assertRaises(ValueError):
            evaluation.run(self.output, planner=self.planner)

    def test_wire_tampering_fails_before_calls(self):
        self.prepare()
        (self.output/'requests/01_ppi_full.json').write_text('{}')
        with self.assertRaises(ValueError):
            evaluation.run(self.output, planner=self.planner)
        self.assertEqual(self.calls, [])
        self.assertFalse((self.output/'results').exists())

    def test_implementation_copy_tampering_fails_before_calls(self):
        self.prepare()
        (self.output/'implementation/biograph_steward/nemotron_construction.py').write_text('# changed')
        with self.assertRaises(ValueError):
            evaluation.run(self.output, planner=self.planner)
        self.assertEqual(self.calls, [])

    def test_truncated_output_is_not_scored_as_correct_withholding(self):
        self.prepare()
        raw = {"model":self.probe.MODEL, "choices":[{"finish_reason":"length",
               "message":{"role":"assistant","content":"No call"}}]}
        class Opener:
            def open(self, request, timeout):
                return io.BytesIO(json.dumps(raw).encode())
        with patch.object(self.probe, "build_opener", return_value=Opener()):
            result = evaluation.run(self.output, planner=self.planner)
        self.assertEqual(result["summary"]["invalid_plans"],12)
        self.assertEqual(result["summary"]["unsupported_no_call_text"],0)
        self.assertEqual(result["summary"]["scope_matches"],0)

    def test_other_case_trace_is_not_accepted_under_current_case(self):
        self.prepare()
        original = self.planner.plan
        def other_scope(scope):
            changed = {**scope, "question":"Another request with the same protein cohort."}
            return original(changed)
        with patch.object(self.planner, "plan", side_effect=other_scope), self.assertRaisesRegex(ValueError, "Trace scope"):
            evaluation.run(self.output, planner=self.planner)
        result = json.loads((self.output/'results/comparison.json').read_text())
        self.assertEqual(result['status'], 'interrupted')
        self.assertEqual(result['summary']['completed_cases'], 0)
        self.assertEqual(result['pending_case'], 'ppi_full')

    def test_changed_trace_configuration_is_not_accepted(self):
        self.prepare()
        original = self.planner.plan
        def changed_endpoint(scope):
            trace = original(scope)
            trace['endpoint'] = 'http://127.0.0.1:9999/v1/chat/completions'
            return evaluation._seal(trace)
        with patch.object(self.planner, "plan", side_effect=changed_endpoint), self.assertRaisesRegex(ValueError, "Trace configuration"):
            evaluation.run(self.output, planner=self.planner)
        result = json.loads((self.output/'results/comparison.json').read_text())
        self.assertEqual(result['summary']['completed_cases'], 0)


class NemotronToolV2EvaluationTests(unittest.TestCase):
    def setUp(self):
        # Reuse the mocked transport, never a live endpoint or runtime fixture.
        NemotronToolEvaluationTests.setUp(self)
        from biograph_steward.nemotron_construction_v2 import NemotronConstructionPlannerV2
        self.planner = NemotronConstructionPlannerV2()
        self.runtime_dir = Path(self.temp.name) / "runtime"
        self.runtime_dir.mkdir()
        self.runtime_path = self.runtime_dir / "observation.json"

    def prepare(self):
        return evaluation.prepare(self.output, planner=self.planner)

    def runtime(self, **overrides):
        evidence = self.runtime_dir / "startup.log"
        evidence.write_text("Mocked runtime evidence for offline runner tests only.\n")
        receipt = {**evaluation.runtime_prerequisite(evaluation.model_configuration(self.planner)),
                   "observed_at": evaluation.utcnow(), "image_id": "sha256:" + "a" * 64,
                   "container_id": "b" * 64, "evidence_files": {"startup.log": evaluation.sha(evidence)},
                   **overrides}
        self.runtime_path.write_text(json.dumps(receipt))
        return self.runtime_path

    def test_prepare_preserves_fixed_scopes_without_reference_derived_selection(self):
        manifest = self.prepare()
        self.assertEqual(manifest["interface"], "nemotron_tool_v2")
        self.assertEqual(manifest["format"], evaluation.TOOL_V2_FORMAT)
        for name in ("biograph_steward/nemotron_construction_v2.py", "biograph_steward/graph.py",
                     "biograph_steward/retrieval.py", "biograph_steward/__init__.py"):
            self.assertIn(name, manifest["implementation_sha256"])
        self.assertEqual(self.calls, [])
        cases = json.loads((self.output / "cases.json").read_text())
        self.assertEqual(cases, fixed_construction_cases())
        for i, case in enumerate(cases, 1):
            wire = json.loads((self.output / f"requests/{i:02d}_{case['id']}.json").read_text())
            request_scope = json.loads(wire["messages"][1]["content"].split("Untrusted request data:\n", 1)[1])
            self.assertEqual(request_scope, case["scope"])
            self.assertNotIn("exact_selection", request_scope)
            self.assertNotIn("expected_request", json.dumps(wire))
            self.assertNotIn("expected_action", json.dumps(wire))
            self.assertEqual(wire["response_format"]["type"], "structural_tag")

    def test_missing_runtime_fails_before_calls_or_result_creation(self):
        self.prepare()
        with self.assertRaisesRegex(ValueError, "requires --runtime-observation"):
            evaluation.run(self.output, planner=self.planner)
        self.assertEqual(self.calls, [])
        self.assertFalse((self.output / "results").exists())

    def test_incompatible_stale_or_fixture_runtime_is_not_accepted(self):
        self.prepare()
        for change in ({"engine": "V0"}, {"observed_at": "2020-01-01T00:00:00+00:00"},
                       {"observed_at": "2999-01-01T00:00:00+00:00"},
                       {"observation_kind": "synthetic_fixture"},
                       {"request_endpoint": "http://127.0.0.1:9999/v1/chat/completions"},
                       {"effective_flags": {"enable_prefix_caching": True}},
                       {"image_id": None}, {"container_id": None}):
            with self.subTest(change=change), self.assertRaises(ValueError):
                evaluation.run(self.output, planner=self.planner, runtime_observation=self.runtime(**change))
            self.assertEqual(self.calls, [])
            self.assertFalse((self.output / "results").exists())

    def test_runtime_evidence_tampering_fails_before_calls(self):
        self.prepare()
        self.runtime()
        (self.runtime_dir / "startup.log").write_text("Changed evidence")
        with self.assertRaisesRegex(ValueError, "evidence file or hash"):
            evaluation.run(self.output, planner=self.planner, runtime_observation=self.runtime_path)
        self.assertEqual(self.calls, [])
        self.assertFalse((self.output / "results").exists())

    def test_resealing_an_older_runtime_receipt_cannot_make_it_current(self):
        self.prepare()
        self.runtime(observed_at="2020-01-01T00:00:00+00:00")
        stale = evaluation._seal(json.loads(self.runtime_path.read_text()))
        self.runtime_path.write_text(json.dumps(stale))
        with self.assertRaisesRegex(ValueError, "recorded after this comparison was frozen"):
            evaluation.run(self.output, planner=self.planner, runtime_observation=self.runtime_path)
        self.assertEqual(self.calls, [])
        self.assertFalse((self.output / "results").exists())

    def test_full_run_binds_runtime_and_keeps_no_call_semantics_separate(self):
        self.prepare()
        result = evaluation.run(self.output, planner=self.planner, runtime_observation=self.runtime())
        self.assertEqual(result["status"], "completed")
        self.assertEqual(result["summary"]["supported_exact_matches"], 4)
        self.assertEqual(result["summary"]["scope_matches"], 4)
        self.assertEqual(result["summary"]["unsupported_no_call_text"], 8)
        self.assertEqual(result["summary"]["unsupported_explicit_abstentions"], 0)
        self.assertEqual(result["runtime_observation_sha256"], evaluation.sha(self.runtime_path))
        self.assertEqual(result["files"]["runtime_observation.json"], evaluation.sha(self.runtime_path))
        self.assertIn("runtime_evidence/startup.log", result["files"])
        self.assertIn("cannot attest live engine state", (self.output / "results/report.html").read_text())
        self.assertEqual(len(self.calls), 12)
        self.assertNotIn("expected_request", json.dumps(self.calls))
        with self.assertRaises(ValueError):
            evaluation.run(self.output, planner=self.planner, runtime_observation=self.runtime_path)
        self.assertEqual(len(self.calls), 12)

    def test_runtime_change_during_execution_preserves_first_trace_and_stops(self):
        self.prepare()
        self.runtime()
        original = self.planner.plan
        def changing_runtime(scope):
            trace = original(scope)
            receipt = json.loads(self.runtime_path.read_text())
            receipt["interpretation"] = "Changed after first call"
            self.runtime_path.write_text(json.dumps(receipt))
            return trace
        with patch.object(self.planner, "plan", side_effect=changing_runtime), self.assertRaisesRegex(ValueError, "changed during execution"):
            evaluation.run(self.output, planner=self.planner, runtime_observation=self.runtime_path)
        result = json.loads((self.output / "results/comparison.json").read_text())
        self.assertEqual(result["status"], "interrupted")
        self.assertEqual(result["summary"]["completed_cases"], 1)
        self.assertEqual(len(self.calls), 1)
        self.assertTrue((self.output / "results/traces/01_ppi_full.json").is_file())

    def test_v2_request_tampering_is_rejected_before_calls(self):
        self.prepare()
        self.runtime()
        (self.output / "requests/01_ppi_full.json").write_text("{}")
        with self.assertRaisesRegex(ValueError, "Frozen request changed"):
            evaluation.run(self.output, planner=self.planner, runtime_observation=self.runtime_path)
        self.assertEqual(self.calls, [])
        self.assertFalse((self.output / "results").exists())


if __name__ == "__main__":
    unittest.main()
