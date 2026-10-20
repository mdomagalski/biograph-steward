# Brev deployment checkpoint — October 19, 2026 (EDT)

The core v0.8.0 app was deployed and tested on a Brev Ubuntu VM using source commit `936d3208fbe2011c7d203fc261af82f541f818a7`. This checkpoint establishes deployment behavior with synthetic data. Model inference, biomedical accuracy, real-source retrieval in Brev and AWS integration were not tested in this run.

Artifact names and machine timestamps use UTC, so the corresponding deployment receipts are labeled `20261020`.

The later [local Nemotron increment](LOCAL_MODEL.md) connects the planner through a separate loopback-only vLLM service. Use both `compose.yaml` and `compose.brev-local-model.yaml` when recreating that current deployment. Its [first live comparison](evaluations/NEMOTRON_20261019.md) failed the planning usefulness check; the checkpoint below describes the preceding core-only deployment and does not imply successful model planning.

## Verified environment

- One NVIDIA L40S, 48 GB; driver 565.57.01.
- Host Python 3.10.12, Docker 27.3.1 and Docker Compose 2.29.7.
- The app runs in its Python 3.12 Docker image as UID/GID 10001.
- Source code was transferred as a hash-verified Git bundle. Local datasets, caches and credentials were excluded.
- The Linux suite passed all 232 test cases, with the optional NeMo test skipped.

The image identity and resolved Python base digest are recorded in the deployment's `runtime.json`, alongside the before/after restart receipts. These reports are retained in the local ignored `runs/brev_deployment_20261020/` directory. The VM retains its test/build logs beneath the project's `workspace-data/deployment/` directory and smoke reports in the container's persistent `/data/runs/` volume.

## Verified behavior

The initial smoke test passed service health/version checks, authenticated UI access, rejection of anonymous access and unapproved browser origins, synthetic source creation, a deterministic answer with citations and source integrity checks.

After a real container restart, the same source graph and saved question reopened with unchanged hashes. A further test through the SSH tunnel verified authenticated UI access and an approved browser-origin write; its answer contained six citations. No model requests or external source retrieval were made.

## Access this deployment

On the VM, the project is `/home/ubuntu/workspace/biograph-steward`. Docker publishes the app only on `127.0.0.1:8766`. The browser origin `http://127.0.0.1:8767` is explicitly allowed for the protected SSH-forwarded UI.

If a tunnel is not already running, run this on the Mac after Brev login/refresh:

```bash
ssh -N -T -o ExitOnForwardFailure=yes \
  -L 127.0.0.1:8767:127.0.0.1:8766 biograph-steward-dev
```

Open <http://127.0.0.1:8767/>. The sign-in form uses the generated `BIOGRAPH_ACCESS_TOKEN` in the VM's project `.env` file, which is private and excluded from Git. To view that app token in your own remote terminal:

```bash
grep '^BIOGRAPH_ACCESS_TOKEN=' ~/workspace/biograph-steward/.env
```

Use only the value after `=` in the **Workspace access token** field. Do not paste it into chat or team messages. This token is distinct from Brev login credentials and any model download key. Browser sessions expire after eight hours, sign-out or an app restart.

The original HTTP Basic password prompt worked in Chrome but failed in the Codex browser with `ERR_INVALID_AUTH_CREDENTIALS`. A browser sign-in form now avoids that native prompt; Bearer and explicit Basic API credentials remain supported. This source increment must be identified alongside the base commit when reproducing the deployment.

The sign-in increment passed the full 238-case core suite on macOS (one optional test skipped) and all six new sign-in tests on the VM's Python 3.10. It was rebuilt into image `sha256:7f2be16100f4c7fbdac226738588a6e1734fdff3a035925ab28bd039cfe22351`. The deployed source archive's SHA-256 is `18ebb3fdc8cb6caecaf70a6713736413d472b7d5ea50fcebcc0539ab6371ef56`; its per-file manifest is retained in `browser_login_source.json` alongside the original deployment receipts. This archive identifies the deployed implementation before subsequent documentation edits.

HTTP checks through port 8767 passed sign-in, saved-question redirect preservation, cookie-authenticated reads and writes, rejection of an incorrect token and anonymous data access, and session revocation on sign-out. The original source and saved question reopened unchanged, and a further synthetic question returned six citations. Reports are `browser_login_http.json` and `browser_login_reopen/report.json` in the local deployment directory. No model calls were made. Automated visual inspection of the in-app browser was blocked by its URL access policy, so these checks establish server behavior rather than verified browser rendering.

To inspect or restart the app, run on the VM:

```bash
cd ~/workspace/biograph-steward
docker compose ps
docker compose restart steward
```

Stopping the Brev VM stops compute billing while retaining its storage. Stop the instance through Brev when it is not needed; stopping only the app container does not stop VM billing. Preserve artifacts outside the VM before deleting it.

## Local-model readiness

The planner and source verifier remain unconfigured on this deployment. The GPU is available, but that is not evidence that a model is serving.

The installed driver requires a deliberate NIM release choice: [NIM 2.0.13 prerequisites](https://docs.nvidia.com/nim/large-language-models/2.0.13/get-started/prerequisites.html) specify driver 580 or later, while this VM has 565.57.01. The [NIM 1.8 prerequisites](https://docs.nvidia.com/nim/large-language-models/1.8.0/getting-started.html) specify driver 560 or later and describe NGC authentication. A compatible older release is an option to verify, not a tested inference result. Resolve the exact image, model access and driver requirements before loading a model; the core app deployment does not require a driver change.

## Native browser form fix — October 20, 2026

Commit `884a7805fc614d534b1cf9c28556e90eea49e3f4` fixes a native-form failure that explicit-Origin HTTP probes had missed. In an isolated Chrome test using an invented token, the original `Referrer-Policy: no-referrer` produced `Origin: null` and HTTP 403. `same-origin` preserves the expected form Origin while suppressing referrers to external destinations. The corrected browser completed sign-in, returned to a saved report and signed out. Null, missing and foreign form origins remain rejected.

`/auth/login` now serves its form directly. HTML navigation to a protected evaluation report shows the form and preserves that exact report as its return destination. Anonymous programmatic report/metrics/download requests still receive HTTP 401. Return destinations remain restricted to local root/question and HTML-report URLs.

Deployment resumed after the user restarted the stopped Brev instance. Local Python 3.14 and Brev Python 3.12 each ran 359 tests, with one optional integration skipped and no failures. The app-only rebuild produced image `sha256:8af4ca4bffd354c2564ba87448a9e30953397915bf9046f28e37d5fe13306a52`; both app and model services are healthy. The model service was not rebuilt or restarted by this deployment.

Through the restored loopback tunnel on port 8767, checks passed public form routes, the response policy, token-to-cookie sign-in, exact saved-report return, logout revocation and rejection of invalid origins. The protocol report/metrics and all eleven export files matched saved bytes; seven earlier reports were unchanged. These deployment checks are HTTP-level; the native Chrome test used the local isolated fixture. The in-app browser remains visually unverified because its automation dependency could not load. No real token/session values were saved in receipts and no inference calls were made. Local receipts and the Chrome screenshot are under ignored `runs/browser_origin_fix_20261020/`.
