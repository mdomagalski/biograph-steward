#!/usr/bin/env python3
"""Freeze and run the bounded construction planner's twelve development cases.

No Pharos retrieval or biological scoring occurs. Preparation is local. Running
uses one configured model call per case and preserves each completed trace before
the next call. A run cannot be resumed or silently replaced.
"""
from __future__ import annotations

import argparse
from html import escape
import json
from pathlib import Path
import platform
import statistics
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from biograph_steward.client import digest, utcnow, write_json
from biograph_steward.file_utils import new_output, sha
from biograph_steward.construction_planning import (
    POLICY, configured_construction_planner, compare_construction_cases,
    fixed_construction_cases, save_construction_plan, verify_construction_plan_trace,
)

FORMAT = "biograph-steward.construction-planner-development.v1"
BOUND_FILES = (
    "biograph_steward/construction_planning.py", "biograph_steward/model_transport.py",
    "biograph_steward/codex_transport.py", "biograph_steward/construction.py",
    "biograph_steward/client.py", "biograph_steward/file_utils.py",
    "scripts/evaluate_construction_planner.py", "compose.brev-local-model.yaml",
)
LIMITATION = ("Development agreement with explicit deterministic requests; not a held-out "
              "scientific benchmark, biological accuracy, graph improvement, or source retrieval evaluation.")


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


def implementation_hashes():
    return {name: sha(ROOT / name) for name in BOUND_FILES}


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


def prepare(out, *, planner=None, provider=None, model=None):
    planner = planner or configured_construction_planner(provider=provider, model=model)
    config = model_configuration(planner)
    cases = fixed_construction_cases()
    implementation = implementation_hashes()
    out = new_output(out)
    write_json(out / "cases.json", cases)
    manifest = _seal({"format": FORMAT, "status": "prepared", "created_at": utcnow(),
        "policy": POLICY, "cases_sha256": digest(cases), "cases_file_sha256": sha(out / "cases.json"),
        "case_count": len(cases), "implementation_sha256": implementation,
        "model_configuration": config, "expected_runtime": expected_runtime(config),
        "local_python": platform.python_version(),
        "model_calls_during_preparation": 0, "source_calls": 0,
        "reference_exposure": "Fixed development cases; expected requests excluded from all model payloads.",
        "retry_policy": "One call per case; no retries, repair, fallback, or resumption.",
        "interpretation": LIMITATION})
    write_json(out / "manifest.json", manifest)
    validate_freeze(out, planner=planner)
    return manifest


def validate_freeze(experiment, *, planner=None):
    experiment = Path(experiment)
    if experiment.is_symlink() or not experiment.is_dir():
        raise ValueError("Comparison must be an ordinary prepared directory.")
    manifest = _strict_json(experiment / "manifest.json")
    if (not isinstance(manifest, dict) or manifest != _seal(manifest)
            or manifest.get("format") != FORMAT or manifest.get("status") != "prepared"
            or manifest.get("policy") != POLICY):
        raise ValueError("Invalid or changed comparison manifest.")
    if manifest.get("implementation_sha256") != implementation_hashes():
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
            "unsupported_requests_constructed": sum(r["unsafe_construct_on_abstention"] for r in rows),
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
        explain = (trace.get("validated_plan") or {}).get("reason", trace.get("error", ""))
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
    html += f"<p><strong>{summary['scope_matches']} scope matches</strong>; {summary['unsupported_requests_constructed']} unsupported requests proposed for construction; {summary['invalid_plans']} invalid plans; {summary['planner_errors']} model errors.</p>"
    html += "<p>One model call per case; no retries, repairs, source retrieval or graph writes. The comparator is the explicit deterministic request shown below. Expectations were not sent to the model.</p>"
    html += "<h2>Usage and latency</h2><pre>" + escape(json.dumps(summary, indent=2)) + "</pre>"
    html += "<h2>Case decisions</h2><table><thead><tr><th>Case</th><th>Agreement</th><th>Status</th><th>Expected request</th><th>Selected request and explanation</th></tr></thead><tbody>" + "".join(rows) + "</tbody></table>"
    if result.get("pending_case"):
        html += "<p class='notice'>Interrupted while handling " + escape(result["pending_case"]) + ". An in-flight call may have been billed without a complete trace. No automatic resumption is permitted.</p>"
    html += "<p><a href='comparison.json'>Machine-readable results</a> · <a href='../manifest.json'>Frozen manifest</a> · <a href='../cases.json'>Fixed development cases</a></p></html>"
    path.write_text(html, encoding="utf-8")


def run(experiment, *, planner=None):
    experiment = Path(experiment)
    manifest, cases = validate_freeze(experiment)
    manifest_file_sha256 = sha(experiment / "manifest.json")
    if (experiment / "results").exists() or (experiment / "results").is_symlink():
        raise ValueError("This comparison already has a run. Preserve it; do not resume or replace results.")
    config = manifest["model_configuration"]
    planner = planner or configured_construction_planner(provider=config["provider"], model=config["model"])
    validate_freeze(experiment, planner=planner)
    output = experiment / "results"
    output.mkdir()
    (output / "traces").mkdir()
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
            pending = case["id"]
            write_json(output / "progress.json", {"status": "running", "completed_cases": len(rows), "pending_case": pending})
            trace = planner.plan(scope)
            actual = verify_construction_plan_trace(trace)
            save_construction_plan(trace, output / "traces" / f"{index + 1:02d}_{case['id']}.json")
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
        compare_construction_cases(Recorder(), cases)
        validate_freeze(experiment, planner=planner)
        if sha(experiment / "manifest.json") != manifest_file_sha256:
            raise ValueError("Frozen manifest changed during execution.")
    except BaseException as exc:
        status, error = "interrupted", type(exc).__name__
        raise
    finally:
        result = {"format": FORMAT + ".results", "created_at": utcnow(), "status": status,
                  "manifest_sha256": manifest_file_sha256,
                  "cases_sha256": manifest["cases_sha256"], "model_configuration": config,
                  "expected_runtime": manifest["expected_runtime"], "planned_cases": len(cases),
                  "summary": _summarize(rows), "rows": rows, "pending_case": pending,
                  "interruption_type": error, "interpretation": LIMITATION,
                  "files": {p.relative_to(output).as_posix(): sha(p) for p in sorted((output / "traces").glob("*.json"))}}
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
    execute = commands.add_parser("run", help="Run the frozen comparison once; requires the configured model.")
    execute.add_argument("--experiment", type=Path, required=True)
    args = parser.parse_args(argv)
    if args.command == "prepare":
        result = prepare(args.out, provider=args.provider, model=args.model)
        print(json.dumps({"status": result["status"], "cases": result["case_count"], "output": str(args.out)}))
    else:
        result = run(args.experiment)
        print(json.dumps({"status": result["status"], "summary": result["summary"],
                          "report": str(args.experiment / "results/report.html")}))


if __name__ == "__main__":
    main()
