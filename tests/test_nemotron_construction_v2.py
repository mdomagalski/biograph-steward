"""Offline guards for the revised contract and caller-owned exact selection.

These fixtures check transport, parsing, and selection enforcement. They are not
model-performance measurements or evidence of biomedical correctness.
"""
from copy import deepcopy
import io
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
from urllib.error import HTTPError

from biograph_steward.client import digest
from biograph_steward.construction_planning import (
    fixed_construction_cases, verify_construction_plan_trace,
)
from biograph_steward.nemotron_construction import (
    parse_tool_text, verify_nemotron_construction_trace,
)
from biograph_steward.nemotron_construction_v2 import (
    INTERFACE, POLICY, NemotronConstructionPlannerV2, function_definition,
    parse_tool_text_v2, response_format, save_nemotron_construction_trace_v2,
    validate_scope, verify_nemotron_construction_trace_v2,
)
from scripts import probe_nemotron_tool_interface as probe


CASES = {case["id"]: case for case in fixed_construction_cases()}
SCOPE = CASES["ppi_full"]["scope"]
REQUEST = CASES["ppi_full"]["expected_request"]
SUBSET = CASES["subset"]["expected_request"]


def locked_scope(selection=None, scope=None):
    return {**deepcopy(SCOPE if scope is None else scope),
            "exact_selection": deepcopy(REQUEST if selection is None else selection)}


def tool_text(arguments=None, name="construct_cohort"):
    return "<TOOLCALL>" + json.dumps([
        {"name": name, "arguments": REQUEST if arguments is None else arguments}
    ]) + "</TOOLCALL>"


def envelope(text, **fields):
    return {"model": probe.MODEL, "usage": {"prompt_tokens": 50, "completion_tokens": 20},
            "choices": [{"finish_reason": "stop", "message": {
                "role": "assistant", "content": text, **fields}}]}


def reseal(trace):
    trace["content_sha256"] = digest({k: v for k, v in trace.items() if k != "content_sha256"})
    return trace


def expected_response_format():
    """Checked-in shape of the frozen two-call V1 compatibility schema.

    Do not read ignored runs/ artifacts: this expectation must work in a clean
    checkout and must not be derived from the implementation under test.
    """
    def branch(profile, relations):
        return {"type": "object", "additionalProperties": False,
                "required": ["accessions", "focus_uniprot", "profile", "relations"],
                "properties": {
                    "accessions": {"type": "array", "items": {
                        "type": "string", "enum": ["P04637", "P00533", "P01116"]}},
                    "focus_uniprot": {"type": "string", "enum": ["P04637", "P00533", "P01116"]},
                    "profile": {"type": "string", "enum": [profile]},
                    "relations": {"type": "array", "enum": relations}}}
    return {"type": "structural_tag", "structures": [{
        "begin": "<TOOLCALL>", "schema": {"type": "array", "items": {
            "type": "object", "additionalProperties": False,
            "required": ["name", "arguments"], "properties": {
                "name": {"type": "string", "enum": ["construct_cohort"]},
                "arguments": {"anyOf": [
                    branch("ppi", [["interactions"]]),
                    branch("context", [["interactions"], ["shared_pathways"],
                                       ["interactions", "shared_pathways"],
                                       ["shared_pathways", "interactions"]])
                ]}}}}, "end": "</TOOLCALL>"}], "triggers": ["<TOOLCALL>"]}


class ExactSelectionParserTests(unittest.TestCase):
    def test_unlocked_scope_preserves_old_parser_behavior(self):
        examples = [tool_text(), tool_text(SUBSET), "Please clarify your request.",
                    tool_text({**REQUEST, "profile": "pathways"}),
                    tool_text({**REQUEST, "accessions": ["P15056"], "focus_uniprot": "P15056"}),
                    tool_text() + tool_text(), "Explanation: " + tool_text()]
        for text in examples:
            with self.subTest(text=text):
                old = parse_tool_text(text, SCOPE)
                new = parse_tool_text_v2(text, SCOPE)
                self.assertEqual(new["status"], old["status"])
                self.assertEqual(new["construction_request"], old["construction_request"])
                self.assertFalse(new["explicit_selection_supplied"])
                self.assertIsNone(new["explicit_selection_agreement"])

    def test_selection_mismatches_fail_without_silently_repairing_proposal(self):
        selection = SUBSET
        proposed = [REQUEST, {**SUBSET, "accessions": ["P00533"]},
                    {**SUBSET, "focus_uniprot": "P04637"},
                    {**SUBSET, "profile": "context"},
                    {**SUBSET, "profile": "context", "relations": ["shared_pathways"]}]
        for arguments in proposed:
            with self.subTest(arguments=arguments):
                result = parse_tool_text_v2(tool_text(arguments), locked_scope(selection))
                self.assertEqual(result["status"], "invalid_plan")
                self.assertIsNone(result["construction_request"])
                self.assertIsNone(result["validated_plan"])
                self.assertTrue(result["explicit_selection_supplied"])
                self.assertFalse(result["explicit_selection_agreement"])
                for key, value in arguments.items():
                    self.assertEqual(result["proposed_plan"][key], value)

    def test_order_is_canonicalized_without_changing_membership_or_profile(self):
        selection = {**deepcopy(REQUEST), "profile": "context",
                     "relations": ["shared_pathways", "interactions"]}
        selection["accessions"].reverse()
        proposal = {**deepcopy(REQUEST), "profile": "context",
                    "relations": ["interactions", "shared_pathways"]}
        result = parse_tool_text_v2(tool_text(proposal), locked_scope(selection))
        self.assertEqual(result["status"], "validated")
        self.assertEqual(result["construction_request"], proposal)
        self.assertTrue(result["explicit_selection_agreement"])
        self.assertEqual(selection["accessions"], ["P01116", "P00533", "P04637"])

    def test_relation_mismatch_alone_is_rejected(self):
        selection = {**REQUEST, "profile": "context", "relations": ["interactions", "shared_pathways"]}
        proposal = {**selection, "relations": ["interactions"]}
        result = parse_tool_text_v2(tool_text(proposal), locked_scope(selection))
        self.assertEqual(result["status"], "invalid_plan")
        self.assertFalse(result["explicit_selection_agreement"])
        self.assertEqual(result["proposed_plan"]["relations"], ["interactions"])
        self.assertIsNone(result["construction_request"])

    def test_context_with_interactions_is_valid_and_is_not_rewritten_as_ppi(self):
        request = {**REQUEST, "profile": "context"}
        result = parse_tool_text_v2(tool_text(request), locked_scope(request))
        self.assertEqual(result["status"], "validated")
        self.assertEqual(result["construction_request"], request)
        wrong_profile = parse_tool_text_v2(tool_text(), locked_scope(request))
        self.assertEqual(wrong_profile["status"], "invalid_plan")
        self.assertEqual(wrong_profile["proposed_plan"]["profile"], "ppi")

    def test_caller_selection_is_validated_against_constructor_and_authorized_scope(self):
        malformed = [None, [], {}, {**REQUEST, "unexpected": True},
                     {k: v for k, v in REQUEST.items() if k != "relations"},
                     {**REQUEST, "accessions": []},
                     {**REQUEST, "accessions": ["P04637", "P04637"]},
                     {**REQUEST, "accessions": ["P15056"], "focus_uniprot": "P15056"},
                     {**REQUEST, "focus_uniprot": "P15056"},
                     {**REQUEST, "profile": "pathways"},
                     {**REQUEST, "relations": ["shared_pathways"]},
                     {**REQUEST, "relations": ["interactions", "interactions"]}]
        for selection in malformed:
            with self.subTest(selection=selection):
                with self.assertRaises(ValueError):
                    validate_scope({**SCOPE, "exact_selection": selection})
        scope = locked_scope(SUBSET)
        original = deepcopy(scope)
        validate_scope(scope)
        self.assertEqual(scope, original)

    def test_exact_selection_does_not_establish_unsupported_filter_semantics(self):
        scope = locked_scope(REQUEST, CASES["assay_filter"]["scope"])
        result = parse_tool_text_v2(tool_text(), scope)
        # The lock is an explicit field comparison, not an assay-language model.
        # A contract-compliant request can still omit the user's unsupported
        # assay requirement; the fixed unsupported-case evaluation must catch it.
        self.assertEqual(result["status"], "validated")
        self.assertEqual(result["construction_request"], REQUEST)

    def test_no_call_text_never_becomes_semantic_success(self):
        for text in ("I cannot select a treatment.", "The treatment is definitely effective."):
            result = parse_tool_text_v2(text, locked_scope())
            self.assertEqual(result["status"], "no_call_text")
            self.assertIsNone(result["construction_request"])
            self.assertIsNone(result["validated_plan"])

    def test_schema_reuses_the_observed_v1_shape_and_keeps_valid_context_branch(self):
        self.assertEqual(response_format(SCOPE), expected_response_format())
        self.assertEqual(function_definition(SCOPE)["parameters"],
                         expected_response_format()["structures"][0]["schema"]["items"]["properties"]["arguments"])

    def test_function_contract_covers_previously_omitted_exclusions(self):
        function = function_definition(SCOPE)
        self.assertEqual(function["name"], "construct_cohort")
        text = function["description"].lower()
        for required in ("clinical", "variant", "organism", "disease", "assay",
                         "physical binding", "calibrated confidence", "prun", "arbitrary sources",
                         "url", "code execution", "publication", "unsupported"):
            with self.subTest(required=required):
                self.assertIn(required, text)


class ExactSelectionTransportTests(unittest.TestCase):
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
            self.planner = NemotronConstructionPlannerV2()
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

    def test_request_binds_explicit_selection_without_evaluation_expectations(self):
        scope = locked_scope(SUBSET, CASES["subset"]["scope"])
        wire = self.planner.request(scope)
        self.assertEqual(wire["response_format"], response_format(scope))
        self.assertEqual(wire["model"], probe.MODEL)
        self.assertEqual(wire["max_tokens"], 1600)
        self.assertFalse(wire["stream"])
        self.assertEqual(wire["temperature"], 0)
        self.assertEqual(wire["messages"][0], {"role": "system", "content": "detailed thinking off"})
        self.assertNotIn("expected_request", json.dumps(wire))
        self.assertFalse({"tools", "tool_choice", "guided_json"} & set(wire))
        self.assertIn("exact_selection", json.dumps(wire))
        self.assertEqual(self.calls, [])

    def test_valid_trace_is_versioned_execution_free_and_exclusively_saved(self):
        trace = self.planner.plan(locked_scope())
        self.assertEqual(len(self.calls), 1)
        self.assertEqual(self.calls[0][1], 120)
        self.assertEqual(trace["policy"], POLICY)
        self.assertEqual(trace["evaluation_interface"], INTERFACE)
        self.assertEqual(verify_nemotron_construction_trace_v2(trace), REQUEST)
        self.assertEqual(trace["source_calls"], 0)
        self.assertFalse(trace["construction_executed"])
        self.assertFalse(trace["scientific_accuracy_evaluated"])
        self.assertFalse(trace["semantic_abstention_established"])
        self.assertFalse(trace["api_native_tools_used"])
        for old_verifier in (verify_construction_plan_trace, verify_nemotron_construction_trace):
            with self.assertRaises(ValueError):
                old_verifier(trace)
        path = Path(self.temp.name) / "trace.json"
        save_nemotron_construction_trace_v2(trace, path)
        self.assertEqual(json.loads(path.read_text()), trace)
        with self.assertRaises(FileExistsError):
            save_nemotron_construction_trace_v2(trace, path)

    def test_malformed_selection_fails_before_any_transport(self):
        for selection in (None, {}, {**REQUEST, "focus_uniprot": "P15056"},
                          {**REQUEST, "accessions": ["P04637", "P04637"]}):
            with self.subTest(selection=selection):
                with self.assertRaises(ValueError):
                    self.planner.plan({**SCOPE, "exact_selection": selection})
        self.assertEqual(self.calls, [])

    def test_mismatched_selection_is_preserved_but_not_executable(self):
        trace = self.planner.plan(locked_scope(SUBSET))
        self.assertEqual(trace["status"], "invalid_plan")
        self.assertIsNone(verify_nemotron_construction_trace_v2(trace))
        self.assertEqual(trace["final_text"], tool_text())
        self.assertEqual(trace["proposed_plan"]["accessions"], REQUEST["accessions"])
        self.assertIsNone(trace["construction_request"])

    def test_no_call_text_is_unscored_and_cannot_be_promoted_by_resealing(self):
        self.response = envelope("I cannot select a treatment for you.")
        trace = self.planner.plan(locked_scope())
        self.assertEqual(trace["status"], "no_call_text")
        self.assertIsNone(verify_nemotron_construction_trace_v2(trace))
        self.assertFalse(trace["semantic_abstention_established"])
        trace["semantic_abstention_established"] = True
        with self.assertRaises(ValueError):
            verify_nemotron_construction_trace_v2(reseal(trace))

    def test_resealed_selection_request_and_outcome_changes_are_rejected(self):
        original = self.planner.plan(locked_scope())
        mutations = [
            lambda t: t["scope"].update(exact_selection=deepcopy(SUBSET)),
            lambda t: t["construction_request"].update(focus_uniprot="P00533"),
            lambda t: t["validated_plan"].update(profile="context"),
            lambda t: t.update(final_text="No available function."),
            lambda t: t.update(status="no_call_text", construction_request=None),
            lambda t: t.update(construction_executed=True),
            lambda t: t.update(prompt_sha256="0" * 64),
            lambda t: t.update(request_sha256="0" * 64),
            lambda t: t.update(explicit_selection_supplied=False),
            lambda t: t.update(explicit_selection_agreement=False),
            lambda t: t["response_metadata"].update(reasoning_content="private"),
        ]
        for mutate in mutations:
            trace = deepcopy(original)
            mutate(trace)
            with self.subTest(trace_status=trace["status"]):
                with self.assertRaises(ValueError):
                    verify_nemotron_construction_trace_v2(reseal(trace))

    def test_resealed_invalid_selection_cannot_be_promoted_to_validated(self):
        trace = self.planner.plan(locked_scope(SUBSET))
        trace.update(status="validated", error=None, construction_request=deepcopy(REQUEST),
                     validated_plan=deepcopy(trace["proposed_plan"]))
        with self.assertRaises(ValueError):
            verify_nemotron_construction_trace_v2(reseal(trace))

    def test_resealed_old_interface_is_rejected(self):
        trace = self.planner.plan(SCOPE)
        trace.update(format="biograph-steward.nemotron-tool-construction.v1",
                     policy="biograph-steward.nemotron-tool-construction.v1",
                     evaluation_interface="nemotron_tool_v1")
        with self.assertRaises(ValueError):
            verify_nemotron_construction_trace_v2(reseal(trace))

    def test_native_tools_incomplete_output_and_reasoning_markup_fail_closed(self):
        responses = [envelope(tool_text(), tool_calls=[{"function": {"name": "construct_cohort"}}]),
                     envelope("<think>private chain</think>" + tool_text()), envelope(tool_text())]
        responses[-1]["choices"][0]["finish_reason"] = "length"
        for response in responses:
            self.response = response
            trace = self.planner.plan(locked_scope())
            self.assertEqual(trace["status"], "invalid_plan")
            self.assertIsNone(verify_nemotron_construction_trace_v2(trace))
            self.assertNotIn("private chain", json.dumps(trace))

    def test_private_metadata_and_credentials_are_not_retained(self):
        self.response = envelope(tool_text(), reasoning_content="private chain", unknown="hidden metadata")
        self.response["secret"] = self.planner.client.key
        trace = self.planner.plan(locked_scope())
        self.assertEqual(trace["status"], "validated")
        for value in ("private chain", "hidden metadata", self.planner.client.key):
            self.assertNotIn(value, json.dumps(trace))
        self.response = envelope("Here is " + self.planner.client.key)
        withheld = self.planner.plan(locked_scope())
        self.assertIsNone(verify_nemotron_construction_trace_v2(withheld))
        self.assertNotIn(self.planner.client.key, json.dumps(withheld))

    def test_wrong_returned_model_and_resealed_attribution_fail_closed(self):
        self.response["model"] = "different-model"
        trace = self.planner.plan(SCOPE)
        self.assertEqual(trace["status"], "invalid_plan")
        self.assertIsNone(verify_nemotron_construction_trace_v2(trace))
        self.assertEqual(trace["model_returned"], "different-model")
        self.assertEqual(trace["final_text"], tool_text())
        self.response = envelope(tool_text())
        original = self.planner.plan(SCOPE)
        for field, value in {"model_returned": "different-model", "usage": {"total_tokens": 999},
                             "latency_ms": 999.0}.items():
            for top_level in (True, False):
                altered = deepcopy(original)
                (altered if top_level else altered["response_metadata"])[field] = value
                with self.assertRaises(ValueError):
                    verify_nemotron_construction_trace_v2(reseal(altered))

    def test_transport_error_has_no_retry_or_arbitrary_provider_body(self):
        self.response = HTTPError(self.planner.client.endpoint, 400, "private error", {}, io.BytesIO(b"secret body"))
        trace = self.planner.plan(SCOPE)
        self.assertEqual(trace["status"], "planner_error")
        self.assertEqual(len(self.calls), 1)
        self.assertIsNone(verify_nemotron_construction_trace_v2(trace))
        for value in ("private error", "secret body"):
            self.assertNotIn(value, json.dumps(trace))


if __name__ == "__main__":
    unittest.main()
