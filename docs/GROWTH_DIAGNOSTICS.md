# Diagnose the completed pilot and reserve a fresh test

The first frozen comparison found no demonstrated gain from adding the CPTAC summary. These commands investigate the recorded failure using **already exposed development data**, while separately reserving untouched genes. Neither command takes an experimental score-matrix argument or opens that matrix. Neither produces a new unbiased biological test result.

```sh
python3 app.py growth-reserve \
  --panel runs/matched_pharos_panel_20261020/frozen_panel \
  --comparison runs/crc_growth_comparison_20261020/result \
  --out runs/crc_growth_diagnostics_20261020/reservation

python3 app.py growth-diagnose \
  --comparison runs/crc_growth_comparison_20261020/result \
  --out runs/crc_growth_diagnostics_20261020/diagnostics
```

Both outputs must be new. The original protocol, result and first-test-access ledger remain unchanged. The parent comparison is verified before either operation.

## Development ablations

The six additional ridge representations are pathways only, expression only, BioPlex only, without pathways, without expression and without BioPlex. Numeric and categorical expression are one declared block; Reactome and WikiPathways retain their separate namespace weights inside the pathway block. Each mask removes a complete block after the original train-only transforms. Retained block values and weights do not change. No source confidence, new labels, identity features or post-test tuning grid is introduced.

Every ablation uses the original three-alpha selection budget and one final refit, adding 24 ridge fits. Validation uses the original validation genes × validation sample groups; refit uses the original train/validation union. Scores on the original 52 test genes are now exploratory development scores. The same validation set is also being reused adaptively for the new hypotheses. A high value cannot be presented as confirmation.

A separate fixed late combination averages the saved Pharos and CPTAC-only predicted dependency values with weights 0.5 and 0.5. Both predictions already have the same experimental-effect units. It fits no new model or calibration weight. It reuses two individually tuned component models, so its component budget is twice that of a single ridge arm; the report states this difference.

The recorded development proposal follows a predeclared rule: highest original validation Spearman among restricted Pharos, enriched Pharos, CPTAC only, the six ablations and fixed late combination. Exact ties follow that listed order; undefined correlations rank last. Coverage-only remains a control. Exposed test scores cannot select the proposal. The baseline is eligible, so this rule need not propose a change.

The rank audit covers every exposed test gene. It retains original/enriched/measured ranks, the change in absolute rank error, feature visibility against the fitted vocabulary, BioPlex neighbors in the fit set and each model's block contributions plus intercept. Contributions reconcile with saved predictions. These are statistical decompositions, not causal explanations or target-validity judgments. Source pointers reference the copied original feature packet and its evidence passports.

## Untouched gene reservation

Continue the original eligible population's stable-ID hash order. Conservatively mark all 256 genes from the first pilot as exposed, including its train, validation and test genes. Form connected components across every reviewed protein product in the full eligible population and exclude whole components containing an exposed gene. Select whole remaining components in hash order until at least 256 genes are reserved. The count can exceed 256 at a component boundary. Do not reseed, split a component, select on disease labels or replace members after inspecting features/outcomes.

The reservation binds the original panel, eligible population, exposure-file identities and model partitions. It has zero overlap in genes and protein products with the previous pilot. It is fresh relative to the bound pilot's gene outcomes; it is not new laboratory data or an attestation about outside analyses. The historical release, processed Chronos values and recorded model groups are reused.

This is a reservation, **not a frozen final scoring protocol**. Before using it, retrieve Pharos context over development plus reserved genes with a common version and consistent PPI partner scope. A fresh-only interaction subgraph omits fresh-to-development links and is not an adequate test representation. Freeze the final development candidate, grouped assignments, feature policy, endpoint, controls and full tuning/combination budget. Seal predictions before first reserved-outcome access, and preserve a separate exclusive access ledger. Reserved genes are not available for selecting a feature policy or trying many variants on the test scores.

## Replay and serving

```python
from biograph_steward.growth_diagnostics import verify_diagnostics, verify_reserve
verify_diagnostics('runs/crc_growth_diagnostics_20261020/diagnostics')
verify_reserve('runs/crc_growth_diagnostics_20261020/reservation')
```

Diagnostic replay verifies artifact hashes, original model identities, masked predictions, fixed fusion, metrics, validation-only selection and rank decomposition. Reservation replay reconstructs shared-product exclusions and selected membership from the frozen population. Neither replay refits predictors or reads the original score matrix.

Both packets have `report.html` and `metrics.json` and can be published through the protected generic evaluation/export routes. The diagnostic packet includes the relevant original artifacts; the reservation contains identifiers/provenance and no fresh dependency values. Both use standard-library CPU code, with no model-service requests, GPU inference or AWS resources.
