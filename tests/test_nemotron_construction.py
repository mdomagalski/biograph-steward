"""Strict observed-format parsing and execution-free transport, using fixtures."""
from copy import deepcopy
import io
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
from urllib.error import HTTPError

from biograph_steward.client import digest
from biograph_steward.construction_planning import fixed_construction_cases, verify_construction_plan_trace
from biograph_steward.nemotron_construction import (
    ADAPTER_REASON, NemotronConstructionPlanner, parse_tool_text,
    save_nemotron_construction_trace, verify_nemotron_construction_trace,
)
from scripts import probe_nemotron_tool_interface as probe


SCOPE = fixed_construction_cases()[0]["scope"]
REQUEST = fixed_construction_cases()[0]["expected_request"]


def tool_text(arguments=None, name="construct_cohort"):
    return "<TOOLCALL>" + json.dumps([{"name": name, "arguments": arguments or REQUEST}]) + "</TOOLCALL>"


def envelope(text, **fields):
    return {"model": probe.MODEL, "usage": {"prompt_tokens": 50, "completion_tokens": 20},
            "choices": [{"finish_reason": "stop", "message": {"role": "assistant", "content": text, **fields}}]}


def reseal(trace):
    trace["content_sha256"] = digest({k: v for k, v in trace.items() if k != "content_sha256"})
    return trace


class ObservedToolParserTests(unittest.TestCase):
    def test_observed_probe_shape_maps_to_existing_canonical_request(self):
        result = parse_tool_text(tool_text(), SCOPE)
        self.assertEqual(result["status"], "validated")
        self.assertEqual(result["construction_request"], REQUEST)
        self.assertEqual(result["proposed_plan"]["reason"], ADAPTER_REASON)

    def test_plain_text_is_never_misrepresented_as_semantic_abstention(self):
        for text in ("I'm unable to select a treatment.", "The answer is definitely yes.", "Please clarify your request."):
            result = parse_tool_text(text, SCOPE)
            self.assertEqual(result["status"], "no_call_text")
            self.assertIsNone(result["construction_request"])
            self.assertIsNone(result["validated_plan"])

    def test_malformed_multiple_unknown_or_repaired_representations_fail_closed(self):
        call = {"name": "construct_cohort", "arguments": REQUEST}
        duplicate = tool_text().replace('"name": "construct_cohort"', '"name": "wrong", "name": "construct_cohort"')
        invalid = ["", "<TOOLCALL>[]</TOOLCALL>",
            "<TOOLCALL>" + json.dumps([call, call]) + "</TOOLCALL>",
            tool_text(name="arbitrary_tool"), duplicate,
            tool_text() + tool_text(), "Explanation: " + tool_text(), tool_text() + " trailing text",
            tool_text().replace("</TOOLCALL>", ""),
            "```json\n" + tool_text() + "\n```", json.dumps([call]),
            "construct_cohort(accessions=['P04637'])", "unknown_tool(x=1)",
            "<TOOLCALL>[construct_cohort(accessions=['P04637'])]</TOOLCALL>",
            "<TOOLCALL>" + json.dumps([{**call, "extra": 1}]) + "</TOOLCALL>",
            "<TOOLCALL>" + json.dumps([{**call, "arguments": json.dumps(REQUEST)}]) + "</TOOLCALL>",
            "<TOOLCALL>[NaN]</TOOLCALL>", "<think>private</think>" + tool_text()]
        for text in invalid:
            with self.subTest(text=text[:90]):
                result = parse_tool_text(text, SCOPE)
                self.assertEqual(result["status"], "invalid_plan")
                self.assertIsNone(result["construction_request"])

    def test_existing_identity_and_capability_bounds_still_apply(self):
        invalid = [
            {**REQUEST, "accessions": ["P15056"], "focus_uniprot": "P15056"},
            {**REQUEST, "accessions": ["P04637", "P04637"]},
            {**REQUEST, "focus_uniprot": "P15056"},
            {**REQUEST, "relations": ["shared_pathways"]},
            {**REQUEST, "extra": "override"},
            {**REQUEST, "accessions": []},
            {**REQUEST, "relations": ["interactions", "interactions"]},
        ]
        for arguments in invalid:
            with self.subTest(arguments=arguments):
                self.assertEqual(parse_tool_text(tool_text(arguments), SCOPE)["status"], "invalid_plan")

    def test_valid_syntax_does_not_establish_requested_scope(self):
        both_scope = fixed_construction_cases()[2]["scope"]
        result = parse_tool_text(tool_text(), both_scope)
        self.assertEqual(result["status"], "validated")
        self.assertNotEqual(result["construction_request"], fixed_construction_cases()[2]["expected_request"])


class ObservedToolTransportTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.calls = []
        with patch.dict("os.environ", {
            "BIOGRAPH_PLANNER_MODEL": probe.MODEL,
            "BIOGRAPH_PLANNER_ENDPOINT": "http://127.0.0.1:8010/v1/chat/completions",
            "BIOGRAPH_PLANNER_API": "nim_chat", "BIOGRAPH_PLANNER_PROMPT_PROFILE": "nemotron_nano_v1",
            "BIOGRAPH_PLANNER_MAX_OUTPUT_TOKENS": "1600", "BIOGRAPH_PLANNER_TIMEOUT": "120",
            "BIOGRAPH_PLANNER_API_KEY": "fixture-secret-key"}, clear=True):
            self.planner = NemotronConstructionPlanner()
        self.response = envelope(tool_text())
        test = self
        class Opener:
            def open(self, request, timeout):
                test.calls.append((json.loads(request.data), timeout))
                if isinstance(test.response, BaseException):
                    raise test.response
                return io.BytesIO(json.dumps(test.response).encode())
        self.mock = patch.object(probe, "build_opener", return_value=Opener())
        self.mock.start()
        self.addCleanup(self.mock.stop)

    def test_wire_payload_exactly_reuses_probe_and_expectations_stay_out(self):
        for case in fixed_construction_cases():
            actual = self.planner.request(case["scope"])
            self.assertEqual(actual, probe.payload(case, self.planner.client))
            self.assertNotIn("expected_request", json.dumps(actual))
            self.assertFalse({"tools", "tool_choice", "guided_json", "response_format"} & set(actual))
        self.assertEqual(self.calls, [])

    def test_trace_binds_single_call_and_old_policy_rejects_new_interface(self):
        trace = self.planner.plan(SCOPE)
        self.assertEqual(len(self.calls), 1)
        self.assertEqual(self.calls[0][1], 120)
        self.assertEqual(trace["final_text"], tool_text())
        self.assertEqual(verify_nemotron_construction_trace(trace), REQUEST)
        self.assertEqual(trace["source_calls"], 0)
        self.assertFalse(trace["construction_executed"])
        self.assertFalse(trace["semantic_abstention_established"])
        self.assertFalse(trace["api_native_tools_used"])
        with self.assertRaises(ValueError):
            verify_construction_plan_trace(trace)
        path = Path(self.temp.name) / "trace.json"
        save_nemotron_construction_trace(trace, path)
        self.assertEqual(json.loads(path.read_text()), trace)
        with self.assertRaises(FileExistsError):
            save_nemotron_construction_trace(trace, path)

    def test_no_call_text_is_visible_and_has_no_executable_request(self):
        self.response = envelope("I cannot select a treatment for you.")
        trace = self.planner.plan(SCOPE)
        self.assertEqual(trace["status"], "no_call_text")
        self.assertEqual(trace["final_text"], "I cannot select a treatment for you.")
        self.assertIsNone(verify_nemotron_construction_trace(trace))
        self.assertIsNone(trace["proposed_plan"])
        self.assertFalse(trace["semantic_abstention_established"])

    def test_native_calls_reasoning_and_incomplete_content_fail_closed(self):
        responses = [envelope(tool_text(), tool_calls=[{"function": {"name": "construct_cohort"}}]),
                     envelope("<think>private chain</think>" + tool_text()), envelope(tool_text())]
        responses[-1]["choices"][0]["finish_reason"] = "length"
        for response in responses:
            self.response = response
            trace = self.planner.plan(SCOPE)
            self.assertEqual(trace["status"], "invalid_plan")
            self.assertIsNone(verify_nemotron_construction_trace(trace))
            self.assertNotIn("private chain", json.dumps(trace))

    def test_only_allowlisted_metadata_and_public_final_text_are_saved(self):
        self.response = envelope(tool_text(), reasoning_content="private chain", unknown="hidden metadata")
        self.response["secret"] = self.planner.client.key
        trace = self.planner.plan(SCOPE)
        for value in ("private chain", "hidden metadata", self.planner.client.key):
            self.assertNotIn(value, json.dumps(trace))
        self.assertEqual(trace["status"], "validated")

    def test_wrong_returned_model_fails_closed_without_concealing_response(self):
        self.response["model"] = "different-model"
        trace = self.planner.plan(SCOPE)
        self.assertEqual(trace["status"], "invalid_plan")
        self.assertIn("model identifier", trace["error"])
        self.assertEqual(trace["model_returned"], "different-model")
        self.assertEqual(trace["final_text"], tool_text())
        self.assertIsNone(verify_nemotron_construction_trace(trace))
        self.assertIsNone(trace["validated_plan"])

    def test_missing_returned_model_stays_explicitly_unknown(self):
        del self.response["model"]
        trace = self.planner.plan(SCOPE)
        self.assertEqual(trace["status"], "validated")
        self.assertIsNone(trace["model_returned"])
        self.assertIsNone(trace["response_metadata"]["model_returned"])
        self.assertEqual(verify_nemotron_construction_trace(trace), REQUEST)

    def test_resealed_duplicate_attribution_and_usage_inconsistencies_are_rejected(self):
        original = self.planner.plan(SCOPE)
        changes = {"model_returned": "different-model", "usage": {"total_tokens": 999}, "latency_ms": 999.0}
        for field, value in changes.items():
            for top_level in (True, False):
                with self.subTest(field=field, top_level=top_level):
                    trace = deepcopy(original)
                    (trace if top_level else trace["response_metadata"])[field] = value
                    with self.assertRaises(ValueError):
                        verify_nemotron_construction_trace(reseal(trace))

    def test_transport_error_is_recorded_without_retry_or_arbitrary_body(self):
        self.response = HTTPError(self.planner.client.endpoint, 400, "private error", {}, io.BytesIO(b"secret body"))
        trace = self.planner.plan(SCOPE)
        self.assertEqual(trace["status"], "planner_error")
        self.assertEqual(len(self.calls), 1)
        self.assertIsNone(verify_nemotron_construction_trace(trace))
        self.assertNotIn("private error", json.dumps(trace))
        self.assertNotIn("secret body", json.dumps(trace))

    def test_resealed_inconsistent_request_or_execution_claims_are_rejected(self):
        original = self.planner.plan(SCOPE)
        mutations = [lambda t: t.update(final_text="No available function."),
                     lambda t: t["construction_request"].update(focus_uniprot="P00533"),
                     lambda t: t.update(semantic_abstention_established=True),
                     lambda t: t.update(construction_executed=True),
                     lambda t: t.update(endpoint="https://example.com/v1/chat/completions"),
                     lambda t: t["response_metadata"].update(reasoning_content="private"),
                     lambda t: t.update(prompt_sha256="0" * 64)]
        for mutate in mutations:
            trace = deepcopy(original)
            mutate(trace)
            with self.assertRaises(ValueError):
                verify_nemotron_construction_trace(reseal(trace))
        self.assertEqual(len(self.calls), 1)

    def test_invalid_input_scope_prevents_transport(self):
        with self.assertRaises(ValueError):
            self.planner.plan({**SCOPE, "accessions": ["P04637", "P04637"]})
        self.assertEqual(self.calls, [])


if __name__ == "__main__":
    unittest.main()
