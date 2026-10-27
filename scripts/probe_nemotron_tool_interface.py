#!/usr/bin/env python3
"""Two immutable, execution-free probes of Nano's published tool-prompt wrapper.

This deliberately does not use JSONModelClient.generate: that method constrains
and parses JSON, whereas the exact Nano tool-output parser is not verified. Only
its configuration checks and HTTP safety utilities are reused. No accuracy score,
tool parser, source access or tool execution is provided by this diagnostic.
"""
from __future__ import annotations

import argparse
from copy import deepcopy
import json
import os
from pathlib import Path
import re
import ssl
import sys
import time
from urllib.error import HTTPError, URLError
from urllib.parse import urlparse
from urllib.request import HTTPSHandler, ProxyHandler, Request, build_opener

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from biograph_steward.client import digest, utcnow, write_json
from biograph_steward.construction_planning import fixed_construction_cases
from biograph_steward.file_utils import new_output, sha
from biograph_steward.model_transport import JSONModelClient, ModelUnavailable, _NoRedirect
from scripts.evaluate_construction_planner import _seal, _strict_json, expected_runtime, model_configuration

FORMAT = "biograph-steward.nano-tool-format-probe.v1"
MODEL = "nvidia/Llama-3.1-Nemotron-Nano-8B-v1"
MODEL_CARD = "https://huggingface.co/nvidia/Llama-3.1-Nemotron-Nano-8B-v1/blob/54641c1611fcff44fa4865626462445e0a153fc7/README.md"
INTERPRETATION = ("Author-pattern adaptation and output-format observation only. Nano's exact released "
                  "tool parser is unverified; no BFCL reproduction, task-accuracy score, tool execution "
                  "or biological evaluation is claimed.")
BOUND_FILES = (
    "scripts/probe_nemotron_tool_interface.py", "scripts/evaluate_construction_planner.py",
    "biograph_steward/model_transport.py", "biograph_steward/construction_planning.py",
    "biograph_steward/construction.py", "biograph_steward/client.py",
    "biograph_steward/file_utils.py", "compose.brev-local-model.yaml",
)
REASONING_MARKUP = re.compile(r"<\s*/?\s*(?:think|thinking|analysis|reasoning)\b|\[/?THINK\]|<\|(?:analysis|channel)\|>", re.I)


def configured_client():
    # A local SSH forward to the existing model is the only intended endpoint.
    client = JSONModelClient(role="planner", provider="api")
    validate_client(client)
    return client


def validate_client(client):
    endpoint = urlparse(client.endpoint)
    if (client.model != MODEL or client.api != "nim_chat"
            or client.prompt_profile != "nemotron_nano_v1" or not client.loopback
            or endpoint.scheme not in {"http", "https"}
            or endpoint.hostname not in {"localhost", "127.0.0.1", "::1"}
            or endpoint.username is not None or endpoint.password is not None
            or endpoint.query or endpoint.fragment or endpoint.path != "/v1/chat/completions"
            or client.transport is not None):
        raise ModelUnavailable("Use the existing Nano model, nim_chat, nemotron_nano_v1 and a loopback /v1/chat/completions endpoint.")
    if not 128 <= client.max_output_tokens <= 1600 or not 1 <= client.timeout <= 120:
        raise ModelUnavailable("The format probe permits at most 1600 output tokens and 120 seconds per request.")


def cases():
    selected = {case["id"]: case for case in fixed_construction_cases()}
    return [deepcopy(selected[name]) for name in ("ppi_full", "clinical")]


def function_definition(scope):
    """Describe the existing constructor; this is not a decoding schema."""
    identities = scope["accessions"]
    return {"name": "construct_cohort", "description": (
        "Retrieve Pharos candidate interaction and/or shared pathway evidence for an exact protein cohort. "
        "This does not select treatments, prove biological truth, predict interactions, prune evidence, "
        "or restrict evidence to physical binding. Use only supplied exact accessions. Preserve the "
        "supplied cohort and default focus unless the request explicitly selects a smaller cohort or "
        "another supplied focus. Select profile ppi for interactions alone and context when pathways "
        "are requested. The executor owns retrieval limits and source access."),
        "parameters": {"type": "object", "additionalProperties": False,
            "required": ["accessions", "focus_uniprot", "profile", "relations"],
            "properties": {
                "accessions": {"type": "array", "items": {"type": "string", "enum": identities},
                               "minItems": 1, "maxItems": 25, "uniqueItems": True},
                "focus_uniprot": {"type": "string", "enum": identities},
                "profile": {"type": "string", "enum": ["ppi", "context"]},
                "relations": {"type": "array", "items": {"type": "string", "enum": ["interactions", "shared_pathways"]},
                              "minItems": 1, "maxItems": 2, "uniqueItems": True}}}}


def payload(case, client):
    scope = case["scope"]
    functions = json.dumps([function_definition(scope)], ensure_ascii=True)
    question = (scope["question"] + "\nAuthorized exact UniProt cohort: "
                + json.dumps(scope["accessions"]) + "\nDefault focus: " + scope["focus_uniprot"])
    return {"model": client.model, "messages": [
        {"role": "system", "content": "detailed thinking off"},
        {"role": "user", "content": "<AVAILABLE_TOOLS>" + functions + "</AVAILABLE_TOOLS>\n\n" + question}],
        "stream": False, "temperature": 0, "max_tokens": client.max_output_tokens}


def implementation_hashes():
    return {name: sha(ROOT / name) for name in BOUND_FILES}


def prepare(out, *, client=None):
    client = client or configured_client()
    validate_client(client)
    selected, config = cases(), model_configuration(client)
    wires = {f"requests/{i:02d}_{case['id']}.json": payload(case, client)
             for i, case in enumerate(selected, 1)}
    artifacts = {"cases.json": selected,
                 "function_definition.json": function_definition(selected[0]["scope"]), **wires}
    out = new_output(out)
    (out / "requests").mkdir()
    for name, value in artifacts.items():
        write_json(out / name, value)
    implementation = implementation_hashes()
    for name in implementation:
        destination = out / "implementation" / name
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_bytes((ROOT / name).read_bytes())
    manifest = _seal({"format": FORMAT, "status": "prepared", "created_at": utcnow(),
        "model_configuration": config, "expected_runtime": expected_runtime(config),
        "implementation_sha256": implementation,
        "files": {name: sha(out / name) for name in artifacts},
        "payload_sha256": {name: digest(value) for name, value in wires.items()},
        "function_definition_sha256": digest(artifacts["function_definition.json"]),
        "case_count": 2, "maximum_model_calls": 2, "model_calls_during_preparation": 0,
        "maximum_output_tokens": 2 * client.max_output_tokens,
        "request_timeout_seconds": client.timeout, "retries": 0, "redirects": False,
        "source_calls": 0, "tool_execution": False, "output_parser": None,
        "format_assessment": "unassessed", "accuracy_scored": False,
        "reference": MODEL_CARD, "interpretation": INTERPRETATION})
    write_json(out / "manifest.json", manifest)
    validate_freeze(out, client)
    return manifest


def validate_freeze(experiment, client):
    validate_client(client)
    experiment = Path(experiment)
    if experiment.is_symlink() or not experiment.is_dir():
        raise ValueError("Probe must be an ordinary prepared directory.")
    manifest = _strict_json(experiment / "manifest.json")
    if (manifest != _seal(manifest) or manifest.get("format") != FORMAT
            or manifest.get("status") != "prepared" or manifest.get("interpretation") != INTERPRETATION
            or manifest.get("model_configuration") != model_configuration(client)
            or manifest.get("expected_runtime") != expected_runtime(model_configuration(client))
            or manifest.get("implementation_sha256") != implementation_hashes()
            or manifest.get("case_count") != 2 or manifest.get("maximum_model_calls") != 2
            or manifest.get("model_calls_during_preparation") != 0
            or manifest.get("maximum_output_tokens") != 2 * client.max_output_tokens
            or manifest.get("request_timeout_seconds") != client.timeout
            or manifest.get("retries") != 0 or manifest.get("redirects") is not False
            or manifest.get("source_calls") != 0 or manifest.get("tool_execution") is not False
            or manifest.get("output_parser") is not None or manifest.get("accuracy_scored") is not False
            or manifest.get("format_assessment") != "unassessed" or manifest.get("reference") != MODEL_CARD):
        raise ValueError("Changed probe configuration or implementation; preserve it and prepare a new directory.")
    artifacts = {"cases.json": cases(), "function_definition.json": function_definition(cases()[0]["scope"])}
    wires = {f"requests/{i:02d}_{case['id']}.json": payload(case, client) for i, case in enumerate(cases(), 1)}
    artifacts.update(wires)
    if (set(manifest["files"]) != set(artifacts)
            or manifest["payload_sha256"] != {name: digest(value) for name, value in wires.items()}
            or manifest["function_definition_sha256"] != digest(artifacts["function_definition.json"])):
        raise ValueError("Changed probe input inventory.")
    for name, expected in artifacts.items():
        if _strict_json(experiment / name) != expected or sha(experiment / name) != manifest["files"][name]:
            raise ValueError("Changed probe input: " + name)
    for name, checksum in manifest["implementation_sha256"].items():
        source = experiment / "implementation" / name
        if source.is_symlink() or not source.is_file() or sha(source) != checksum:
            raise ValueError("Changed preserved implementation: " + name)
    return manifest, wires


def collect_response(raw):
    """Retain final text and allowlisted metadata, without guessing tool syntax."""
    result = {"response_sha256": digest(raw), "status": "invalid_envelope",
              "model_returned": None, "usage": None, "finish_reason": None,
              "content": None, "content_status": "unavailable", "native_tool_calls_present": False,
              "format_assessment": "unassessed", "accuracy_scored": False}
    if not isinstance(raw, dict):
        return result
    if isinstance(raw.get("model"), str) and re.fullmatch(r"[A-Za-z0-9_.:/-]{1,200}", raw["model"]):
        result["model_returned"] = raw["model"]
    if isinstance(raw.get("usage"), dict):
        result["usage"] = {key: value for key, value in raw["usage"].items()
                           if key in {"prompt_tokens", "completion_tokens", "total_tokens"}
                           and type(value) is int and value >= 0}
    choices = raw.get("choices")
    if not isinstance(choices, list) or len(choices) != 1 or not isinstance(choices[0], dict):
        return result
    choice = choices[0]
    message = choice.get("message")
    if not isinstance(message, dict) or message.get("role") != "assistant":
        return result
    finish = choice.get("finish_reason")
    result["finish_reason"] = finish if finish in {"stop", "length", "tool_calls", "function_call", "content_filter"} else "unrecognized"
    result["native_tool_calls_present"] = bool(message.get("tool_calls") or message.get("function_call"))
    result["status"] = "response_received"
    content = message.get("content")
    if finish != "stop":
        result["content_status"] = "not_a_complete_final_message"
    elif message.get("refusal"):
        result["content_status"] = "refusal_metadata_present"
    elif not isinstance(content, str):
        result["content_status"] = "not_text"
    elif len(content.encode("utf-8")) > 20000:
        result["content_status"] = "exceeds_content_bound"
    elif REASONING_MARKUP.search(content):
        # No unverified reasoning stripper: omit the entire field, preserving its
        # response digest. Separate provider reasoning fields are never retained.
        result["content_status"] = "withheld_reasoning_markup"
    else:
        result.update(content=content, content_status="captured_unparsed")
    return result


def request_once(client, wire):
    validate_client(client)
    started = time.perf_counter()
    result = {"status": "transport_error", "error_type": None, "model_calls": 1,
              "format_assessment": "unassessed", "accuracy_scored": False}
    try:
        headers = {"Content-Type": "application/json", "Accept": "application/json"}
        if client.key:
            headers["Authorization"] = "Bearer " + client.key
        request = Request(client.endpoint, data=json.dumps(wire, ensure_ascii=True, allow_nan=False).encode(), headers=headers)
        context = ssl.create_default_context(cafile=os.environ.get("SSL_CERT_FILE") or None)
        opener = build_opener(_NoRedirect(), HTTPSHandler(context=context), ProxyHandler({}))
        with opener.open(request, timeout=client.timeout) as response:
            body = response.read(1_000_001)
        if len(body) > 1_000_000:
            raise ValueError("Response exceeds bound.")
        raw = json.loads(body, parse_constant=lambda _: (_ for _ in ()).throw(ValueError("Nonfinite JSON")))
        result.update(collect_response(raw))
        if client.key and client.key in (result.get("content") or ""):
            result.update(content=None, content_status="withheld_credential_value")
    except (HTTPError, URLError, OSError, ValueError, TypeError) as exc:
        # Exception bodies and unknown provider fields may contain credentials
        # or reasoning. Record type/status only, never their arbitrary contents.
        result["error_type"] = type(exc).__name__
        if isinstance(exc, HTTPError):
            result["http_status"] = exc.code
            exc.close()
    result["latency_ms"] = round((time.perf_counter() - started) * 1000, 3)
    return result


def run(experiment, *, client=None):
    client = client or configured_client()
    experiment = Path(experiment)
    manifest, wires = validate_freeze(experiment, client)
    manifest_hash = sha(experiment / "manifest.json")
    output = experiment / "results"
    if output.exists() or output.is_symlink():
        raise ValueError("This probe already has results; no resume or overwrite is allowed.")
    output.mkdir()
    rows, pending, status, error = [], None, "collected", None
    try:
        for name, wire in wires.items():
            validate_freeze(experiment, client)
            if sha(experiment / "manifest.json") != manifest_hash:
                raise ValueError("Probe manifest changed during execution.")
            pending = name
            write_json(output / "progress.json", {"status": "running", "completed_calls": len(rows), "pending_request": pending})
            row = {"request_file": name, "request_sha256": digest(wire), **request_once(client, wire)}
            rows.append(row)
            write_json(output / Path(name).name, row)
            pending = None
        validate_freeze(experiment, client)
        if sha(experiment / "manifest.json") != manifest_hash:
            raise ValueError("Probe manifest changed during execution.")
    except BaseException as exc:
        status, error = "interrupted", type(exc).__name__
        raise
    finally:
        result = _seal({"format": FORMAT + ".results", "created_at": utcnow(), "status": status,
            "manifest_sha256": manifest_hash, "model_configuration": manifest["model_configuration"],
            "expected_runtime": manifest["expected_runtime"], "completed_calls": len(rows),
            "pending_request": pending, "interruption_type": error, "rows": rows,
            "format_assessment": "unassessed", "accuracy_scored": False, "output_parser": None,
            "source_calls": 0, "tool_execution": False, "interpretation": INTERPRETATION,
            "interruption_note": "An interrupted in-flight call may have consumed tokens; no automatic resumption."})
        write_json(output / "probe.json", result)
        write_json(output / "progress.json", {"status": status, "completed_calls": len(rows), "pending_request": pending})
    return result


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    prep = commands.add_parser("prepare", help="Freeze two wire requests and local configuration; no inference.")
    prep.add_argument("--out", type=Path, required=True)
    execute = commands.add_parser("run", help="Collect two raw final responses, without parsing or execution.")
    execute.add_argument("--experiment", type=Path, required=True)
    args = parser.parse_args(argv)
    result = prepare(args.out) if args.command == "prepare" else run(args.experiment)
    print(json.dumps({"status": result["status"], "format_assessment": result["format_assessment"],
                      "model_calls": result.get("completed_calls", 0), "accuracy_scored": False}))


if __name__ == "__main__":
    main()
