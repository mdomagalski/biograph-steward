# Bounded question-to-construction planner

The construction planner translates a question and an explicitly supplied cohort
into one request for the existing deterministic Pharos constructor. The previous
question planner could query a saved graph but could not select a new construction
request. This adapter closes that workflow gap without adding a model framework,
identity resolver, evidence classifier or autonomous tool loop.

## Established capabilities reused

The deployed runtime is NVIDIA `Llama-3.1-Nemotron-Nano-8B-v1`, revision
`54641c1611fcff44fa4865626462445e0a153fc7`, served by vLLM `0.8.5`. The existing
[`JSONModelClient`](../biograph_steward/model_transport.py) already supports its
`guided_json` transport, bounded output, single request, no retries and no model
tools. The version-specific [vLLM structured-output documentation](https://docs.vllm.ai/en/v0.8.5/features/structured_outputs.html)
documents JSON Schema constrained generation. NVIDIA's [official model card](https://huggingface.co/nvidia/Llama-3.1-Nemotron-Nano-8B-v1)
specifies the reasoning-mode system message and greedy decoding for reasoning off.
The existing `nemotron_nano_v1` profile retains those settings. This is a vLLM
deployment of the NVIDIA model; it is not a verified NIM deployment.

The adapter also reuses the existing HTTP provider options and isolated Codex
transport when explicitly configured. It introduces no new API key or serving
service. Existing configuration and licenses remain applicable; see
[local model](LOCAL_MODEL.md) and [portability](PORTABILITY.md).

Documented capability: constrained JSON output. Verified local integration:
exact field, identity, profile and relation checks; trace binding; single-call
transport and failure handling with injected responses. Unresolved until a live
comparison: whether the configured model consistently interprets questions and
abstains for unsupported conditions. Schema validity cannot establish that.

## Input and permitted selection

The caller supplies exactly:

```json
{
  "question": "Retrieve interaction candidates only among P04637 and P00533, focused on P00533.",
  "accessions": ["P04637", "P00533", "P01116"],
  "focus_uniprot": "P04637"
}
```

The scope contains 1–25 unique exact UniProt accessions and an in-scope default
focus. There is no symbol or synonym substitution. A question can explicitly
select a subset or another focus within that scope. Otherwise the full supplied
cohort and default focus are requested. The model can select:

- `ppi` with `interactions`;
- `context` with `shared_pathways` and/or `interactions`;
- abstention, without an executable request.

The existing constructor owns the fixed retrieval limits, source adapter,
exact-identity checks, cohort-limited PPI retention and source provenance.
The model cannot add identifiers, change limits or source URLs, run code,
review/prune evidence, create confidence scores or publish externally. Source
evidence remains candidate evidence. In particular, a Pharos interaction is not
necessarily direct physical binding, and absence of an annotation is not a
biological negative.

The prompt requires abstention for ambiguous or unsupported tasks, including
clinical/variant interpretation, predictions, arbitrary source ingestion and
assay or physical-binding-only filters. **The deterministic validator enforces
the permitted operation and identity scope; it does not prove that a permitted
operation satisfies an arbitrary natural-language question.** That limitation
must remain visible in the UI, review and comparison results.

## Callable integration

Implementation: [`construction_planning.py`](../biograph_steward/construction_planning.py).

- `validate_construction_scope(scope)` rejects invalid input before inference.
- `configured_construction_planner(provider=None, model=None).plan(scope)` makes
  one configured model call and returns a sealed trace.
- `verify_construction_plan_trace(trace)` checks the trace and returns a
  canonical deterministic construction request, or `None` for abstention/error.
- `save_construction_plan(trace, path)` preserves a standalone outcome without
  overwriting an earlier file.
- `fixed_construction_cases()` returns the predeclared development cases.
- `compare_construction_cases(planner, cases=None)` performs one model call per
  case, without any source retrieval or retry.

The publication layer calls `verify_construction_plan_trace` before source
retrieval and binds `construction_planner_trace.json` into the publication
receipt. The receipt distinguishes model selection from deterministic execution
and labels injected test transports separately from live inference. The trace
and manifest binding survive assay attachment, review, replay and source-packet
export. A planning trace alone never claims that construction occurred.

## Use the complete flow

In the **Build from a protein cohort** form, supply exact accessions and a focus,
then open **Let the agent choose a retrieval plan**. Enter the question and use
**Plan from question**. Inspect the selected proteins, profile and relations
before choosing **Build planned graph**. An abstention or failed plan cannot
retrieve evidence. Changing the scope or opening another graph clears the plan.

The equivalent command-line steps use the existing model environment settings:

```sh
python3 app.py construction-plan \
  --accessions P22674 P38936 --focus-uniprot P22674 \
  --question 'Retrieve reported interaction candidates among this cohort, focused on P22674.' \
  --out runs/cohort_plan
python3 app.py construction-execute \
  --plan runs/cohort_plan/construction_planner_trace.json \
  --out runs/planned_cohort
python3 app.py construction-verify --run runs/planned_cohort
```

Use new directories; earlier runs are immutable. Preparation and verification
need no model, but `construction-plan` makes one call to the explicitly
configured model. The resulting graph remains candidate source evidence.

Traces preserve the exact scope/question, proposed and validated plan, selected
construction request, model/provider identifiers, returned usage, latency, schema
and request hashes, and transport guards. No private model reasoning, credentials
or inferred financial price are stored. Digest checks detect alteration; they
are not signatures or scientific validation.

## Fixed comparison and interpretation

The twelve small cases cover the full cohort, pathways, both relations, an
explicit subset/focus change, unknown identifiers, an ambiguous request,
physical-binding-only evidence, clinical advice, pruning, arbitrary URLs,
prediction and an assay filter. Each has an explicit deterministic request or
expected abstention. Expected values never enter the model payload.

Freeze the case JSON and its digest **before** live inference. The comparison
records exact scope agreement, invalid output, provider errors, and cases in
which a construction was proposed despite expected abstention. It records usage
and latency through each trace. These are development capability checks, not a
held-out scientific benchmark; do not describe them as biological accuracy,
graph improvement or a fair timing comparison against an NLP-free explicit form.

Local tests use invented model responses, including a deliberately wrong but
schema-valid physical-binding plan: that case must fail scope agreement. They
do not establish live model performance. Before the live comparison, tell the
user the exact inference work needed so they can start Brev. No Brev GPU or AWS
service is needed to run local contract tests or prepare fixed cases.

The [frozen runner](../scripts/evaluate_construction_planner.py) saves each
completed trace immediately and rejects changed code, cases or model settings:

```sh
python3 scripts/evaluate_construction_planner.py prepare --out runs/construction_planner_check
python3 scripts/evaluate_construction_planner.py run --experiment runs/construction_planner_check
```

The first command makes no inference calls. The second makes twelve. Results
are preserved on interruption; there is no automatic retry or result overwrite.

```bash
python3 -m unittest discover -s tests -p test_construction_planning.py -v
```
