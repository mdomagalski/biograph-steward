"""Frozen raw-format observation with no model or network calls."""
import importlib.util
import io
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
from urllib.error import HTTPError
from urllib.request import ProxyHandler

from biograph_steward.model_transport import JSONModelClient, ModelUnavailable, _NoRedirect

SPEC = importlib.util.spec_from_file_location(
    "probe_nemotron_tool_interface", Path(__file__).resolve().parents[1] / "scripts/probe_nemotron_tool_interface.py")
probe = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(probe)


def envelope(content="Unparsed final content", **message_fields):
    return {"model": probe.MODEL, "usage": {"prompt_tokens": 12, "completion_tokens": 8, "total_tokens": 20},
            "choices": [{"finish_reason": "stop", "message": {"role": "assistant", "content": content, **message_fields}}]}


class NanoToolProbeTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.output = Path(self.temp.name) / "probe"
        self.calls, self.handlers = [], []
        environment = {"BIOGRAPH_PLANNER_MODEL": probe.MODEL,
            "BIOGRAPH_PLANNER_ENDPOINT": "http://127.0.0.1:8010/v1/chat/completions",
            "BIOGRAPH_PLANNER_API": "nim_chat", "BIOGRAPH_PLANNER_PROMPT_PROFILE": "nemotron_nano_v1",
            "BIOGRAPH_PLANNER_MAX_OUTPUT_TOKENS": "1600", "BIOGRAPH_PLANNER_TIMEOUT": "120",
            "BIOGRAPH_PLANNER_API_KEY": "fixture-secret-key"}
        with patch.dict("os.environ", environment, clear=True):
            self.client = probe.configured_client()
        self.responses = [envelope("<TOOLCALL>not parsed or executed</TOOLCALL>"), envelope("No available function.")]
        test = self
        class FakeOpener:
            def open(self, request, timeout):
                test.calls.append((request, timeout))
                value = test.responses[len(test.calls) - 1]
                if isinstance(value, BaseException):
                    raise value
                return io.BytesIO(value if isinstance(value, bytes) else json.dumps(value).encode())
        def build(*handlers):
            self.handlers.append(handlers)
            return FakeOpener()
        self.network = patch.object(probe, "build_opener", side_effect=build)
        self.network.start()
        self.addCleanup(self.network.stop)

    def prepare(self):
        return probe.prepare(self.output, client=self.client)

    def test_preparation_freezes_author_wrapper_without_calls_or_expected_answers(self):
        manifest = self.prepare()
        self.assertEqual(self.calls, [])
        self.assertEqual(manifest["maximum_model_calls"], 2)
        self.assertEqual(manifest["maximum_output_tokens"], 3200)
        self.assertIsNone(manifest["output_parser"])
        _, wires = probe.validate_freeze(self.output, self.client)
        for wire in wires.values():
            self.assertEqual(wire["messages"][0], {"role": "system", "content": "detailed thinking off"})
            self.assertTrue(wire["messages"][1]["content"].startswith("<AVAILABLE_TOOLS>["))
            self.assertNotIn("expected_request", json.dumps(wire))
            self.assertNotIn("expected_action", json.dumps(wire))
            self.assertFalse({"guided_json", "response_format", "tools", "tool_choice"} & set(wire))
            self.assertNotIn(self.client.key, json.dumps(wire))
        self.assertNotIn(self.client.key, (self.output / "manifest.json").read_text())
        with self.assertRaises(ValueError):
            self.prepare()

    def test_two_calls_capture_unparsed_content_and_reuse_no_redirect_loopback_guards(self):
        self.prepare()
        result = probe.run(self.output, client=self.client)
        self.assertEqual(len(self.calls), 2)
        self.assertEqual(result["completed_calls"], 2)
        self.assertEqual(result["format_assessment"], "unassessed")
        self.assertFalse(result["accuracy_scored"])
        self.assertFalse(result["tool_execution"])
        self.assertEqual(result["source_calls"], 0)
        self.assertEqual(result["rows"][0]["content"], self.responses[0]["choices"][0]["message"]["content"])
        self.assertEqual(result["rows"][0]["usage"]["total_tokens"], 20)
        for (request, timeout), handlers in zip(self.calls, self.handlers):
            self.assertEqual(request.get_method(), "POST")
            self.assertEqual(timeout, 120)
            self.assertTrue(any(isinstance(h, _NoRedirect) for h in handlers))
            self.assertTrue(any(isinstance(h, ProxyHandler) and h.proxies == {} for h in handlers))
            self.assertNotIn(self.client.key, request.data.decode())
        with self.assertRaises(ValueError):
            probe.run(self.output, client=self.client)
        self.assertEqual(len(self.calls), 2)

    def test_changed_wire_code_or_config_fails_before_calls(self):
        self.prepare()
        path = self.output / "requests/01_ppi_full.json"
        original = path.read_bytes()
        path.write_text("{}")
        with self.assertRaises(ValueError):
            probe.run(self.output, client=self.client)
        path.write_bytes(original)
        self.client.timeout = 119
        with self.assertRaises(ValueError):
            probe.run(self.output, client=self.client)
        self.client.timeout = 120
        changed = probe.implementation_hashes()
        changed["biograph_steward/model_transport.py"] = "0" * 64
        with patch.object(probe, "implementation_hashes", return_value=changed), self.assertRaises(ValueError):
            probe.run(self.output, client=self.client)
        self.assertEqual(self.calls, [])
        self.assertFalse((self.output / "results").exists())

    def test_inputs_and_output_symlinks_fail_before_calls(self):
        self.prepare()
        path = self.output / "cases.json"
        saved = self.output / "original.json"
        path.rename(saved)
        path.symlink_to(saved)
        with self.assertRaises(ValueError):
            probe.run(self.output, client=self.client)
        path.unlink()
        saved.rename(path)
        (self.output / "results").symlink_to(self.output / "missing")
        with self.assertRaises(ValueError):
            probe.run(self.output, client=self.client)
        self.assertEqual(self.calls, [])

    def test_unknown_metadata_reasoning_and_credential_echo_not_persisted(self):
        self.responses[0] = envelope("Final text", reasoning_content="private reasoning", unknown="unknown metadata")
        self.responses[0]["debug"] = self.client.key
        self.responses[0]["usage"]["secret"] = self.client.key
        self.responses[1] = envelope(self.client.key)
        self.prepare()
        result = probe.run(self.output, client=self.client)
        saved = (self.output / "results/probe.json").read_text()
        for forbidden in ("private reasoning", "unknown metadata", self.client.key):
            self.assertNotIn(forbidden, saved)
        self.assertEqual(result["rows"][0]["content"], "Final text")
        self.assertIsNone(result["rows"][1]["content"])
        self.assertEqual(result["rows"][1]["content_status"], "withheld_credential_value")

    def test_thinking_markup_and_incomplete_output_are_not_retained(self):
        for content in ("<think>private</think>final", "<think>partial", "<|analysis|>private"):
            result = probe.collect_response(envelope(content))
            self.assertEqual(result["content_status"], "withheld_reasoning_markup")
            self.assertIsNone(result["content"])
        raw = envelope("partial output")
        raw["choices"][0]["finish_reason"] = "length"
        result = probe.collect_response(raw)
        self.assertEqual(result["content_status"], "not_a_complete_final_message")
        self.assertIsNone(result["content"])

    def test_native_tool_calls_are_observed_without_parsing_or_executing(self):
        raw = envelope(None, tool_calls=[{"function": {"name": "arbitrary", "arguments": "not executed"}}])
        raw["choices"][0]["finish_reason"] = "tool_calls"
        result = probe.collect_response(raw)
        self.assertTrue(result["native_tool_calls_present"])
        self.assertIsNone(result["content"])
        self.assertNotIn("arbitrary", json.dumps(result))

    def test_http_error_is_not_retried_and_error_body_not_saved(self):
        self.responses[0] = HTTPError(self.client.endpoint, 302, self.client.key, {}, io.BytesIO(b"private error body"))
        self.prepare()
        result = probe.run(self.output, client=self.client)
        self.assertEqual(len(self.calls), 2)
        self.assertEqual(result["rows"][0]["http_status"], 302)
        self.assertEqual(result["rows"][0]["status"], "transport_error")
        self.assertNotIn(self.client.key, json.dumps(result))
        self.assertNotIn("private error body", json.dumps(result))

    def test_response_and_content_size_limits(self):
        self.responses[0] = b"x" * 1_000_002
        self.responses[1] = envelope("x" * 20001)
        self.prepare()
        result = probe.run(self.output, client=self.client)
        self.assertEqual(result["rows"][0]["error_type"], "ValueError")
        self.assertEqual(result["rows"][1]["content_status"], "exceeds_content_bound")
        self.assertIsNone(result["rows"][1]["content"])

    def test_interrupted_call_preserves_first_result_and_cannot_resume(self):
        self.responses[1] = KeyboardInterrupt()
        self.prepare()
        with self.assertRaises(KeyboardInterrupt):
            probe.run(self.output, client=self.client)
        result = json.loads((self.output / "results/probe.json").read_text())
        self.assertEqual(result["status"], "interrupted")
        self.assertEqual(result["completed_calls"], 1)
        self.assertEqual(result["pending_request"], "requests/02_clinical.json")
        self.assertEqual(len(self.calls), 2)
        with self.assertRaises(ValueError):
            probe.run(self.output, client=self.client)

    def test_probe_rejects_wrong_runtime_remote_endpoint_and_excess_budget(self):
        for field, bad in (("model", "another-model"), ("api", "responses"), ("prompt_profile", "standard"),
                           ("endpoint", "https://example.com/v1/chat/completions"),
                           ("max_output_tokens", 1601), ("timeout", 121)):
            original = getattr(self.client, field)
            setattr(self.client, field, bad)
            with self.subTest(field=field), self.assertRaises(ModelUnavailable):
                probe.prepare(self.output, client=self.client)
            setattr(self.client, field, original)
        self.assertEqual(self.calls, [])
        self.assertFalse(self.output.exists())


if __name__ == "__main__":
    unittest.main()
