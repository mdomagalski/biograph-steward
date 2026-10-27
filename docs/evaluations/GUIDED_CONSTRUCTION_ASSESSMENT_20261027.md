# Guided NVIDIA construction assessment

The existing JSON v3 planner and exact-selection guard can now be checked in a
separate bounded runner. The historical twelve-case comparisons, interfaces,
prompts and results remain unchanged. This closes a measurement gap: the old
runner does not exercise explicit form choices or the current guard.

Preparation and the failure controls are local. A live result must be recorded
separately after Brev is ready and the current runtime is checked. Preparation
does not establish that the model is running or that planning has improved.

## Reused implementation and documented limits

The runner invokes the current `ConstructionPlanner`, `guard_construction_trace`,
trace verifier and deterministic publisher. It adds no prompt, resolver,
classifier, model repair or source-retrieval path. The exact payload is captured
from the existing transport before any inference and bound into the freeze.

[vLLM 0.8.5 structured-output documentation](https://docs.vllm.ai/en/v0.8.5/features/structured_outputs.html)
documents `guided_json`; the [NVIDIA Nano v1 model card](https://huggingface.co/nvidia/Llama-3.1-Nemotron-Nano-8B-v1)
specifies the reasoning-off system message, user-message task instructions and
greedy decoding. Those upstream sources were rechecked on October 27. They
describe generation interfaces, not evidence that the planner understands these
tasks. The existing [reuse investigation](../literature/CONSTRUCTION_PLANNING_REUSE_20261026.md)
and [construction capability note](../CONSTRUCTION_AGENT.md) preserve the earlier
version-specific diagnosis and failed results.

The current guard checks a proposal **after inference**. It neither sends form
choices to the model nor repairs a proposal to match them. It can block a wrong
cohort, focus, profile or relation selection. A broad PPI proposal can still
match the form while ignoring a yeast-two-hybrid-only free-text condition.
That remains a task failure, even if the guard admits the proposal. The runner
reports that distinction explicitly; it does not propose another workaround.

## Declared tasks and interpretation

Eight literal cases are defined in
[`evaluate_guided_construction.py`](../../scripts/evaluate_guided_construction.py):

| Group | Requests | Purpose |
|---|---:|---|
| Supported, aligned form and question | 4 | Full-cohort interactions, shared pathways, both relations, and an explicit subset/focus |
| Conflicting form and question | 1 | Both relations requested in text while the form still selects PPI only |
| Unsupported text with ordinary PPI form | 2 | Assay-only filter and an unauthorized extra identity |
| Saved real two-protein cohort | 1 | One fixed CCNO/CDKN1A plan, followed by conditional source replay/publication parity |

The questions include already-consumed development examples. This is a new
assessment contract around those examples, **not a fresh holdout**. Form inputs
are literal declared caller choices. They are not generated from expected
answers, case IDs, model outputs or a question recognizer. Intent references
are separate; neither references nor form choices enter the model payload.

Report the raw model's intent agreement, exact form agreement, mismatches
blocked, and unsupported raw/admitted proposals separately. The four supported
aligned tasks have their own denominator. Invalid proposals, structured
abstentions and transport failures remain distinct. No composite accuracy score
is used as a biological or usability result.

Budget: **eight calls**, at most **1,600 output tokens each / 12,800 total**,
120 seconds per request, one call per case, no retries, repairs, fallback or
resumption. An interrupted run is preserved, including completed traces and
the pending request; an in-flight request may have been billed without a trace.

## Local preparation and execution

Use the current production V0 server. The experimental structural-tag tool
interface and its temporary V1 service are outside this assessment. Check the
existing instance and model health without restarting or downloading weights.
Use the established SSH forward from local port 8010 to the VM's loopback 8000.

```sh
export BIOGRAPH_PLANNER_MODEL=nvidia/Llama-3.1-Nemotron-Nano-8B-v1
export BIOGRAPH_PLANNER_ENDPOINT=http://127.0.0.1:8010/v1/chat/completions
export BIOGRAPH_PLANNER_API=nim_chat
export BIOGRAPH_PLANNER_PROMPT_PROFILE=nemotron_nano_v1
export BIOGRAPH_PLANNER_MAX_OUTPUT_TOKENS=1600
export BIOGRAPH_PLANNER_TIMEOUT=120
export BIOGRAPH_PLANNER_API_KEY=''

python3 scripts/evaluate_guided_construction.py prepare \
  --source-snapshot runs/assay_workbench_v2_20261026/snapshot.json \
  --out runs/guided_construction_live_20261027
```

The freeze preserves all eight inference payloads, declarations, code copies,
sanitized model settings and the unchanged saved source snapshot. It verifies
the original snapshot before and after execution. Choose a new output directory
for any separate assessment; never edit or reuse a consumed freeze.

After the freeze, record a **fresh read-only runtime observation**. Confirm the
actual image/container IDs, model and tokenizer revisions, served model ID,
health, vLLM/XGrammar versions, V0 engine and effective limits against
`manifest.json`'s `runtime_prerequisite`. Preserve allowlisted command results
and their SHA-256 values in `evidence_files`. Do not manufacture the observation
by copying expected fields without checking the actual server. The observation
and hashes document the caller's check; the runner cannot attest that the live
server remains unchanged.

The existing Brev CLI accepts a local script with `@`. The read-only observer
prints an allowlisted view; it does not restart the service or print credentials
or the full container environment:

```sh
brev exec biograph-steward-dev @scripts/observe_guided_construction_runtime.sh
```

Save that output as `runtime/observed_raw.json`. Build `runtime/observation.json`
from its `derived_observation` plus `evidence_files` containing the actual SHA-256
of the saved raw observation and a byte-for-byte copy of the observer script.
Check the actual image repository digest as well as the configured image string.
The remote observer labels local forwarded port 8010 as caller configuration;
check the local loopback forward independently before inference.

```sh
python3 scripts/evaluate_guided_construction.py run \
  --experiment runs/guided_construction_live_20261027 \
  --runtime-observation runs/guided_construction_live_20261027/runtime/observation.json

python3 scripts/evaluate_guided_construction.py score \
  --experiment runs/guided_construction_live_20261027
```

`score` re-derives results from preserved raw/guarded traces and verifies source,
implementation, runtime, payload and output bindings without inference or writes.
The HTML report keeps task intent and form agreement side by side. No inferred
cost is reported; usage excludes VM startup and idle billing.

## Conditional real-cohort demonstration

The final request is fixed to P22674/P38936, P22674 focus, PPI profile and
interactions. Publication is permitted only when that exact request passes the
current model verifier and guard. If the model abstains or mismatches, record
the outcome and perform no publication. There is no second attempt.

If it matches, the existing publisher verifies and replays the saved Pharos
exchanges in two publications: one carrying the real model/guard trace, and one
using the identical snapshot deterministically. The graphs, answer results and
citations must match. No network client is created and no new Pharos or IntAct
request is made. This is the **Pharos-only construction snapshot**; the separate
assay attachment is not silently included. Parity verifies that model selection
uses the same established transformation, not biological improvement or added
knowledge.

## Failure controls

[`test_guided_construction_evaluation.py`](../../tests/test_guided_construction_evaluation.py)
uses invented model and source responses. It checks inference-free preparation,
absence of references/choices in payloads, immutable attempts, conflicting choices,
unsupported free-text proposals that match the form, abstention before publication,
changed case/wire/code/source/configuration bindings, returned-model contradiction,
interruption, forged scores, changed artifacts, and stale/drifted runtime evidence.
Conditional graph and answer parity is checked with synthetic data only in these
tests. Passing these controls is software verification, not a live model result.

## Completed live result

The fixed assessment completed once on the existing NVIDIA Nano v1 / vLLM 0.8.5
V0 service. A fresh read-only observation matched the pinned model/tokenizer
revisions, actual image repository digest, XGrammar 0.1.18 and production limits.
Eight requests used 5,485 prompt and 528 completion tokens. There were no transport
errors, retries, repairs or new source calls. The
[machine summary](guided_construction_live_20261027_summary.json) binds the freeze,
runtime evidence, raw and guarded traces, offline scoring result and source check.

**Planning remains unreliable.** None of the four aligned supported tasks
succeeded. The model declined full-cohort PPI, pathways and the subset request.
For the combined interaction/pathway request it omitted pathways. The new guard
correctly blocked that mismatch before execution. This is one observed benefit
of the application check; it is not an improvement in model interpretation.

| Observed category | Result |
|---|---|
| Four aligned supported tasks | No successful task; three abstentions and one omitted relation |
| Aligned combined-relation request | PPI-only proposal blocked because the form required both relations |
| Conflicting form/text request | The same PPI-only proposal matched the form, but still failed the text request |
| Unsupported assay-only request | Explicit model abstention |
| Unauthorized extra identity | Invalid construction attempt with a duplicate allowed accession; rejected by the existing validator |
| Saved real-cohort request | Model abstention; no model-selected publication or parity run |

The one raw intent match was the unsupported assay abstention. The one form
agreement occurred on the deliberately conflicting request and **is not a
successful supported task**. The identity validator's rejection is not scored
as a correct semantic abstention. Zero admitted unsupported proposals on these
two examples cannot establish broader safety or understanding.

The separate local source check did verify the actual saved two-protein Pharos
snapshot: seven recorded exchanges, two nodes, one Pharos evidence edge and one
cited answer. Two deterministic publications matched and the original snapshot
bytes remained unchanged. That check made no model or source calls and did not
include the assay attachment. It must not be presented as agent-built graph
parity, because the live real-cohort plan abstained.

The frozen current runner re-derived all scores from saved traces offline after
the run. Independent local review confirmed the same outcome and image digest.
Historical JSON v3 and tool V2 outcomes remain unchanged. Keep deterministic
construction as the working path and the optional planner experimental. No
prompt tuning, model switch or repeated trial was performed. No
biological accuracy, graph improvement or intended-user success was measured.
The Brev model is no longer needed for this completed check.
