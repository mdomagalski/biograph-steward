# Bounded question-to-construction planner

The construction planner translates a question and an explicitly supplied cohort
into one request for the existing deterministic Pharos constructor. The previous
question planner could query a saved graph but could not select a new construction
request. This adapter closes that workflow gap without adding a model framework,
identity resolver, evidence classifier or autonomous tool loop.

The [October 27 guided live assessment](evaluations/GUIDED_CONSTRUCTION_ASSESSMENT_20261027.md)
tested the current JSON v3 planner and explicit-selection guard. All eight
requests completed; none of the four supported tasks succeeded. The guard blocked
one incomplete proposal but did not improve model interpretation. The real-cohort
request abstained, so no agent-built graph is claimed. Keep this path experimental;
the deterministic constructor remains the working product path.

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

### Current contract and deployed decoder

Policy `biograph-steward.bounded-construction-planner.v3` uses separate complete
`anyOf` branches for abstention, PPI construction and context construction. It
reuses the branch pattern already in `planning_scope.tool_schema`; literal empty
arrays and whole-array relation enums prevent contradictory output shapes.

The [vLLM 0.8.5 feature detector](https://github.com/vllm-project/vllm/blob/v0.8.5/vllm/model_executor/guided_decoding/utils.py)
and [backend selection](https://github.com/vllm-project/vllm/blob/v0.8.5/vllm/model_executor/guided_decoding/__init__.py)
switch away from XGrammar for array item limits. The current schema omits those
keywords. Application code still enforces cohort cardinality, uniqueness, focus
membership and exact identity authorization before retrieval. The installed
vLLM 0.8.5 / XGrammar 0.1.18 preflight and grammar checks passed all 27 controls.

[XGrammar's version-specific tests](https://github.com/mlc-ai/xgrammar/blob/v0.1.18/tests/python/test_json_schema_converter.py)
and [converter](https://github.com/mlc-ai/xgrammar/blob/v0.1.18/cpp/json_schema_converter.cc)
support these branch/constant patterns. Direct grammar checks alone do not cover
the serving layer's backend selection; both checks are required.

The [live development result](evaluations/CONSTRUCTION_PLANNER_20261026.md)
improved from 5/12 to 7/12 scope matches and reduced invalid plans from seven to
one, but **all four supported construction tasks still failed**. Three were
declined and one omitted requested pathways. The planner remains experimental;
useful task selection is unproven. Schema validity cannot establish intent.

The first experimental Nano tool interface matched **1/4 supported requests**
but admitted one of eight unsupported requests as an unfiltered construction
plan. Its six plain-text no-call responses remain separately unscored for
semantic success. This result does not justify replacing v3; the two interfaces'
aggregate scope-match counts do not measure identical abstention behavior. See
the same evaluation note for preserved inputs, failures and the bounded comparison.

The completed tool V2 comparison matched **3/4 supported requests**, but admitted
**2/8 unsupported requests**, versus 1/8 for tool V1. The combined interaction and
pathway request still lost its pathways; an ambiguous request and an assay-only
request became admissible broad PPI proposals. This mixed result does not justify
promoting V2 to production. The [V2 summary](evaluations/construction_planner_tool_v2_20261026_summary.json)
preserves the distinction between improved supported-task agreement and remaining
unsafe proposals. No construction executed and no biological accuracy was measured.

The evaluation note preserves the initial v1 failure and the intermediate v2
serving rejection, exact source snapshots and unchanged case/prompt/model
bindings. V1 traces require checkpoint `dd04e58`; v2 has its preserved module.
Current verification does not silently reinterpret old traces. Other providers'
schema restrictions require separate endpoint validation.

The adapter also reuses the existing HTTP provider options and isolated Codex
transport when explicitly configured. It introduces no new API key or serving
service. Existing configuration and licenses remain applicable; see
[local model](LOCAL_MODEL.md) and [portability](PORTABILITY.md).

Documented capability: constrained JSON output. Verified local integration:
exact field, identity, profile and relation checks; trace binding; single-call
transport and failure handling with injected responses. Live checks found
unreliable task selection despite the structural repair. Intended-user usefulness
and broader model performance remain unproven.

## Current guided form and execution check

The protein-cohort form now defines the exact cohort, focus, evidence profile
and answer relations. A subset request requires editing those form choices.
The experimental question planner still uses the unchanged JSON v3 model
prompt and provider; the Nano tool V2 interface has not been promoted.

The new [`guided_construction.py`](../biograph_steward/guided_construction.py)
wrapper validates the complete explicit selection before inference, preserves
the original model trace and compares the canonical model request with the
selection. A mismatch is recorded as a blocked plan with the model proposal
visible; no request is rewritten or executed. The UI presents **Your exact
selection** alongside **Model proposal** and requires **I reviewed the selected
proteins, evidence and proposed plan** before enabling **Build reviewed plan**.
This is review of retrieval choices, not a request for biological expertise.

`POST /api/construction-plan` requires the ordinary question, accessions and
focus plus `exact_selection`. `POST /api/construct` in planned mode requires the
saved `plan_id`, current `exact_selection` and `plan_reviewed: true`. The server
re-verifies the saved trace and current choices before source access. Changing
the cohort, focus, profile, relations, question or refresh choice clears the
plan and review; late responses cannot restore a stale plan. The direct
deterministic form remains available independently of model planning.

Policy `biograph-steward.guided-construction-selection.v1` has its own digest and
binds the guard implementation hash, the original v3 trace and supplied choices.
The existing verifier dispatches this policy to the wrapper while preserving
old trace semantics. The 36 preserved development traces still verify. Existing
model-planned publication receipts also bind `construction_planning.py`, so
replaying an older publication can require its original code checkpoint; that
code-hash boundary predates this wrapper. The local review found no persisted
model-planned publications affected by this increment. Digests provide integrity
checks, not signatures or scientific truth.

Injected-response helper, HTTP and JavaScript tests cover matching, mismatched,
unreviewed and stale choices, with invalid inputs rejected before model or
source calls. These are local integration checks. The twelve-case live V2
comparison supplied no exact selections and did not exercise this wrapper;
its **3/4 supported** and **2/8 unsupported admitted** results remain unchanged.

The form discloses unsupported assay, organism, disease and physical-binding-only
filters, predictions and clinical recommendations. Agreement with explicit
choices does not verify arbitrary conditions in the free-text question: a broad
PPI plan can match the form while overlooking an assay condition. Neither the
wrapper nor its review checkbox establishes semantic correctness or biological
accuracy. Live contribution and intended-user usability remain unmeasured.

## V1 serving compatibility and experimental tool V2

The [tool-interface diagnosis](literature/CONSTRUCTION_PLANNING_REUSE_20261026.md#full-comparison-diagnosis-and-existing-remedies)
separates missing generation constraints, omitted capability restrictions and
incorrect interpretation of an authorized cohort. They require different checks.
The [pinned-engine compatibility gate](literature/CONSTRUCTION_PLANNING_REUSE_20261026.md#pinned-engine-compatibility-gate)
records that the current compose configuration pins `VLLM_USE_V1=0`; vLLM 0.8.5's
structural-tag serving path requires V1. The installed CPU controls and a
separately frozen [two-request live diagnostic](evaluations/nemotron_v1_structural_probe_20261026_summary.json)
have now passed in an isolated V1 service using the same pinned image, Nano revision
and BF16 weights. The PPI response contained the exact original cohort, focus,
profile and relation arguments. The clinical response contained a refusal and
no tool call; the parser records `no_call_text`, without an independent semantic
success score. Both are previously consumed development cases. The only request
change was the CPU-verified structural `response_format`; the tool description
was deliberately unchanged. Both final texts exactly match the earlier
unconstrained two-request probe, so these examples show no answer improvement.

The diagnostic used V1 chunked prefill with a 2,048-token batch limit and prefix
caching explicitly off, recording those differences from the V0 reference.
The temporary V1 service was removed and the original V0 service restored
healthy. This closed the tested serving-compatibility gate without changing the
then-current **1/4 supported-request** result. It did not establish broader
planning accuracy or biological improvement. No graph construction occurred.

The compatibility check itself did not implement a new adapter or change the
production trace policy. The subsequent separate experimental interface
`nemotron_tool_v2` is now implemented locally in
[`nemotron_construction_v2.py`](../biograph_steward/nemotron_construction_v2.py).
The existing v3 model default remains unchanged. The current form adds the
separate explicit-selection wrapper described above.
V2 restores the complete capability contract:
ambiguous or unknown identities; clinical, therapy, variant or causal interpretation;
prediction; organism, disease, assay or physical-binding-only filters; evidence
truth, calibrated confidence, acceptance or pruning; arbitrary sources, URLs,
code execution and external publication. It explicitly forbids replacing an
unsupported requirement with a nearby supported request. These are capability
rules, not a claim that a prompt enforces arbitrary language semantics.

V2 reuses the structural `response_format` checked in the CPU and two-request
live diagnostics. The strict parser remains necessary: the grammar allows
ordinary no-call text and does not enforce the one-call envelope, cohort
cardinality, uniqueness or focus membership. The subsequent twelve-case V2
comparison is recorded below, separately from these compatibility observations.

Optional `exact_selection` is an explicit caller input distinct from the
authorized identity scope. V2 validates it with the existing constructor,
including focus membership, and requires the returned request to agree with the
selected cohort, focus, profile and relations. It rejects mismatches without
rewriting the model output. The experimental module's check remains separate
from the current UI/API wrapper, which binds unchanged v3 proposals to explicit
form choices. The revised form declares the cohort and retrieval controls exact;
a user must edit them before requesting a subset. Even an explicit lock cannot
detect every unsupported requirement in
free text: an unfiltered PPI plan can match the controls while ignoring an assay
condition. Preserve plan inspection and disclose that limitation.

An evaluation with explicit selections measures a different, user-assisted task.
Never populate those inputs from `expected_request`, expected action, case IDs or
a recognizer tailored to the twelve exposed questions. Keep their historical
inputs, wires, traces and failed outcomes intact; they remain development
regressions, not a fresh holdout. Any selection-bound evaluation needs separately
declared inputs and interpretation. Compare supported exact selections, rejected
outputs and unsupported proposals separately. Plain-text no-call responses stay
unscored for semantic success unless a separate assessment establishes it.

Do not repair illegal profile values automatically. The constructor permits
`context + interactions`, which retrieves more source families than `ppi`;
mapping a relation label into a profile can therefore change retrieval scope.
Local V2 checks passed for contract exclusions, explicit-selection mismatch,
profile/relation compatibility, exact trace/input binding and preservation of
prior interfaces. All twelve historical V1 traces still verify. The unchanged
development cases and new requests were [frozen before the live comparison](evaluations/construction_planner_tool_v2_20261026_preparation.json).
No `exact_selection` was supplied in that historical comparison. At that checkpoint,
the agreement guard and guided UI/API had only local injected-response coverage.
The separate October 27 guided assessment above now measures the current guard.

The experimental module exposes `validate_scope(scope)`,
`NemotronConstructionPlannerV2(client=None).request(scope)` for an inference-free
wire request, and `.plan(scope)` for one bounded model call.
`verify_nemotron_construction_trace_v2(trace)` rechecks the exact input, wire and
parsed selection; `save_nemotron_construction_trace_v2(trace, path)` preserves it
without overwriting an earlier trace. To lock an explicit choice, add this field
to the ordinary question/authorized-cohort/default-focus scope:

```json
{
  "exact_selection": {
    "accessions": ["P04637", "P00533"],
    "focus_uniprot": "P00533",
    "profile": "ppi",
    "relations": ["interactions"]
  }
}
```

The complete selection must remain within the authorized cohort. A null or
partial selection is invalid. V2 traces cannot be executed through the existing
v3 construction endpoint. The caller must independently verify a compatible V1
server before invoking `.plan`; the module does not attest the serving engine.

The twelve-case comparison completed once with a newly recorded V1 runtime
observation and preserved evidence hashes. The [case report](../runs/construction_planner_tool_v2_20261026/results/report.html)
and [machine summary](evaluations/construction_planner_tool_v2_20261026_summary.json)
record three exact supported requests: full-cohort PPI, pathways and the requested
subset. The combined request still omitted pathways. Two unsupported requests
passed argument validation: the ambiguous relation now received a PPI plan, and
the assay-only restriction was again silently dropped. The unknown-identity case
returned a duplicate allowed accession and was rejected. Five other unsupported
cases returned empty tagged arrays; the frozen parser rejected them as invalid
plans. They are not retrospectively scored as correct abstentions.

All twelve requests completed, using 9,288 prompt and 532 completion tokens,
with no retries, repairs, source calls, tool execution or graph changes. The
temporary V1 service was removed and the original V0 service restored healthy.
Prompt contract, generation constraints and serving engine changed together;
this consumed development set does not isolate their effects or establish
generalization. Keep the v3 model prompt/provider and deterministic constructor
as the current execution path, with the new guided selection check around the
optional model proposal.
A separate user-assisted evaluation is needed to assess explicit selections.

## Input and permitted selection

For the unchanged low-level v3 planner and CLI, the caller supplies exactly:

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

In the **Build from a protein cohort** form, supply exact accessions, focus,
evidence and answer connections, then open **Check a question against your exact
selections**. Enter the question and use **Check question and plan**. Compare
the selected proteins, evidence and connections with the model proposal. If
they match and represent the supported retrieval you intend, check the review
box and choose **Build reviewed plan**. An abstention, mismatch or failed plan
cannot retrieve evidence. Changing any relevant form choice or opening another
graph clears the plan and review.

The existing lower-level command-line steps retain their original v3 semantics
and model environment settings; they do not add the new UI review checkbox:

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
