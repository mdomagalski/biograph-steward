# Combined historical profile and published GeneMANIA+

This is one **development** follow-up chosen after the existing PK and NK/LK
results were inspected. It fills the full-source GeneMANIA+ cell on the exact
6,100 already evaluated PK target identities. It is not a new blinded test,
prospective forecast, whole-graph accuracy estimate or hyperparameter search.

The source graph/training bytes are unchanged from the deployed strict historical
profile: 20,412 proteins, 985,863 weighted source pairs and the official known-t0
annotations. The optional GPL author implementation stays separate from the MIT
application. `alpha=1` and `tol=1e-5` remain fixed. The already tested numerical
certificate wrapper calls the unchanged native CG solver and retains raw scores.

The earlier 547-target GM run includes 210 overlapping PK identities (26 original,
184 additional-cohort). Every raw positive prediction on those common identities
must reproduce exactly against a separate same-host replay of the earlier
547-target computation, for all 17,670 training heads, before the new outputs can
be admitted. The original platform-unrecorded file remains unchanged, with its
cross-runtime numerical differences reported separately. No source, reference, threshold or earlier result is modified.

Evaluation reuses the unchanged official CAFA evaluator and the existing released
labels. All six cohort/aspect outcomes, macro/IA/Smin and fixed-0.5 trade-offs stay
visible. Existing 240 outcome slots remain an immutable comparison source. Paired
BPO uncertainty uses the existing 2,000-draw, seed-20261113 protein bootstrap.
Original scoped GM/Local are valid only for the original cohort: the additional
4,806 identities are outside that graph, so a missing old model is unsupported,
not a meaningful zero-score biological comparator.

The published method is the positive-only regularized-Laplacian implementation
from [Law, Kale and Murali](https://doi.org/10.1093/bioinformatics/btaa885), using
the [official code](https://github.com/Murali-group/multi-species-GOA-prediction)
at the previously pinned commit. It does not learn multiple network weights or
execute the full GeneMANIA web server. Prior equal-weight sequence/graph fusions
are preserved negative controls; this follow-up introduces no score fusion.

The practical gate is written before these new cell outcomes are computed:
ordinary and IA BPO paired difference intervals versus matched full strict
LocalPlus must lie above zero on both existing cohorts to retain a combination
advantage. Original-versus-old-GM and the four-cell original-cohort interaction
are descriptive additional contrasts. Any retention remains development reuse,
with all unfavorable controls/readouts retained and no automatic graph acceptance.

The current app's exact one-hop LocalPlus explanations cannot be relabeled as GM
diffusion explanations. This package first measures the missing combination;
it does not alter the application or accept scientific claims.

## Numerical reproducibility control

The first attempt stopped at its exact shared-target check, before scoring any
new cell outcome. On the first training head, all 208 common positive rows were
present, with raw value differences no larger than 1.74e-18. The old prediction
manifest did not record its execution platform; its `/Users` paths are source
provenance rather than proof of its execution architecture. All old files and
the failed attempt remain unchanged.

`matched_replay.py` therefore repeats the exact original 547-target computation
on the same pinned Brev runtime. It preserves all original/replay numerical
differences and uses the existing native residual certificates, without clipping
or replacing the original benchmark. `run_v2.py` retains the **exact** 210-target
gate against that separately executed same-host control. Parameters, source
bytes, score generation, reference labels and outcome policy remain unchanged.
The original 240-slot and NK/LK reports are never rewritten by this control.

This addresses the known distinction between an unchanged floating-point
algorithm and cross-platform bitwise reproducibility. See the official
[NumPy 1.26 numerical-thread configuration](https://numpy.org/doc/1.26/reference/global_state.html)
and the [reproducible BLAS study](https://www2.eecs.berkeley.edu/Pubs/TechRpts/2016/EECS-2016-121.html).

## Completed development result

The fixed retention gate **did not pass**. On the original PK cohort, the
ordinary and IA biological-process differences versus full strict LocalPlus
were slightly negative, with paired intervals crossing zero. On the additional
PK cohort, the ordinary difference was positive (95% interval
`[0.000027, 0.007143]`), but its IA interval still crossed zero. This does not
justify replacing the retained LocalPlus inspector.

The full result keeps all six aspect/cohort cells, including cellular-component
point gains and mixed molecular-function and macro readouts. These observations
do not define a new aspect-specific winner rule. At the fixed 0.5 cutoff, the
native evaluator returned no coverage/curve for five cells; the sixth had very
low recall. Missing operating-point values remain unreported, rather than
substituted zeros. The original-cohort four-cell contrast was negative, so the
earlier method and source-profile improvements did not simply add in this
development comparison.

The aggregate-only delivery artifact is
`runs/combined_improvement_assessment_20261114/report.html`; its sealed
`summary.json` includes every new cell and paired interval, and
`prior_240_outcomes.json` preserves the complete earlier inventory separately.
The application, graph, accepted claims and previous benchmarks remain unchanged.
