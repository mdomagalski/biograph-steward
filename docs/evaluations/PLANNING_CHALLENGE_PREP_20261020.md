# Prospective planning preparation — October 20, 2026 (EDT)

The next planning experiment is prepared locally with Brev stopped. No Brev connection, source refresh, hosted inference or live model call was made during this increment. The production v3 planner, resolver, scope rules and transports remain byte-identical to the last evaluated control.

The frozen packet contains **32 AI-prepared scope questions in 16 paired families**: 23 draft queries and nine draft abstentions. All 32 reference-scope judgments remain blank. These are same-source prospective challenges authored after seeing the original development set. They are not independently reviewed biological labels or evidence of semantic independence. Case IDs, group labels and normalized question text have no overlap with the prior 24-case control; those checks do not establish that capabilities are independent.

## What the offline audit found

The current application's generation constraints or post-generation checks exclude **six of the 23 draft query plans**:

| Cases | Constraint conflict to review |
|---|---|
| Two negated-relation questions | Mentioning an excluded relation causes it to be included in required relation scope. |
| Two background-therapy questions | Both mentioned drugs are treated as requested targets despite the explicit background clause. |
| Named profile after “do not query all profiles” | Post-validation permits the named profile, but the generation schema restricts it to `all`. |
| Inspection after “do not recommend a drug” | A lexical clinical-recommendation rule forces abstention despite the negation. |

There are seven application-forced abstention shapes. Three of the nine draft abstentions are not forced: two lowercase unknown compound profiles and an exact-disease subtype request. The model may still choose to abstain correctly; the disease-binding validator also rejects a query that substitutes the CIViC disease. These diagnostics do not show what a model actually did.

The audit checks both schema admissibility and independent post-validation, without repairing references or querying the model. The six conflicts are against **pending draft references**; scope review must settle their interpretation. No planning-accuracy score is assigned. The planner is intentionally unchanged so its first live comparison remains interpretable.

## Deterministic preparation run

| Reference-plan workflow | Answered | No evidence | Abstained | Source gap |
|---|---:|---:|---:|---:|
| Pharos | 10 | 2 | 9 | 11 |
| Enriched | 21 | 2 | 9 | 0 |
| Planner | — | — | — | — |

The planner is explicitly `not_run` on all 32 questions, with zero model requests and no plan-agreement denominator. The deterministic arms execute the supplied draft scopes; their coverage counts do not adjudicate the references, citations or biological quality. All saved answer hashes verified. Source bytes and original review events matched both the prior suite and the new copied sources.

The new runner provides scope-review materials **before** live inference. Its `--planner live` mode rejects an incomplete or altered scope worksheet before constructing a model client. The real 32-row packet's unreviewed gate was checked with the model factory mocked to fail if called; it was never called. Reviewed scope does not imply independent expertise or scientific support, and the generic historical evaluation runner remains available for other experiments.

## Reproducibility and next action

- Packet: `runs/planning_challenge_20261020/`; SHA-256 `23a6e8fd147092ee829676c935ffd71046c4366682d9cd0b779f36e40c278c43`.
- Frozen suite: `suite/` inside that packet; SHA-256 `8e41abbea0dc24ea4df3e626ecadff8612114c662cfc5a186897fdd0627cbf8e`.
- Offline results: `runs/planning_challenge_offline_20261020/`, including `comparison.json`, the evaluation report and blank reviewer sheets.
- The [machine-readable preparation record](planning_challenge_20261020_preparation.json) binds source/planner controls, per-conflict case IDs, checks and artifact hashes.
- The full local suite ran **283 tests**, with one optional skip. The macOS system proxy intercepted the first HTTP test attempts; the final passing run used an explicit test-only direct loopback opener and `NO_PROXY` exclusions. Production proxy settings were not changed. No Linux/Brev execution of this increment is claimed.

Open the packet's `review.html` and review a copy of `case_reviews.tsv` using the [scope criteria and resume commands](../PROSPECTIVE_PLANNING.md). Then restore Brev access, deploy the saved source revision, verify the pinned serving configuration, and run the unchanged v3 planner once on the reviewed packet. Preserve that first result before fixing its observed failures. If the questions or diagnostics guide subsequent tuning, treat this set as development and obtain another prospective set.

Scientific support remains unjudged, `scientific_improvement_established` remains false, and the controlled prediction experiment for biological graph improvement remains separate.
