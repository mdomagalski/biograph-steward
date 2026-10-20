# Fresh reserved-gene comparison — October 20, 2026

**The predeclared pathway-only improvement did not replicate.** On 256 previously reserved genes and 13 recorded test sample groups/models, full restricted Pharos achieved Spearman **0.2607** and pathway-only achieved **0.2635**. The paired change was **+0.0028**, with a 95% interval of **[−0.1272, +0.1281]** from 2,000/2,000 defined bootstrap replicates. It failed the frozen internal rule requiring a change of at least +0.05 and a positive lower bound. This is no demonstrated gain, not proof of equivalence or absence of a pathway effect.

The [development diagnostic's](CRC_GROWTH_DIAGNOSTICS_20261020.md) exposed-data score of 0.5525 was a hypothesis-generating result. It is not the fresh result. Different panels and development assignments also mean that the original Pharos score of 0.3810 and this run's 0.2607 cannot isolate the effect of more complete retrieval. Compare arms within the same frozen run.

## Consistent Pharos context for the full cohort

The verified union contains **512 genes and 513 requested protein products**. Pharos resolved 512 products, covering every gene. SCRIB's additional product remained unavailable while its other product resolved; no gene or product was substituted.

The successful refreshed pull used **1,441 source envelopes, zero cached envelopes**, and database version **`pharos319` before and after**. Every requested family was complete for all 512 resolved products. The retained interaction scope is the full resolved union, including development-to-reserved links.

| Family | Raw retrieved = reported available | Retained after declared scope |
|---|---:|---:|
| Pathways | 12,421 | 12,421 |
| GO | 8,403 | 8,403 |
| Interactions | 81,787 | 3,950 |
| Expression | 316,438 | 5,284 |
| Total | 419,049 | 30,058 |

Drugs/publications were explicitly outside this profile. A first attempt encountered repeated HTTP 502 gateway errors on multi-protein expression pages. A new complete attempt serialized expression requests while retaining identical members, family fields and per-protein limits. All successful-packet requests were refreshed; failed-attempt responses were not mixed into the packet. Completeness is observed API count reconciliation, not an atomic database snapshot or the entirety of Pharos.

The unchanged source-review policy retained **7,492 unique gene–pathway memberships**, **112 qualifying undirected BioPlex pairs** from 224 source records, and **4,211 source-specific expression records**. There are 378 genes with pathways, 121 with BioPlex neighbors, 512 with numeric expression and 419 with categorical expression. All 512 have CPTAC summaries. Repeated/revision pathway memberships collapsed (2,342); GO, integrated expression and interactions lacking a separable qualified BioPlex component stayed outside predictors. Raw records and reasons remain available. These are AI-authored source-contract decisions, not human scientific gold adjudications or independent-study counts.

## Freeze, development and first test access

The [implementation and rules](../FRESH_GROWTH_COMPARISON.md) were committed before the freeze and real fitting. Original train+validation genes became development training (**204**); the old test genes became development validation (**52**). All are already exposed genes. The 256 reserved genes alone became final test. Original model/sample-group assignments stayed together: 38/12/13 models in 36/12/13 groups.

Training used training genes × training groups; validation used development validation genes × validation groups. Selected models were refitted on all 256 development genes × the 50 train/validation models. Only the 256 reserved genes × 13 test models were parsed for the final endpoint. Vocabulary, scaling and imputation used fit genes only. Outcomes are the same pinned continuous negated DepMap gene effects, with medians within and across recorded groups.

Exactly one primary hypothesis was frozen: **pathway-only minus full restricted Pharos**. The prior validation nominee, CPTAC-only, remained a named secondary control. Ten base ridge representations, 20 within-role CPTAC permutations and 20 within-role pathway permutations used the same three-alpha budget plus one final fit: **200 ridge fits**. The late combination averaged saved Pharos/CPTAC-only predictions with fixed equal weights, reusing two component budgets and fitting no weight. An intercept and 100 fixed hash rankings were also preserved.

Every model, preprocessing receipt, validation choice, donor mapping and reserved prediction was saved in the prediction seal before the source-bound exclusive access ledger was created. The ledger records all 256 test genes and prevents testing overlapping reserved genes under another protocol identity. The reserve is **now consumed**. The earlier reservation packet remains a historical record of the pre-access state; its identifiers cannot be used as a new untouched holdout.

## Primary and descriptive secondary results

| Representation | Selected alpha | Test Spearman | Mean absolute error | Recall@10 |
|---|---:|---:|---:|---:|
| Full restricted Pharos | 0.1 | 0.2607 | 0.2994 | 0.30 |
| Pathways only — primary candidate | 1 | 0.2635 | 0.3214 | 0.30 |
| Pharos + CPTAC — secondary | 0.1 | 0.3226 | 0.3135 | 0.30 |
| CPTAC only — prior validation nominee | 10 | 0.2986 | 0.3217 | 0.00 |
| Coverage only | 0.1 | 0.2961 | 0.3096 | 0.40 |
| Expression only | 0.1 | 0.1340 | 0.3221 | 0.20 |
| BioPlex only | 10 | 0.1333 | 0.3251 | 0.10 |
| Without pathways | 0.1 | 0.1437 | 0.3207 | 0.20 |
| Without expression | 0.1 | 0.2797 | 0.2999 | 0.30 |
| Without BioPlex | 0.1 | 0.2581 | 0.3003 | 0.30 |
| Fixed half Pharos / half CPTAC | fixed | 0.2928 | 0.3085 | 0.30 |

Pharos+CPTAC was descriptively +0.0619 above Pharos in correlation. That is a predeclared secondary observation, not a replacement primary success or a multiplicity-adjusted improvement claim. Its mean absolute error was worse and Recall@10 unchanged. CPTAC-only's ranking correlation also did not translate into top-ten recovery in this panel. Preserve these tradeoffs when choosing what to investigate next.

Coverage-only exceeded both primary arms, so this run does not establish pathway/graph value beyond annotation availability. Random rankings had mean Spearman −0.0015 (descriptive 2.5–97.5 percentile range [−0.1239, +0.1169]). Pathway-shuffled controls averaged −0.0001, with range [−0.0670, +0.1056]. CPTAC-shuffled enriched controls averaged 0.2560, with range [0.2238, 0.2964]. These controls are descriptive distributions, not independent biological samples or confidence intervals for the observed arm scores. The intercept correlation was undefined.

No extra alpha, feature threshold, cohort substitution or test-driven candidate selection was performed. The result does not justify removing expression evidence, replacing the default workflow, or claiming graph improvement. Evidence records remain available under their original lifecycle rules.

## Reproduction, provenance and protected access

Implementation: `7353fd0` (union scope/retrieval), `ee69b3a` (smaller expression requests), and `3f5f0ed6e085b90356666601db473a9ba8327881` (frozen comparison). **387 tests passed locally on Python 3.14 and on Brev Python 3.12**, with one optional integration skipped per runtime. Invented tests cover the complete budget, first-access boundary, primary-policy tampering, raw-envelope scope replay, source mismatch and source-bound overlapping-gene rejection. They are software checks, not biological gold labels.

Protocol identity: `5953abe3c7affc029d81b1a7e5879f7a7e07949d58a51b5474a0045bc7a3e76b`. Result identity: `ec15c225b6d9a3c520bccf8273953111a18a6745b7d906b2f8d00f954e31a25e`. The [machine-readable record](crc_fresh_comparison_20261020_summary.json) binds cohort, source, pre-execution, exposure and deployment identities.

Brev verified all cohort and raw retrieval files, then independently rebuilt the frozen feature/exclusion/partition/rule files byte for byte from transferred sources and the preserved mapping/reference parents. It reproduced result predictions, grouped endpoints, all arm/control metrics, primary uncertainty/decision and every gene passport without fitting predictors or reopening the original outcome matrix. The source-bound exposure ledger was mirrored byte for byte, and Brev confirmed a repeat fails before source loading or fitting. Authenticated reports and full exports matched saved bytes; anonymous access was rejected and all eleven previous reports remained unchanged. Browser rendering was not independently verified. The app is healthy; the existing GPU/model service was not restarted. This increment used zero model-service requests and no AWS resources.

- [Fresh result report](http://127.0.0.1:8767/api/evaluation/crc_fresh_comparison_20261020/) and [25-file result export](http://127.0.0.1:8767/api/download/crc_fresh_comparison_20261020).
- [Frozen protocol](http://127.0.0.1:8767/api/evaluation/crc_fresh_protocol_20261020/) and [15-file protocol export](http://127.0.0.1:8767/api/download/crc_fresh_protocol_20261020).
- [Full-cohort Pharos retrieval](http://127.0.0.1:8767/api/evaluation/crc_fresh_pharos_20261020/) and [10-file raw source export](http://127.0.0.1:8767/api/download/crc_fresh_pharos_20261020).

Use workspace sign-in with the existing SSH tunnel. Local packets are `runs/crc_fresh_comparison_20261020/{cohort,retrieval_serial,frozen,result}/`. Brev stores them as `/data/runs/crc_fresh_cohort_20261020/`, `crc_fresh_pharos_20261020/`, `crc_fresh_protocol_20261020/` and `crc_fresh_comparison_20261020/`.

Each result passport includes exact pathway source support and CPTAC row/measurement identity. The `source_inputs.json` locators use the frozen protocol namespace: those bytes appear as `protocol_source_inputs.json` in the result ZIP. Parent `snapshot.json` locators refer to the separate raw Pharos packet. The protocol/raw downloads therefore allow tracing every retained source row without renaming historical locators. Contributions are statistical explanations, not causal target validity.

Experimental outcomes are attributed to the Broad Institute's [DepMap 24Q4 Public v1](https://doi.org/10.25452/figshare.plus.27993248.v1), CC BY 4.0, with the recorded negation/grouping transformations. Original Pharos/CPTAC/BioPlex source licenses and references are retained. The 2026 annotations postdate the historical outcomes; upstream Chronos processing and the recorded laboratory groups are reused. The interval excludes training/cohort-selection uncertainty, and underlying-study independence is unresolved. This is a fresh gene holdout within a retrospective processed release, not prospective laboratory, clinical, GNN/link-prediction or pruning validation.

The next challenge-facing evaluation should measure graph-link recovery and evidence-pruning accuracy under an appropriate measured relationship protocol. The completed gene-ranking holdouts remain development history; secondary hypotheses require another separately frozen evaluation before being promoted as improvements.
