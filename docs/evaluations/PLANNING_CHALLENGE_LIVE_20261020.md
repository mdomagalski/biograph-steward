# First prospective planning run — October 20, 2026 (EDT)

The unchanged v3 hybrid planner matched **22/32 scope plans (68.75%)** on the prospective question packet. Nine of 16 paired families matched in full. Its earlier 24/24 development result did not generalize to this set. The two percentages use different questions and are not a paired comparison of software versions.

| Outcome | First prospective run |
|---|---:|
| Questions / model requests / HTTP transport requests | 32 / 32 / 32 |
| Scope plans matched | 22 / 32 |
| Answered | 21 |
| No evidence | 2 |
| Abstained | 8 |
| Invalid plan blocked | 1 |
| Validated read-only query calls | 23 |
| Queries executed with incorrect scope | 7 |
| Unsupported-reference questions that reached a query | 2 |
| Query outputs equal to the enriched reference output | 16 / 21 comparable pairs |

Answer count alone overstates usefulness: seven executed queries did not preserve the requested scope. Two of those answered questions whose reference required abstention, so there is no corresponding deterministic query output for those two. Of the remaining 21 query/output pairs, 16 matched exactly after excluding only the arm's `source_run` label and its derived answer hash.

## Scope review and evidence limits

Before inference, Codex reviewed all 32 question/reference pairs against the frozen catalogue and implemented tool contracts, recording a case-specific rationale in a **separate, explicitly AI-attributed worksheet**. The [review provenance](planning_challenge_scope_ai_20261020.json) preserves every rationale and worksheet hash. The original packet, questions, draft plans and blank worksheet were not edited. References retain their original draft wording because they are immutable.

This is AI-assisted engineering scope review, not independent human review or biomedical adjudication. Human-approved reference-plan count is **zero**. The runner's `approved_reference_plans=32` field means the AI-attributed scope worksheet passed its import checks; it must not be described as 32 human approvals. Publication support, citation accuracy and biological graph improvement remain unjudged. The author/reviewer has seen the earlier development set, and the same frozen source entities are reused.

## Where the ten mismatches occurred

| Failure group | Cases | Observed behavior |
|---|---:|---|
| Negated relation | 2 | The schema required both relations despite one being explicitly excluded; both queries executed with excessive relation scope. |
| Background therapy | 2 | Both drug mentions became requested targets; the query used `both` instead of the one requested drug. |
| Negated all-profiles request | 1 | The schema restricted the profile to `all`, even though the question explicitly requested only KRAS G12D after negating all profiles. |
| Negated recommendation disclaimer | 1 | A supported inspection request was forced to abstain because “do not recommend” triggered the clinical-recommendation rule. |
| Unknown lowercase AND/OR profile | 2 | The complete unknown expressions were reduced to KRAS G12D, and queries executed for the contained profile. |
| Supported known profile | 1 | The model unnecessarily abstained on an admissible KRAS G12D/cetuximab query. |
| Exact disease boundary | 1 | A query proposal substituted the CIViC disease for the requested Pharos subtype. The post-validator blocked it, so no wrong-disease query executed. |

The first six mismatches correspond exactly to the [offline constraint conflicts](PLANNING_CHALLENGE_PREP_20261020.md). Those constraints made the intended reference plans unavailable regardless of model quality. The other four references were admissible: two exposed incomplete-profile detection, one was an unnecessary model abstention, and one produced an invalid plan at the source-disease boundary.

Some brief model reasons described the correct requested scope while their constrained JSON arguments differed. Reasons must not be treated as execution evidence; the actual plan fields, validation result and returned graph paths determine what ran. No repair, retry or selective case removal was used.

## Controls and deployment checks

The experiment used source commit `5da22020289cb9915564305638bc8cf02b65e282`, packet SHA-256 `23a6e8fd147092ee829676c935ffd71046c4366682d9cd0b779f36e40c278c43` and suite SHA-256 `8e41abbea0dc24ea4df3e626ecadff8612114c662cfc5a186897fdd0627cbf8e`. All six planning/transport files remain byte-identical to the preceding v3 development run. Source snapshots, review events and display budgets (eight results, three paths) are unchanged.

The Brev L40S resumed the same `nvidia/Llama-3.1-Nemotron-Nano-8B-v1` revision `54641c1611fcff44fa4865626462445e0a153fc7`, vLLM 0.8.5 image digest `sha256:6cf9808ca8810fc6c3fd0451c2e7784fb224590d81f7db338e7eaf3c02a33d33`, reasoning-off profile and serving limits. XGrammar 0.1.18 compiled all 32 output schemas before inference. There were 32 model/transport requests, no retries or repair calls and no extra live preflight requests. Model reasons are brief public explanations; private reasoning was not requested.

All **64 deterministic Pharos/enriched outputs** matched the offline preparation run. Saved-answer hashes verified, and post-run source/packet integrity checks passed. Median recorded request latency was 5.66 seconds (3.61–7.10); reported token usage totaled 44,584. Timing is descriptive on different questions, not a paired performance benchmark.

The 42 focused tests passed on Brev's Python 3.10. The preceding local core run covered 283 tests with one optional skip; it was not rerun or claimed as a full Linux test here. The saved source and cited answer reopened after the VM stop/start. Authenticated HTTP access and the preserved historical report were verified through the restored port-8767 tunnel. Automated browser rendering remains unverified. No AWS resources or live source refresh were used.

## Records and next increment

The [machine-readable result](planning_challenge_live_20261020_summary.json) contains every case, proposed/validated plan, scope comparison, call count, group outcome and request/response hash. Full results remain at `/data/runs/planning_challenge_live_20261020/` on Brev and `runs/brev_planning_challenge_20261020/live/planning_challenge_live_20261020/` locally. The protected app serves `/api/evaluation/planning_challenge_live_20261020/`; its full ZIP includes the submitted AI-attributed scope worksheet and `comparison.json`.

Keep this first result unchanged. The next implementation should version the planner contract and address:

1. Clause-aware negation/background handling for relations, therapy targets, all-profile requests and unsupported-action disclaimers. Do not treat every catalogue mention as a requested target.
2. Complete-profile validation that rejects an unknown AND/OR/NOT expression before offering a contained known profile, including lowercase operators.
3. Consistent source-bound abstention and clearer query-versus-abstain instructions, while retaining independent post-validation.

Use these 32 cases as disclosed regression/development cases if they guide fixes. Compare any new protocol with this frozen v3 result using the same sources, references, serving configuration and budgets, then obtain another prospective set for a generalization claim. Keep deterministic guided questions as the working default. Biological improvement still requires source-level adjudication and the separate controlled prediction experiment.
