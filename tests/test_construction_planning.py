"""Bounded construction selection with invented model responses; no live calls."""
from copy import deepcopy
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from biograph_steward.client import digest
from biograph_steward.construction_planning import (
    ConstructionPlanner, configured_construction_planner, construction_planning_request,
    validate_construction_scope, validate_construction_plan, verify_construction_plan_trace,
    construction_request_from_plan, save_construction_plan, fixed_construction_cases,
    compare_construction_cases,
)


def scope(**changes):
    return {"question": "Retrieve interaction candidates for the supplied cohort.",
            "accessions": ["P04637", "P00533", "P01116"], "focus_uniprot": "P04637", **changes}


def proposal(**changes):
    return {"reason": "Inspect source-reported interaction candidates.", "action": "construct",
            "tool": "construct_cohort", "profile": "ppi", "accessions": ["P04637", "P00533", "P01116"],
            "focus_uniprot": "P04637", "relations": ["interactions"], **changes}


def abstention():
    return proposal(action="abstain", tool=None, profile=None, accessions=[], focus_uniprot=None,
                    relations=[], reason="The requested capability is unavailable.")


def response(plan):
    return {"status": "completed", "model": "test-model-returned", "usage": {"input_tokens": 42, "output_tokens": 20},
            "output": [{"type": "message", "content": [{"type": "output_text", "text": json.dumps(plan)}]}]}


def planner(output, calls=None, **kwargs):
    def transport(payload):
        if calls is not None:
            calls.append(payload)
        return response(output)
    return ConstructionPlanner(model="test-model", endpoint="http://localhost:9999/v1/responses",
                               transport=transport, **kwargs)


def reseal(trace):
    trace = deepcopy(trace)
    trace.pop("content_sha256", None)
    trace["content_sha256"] = digest(trace)
    return trace


class ConstructionPlanningTests(unittest.TestCase):
    def test_exact_cohort_and_question_validated_before_model_call(self):
        calls = []
        client = planner(proposal(), calls)
        for changes in ({"question": " "}, {"question": 10}, {"question": "x" * 4001},
                        {"accessions": []}, {"accessions": ["TP53"]},
                        {"accessions": ["P04637", "P04637"]}, {"focus_uniprot": "P15056"},
                        {"endpoint": "https://other.example"}):
            with self.subTest(changes=changes), self.assertRaises(ValueError):
                client.plan(scope(**changes))
        self.assertEqual(calls, [])

    def test_single_call_schema_bound_to_allowed_ids_with_no_reference_or_evidence(self):
        calls = []
        original = scope()
        trace = planner(proposal(), calls).plan(original)
        self.assertEqual(len(calls), 1)
        self.assertEqual(trace["status"], "validated")
        self.assertEqual(trace["planner_kind"], "injected_test_model")
        self.assertEqual(trace["model_requested"], "test-model")
        self.assertEqual(trace["model_returned"], "test-model-returned")
        self.assertEqual(trace["usage"], {"input_tokens": 42, "output_tokens": 20})
        self.assertEqual(trace["source_calls"], 0)
        self.assertFalse(trace["construction_executed"])
        self.assertFalse(trace["scientific_accuracy_evaluated"])
        self.assertEqual(trace["scope"], original)
        self.assertEqual(verify_construction_plan_trace(trace), trace["construction_request"])
        schema = calls[0]["text"]["format"]["schema"]
        self.assertEqual(schema["properties"]["accessions"]["items"]["enum"], original["accessions"])
        self.assertFalse(schema["additionalProperties"])
        serialized = json.dumps(calls)
        for secret in ("expected_request", "reference_plan", "assay_outcome", "source_statement"):
            self.assertNotIn(secret, serialized)
        self.assertNotIn("tools", calls[0])
        self.assertEqual(original, scope())

    def test_permitted_subset_and_focus_are_canonicalized_without_expansion(self):
        p = proposal(accessions=["P00533", "P04637"], focus_uniprot="P00533")
        validated = validate_construction_plan(p, scope())
        self.assertEqual(validated["accessions"], ["P04637", "P00533"])
        self.assertEqual(validated["focus_uniprot"], "P00533")
        self.assertEqual(p["accessions"], ["P00533", "P04637"])

    def test_deterministic_scope_validation_rejects_invented_identity_tool_and_parameters(self):
        cases = [{"accessions": ["P04637", "P15056"]}, {"focus_uniprot": "P15056"},
                 {"accessions": ["P04637", "P04637"]}, {"accessions": []},
                 {"accessions": ["TP53"]}, {"tool": "shell"}, {"tool": None},
                 {"tool": ["construct_cohort"]}, {"action": "publish"}, {"action": []},
                 {"profile": "unbounded"}, {"relations": ["causes"]},
                 {"relations": ["interactions", "interactions"]}, {"relations": []},
                 {"endpoint": "https://example.org"}, {"confidence": 0.99}, {"accept": True},
                 {"reason": " "}, {"reason": "x" * 1201}]
        for changes in cases:
            with self.subTest(changes=changes):
                trace = planner(proposal(**changes)).plan(scope())
                self.assertEqual(trace["status"], "invalid_plan")
                self.assertIsNone(trace["construction_request"])
                self.assertIsNone(verify_construction_plan_trace(trace))

    def test_profile_relation_rules_reuse_constructor(self):
        with self.assertRaises(ValueError):
            validate_construction_plan(proposal(relations=["shared_pathways"]), scope())
        p = proposal(profile="context", relations=["shared_pathways", "interactions"])
        result = construction_request_from_plan(p, scope())
        self.assertEqual(result["relations"], ["interactions", "shared_pathways"])
        p = proposal(profile="context", relations=["shared_pathways"])
        self.assertEqual(construction_request_from_plan(p, scope())["profile"], "context")

    def test_abstention_cannot_hide_a_construction(self):
        trace = planner(abstention()).plan(scope(question="Predict physical binding."))
        self.assertEqual(trace["status"], "abstained")
        self.assertIsNone(verify_construction_plan_trace(trace))
        for changes in ({"tool": "construct_cohort"}, {"accessions": ["P04637"]},
                        {"focus_uniprot": "P04637"}, {"profile": "ppi"}, {"relations": ["interactions"]}):
            with self.subTest(changes=changes), self.assertRaises(ValueError):
                validate_construction_plan({**abstention(), **changes}, scope())

    def test_invalid_or_refused_transport_output_never_yields_executable_request(self):
        examples = [[], {"status": "incomplete"}, {"status": "completed", "output": []},
                    {"status": "completed", "output": [{"type": "message", "content": [{"type": "refusal"}]}]},
                    response(proposal())]
        examples[-1]["output"][0]["content"][0]["text"] = "not json"
        for raw in examples:
            with self.subTest(raw=raw):
                client = ConstructionPlanner(model="test", endpoint="http://localhost:9999",
                                            transport=lambda _, raw=raw: raw)
                trace = client.plan(scope())
                self.assertEqual(trace["status"], "invalid_plan")
                self.assertIsNone(verify_construction_plan_trace(trace))

    def test_transport_failure_is_preserved_without_fallback(self):
        calls = []
        def unavailable(payload):
            calls.append(payload)
            raise OSError("fixture failure")
        client = ConstructionPlanner(model="test", endpoint="http://localhost:9999", transport=unavailable)
        trace = client.plan(scope())
        self.assertEqual(len(calls), 1)
        self.assertEqual(trace["status"], "planner_error")
        self.assertEqual(trace["execution_guard"]["retries"], 0)
        self.assertIsNone(verify_construction_plan_trace(trace))

    def test_existing_nvidia_nano_prompt_and_guided_json_transport_are_preserved(self):
        calls = []
        def nim(payload):
            calls.append(payload)
            return {"model": "nvidia/test", "choices": [{"finish_reason": "stop",
                    "message": {"role": "assistant", "content": json.dumps(proposal())}}]}
        with patch.dict("os.environ", {"BIOGRAPH_PLANNER_PROMPT_PROFILE": "nemotron_nano_v1",
                                       "BIOGRAPH_PLANNER_API_KEY": "test-secret"}):
            client = ConstructionPlanner(model="nvidia/test", endpoint="http://localhost:9999/v1/chat/completions",
                                         api="nim_chat", provider="api", transport=nim)
            trace = client.plan(scope())
        self.assertEqual(trace["status"], "validated")
        self.assertEqual(calls[0]["messages"][0], {"role": "system", "content": "detailed thinking off"})
        self.assertIn("Untrusted input data:", calls[0]["messages"][1]["content"])
        self.assertIn("guided_json", calls[0])
        self.assertEqual(calls[0]["temperature"], 0)
        self.assertNotIn("test-secret", json.dumps(trace))
        self.assertNotIn("test-secret", json.dumps(calls))

    def test_changed_saved_trace_requires_consistent_revalidation_not_only_new_digest(self):
        original = planner(proposal()).plan(scope())
        changed = deepcopy(original)
        changed["scope"]["question"] = "Changed question"
        with self.assertRaises(ValueError):
            verify_construction_plan_trace(changed)
        with self.assertRaises(ValueError):
            verify_construction_plan_trace(reseal(changed))
        for key, value in (("construction_request", None), ("source_calls", 1),
                           ("construction_executed", True), ("scientific_accuracy_evaluated", True),
                           ("validated_plan", abstention()), ("status", "abstained")):
            changed = deepcopy(original)
            changed[key] = value
            with self.subTest(key=key), self.assertRaises(ValueError):
                verify_construction_plan_trace(reseal(changed))

    def test_standalone_trace_save_is_exclusive_and_replayable(self):
        trace = planner(proposal()).plan(scope())
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp) / "plan.json"
            self.assertEqual(save_construction_plan(trace, path), path)
            self.assertEqual(verify_construction_plan_trace(json.loads(path.read_text())), trace["construction_request"])
            with self.assertRaises(FileExistsError):
                save_construction_plan(trace, path)

    def test_unconfigured_provider_fails_without_implicit_network_selection(self):
        with patch.dict("os.environ", {}, clear=True), self.assertRaises(ValueError):
            configured_construction_planner()
        with self.assertRaises(ValueError):
            configured_construction_planner(provider="unlisted", model="test")

    def test_fixed_comparison_separates_expected_request_from_model_input(self):
        cases = fixed_construction_cases()
        calls = []
        outputs = []
        for case in cases:
            expected = case["expected_request"]
            outputs.append(abstention() if expected is None else proposal(**expected))
        def transport(payload):
            calls.append(payload)
            return response(outputs[len(calls) - 1])
        client = ConstructionPlanner(model="test", endpoint="http://localhost:9999", transport=transport)
        result = compare_construction_cases(client, cases)
        self.assertEqual(result["summary"]["scope_matches"], len(cases))
        self.assertEqual(result["summary"]["unsafe_construct_on_abstention"], 0)
        self.assertEqual(result["summary"]["model_calls"], len(cases))
        self.assertEqual(result["summary"]["source_calls"], 0)
        self.assertNotIn("expected_request", json.dumps(calls))
        self.assertNotIn("expected_action", json.dumps(calls))

    def test_comparison_records_semantically_wrong_but_schema_valid_plan_as_failure(self):
        cases = [fixed_construction_cases()[6]]  # Physical-binding-only is unsupported.
        result = compare_construction_cases(planner(proposal()), cases)
        self.assertEqual(result["summary"]["scope_matches"], 0)
        self.assertEqual(result["summary"]["unsafe_construct_on_abstention"], 1)
        self.assertEqual(result["rows"][0]["trace"]["status"], "validated")
        self.assertEqual(result["summary"]["source_calls"], 0)

    def test_all_comparison_references_checked_before_any_model_call(self):
        calls = []
        cases = fixed_construction_cases()
        cases[-1]["expected_request"] = {"accessions": ["P15056"], "focus_uniprot": "P15056",
                                        "profile": "ppi", "relations": ["interactions"]}
        cases[-1]["expected_action"] = "construct"
        with self.assertRaises(ValueError):
            compare_construction_cases(planner(proposal(), calls), cases)
        self.assertEqual(calls, [])


if __name__ == "__main__":
    unittest.main()
