#!/usr/bin/env python3
"""Freeze and run the bounded construction planner's twelve development cases.

No Pharos retrieval or biological scoring occurs. Preparation is local. Running
uses one configured model call per case and preserves each completed trace before
the next call. A run cannot be resumed or silently replaced.
"""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
from html import escape
import json
from pathlib import Path
import platform
import re
import statistics
import sys
from urllib.parse import urlparse

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from biograph_steward.client import digest, utcnow, write_json
from biograph_steward.file_utils import new_output, sha
from biograph_steward.construction_planning import (
    POLICY, configured_construction_planner,
    fixed_construction_cases, save_construction_plan, verify_construction_plan_trace,
)

FORMAT = "biograph-steward.construction-planner-development.v1"
TOOL_FORMAT = "biograph-steward.construction-tool-development.v1"
TOOL_V2_FORMAT = "biograph-steward.construction-tool-development.v2"
TOOL_INTERFACES = ("nemotron_tool_v1", "nemotron_tool_v2")
INTERFACES = ("json_v3", *TOOL_INTERFACES)
BOUND_FILES = (
    "biograph_steward/construction_planning.py", "biograph_steward/model_transport.py",
    "biograph_steward/codex_transport.py", "biograph_steward/construction.py",
    "biograph_steward/client.py", "biograph_steward/file_utils.py",
    "scripts/evaluate_construction_planner.py", "compose.brev-local-model.yaml",
)
LIMITATION = ("Development agreement with explicit deterministic requests; not a held-out "
              "scientific benchmark, biological accuracy, graph improvement, or source retrieval evaluation.")
RUNTIME_NOTE = ("Externally supplied runtime observation and evidence hashes are checked and preserved. "
                "The caller must verify the current server; this runner cannot attest live engine state.")


def runtime_prerequisite(config):
    """Reuse the exact configuration exercised by the isolated V1 diagnostic."""
    model = "nvidia/Llama-3.1-Nemotron-Nano-8B-v1"
    revision = "54641c1611fcff44fa4865626462445e0a153fc7"
    return {
        "format": "biograph-steward.nano-v1-structural-runtime.v1",
        "observation_kind": "live_runtime_observation", "engine": "V1",
        "vllm_version": "0.8.5", "xgrammar_version": "0.1.18",
        "image": "vllm/vllm-openai:v0.8.5@sha256:6cf9808ca8810fc6c3fd0451c2e7784fb224590d81f7db338e7eaf3c02a33d33",
        "model": model, "model_revision": revision, "tokenizer_revision": revision,
        "dtype": "bfloat16", "health_http_status": 200, "served_model_ids": [model],
        "fallback_used": False, "download_policy": "offline_cached_only",
        "offline_environment_verified": True, "cached_weights_only": True,
        "request_endpoint": config["endpoint"], "server_endpoint": "http://127.0.0.1:8001",
        "effective_flags": {"max_model_len": 16384, "max_num_seqs": 1,
            "gpu_memory_utilization": 0.75, "enforce_eager": True,
            "enable_chunked_prefill": True, "max_num_batched_tokens": 2048,
            "enable_prefix_caching": False, "guided_decoding_backend": "xgrammar",
            "generation_config": "vllm"},
    }


def _interface(planner):
    return getattr(planner, "evaluation_interface", "json_v3")


def _planner(interface, provider=None, model=None):
    if interface == "json_v3":
        return configured_construction_planner(provider=provider, model=model)
    if interface == "nemotron_tool_v1":
        from biograph_steward.nemotron_construction import NemotronConstructionPlanner
        from biograph_steward.model_transport import JSONModelClient
        return NemotronConstructionPlanner(client=JSONModelClient(
            role="planner", provider=provider or "api", model=model))
    if interface == "nemotron_tool_v2":
        from biograph_steward.nemotron_construction_v2 import NemotronConstructionPlannerV2
        from biograph_steward.model_transport import JSONModelClient
        return NemotronConstructionPlannerV2(client=JSONModelClient(
            role="planner", provider=provider or "api", model=model))
    raise ValueError("Unknown comparison interface.")


def _policy(interface):
    if interface == "json_v3":
        return POLICY
    if interface == "nemotron_tool_v1":
        from biograph_steward.nemotron_construction import POLICY as tool_policy
        return tool_policy
    if interface == "nemotron_tool_v2":
        from biograph_steward.nemotron_construction_v2 import POLICY as tool_policy
        return tool_policy
    raise ValueError("Unknown comparison interface.")


def _verify_trace(trace, interface):
    if interface == "nemotron_tool_v2":
        from biograph_steward.nemotron_construction_v2 import verify_nemotron_construction_trace_v2
        return verify_nemotron_construction_trace_v2(trace)
    if interface == "nemotron_tool_v1":
        from biograph_steward.nemotron_construction import verify_nemotron_construction_trace
        return verify_nemotron_construction_trace(trace)
    return verify_construction_plan_trace(trace)


def _save_trace(trace, path, interface):
    if interface == "nemotron_tool_v2":
        from biograph_steward.nemotron_construction_v2 import save_nemotron_construction_trace_v2
        return save_nemotron_construction_trace_v2(trace, path)
    if interface == "nemotron_tool_v1":
        from biograph_steward.nemotron_construction import save_nemotron_construction_trace
        return save_nemotron_construction_trace(trace, path)
    return save_construction_plan(trace, path)


def _format(interface):
    return {"json_v3": FORMAT, "nemotron_tool_v1": TOOL_FORMAT,
            "nemotron_tool_v2": TOOL_V2_FORMAT}[interface]


def _seal(value):
    value = {key: item for key, item in value.items() if key != "content_sha256"}
    return {**value, "content_sha256": digest(value)}


def _strict_json(path):
    path = Path(path)
    if path.is_symlink() or not path.is_file():
        raise ValueError("Comparison inputs must be ordinary files without symlinks.")
    def pairs(items):
        result = {}
        for key, value in items:
            if key in result:
                raise ValueError("Duplicate JSON key: " + key)
            result[key] = value
        return result
    def constant(value):
        raise ValueError("Nonfinite JSON value: " + value)
    return json.loads(path.read_text(encoding="utf-8"), object_pairs_hook=pairs, parse_constant=constant)


def implementation_hashes(interface="json_v3"):
    names = BOUND_FILES
    if interface in TOOL_INTERFACES:
        names += ("biograph_steward/nemotron_construction.py", "scripts/probe_nemotron_tool_interface.py")
    if interface == "nemotron_tool_v2":
        names += ("biograph_steward/nemotron_construction_v2.py", "biograph_steward/graph.py",
                  "biograph_steward/retrieval.py", "biograph_steward/__init__.py")
    return {name: sha(ROOT / name) for name in names}


def model_configuration(planner):
    """Explicit allowlist only; never serialize transport state or credentials."""
    client = getattr(planner, "client", planner)
    return {"provider": getattr(client, "provider", "codex"),
            "planner_kind": client.kind, "model": client.model,
            "endpoint": client.endpoint, "api": client.api,
            "prompt_profile": getattr(client, "prompt_profile", None),
            "max_output_tokens": getattr(client, "max_output_tokens", None),
            "timeout_seconds": getattr(client, "timeout", 90),
            "cli_version": getattr(client, "cli_version", None)}


def expected_runtime(config):
    reference = {"verification_status": "Not attested by this runner; check the server separately.",
                 "configuration_reference": "docs/LOCAL_MODEL.md"}
    if config["model"] == "nvidia/Llama-3.1-Nemotron-Nano-8B-v1":
        reference.update(model_revision="54641c1611fcff44fa4865626462445e0a153fc7",
                         serving_implementation="vLLM", serving_version="0.8.5",
                         image_digest="sha256:6cf9808ca8810fc6c3fd0451c2e7784fb224590d81f7db338e7eaf3c02a33d33")
    else:
        reference["serving_implementation"] = "Not declared for this configured model."
    return reference


def validate_runtime(path, manifest):
    """Bind a fresh external receipt; never infer V1 from a request or response.

    Adapted from the already-tested two-request V1 probe. Freshness rejects old
    diagnostic receipts, but does not establish that a server remains unchanged.
    """
    if path is None:
        raise ValueError("nemotron_tool_v2 requires --runtime-observation for the current V1 server.")
    path = Path(path)
    observation = _strict_json(path)
    config = manifest["model_configuration"]
    endpoint = urlparse(config["endpoint"])
    prerequisite = runtime_prerequisite(config)
    if (endpoint.scheme not in {"http", "https"}
            or endpoint.hostname not in {"localhost", "127.0.0.1", "::1"}
            or endpoint.username is not None or endpoint.password is not None
            or endpoint.query or endpoint.fragment or endpoint.path != "/v1/chat/completions"
            or config["model"] != prerequisite["model"]
            or not isinstance(observation, dict)
            or any(observation.get(key) != value for key, value in prerequisite.items())):
        raise ValueError("Runtime observation differs from the pinned V1 configuration or frozen loopback endpoint.")
    try:
        observed = datetime.fromisoformat(observation["observed_at"])
        prepared = datetime.fromisoformat(manifest["created_at"])
        if (observed.tzinfo is None or prepared.tzinfo is None
                or observed < prepared or observed > datetime.now(timezone.utc)):
            raise ValueError
    except (KeyError, TypeError, ValueError) as exc:
        raise ValueError("Runtime observation must be recorded after this comparison was frozen and cannot be future-dated.") from exc
    if (not isinstance(observation.get("image_id"), str)
            or re.fullmatch(r"sha256:[0-9a-f]{64}", observation["image_id"]) is None
            or not isinstance(observation.get("container_id"), str)
            or re.fullmatch(r"[0-9a-f]{64}", observation["container_id"]) is None
            or not isinstance(observation.get("evidence_files"), dict) or not observation["evidence_files"]):
        raise ValueError("Runtime observation requires image/container IDs and hashed evidence files.")
    for name, checksum in observation["evidence_files"].items():
        if not isinstance(name, str) or not isinstance(checksum, str):
            raise ValueError("Invalid runtime evidence file or hash.")
        relative = Path(name)
        evidence = path.parent / relative
        if (relative.is_absolute() or ".." in relative.parts
                or any((path.parent / Path(*relative.parts[:i])).is_symlink()
                       for i in range(1, len(relative.parts) + 1))
                or not evidence.is_file() or sha(evidence) != checksum):
            raise ValueError("Invalid runtime evidence file or hash.")
    return observation


def prepare(out, *, planner=None, provider=None, model=None, interface="json_v3"):
    planner = planner or _planner(interface, provider=provider, model=model)
    interface = _interface(planner)
    if interface not in INTERFACES:
        raise ValueError("Unknown comparison interface.")
    config = model_configuration(planner)
    cases = fixed_construction_cases()
    implementation = implementation_hashes(interface)
    out = new_output(out)
    write_json(out / "cases.json", cases)
    requests = {}
    if interface in TOOL_INTERFACES:
        (out / "requests").mkdir()
        for i, case in enumerate(cases, 1):
            name = f"requests/{i:02d}_{case['id']}.json"
            write_json(out / name, planner.request(case["scope"]))
            requests[name] = sha(out / name)
        for name in implementation:
            destination = out / "implementation" / name
            destination.parent.mkdir(parents=True, exist_ok=True)
            destination.write_bytes((ROOT / name).read_bytes())
    manifest = {"format": _format(interface),
        "interface": interface, "status": "prepared", "created_at": utcnow(),
        "policy": _policy(interface), "cases_sha256": digest(cases), "cases_file_sha256": sha(out / "cases.json"),
        "case_count": len(cases), "implementation_sha256": implementation,
        "model_configuration": config, "expected_runtime": expected_runtime(config), "request_files": requests,
        "local_python": platform.python_version(),
        "model_calls_during_preparation": 0, "source_calls": 0,
        "reference_exposure": "Fixed development cases; expected requests excluded from all model payloads.",
        "retry_policy": "One call per case; no retries, repair, fallback, or resumption.",
        "no_call_scoring": "Plain text without a call is reported separately; it does not establish semantic abstention or task success.",
        "interpretation": LIMITATION}
    if interface == "nemotron_tool_v2":
        manifest["runtime_prerequisite"] = runtime_prerequisite(config)
        manifest["runtime_verification"] = RUNTIME_NOTE
        manifest["exact_selection"] = "Absent in all fixed cases; never inferred from expected requests."
    manifest = _seal(manifest)
    write_json(out / "manifest.json", manifest)
    validate_freeze(out, planner=planner)
    return manifest


def validate_freeze(experiment, *, planner=None):
    experiment = Path(experiment)
    if experiment.is_symlink() or not experiment.is_dir():
        raise ValueError("Comparison must be an ordinary prepared directory.")
    manifest = _strict_json(experiment / "manifest.json")
    interface = manifest.get("interface", "json_v3") if isinstance(manifest, dict) else None
    if (not isinstance(manifest, dict) or manifest != _seal(manifest)
            or interface not in INTERFACES
            or manifest.get("format") != _format(interface)
            or manifest.get("status") != "prepared" or manifest.get("policy") != _policy(interface)):
        raise ValueError("Invalid or changed comparison manifest.")
    if manifest.get("implementation_sha256") != implementation_hashes(interface):
        raise ValueError("Frozen implementation differs. Preserve this freeze and prepare a new comparison.")
    cases = _strict_json(experiment / "cases.json")
    if (manifest.get("cases_file_sha256") != sha(experiment / "cases.json")
            or manifest.get("cases_sha256") != digest(cases)
            or cases != fixed_construction_cases() or manifest.get("case_count") != 12):
        raise ValueError("Frozen cases differ from the twelve predeclared development requests.")
    if (manifest.get("source_calls") != 0 or manifest.get("model_calls_during_preparation") != 0
            or manifest.get("interpretation") != LIMITATION):
        raise ValueError("The prepared comparison cannot claim source calls or scientific evaluation.")
    if manifest.get("expected_runtime") != expected_runtime(manifest["model_configuration"]):
        raise ValueError("Expected runtime differs from this runner's declared configuration reference.")
    if planner is not None and manifest.get("model_configuration") != model_configuration(planner):
        raise ValueError("Model configuration differs from the frozen comparison; no model was called.")
    if planner is not None and _interface(planner) != interface:
        raise ValueError("Planner interface differs from the frozen comparison.")
    if interface == "nemotron_tool_v2" and (
            manifest.get("runtime_prerequisite") != runtime_prerequisite(manifest["model_configuration"])
            or manifest.get("runtime_verification") != RUNTIME_NOTE
            or manifest.get("exact_selection") != "Absent in all fixed cases; never inferred from expected requests."):
        raise ValueError("V2 runtime or explicit-selection comparison requirements differ.")
    if interface in TOOL_INTERFACES:
        config = manifest["model_configuration"]
        planner = planner or _planner(interface, config["provider"], config["model"])
        if model_configuration(planner) != config:
            raise ValueError("Model configuration differs from the frozen comparison.")
        expected = {f"requests/{i:02d}_{case['id']}.json": planner.request(case["scope"])
                    for i, case in enumerate(cases, 1)}
        if set(manifest.get("request_files", {})) != set(expected):
            raise ValueError("Frozen request inventory differs.")
        for name, payload in expected.items():
            if (_strict_json(experiment / name) != payload
                    or sha(experiment / name) != manifest["request_files"][name]):
                raise ValueError("Frozen request changed: " + name)
        for name, checksum in manifest["implementation_sha256"].items():
            path = experiment / "implementation" / name
            if path.is_symlink() or not path.is_file() or sha(path) != checksum:
                raise ValueError("Frozen implementation copy changed: " + name)
    return manifest, cases


def _summarize(rows):
    traces = [row["trace"] for row in rows]
    latencies = [t["latency_ms"] for t in traces if isinstance(t.get("latency_ms"), (int, float))]
    token_totals = {}
    for trace in traces:
        for key, value in (trace.get("usage") or {}).items():
            if type(value) is int:
                token_totals[key] = token_totals.get(key, 0) + value
    return {"completed_cases": len(rows), "scope_matches": sum(r["scope_match"] for r in rows),
            "supported_cases": sum(r["expected_request"] is not None for r in rows),
            "supported_exact_matches": sum(r["scope_match"] and r["expected_request"] is not None for r in rows),
            "unsupported_cases": sum(r["expected_request"] is None for r in rows),
            "unsupported_explicit_abstentions": sum(r["scope_match"] and r["expected_request"] is None for r in rows),
            "unsupported_no_call_text": sum(r["expected_request"] is None and r["trace"]["status"] == "no_call_text" for r in rows),
            "supported_no_call_text": sum(r["expected_request"] is not None and r["trace"]["status"] == "no_call_text" for r in rows),
            "unsupported_requests_constructed": sum(r["unsafe_construct_on_abstention"] for r in rows),
            "unsupported_parsed_call_attempts": sum(r["expected_request"] is None and
                (r["trace"].get("proposed_plan") or {}).get("action") == "construct" for r in rows),
            "invalid_plans": sum(t["status"] == "invalid_plan" for t in traces),
            "planner_errors": sum(t["status"] == "planner_error" for t in traces),
            "recorded_model_calls": sum(t.get("model_calls", 0) for t in traces),
            "returned_token_totals": token_totals, "usage_available_cases": sum(t.get("usage") is not None for t in traces),
            "total_latency_ms": round(sum(latencies), 3),
            "median_latency_ms": round(statistics.median(latencies), 3) if latencies else None,
            "cost": None, "cost_note": "No provider prices or GPU billing allocation assumed; returned usage and latency recorded.",
            "source_calls": 0, "biological_accuracy_measured": False}


def _write_report(path, result):
    summary = result["summary"]
    rows = []
    for row in result["rows"]:
        trace = row["trace"]
        proposed = trace.get("construction_request")
        expected = row["expected_request"]
        explain = trace.get("final_text") or (trace.get("validated_plan") or {}).get("reason", trace.get("error", ""))
        rows.append("<tr><td>" + escape(row["case_id"]) + "</td><td>"
                    + ("Match" if row["scope_match"] else "Mismatch") + "</td><td>"
                    + escape(trace["status"]) + "</td><td><pre>"
                    + escape(json.dumps(expected, indent=2)) + "</pre></td><td><pre>"
                    + escape(json.dumps(proposed, indent=2)) + "</pre>" + escape(explain) + "</td></tr>")
    config = result["model_configuration"]
    html = """<!doctype html><html lang="en"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>Construction planner development comparison</title><style>
body{font:16px/1.5 system-ui,sans-serif;max-width:1200px;margin:2rem auto;padding:0 1rem;color:#172b3a}
h1{line-height:1.2}.notice{background:#fff5d8;padding:1rem;border-left:4px solid #bd870e}
table{border-collapse:collapse;width:100%;margin:1.5rem 0}td,th{border:1px solid #cad3d8;padding:.6rem;text-align:left;vertical-align:top}
pre{white-space:pre-wrap;overflow-wrap:anywhere;font-size:12px}code{overflow-wrap:anywhere}a{color:#075f94}
</style><h1>Construction planner development comparison</h1>"""
    html += f"<p><strong>Status: {escape(result['status'])}</strong>. {summary['completed_cases']} / {result['planned_cases']} cases completed.</p>"
    html += f"<p class='notice'>{escape(LIMITATION)} Schema-valid output can still misunderstand a question.</p>"
    html += f"<p>Model: <code>{escape(config['model'])}</code>; provider kind: {escape(config['planner_kind'])}. Expected runtime is recorded in the manifest and is not independently attested here.</p>"
    if result.get("runtime_observation_sha256"):
        html += "<p>" + escape(RUNTIME_NOTE) + " <a href='runtime_observation.json'>Recorded runtime observation</a>.</p>"
    html += f"<p><strong>{summary['supported_exact_matches']} / {summary['supported_cases']} supported requests matched exactly</strong>; {summary['unsupported_requests_constructed']} unsupported requests accepted as construction plans; {summary['invalid_plans']} invalid plans; {summary['planner_errors']} model errors.</p>"
    html += "<p>One model call per case; no retries, repairs, source retrieval or graph writes. The comparator is the explicit deterministic request shown below. Expectations were not sent to the model.</p>"
    html += "<p>Supported exact requests, explicit structured abstentions, plain-text no-call responses and invalid outputs are reported separately. A no-call response may decline, ask a question or give an unsupported answer; absence of a call alone is not semantic task success.</p>"
    html += "<h2>Usage and latency</h2><pre>" + escape(json.dumps(summary, indent=2)) + "</pre>"
    html += "<h2>Case decisions</h2><table><thead><tr><th>Case</th><th>Agreement</th><th>Status</th><th>Expected request</th><th>Selected request and explanation</th></tr></thead><tbody>" + "".join(rows) + "</tbody></table>"
    if result.get("pending_case"):
        html += "<p class='notice'>Interrupted while handling " + escape(result["pending_case"]) + ". An in-flight call may have been billed without a complete trace. No automatic resumption is permitted.</p>"
    html += "<p><a href='comparison.json'>Machine-readable results</a> · <a href='../manifest.json'>Frozen manifest</a> · <a href='../cases.json'>Fixed development cases</a></p></html>"
    path.write_text(html, encoding="utf-8")


def run(experiment, *, planner=None, runtime_observation=None):
    experiment = Path(experiment)
    manifest, cases = validate_freeze(experiment, planner=planner)
    manifest_file_sha256 = sha(experiment / "manifest.json")
    if (experiment / "results").exists() or (experiment / "results").is_symlink():
        raise ValueError("This comparison already has a run. Preserve it; do not resume or replace results.")
    config = manifest["model_configuration"]
    interface = manifest.get("interface", "json_v3")
    planner = planner or _planner(interface, provider=config["provider"], model=config["model"])
    validate_freeze(experiment, planner=planner)
    runtime, runtime_sha = None, None
    if interface == "nemotron_tool_v2":
        runtime = validate_runtime(runtime_observation, manifest)
        runtime_sha = sha(runtime_observation)
    elif runtime_observation is not None:
        raise ValueError("A V1 structural-runtime observation is only supported for nemotron_tool_v2.")
    output = experiment / "results"
    output.mkdir()
    (output / "traces").mkdir()
    runtime_files = {}
    if runtime is not None:
        with (output / "runtime_observation.json").open("xb") as handle:
            handle.write(Path(runtime_observation).read_bytes())
        runtime_files["runtime_observation.json"] = runtime_sha
        for name, checksum in runtime["evidence_files"].items():
            source, destination = Path(runtime_observation).parent / name, output / "runtime_evidence" / name
            destination.parent.mkdir(parents=True, exist_ok=True)
            with destination.open("xb") as handle:
                handle.write(source.read_bytes())
            runtime_files[destination.relative_to(output).as_posix()] = checksum
        if any(sha(output / name) != checksum for name, checksum in runtime_files.items()):
            raise ValueError("Runtime observation changed while being copied; no model was called.")
    def verify_runtime_unchanged():
        if runtime is not None:
            validate_runtime(runtime_observation, manifest)
            if sha(runtime_observation) != runtime_sha or any(
                    sha(output / name) != checksum for name, checksum in runtime_files.items()):
                raise ValueError("Runtime observation or saved evidence changed during execution.")
    rows, pending = [], None
    class Recorder:
        def plan(self, scope):
            nonlocal pending
            index = len(rows)
            case = cases[index]
            if scope != case["scope"]:
                raise ValueError("Case order or scope changed before model execution.")
            # Recheck code/config before each call, preventing a mixed implementation run.
            validate_freeze(experiment, planner=planner)
            if sha(experiment / "manifest.json") != manifest_file_sha256:
                raise ValueError("Frozen manifest changed during execution.")
            verify_runtime_unchanged()
            pending = case["id"]
            write_json(output / "progress.json", {"status": "running", "completed_cases": len(rows), "pending_case": pending})
            trace = planner.plan(scope)
            if trace.get("scope") != scope:
                raise ValueError("Trace scope differs from the requested comparison case.")
            if interface in TOOL_INTERFACES:
                wire = _strict_json(experiment / f"requests/{index + 1:02d}_{case['id']}.json")
                if trace.get("request_sha256") != digest(wire):
                    raise ValueError("Trace request differs from the frozen wire payload.")
                bound_config = {"provider_requested": config["provider"],
                    "planner_kind": config["planner_kind"], "model_requested": config["model"],
                    "endpoint": config["endpoint"], "api": config["api"],
                    "prompt_profile": config["prompt_profile"],
                    "request_settings": {"max_output_tokens": config["max_output_tokens"],
                                         "timeout_seconds": config["timeout_seconds"]}}
                if any(trace.get(key) != value for key, value in bound_config.items()):
                    raise ValueError("Trace configuration differs from the frozen model configuration.")
            actual = _verify_trace(trace, interface)
            _save_trace(trace, output / "traces" / f"{index + 1:02d}_{case['id']}.json", interface)
            row = {"case_id": case["id"], "expected_request": case["expected_request"],
                   "expected_action": case["expected_action"], "trace": trace,
                   "scope_match": trace["status"] in {"validated", "abstained"} and actual == case["expected_request"],
                   "unsafe_construct_on_abstention": case["expected_request"] is None and actual is not None,
                   "source_calls": 0}
            rows.append(row)
            pending = None
            write_json(output / "progress.json", {"status": "running", "completed_cases": len(rows), "pending_case": None})
            return trace
    status, error = "completed", None
    try:
        recorder = Recorder()
        for case in cases:
            recorder.plan(case["scope"])
        validate_freeze(experiment, planner=planner)
        if sha(experiment / "manifest.json") != manifest_file_sha256:
            raise ValueError("Frozen manifest changed during execution.")
        verify_runtime_unchanged()
    except BaseException as exc:
        status, error = "interrupted", type(exc).__name__
        raise
    finally:
        result = {"format": manifest["format"] + ".results", "interface": interface,
                  "created_at": utcnow(), "status": status,
                  "manifest_sha256": manifest_file_sha256,
                  "cases_sha256": manifest["cases_sha256"], "model_configuration": config,
                  "expected_runtime": manifest["expected_runtime"], "planned_cases": len(cases),
                  "summary": _summarize(rows), "rows": rows, "pending_case": pending,
                  "interruption_type": error, "interpretation": LIMITATION,
                  "files": {**runtime_files, **{p.relative_to(output).as_posix(): sha(p) for p in sorted((output / "traces").glob("*.json"))}}}
        if runtime is not None:
            result.update(runtime_observation_sha256=runtime_sha, runtime_verification=RUNTIME_NOTE)
        result = _seal(result)
        write_json(output / "comparison.json", result)
        _write_report(output / "report.html", result)
        write_json(output / "progress.json", {"status": status, "completed_cases": len(rows), "pending_case": pending})
    return result


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    prep = commands.add_parser("prepare", help="Freeze fixed cases and sanitized model settings; no inference.")
    prep.add_argument("--out", type=Path, required=True)
    prep.add_argument("--provider", choices=["api", "nim", "codex"])
    prep.add_argument("--model")
    prep.add_argument("--interface", choices=INTERFACES, default="json_v3")
    execute = commands.add_parser("run", help="Run the frozen comparison once; requires the configured model.")
    execute.add_argument("--experiment", type=Path, required=True)
    execute.add_argument("--runtime-observation", type=Path,
                         help="Current V1 runtime receipt with hashed evidence; required only for nemotron_tool_v2.")
    args = parser.parse_args(argv)
    if args.command == "prepare":
        result = prepare(args.out, provider=args.provider, model=args.model, interface=args.interface)
        print(json.dumps({"status": result["status"], "cases": result["case_count"], "output": str(args.out)}))
    else:
        result = run(args.experiment, runtime_observation=args.runtime_observation)
        print(json.dumps({"status": result["status"], "summary": result["summary"],
                          "report": str(args.experiment / "results/report.html")}))


if __name__ == "__main__":
    main()
