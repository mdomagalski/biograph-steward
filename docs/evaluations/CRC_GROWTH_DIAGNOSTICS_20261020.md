# Development source ablations and a fresh gene reserve — October 20, 2026

Follow-up: the [full-cohort retrieval and fresh comparison](CRC_FRESH_COMPARISON_20261020.md) is complete. The reserve is now consumed; pathway-only did not meet the predeclared improvement rule. The notes below retain the earlier development-stage results and reservation state.

**Pathway variants are promising hypotheses; no new improvement has been confirmed.** Following the [negative/inconclusive first comparison](CRC_GROWTH_COMPARISON_20261020.md), the diagnostic runner separated source blocks, audited all original test-gene rank changes and reserved 256 untouched genes. Every score below reuses the already exposed 52-gene holdout. These are development diagnostics, not a second independent test.

## What the ablations show

| Variant | Original validation Spearman | Exposed test Spearman — exploratory | Exposed Recall@10 |
|---|---:|---:|---:|
| Restricted Pharos | 0.1652 | 0.3810 | 0.50 |
| Pharos + CPTAC | 0.2672 | 0.2605 | 0.50 |
| CPTAC only | 0.2988 | 0.2376 | 0.40 |
| Coverage only | 0.1927 | 0.3192 | 0.20 |
| Pathways only | 0.2829 | 0.5525 | 0.70 |
| Expression only | 0.0114 | 0.1842 | 0.20 |
| BioPlex only | undefined | 0.2006 | 0.10 |
| Without pathways | 0.0159 | 0.1790 | 0.20 |
| Without expression | 0.2868 | 0.5559 | 0.70 |
| Without BioPlex | 0.1599 | 0.3803 | 0.50 |
| Fixed half Pharos / half CPTAC | 0.1836 | 0.3898 | 0.50 |

The six new ridge ablations use the same training-only transforms, three-alpha grid and one final refit as the original model: 24 additional fits per diagnostic execution. Whole source blocks are removed without reweighting retained blocks. The fixed late combination averages saved predictions in common dependency units, fitting no weight. It reuses two independently tuned components and therefore has twice a single ridge arm's original component budget.

Pathway-containing models without expression performed better on both original validation and exposed test scores than full Pharos. Expression alone was weak in this representation; removing BioPlex barely changed the Pharos score. These observations motivate a source-policy experiment. They do not establish that expression or interactions are biologically irrelevant, nor that deleting these evidence records improves the product. Keep the records and provenance; feature-policy experiments remain separate from graph evidence lifecycle decisions.

The predeclared validation-only nomination is **CPTAC only**, whose original validation correlation of 0.2988 exceeds the best graph variant's 0.2868. Its weaker exposed test score is retained. The workflow did not replace that nomination with the highest exposed test result. This disagreement illustrates uncertainty from the small development split. The nomination is not an automatic production change, and the reused validation set is adaptive development too. No confidence interval or confirmatory significance claim is assigned to these ablations.

## Rank changes and usable evidence

The CPTAC-enriched ranking moved **30 genes closer** to their measured ranks, **21 farther away**, and left one unchanged. Mean absolute rank error nevertheless increased from **12.8846 to 13.9615**. Counting individually improved genes is therefore insufficient to claim overall improvement. The report records every gene rather than only favorable examples.

All 36 test genes with retained pathway memberships had at least one membership in the fitted vocabulary. Only **8 of 52** test genes had BioPlex neighbors among the fit genes. The BioPlex-only validation predictions were constant, leaving validation Spearman undefined and selecting the strongest alpha by the declared tie rule. This sparse representation is inadequate for a broad claim about interaction data.

Each gene's Pharos and enriched predictions are decomposed into pathway, numeric/categorical expression, BioPlex and CPTAC contributions plus intercept. The sums reconcile to the original predictions. Evidence pointers, CPTAC row/measurement identities, original models and source-reference/manifest records remain in the export. The decompositions are statistical explanations, not biological causal explanations.

## Reserved final-test population

The original frozen eligible population contains 6,153 complete-measurement genes. All **256** original pilot genes are conservatively treated as exposed. Connected components across reviewed protein products are formed over the full eligible population; every component containing an exposed gene is excluded. Continuing the original stable-ID hash order reserves **256 new genes**, with **zero gene overlap and zero protein-product overlap**. Another 5,641 eligible genes remain unreserved. Selection used no dependency values, disease labels, fresh annotation coverage or reseeding.

The development plus reserved cohort has **512 genes and 513 requested protein products**. No new Pharos retrieval or reserved-gene scoring has been performed. The reservation is not a frozen final scoring protocol. The recorded model groups and historical outcome release are reused; this is not an independent laboratory cohort. “Untouched” is relative to the bound pilot's outcome files, not an attestation about outside analyses.

The next experiment must retrieve features with a common database version and consistent interaction partner scope across the full 512-gene cohort. A reserved-only subgraph would discard links to development genes. Then freeze the final comparison, including the validation-nominated CPTAC-only control and the pathway/source-removal hypotheses, explicit tuning/combination budgets and multiple-comparison interpretation. Keep reserved outcomes sealed while making those choices. Do not promote the exposed 0.5559 score or repeatedly search the reserved holdout for a winner. A separate measured-edge graph-link/pruning benchmark is still required for the challenge.

## Verification and access

Implementation commits: `4bca83e3e05a2257b661bf8408b5e0b6d03cf6c0` (diagnostic/reservation workflow) and `5f86378f343fd65e517486ecef1aa743a6198857` (source-attribution export). **379 tests passed on both local Python 3.14 and Brev Python 3.12**, with one optional integration skipped per runtime. Tests cover removed-block invariance, fixed fusion, validation-only nomination, transitive shared-product exclusions, whole-component selection, invalid-parent rejection and artifact replay/tamper checks. The attribution packaging replay preserved identical scores, predictions and reserved membership; it introduced no model or feature search.

The protected Brev app verifies saved model predictions, scores, proposal and rank decomposition without refitting or reopening the original score matrix. Reservation replay reproduces selection/exclusions from the frozen eligible population. All packet and export bytes match the saved artifacts, anonymous access is rejected and all nine earlier reports are unchanged. Browser rendering was not independently verified. The app is healthy, the GPU/model service was not restarted, and this increment used zero model-service requests and no AWS resources.

- [Development diagnostic report](http://127.0.0.1:8767/api/evaluation/crc_growth_diagnostics_20261020/) and [18-file export](http://127.0.0.1:8767/api/download/crc_growth_diagnostics_20261020).
- [Untouched-gene reservation](http://127.0.0.1:8767/api/evaluation/crc_growth_reserve_20261020/) and [8-file export](http://127.0.0.1:8767/api/download/crc_growth_reserve_20261020).
- [Commands and interpretation](../GROWTH_DIAGNOSTICS.md), and the [machine-readable record](crc_growth_diagnostics_20261020_summary.json).

The reports require workspace sign-in and the existing SSH tunnel. Published local packets are `runs/crc_growth_diagnostics_20261020/published_diagnostics/` and `published_reservation/`; Brev stores them under `/data/runs/crc_growth_diagnostics_20261020/` and `/data/runs/crc_growth_reserve_20261020/`. The original first-pilot packet and access ledger are unchanged.

Experimental values are from the Broad Institute's [DepMap 24Q4 Public v1](https://doi.org/10.25452/figshare.plus.27993248.v1), CC BY 4.0, negated and grouped under the original protocol. Original Pharos/CPTAC/BioPlex source contracts, references and limitations remain applicable. No human scientific adjudications were manufactured.
