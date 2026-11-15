# Annotation preservation: useful trade-off, no general replacement

One fixed author-supported annotation-preservation operation completed across
all 18 existing settings. It **does not resolve the uncertain primary advantage
beyond current-data LocalPlus**. This is development on the already consumed
reference, not a second independent confirmation. The original frozen study
and its success rules remain unchanged.

The CAFA6 authors append known-term predictions at Float32(0.99) and take MAX
with their existing scores. Their competition labels are unsafe here and were
excluded. Our [fixed adaptation](ANNOTATION_PRIOR_DEVELOPMENT_PLAN_20261115.md)
uses only the complete legal T0 nonexperimental-GOA prior sealed in the original
study. There is no new fitting, retrieval, weight search or aspect routing.
The value 0.99 is a ranking heuristic, not a calibrated probability of truth.

| PK aspect | Native: selected → selected + prior | Fixed-T0: selected → selected + prior | Interpretation |
|---|---:|---:|---|
| Biological process, original primary aspect | 0.073431 → 0.046331 | 0.210093 → 0.190092 | Worse than the original selected model in both views; both paired intervals exclude zero. |
| Molecular function | 0.245247 → 0.258886 | 0.299478 → 0.309252 | Small increases; intervals against the original selected model and direct prior cross zero. |
| Cellular component | 0.260227 → 0.276155 | 0.267299 → 0.286030 | Improves over the selected model in both views, but remains below the direct prior (0.321676 / 0.335678); both contrasts favor that prior. |

All intervals are conditional, unadjusted descriptive paired intervals from
2,000 whole-protein draws. The [complete development report](annotation_prior_development_20261115/report.html)
retains every original control, all NK/LK settings, both views, full resampling
frames, unfavorable results and exact contrasts. It introduces no new success
gate or adopted model. Fmax measures recovery of later curator annotations;
it is not whole-graph accuracy or a test of experimental discovery.

The integration checks passed: all 36 new native score/count curves agree,
and in all 18 cells the matched annotation-only control reproduces both the
original prior's point score and each of its 2,000 bootstrap peaks exactly.
This supports numerical alignment, not biological correctness. Source-only
checks found just seven positive CC prior memberships outside the learned
vocabulary across 3,300 targets, so vocabulary omission alone cannot explain
the earlier large CC gap. A training or calibration cause has not been proved.

The practical conclusion is to retain the published methods and direct source
baseline as distinct controls. Forcing all nonexperimental annotations to a
high score is not a generally better combination. No app default, graph,
review disposition or pruning policy changes. A confirmatory claim now needs
an untouched reference, with the current-data LocalPlus and direct annotation
controls fixed before opening it; further tuning on these same labels would
remain development.

Source: [pinned CAFA6 author implementation](https://github.com/btbpanda/CAFA6-updates/blob/0ee85d2f07f724be1721ea39211f1b364535f976/model_scripts/postproc_and_sub.py).
The [machine-readable publication](annotation_prior_development_20261115/summary.json)
and its manifest preserve the original source/result bindings without raw
reference cases, draws or forecast matrices.
