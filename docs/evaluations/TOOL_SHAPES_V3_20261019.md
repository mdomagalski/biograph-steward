# Tool-shape protocol v3 development comparison — October 19, 2026 (EDT)

The same Nemotron model on the same Brev L40S now produces useful bounded plans with the revised hybrid planning protocol. All 24 development plans matched the draft scope references; all 16 executed queries reproduced the enriched deterministic outputs. This demonstrates recovery of the supported workflow on reused cases. It does not establish unseen-question performance, scientific correctness or improvement to the biological graph.

| Outcome | Original v1 | Entity/tool v2 | Tool-shape v3 |
|---|---:|---:|---:|
| Development questions / live requests | 24 / 24 | 24 / 24 | 24 / 24 |
| Draft scope matches | 8 (33.3%) | 6 (25.0%) | 24 (100%) |
| Answered | 0 | 8 | 14 |
| No evidence | 0 | 1 | 2 |
| Abstained | 24 | 0 | 8 |
| Invalid plans blocked | 0 | 15 | 0 |
| Read-only query calls | 0 | 9 | 16 |

The [original failure](NEMOTRON_20261019.md) and [v2 failure](ENTITY_TOOLS_V2_20261019.md) remain unchanged. V2 passed its synthetic preflight but failed the full comparison; it is not counted as a successful intermediate result.

## What changed and why

The original responses demanded identifiers already resolvable from supplied symbols, confused requirements of protein and CIViC tools, and declined candidate inspection. V2 added exact entity binding and per-tool instructions. Its full comparison exposed cross-tool field contamination, incorrect evidence views and an unsupported causal request reaching a query. These are observations about returned outputs, not claims about the model's internal reasoning or a GPU fault.

V3 retains the exact resolver and focused contracts, then supplies separate output shapes for abstention, protein-neighborhood and CIViC queries. Irrelevant fields are fixed to null or empty. Complete molecular profiles retain AND/OR/NOT; unknown or ambiguous identities do not silently become gene-level queries. Candidate and accepted views remain distinct. The application independently validates bindings and scope after generation, without repairing or retrying a wrong plan. See the [protocol specification](../PLANNER_PROTOCOL.md).

Conservative lexical capability checks also constrain the family, view and explicit relations. **Eight development requests receive an abstention-only schema from application rules**; on the remaining 16 the model can query or abstain. Thus the 24/24 result measures the hybrid system, not independent model tool-selection ability. Neither the resolver nor the rules receive case IDs or reference plans. They were iteratively developed using these same cases, and unfamiliar wording, synonyms and complex negation remain limitations.

The model received application-owned, versioned instructions and tool contracts. No standalone skills were fetched, and Codex's own skills are not automatically installed into the served model.

## Controls and verification

The experiment retained all 24 questions in 15 development groups, draft references, source snapshot bytes, review events and display budgets (eight results, three paths). The model, weight/tokenizer revision, server image, reasoning-off profile and inference budgets were unchanged. A new suite froze the changed implementation. There was one live model call per case, no automatic retry or repair, plus one separately recorded successful synthetic preflight.

The model was `nvidia/Llama-3.1-Nemotron-Nano-8B-v1`, revision `54641c1611fcff44fa4865626462445e0a153fc7`, served by vLLM 0.8.5 at image digest `sha256:6cf9808ca8810fc6c3fd0451c2e7784fb224590d81f7db338e7eaf3c02a33d33`. XGrammar 0.1.18 compiled all 24 output schemas before inference. This verifies the pinned server's schema support; other providers still require their own capability check.

All 48 Pharos/enriched deterministic outputs matched both the current local baseline and the original experiment. All 16 planner query outputs matched the current enriched arm after excluding only the arm's `source_run` label and the answer hash derived from that label. Saved-answer integrity checks passed. The two empty results remained explicit no-evidence outcomes; source snapshots and review states were unchanged. Exact citation/integrity checks do not adjudicate whether a paper supports a biomedical claim.

The core suite ran 258 tests successfully with one optional skip. The nine identity tests and eight new scope/schema tests also passed on Brev's Python 3.10. Median recorded request latency was 6.13 seconds (range 3.62–6.82); reported usage totaled 33,585 tokens across the 24 evaluation calls. These timings are descriptive, not a repeated performance benchmark.

## Records and limits

The [machine-readable summary](tool_shapes_v3_20261019_summary.json) contains every case outcome, forced-abstention flags and request/response hashes. Suite SHA-256: `569dd35372b910b3b9719597f79e32b0c348d66c77c7eb225705e6cfe15a3a5b`. Evaluation SHA-256: `5c92930a64a43c917585500978ec392d2070b284dbfb2908eb2379b5e9623898`.

Complete results and reviewer sheets are retained on Brev at `/data/runs/evaluation_tool_shapes_20261020/`, with the frozen suite at `/data/runs/tool_shapes_suite_20261020/`. The protected app serves the report at `/api/evaluation/evaluation_tool_shapes_20261020/`. Locally, active artifacts are under `runs/brev_tool_shapes_20261020/final_suite/`, `final_deterministic/` and `live/`. Earlier preparation-only directories remain retained and were not used for live v3 inference. Artifact names use UTC; this report uses the experiment's EDT date.

There are zero held-out cases and zero human-approved reference plans. Citation-support accuracy remains unknown, and `scientific_improvement_established` is false. Before expanding the agent workflow, freeze new question families that challenge aliases, complete profiles, negation, evidence views and unsupported requests, review their scope independently, and run the unchanged protocol once. Biological graph improvement still requires the separate controlled prediction experiment and source-level adjudication.
