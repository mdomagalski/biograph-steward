# First frozen growth-ranking comparison — October 20, 2026

**Adding the CPTAC summary did not demonstrate an incremental gain.** On the 52 held-out genes and 13 held-out colorectal cell models / recorded tissue-sample groups, restricted Pharos achieved Spearman 0.3810 and Pharos+CPTAC achieved 0.2605. The paired change was **−0.1205**, with a fixed-predictor, two-axis bootstrap 95% interval of **[−0.3929, +0.1876]** (2,000/2,000 defined replicates). The preset rule required a change of at least +0.05 and a positive interval lower bound. It failed. The interval also does not establish that enrichment reliably harms performance.

This is the first scored execution of the [frozen protocol](CRC_GROWTH_PROTOCOL_20261020.md), using [the tested CPU runner](../GROWTH_COMPARISON.md). It is a retrospective growth-dependency ranking experiment on a restricted Pharos feature representation. It does not establish performance against the complete Pharos graph, CRC selectivity, treatment response, causal target validity, or the challenge's graph-link/pruning task.

## Identical held-out panel and tuning budget

| Representation | Selected alpha | Test Spearman ↑ | Mean absolute error ↓ | Recall@10 ↑ |
|---|---:|---:|---:|---:|
| Restricted Pharos | 0.1 | 0.3810 | 0.3110 | 0.50 |
| Restricted Pharos + CPTAC | 10 | 0.2605 | 0.3501 | 0.50 |
| CPTAC only | 10 | 0.2376 | 0.3510 | 0.40 |
| Coverage only | 10 | 0.3192 | 0.3468 | 0.20 |

All arms used the fixed three-alpha validation budget and the same grouped splits. Each model was refitted on the 204 train/validation genes and 50 train/validation models before predicting the 52 test genes. The 24 representations, including all 20 predeclared CPTAC permutations, required 96 ridge fits. All predictions, fitted models, transformations and validation choices were sealed before the runner opened test outcomes.

The intercept's ranking correlation was undefined because all predictions were equal. The 100 fixed random rankings had mean Spearman −0.0384 and a descriptive 2.5–97.5 percentile range of [−0.2866, +0.2219]. These percentiles are a control distribution, not a confidence interval for Pharos. The 20 enriched models with CPTAC values shuffled within their original gene partitions had mean Spearman 0.3650 and range [0.2846, 0.4747]; all exceeded the unshuffled enriched score. This pilot supplies no affirmative evidence for the chosen CPTAC feature's incremental value. No control was selected as a replacement model after seeing test results.

## What the recorded choices explain

The enriched model improved validation correlation from the Pharos model's selected 0.1652 to 0.2672, so its worse test result was not visible from validation alone. It selected stronger regularization (10 versus 0.1); the enriched result therefore reflects both the added feature and the allowed validation-driven model choice. This observation does not isolate a biological cause or show what would happen under another tuning policy. No additional alpha was tried after test access.

The complete report includes all 52 source-linked gene passports. Large rank changes were not uniformly helpful. For example, TPM2 moved from predicted rank 8 to 52 while its measured rank was 14; LSM14B moved from 35 to 3 while its measured rank was 52. These are descriptive examples from the completed test set, not new target-validity judgments or evidence for changing panel membership. Passports retain exact CPTAC row/measurement identities and the largest statistical contributions with pathway, expression or interaction source locators.

## Verification, artifacts and access

Implementation commit: `e8fbd38d42231ffeabf575cd822c730d845bd740`. Frozen protocol identity: `f326b0ba9e2bbcbcfcb86e0fab4a59c731db33837d9657ffd5ef2c30aac90dfb`. Result identity: `e703cbab21e820f2ce331ba09912045774ecc7322e1f4987494bbc3f221b8ff5`. The original protocol implementation and frozen packet were unchanged. An exclusive sibling test-access ledger was created after the prediction seal; rerunning that holdout is rejected.

Before real outcome access, **370 tests passed on both local Python 3.14 and Brev Python 3.12**, with one optional integration test skipped on each. The invented tests cover the ridge objective against an analytic solution, train-only transforms, grouping, missing/nonfinite values, stable matrix identities, all controls, prediction sealing and tamper rejection. These tests are software validation, not scientific gold labels.

The local result is `runs/crc_growth_comparison_20261020/result/`. All 18 packet files were transferred byte for byte to `/data/runs/crc_growth_comparison_20261020/` on Brev. Brev independently reproduced saved predictions, grouped endpoints, scores and bootstrap from the sealed artifacts without fitting models or reopening the original outcome matrix. Authenticated HTTP report/metrics and the complete ZIP matched the saved bytes; anonymous report/export access was rejected. All eight preceding reports remained byte identical. Browser rendering was not independently verified. The app is healthy; the existing GPU/model service was not restarted. Scoring and verification used zero model-service requests and no AWS resources.

With the SSH tunnel active, open the [protected result report](http://127.0.0.1:8767/api/evaluation/crc_growth_comparison_20261020/) or [download all 18 files](http://127.0.0.1:8767/api/download/crc_growth_comparison_20261020). The packet retains the original [DepMap 24Q4 Public v1 attribution](https://doi.org/10.25452/figshare.plus.27993248.v1), source manifest and licenses. Its test outcomes are continuous negated processed gene effects. The full 447 MB original source archive remains separate. The [machine-readable record](crc_growth_comparison_20261020_summary.json) preserves the metrics, checksums and deployment checks in Git; raw source runs remain outside Git.

## Consequence for the next experiment

Preserve this negative/inconclusive result and its consumed test set. Audit the saved rank changes and source coverage before choosing a new feature policy. The next proposed experiment should separate pathway, expression and BioPlex blocks and compare late combination of Pharos and CPTAC predictions, specifying all choices on development data and reserving fresh genes for final testing. Those are hypotheses prompted by this result, not already verified improvements. Do not treat repeated scores on these 52 genes as a new unbiased test.

Coverage-only correlation of 0.3192 means annotation availability is a material control in this panel; Pharos's modest descriptive advantage over it does not establish graph-structure value. BioPlex coverage is sparse, source-study independence is unresolved, modern annotations postdate the historical outcomes, upstream joint Chronos processing remains, and the interval excludes training/selection uncertainty. Establishing challenge alignment still requires a separate same-model graph-link prediction comparison and pruning ablation with an appropriate measured relationship set. More sources or agents are not justified by this result alone.
