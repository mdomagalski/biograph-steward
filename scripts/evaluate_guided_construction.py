#!/usr/bin/env python3
"""Freeze and assess unchanged JSON v3 proposals against explicit form choices.

Eight bounded requests, no retries or repairs. The four familiar supported
questions and two unsupported challenges are consumed development examples.
The evaluation contract is new; these are not a new held-out benchmark. The
guard receives literal form selections after inference, never in the prompt.
Conditional real-cohort publication replays only the frozen saved snapshot.
"""
from __future__ import annotations

import argparse
from copy import copy, deepcopy
from datetime import datetime, timezone
from html import escape
import json
from pathlib import Path
import re
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from biograph_steward.client import digest, utcnow, write_json
from biograph_steward.construction import publish_construction, verify_construction_run, verify_construction_snapshot
from biograph_steward.construction_planning import (
    ConstructionPlanner, POLICY as MODEL_POLICY, construction_request_from_plan,
    save_construction_plan, validate_construction_scope, verify_construction_plan_trace,
)
from biograph_steward.file_utils import new_output, sha
from biograph_steward.guided_construction import (
    POLICY as GUARD_POLICY, guard_construction_trace, validate_guided_selection,
)
from scripts import evaluate_construction_planner as existing

FORMAT = "biograph-steward.guided-construction-development.v1"
LIMITATION = ("Consumed development questions with explicitly declared form choices; "
              "not a held-out benchmark, biological accuracy, intended-user success or graph improvement.")
REAL_SELECTION = {"accessions": ["P22674", "P38936"], "focus_uniprot": "P22674",
                  "profile": "ppi", "relations": ["interactions"]}


def fixed_cases():
    """Literal form inputs and separate references, never answer-derived choices.

    The ordinary PPI form is deliberately left selected in conflicting and
    unsupported free-text cases. Agreement with that form is not intent success.
    """
    ids = ["P04637", "P00533", "P01116"]
    ppi = {"accessions": list(ids), "focus_uniprot": "P04637", "profile": "ppi", "relations": ["interactions"]}
    pathways = {"accessions": list(ids), "focus_uniprot": "P04637", "profile": "context", "relations": ["shared_pathways"]}
    both = {"accessions": list(ids), "focus_uniprot": "P04637", "profile": "context", "relations": ["interactions", "shared_pathways"]}
    subset = {"accessions": ["P04637", "P00533"], "focus_uniprot": "P00533", "profile": "ppi", "relations": ["interactions"]}
    rows = [
        ("guided_ppi", "supported_aligned", "Retrieve Pharos interaction candidates among the supplied cohort, focused on P04637.", ppi, deepcopy(ppi)),
        ("guided_pathways", "supported_aligned", "Build shared pathway candidates for the supplied cohort, focused on P04637.", pathways, deepcopy(pathways)),
        ("guided_both", "supported_aligned", "Construct interaction and shared pathway evidence for the supplied cohort, focused on P04637.", both, deepcopy(both)),
        ("guided_subset", "supported_aligned", "Retrieve interaction candidates only among P04637 and P00533, focused on P00533.", subset, deepcopy(subset)),
        ("conflicting_choices", "conflicting_form_and_text", "Construct interaction and shared pathway evidence for the supplied cohort, focused on P04637.", ppi, deepcopy(both)),
        ("unsupported_assay", "unsupported_text", "Retrieve only interactions verified by yeast two-hybrid assays.", ppi, None),
        ("unsupported_identity", "unsupported_text", "Add P15056 to the supplied cohort and retrieve its interactions.", ppi, None),
    ]
    cases = [{"id": key, "category": category,
              "scope": {"question": question, "accessions": list(ids), "focus_uniprot": "P04637"},
              "selection": deepcopy(selection), "expected_intent_request": reference}
             for key, category, question, selection, reference in rows]
    cases.append({"id": "real_cohort", "category": "saved_real_cohort",
        "scope": {"question": "Retrieve reported interaction candidates among this cohort, focused on P22674.",
                  "accessions": ["P22674", "P38936"], "focus_uniprot": "P22674"},
        "selection": deepcopy(REAL_SELECTION), "expected_intent_request": deepcopy(REAL_SELECTION)})
    return cases


def implementation_hashes():
    names = set(existing.BOUND_FILES) | {
        "scripts/evaluate_guided_construction.py", "biograph_steward/guided_construction.py",
        "scripts/observe_guided_construction_runtime.sh",
        "biograph_steward/graph.py", "biograph_steward/retrieval.py", "biograph_steward/questions.py",
        "biograph_steward/context.py", "biograph_steward/normalization.py",
        "biograph_steward/assertions.py", "biograph_steward/benchmark.py", "biograph_steward/gold_packet.py",
    }
    return {name: sha(ROOT / name) for name in sorted(names)}


def _planner():
    return ConstructionPlanner(provider="api")


def wire_request(planner, scope):
    """Capture the existing transport's exact payload without network or inference."""
    captured = []
    class Captured(BaseException):
        pass
    def transport(payload):
        captured.append(deepcopy(payload))
        raise Captured()
    client = copy(planner)
    client.transport = transport
    try:
        client.plan(deepcopy(scope))
    except Captured:
        pass
    if len(captured) != 1:
        raise ValueError("Expected exactly one inference-free wire capture.")
    return captured[0]


def runtime_prerequisite(config):
    """Current production V0 settings; no structural-tag engine migration."""
    return {"format": FORMAT + ".runtime", "observation_kind": "live_runtime_observation",
        "engine": "V0", "vllm_version": "0.8.5", "xgrammar_version": "0.1.18",
        "image": "vllm/vllm-openai:v0.8.5@sha256:6cf9808ca8810fc6c3fd0451c2e7784fb224590d81f7db338e7eaf3c02a33d33",
        "model": "nvidia/Llama-3.1-Nemotron-Nano-8B-v1",
        "model_revision": "54641c1611fcff44fa4865626462445e0a153fc7",
        "tokenizer_revision": "54641c1611fcff44fa4865626462445e0a153fc7",
        "dtype": "bfloat16", "health_http_status": 200,
        "served_model_ids": ["nvidia/Llama-3.1-Nemotron-Nano-8B-v1"],
        "request_endpoint": config["endpoint"], "server_endpoint": "http://127.0.0.1:8000",
        "effective_flags": {"max_model_len": 16384, "max_num_seqs": 1,
            "gpu_memory_utilization": 0.75, "enforce_eager": True,
            "guided_decoding_backend": "xgrammar", "generation_config": "vllm"}}


def _validate_cases(cases):
    if cases != fixed_cases():
        raise ValueError("Cases differ from the declared eight guided tasks.")
    for case in cases:
        validate_construction_scope(case["scope"])
        validate_guided_selection(case["scope"], case["selection"])
        if case["expected_intent_request"] is not None:
            plan = {"action": "construct", "tool": "construct_cohort", "reason": "Separate intent comparator.",
                    **case["expected_intent_request"]}
            if construction_request_from_plan(plan, case["scope"]) != case["expected_intent_request"]:
                raise ValueError("Noncanonical intent comparator.")


def _validate_live_config(config):
    if config["planner_kind"] == "injected_test_model":
        return
    from urllib.parse import urlparse
    endpoint = urlparse(config["endpoint"])
    if (config["provider"] != "api" or config["planner_kind"] != "live_model"
            or config["model"] != runtime_prerequisite(config)["model"]
            or config["api"] != "nim_chat" or config["prompt_profile"] != "nemotron_nano_v1"
            or config["max_output_tokens"] != 1600 or config["timeout_seconds"] != 120
            or endpoint.scheme != "http" or endpoint.hostname not in {"127.0.0.1", "localhost", "::1"}
            or endpoint.username is not None or endpoint.password is not None
            or endpoint.query or endpoint.fragment or endpoint.path != "/v1/chat/completions"):
        raise ValueError("Use the pinned Nano v1 loopback/V0 configuration and budgets.")


def prepare(out, source_snapshot, *, planner=None):
    planner = planner or _planner()
    config = existing.model_configuration(planner)
    _validate_live_config(config)
    source_snapshot = Path(source_snapshot)
    if source_snapshot.is_symlink():
        raise ValueError("Use an ordinary saved snapshot without symlinks.")
    source_snapshot = source_snapshot.resolve()
    source = existing._strict_json(source_snapshot)
    verify_construction_snapshot(source)
    if source["construction"]["request"] != REAL_SELECTION:
        raise ValueError("The saved source must be the predeclared CCNO/CDKN1A PPI snapshot.")
    if config["planner_kind"] != "injected_test_model" and source.get("data_kind") != "live_pharos":
        raise ValueError("A live assessment requires real saved Pharos source responses.")
    cases = fixed_cases()
    _validate_cases(cases)
    wires = [wire_request(planner, case["scope"]) for case in cases]
    implementation = implementation_hashes()
    out = new_output(out, source_snapshot.parent)
    write_json(out / "cases.json", cases)
    (out / "source_snapshot.json").write_bytes(source_snapshot.read_bytes())
    request_files = {}
    for index, wire in enumerate(wires, 1):
        name = f"requests/{index:02d}.json"
        write_json(out / name, wire)
        request_files[name] = sha(out / name)
    for name in implementation:
        destination = out / "implementation" / name
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_bytes((ROOT / name).read_bytes())
    manifest = existing._seal({"format": FORMAT, "status": "prepared", "created_at": utcnow(),
        "model_policy": MODEL_POLICY, "guard_policy": GUARD_POLICY,
        "cases_sha256": digest(cases), "cases_file_sha256": sha(out / "cases.json"),
        "case_count": len(cases), "model_configuration": config,
        "implementation_sha256": implementation, "request_files": request_files,
        "source_snapshot_sha256": sha(out / "source_snapshot.json"),
        "original_source_snapshot": str(source_snapshot), "original_source_sha256": sha(source_snapshot),
        "source_snapshot_content_sha256": source["content_sha256"],
        "source_scope": "Saved Pharos-only construction snapshot; assay attachments are not replayed.",
        "maximum_model_calls": 8, "maximum_output_tokens": 8 * config["max_output_tokens"],
        "model_calls_during_preparation": 0, "new_source_calls": 0,
        "reference_exposure": "Development questions reused; literal form choices are not inferred from references. No references or choices enter the model prompt.",
        "retry_policy": "One call per case; no retries, repairs, fallback or resumption.",
        "publication_rule": "Only the fixed real-cohort trace may publish if it matches both explicit form choices and the saved snapshot request; same frozen snapshot in both arms.",
        "runtime_prerequisite": runtime_prerequisite(config),
        "runtime_verification": existing.RUNTIME_NOTE, "interpretation": LIMITATION})
    write_json(out / "manifest.json", manifest)
    validate_freeze(out, planner=planner)
    return manifest


def validate_freeze(experiment, *, planner=None):
    experiment = Path(experiment)
    if experiment.is_symlink() or not experiment.is_dir():
        raise ValueError("Use an ordinary frozen experiment directory.")
    manifest = existing._strict_json(experiment / "manifest.json")
    if (manifest != existing._seal(manifest) or manifest.get("format") != FORMAT
            or manifest.get("status") != "prepared" or manifest.get("model_policy") != MODEL_POLICY
            or manifest.get("guard_policy") != GUARD_POLICY or manifest.get("interpretation") != LIMITATION
            or manifest.get("runtime_verification") != existing.RUNTIME_NOTE
            or manifest.get("implementation_sha256") != implementation_hashes()):
        raise ValueError("Frozen manifest, policy or implementation changed.")
    cases = existing._strict_json(experiment / "cases.json")
    _validate_cases(cases)
    if (sha(experiment / "cases.json") != manifest["cases_file_sha256"]
            or digest(cases) != manifest["cases_sha256"] or manifest.get("case_count") != 8
            or manifest.get("maximum_model_calls") != 8 or manifest.get("model_calls_during_preparation") != 0
            or manifest.get("new_source_calls") != 0):
        raise ValueError("Frozen case inventory or limits changed.")
    config = manifest["model_configuration"]
    _validate_live_config(config)
    planner = planner or _planner()
    if existing.model_configuration(planner) != config:
        raise ValueError("Planner configuration differs from the freeze.")
    if (manifest.get("maximum_output_tokens") != 8 * config["max_output_tokens"]
            or manifest.get("runtime_prerequisite") != runtime_prerequisite(config)):
        raise ValueError("Frozen runtime or token budget changed.")
    for name, checksum in manifest["implementation_sha256"].items():
        path = experiment / "implementation" / name
        if path.is_symlink() or not path.is_file() or sha(path) != checksum:
            raise ValueError("Frozen implementation copy changed: " + name)
    if set(manifest["request_files"]) != {f"requests/{index:02d}.json" for index in range(1, 9)}:
        raise ValueError("Frozen request inventory changed.")
    for index, case in enumerate(cases, 1):
        name = f"requests/{index:02d}.json"
        if (existing._strict_json(experiment / name) != wire_request(planner, case["scope"])
                or sha(experiment / name) != manifest["request_files"][name]):
            raise ValueError("Frozen request changed: " + name)
    source = existing._strict_json(experiment / "source_snapshot.json")
    verify_construction_snapshot(source)
    original = Path(manifest["original_source_snapshot"])
    if (sha(experiment / "source_snapshot.json") != manifest["source_snapshot_sha256"]
            or source["content_sha256"] != manifest["source_snapshot_content_sha256"]
            or source["construction"]["request"] != REAL_SELECTION
            or sha(original) != manifest["original_source_sha256"]):
        raise ValueError("Saved/original source snapshot changed.")
    return manifest, cases, source


def validate_runtime(path, manifest, *, evidence_base=None):
    if manifest["model_configuration"]["planner_kind"] == "injected_test_model":
        if path is not None:
            raise ValueError("Injected tests cannot claim a live runtime observation.")
        return None
    if path is None:
        raise ValueError("Record a fresh read-only V0 runtime observation before inference.")
    path = Path(path)
    observation = existing._strict_json(path)
    if not isinstance(observation, dict) or any(observation.get(key) != value for key, value in manifest["runtime_prerequisite"].items()):
        raise ValueError("Runtime observation differs from the pinned V0 configuration.")
    try:
        observed = datetime.fromisoformat(observation["observed_at"])
        prepared = datetime.fromisoformat(manifest["created_at"])
        if observed.tzinfo is None or prepared.tzinfo is None or observed < prepared or observed > datetime.now(timezone.utc):
            raise ValueError
    except (KeyError, TypeError, ValueError) as exc:
        raise ValueError("Runtime observation must follow the freeze and cannot be future-dated.") from exc
    if (re.fullmatch(r"sha256:[0-9a-f]{64}", observation.get("image_id", "")) is None
            or re.fullmatch(r"[0-9a-f]{64}", observation.get("container_id", "")) is None
            or not isinstance(observation.get("evidence_files"), dict) or not observation["evidence_files"]):
        raise ValueError("Runtime needs actual image/container IDs and hashed observation evidence.")
    for name, checksum in observation["evidence_files"].items():
        if not isinstance(name, str) or not isinstance(checksum, str) or re.fullmatch(r"[0-9a-f]{64}", checksum) is None:
            raise ValueError("Invalid runtime evidence name or checksum.")
        relative = Path(name)
        base = Path(evidence_base) if evidence_base is not None else path.parent
        evidence = base / relative
        if (relative.is_absolute() or ".." in relative.parts
                or any((base / Path(*relative.parts[:i])).is_symlink() for i in range(1, len(relative.parts) + 1))
                or not evidence.is_file() or sha(evidence) != checksum):
            raise ValueError("Runtime evidence changed or uses an unsafe path.")
    return observation


def assess(case, raw, guarded):
    raw_request = verify_construction_plan_trace(raw)
    guarded_request = verify_construction_plan_trace(guarded)
    if guarded["model_trace"] != raw or guarded["scope"] != case["scope"] or guarded["supplied_selection"] != case["selection"]:
        raise ValueError("Guarded trace does not bind this raw trace and literal selection.")
    raw_success = raw["status"] in {"validated", "abstained"} and raw_request == case["expected_intent_request"]
    return {"case_id": case["id"], "category": case["category"], "raw_status": raw["status"],
        "guarded_status": guarded["status"], "raw_request": raw_request, "guarded_request": guarded_request,
        "raw_intent_match": raw_success, "explicit_selection_agreement": guarded["explicit_selection_agreement"],
        "mismatch_blocked": raw_request is not None and guarded["explicit_selection_agreement"] is False and guarded_request is None,
        "unsupported_raw_proposal": case["expected_intent_request"] is None and raw_request is not None,
        "unsupported_parsed_construct_attempt": case["expected_intent_request"] is None
            and isinstance(raw.get("proposed_plan"), dict) and raw["proposed_plan"].get("action") == "construct",
        "unsupported_guarded_proposal": case["expected_intent_request"] is None and guarded_request is not None,
        "question_form_conflict": case["category"] == "conflicting_form_and_text",
        "aligned_supported_task_success": case["category"] == "supported_aligned" and raw_success and guarded_request == case["selection"],
        "execution_authorized_by_evaluation": case["category"] == "saved_real_cohort" and raw_success and guarded_request == REAL_SELECTION}


def summarize(rows, raw_traces):
    usage = {}
    for trace in raw_traces:
        for key, value in (trace.get("usage") or {}).items():
            if type(value) is int:
                usage[key] = usage.get(key, 0) + value
    count = lambda key: sum(row[key] is True for row in rows)
    return {"completed_cases": len(rows), "supported_aligned_cases": sum(row["category"] == "supported_aligned" for row in rows),
        "supported_aligned_successes": count("aligned_supported_task_success"), "raw_intent_matches": count("raw_intent_match"),
        "selection_agreements": count("explicit_selection_agreement"), "mismatches_blocked": count("mismatch_blocked"),
        "unsupported_raw_proposals": count("unsupported_raw_proposal"), "unsupported_guarded_proposals": count("unsupported_guarded_proposal"),
        "unsupported_parsed_construct_attempts": count("unsupported_parsed_construct_attempt"),
        "raw_invalid_plans": sum(row["raw_status"] == "invalid_plan" for row in rows),
        "raw_planner_errors": sum(row["raw_status"] == "planner_error" for row in rows),
        "model_calls": sum(trace["model_calls"] for trace in raw_traces), "returned_token_totals": usage,
        "new_source_calls": 0, "biological_accuracy_measured": False, "intended_user_success_measured": False,
        "cost": None, "cost_note": "Returned usage only; VM billing/startup/idle costs are not allocated."}


def _trace_binding(trace, case, wire, config):
    if trace.get("scope") != case["scope"] or trace.get("request_sha256") != digest(wire):
        raise ValueError("Trace scope/wire differs from this fixed request.")
    fields = {"provider_requested": config["provider"], "planner_kind": config["planner_kind"],
        "model_requested": config["model"], "endpoint": config["endpoint"], "api": config["api"],
        "prompt_profile": config["prompt_profile"], "request_settings": {
            "max_output_tokens": config["max_output_tokens"], "timeout_seconds": config["timeout_seconds"]},
        "model_calls": 1, "transport_requests": 1}
    if any(trace.get(key) != value for key, value in fields.items()):
        raise ValueError("Trace model configuration/call budget differs from the freeze.")
    if trace.get("model_returned") not in {None, config["model"]}:
        raise ValueError("Returned model explicitly contradicts the declared model.")
    verify_construction_plan_trace(trace)


def _parity(source, guarded, output):
    """Existing publisher replays recorded responses; no network client exists here."""
    if verify_construction_plan_trace(guarded) != REAL_SELECTION:
        return {"status": "not_executed_nonmatching_real_plan", "new_source_calls": 0}
    planned = publish_construction(deepcopy(source), output / "planned_publication", planning_trace=guarded)
    deterministic = publish_construction(deepcopy(source), output / "deterministic_publication")
    verify_construction_run(output / "planned_publication")
    verify_construction_run(output / "deterministic_publication")
    if planned["graph"] != deterministic["graph"]:
        raise ValueError("Same-snapshot graph parity failed.")
    for key in ("results", "citations"):
        if planned["question"][key] != deterministic["question"][key]:
            raise ValueError("Same-snapshot answer parity failed: " + key)
    return {"status": "same_snapshot_publication_parity_passed", "graph_sha256": digest(planned["graph"]),
        "results_sha256": digest(planned["question"]["results"]), "citations_sha256": digest(planned["question"]["citations"]),
        "new_source_calls": 0, "recorded_source_exchanges_per_replay": len(source["requests"]),
        "assay_attachment_replayed": False, "biological_accuracy_measured": False}


def _write_report(path, result):
    rows = "".join("<tr><td>" + escape(row["case_id"]) + "</td><td>" + escape(row["raw_status"]) +
        "</td><td>" + str(row["raw_intent_match"]) + "</td><td>" + str(row["explicit_selection_agreement"]) +
        "</td><td>" + escape(row["guarded_status"]) + "</td></tr>" for row in result["rows"])
    path.write_text("<!doctype html><html lang='en'><meta charset='utf-8'><title>Guided construction assessment</title>"
        "<style>body{font:16px/1.5 system-ui;max-width:1100px;margin:2rem auto;padding:1rem}td,th{border:1px solid #ccc;padding:.5rem}table{border-collapse:collapse}pre{white-space:pre-wrap}</style>"
        "<h1>Guided construction assessment</h1><p>" + escape(result["status"]) + "</p><p>" + escape(LIMITATION) + "</p>"
        "<p>The model prompt is unchanged. Explicit choices are checked after inference; no output is repaired. "
        "Agreement with form choices does not establish compliance with unsupported free-text conditions. "
        "An interrupted request may have been billed without a complete trace; no resumption is allowed.</p><p>" +
        escape(existing.RUNTIME_NOTE) + "</p><pre>" +
        escape(json.dumps(result["summary"], indent=2)) + "</pre><table><tr><th>Case</th><th>Raw status</th>"
        "<th>Raw intent match</th><th>Selection agreement</th><th>Guarded status</th></tr>" + rows + "</table><pre>" +
        escape(json.dumps(result["real_cohort_parity"], indent=2)) + "</pre><p><a href='comparison.json'>Results</a> · "
        "<a href='../cases.json'>Declared tasks and choices</a> · <a href='../manifest.json'>Freeze</a></p></html>", encoding="utf-8")


def run(experiment, *, planner=None, runtime_observation=None):
    planner = planner or _planner()
    experiment = Path(experiment)
    manifest, cases, source = validate_freeze(experiment, planner=planner)
    runtime = validate_runtime(runtime_observation, manifest)
    output = experiment / "results"
    if output.exists() or output.is_symlink():
        raise ValueError("This assessment has a run; preserve it without resuming or replacing it.")
    manifest_sha = sha(experiment / "manifest.json")
    output.mkdir()
    rows, raw_traces, pending, error = [], [], None, None
    status, parity = "completed", {"status": "not_reached", "new_source_calls": 0}
    runtime_sha = None
    if runtime is not None:
        runtime_sha = sha(runtime_observation)
        (output / "runtime_observation.json").write_bytes(Path(runtime_observation).read_bytes())
        for name in runtime["evidence_files"]:
            destination = output / "runtime_evidence" / name
            destination.parent.mkdir(parents=True, exist_ok=True)
            destination.write_bytes((Path(runtime_observation).parent / name).read_bytes())
        validate_runtime(output / "runtime_observation.json", manifest, evidence_base=output / "runtime_evidence")
    try:
        for index, case in enumerate(cases, 1):
            validate_freeze(experiment, planner=planner)
            if sha(experiment / "manifest.json") != manifest_sha:
                raise ValueError("Manifest changed during execution.")
            if runtime is not None:
                validate_runtime(runtime_observation, manifest)
                if sha(runtime_observation) != runtime_sha:
                    raise ValueError("Runtime observation changed during execution.")
            pending = case["id"]
            write_json(output / "progress.json", {"status": "running", "completed_cases": len(rows), "pending_case": pending})
            raw = planner.plan(deepcopy(case["scope"]))
            # Preserve a returned record even if its binding subsequently fails.
            write_json(output / "returned" / f"{index:02d}.json", raw)
            wire = existing._strict_json(experiment / f"requests/{index:02d}.json")
            _trace_binding(raw, case, wire, manifest["model_configuration"])
            guarded = guard_construction_trace(raw, deepcopy(case["selection"]))
            save_construction_plan(raw, output / "raw_traces" / f"{index:02d}.json")
            save_construction_plan(guarded, output / "guarded_traces" / f"{index:02d}.json")
            rows.append(assess(case, raw, guarded))
            raw_traces.append(raw)
            pending = None
            if case["category"] == "saved_real_cohort":
                parity = _parity(source, guarded, output)
        validate_freeze(experiment, planner=planner)
        if sha(experiment / "manifest.json") != manifest_sha:
            raise ValueError("Manifest changed during execution.")
        if runtime is not None:
            validate_runtime(runtime_observation, manifest)
            validate_runtime(output / "runtime_observation.json", manifest, evidence_base=output / "runtime_evidence")
            if sha(runtime_observation) != runtime_sha or sha(output / "runtime_observation.json") != runtime_sha:
                raise ValueError("Runtime observation changed during execution.")
    except BaseException as exc:
        status, error = "interrupted", type(exc).__name__
        raise
    finally:
        files = {path.relative_to(output).as_posix(): sha(path) for path in sorted(output.rglob("*"))
                 if path.is_file() and path.name != "progress.json"}
        result = existing._seal({"format": FORMAT + ".results", "status": status, "created_at": utcnow(),
            "manifest_sha256": manifest_sha, "model_configuration": manifest["model_configuration"],
            "rows": rows, "summary": summarize(rows, raw_traces), "pending_case": pending,
            "interruption_type": error, "real_cohort_parity": parity, "files": files,
            "runtime_observation_sha256": runtime_sha, "interpretation": LIMITATION})
        write_json(output / "comparison.json", result)
        _write_report(output / "report.html", result)
        write_json(output / "progress.json", {"status": status, "completed_cases": len(rows), "pending_case": pending})
    return result


def score(experiment, *, planner=None):
    """Re-derive every score offline; never invoke the model or change artifacts."""
    experiment = Path(experiment)
    manifest, cases, source = validate_freeze(experiment, planner=planner)
    output = experiment / "results"
    result = existing._strict_json(output / "comparison.json")
    if (result != existing._seal(result) or result.get("format") != FORMAT + ".results"
            or result.get("manifest_sha256") != sha(experiment / "manifest.json")
            or result.get("interpretation") != LIMITATION
            or result.get("model_configuration") != manifest["model_configuration"]):
        raise ValueError("Result seal or freeze binding changed.")
    if result.get("status") not in {"completed", "interrupted"} or len(result["rows"]) > 8:
        raise ValueError("Invalid assessment completion state.")
    for name, checksum in result["files"].items():
        relative = Path(name)
        if relative.is_absolute() or ".." in relative.parts or (output / relative).is_symlink() or sha(output / relative) != checksum:
            raise ValueError("Result artifact changed: " + name)
    if manifest["model_configuration"]["planner_kind"] != "injected_test_model":
        validate_runtime(output / "runtime_observation.json", manifest, evidence_base=output / "runtime_evidence")
        if sha(output / "runtime_observation.json") != result["runtime_observation_sha256"]:
            raise ValueError("Saved live runtime receipt changed.")
    elif result.get("runtime_observation_sha256") is not None:
        raise ValueError("Injected tests cannot claim a live runtime receipt.")
    rows, traces = [], []
    for index, declared in enumerate(result["rows"], 1):
        case = cases[index - 1]
        raw = existing._strict_json(output / f"raw_traces/{index:02d}.json")
        guarded = existing._strict_json(output / f"guarded_traces/{index:02d}.json")
        _trace_binding(raw, case, existing._strict_json(experiment / f"requests/{index:02d}.json"), manifest["model_configuration"])
        row = assess(case, raw, guarded)
        if row != declared:
            raise ValueError("Recorded case score differs from its preserved traces.")
        rows.append(row)
        traces.append(raw)
    if summarize(rows, traces) != result["summary"]:
        raise ValueError("Recorded totals differ from preserved traces.")
    if result["status"] == "completed" and len(rows) != 8:
        raise ValueError("A complete result must preserve all eight outcomes.")
    parity = result["real_cohort_parity"]
    if result["status"] == "completed":
        expected_parity = ("same_snapshot_publication_parity_passed" if rows[-1]["execution_authorized_by_evaluation"]
                           else "not_executed_nonmatching_real_plan")
        if parity["status"] != expected_parity:
            raise ValueError("Completed real-cohort publication outcome differs from its plan.")
    if parity["status"] == "same_snapshot_publication_parity_passed":
        if not rows or not rows[-1]["execution_authorized_by_evaluation"]:
            raise ValueError("Publication lacks a matching real-cohort plan.")
        for name in ("planned_publication", "deterministic_publication"):
            verify_construction_run(output / name)
        planned = existing._strict_json(output / "planned_publication/graph.json")
        deterministic = existing._strict_json(output / "deterministic_publication/graph.json")
        if planned != deterministic or digest(planned) != parity["graph_sha256"]:
            raise ValueError("Saved publication graph parity changed.")
        for name in ("planned_publication", "deterministic_publication"):
            if existing._strict_json(output / name / "snapshot.json") != source:
                raise ValueError("Publication used a different source snapshot.")
        for key in ("results", "citations"):
            a = existing._strict_json(output / "planned_publication/question.json")[key]
            b = existing._strict_json(output / "deterministic_publication/question.json")[key]
            if a != b or digest(a) != parity[key + "_sha256"]:
                raise ValueError("Saved answer parity changed.")
    return result


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    prep = commands.add_parser("prepare")
    prep.add_argument("--out", type=Path, required=True)
    prep.add_argument("--source-snapshot", type=Path, required=True)
    execute = commands.add_parser("run")
    execute.add_argument("--experiment", type=Path, required=True)
    execute.add_argument("--runtime-observation", type=Path, required=True)
    verify = commands.add_parser("score")
    verify.add_argument("--experiment", type=Path, required=True)
    args = parser.parse_args(argv)
    if args.command == "prepare":
        result = prepare(args.out, args.source_snapshot)
    elif args.command == "run":
        result = run(args.experiment, runtime_observation=args.runtime_observation)
    else:
        result = score(args.experiment)
    print(json.dumps(result.get("summary", {"status": result["status"], "maximum_model_calls": result.get("maximum_model_calls")}), indent=2))


if __name__ == "__main__":
    main()
