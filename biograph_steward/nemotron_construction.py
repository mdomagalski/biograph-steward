"""Experimental, execution-free adapter for the observed Nano TOOLCALL format.

The pinned NVIDIA card supplies the prompt wrapper, but not an exact Nano parser.
Our two-call probe observed a JSON array inside TOOLCALL tags, unlike the related
BFCL Ultra handler's Python-call representation. This parser accepts only that
observed shape. It is an author-pattern adaptation, not a BFCL reproduction or
API-native tool implementation. Existing production planner policies are unchanged.
"""
from __future__ import annotations

from copy import deepcopy
import json
from pathlib import Path
import re
from types import SimpleNamespace

from .client import digest, utcnow
from .construction_planning import (
    construction_request_from_plan, validate_construction_plan, validate_construction_scope,
)

POLICY = "biograph-steward.nemotron-tool-construction.v1"
INTERFACE = "nemotron_tool_v1"
ARGUMENT_FIELDS = {"accessions", "focus_uniprot", "profile", "relations"}
RESPONSE_FIELDS = {"status", "error_type", "http_status", "model_calls", "format_assessment",
    "accuracy_scored", "response_sha256", "model_returned", "usage", "finish_reason",
    "content_status", "native_tool_calls_present", "latency_ms"}
ADAPTER_REASON = "Adapter parsed one construct_cohort call; syntax and capability bounds only."
FORMAT_NOTE = ("Observed Nano TOOLCALL JSON-array adaptation; not an exact BFCL reproduction "
               "or evidence of API-native tool support.")


def _probe():
    # Deliberate research-only reuse: this module is not a default production
    # provider. Lazy loading also avoids the probe/evaluation runner import cycle.
    from scripts import probe_nemotron_tool_interface
    return probe_nemotron_tool_interface


def _strict_loads(text):
    def pairs(items):
        result = {}
        for key, value in items:
            if key in result:
                raise ValueError("Duplicate tool-call JSON key.")
            result[key] = value
        return result
    def constant(_):
        raise ValueError("Nonfinite tool-call JSON value.")
    return json.loads(text, object_pairs_hook=pairs, parse_constant=constant)


def parse_tool_text(text, scope):
    """Parse one exact call, or distinguish unstructured no-call text.

    No-call is only a syntax observation: the text could refuse, ask a question,
    answer incorrectly, or be irrelevant. It is never promoted to an abstention.
    """
    scope = validate_construction_scope(scope)
    result = {"status": "invalid_plan", "proposed_plan": None, "validated_plan": None,
              "construction_request": None, "error": "Unsupported or malformed tool-call representation."}
    if (not isinstance(text, str) or not text.strip() or len(text.encode("utf-8")) > 20000
            or _probe().REASONING_MARKUP.search(text)):
        return result
    stripped = text.strip()
    match = re.fullmatch(r"<TOOLCALL>(.*)</TOOLCALL>", stripped, re.DOTALL)
    if match is None:
        # Do not relabel recognizable malformed/untagged structured calls as a
        # natural-language no-call response. No partial tag or JSON repair.
        structured = (re.search(r"TOOLCALL|\b[A-Za-z_][A-Za-z0-9_.]*\s*\(|```", stripped, re.I)
                      or stripped.startswith(("[", "{", "<")))
        if not structured:
            result.update(status="no_call_text", error=None)
        return result
    try:
        calls = _strict_loads(match.group(1))
        if (not isinstance(calls, list) or len(calls) != 1 or not isinstance(calls[0], dict)
                or set(calls[0]) != {"name", "arguments"}
                or calls[0]["name"] != "construct_cohort"
                or not isinstance(calls[0]["arguments"], dict)
                or set(calls[0]["arguments"]) != ARGUMENT_FIELDS):
            return result
        proposed = {"reason": ADAPTER_REASON, "action": "construct", "tool": "construct_cohort",
                    **calls[0]["arguments"]}
        result["proposed_plan"] = proposed
        validated = validate_construction_plan(proposed, scope)
        result.update(status="validated", validated_plan=validated,
                      construction_request=construction_request_from_plan(validated, scope), error=None)
    except (ValueError, TypeError, RecursionError):
        pass
    return result


def _audit(scope, wire):
    probe = _probe()
    return {"scope": deepcopy(scope), "scope_sha256": digest(scope),
            "question_sha256": digest(scope["question"]),
            "function_definition_sha256": digest(probe.function_definition(scope)),
            "prompt_sha256": digest(wire["messages"]), "request_sha256": digest(wire)}


def _interpret(final_text, metadata, scope):
    empty = {"status": "invalid_plan", "proposed_plan": None, "validated_plan": None,
             "construction_request": None, "error": "No complete supported text-only response."}
    if metadata.get("status") == "transport_error":
        return {**empty, "status": "planner_error", "error": "Model transport failed; no retry or fallback."}
    returned_model = metadata.get("model_returned")
    if returned_model is not None and returned_model != _probe().MODEL:
        return {**empty, "error": "Returned model identifier differs from the configured Nano model."}
    if (metadata.get("status") != "response_received" or metadata.get("finish_reason") != "stop"
            or metadata.get("native_tool_calls_present") is not False
            or metadata.get("content_status") != "captured_unparsed"):
        return empty
    return parse_tool_text(final_text, scope)


class NemotronConstructionPlanner:
    """One call through the already-bounded probe transport; never executes tools."""
    policy = POLICY
    evaluation_interface = INTERFACE

    def __init__(self, client=None):
        self.client = client or _probe().configured_client()
        _probe().validate_client(self.client)

    def request(self, scope):
        scope = validate_construction_scope(scope)
        _probe().validate_client(self.client)
        return _probe().payload({"scope": scope}, self.client)

    def plan(self, scope):
        scope = validate_construction_scope(scope)
        wire = self.request(scope)
        observation = _probe().request_once(self.client, wire)
        # The probe already omits unknown metadata, credentials and reasoning.
        # Persist final text once, separately from the response envelope metadata.
        final_text = observation.pop("content", None)
        observation = {key: value for key, value in observation.items() if key in RESPONSE_FIELDS}
        outcome = _interpret(final_text, observation, scope)
        trace = {"format": POLICY, "policy": POLICY, "created_at": utcnow(),
            "evaluation_interface": INTERFACE, "planner_kind": self.client.kind,
            "provider_requested": self.client.provider, "model_requested": self.client.model,
            "model_returned": observation.get("model_returned"), "endpoint": self.client.endpoint,
            "api": self.client.api, "prompt_profile": self.client.prompt_profile,
            "model_calls": 1, "transport_requests": 1, "usage": observation.get("usage"),
            "latency_ms": observation.get("latency_ms"), "cost": None,
            "request_settings": {"max_output_tokens": self.client.max_output_tokens,
                                 "timeout_seconds": self.client.timeout},
            **_audit(scope, wire), "response_metadata": observation, "final_text": final_text,
            **outcome, "reason_origin": "adapter_provided_not_model_reasoning",
            "source_calls": 0, "construction_executed": False, "scientific_accuracy_evaluated": False,
            "semantic_abstention_established": False, "api_native_tools_used": False,
            "execution_guard": {"tools_supplied": False, "redirects": False, "retries": 0,
                                "repair_calls": 0, "tool_execution": False},
            "format_note": FORMAT_NOTE,
            "semantic_intent_validation": "Not established by tool syntax or capability validation."}
        trace["content_sha256"] = digest(trace)
        verify_nemotron_construction_trace(trace)
        return trace


def verify_nemotron_construction_trace(trace):
    """Re-derive parsed selection; integrity is not a semantic correctness claim."""
    try:
        if (not isinstance(trace, dict) or trace.get("format") != POLICY or trace.get("policy") != POLICY
                or trace.get("evaluation_interface") != INTERFACE
                or trace.get("content_sha256") != digest({k: v for k, v in trace.items() if k != "content_sha256"})):
            raise ValueError("Invalid experimental construction trace digest or policy.")
        scope = validate_construction_scope(trace["scope"])
        settings = trace["request_settings"]
        if (type(settings["max_output_tokens"]) is not int or not 128 <= settings["max_output_tokens"] <= 1600
                or type(settings["timeout_seconds"]) is not int or not 1 <= settings["timeout_seconds"] <= 120
                or trace.get("model_requested") != _probe().MODEL):
            raise ValueError("Invalid model or request bounds.")
        _probe().validate_client(SimpleNamespace(model=trace["model_requested"], api=trace["api"],
            prompt_profile=trace["prompt_profile"], endpoint=trace["endpoint"], loopback=True,
            transport=None, max_output_tokens=settings["max_output_tokens"], timeout=settings["timeout_seconds"]))
        wire = _probe().payload({"scope": scope}, SimpleNamespace(
            model=trace["model_requested"], max_output_tokens=settings["max_output_tokens"]))
        if any(trace.get(key) != value for key, value in _audit(scope, wire).items()):
            raise ValueError("Experimental trace differs from its exact wire request.")
        if (trace.get("source_calls") != 0 or trace.get("construction_executed") is not False
                or trace.get("scientific_accuracy_evaluated") is not False
                or trace.get("semantic_abstention_established") is not False
                or trace.get("api_native_tools_used") is not False
                or trace.get("model_calls") != 1 or trace.get("transport_requests") != 1
                or trace.get("reason_origin") != "adapter_provided_not_model_reasoning"
                or trace.get("format_note") != FORMAT_NOTE
                or trace.get("execution_guard") != {"tools_supplied": False, "redirects": False,
                    "retries": 0, "repair_calls": 0, "tool_execution": False}):
            raise ValueError("Experimental planning cannot claim execution or semantic abstention.")
        text = trace.get("final_text")
        if text is not None and (not isinstance(text, str) or len(text.encode("utf-8")) > 20000
                                 or _probe().REASONING_MARKUP.search(text)):
            raise ValueError("Trace cannot retain oversized content or reasoning markup.")
        if not isinstance(trace["response_metadata"], dict) or set(trace["response_metadata"]) - RESPONSE_FIELDS:
            raise ValueError("Trace has unsupported response metadata.")
        if any(trace.get(key) != trace["response_metadata"].get(key)
               for key in ("model_returned", "usage", "latency_ms")):
            raise ValueError("Trace attribution or usage differs from the recorded response metadata.")
        expected = _interpret(text, trace["response_metadata"], scope)
        if any(trace.get(key) != value for key, value in expected.items()):
            raise ValueError("Experimental trace does not match the parsed final response.")
        return expected["construction_request"]
    except (KeyError, TypeError, AttributeError, RecursionError) as exc:
        raise ValueError("Malformed experimental construction trace.") from exc


def save_nemotron_construction_trace(trace, path):
    verify_nemotron_construction_trace(trace)
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("x", encoding="utf-8") as handle:
        handle.write(json.dumps(trace, indent=2, ensure_ascii=True, allow_nan=False) + "\n")
    return path
