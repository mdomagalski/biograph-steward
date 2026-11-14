# Method complementarity and a fixed review budget

**Complete; no automatic adoption.** The methods return different predictions,
but the fixed fusion does not establish an advantage over the better parent
across the designated tasks. All twelve diagnostic strata, twenty-four parent
points, twelve fusion points and twenty-four paired contrasts are retained.
The source-frozen question was whether DeepGO and the retained strict-source LocalPlus predictor
recover different curator-supported functions, including functions absent
from the strong pre-existing annotation control. Their separate Fmax values
and marginal confusion counts cannot answer this question.

The [earlier shortlist assessment](DEEPGO_SHORTLIST_20261114.md) measured
ancestor-related redundancy within each method. It did not retain a public
case-level list of their shared or unique successes. The unsuccessful
[GeneMANIA/context combination](COMBINED_CONTEXT_AND_SKILLS_20261114.md)
combined a graph method with fuller source context; it did not test fusion of
DeepGO and LocalPlus predictions. The present comparison changes neither
earlier result nor its failed adoption rule.

## Established methods and the verified gap

Protein-function integration is well established.
[GOLabeler](https://doi.org/10.1093/bioinformatics/bty130) combines component
predictors using learning to rank.
[ProtBoost](https://arxiv.org/html/2412.04529v1) combines model predictions and
electronic annotations with learned stacking; its paper describes protein
cross-validation and a small separate stacking holdout. Its
[released code](https://github.com/btbpanda/CAFA5-protein-function-prediction-2nd-place)
is a substantial training/inference pipeline, not pretrained fusion weights
for the models used here.
[DeepGOPlus](https://pmc.ncbi.nlm.nih.gov/articles/PMC9883727/) uses a weighted
combination of similarity and CNN scores. Its
[author implementation](https://github.com/bio-ontology-research-group/deepgoplus/blob/master/predict.py)
uses namespace-specific weights and later ontology propagation. Those
components, weights and output budget cannot simply be substituted for this
project's different predictors.

The project already has qualified forecasts, deterministic top-three ordering,
native CAFA identity/ontology/mask/count APIs and paired bootstrap code. The
remaining implementation gap is reconstructing cross-method selected-term
membership and evaluating one scale-independent combination. No new predictor,
calibration fit, training labels, broad framework or source service is needed.

The fixed baseline adapts
[reciprocal rank fusion (Cormack, Clarke and Büttcher, 2009)](https://cormack.uwaterloo.ca/cormack/cormacksigir09-rrf.pdf).
For a term present at one-based rank `r` in a supplied list, it adds
`1 / (60 + r)`; an absent term contributes zero. Both methods have equal weight.
The constant 60 comes from that published method, rather than a search on these
outcomes. The cited experiments concern information retrieval, so this is an
explicit **truncated-list transfer baseline**, not a claim to replicate a
biomedical ensemble result. The formula is implemented directly with exact
rational arithmetic for ties; existing ranking and scientific scoring APIs
remain in use.

## Declared populations and source semantics

All four existing frames and all three GO aspects are retained:

| Frame | Native task | Known-term handling |
|---|---|---|
| Original protein cohort | Partial knowledge (PK) | Native known-at-t0 closure excluded |
| Additional protein cohort | Partial knowledge (PK) | Native known-at-t0 closure excluded |
| No knowledge | NK | Native `exclude=None` branch |
| Limited knowledge | LK | Native `exclude=None` branch |

The historical ontology, canonical/alternative-ID parser, `fill` propagation,
terms of interest, roots policy, IA values and reference populations remain
the established native contract. Existing PK shortlist summaries must reproduce
before new overlap outcomes are admitted. Empty known masks are not substituted
for the native NK/LK count branch. Full-frame and per-protein calls must agree
under the existing scale-aware six-column count tolerance.

The annotation control is a **membership footprint**, not a third ranked voter:
its admitted predictions all score one. Arbitrarily choosing three tied control
terms would not provide a meaningful third ranking. The audit distinguishes:

1. Canonical IDs represented literally in the released baseline prediction file.
2. IDs added only by this comparison's native `fill` closure.
3. IDs absent from that closure.

The unchanged native library parser's `mode=None` branch is mechanically
qualified for the first footprint, including alternative IDs and duplicate
maximum handling, against its actual pinned implementation. It is not an
advertised CAFA command-line mode. The fixture contrasts that branch with
`fill`. “Literal released baseline” does **not** establish a literal original
GOA/GAF assertion: upstream processing of the released prediction file cannot
be undone by disabling propagation in the local reader. Baseline absence is
not proof of a new biological discovery.

## Diagnostic and single-combination rules

Both parents retain the existing source-qualified positive-score top three,
descending by their own scores with canonical GO ID ties. The audit partitions
their exact shared terms, DeepGO-only terms, LocalPlus-only terms and union.
Each bucket records selected, curator-supported and reference-unmatched pairs,
IA support and the three baseline-membership strata above. Exact overlap is
separate from nonidentical ancestor/descendant relationships. No related-term
filter or reranking is fitted to the reference.

A reference-aware oracle caps union support at three slots per protein and
compares it with the best parent's support for that protein. Both quantities
use future reference knowledge and are diagnostic ceilings, not usable
selectors or attainable performance claims. The same diagnostic is recorded
for support absent from the baseline closure.

The execution gate is **label-free**: if any eligible protein in the declared
MFO frames has different parent top-three sets, execute the already fixed RRF
baseline for all twelve strata. Otherwise no fusion points or intervals are
generated. This is a structural opportunity check, not a statistical utility
threshold or a screen for favorable curator outcomes. Oracle values and
supported-only subsets do not control execution.

RRF uses only the two existing ranked lists, so its candidate union contains at
most six exact IDs. It returns at most three, breaks exact rational-score ties
by canonical GO ID, and performs no ancestor expansion after selection. There
is no offset/weight/cutoff sweep and no selection of a favorable cohort. A
larger union alone is never compared with a parent's three-slot result as if
the review budgets matched.

The primary review-budget endpoint remains curator-supported slots divided by
three times the native eligible population. Coverage, returned-list PPV,
recall, unused slots and IA point readouts remain distinct. The single fusion
has twenty-four ordinary paired contrasts: both parents, four frames and three
aspects. They reuse the existing paired SciPy percentile bootstrap with 2,000
draws, seed 20261113 and the same eligible proteins within each comparison.
MFO is the designated focus; all BPO/CCO readouts remain visible. These
conditional intervals are not multiplicity-adjusted confirmation.

## Interpretation and delivery boundaries

All these reference outcomes were already exposed during project development.
This plan can assess complementarity on consumed data; it cannot turn the
result into a new blind test. NK/LK categories do not imply Pharos Tdark or
training-unseen proteins. Training/homology overlap, shared source supervision,
GO hierarchy dependence and incomplete curator labels remain limitations.
Shared predictions are not independent experimental confirmations, and
reference-unmatched predictions are not asserted to be biologically false.

Raw forecasts, selected identities, reference rows and per-protein numeric
artifacts stay on Brev. The optional standard-library publisher verifies the
frozen source/runtime binding, all twelve diagnostic strata, twenty-four
parent points, complete conditional fusion outcomes, native count gates,
matched row order and aggregate partition identities. It does not follow
private source paths, load a model or reopen cases. Public JSON/HTML retain
source hashes, complete aggregate outcomes and the no-adoption boundary.

No app default, source graph, accepted annotation or pruning rule changes from
this development assessment. Any learned fusion or deployment decision would
need a separately defined validation boundary. CPU and memory on the existing
Brev instance suffice; no new model inference, GPU runtime or source retrieval
is required.

The executed source plan was frozen before these new diagnostic outcomes:

- Source freeze FILE SHA256: `c5279b9d9e1ed890bc423fc4ebe43b488994fe9ad220966554e50d3fb9ffb348`
- Source freeze content seal: `dfc054b24d2021c152f447625a0b4cfafd95aa81c777bcc565acdb3d0d15c1d4`

The frozen producer passed source review and invented-data checks, including
native-library fixtures, before the bounded CPU execution. The aggregate-only publisher is a
separate delivery tool and is not imported by the measurement process.

## Completed results

The [complete static report](method_complementarity_20261114/report.html) and
[sanitized aggregate](method_complementarity_20261114/report.json) retain the
whole declared comparison. The label-free execution gate passed: parent MFO
sets differ for 480/525 original PK, 2,081/2,192 additional PK, 36/39 NK and
57/60 LK eligible proteins. The single fixed RRF rule was therefore executed
for every declared stratum; no oracle or curator-support subset selected the
method, its weights or its evaluation population.

### What the overlap reveals

MFO exact pooled Jaccard is about 0.18–0.30, so the two methods often return
different terms. Low overlap is not sufficient evidence that combining them
helps. Unique supported terms also frequently occur in the pre-existing
annotation footprint. These are protein/GO pairs, not counts of independent
mechanisms or experiments.

| Frame | Ordinary / IA N | Exact pooled Jaccard | Shared supported pairs | DeepGO-only supported / baseline-absent | LocalPlus-only supported / baseline-absent |
|---|---:|---:|---:|---:|---:|
| Original PK | 525 / 525 | 0.209454 | 111 | 98 / 40 | 85 / 58 |
| Additional PK | 2192 / 2191 | 0.178147 | 413 | 499 / 174 | 366 / 237 |
| NK | 39 / 39 | 0.297753 | 25 | 45 / 3 | 11 / 8 |
| LK | 60 / 60 | 0.252632 | 44 | 77 / 9 | 29 / 17 |

Agreement is not a uniform support proxy. In original/additional PK, shared
MFO predictions have recorded curator support in 20.4%/20.8% of selected pairs,
versus 9.5%/10.9% for DeepGO-only pairs and 8.3%/8.1% for LocalPlus-only pairs.
In NK the shared fraction is 25/53 (47.2%), below DeepGO-only 45/64 (70.3%);
in LK it is 44/72 (61.1%), below DeepGO-only 77/108 (71.3%). These buckets
also differ in specificity and annotation reuse. The ratios are descriptive,
not matched significance tests, calibrated confidence or causal explanations
for fusion performance. They show why consensus alone cannot serve as a
general biological acceptance rule.

In NK, only 3 of the 45 DeepGO-only supported MFO pairs are absent from the
baseline closure; in LK, 9 of 77 are absent. LocalPlus has fewer unique
supported pairs overall, but 8 of 11 in NK and 17 of 29 in LK are absent from
that footprint. Thus much of DeepGO’s unique supported top-three recovery in
these sparse-annotation tasks repeats already available annotation information.
This does not diminish the prediction result, but narrows its added-information
interpretation. Baseline absence still does not establish biological novelty.

Nonidentical ancestor/descendant pairs occur across the two MFO lists for
298/525 original PK, 1,169/2,192 additional PK, 33/39 NK and 52/60 LK proteins.
Some exact disagreement therefore concerns hierarchical levels rather than
wholly separate functions. This is descriptive; no semantic-equivalence
judgment or hierarchy-based reranking was inferred.

### All fixed-budget point results

The endpoint below is supported slots divided by three times the native
eligible population. It is not Fmax or a whole-graph accuracy percentage.
Returned-list PPV, recall, IA points, coverage and unused slots remain in the
complete aggregate.

| Frame | Aspect | Ordinary / IA N | DeepGO | LocalPlus | Fixed RRF |
|---|---|---:|---:|---:|---:|
| Original PK | BPO | 833 / 832 | 0.172469 | 0.205682 | 0.190476 |
| Original PK | MFO | 525 / 525 | 0.132698 | 0.124444 | 0.134603 |
| Original PK | CCO | 445 / 445 | 0.227715 | 0.268914 | 0.241199 |
| Additional PK | BPO | 2826 / 2825 | 0.183770 | 0.206063 | 0.201463 |
| Additional PK | MFO | 2192 / 2191 | 0.138686 | 0.118461 | 0.140055 |
| Additional PK | CCO | 1450 / 1450 | 0.293103 | 0.315172 | 0.294943 |
| NK | BPO | 44 / 44 | 0.590909 | 0.484848 | 0.560606 |
| NK | MFO | 39 / 39 | 0.598291 | 0.307692 | 0.444444 |
| NK | CCO | 118 / 118 | 0.833333 | 0.810734 | 0.844633 |
| LK | BPO | 227 / 227 | 0.643172 | 0.646109 | 0.653451 |
| LK | MFO | 60 / 60 | 0.672222 | 0.405556 | 0.494444 |
| LK | CCO | 197 / 197 | 0.857868 | 0.851100 | 0.871404 |

### All twenty-four paired contrasts

Each cell gives the observed fixed-budget difference, followed by its paired
95% percentile interval. These are ordinary-support contrasts; no new IA or
baseline-absent uncertainty analysis is inferred from them. MFO remains the
designated focus and all BPO/CCO results are preserved.

| Frame | Aspect | RRF minus DeepGO: difference [95% interval] | RRF minus LocalPlus: difference [95% interval] |
|---|---|---:|---:|
| Original PK | BPO | +0.018007 [+0.007203, +0.029212] | -0.015206 [-0.026421, -0.004402] |
| Original PK | MFO | +0.001905 [-0.010159, +0.013968] | +0.010159 [-0.001270, +0.022222] |
| Original PK | CCO | +0.013483 [-0.005243, +0.030712] | -0.027715 [-0.043446, -0.011236] |
| Additional PK | BPO | +0.017693 [+0.012031, +0.023237] | -0.004600 [-0.010383, +0.001533] |
| Additional PK | MFO | +0.001369 [-0.005326, +0.008060] | +0.021594 [+0.015511, +0.027220] |
| Additional PK | CCO | +0.001839 [-0.008741, +0.012644] | -0.020230 [-0.031270, -0.009879] |
| NK | BPO | -0.030303 [-0.068182, +0.007576] | +0.075758 [+0.007576, +0.151515] |
| NK | MFO | -0.153846 [-0.247863, -0.068376] | +0.136752 [+0.068376, +0.213675] |
| NK | CCO | +0.011299 [-0.005650, +0.028249] | +0.033898 [-0.011299, +0.081992] |
| LK | BPO | +0.010279 [-0.013216, +0.033774] | +0.007342 [-0.019090, +0.035242] |
| LK | MFO | -0.177778 [-0.261111, -0.094444] | +0.088889 [+0.033333, +0.138889] |
| LK | CCO | +0.013536 [-0.005118, +0.033841] | +0.020305 [-0.006768, +0.050761] |

Against DeepGO, two of the twelve intervals are positive, two are negative and
eight cross zero. Against LocalPlus, four are positive, three are negative and
five cross zero. These counts describe the complete unadjusted inventory and
do not constitute a separate pooled hypothesis test.

For the designated MFO comparisons, RRF does not establish an advantage over
DeepGO in either PK frame and is worse in both NK/LK intervals. It improves
over LocalPlus in additional PK, NK and LK, while original PK is uncertain.
A universal combination advantage is therefore unsupported. The original
LocalPlus product default and the separately reported DeepGO research results
remain unchanged.

### Baseline-absent support and the oracle ceiling

The following MFO yields count only supported selected terms absent from the
released annotation baseline’s filled closure, using the same three-slot
denominator. They are descriptive point readouts, with no declared paired
intervals. They are not a new acceptance endpoint or evidence of discovery.

| Frame | DeepGO baseline-absent yield | LocalPlus baseline-absent yield | RRF baseline-absent yield | Oracle extra supported slots over per-protein best parent: all / baseline-absent |
|---|---:|---:|---:|---:|
| Original PK | 0.058413 | 0.069841 | 0.067937 | 1 / 1 |
| Additional PK | 0.054440 | 0.064021 | 0.066150 | 20 / 11 |
| NK | 0.076923 | 0.119658 | 0.119658 | 2 / 1 |
| LK | 0.122222 | 0.166667 | 0.166667 | 2 / 1 |

RRF raises this descriptive MFO baseline-absent yield relative to DeepGO in
each frame, while ordinary total support falls substantially relative to
DeepGO in NK/LK. In those two tasks its baseline-absent yield equals
LocalPlus’s; additional PK has a small point increase and original PK a small
decrease versus LocalPlus. This is an objective trade-off rather than a
demonstrated overall improvement.

The MFO union oracle can add only 1, 20, 2 and 2 supported slots beyond a
reference-aware choice of the better parent separately for each protein
(original PK, additional PK, NK, LK). For support outside the baseline closure
those increments are 1, 11, 1 and 1. This suggests that much apparent headroom
concerns choosing between methods for different proteins rather than mixing
more correct terms within a protein. That is an inference from the oracle
diagnostic: the audit does not provide a usable method-selection rule, and
choosing the better parent using future labels is not deployable.

Hierarchy-related lists also remain common after fusion. RRF has a related
MFO term pair in 346/525 original PK and 1,389/2,192 additional PK lists, and
in all 39 NK and all 60 LK lists. The combination is not a redundancy-removal
method. IA readouts can disagree with ordinary counts: for example, NK MFO
IA returned-list PPV rises slightly from 0.602957 for DeepGO to 0.608073 for
RRF, while IA recall falls from 0.213371 to 0.153456. No new IA significance
claim follows.

### Execution and retained decision

Both parents reproduce the earlier PK shortlist contract. The literal/fill
footprints, real native PK/None count branches, complete twelve-stratum
inventory and matched row orders pass their declared gates. The public
projection also verifies the shared/unique/union and baseline partitions,
parent ordinary/IA support reconstruction, strict budget identities and oracle
bounds. Only saved aggregates were opened for publication.

- Completed source report FILE SHA256: `5788098b2beb9e0944629588155589639bbcac4b11f6e02fa4924fae34ec66e1`
- Completed source report content seal: `a0ccfdf8665306fffd21399ab337d2d9f510613a0e39a24bac0b9cbbebc89895`

An independent CPU replay reconstructed all 8,956 fusion selections with an
integer-weight implementation, all twelve overlap/baseline/oracle partitions
and all 36 point summaries. All 24 paired bootstrap distributions match
bitwise and every saved paired summary matches exactly. Native ordinary/IA
per-row counts agree within 2.84×10⁻¹⁴; aggregate differences are zero. This
validates the arithmetic on the same reference. The small review receipt FILE
SHA256 is `6ec6937bb878176f75d060f788ab7ea44bfb39429a3d26e142ed8b2ed970eff6`.
All large arrays and reference rows remained on Brev.

Common benchmark canonicalization does not erase the predictors' different
supervision and ontology vintages. The [qualified DeepGO record](DEEPGO_SE_20261114.md)
retains those differences; these aggregate matches do not establish identical
source meanings, independent experiments, or novelty in today's Pharos.

No weight, offset, threshold, hierarchy filter, favorable subgroup, new model
or automatic policy was selected after these results. The fixed combination
is retained as a completed negative/mixed comparison. The actionable finding
is to preserve method identity, existing-annotation reuse and disagreement
for inspection; this result does not justify replacing the predictor or
accepting graph facts by agreement alone.
