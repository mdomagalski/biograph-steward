# Execute the frozen growth-ranking pilot

The runner executes [the frozen protocol](COMPARISON_PROTOCOL.md) using Python's standard library on a CPU. It adds no package dependency, hosted model, GPU inference or source-network request. This is a retrospective ranking experiment on the fixed panel, not a GNN/link-prediction or pruning benchmark.

```sh
python3 app.py growth-compare \
  --protocol runs/crc_growth_protocol_20261020/frozen \
  --source runs/depmap_feasibility_20261020/source \
  --out runs/crc_growth_comparison_20261020/result
```

Use a new immutable output. The protocol and publisher-verified experimental source identities must agree. The old feature packet and its engine fingerprint remain historical; the new execution has its own implementation fingerprint and source bindings.

## Execution boundary

First verify all source bytes and frozen views. Parse numeric outcomes only for the training/validation gene × model block. Tune each model on training genes × training groups against validation genes × validation groups. Refit the selected alpha on the union of those genes/groups. Test genes' feature values are available for prediction, but their experimental values remain unopened.

Fit the four specified representations and all twenty CPTAC permutations, with the identical three-alpha selection budget and one final fit per representation: **96 ridge fits**. Create the intercept baseline and 100 fixed hash rankings. Save the fitted models, fitted preprocessing, validation choices, feature vectors and all test predictions. `sealed_predictions.json` binds those files and predictions before test access.

An exclusive sibling ledger named `.growth_test_access_<protocol-sha>.json` records the first test access outside the immutable protocol directory. Only then parse test genes × test models, compute grouped endpoints, scores and uncertainty. Other numeric matrix cells are not parsed. Missing/nonfinite selected outcomes, changed column/model identities, malformed files or a prior test-access ledger fail the run. A post-access failure preserves the ledger and incomplete output; it does not authorize another adaptive run or deleting the ledger. Diagnose/recover from the sealed artifacts without changing predictions or selection.

The runner supports no alternate alpha grid, seed, cohort selection or post-test tuning flags. The protocol's implementation details are resolved before real outcome access:

- Numeric transforms fit the observed median, impute fit-gene values, then fit population mean/std on that imputed training column. The expression block divisor counts both value and missing-indicator columns. CPTAC remains signed and receives no log1p transform.
- Each pathway namespace, BioPlex adjacency and categorical expression block has the specified row normalization. Unknown held-out memberships/categories cannot create columns. Coverage-only uses the specified counts and missingness indicators with train-only scaling.
- Ridge solves the centered linear kernel system by Cholesky, with diagonal penalty `n_fit * alpha`, equivalent to the frozen mean-squared-error objective and an unpenalized intercept. An analytic closed-form test checks this normalization.
- Spearman uses average ranks. Random controls are rankings, so their MAE is undefined rather than an arbitrary comparison between hash/rank units and gene-effect units.
- Bootstrap draws sample groups first and genes second, using `Random(20261020)`, 2,000 paired draws and linear-interpolated percentile bounds. It retains duplicate draws and reports undefined replicates. These are conditional fixed-predictor intervals, not training or donor-selection uncertainty.

## Result and traceability

`report.html` leads with the paired Spearman change and the predeclared decision rule. It compares restricted Pharos, enriched Pharos, CPTAC-only and coverage-only, and exposes random/permutation controls. The complete test-gene table shows both predicted ranks, their change and the measured rank. Each expandable passport contains source locators, CPTAC row/measurement identity and the largest model contributions. Contributions reconcile to predictions; they are statistical explanations, not evidence of causal target validity.

`metrics.json` binds all artifacts. `fit_outcomes.json` and `test_outcomes.json` retain the exact parsed continuous experimental values and grouping. `fitted_models.json` retains validation scores, selected regularization, scalers, column vocabularies, coefficients and vectors. `scores.json`, `paired_bootstrap.json`, `gene_passports.json` and the copied protocol/source manifests support offline inspection. The full 447 MB source archive is not copied into this export; attribution, licenses, checksums and the original protocol links remain available.

Verify saved predictions, model/value consistency, grouped endpoints, scores and bootstrap without retraining or reopening the original score matrix:

```python
from biograph_steward.growth_comparison import verify_comparison
verify_comparison('runs/crc_growth_comparison_20261020/result')
```

The protected app serves a published result at `/api/evaluation/<name>/` and its complete ZIP at `/api/download/<name>`. No inference endpoint is invoked by scoring, verification or serving the saved report.

Interpret the primary change under the preset threshold and interval rule, retaining inconclusive or negative results. A gain over restricted Pharos alone does not establish value beyond the CPTAC-only control or against the complete Pharos KG. The small holdout, source chronology/overlap and joint upstream Chronos processing remain limitations. A separate same-ML graph-link comparison and pruning ablation are still needed for the challenge.
