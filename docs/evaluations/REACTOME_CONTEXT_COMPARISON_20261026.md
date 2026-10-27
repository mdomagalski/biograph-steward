# Reactome context development comparison

October 26, 2026. **Completed; mixed seed effects, no consistent incremental benefit demonstrated.**

The selected addition of existing Pharos Reactome memberships raised mean average precision (AP) from **0.717794 to 0.719605** (+0.001812), but one of three matched seeds worsened. Mean ROC-AUC rose from 0.814659 to 0.817623 (+0.002965). This is a completed assessment of recorded assay detection, not independent scientific accuracy or new biology beyond Pharos. The fixed candidate is closed without further tuning.

## Task and matched inputs

Both arms ranked the same 1,751 complete-scored off-diagonal INMC protein pairs: 737 detections and 1,014 nondetections. A detection means at least one positive among three definitive assay outcomes; a nondetection requires all three negative. Failed, untested and unscored rows remain excluded under the original rules. All 3,276 nominations were predicted in both arms; 495 self-pairs are kept separate and 1,030 incomplete off-diagonal pairs are excluded from primary metrics. Lack of Reactome context never removes a pair.

The baseline contains the original HuRI supervision scaffold, frozen gene-to-reviewed-product links and restricted qualified Pharos GO cellular-component annotations. The intervention adds exactly 11,138 source-listed human Reactome product-to-pathway memberships, covering 982 products and 1,490 pathway IDs. Sharing a pathway creates no direct protein-pair assertion. Neither arm uses added GO hierarchy or direct Pharos PPI context.

Both arms use the same ordered union vocabulary (11,840 entities and five relations), unchanged 99,394 supervision triples, candidates, development split and equivalence masks. Adjacency sizes are 103,768 and 114,906 triples. The baseline was rerun in this shared vocabulary; its scores are not interchangeable with the historical GO comparison.

## Fixed learner and execution

Native PyKEEN 1.11.1 / torch 2.6.0 R-GCN used three layers, 32 dimensions, four bases, ReLU, native DistMult interaction, SoftplusLoss and Adam at 0.001. Each run used 20 epochs, batch size 4,096 and 16 typed negative proposals per positive, with supported disabled dropout and ordinary batching. Seeds were 17, 43 and 101. All six fits completed 500 optimizer updates each, totaling 3,000. No hyperparameter search, early stopping or favorable seed selection occurred.

Actual CPU resource checks passed before the immutable execution freeze. The saved code, source, graph, runtime, scorer and proof hashes were authenticated before fitting and again before outcome materialization. Per-seed initial parameter, positive minibatch, negative proposal, filter-mask and accepted-negative fingerprints matched between arms. All finite bidirectional scores were complete and sealed before this new outcome access. Training took 447.4 seconds locally; Brev, its language model and AWS were unnecessary.

## Primary and secondary results

AP is the predeclared primary metric; ROC-AUC is secondary. Pair scores are the arithmetic mean of forward and reverse predictions. Seed means are arithmetic means, not pooled predictions.

| Seed | Baseline AP | Reactome AP | AP difference | Baseline ROC-AUC | Reactome ROC-AUC | AUC difference |
|---|---:|---:|---:|---:|---:|---:|
| 17 | 0.711403 | 0.730225 | +0.018822 | 0.810417 | 0.825549 | +0.015133 |
| 43 | 0.729364 | 0.705472 | -0.023891 | 0.819754 | 0.812018 | -0.007736 |
| 101 | 0.712615 | 0.723119 | +0.010505 | 0.813806 | 0.815302 | +0.001497 |
| Mean | 0.717794 | 0.719605 | +0.001812 | 0.814659 | 0.817623 | +0.002965 |

Two seeds improve both metrics and one worsens both. The small positive average therefore does not demonstrate a consistent benefit under the selected settings. No formal significance or equivalence claim is made.

## Coverage and gene influence

The predeclared untrained coverage-only diagnostic counts original gene endpoints with any exact Reactome membership through the frozen product mapping (0, 1 or 2). It retains all ties. AP is **0.497548** and ROC-AUC **0.615972** on the same 1,751 pairs. The eligible detection proportion is 0.420902. Annotation availability carries descriptive ranking signal in this selected panel; it does not explain the model difference by itself or establish a mechanism. Missing context is not negative biological evidence.

| Endpoints with Reactome context | Pairs | Detected | Nondetected | Mean AP difference | Mean AUC difference |
|---|---:|---:|---:|---:|---:|
| 0 | 279 | 77 | 202 | -0.003824 | -0.003600 |
| 1 | 791 | 285 | 506 | +0.006073 | +0.003987 |
| 2 | 681 | 375 | 306 | -0.004492 | +0.001685 |

All coverage strata retain the same mixed AP seed pattern; none establishes a consistent improvement. Stratum AP values are not directly comparable without their differing class proportions, and stratum deltas do not average to overall AP.

Descriptive removal of each of 1,055 eligible original genes, without retraining, retains positive AP differences for seeds 17 and 101 and negative differences for seed 43 in every scored deletion. The mean AP difference across seeds ranges from -0.001016 to +0.005435. Omitting ENSG00000125991 removes 19 pairs and reverses the small mean difference; this is sensitivity of a fixed ranking, not an independent resample or confidence interval. No gene was removed from the headline denominator.

## Reference reconciliation and limits

The original source adapter reconciled all 2,038 complete-scored pairs with the author reference, including 287 self-pairs excluded from primary metrics. This covers 863 detected and 1,175 nondetected pairs; the primary off-diagonal subset contains 737 and 1,014. Nondetections come from actual assay outcomes, not the complement of a positive-only list.

The INMC outcomes were first accessed on October 23 at 15:10:21 UTC and were already consumed before this intervention was selected. A new freeze does not make them unseen. Pharos postdates the assays; Reactome import release and underlying study lineage remain unresolved. Excluding direct PPI edges and outcome derivatives does not prove independence from reference-derived context. These results cannot establish general biological truth, causal mechanisms, valid pruning or superiority of the full Pharos graph.

The literature supports testing pathway context, not assuming a gain. The [ppiPre primary paper](https://pmc.ncbi.nlm.nih.gov/articles/PMC3851814/) used KEGG co-pathway features in different PPI settings; it is motivation rather than a reproduced comparator. The [Reactome data model](https://reactome.org/documentation/data-model) distinguishes memberships, molecular forms and reaction roles; no binding label was inferred here. The [source and method review](../literature/REACTOME_CONTEXT_INTERVENTION_20261026.md) documents version, code/license and leakage checks.

## Decision and reproducible records

Close this selected context addition as a mixed development result, preserve it and the earlier negative comparisons, and stop this panel-specific variation. The next scientific requirement is a source-overlap-qualified independent evaluation scope, not a sweep for a favorable seed or source combination. Organizer scoring and independent biomedical-user assessment remain separate.

- [Machine-readable result and hashes](reactome_context_comparison_20261026_summary.json).
- [Graph preparation](REACTOME_CONTEXT_GRAPH_20261026.md), [native controls](REACTOME_CONTEXT_NATIVE_20261026.md), and [guarded handoff commands](REACTOME_CONTEXT_HANDOFF_20261026.md).
- Execution: `runs/reactome_context_execution_20261026_cpu/execution.json`.
- Predictions and complete receipts: `runs/reactome_context_comparison_20261026_cpu/predictions/`.
- Authenticated outcomes, metrics and exposure record: `runs/reactome_context_comparison_20261026_cpu/scored/`.
- Separate arithmetic review: `runs/reactome_context_comparison_20261026_cpu/arithmetic_review.json`.

All 20 explicitly pinned historical boundary files remain unchanged. Reserved IntAct interaction bodies remain unopened. These saved run artifacts are local and are not newly redistributed by the documentation commit.
