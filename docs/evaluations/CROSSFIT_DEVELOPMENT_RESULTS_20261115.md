# Cross-fitted graph/frequency context: completed development comparison

**The retained Pharos-derived graph baseline performed worse on this
biological-process recovery task.** The new candidate raises Fmax from
**0.05473 to 0.07113** in the native view and **0.17155 to 0.21336** with the
starting ontology held fixed; paired intervals favor the candidate in both
views. Against the stronger current-annotation LocalPlus control, only the
fixed-ontology interval is positive. Neither view establishes an advantage
over the previously selected context model. The candidate is retained without
model, graph or pruning-policy promotion.

This is one completed follow-up on the already consumed April–November 2026
human GO reference. It measures recovery of later curator annotations, not
whole-graph biological accuracy or independent experimental confirmation.
The original study, earlier failures and favorable results remain unchanged.

Here, the baseline is LocalPlus on the historical Pharos-derived STRING
network with dated GO annotations as supervision. It is not the raw Pharos
database scored for correctness. The two baseline differences have paired
95% intervals **[+0.001880, +0.031774]** (native) and
**[+0.015086, +0.065568]** (fixed T0). These remain conditional, unadjusted
development intervals on an already consumed reference.

## Results

All scores are ordinary micro-Fmax for biological process; higher is better
within a cell. The LocalPlus comparator below uses its **complete current-T0
curated annotations**, rather than the older retained baseline.

| Reference view | Setting | Current-annotation LocalPlus | Previously selected context model | Cross-fitted graph/frequency context |
|---|---|---:|---:|---:|
| Native | PK | 0.0588377 | 0.0734311 | 0.0711293 |
| Fixed T0 | PK | 0.1827713 | 0.2100933 | 0.2133615 |
| Native | NK | 0.2370690 | 0.3104693 | 0.3038869 |
| Fixed T0 | NK | 0.2382134 | 0.3127273 | 0.3060498 |
| Native | LK | 0.3582766 | 0.3905668 | 0.3923445 |
| Fixed T0 | LK | 0.3598700 | 0.3887277 | 0.3898467 |

The primary PK candidate-minus-current-LocalPlus difference is **+0.0305902**
in the fixed-T0 view, with paired 95% interval **[+0.004094, +0.056651]**.
In the native view the difference is **+0.0122917**, with interval
**[−0.002757, +0.027536]**. The original rule requires an interval wholly
above zero in both primary views; this follow-up does not meet that standard.
All six intervals against the previously selected context model cross zero,
including native PK **[−0.009761, +0.004918]** and fixed-T0 PK
**[−0.009906, +0.016443]**. A small point increase alone does not select a
replacement.

Native uses each epoch's captured ontology; fixed T0 constructs both epochs
on the March 25 ontology with the same original terms-of-interest mask.
Their populations differ, so their absolute scores are not a before/after
comparison. Native PK has 1,954 parsed protein rows and 322 residual-positive
rows after exclusions; fixed-T0 PK has 319/319. NK and LK have only eight and
59 residual-positive proteins in each view.

Under the unchanged native reference classifier, **NK** means no admitted
T0 function in any GO aspect; **LK** means prior knowledge in another aspect
but newly annotated biological process; **PK** means new functions in an
already known aspect, with T0-known functions excluded. The
[original protocol](CONTEXTUAL_COMBINATION_PROTOCOL_20261115.md) and
[pinned native reference recipe](../../tools/contextual_combination/reference_recipe/README.md)
retain the full definitions and evidence rules. Fmax is the best benchmark
F1 on the fixed threshold grid, not an accuracy percentage or deployed
confidence threshold. The 2,000 paired whole-protein intervals are
conditional, unadjusted development descriptions.

## What was qualified and completed

The candidate combines **LocalPlus + observed fitting-label frequency + the
original 40 GOA context channels**. Five exact full-sequence folds exclude
each fitting fold from its graph-parent seeds and frequency/prior
calculations. Validation and final features use all original fitting rows.
Native head availability, alias-score merging, LocalPlus replay and original
full-fit priors passed their compatibility checks before fitting.

One unchanged eight-layer native GCN recipe ran for 20 epochs, with the
author's best-three-checkpoint averaging on the already consumed validation.
It retained the original 4,040 fitting proteins, 208,835 positive memberships,
27,942 output terms and dated contexts. All 3,300 final forecasts were complete
before scoring; the original model service was restored and verified healthy.
The [execution receipt](training_followup_20261115/execution.json) records the
qualification, fit, forecast and assessment chain.
The [retention receipt](training_followup_20261115/numerical_replay_receipt.json)
records verified private copies of all six new count files and native curves;
the fitted model and full statistical report are also retained privately.

This is **one combined input-profile change**, not an isolated estimate of
cross-fitting's effect or a full ProtBoost reproduction. DeepGO is absent
from this candidate; its removal does not establish leakage in the earlier
model. Annotation frequency is not biological prevalence. The
[PU-GO qualification](training_followup_20261115/pu_qualification.md) did not
admit a positive-unlabeled loss, and the native benchmark loss is unchanged.
Exact-sequence folds do not establish family, study or GOA-source independence.

The [complete aggregate report](crossfit_development_20261115/report.html) and
[safe summary](crossfit_development_20261115/summary.json) preserve all six BP
cells, all 23 methods and 324 contrasts: 192 earlier contrasts plus 132 new
ones. Earlier scalar results and paired draws were retained. No new success
gate, threshold selection, biological-negative interpretation or automatic
application change follows. Further comparison on this consumed reference
cannot supply independent confirmation.
