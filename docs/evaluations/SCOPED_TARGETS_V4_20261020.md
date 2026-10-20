# Paired v4 planning regression — October 20, 2026 (EDT)

The first `scoped_targets_v4` run matched **26/32 scope plans (81.25%)**, compared with the preserved v3 control's **22/32 (68.75%)** on the exact same questions. Wrong-scope queries fell from **seven to zero** in this run. All **17 executed query outputs** matched the enriched deterministic outputs. The improvement comes with more unnecessary abstentions: **six supported questions were declined**, compared with two in v3.

These 32 cases informed v4 development. This is a **paired regression after tuning**, not an unseen benchmark, independent model test or demonstration of biological graph improvement. Keep deterministic guided questions as the working default; model planning remains experimental.

| Outcome | Preserved v3 control | First v4 run |
|---|---:|---:|
| Scope plans matched | 22/32 | 26/32 |
| Correct query scope on supported questions | 16/23 | 17/23 |
| Correct abstention on unsupported questions | 6/9 | 9/9 |
| Wrong-scope queries executed | 7 | 0 |
| Unsupported-reference questions reaching a query | 2 | 0 |
| Supported questions unnecessarily declined | 2 | 6 |
| Invalid plans blocked | 1 | 0 |
| Answered / no evidence / abstained | 21 / 2 / 8 | 16 / 1 / 15 |
| Read-only query calls | 23 | 17 |
| Equal enriched query outputs / comparable pairs | 16/21 | 17/17 |
| Entire paired families matched | 9/16 | 10/16 |
| Application-forced abstentions | 7 | 9 |
| Model requests / HTTP transport requests | 32 / 32 | 32 / 32 |

Eight formerly incorrect cases became correct, four formerly correct cases regressed, and two remained incorrect. All six v4 failures are unnecessary abstentions: their intended query plans pass both application validation and the output schema, and their `unsupported_requirements` lists are empty. V4 fixes the earlier application/reference conflicts; it does not make the small model consistently choose a supported query.

## What changed

The [v4 protocol](../PLANNER_PROTOCOL.md) retains raw exact mentions for the audit and separately selects requested targets. Bounded clause polarity handles explicitly negated relations, background therapies, negated all-profile requests and simple unsupported-action disclaimers. It rejects unknown compound-profile extensions case-insensitively before a contained known profile can become a query target, and checks exact source disease scope. Known whole AND/OR/NOT profiles remain intact. Tool shapes and independent post-generation checks remain in place; no generated plan is repaired.

The application now forces abstention for nine unsupported requests, leaving 23 query-or-abstain choices to the model. All draft query references are admissible. These are properties of the hybrid application, not an accuracy score for an unconstrained agent. Rules remain a bounded lexical interface and can misinterpret unfamiliar wording.

## Retained failures

| Case | Observed model behavior | Change from v3 |
|---|---|---|
| `fresh-symbol-id-symbol` | Declined the exact lowercase TP53 symbol with `insufficient_evidence`, before executing a query. | Regression |
| `fresh-double-negation-remove` | Restated the supported APC accepted-only query but returned abstention. | Regression |
| `fresh-relation-negation-interactions` | Treated exclusion of shared pathways as an unprocessed requirement, although the selected tool supports querying interactions alone. | Still incorrect |
| `fresh-or-profile-lower` | Cited `request_scope.unsupported_requirements` despite that list being empty; the complete known OR profile was correctly resolved. | Regression |
| `fresh-all-profile-negation-single` | Also cited the empty unsupported-requirements list, although only the named KRAS G12D profile was selected. | Still incorrect |
| `fresh-direction-scope-retain` | Declined a supported all-directions query with the explanation “No condition cannot be expressed by the tool.” | Regression |

The model does not see source evidence outcomes. An `insufficient_evidence` planning explanation therefore cannot establish an evidence gap; a valid query must run to determine that. Public explanations are retained for diagnosis and must not substitute for actual plan fields or execution records. These observations do not establish the model's internal cause of failure.

## Controls, attribution and checks

The comparison uses source commit `68e7f8d398b0af1eba456d1b3d308653f1719619`, packet SHA-256 `5ac030957aff56aae66fed365a15fecf326f5d0d3137228f8e3309fd6cec2b0d`, and suite SHA-256 `e5acd4d33709bf77a66acb5b9a2872296d3847d798310d7b911c15beea8cc222`. Its preserved [v3 control](PLANNING_CHALLENGE_LIVE_20261020.md) has evaluation SHA-256 `4c99b7c90480a4a2225a505464ceb4c168b79a29bcf69d7e6c32c7e900e08434`.

Questions, draft plans, source bytes, review events, display budgets (eight results, three paths) and the submitted scope-review worksheet are identical to the control. The original `test` split labels remain for identity preservation; reuse is explicitly recorded in the packet, summary and report. The worksheet SHA-256 is `cccc1fea6dd2356defcb10e2659cff2e537409cc5e491a4e90f727fd91c384f1`. Preparation verifies the control evaluation/comparison bindings, source hashes and exact submitted worksheet before freezing the new engine. A changed worksheet is rejected before constructing a live planner.

Scope references and reviews are AI-assisted engineering work. **Human-approved reference plans: zero.** Reviewer independence and biomedical validity are not established. The runner's 32 approved references refer to that AI-attributed scope worksheet. Scientific judgments remain blank, citation-support accuracy remains null, and no graph assertions or human review states were changed.

The same Brev L40S served `nvidia/Llama-3.1-Nemotron-Nano-8B-v1` revision `54641c1611fcff44fa4865626462445e0a153fc7` using vLLM 0.8.5 image digest `sha256:6cf9808ca8810fc6c3fd0451c2e7784fb224590d81f7db338e7eaf3c02a33d33`. Image, model revision, reasoning-off profile, generation budgets and serving settings matched the control. Only the app was rebuilt; the model service was retained. XGrammar 0.1.18 compiled all 32 schemas without inference. The run made 32 model/transport requests, with no model retry, repair or extra live preflight. A launcher syntax error was corrected before any process launch or model request; its separate zero-request setup receipt is preserved.

All **64 deterministic outputs** matched both the v3 control and local offline preparation. All 168 v1–v3 request contracts across the original 24 and subsequent 32 questions remained unchanged. Saved-answer and observation hashes verified, as did post-run packet/source integrity. Exact query-output comparison excludes only `source_run` and its derived answer hash.

The final local suite ran **304 tests with one optional skip**; all **63 focused tests** passed on Brev's Python 3.10. Authenticated HTTP report/metrics bytes and the full ZIP matched saved results; anonymous report access was rejected, and the historical v3 report remained unchanged. Automated browser rendering remains unverified. No AWS resources or live source refresh were used.

Median model-request latency was 4.99 seconds (3.08–5.92). Reported usage was 54,532 prompt and 2,367 completion tokens, totaling 56,899, versus the control's 44,584 total tokens. These are descriptive single-run measurements; there is no repeated-seed variance estimate.

## Records and next increment

The [machine-readable paired result](scoped_targets_v4_20261020_summary.json) includes all 32 cases, proposed/validated plans, gains, regressions, group outcomes, controls and request/response hashes. Full results are retained locally at `runs/scoped_targets_v4_20261020/live/scoped_targets_v4_live_20261020/` and on Brev at `/data/runs/scoped_targets_v4_live_20261020/`. The protected app serves `/api/evaluation/scoped_targets_v4_live_20261020/`; its ZIP preserves the exact AI-attributed worksheet and comparison record. The original v3 packet and first result remain unchanged.

The next implementation should simplify the model-facing contract while retaining the full raw target audit outside the prompt, and measure whether this reduces unnecessary abstentions without reintroducing wrong-scope queries. That requires another versioned regression experiment, not retries of this run. Freeze that implementation before preparing a genuinely new, separately reviewed prospective packet. Source-level adjudication and the controlled prediction experiment remain separate requirements for a biological graph-improvement claim.
