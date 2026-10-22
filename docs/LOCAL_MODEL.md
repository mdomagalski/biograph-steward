# Local Nemotron planner on Brev

The Linux-only `compose.brev-local-model.yaml` overlay connects the existing app to NVIDIA's publicly downloadable [Llama-3.1-Nemotron-Nano-8B-v1](https://huggingface.co/nvidia/Llama-3.1-Nemotron-Nano-8B-v1), served by [vLLM](https://docs.vllm.ai/en/v0.8.5/deployment/docker.html). This is a vLLM deployment of an NVIDIA model, not an NVIDIA NIM deployment. It requires no hosted inference API or NGC download key. The model's license and upstream notices remain applicable.

## Fixed configuration

- Model and tokenizer revision: `54641c1611fcff44fa4865626462445e0a153fc7`.
- Server: vLLM `0.8.5`, image digest `sha256:6cf9808ca8810fc6c3fd0451c2e7784fb224590d81f7db338e7eaf3c02a33d33`.
- Verified container runtime: PyTorch `2.6.0+cu124`, CUDA `12.4`, on the VM's NVIDIA L40S and driver `565.57.01`.
- BF16 weights, 16,384-token context, one concurrent sequence, 75% GPU-memory budget, eager execution and guided JSON output. These are configured limits, not a throughput benchmark.
- Planner: one request, at most 1,600 output tokens, 120-second timeout, no retries, no repair calls and at most one application-controlled read-only query.

The overlay uses Linux host networking and explicitly binds the app to `127.0.0.1:8766` and the model to `127.0.0.1:8000`. It removes the base Compose port mapping. It does not expose either API publicly or change the configured browser-origin allowlist. App data and model downloads use separate persistent named volumes.

The planner provider is `api`. Its `nim_chat` setting names the existing `guided_json`/`max_tokens` request format, which this vLLM release also accepts; it does not identify the serving implementation as NIM. The active integration is the bounded planner; retired source-verifier workflows belong to the research archive.

The current overlay explicitly enables `BIOGRAPH_PLANNER_PROTOCOL=scoped_targets_v4`: [exact entity binding, target scope and per-tool shapes](PLANNER_PROTOCOL.md). `catalogue_v1`, `entity_tools_v2` and `tool_shapes_v3` remain selectable for reproducing the earlier experiments. The model revision, reasoning profile and serving budgets are unchanged by this protocol selection.

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

Keep the existing Mac-to-Brev SSH forward and open `http://127.0.0.1:8767/`. After selecting a saved run, the existing experimental question planner uses this local model. Deterministic guided questions remain available separately.

## Check the deployment

Use `deployment-smoke --with-planner` with a new output directory for one synthetic integration check. A valid response that selects the wrong scope still fails the check. Do not turn a recorded failure into a successful receipt.

The planner's earlier comparison runners and results are in the [research archive](EXPERIMENT_HISTORY.md). Their scope-agreement scores do not establish scientific accuracy or graph improvement. Current scientific work is [INMC input preparation](evaluations/INMC_INPUT_READINESS_20261022.md), which does not need this model or GPU.
