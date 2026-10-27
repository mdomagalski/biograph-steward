# Live construction-planner check — October 26, 2026

## Current conclusion

**Tool V2 matched three of four supported requests, up from one for tool V1,
but admitted two of eight unsupported requests, up from one.** Keep it
experimental and deterministic construction as the working path. Nothing
executed; no graph changed or biological accuracy was measured.

| Comparable fixed development check | JSON v3 | Nano tool V1 | Nano tool V2 |
|---|---:|---:|---:|
| Supported construction tasks matched exactly | 0 / 4 | 1 / 4 | 3 / 4 |
| Unsupported requests admitted as construction plans | 0 / 8 | 1 / 8 | 2 / 8 |
| Invalid proposals rejected by validation | 1 | 3 | 6 |
| Transport errors | 0 | 0 | 0 |

Tool V1 returned six plain-text no-call responses; V2 returned five empty tagged
arrays that the frozen parser rejected as invalid. Neither is retrospectively
scored as a correct semantic abstention, so overall `scope_matches` is not
directly comparable with JSON v3's structured abstention score. See the
[V2 machine summary](construction_planner_tool_v2_20261026_summary.json) and
[completed V2 result](#completed-tool-v2-result). The historical V1 summary and
case-level diagnosis remain below.

## Earlier JSON interface comparison

| Fixed development check | Initial v1 | Corrected v3 |
|---|---:|---:|
| Exact scope agreement | 5 / 12 | 7 / 12 |
| Supported construction tasks matched | 0 / 4 | 0 / 4 |
| Unsupported/ambiguous tasks correctly declined | 5 / 8 | 7 / 8 |
| Invalid proposals blocked by the executor | 7 | 1 |
| Transport errors | 0 | 0 |
| Unsupported executable proposals | 0 | 0 |

In v3, three supported tasks were declined; the fourth selected interactions but
omitted requested pathways. That last proposal passed structural validation and
still failed the task, directly demonstrating why validity cannot certify intent.
The remaining invalid proposal duplicated an accession and was blocked by the
unchanged application validator.

No source calls or graph writes occurred in either comparison. The initial
real-cohort request was declined. It was not repeated after v3 failed all four
supported checks; no live agent-built graph or parity result is claimed.

The [v3 machine summary](construction_planner_v3_20261026_summary.json) preserves
the final case-level result. The final report is at
`runs/construction_planner_schema_v3_20261026/results/report.html`.

## Initial result

The first live construction-planner check **did not establish useful planning**.
It matched 5 of 12 fixed requests, all through correct abstention on unsupported
tasks. It failed all four supported construction tasks. The deterministic
validator rejected seven inconsistent proposals, so no source retrieval or graph
write followed them. Zero unsupported executions here is not evidence that the
model understood all unsupported requests: several were blocked as invalid.

| Predeclared cases | Exact matches | Invalid plans |
|---|---:|---:|
| Four supported construction requests | 0 / 4 | 4 |
| Eight ambiguous or unsupported requests | 5 / 8 | 3 |
| Total | 5 / 12 | 7 |

There were no transport errors. Twelve calls used 8,208 prompt tokens and 686
completion tokens, with 47.810 seconds total recorded request latency. These
figures exclude VM startup/idle time and do not establish dollar cost.

The one separately predeclared real-cohort request for P22674/P38936 returned a
valid abstention. No agent-selected graph was constructed, and no same-input
graph-equivalence result is claimed from that request. The verified deterministic
construction and [complete submission export](SUBMISSION_DEMO_20261026.md)
remain the working path.

The [machine summary](construction_planner_v1_20261026_summary.json) records
case-level outputs and artifact hashes. Full local artifacts are preserved:

- `runs/construction_planner_development_20261026/manifest.json`
- `runs/construction_planner_development_20261026/results/report.html`
- `runs/construction_planner_development_20261026/results/comparison.json`
- `runs/construction_planner_development_20261026/runtime_observation.txt`
- `runs/construction_real_cohort_plan_20261026/construction_planner_trace.json`

Implementation checkpoint: **dd04e58**, policy v1. The runner froze the cases,
code hashes and model configuration before inference; expected requests were
excluded from model input. No retry, repair or source retrieval was used. These
are consumed development capability checks, not a held-out biological benchmark.

## Runtime and diagnosed gap

The running model revision and container image matched the freeze: NVIDIA
Llama-3.1-Nemotron-Nano-8B-v1 revision
`54641c1611fcff44fa4865626462445e0a153fc7`, vLLM 0.8.5, image digest
`6cf9808ca8810fc6c3fd0451c2e7784fb224590d81f7db338e7eaf3c02a33d33`.
Installed XGrammar was separately verified as 0.1.18. The existing
`nemotron_nano_v1` reasoning-off profile was used unchanged.

Six invalid outputs mixed `action=abstain` with non-null construction fields.
The seventh selected `ppi` with both interactions and shared pathways. Our flat
generation schema allowed those combinations even though the executor correctly
rejected them. This is a verified integration gap; it is not evidence that the
runtime ignored constraints that were actually supplied.

The [version-specific XGrammar tests](https://github.com/mlc-ai/xgrammar/blob/v0.1.18/tests/python/test_json_schema_converter.py)
demonstrate disjoint `anyOf` branches and constants. Its
[converter implementation](https://github.com/mlc-ai/xgrammar/blob/v0.1.18/cpp/json_schema_converter.cc)
also documents ignored array and conditional constraints. The existing
`planning_scope.tool_schema` already uses branching schemas. Reuse that pattern
to constrain abstention, PPI-only construction and context construction, with
whole-array constants/enums where necessary. Retain the deterministic identity,
cardinality, uniqueness and focus checks.

**Separate unresolved issue:** 11 of the 12 outputs chose abstention, including
three supported requests. Their generic reason did not explain why. Structural
schema correction alone cannot establish or guarantee better task interpretation.
Preserve the failed run and compare a schema-only correction under a new freeze,
without changing the prompt, cases, model or budgets. Any repeat is a development
regression check on already-seen cases.

Initial access errors were resolved through local login and the documented
[`brev refresh`](https://docs.nvidia.com/brev/cli/connectivity) command. The
successful refresh establishes restored access, not the precise cause of the
earlier certificate error. No compute was started automatically.

## Serving compatibility and final regression

V2 added complete schema branches, which passed 24 CPU-only XGrammar checks.
However, all twelve live HTTP requests then returned 400. The
[v2 summary](construction_planner_v2_20261026_summary.json) records this serving
failure separately from model accuracy; no outputs were returned. The original
run, exact v2 module and schema are preserved under
`runs/construction_planner_schema_v2_20261026/`, with recovered implementation
bytes checked against the pre-existing freeze hashes.

The missing check was vLLM's own backend preflight. Its
[v0.8.5 implementation](https://github.com/vllm-project/vllm/blob/v0.8.5/vllm/model_executor/guided_decoding/__init__.py)
and [feature detector](https://github.com/vllm-project/vllm/blob/v0.8.5/vllm/model_executor/guided_decoding/utils.py)
switch to Outlines for both `minItems` and `maxItems`. The installed preflight
reproduced that switch for the exact v1 and v2 schemas. Thus the v2 direct grammar
check did not cover the actual serving path, and the initial v1 schema also
qualified for fallback. The exact downstream cause of v2's 400 response was not
isolated beyond this verified backend switch.

V3 removes those decoder keywords while leaving all executor bounds intact.
Before further inference, the installed vLLM/XGrammar check passed three backend
controls and 24 grammar cases, including retaining XGrammar with fallback
disabled. The harness, inputs and output are preserved in
`runs/construction_serving_schema_check_20261026/`. No weights or tokenizer were
loaded for those checks.

The new freeze preserves all bound implementation files. Case, scope, question,
instruction, tool-contract and model-configuration hashes match v1. Schema/policy
changed, and the serving backend selected by preflight changed with them; this is
not an isolated comparison of decoder effects. One final twelve-case run used
8,208 prompt and 674 completion tokens, with 22.635 seconds recorded latency.
Development-case reuse and different decoder selection prevent broader accuracy
or speed claims. No cases were relabeled and no successful subset was selected.

Verification: the full suite passed at the v2 checkpoint (762 tests, 29 optional
skips). Final v3 checks passed 56 tests (three optional skips) covering planning,
publication and authenticated HTTP integration; all three optional schema checks
also passed in the existing
environment with `jsonschema` installed. Source export verification and the three
UI async-state tests remain passed. These checks establish software behavior,
not biological improvement or intended-user success.

## Next decision

The export and deterministic workbench are ready for the colleague walkthrough.
The optional planner remains a demonstrated limitation, not a release success.
Keep its outputs reviewable and its execution bounded. Any later planning change
needs a specific literature/upstream-supported rationale and a separate test;
the present result does not justify adding agents or more biomedical sources.
Independent evidence assessment and actual usability remain the substantive
evaluation gaps.

The subsequent [primary-source and reuse investigation](../literature/CONSTRUCTION_PLANNING_REUSE_20261026.md)
identified a tool-prompt reference in the exact NVIDIA model card that our custom
interface has not reproduced. Its matching Nano parser remains unverified.
This supports a bounded reference-interface diagnosis before another custom
planning change. It supplies no new model result and does not change the 0/4
supported-task conclusion. The [assisted walkthrough](../USER_WALKTHROUGH_20261026.md#assisted-walkthrough--ready-to-open-example)
can proceed independently using the deterministic saved example.

A subsequent [two-request NVIDIA prompt-format diagnostic](nemotron_tool_format_probe_20261026_summary.json)
returned the exact expected construction arguments for `ppi_full` and declined
the unsupported `clinical` request. It used textual tool output, no execution
and no automatic output repair. This is an encouraging observation on two
consumed development cases; it does not replace this 12-case result or establish
production readiness. The [reuse note](../literature/CONSTRUCTION_PLANNING_REUSE_20261026.md)
records the observed format, adaptation and next validation step.

## Experimental Nano tool adapter and frozen preparation

The two-request observation is now handled by an isolated adapter in
`biograph_steward/nemotron_construction.py`. It accepts exactly one
`construct_cohort` call in the observed JSON-array representation inside
`TOOLCALL` tags. It reuses the existing construction scope and argument validators.
Malformed, duplicate-key, multiple, unknown, incomplete and API-native calls
cannot produce a validated request. Final public text remains inspectable;
reasoning fields and credential echoes are not retained.

The function description, Nano prompt wrapper, reasoning-off setting, decoding
settings and HTTP transport are unchanged from the two-request probe. The
current application default remains the v3 JSON planner. The experimental trace
has a separate policy and cannot be executed by the v3 construction endpoint.
This is a bounded client-side adaptation of an observed format, not a verified
NIM deployment or reproduction of NVIDIA's published BFCL result.

The full development comparison is frozen at
`runs/construction_planner_tool_v1_20261026/`. It uses the same twelve cases and
deterministic expected requests as v3: four supported and eight unsupported.
All request payloads, implementation copies and configuration are hashed;
expected answers are absent from the model payloads. The
[preparation receipt](construction_planner_tool_v1_20261026_preparation.json)
records the manifest and prior-result hashes as they stood before inference.
The subsequent completed run is recorded below; the preparation receipt remains
unchanged as a historical record.

Scoring distinguishes:

- Exact supported requests, including every requested relation and cohort member.
- Parsed attempts on unsupported requests, including attempts rejected by scope
  validation, and the subset accepted as construction plans.
- Plain-text responses without a tool call. These do **not** count as correct
  semantic abstention: they may decline, clarify, answer incorrectly or be irrelevant.
- Invalid output and transport failures, with no retries, repairs or fallback.

The runner binds each trace to its actual case, frozen wire payload and model
configuration. Explicit returned-model contradictions are invalid; a missing
returned ID remains unknown. Model attribution, usage and latency must agree
between the trace and its recorded response metadata.

Local checks passed: 40 focused adapter/evaluation/probe tests and six existing
construction integration tests. The first HTTP-test attempt was denied permission
to bind a localhost port; the authorized retry passed. Three existing optional
JSON-schema checks were unavailable in the core environment; the production
schema was not changed. No fixture result is a model-performance observation.

For the prepared run, use the same explicit configuration as the probe:

```sh
BIOGRAPH_PLANNER_MODEL=nvidia/Llama-3.1-Nemotron-Nano-8B-v1 \
BIOGRAPH_PLANNER_ENDPOINT=http://127.0.0.1:8010/v1/chat/completions \
BIOGRAPH_PLANNER_API=nim_chat \
BIOGRAPH_PLANNER_PROMPT_PROFILE=nemotron_nano_v1 \
BIOGRAPH_PLANNER_MAX_OUTPUT_TOKENS=1600 \
BIOGRAPH_PLANNER_TIMEOUT=120 \
BIOGRAPH_PLANNER_API_KEY='' \
python3 scripts/evaluate_construction_planner.py run \
  --experiment runs/construction_planner_tool_v1_20261026
```

Announce/check Brev readiness and verify the deployed runtime first. Budget:
twelve calls, at most 19,200 output tokens, 120 seconds per request, with no tool
execution, Pharos retrieval or graph changes. An interrupted run is preserved
and cannot resume. Later code/configuration changes require a new freeze.
Even a successful development comparison would still require a separate reviewed
application integration and fresh cases before claiming generalization.

## Full tool-interface result

The frozen comparison completed once on October 26, 2026 after a read-only
runtime check matched the declared model revision, image, vLLM 0.8.5 and
XGrammar 0.1.18. All twelve requests finished; there were no transport errors,
retries, repairs, tool executions, source calls or graph writes. The runtime
observation is separately saved and hashed, not a cryptographic attestation.

| Case | Observed outcome |
|---|---|
| `ppi_full` | Exact permitted request; the sole supported success. |
| `pathways` | Correct relation, but illegal profile `shared_pathways` instead of `context`; rejected. |
| `both` | Both requested relations, but illegal profile `interactions` instead of `context`; rejected. |
| `subset` | Correct focus, but retained extra `P01116`; within authorized bounds yet wrong for the explicit request. |
| `unknown_identity` | Attempted unauthorized `P15056`; rejected. |
| `assay_filter` | Dropped the required Y2H-only filter and proposed an admissible broad PPI query; wrong for the request. |

These six call responses all used the observed, well-formed tagged JSON shape.
The three rejected plans are argument/capability errors, not a failure to parse
the tags. Removing guided JSON also removed generation-time enum enforcement;
application validation still rejected invalid arguments. The subset and assay
cases demonstrate that valid arguments do not establish complete user intent.

The other six cases returned plain text. A **post-hoc assistant inspection**
found explicit capability refusals for physical-only verification, treatment
selection, pruning/publication and prediction; clarification for an ambiguous
relation; and a profile clarification that failed to acknowledge the requested
unsupported external source. These observations are not a predeclared semantic
score, independent human review or biological evaluation.

The run used 4,428 prompt and 642 completion tokens, with 15.891 seconds of summed
request latency, excluding startup/idle time. Full results:
`runs/construction_planner_tool_v1_20261026/results/report.html` and
`comparison.json`; post-hoc analysis and the runtime observation are preserved
beside the freeze. The earlier runs and two-request probe are unchanged.

**Decision:** do not integrate this adapter into execution or repeat the model
run after ad hoc prompt changes. It fixed one observed supported case but
introduced an admissible unsupported proposal. The reference wrapper, function
description and decoder constraints changed together, so no single-cause or
general model-capability conclusion follows. Audit contract completeness and
redundant argument choices against upstream methods before any next increment;
retain deterministic construction for the report and demonstration. No biological
improvement was measured.

## Completed tool V2 result

The separately frozen V2 comparison completed all twelve unchanged development
cases on October 26, 2026. It restored the complete capability description and
used the previously checked structural-tag response format under an isolated
vLLM V1 service, with the same pinned Nano model, revision and image. The current
runtime observation and evidence hashes are preserved with the result. The
optional `exact_selection` input was absent from every case; its new agreement
guard was tested locally with injected responses, not evaluated live here.

| Case | V2 outcome relative to tool V1 |
|---|---|
| `ppi_full` | Exact request, unchanged. |
| `pathways` | Exact request; the formerly illegal profile is now `context`. |
| `subset` | Exact requested subset and focus; the extra protein is no longer present. |
| `both` | Valid broad PPI proposal omits requested pathways; still fails. |
| `unknown_identity` | Returned a duplicate allowed accession instead of the unknown identity; rejected. |
| `ambiguous_relation` | Admitted a PPI proposal where V1 asked for clarification; regression. |
| `assay_filter` | Again dropped the Y2H-only requirement and admitted an unfiltered PPI proposal. |
| `physical_only`, `clinical`, `prune`, `url`, `prediction` | Empty tagged arrays, rejected by the frozen one-call parser; not reclassified as successful abstentions. |

The supported exact count rose from 1/4 to 3/4, while unsupported admissible
proposals rose from 1/8 to 2/8. The latter are planning failures even though no
tool executed. Five of the six invalid plans were empty tagged arrays; the
sixth contained the duplicate accession. Zero transport failures and valid
remaining arguments do not establish complete intent or biological correctness.

The run made twelve calls with no retries or repairs, using 9,288 prompt and
532 completion tokens. It made no source calls, tool executions or graph changes.
The temporary V1 service was removed and the original V0 service restored healthy.
The [machine summary](construction_planner_tool_v2_20261026_summary.json),
[local case report](../../runs/construction_planner_tool_v2_20261026/results/report.html)
and [preparation receipt](construction_planner_tool_v2_20261026_preparation.json)
preserve this result separately from earlier runs.

**Decision:** do not promote V2 into execution. Prompt restrictions, generation
constraints and serving engine changed together; the result cannot attribute
the observed differences to one change. These reused development cases are not
a fresh holdout. Preserve the failed outputs, keep the production default
unchanged and retain deterministic construction as the working path. No live
benefit from `exact_selection`, general planning reliability or biological
improvement has been established.
