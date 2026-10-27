"""Bind an unchanged v3 model proposal to explicit guided-form choices.

This is an application check, not a new model prompt or an assessment of free
text, source truth or scientific accuracy. The original model trace remains
intact and the existing publication/export hooks preserve this outer record.
"""
from __future__ import annotations

from copy import deepcopy
from pathlib import Path

from .client import digest, utcnow
from .file_utils import sha
from .construction_planning import (
    POLICY as MODEL_POLICY, construction_request_from_plan,
    validate_construction_scope, verify_construction_plan_trace,
)

POLICY = "biograph-steward.guided-construction-selection.v1"
SELECTION_FIELDS = {"accessions", "focus_uniprot", "profile", "relations"}
ATTRIBUTION_FIELDS = (
    "planner_kind", "provider_requested", "model_requested", "model_returned",
    "endpoint", "api", "prompt_profile", "request_settings", "model_calls",
    "transport_requests", "usage", "cost", "cost_note", "latency_ms",
    "execution_guard",
)
LIMITATION = (
    "Agreement with explicit guided choices only; arbitrary natural-language "
    "intent and scientific accuracy are not established."
)


def validate_guided_selection(scope, selection):
    """Reuse construction bounds and v3 canonical ordering; never repair choices."""
    scope = validate_construction_scope(scope)
    if not isinstance(selection, dict) or set(selection) != SELECTION_FIELDS:
        raise ValueError("Supply the complete explicit cohort, focus, profile and relations.")
    return construction_request_from_plan({
        "action": "construct", "tool": "construct_cohort",
        "reason": "Explicit guided-form selection.", **deepcopy(selection),
    }, scope)


def _fields(trace, selection, created_at):
    # Only original v3 traces are eligible. This prevents nested wrappers and
    # prevents an experimental Nano interface from acquiring execution rights.
    if not isinstance(trace, dict) or trace.get("format") != MODEL_POLICY:
        raise ValueError("Guided selection requires the unchanged v3 model trace.")
    model_request = verify_construction_plan_trace(trace)
    scope = validate_construction_scope(trace["scope"])
    exact = validate_guided_selection(scope, selection)
    agrees = None if model_request is None else model_request == exact
    status = trace["status"] if agrees is not False else "invalid_plan"
    result = {
        "format": POLICY, "policy": POLICY, "created_at": created_at,
        "selection_guard_implementation_sha256": sha(Path(__file__)),
        **{key: deepcopy(trace[key]) for key in ATTRIBUTION_FIELDS if key in trace},
        "scope": scope, "scope_sha256": digest(scope),
        "question_sha256": digest(scope["question"]),
        "supplied_selection": deepcopy(selection), "exact_selection": exact,
        "selection_sha256": digest(exact),
        "model_trace": deepcopy(trace), "model_trace_sha256": digest(trace),
        "model_construction_request": deepcopy(model_request),
        "explicit_selection_agreement": agrees, "status": status,
        "proposed_plan": deepcopy(trace.get("proposed_plan")),
        "validated_plan": deepcopy(trace.get("validated_plan")) if agrees is not False else None,
        "construction_request": deepcopy(model_request) if agrees is True else None,
        "source_calls": 0, "construction_executed": False,
        "scientific_accuracy_evaluated": False,
        "semantic_intent_validation": LIMITATION,
        "selection_guard": {"comparison": "complete_canonical_request_equality",
                            "repair_applied": False, "model_prompt_changed": False},
    }
    if agrees is False:
        result["error"] = "Model proposal differs from your explicit choices; no repair or retrieval was performed."
    elif "error" in trace:
        result["error"] = deepcopy(trace["error"])
    return result


def guard_construction_trace(trace, selection):
    """Return a new immutable-style record; do not modify the original model trace."""
    guarded = _fields(trace, selection, utcnow())
    guarded["content_sha256"] = digest(guarded)
    verify_guided_construction_trace(guarded)
    return guarded


def verify_guided_construction_trace(trace):
    """Recheck the original trace and exact selection before any source access."""
    try:
        if (not isinstance(trace, dict) or trace.get("format") != POLICY
                or trace.get("policy") != POLICY
                or trace.get("content_sha256") != digest({
                    key: value for key, value in trace.items() if key != "content_sha256"})):
            raise ValueError("Guided construction trace digest or policy is invalid.")
        created_at = trace["created_at"]
        if not isinstance(created_at, str) or not 1 <= len(created_at) <= 100:
            raise ValueError("Guided construction creation time is invalid.")
        expected = _fields(trace["model_trace"], trace["supplied_selection"], created_at)
        expected["content_sha256"] = digest(expected)
        if trace != expected:
            raise ValueError("Guided trace differs from the original proposal or explicit choices.")
        return deepcopy(trace["construction_request"])
    except (KeyError, TypeError, AttributeError) as exc:
        raise ValueError("Malformed guided construction trace.") from exc
