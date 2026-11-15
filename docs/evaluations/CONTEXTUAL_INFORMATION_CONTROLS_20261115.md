# Current-information controls across all PK aspects

Display-only addendum to the frozen comparison. All rows below come from the unchanged public summary; no new forecast, score, interval or model choice is computed. BP is primary; MF/CC remain secondary.

The selected model improves over retained LocalPlus. A stronger statement must also consider the existing annotation controls: the primary BP comparison with current-curated LocalPlus is uncertain; for MF the direct nonexperimental-GOA comparison is uncertain; CC favors the direct nonexperimental-GOA control. These are different source roles, not independent evidence replications.

## native

| Aspect | Residual-positive N | Selected context | Current-curated LocalPlus | DeepGO-SE | Nonexperimental GOA | Selected − nonexperimental GOA [paired 95% interval] |
|---|---:|---:|---:|---:|---:|---:|
| biological_process (primary) | 322 | 0.073431 | 0.058838 | 0.036422 | 0.025476 | +0.047955 [+0.035253, +0.066741] |
| molecular_function (secondary) | 229 | 0.245247 | 0.125798 | 0.178694 | 0.265878 | -0.020631 [-0.041767, +0.018108] |
| cellular_component (secondary) | 1230 | 0.260227 | 0.167363 | 0.173657 | 0.321676 | -0.061449 [-0.077297, -0.044071] |

## fixed_T0

| Aspect | Residual-positive N | Selected context | Current-curated LocalPlus | DeepGO-SE | Nonexperimental GOA | Selected − nonexperimental GOA [paired 95% interval] |
|---|---:|---:|---:|---:|---:|---:|
| biological_process (primary) | 319 | 0.210093 | 0.182771 | 0.131391 | 0.146169 | +0.063924 [+0.043943, +0.085867] |
| molecular_function (secondary) | 228 | 0.299478 | 0.139747 | 0.211432 | 0.311316 | -0.011839 [-0.034411, +0.017973] |
| cellular_component (secondary) | 1230 | 0.267299 | 0.170379 | 0.180277 | 0.335678 | -0.068379 [-0.083759, -0.051211] |

Intervals are the saved conditional, unadjusted 2,000-draw paired protein intervals. Residual-positive N is not the complete resampling frame: native BP includes 1,954 raw rows/322 residual-positive proteins; fixed-T0 BP is 319/319. The original report/JSON retain every other method, all 18 cells and coverage slices. This addendum does not assert a new primary success gate or a generally superior replacement.
