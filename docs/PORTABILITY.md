# Brev and model-provider portability — v0.8.0

The core app remains standard-library Python 3.10+. Use Python 3.12 for the optional NeMo Agent Toolkit environment. This increment adds explicit hosting configuration, persistent run/cache paths, a shared HTTP model transport, NVIDIA NIM request support and one optional NeMo workflow. It does not provision cloud resources or include a model.

## Start in a Brev VM

Clone the repository into your challenge VM and change into it. No installation is needed for the core app. Choose an absolute persistent directory on that VM:

```bash
export BIOGRAPH_DATA_DIR="$PWD/workspace-data"
export BIOGRAPH_PORT=8766
python3 app.py runtime-check
python3 app.py serve --no-browser
```

The runtime check makes no inference or source requests. HTTP model configuration is validated locally; it does not establish that a remote endpoint is available. Checking a configured Codex provider may run its local `--version` check. Models are optional for deterministic guided questions and reports.

Run this on your own computer to access the VM through SSH, using the real instance name:

```bash
brev port-forward YOUR_INSTANCE_NAME --port 8766:8766
```

Then open <http://127.0.0.1:8766/>. Keep local and remote ports identical for this default browser-origin policy. A port already in use must be freed or changed on both sides. The [Brev connectivity guide](https://docs.nvidia.com/brev/cli/connectivity) documents the forwarding command.

`BIOGRAPH_DATA_DIR` sets defaults for `runs/` and `cache/` beneath that directory. `BIOGRAPH_RUNS_DIR` and `BIOGRAPH_CACHE_DIR` override those individually; `--runs-dir` and `--cache-dir` override the environment for commands that expose them. Commands requiring `--out` still need an explicit output path. Data paths do not automatically move old runs.

The default `runs/`, cache and the example `workspace-data/` directories are excluded from Git. If choosing another data directory inside the checkout, add it to `.gitignore` before retrieving sources. A clone starts with the synthetic example and code. Retrieve new sources, prepare SciFact using [the benchmark guide](VERIFICATION_BENCHMARKS.md), or copy frozen run directories with their manifests and hashes. A directory existing on this Mac is not automatically available in Brev. Back up the VM data directory; VM deletion is not an artifact-storage policy.

## Brev secure links and shared browser access

For a [Brev Secure Link](https://docs.nvidia.com/brev/concepts/launchables), configure the exact external HTTPS origin and a generated workspace token in the environment of the running process:

```bash
export BIOGRAPH_ACCESS_TOKEN="$(python3 -c 'import secrets; print(secrets.token_urlsafe(32))')"
export BIOGRAPH_ALLOWED_ORIGINS="https://YOUR_ACTUAL_SECURE_LINK_HOST"
# Set 0.0.0.0 only when the configured proxy/container network requires it.
export BIOGRAPH_HOST=0.0.0.0
python3 app.py runtime-check
python3 app.py serve --no-browser
```

Replace the placeholder with the workspace's actual origin, without a path. The server does not enable TLS itself; external access goes through the authenticated HTTPS proxy. Remote browser origins and non-loopback binding require `BIOGRAPH_ACCESS_TOKEN` (24–256 non-whitespace ASCII characters). There is no wildcard-origin mode and forwarded headers do not expand the allowlist.

The browser shows a sign-in page: enter **the configured workspace token**. A successful sign-in sets an opaque `HttpOnly`, `SameSite=Strict` session cookie for up to eight hours. HTTPS browser origins receive a `Secure` cookie; a loopback SSH tunnel uses its local HTTP origin. Sign out revokes that session, and restarting the app revokes all browser sessions. Saved run/question links survive sign-in. Native HTTP Basic prompts are avoided because some embedded browsers cannot use them.

Programmatic clients may send `Authorization: Bearer <workspace-token>`; explicit Basic headers (`steward` and the workspace token) remain supported. Browser cookie writes, sign-in and sign-out also require an explicit approved `Origin`; CLI requests with explicit API credentials need no Origin. The token protects all workspace data and actions. Anonymous access is limited to service status/version at `/healthz` and the sign-in form. Keep credentials in the deployment's secret configuration, never in URLs or Git. This shared workspace token does not authenticate an individual scientific reviewer or provide per-user authorization.

Brev launch parameters are not automatically permanent shell environment variables. Pass the selected values to the actual process/container on every start. Preserve runtime secrets through the workspace's approved secret mechanism. A restart with a new token invalidates the old credential. Check that the configured HTTPS proxy preserves the app's Authorization header.

## Docker and Docker Compose

The Docker image runs core Python as UID/GID 10001, stores data beneath `/data`, and requires no GPU. Docker is optional for VM use. The image excludes local datasets, credentials, Git metadata and generated caches. NeMo and self-hosted NIM containers are separate optional environments.

```bash
cp .env.example .env
# Fill BIOGRAPH_ACCESS_TOKEN with a generated token.
# Fill the model fields only if using a model; leave them blank for the data UI.
docker compose up --build -d
```

Compose publishes port 8766 on host loopback by default and persists `/data` in the `steward-data` named volume. For a secure-link proxy requiring a host-network binding, set `BIOGRAPH_PUBLISH_HOST=0.0.0.0` alongside the token and exact HTTPS allowed origin. Keep direct ingress restricted to the intended proxy. Stop with `docker compose down`; omitting `--volumes` preserves the dataset volume.

If replacing the named volume with a host bind mount, make that directory writable by UID/GID 10001. The application does not change ownership of existing user datasets.

The Python app does not load `.env`; Compose does. For VM operation export settings in the process environment instead. Do not source the file as executable shell code. `.env.example` is a template, not a working model configuration.

Run a CLI job against the same persistent volume:

```bash
docker compose exec steward python app.py runtime-check
docker compose exec steward python app.py demo --out /data/runs/synthetic_demo_01
```

`BIOGRAPH_PYTHON_IMAGE` can pin an approved Python 3.12 image by digest for a controlled build. The default is `python:3.12-slim`; that tag is not an immutable image identity. Record the resolved image ID for a frozen deployment.

## Check the running deployment

Run the smoke command from the same checkout/version as the running service. It uses only invented demo records; it does not retrieve Pharos/CIViC or change scientific review state. The default requests no model inference. Use new output directories each time:

```bash
python3 app.py deployment-smoke \
  --base-url http://127.0.0.1:8766 \
  --out "$BIOGRAPH_DATA_DIR/runs/deployment_before_restart_01"
```

For a Secure Link, replace `--base-url` with its exact root HTTPS URL. Supply the app's existing `BIOGRAPH_ACCESS_TOKEN` to this command through the environment. This is the workspace access token, not the model API key. The origin defaults to that URL; `--browser-origin` can specify the approved external origin when testing a proxy through a local connection. Redirects are rejected, so a proxy login page cannot silently receive forwarded credentials.

The checks cover service version, anonymous/authenticated access, the browser-origin guard, saving an explicitly synthetic graph, and answering a candidate-pathway question with matching source hashes and citations. A failed check exits with status 1 and retains `report.json`; invalid settings or an existing output directory fail before testing. A successful initial report is also a receipt for the next check.

Restart the actual service while keeping the data mount/directory. For Compose, run `docker compose restart steward`; for a VM process, stop and start it with the same environment. Then reopen the saved data:

```bash
python3 app.py deployment-smoke \
  --base-url http://127.0.0.1:8766 \
  --receipt "$BIOGRAPH_DATA_DIR/runs/deployment_before_restart_01/report.json" \
  --out "$BIOGRAPH_DATA_DIR/runs/deployment_after_restart_01"
```

Receipt mode performs only reads against the service and checks the same source, review basis and saved answer. It writes a new local report. It cannot independently attest that an operator restarted the service; CI performs a real container restart between those two commands. Receipt mode never requests another model turn.

After configuring the model below, repeat the initial command with `--with-planner` and a new output directory. This explicitly requests one model plan using the demo catalogue. It checks the planned scope and compares execution with the equivalent deterministic query. Failed or timed-out model requests are not retried. `planner_http_requests` counts requests to the app; `reported_model_calls` is the app's trace metadata and remains unknown if that response is unavailable. Token usage and served model names remain provider-reported metadata. Neither a successful deployment check nor synthetic model success establishes biomedical accuracy. Use the separate training benchmark before evaluating a new model scientifically.

## Configure a shared model for planner and verifier

For the tested local NVIDIA-model serving configuration, see [Local Nemotron on Brev](LOCAL_MODEL.md). Its Linux-only Compose overlay keeps the app and vLLM model on VM loopback and enables only the planner. The NIM setup below remains a separate option.

The [compute readiness guide](COMPUTE_READINESS.md) distinguishes verified development hosting from pending production/AWS work. AWS is not required for local-model evaluation; a private artifact backup/restore workflow is the suggested first AWS integration.

All model IDs and full endpoint URLs are explicit. This example describes the **request protocol**, not an installed model:

```bash
export BIOGRAPH_MODEL_PROVIDER=nim
export BIOGRAPH_MODEL_ID='YOUR_WORKSPACE_MODEL_ID'
export BIOGRAPH_MODEL_ENDPOINT='https://YOUR_MODEL_HOST/v1/chat/completions'
export BIOGRAPH_MODEL_API=nim_chat
# Supply BIOGRAPH_MODEL_API_KEY using the workspace secret configuration if needed.
python3 app.py runtime-check
```

Do not enter the placeholders literally. A self-hosted NIM on the same VM can use `http://127.0.0.1:8000/v1/chat/completions`. Non-loopback HTTP is rejected. Inside the app container, loopback is the app container, not the host VM or another service; use an approved HTTPS model endpoint, or run the app on the VM alongside a loopback-published NIM.

| API setting | Request contract |
|---|---|
| `nim_chat` | Chat Completions response envelope; `guided_json`, `max_tokens`, `temperature=0`, no `store` field. |
| `chat_completions` | `response_format` with strict `json_schema`, `max_completion_tokens`, `store=false`. |
| `responses` | `text.format` with strict `json_schema`, `max_output_tokens`, `store=false`. |

Choose the API supported by the exact endpoint and model. The [NIM structured-generation guide](https://docs.nvidia.com/nim/large-language-models/1.14.0/structured-generation.html) documents `guided_json`. Deployments differ; unsupported fields/schema features fail explicitly rather than causing a fallback or repair call. The current NIM/model version, hardware, context capacity and endpoint capabilities still need a live workspace check.

`BIOGRAPH_PLANNER_*` and `BIOGRAPH_VERIFIER_*` override the shared settings for a single role. For example `BIOGRAPH_PLANNER_MODEL` overrides `BIOGRAPH_MODEL_ID`; `BIOGRAPH_VERIFIER_API` overrides `BIOGRAPH_MODEL_API`. Empty explicit values do not silently reuse another setting.

`BIOGRAPH_PLANNER_PROTOCOL` selects `catalogue_v1` (the compatibility default), `entity_tools_v2` (exact mention binding/tool contracts) or `tool_shapes_v3` (additional tool-specific output shapes and request-scope checks). See [the protocol and audit limits](PLANNER_PROTOCOL.md). It is independent of the serving API and model prompt profile. Set it before initializing a planner; changing it requires a separately recorded experiment.

Shared settings are `BIOGRAPH_MODEL_PROVIDER`, `BIOGRAPH_MODEL_ID`, `BIOGRAPH_MODEL_ENDPOINT`, `BIOGRAPH_MODEL_API`, `BIOGRAPH_MODEL_API_KEY`, `BIOGRAPH_MODEL_MAX_OUTPUT_TOKENS`, `BIOGRAPH_MODEL_TIMEOUT` and `BIOGRAPH_MODEL_PROMPT_PROFILE`. Role-specific settings override them. Prompt profiles are `standard` (the default) and explicit `nemotron_nano_v1` (NVIDIA Nano v1's reasoning-off system switch with the complete task policy in the user message). Output budgets are 128–8192 tokens; timeouts are 1–300 seconds. Defaults are 1600 tokens/45 seconds for the planner and 3000 tokens/90 seconds for the HTTP verifier. These are configured budgets, not observed token usage.

Providers are `api`, `nim` or `codex`. Without shared/role configuration, the existing planner defaults to `api` and verifier to `codex`. `OPENAI_API_KEY` is used only for `api.openai.com` and is never sent to custom endpoints. Other endpoints use the role/shared API key; the NIM provider can use `NVIDIA_API_KEY` when no role/shared key was set. Codex retains its existing CLI login and `BIOGRAPH_CODEX_MODEL` / `BIOGRAPH_CODEX_BIN` configuration; the Mac executable path is not portable to Brev.

Both HTTP agents use one bounded request. Redirects, retries, external tool execution and repair calls are disabled. Invalid, truncated, refused or tool-calling responses cannot execute a query or become a source assessment. Exact sentence validation and source hashes remain mandatory. Traces record provider/protocol, requested and returned model IDs, request/schema hashes, budgets and returned usage; no API key or private reasoning is saved. Provider/model names are reported metadata, not independent attestation of the server implementation.

Loopback model requests bypass environment/system proxies so local model credentials stay on the local connection. Remote HTTPS model calls continue to use the configured proxy and certificate settings.

After configuring an actual provider, first run a small **training** smoke test:

```bash
python3 app.py verification-run \
  --benchmark "$BIOGRAPH_DATA_DIR/runs/scifact_verification_train_01" \
  --verifier configured --limit 5 --workers 1 \
  --out "$BIOGRAPH_DATA_DIR/runs/nim_training_smoke_01"
```

Prepare that benchmark directory first. `--verifier nim` / `api` / `codex` explicitly selects a provider; `configured` uses the role/shared provider. The default remains offline `baselines`. Each new model needs its own evaluation and new immutable output directory. The October 15 GPT/Codex results are not NVIDIA or Bedrock results. Existing question-evaluation suites freeze code fingerprints; initialize a new suite for the updated engine, while preserving old reports.

## Optional NeMo Agent Toolkit workflow

Use a dedicated Python 3.12 environment:

```bash
python3.12 -m venv .venv-nvidia
.venv-nvidia/bin/python -m pip install -e '.[nvidia]'
.venv-nvidia/bin/nat info components --query biograph --types function
export BIOGRAPH_NAT_SOURCE_RUN="$BIOGRAPH_DATA_DIR/runs/YOUR_FROZEN_SOURCE_RUN"
.venv-nvidia/bin/nat run --config_file deploy/nvidia/question.yml \
  --input 'Which proteins interact with KRAS in the retrieved cohort?'
```

Configure the model environment first. A source with only candidate assertions will correctly have no accepted-only answer. Candidate inspection must be requested explicitly, as in the existing planner contract.

The optional extra pins `nvidia-nat-core==1.8.0` and `packaging==25.0` (required by that CLI's registry code). Toolkit Python support is 3.11–3.13; the core app still supports 3.10+. Some unused first-party Toolkit plugins can warn about missing optional framework dependencies in a core-only environment. Our workflow does not use those plugins.

The `nat.plugins` entry point registers **biograph_question**, a complete bounded question workflow that can also be used as a function in another configured workflow. Its administrator selects a fixed source run and result/path budgets. User input is only a question. The wrapper calls the existing planner once and executes at most one validated read-only local query. Output is JSON containing the execution result, citations and model trace. The source run is rechecked before execution; changed sources require reloading the workflow. No source retrieval, review transition, graph write or additional agent loop is exposed by this wrapper. Retain its returned JSON through the caller's artifact policy.

This integrates our workflow into NeMo; it does not discover or authorize other challenge agents automatically. See the [public plugin API](https://docs.nvidia.com/nemo/agent-toolkit/latest/extend/plugin-api.html) and [plugin discovery contract](https://docs.nvidia.com/nemo/agent-toolkit/latest/extend/third-party-plugins.html). This is a project-owned integration, not an NVIDIA-certified plugin. We do not expose the NeMo API server publicly in this increment.

## AWS boundary

The HTTP transport can target a selected compatible Bedrock API endpoint using provider `api` and an explicitly supplied service API key, if the exact model/endpoint accepts that protocol and schema. This has not been tested against a live AWS account. [Bedrock API support](https://docs.aws.amazon.com/bedrock/latest/userguide/apis.html) varies by model and endpoint.

Native Bedrock Converse/SigV4 integration, AWS credential-chain handling, S3 artifact export/import and Neptune remain later work. This increment does not read AWS credentials, create AWS resources or claim AWS deployment readiness. It preserves local artifact contracts so those adapters can be added without changing scientific review state.

## Verification status

On October 19, 2026, the full 232-test suite passed on macOS with Python 3.14, skipping the one optional NeMo test. The original 224-test regression suite and the eight new deployment tests also passed against a normally installed core package on Python 3.12. The optional test passed separately using the real NeMo Agent Toolkit 1.8.0 CLI against a local mock model. A CLI smoke run reopened the same graph and cited answer after a real local app-process restart. Installed HTML assets loaded outside the checkout without NeMo dependencies. Deployment YAML and CI shell syntax were checked. Docker is not available on the development machine, so the image has not been built locally.

Use `python3 -m unittest discover -s tests -q` for core tests, and the optional environment's Python with `-p test_nvidia_workflow.py` for the real Toolkit smoke test. Local mock services exercise NIM request formatting, source/quote validation, failure accounting, redirect blocking, authentication, exact proxy origins and fixed-source execution. Mock service success is not a live NIM inference result.

On October 19, 2026 (EDT), the core app was also built and deployed on an actual Brev L40S VM: the 232-test Linux suite passed (one optional NeMo test skipped), protected UI and synthetic question checks passed, and unchanged saved data reopened after a real container restart. The SSH-forwarded browser-origin check passed as well. See the [deployment checkpoint](BREV_DEPLOYMENT.md) for configuration and the unresolved local-model driver requirement. No live model inference or real-source retrieval was performed in that deployment test.

The GitHub Actions portability workflow checks Linux Python versions, installed package assets, the optional NeMo workflow and Docker startup/restart persistence using the deployment-smoke command above. The Brev run does not establish a successful GitHub Actions run. A live Brev Secure Link, actual workspace model and AWS service still require their own deployment checks.
