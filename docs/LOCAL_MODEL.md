# Local Nemotron planner on Brev

The Linux-only `compose.brev-local-model.yaml` overlay connects the existing app to NVIDIA's publicly downloadable [Llama-3.1-Nemotron-Nano-8B-v1](https://huggingface.co/nvidia/Llama-3.1-Nemotron-Nano-8B-v1), served by [vLLM](https://docs.vllm.ai/en/v0.8.5/deployment/docker.html). This is a vLLM deployment of an NVIDIA model, not an NVIDIA NIM deployment. It requires no hosted inference API or NGC download key. The model's license and upstream notices remain applicable.

## Fixed configuration

- Model and tokenizer revision: `54641c1611fcff44fa4865626462445e0a153fc7`.
- Server: vLLM `0.8.5`, image digest `sha256:6cf9808ca8810fc6c3fd0451c2e7784fb224590d81f7db338e7eaf3c02a33d33`.
- Verified container runtime: PyTorch `2.6.0+cu124`, CUDA `12.4`, on the VM's NVIDIA L40S and driver `565.57.01`.
- BF16 weights, 16,384-token context, one concurrent sequence, 75% GPU-memory budget, eager execution and guided JSON output. These are configured limits, not a throughput benchmark.
- Planner: one request, at most 1,600 output tokens, 120-second timeout, no retries, no repair calls and at most one application-controlled read-only query.

The overlay uses Linux host networking and explicitly binds the app to `127.0.0.1:8766` and the model to `127.0.0.1:8000`. It removes the base Compose port mapping. It does not expose either API publicly or change the configured browser-origin allowlist. App data and model downloads use separate persistent named volumes.

The planner provider is `api`. Its `nim_chat` setting names the existing `guided_json`/`max_tokens` request format, which this vLLM release also accepts; it does not identify the serving implementation as NIM. The verifier remains separately configured and is not enabled by this planner-only overlay.

The current overlay explicitly enables `BIOGRAPH_PLANNER_PROTOCOL=tool_shapes_v3`: [exact entity binding, per-tool shapes and scope checks](PLANNER_PROTOCOL.md). `catalogue_v1` and `entity_tools_v2` remain selectable for reproducing the earlier experiments. The model revision, reasoning profile and serving budgets are unchanged by this protocol selection.

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

## Evaluate without changing the sources

Use `deployment-smoke --with-planner` once for a small synthetic integration check. A valid model response that selects the wrong scope still fails that check; do not turn a recorded failure into a successful receipt.

For a development comparison, initialize a new suite using the current engine and the unchanged public-source snapshots, then run:

```bash
docker compose -f compose.yaml -f compose.brev-local-model.yaml exec -T steward \
  python app.py evaluation-run --suite /data/runs/YOUR_NEW_SUITE \
  --planner live --out /data/runs/YOUR_NEW_RESULTS
```

The runner issues one model request for each question and retains invalid plans, errors and abstentions. Compare the planner with the deterministic `enriched` arm on the exact same graph and display budgets. Agreement with draft scope plans is an engineering diagnostic. Citation identity and unchanged source hashes do not establish whether a scientific claim is true; leave scientific judgments pending until source review. The supplied 24 questions are development scenarios, not a held-out biomedical benchmark.

See [the evaluation protocol](EVALUATION.md) for frozen-suite creation, case families, reviewer sheets and metric definitions. A prompt, model, engine or source change needs a new recorded experiment; retain earlier failures and results.

## Stop or revert

To release GPU memory without deleting its model cache:

```bash
docker compose -f compose.yaml -f compose.brev-local-model.yaml stop local-model
```

That stops model inference, not VM compute billing. Stop the Brev instance when it is no longer needed. To return the app to its base deployment, stop `local-model` and recreate `steward` with `docker compose -f compose.yaml up -d --build steward`. Neither operation requires removing the persistent volumes.
