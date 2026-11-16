# Local Nemotron for the source agent and legacy planner

The Linux-only `compose.brev-local-model.yaml` overlay connects the existing app to NVIDIA's publicly downloadable [Llama-3.1-Nemotron-Nano-8B-v1](https://huggingface.co/nvidia/Llama-3.1-Nemotron-Nano-8B-v1), served by [vLLM](https://docs.vllm.ai/en/v0.8.5/deployment/docker.html). This is a vLLM deployment of an NVIDIA model, not an NVIDIA NIM deployment. It requires no hosted inference API or NGC download key. The model's license and upstream notices remain applicable.

The [current-source agent](SOURCE_AGENT.md) uses this configured model transport
for a bounded plan → source query → citation inspection → review-proposal
workflow. It supports the current native physical, native location and archived
pathway tools when attached to the selected workspace. The older one-call
planner and literature-audit agent retain their separate evaluations in the
[NVIDIA integration record](NVIDIA_INTEGRATION_STATUS_20261113.md).

New live agent execution needs the configured model service. Replaying a
recorded agent job or using the guided evidence reader does not: those paths
verify saved source data on CPU. Keep Brev off when no new model calls are
planned. A configured endpoint alone does not establish a successful agent run.

The [November 16 current-tool check](evaluations/SOURCE_AGENT_RESULTS_20261116.md)
completed five supported executions with exact source-query/answer/focused-graph
parity and three zero-call preflight guards. It used 13 Nemotron calls and 972
completion tokens. This demonstrates the bounded controller on those cases;
identities were application-grounded and most plans had one available query
tool. It is not a general routing, biological-accuracy or prediction-gain result.
The prepared recorded job still requires its separate hosted rollout receipt.

## Fixed configuration

- Model and tokenizer revision: `54641c1611fcff44fa4865626462445e0a153fc7`.
- Server: vLLM `0.8.5`, image digest `sha256:6cf9808ca8810fc6c3fd0451c2e7784fb224590d81f7db338e7eaf3c02a33d33`.
- Engine: the overlay explicitly sets `VLLM_USE_V1=0`. V0 and V1 do not expose identical structured-output capabilities in this release.
- Verified container runtime: PyTorch `2.6.0+cu124`, CUDA `12.4`, on the VM's NVIDIA L40S and driver `565.57.01`.
- BF16 weights, 16,384-token context, one concurrent sequence, 75% GPU-memory budget, eager execution and guided JSON output. These are configured limits, not a throughput benchmark.
- Current-source agent: at most three model requests, capped at 1,200 output tokens each, with one bounded source query and up to three complete citation-group inspections. No retries, repair calls or graph/review writes.
- Legacy one-call planner: one request, at most 1,600 output tokens, 120-second timeout, no retries or repairs, and at most one application-controlled read-only query.

The overlay uses Linux host networking and explicitly binds the app to `127.0.0.1:8766` and the model to `127.0.0.1:8000`. It removes the base Compose port mapping. It does not expose either API publicly or change the configured browser-origin allowlist. App data and model downloads use separate persistent named volumes.

The planner provider is `api`. Its `nim_chat` setting names the existing `guided_json`/`max_tokens` request format, which this vLLM release also accepts; it does not identify the serving implementation as NIM. The current-source agent and older planner share that transport while using separate controllers. The new agent does not use the legacy planner protocol; retired verifier workflows remain in the research archive.

The optional Nano tool-format investigation found that vLLM 0.8.5 implements
`response_format.type=structural_tag` in its V1 XGrammar backend, while the
configured V0 backend has no corresponding grammar branch. It cannot be added
to the current deployment as a request-only change. See the
[pinned engine compatibility gate](literature/CONSTRUCTION_PLANNING_REUSE_20261026.md#pinned-engine-compatibility-gate)
for the version-specific source evidence and subsequent bounded checks. The
deployed engine remains V0; the separate V1 diagnostic is recorded below.
This limits a proposed decoder remedy; it does not explain
the previous unconstrained tool-interface errors, which never requested that
decoder.

The subsequent [CPU compatibility check](evaluations/structural_tag_cpu_20261026_summary.json)
passed in the exact cached image without GPU access or a model server. It
verified request conversion, V1 validation and synthetic grammar behavior.
The subsequent [isolated V1 diagnostic](evaluations/nemotron_v1_structural_probe_20261026_summary.json)
also passed startup with the cached pinned model and completed two requests:
the supported example returned its expected arguments, and the clinical example
returned no call and text declining treatment selection. The temporary server
used explicit chunked prefill with 2,048 batch tokens and disabled prefix caching.
It was removed afterward; the original V0 service was restored and verified
healthy. This demonstrates bounded serving/format compatibility, not general
planning improvement or a production engine migration. No graph was constructed.

For the legacy one-call planner, the overlay explicitly enables `BIOGRAPH_PLANNER_PROTOCOL=scoped_targets_v4`: [exact entity binding, target scope and per-tool shapes](PLANNER_PROTOCOL.md). `catalogue_v1`, `entity_tools_v2` and `tool_shapes_v3` remain selectable for reproducing the earlier experiments. The model revision, reasoning profile and serving budgets are unchanged by this protocol selection.

NVIDIA's Nano v1 model instructions reserve the system message for `detailed thinking off` and place task instructions in the user message. `BIOGRAPH_PLANNER_PROMPT_PROFILE=nemotron_nano_v1` applies that explicit format, retaining the complete planner policy and delimited untrusted catalogue. The default `standard` profile preserves the existing message format for other models. The selected profile and complete request hash are recorded in model traces; private reasoning is not requested or stored.

## Start and inspect

On the Brev VM, from the project directory with its existing private `.env`:

```bash
docker compose -f compose.yaml -f compose.brev-local-model.yaml up -d --build
docker compose -f compose.yaml -f compose.brev-local-model.yaml ps
docker compose -f compose.yaml -f compose.brev-local-model.yaml logs --tail 30 local-model
curl --fail http://127.0.0.1:8000/health
docker compose -f compose.yaml -f compose.brev-local-model.yaml exec -T steward python app.py runtime-check
```

Use both Compose files when recreating this deployment. The model initially downloads roughly 16 GB of weights; a healthy app or a valid planner configuration alone does not establish model readiness. Check the model health endpoint before requesting inference. The optional `BIOGRAPH_VLLM_IMAGE` override changes the serving identity and requires a new deployment/evaluation record.

Keep the existing Mac-to-Brev SSH forward and open `http://127.0.0.1:8767/`. After selecting an authorized saved run, use **Agent workflow** for the current-source controller. The older experimental planner remains separate. A shared saved-data reviewer installation disables both live routes and can replay recorded agent jobs instead. Deterministic guided questions remain available.

## Check the deployment

For the current-source controller, use `source-agent-catalogue`,
`source-agent-run` and `source-agent-verify` as described in the
[operator guide](SOURCE_AGENT.md). Catalogue and verification make no model
calls. Live run status, exact source bindings and real-versus-injected provider
identity are recorded; failed or partial attempts remain visible. The new
controller is evaluated separately from the legacy smoke check below.

Use `deployment-smoke --with-planner` with a new output directory for one synthetic integration check. A valid response that selects the wrong scope still fails the check. Do not turn a recorded failure into a successful receipt.

The planner's earlier comparison runners and results are in the [research archive](EXPERIMENT_HISTORY.md). Their scope-agreement scores do not establish scientific accuracy or graph improvement. The old INMC preparation and subsequent comparisons are completed, consumed work; see the [current scientific assessment](evaluations/SCIENTIFIC_DELIVERY_20261113.md). Ordinary source inspection, the CPU grounding evaluation and final delivery work do not need this model or GPU.
