# Live construction-planner check — October 26, 2026

## Current conclusion

**The documented schema/runtime correction improves output consistency, but
useful construction planning is still not demonstrated.** Keep the optional
planner experimental and use explicit cohort selection as the working path.
No automatic construction or further prompt/model sweep was introduced.

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
