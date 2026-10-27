"""Guided assessment binding and failure controls using invented data only."""
from copy import deepcopy
from datetime import datetime, timedelta, timezone
import importlib.util
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from biograph_steward.client import PharosClient, digest, write_json
from biograph_steward.construction import construct_snapshot
from biograph_steward.construction_planning import ConstructionPlanner
from test_pharos_inventory import InventoryAPI

SPEC = importlib.util.spec_from_file_location(
    "evaluate_guided_construction", Path(__file__).resolve().parents[1] / "scripts/evaluate_guided_construction.py")
evaluation = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(evaluation)


def replace_ids(value, replacements):
    if isinstance(value, dict):
        return {key: replace_ids(item, replacements) for key, item in value.items()}
    if isinstance(value, list):
        return [replace_ids(item, replacements) for item in value]
    return replacements.get(value, value) if isinstance(value, str) else value


def fake_source():
    """Relabel the existing invented API fixture; no real saved records read."""
    api = InventoryAPI()
    mapping = {"P22674": "P04637", "P38936": "P00533"}
    reverse = {value: key for key, value in mapping.items()}
    def transport(payload):
        return replace_ids(api(replace_ids(payload, mapping)), reverse)
    return construct_snapshot(PharosClient(transport=transport), deepcopy(evaluation.REAL_SELECTION), data_kind="synthetic_demo")


def abstain():
    return {"reason": "Unsupported request.", "action": "abstain", "tool": None,
            "profile": None, "accessions": [], "focus_uniprot": None, "relations": []}


def proposal(request):
    return {"reason": "Inspect source candidates.", "action": "construct", "tool": "construct_cohort", **deepcopy(request)}


def response(plan, model="test-model"):
    return {"model": model, "status": "completed", "usage": {"input_tokens": 20, "output_tokens": 10},
            "output": [{"type": "message", "content": [{"type": "output_text", "text": json.dumps(plan)}]}]}


class GuidedEvaluationTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name).resolve()
        self.source = self.root / "source/snapshot.json"
        write_json(self.source, fake_source())
        self.original = self.source.read_bytes()
        self.out = self.root / "frozen"
        self.cases = evaluation.fixed_cases()
        self.calls = []
        self.outputs = [abstain() if case["expected_intent_request"] is None
                        else proposal(case["expected_intent_request"]) for case in self.cases]
        def transport(payload):
            self.calls.append(deepcopy(payload))
            return response(self.outputs[len(self.calls) - 1])
        self.planner = ConstructionPlanner(model="test-model", endpoint="http://localhost:9999/v1/responses", transport=transport)

    def prepare(self):
        return evaluation.prepare(self.out, self.source, planner=self.planner)

    def execute(self):
        return evaluation.run(self.out, planner=self.planner)

    def test_prepare_is_inference_free_and_choices_references_not_sent_to_model(self):
        self.planner.key = "never-record-this-secret"
        manifest = self.prepare()
        self.assertEqual(self.calls, [])
        self.assertEqual(manifest["maximum_model_calls"], 8)
        self.assertNotIn("never-record-this-secret", (self.out / "manifest.json").read_text())
        for index, case in enumerate(self.cases, 1):
            wire = json.loads((self.out / f"requests/{index:02d}.json").read_text())
            self.assertEqual(wire, evaluation.wire_request(self.planner, case["scope"]))
            text = json.dumps(wire)
            self.assertNotIn("expected_intent_request", text)
            self.assertNotIn("exact_selection", text)
            self.assertNotIn("supported_aligned", text)
        # The duplicated textual task has different form choices but identical
        # inference payload: the post-generation guard does not help the model.
        self.assertEqual((self.out / "requests/03.json").read_bytes(), (self.out / "requests/05.json").read_bytes())
        with self.assertRaises(ValueError):
            self.prepare()

    def test_complete_run_separates_intent_guard_and_conditional_source_parity(self):
        self.prepare()
        result = self.execute()
        self.assertEqual(len(self.calls), 8)
        self.assertEqual(result["summary"]["supported_aligned_successes"], 4)
        self.assertEqual(result["summary"]["raw_intent_matches"], 8)
        self.assertEqual(result["summary"]["mismatches_blocked"], 1)
        self.assertEqual(result["rows"][4]["guarded_status"], "invalid_plan")
        self.assertTrue(result["rows"][4]["raw_intent_match"])
        self.assertFalse(result["rows"][4]["explicit_selection_agreement"])
        self.assertEqual(result["summary"]["model_calls"], 8)
        self.assertEqual(result["summary"]["returned_token_totals"], {"input_tokens": 160, "output_tokens": 80})
        self.assertEqual(result["real_cohort_parity"]["status"], "same_snapshot_publication_parity_passed")
        self.assertFalse(result["summary"]["biological_accuracy_measured"])
        self.assertEqual(self.original, self.source.read_bytes())
        self.assertEqual(evaluation.score(self.out, planner=self.planner), result)
        self.assertEqual(len(self.calls), 8)  # Scoring is inference-free.
        with self.assertRaises(ValueError):
            self.execute()

    def test_form_agreement_on_unsupported_text_is_not_semantic_success(self):
        self.outputs[5] = proposal(self.cases[5]["selection"])
        self.prepare()
        result = self.execute()
        row = result["rows"][5]
        self.assertTrue(row["explicit_selection_agreement"])
        self.assertFalse(row["raw_intent_match"])
        self.assertTrue(row["unsupported_raw_proposal"])
        self.assertTrue(row["unsupported_guarded_proposal"])
        self.assertEqual(result["summary"]["unsupported_guarded_proposals"], 1)

    def test_abstained_real_plan_never_publishes_or_fetches(self):
        self.outputs[-1] = abstain()
        self.prepare()
        with patch.object(evaluation, "publish_construction", side_effect=AssertionError("Unexpected publication")):
            result = self.execute()
        self.assertEqual(result["real_cohort_parity"]["status"], "not_executed_nonmatching_real_plan")
        self.assertFalse((self.out / "results/planned_publication").exists())
        evaluation.score(self.out, planner=self.planner)

    def test_freeze_wire_case_code_source_and_configuration_tampering_block_before_calls(self):
        manifest = self.prepare()
        changes = [self.out / "requests/01.json", self.out / "cases.json",
                   self.out / "implementation/biograph_steward/guided_construction.py", self.source,
                   self.out / "source_snapshot.json"]
        for path in changes:
            original = path.read_bytes()
            path.write_text("{}")
            with self.subTest(path=path), self.assertRaises((ValueError, KeyError)):
                self.execute()
            path.write_bytes(original)
        self.planner.model = "changed-model"
        with self.assertRaises(ValueError):
            self.execute()
        self.assertEqual(self.calls, [])
        self.assertFalse((self.out / "results").exists())
        self.planner.model = manifest["model_configuration"]["model"]

    def test_wrong_case_trace_is_preserved_but_not_scored_and_cannot_resume(self):
        self.prepare()
        original = self.planner.plan
        wires = {digest(case["scope"]): evaluation.wire_request(self.planner, case["scope"]) for case in self.cases}
        def changed_trace(scope):
            trace = original(scope)
            if trace.get("scope") == self.cases[0]["scope"]:
                trace["scope"] = {**scope, "question": "Different question"}
            return trace
        with patch.object(evaluation, "wire_request", side_effect=lambda planner, scope: wires[digest(scope)]), \
                patch.object(self.planner, "plan", side_effect=changed_trace), self.assertRaises(ValueError):
            self.execute()
        result = json.loads((self.out / "results/comparison.json").read_text())
        self.assertEqual(result["status"], "interrupted")
        self.assertEqual(result["summary"]["completed_cases"], 0)
        self.assertEqual(result["pending_case"], "guided_ppi")
        self.assertTrue((self.out / "results/returned/01.json").is_file())
        with self.assertRaises(ValueError):
            self.execute()

    def test_interruption_preserves_finished_traces_and_unfinished_case(self):
        self.prepare()
        actual_transport = self.planner.transport
        def interrupted(payload):
            if len(self.calls) == 2:
                raise KeyboardInterrupt()
            return actual_transport(payload)
        self.planner.transport = interrupted
        with self.assertRaises(KeyboardInterrupt):
            self.execute()
        result = json.loads((self.out / "results/comparison.json").read_text())
        self.assertEqual(result["summary"]["completed_cases"], 2)
        self.assertEqual(result["pending_case"], "guided_both")
        self.assertEqual(result["status"], "interrupted")
        self.assertEqual(len(list((self.out / "results/raw_traces").glob("*.json"))), 2)
        evaluation.score(self.out, planner=self.planner)

    def test_forged_result_or_modified_artifact_is_rejected_by_offline_score(self):
        self.prepare()
        self.execute()
        comparison = self.out / "results/comparison.json"
        result = json.loads(comparison.read_text())
        result["summary"]["supported_aligned_successes"] = 0
        write_json(comparison, evaluation.existing._seal(result))
        with self.assertRaisesRegex(ValueError, "totals"):
            evaluation.score(self.out, planner=self.planner)
        result["summary"]["supported_aligned_successes"] = 4
        write_json(comparison, evaluation.existing._seal(result))
        (self.out / "results/guarded_traces/01.json").write_text("{}")
        with self.assertRaisesRegex(ValueError, "artifact"):
            evaluation.score(self.out, planner=self.planner)

    def test_returned_model_contradiction_fails_before_publication(self):
        self.prepare()
        self.planner.transport = lambda payload: response(self.outputs[0], "another-model")
        with self.assertRaisesRegex(ValueError, "Returned model"):
            self.execute()
        result = json.loads((self.out / "results/comparison.json").read_text())
        self.assertEqual(result["summary"]["completed_cases"], 0)


class RuntimeObservationTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name).resolve()
        self.observation = self.root / "runtime.json"
        config = {"planner_kind": "live_model", "endpoint": "http://127.0.0.1:8010/v1/chat/completions"}
        self.manifest = {"model_configuration": config,
            "created_at": (datetime.now(timezone.utc) - timedelta(minutes=2)).isoformat(),
            "runtime_prerequisite": evaluation.runtime_prerequisite(config)}
        evidence = self.root / "runtime_evidence.txt"
        evidence.write_text("Invented runtime observation control; not a live server.")
        self.receipt = {**self.manifest["runtime_prerequisite"], "observed_at": (datetime.now(timezone.utc) - timedelta(minutes=1)).isoformat(),
            "image_id": "sha256:" + "a" * 64, "container_id": "b" * 64,
            "evidence_files": {"runtime_evidence.txt": evaluation.sha(evidence)}}
        write_json(self.observation, self.receipt)

    def test_fresh_matching_evidence_accepted_but_old_drifted_or_corrupt_receipts_rejected(self):
        self.assertEqual(evaluation.validate_runtime(self.observation, self.manifest), self.receipt)
        for key, value in [("engine", "V1"), ("model_revision", "changed"),
                           ("observed_at", (datetime.now(timezone.utc) - timedelta(days=1)).isoformat()),
                           ("image_id", "bad"), ("evidence_files", {"../outside": "c" * 64})]:
            write_json(self.observation, {**self.receipt, key: value})
            with self.subTest(key=key), self.assertRaises(ValueError):
                evaluation.validate_runtime(self.observation, self.manifest)
        write_json(self.observation, self.receipt)
        (self.root / "runtime_evidence.txt").write_text("Changed")
        with self.assertRaises(ValueError):
            evaluation.validate_runtime(self.observation, self.manifest)


if __name__ == "__main__":
    unittest.main()
