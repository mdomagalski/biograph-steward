# Frozen growth-dependency protocol — October 20, 2026

Follow-up: the [first scored execution](CRC_GROWTH_COMPARISON_20261020.md) is now complete and found no demonstrated incremental gain. The notes below describe the earlier outcome-blind freeze; its packet remains unchanged.

**The source-reviewed feature packet and scoring protocol are frozen. No dependency values have been loaded, no predictor has been fitted and biological improvement remains untested.** This follows the [matched Pharos panel](MATCHED_PHAROS_PANEL_20261020.md). Existing source pulls, graphs and reports remain historical and unchanged.

## Source review and materialized features

The packet preserves all **256 selected genes**, their **63 colorectal models / 61 recorded tissue-sample groups**, relevant raw annotation rows and mapped CPTAC summaries. It does not replace SCRIB's unavailable additional product or duplicate gene-level measurements across protein links.

| Decision or coverage | Result |
|---|---:|
| Retained Reactome/WikiPathways source records | 5,724 |
| Repeated/revision membership records collapsed | 1,936 |
| Unique source-qualified gene–pathway memberships | 3,788 |
| Genes with retained pathway memberships | 186 |
| Qualifying BioPlex-component source records | 68 |
| Unique undirected BioPlex gene pairs | 34 |
| Genes with BioPlex neighbors | 36 |
| Retained source-specific expression records | 2,085 |
| Genes with numeric expression / HPA categories | 256 / 205 |
| Genes with a mapped CPTAC median ratio | 256 |

The [published Pharos implementation](https://github.com/ncats/pharos-graphql-server/blob/master/src/TCRD.js) applies its confidence exclusion to STRING-only rows. Mixed rows retain a separate BioPlex `p_int` field. The policy now accepts a reported BioPlex component with a unique finite probability of at least 0.75, including mixed rows, and retains one binary gene pair with every source locator. This follows the [BioPlex distinction between filtered and subthreshold networks](https://bioplex.hms.harvard.edu/explorer/help). The 68 records all passed the threshold; they do not become 68 independent experiments. Exact release/cell-context attribution and full study independence remain unresolved.

The review withholds **4,269 GO rows**, whose retrieved schema lacks study references and qualifiers; **858 interaction rows** without a qualifying BioPlex component; **517 JensenLab TISSUES integrated expression scores**; and **1,000 non-approved pathway records**. All source rows remain inspectable. Metadata, disease labels, popularity/annotation counts, non-BioPlex PPI scores and dependency-derived sources stay outside primary predictors. Numeric zero, missing observations and HPA “Not detected” remain distinct.

This is a restricted Pharos representation. Restoring BioPlex component information and collapsing duplicate memberships are feature-policy changes, not evidence of improved biological predictions. The review is AI-authored source-contract inspection, with **zero human scientific adjudications**.

## Exact frozen experiment

The primary comparison is restricted Pharos versus the identical features plus one gene-level median of available source-reported CPTAC tumor/normal log2 ratios. The endpoint is growth dependency in these colorectal models, using negated processed gene effects. Within each partition, first aggregate models within recorded tissue-sample groups, then aggregate groups with equal weight. No clinical-response, CRC-selectivity or causal target label is assigned.

| Assignment | Train | Validation | Test |
|---|---:|---:|---:|
| Gene groups / genes | 153 | 51 | 52 |
| Tissue-sample groups | 36 | 12 | 13 |
| Cell models | 38 | 12 | 13 |

Assignments use a fixed stable-ID hash rule. Related model pairs remain together. Gene components sharing a requested product cannot cross splits. Training uses only training genes × training groups; validation uses validation genes × validation groups. After selecting regularization, refit on the union of training and validation before evaluating test genes × test groups once. Other outcome blocks remain unused. Distinct sample IDs do not establish independent donors.

The specification fixes training-only vocabulary/scaling/imputation, source-specific feature blocks, three ridge regularization values per arm, selection/tie rules, intercept/random/coverage-only/CPTAC-only controls and 20 deterministic CPTAC permutations. Primary performance is the paired change in test-gene Spearman, with secondary errors/ranking recovery and a paired two-axis bootstrap. Undefined metrics remain null. A gain over restricted Pharos alone does not establish value beyond CPTAC alone; all controls must be reported.

The internal pilot signal rule requires a Spearman delta of at least 0.05 and a positive paired interval lower bound. This is not a universal biological significance threshold. The small holdout, modern annotations versus historical outcomes, unresolved study overlap and upstream joint Chronos processing limit interpretation. No post-test cohort, feature or tuning adjustments are permitted under this freeze.

## Reproduction and deployment

See [commands and complete policy](../COMPARISON_PROTOCOL.md), and the [machine-readable record](crc_growth_protocol_20261020_summary.json). The exact frozen rules are in `specification.json`; features, exclusions, grouped assignments, source locators and the inspected implementation/tree are independently hashed. Local packet: `runs/crc_growth_protocol_20261020/frozen/`.

Implementation commit: `8fec17c74ca041a9bdfe8a074002d613eebbd7ed`. Packet identity: `f326b0ba9e2bbcbcfcb86e0fab4a59c731db33837d9657ffd5ef2c30aac90dfb`. Both local Python 3.14 and Brev Python 3.12 ran **357 tests with one optional integration skipped**, without failures. Invented tests cover source-channel separation, probability validation, duplicate/revision collapse, missing/category handling, grouping, source identity and immutable replay. They are not biomedical gold labels.

Brev verified all eleven packet file hashes and reproduced features, exclusions, partitions and rules byte for byte from the previously preserved parents under the identical engine fingerprint. The app-only rebuild is healthy; the model service was not rebuilt or restarted. Authenticated report/metrics/export bytes matched saved artifacts; all seven previous reports remained unchanged. Anonymous report/export access was rejected. Browser rendering was not independently verified. There were no model calls or dependency-score calculations.

With the SSH tunnel active, open the [protected protocol report](http://127.0.0.1:8767/api/evaluation/crc_growth_protocol_20261020/) or [download the packet](http://127.0.0.1:8767/api/download/crc_growth_protocol_20261020). Brev stores it at `/data/runs/crc_growth_protocol_20261020/`. The dependency-score matrix is not included. The next increment implements/tests the runner against this fixed protocol and executes the first matched comparison.
