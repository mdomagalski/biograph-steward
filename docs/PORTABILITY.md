# Brev and model-provider portability — v0.8.0

The core app remains standard-library Python 3.10+. Use Python 3.12 for the optional NeMo Agent Toolkit environment. The retained deployment supports explicit hosting configuration, persistent run/cache paths, model transport for the bounded planner, NVIDIA NIM request formatting and one optional NeMo workflow. It does not provision cloud resources or include a model.

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

The default `runs/`, cache and the example `workspace-data/` directories are excluded from Git. If choosing another data directory inside the checkout, add it to `.gitignore` before retrieving sources. A clone starts with the synthetic example and code. Retrieve new sources or copy compatible frozen workbench runs with their manifests and hashes. Closed experiment packets belong with the separate [archive checkout](EXPERIMENT_HISTORY.md). A directory existing on this Mac is not automatically available in Brev. Back up the VM data directory; VM deletion is not an artifact-storage policy.

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

`/auth/login` also serves the sign-in form directly. Navigating to a supported HTML snapshot-comparison report while signed out shows the form and returns to that same report after sign-in; programmatic report/metrics/download clients still receive HTTP 401 without credentials. Return links are restricted to root question URLs and exact local HTML report paths. Responses use `Referrer-Policy: same-origin`: this preserves the browser Origin for native sign-in/sign-out forms while suppressing referrers to external sites. `no-referrer` makes native form POSTs send `Origin: null` in Chrome and conflicts with the required explicit-origin check. Null, missing and foreign origins remain rejected for browser forms.

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

After removing modules or assets, build distributions from a clean checkout or clean build staging. A new wheel output directory alone does not clear setuptools' intermediate files: stale `build/` or `*.egg-info/` content can retain removed code. Before rebuilding an existing workspace, move aside or remove only generated `build/`, `dist/` and package `*.egg-info/` artifacts, then inspect the resulting wheel. Keep scientific `runs/` and source `cache/` intact. This follows the pinned upstream guidance on [stale build caches](https://github.com/pypa/setuptools/blob/v80.9.0/docs/userguide/miscellaneous.rst) and [orphaned package-data files](https://github.com/pypa/setuptools/blob/v80.9.0/docs/userguide/datafiles.rst).

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

After configuring the model below, repeat the initial command with `--with-planner` and a new output directory. This explicitly requests one model plan using the demo catalogue. It checks the planned scope and compares execution with the equivalent deterministic query. Failed or timed-out model requests are not retried. `planner_http_requests` counts requests to the app; `reported_model_calls` is the app's trace metadata and remains unknown if that response is unavailable. Token usage and served model names remain provider-reported metadata. Neither a successful deployment check nor synthetic model success establishes biomedical accuracy. A scientific quality claim requires a separately justified and frozen evaluation.

## Configure the optional planner

The tested local NVIDIA-model setup is documented in [Local Nemotron on Brev](LOCAL_MODEL.md). The Linux overlay keeps the app and vLLM model on VM loopback. NIM is a separate supported request format, not the currently tested serving implementation.

All model IDs and full endpoint URLs are explicit. This describes the request configuration, not an installed service:

```sh
export BIOGRAPH_MODEL_PROVIDER=nim
export BIOGRAPH_MODEL_ID='YOUR_WORKSPACE_MODEL_ID'
export BIOGRAPH_MODEL_ENDPOINT='https://YOUR_MODEL_HOST/v1/chat/completions'
export BIOGRAPH_MODEL_API=nim_chat
export BIOGRAPH_PLANNER_PROTOCOL=scoped_targets_v4
# Supply BIOGRAPH_MODEL_API_KEY through the deployment's secret configuration if needed.
python3 app.py runtime-check
```

Replace the placeholders with actual endpoint values. A model served on the same VM can use `http://127.0.0.1:8000/v1/chat/completions`; non-loopback HTTP is rejected. Inside a normal container, loopback refers to that container. Use the documented Linux host-network overlay or an approved HTTPS endpoint for the intended service.

| API setting | Request contract |
|---|---|
| `nim_chat` | Chat Completions envelope; `guided_json`, `max_tokens`, `temperature=0`, no `store` field |
| `chat_completions` | Strict `json_schema` in `response_format`, `max_completion_tokens`, `store=false` |
| `responses` | Strict `json_schema` in `text.format`, `max_output_tokens`, `store=false` |

Match the exact endpoint's supported schema and API. The [version-specific NIM guide](https://docs.nvidia.com/nim/large-language-models/1.14.0/structured-generation.html) documents `guided_json`; unsupported fields or schema features fail explicitly. Live NIM inference remains unverified for this project.

Shared settings are `BIOGRAPH_MODEL_PROVIDER`, `BIOGRAPH_MODEL_ID`, `BIOGRAPH_MODEL_ENDPOINT`, `BIOGRAPH_MODEL_API`, `BIOGRAPH_MODEL_API_KEY`, `BIOGRAPH_MODEL_MAX_OUTPUT_TOKENS`, `BIOGRAPH_MODEL_TIMEOUT` and `BIOGRAPH_MODEL_PROMPT_PROFILE`. `BIOGRAPH_PLANNER_*` overrides them for the planner; for example, `BIOGRAPH_PLANNER_MODEL` overrides `BIOGRAPH_MODEL_ID`. Empty explicit values do not silently reuse another setting. The default HTTP planner budget is 1,600 output tokens and 45 seconds; the Brev overlay specifies its own timeout.

Providers are `api`, `nim` or an explicitly configured authenticated `codex` CLI. Model keys are distinct from the workspace access token. `OPENAI_API_KEY` is used only for `api.openai.com`; custom endpoints use their configured key. NIM can use `NVIDIA_API_KEY` when no role/shared key is set. CLI authentication and executable paths are local to the machine running the service.

Use the `standard` prompt profile for ordinary models, or the explicit `nemotron_nano_v1` profile for the documented NVIDIA Nano v1 reasoning-off format. [Planner protocols](PLANNER_PROTOCOL.md) describe the selected query contract and compatibility defaults.

One bounded request may produce at most one application-validated read-only query. Redirects, retries, repair calls and external tool execution are disabled. Invalid responses do not execute a query. Traces include request/schema hashes, configured budgets and returned model/usage metadata, without API keys or private reasoning. Loopback model requests bypass system proxies; remote HTTPS requests retain configured proxy and certificate settings.

After configuring the actual provider, use the deployment smoke command above with `--with-planner` and a new output directory. This requests one synthetic plan and checks its execution against the deterministic query. Old verifier/scientific experiment commands are available only in the [research archive](EXPERIMENT_HISTORY.md).

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

The counts above describe that historical deployment checkpoint, not the consolidated test suite. Use `python3 -m unittest discover -s tests -q` for current core tests, and the optional environment's Python with `-p test_nvidia_workflow.py` for the real Toolkit smoke test. Local mock services exercise NIM request formatting, source/query validation, failure accounting, redirect blocking, authentication, exact proxy origins and fixed-source execution. Mock service success is not a live NIM inference result.

On October 19, 2026 (EDT), the core app was also built and deployed on an actual Brev L40S VM: the 232-test Linux suite passed (one optional NeMo test skipped), protected UI and synthetic question checks passed, and unchanged saved data reopened after a real container restart. The SSH-forwarded browser-origin check passed as well. See the [deployment checkpoint](BREV_DEPLOYMENT.md) for configuration and the unresolved local-model driver requirement. No live model inference or real-source retrieval was performed in that deployment test.

The GitHub Actions portability workflow checks Linux Python versions, installed package assets, the optional NeMo workflow and Docker startup/restart persistence using the deployment-smoke command above. The Brev run does not establish a successful GitHub Actions run. A live Brev Secure Link, actual workspace model and AWS service still require their own deployment checks.
