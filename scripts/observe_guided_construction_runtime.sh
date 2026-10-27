#!/usr/bin/env bash
# Run through: brev exec biograph-steward-dev @scripts/observe_guided_construction_runtime.sh
# Read-only: no restart, pull, inference, source request, credentials or full env.
set -eu
python3 - <<'PY'
from datetime import datetime, timezone
import importlib.metadata
import json
import subprocess
from urllib.request import ProxyHandler, build_opener


def command(args):
    completed = subprocess.run(args, capture_output=True, text=True, timeout=45, check=False)
    if completed.returncode:
        # Docker error strings can include configuration. Do not echo them.
        raise RuntimeError("Read-only command failed: " + args[0] + " " + args[1])
    return completed.stdout


try:
    ids = command(["docker", "ps", "-q", "--filter", "label=com.docker.compose.service=local-model"]).split()
    if len(ids) != 1:
        raise RuntimeError("Expected exactly one running Compose local-model service.")
    full = json.loads(command(["docker", "inspect", ids[0]]))[0]
    image = json.loads(command(["docker", "image", "inspect", full["Image"]]))[0]
    args = full["Config"]["Cmd"]
    value_flags = {"--model", "--revision", "--tokenizer-revision", "--served-model-name", "--host", "--port",
        "--dtype", "--max-model-len", "--max-num-seqs", "--gpu-memory-utilization",
        "--guided-decoding-backend", "--generation-config"}
    boolean_flags = {"--enforce-eager", "--disable-log-requests", "--enable-chunked-prefill", "--enable-prefix-caching"}
    allowed, unknown_count, index = {}, 0, 0
    while index < len(args):
        token = args[index]
        flag, equals, inline = token.partition("=")
        if flag in value_flags:
            if flag in allowed:
                raise RuntimeError("Repeated allowlisted server flag.")
            if equals:
                value = inline
            else:
                index += 1
                if index >= len(args):
                    raise RuntimeError("Incomplete server flag.")
                value = args[index]
            if value.startswith("--"):
                raise RuntimeError("Incomplete server flag value.")
            allowed[flag] = value
        elif flag in boolean_flags and not equals:
            allowed[flag] = True
        else:
            unknown_count += 1
        index += 1
    environment = {}
    for item in full["Config"].get("Env", []):
        key, _, value = item.partition("=")
        if key == "VLLM_USE_V1":
            environment[key] = value
    if allowed.get("--host") != "127.0.0.1" or allowed.get("--port") != "8000":
        raise RuntimeError("The current model service is not on the declared VM loopback endpoint.")
    versions = json.loads(command(["docker", "exec", full["Id"], "python3", "-c",
        "import importlib.metadata,json,platform; print(json.dumps({'python':platform.python_version(),"
        "'vllm':importlib.metadata.version('vllm'),'xgrammar':importlib.metadata.version('xgrammar'),"
        "'torch':importlib.metadata.version('torch')}))"]))
    opener = build_opener(ProxyHandler({}))
    with opener.open("http://127.0.0.1:8000/health", timeout=10) as response:
        health_status = response.status
        health_body = response.read(10001)
    with opener.open("http://127.0.0.1:8000/v1/models", timeout=10) as response:
        models_status = response.status
        body = response.read(1000001)
    if len(body) > 1000000 or len(health_body) > 10000:
        raise RuntimeError("Model health/metadata response exceeded its bound.")
    models = json.loads(body)
    served = [row["id"] for row in models["data"]]
    engine_value = environment.get("VLLM_USE_V1")
    engine = "V0" if engine_value == "0" else "V1" if engine_value == "1" else "not_explicitly_declared"
    flags = {"max_model_len": int(allowed["--max-model-len"]),
        "max_num_seqs": int(allowed["--max-num-seqs"]),
        "gpu_memory_utilization": float(allowed["--gpu-memory-utilization"]),
        "enforce_eager": allowed.get("--enforce-eager", False),
        "guided_decoding_backend": allowed["--guided-decoding-backend"],
        "generation_config": allowed["--generation-config"]}
    observed_at = datetime.now(timezone.utc).isoformat()
    observation = {"format": "biograph-steward.guided-construction-development.v1.runtime",
        "observation_kind": "live_runtime_observation", "observed_at": observed_at,
        "engine": engine, "vllm_version": versions["vllm"], "xgrammar_version": versions["xgrammar"],
        "image": full["Config"]["Image"], "image_id": full["Image"], "container_id": full["Id"],
        "model": allowed["--model"], "model_revision": allowed["--revision"],
        "tokenizer_revision": allowed["--tokenizer-revision"], "dtype": allowed["--dtype"],
        "health_http_status": health_status, "served_model_ids": served,
        "request_endpoint": "http://127.0.0.1:8010/v1/chat/completions",
        "server_endpoint": "http://127.0.0.1:8000", "effective_flags": flags}
    # Only this allowlisted view is printed. The full Docker environment and
    # any unrecognized command arguments remain private and are not retained.
    raw = {"format": "biograph-steward.guided-runtime-sanitized-observation.v1",
        "status": "observed", "observed_at": observed_at,
        "container": {"id": full["Id"], "name": full["Name"], "running": full["State"]["Running"],
            "started_at": full["State"]["StartedAt"], "configured_image": full["Config"]["Image"],
            "image_id": full["Image"], "allowlisted_arguments": allowed,
            "unrecognized_argument_tokens": unknown_count, "environment_allowlist": environment},
        "image": {"id": image["Id"], "repo_digests": image.get("RepoDigests", [])},
        "package_versions": versions, "health_http_status": health_status,
        "models_http_status": models_status, "served_model_ids": served,
        "derived_observation": observation,
        "transport_note": "request_endpoint is the declared local SSH forward, not attested by this remote observer.",
        "scope": "Read-only container/package/health/model metadata; no inference, GPU workload, restart, pull or source retrieval."}
    print(json.dumps(raw, indent=2))
except Exception as exc:
    print(json.dumps({"format": "biograph-steward.guided-runtime-sanitized-observation.v1",
        "status": "observation_failed", "error_type": type(exc).__name__,
        "error": str(exc) if isinstance(exc, RuntimeError) else "Read-only observation failed; private command output omitted."}, indent=2))
    raise SystemExit(1)
PY
