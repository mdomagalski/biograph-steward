# External perturbation comparison — November 13

We completed a new, controlled external functional comparison. Adding historical
Reactome co-complex context modestly improves the earlier experimental-support
ranking in both tested cell contexts, but **does not outperform native STRING
combined confidence on the fixed primary readout**. We therefore do not promote
the new context priority to automatic pruning. The hosted graph is unchanged.

This is a biological measurement outside the previously consumed fitness,
IP-MS and phosphoproteomic references. It evaluates functional neighbour
prioritization, not whole-graph truth, physical binding, clinical accuracy or
unseen-edge link-prediction precision. The two cell contexts are from **one
study**, not independent-study replication. No model was trained.

## What was tested

The source-qualified historical graph has 3,172 present proteins and 89,665
original pairs. Of these, 81,416 pairs are eligible for ranking; every graph view
retains exactly 65,132 eligible pairs plus 8,249 protected source pairs. The
same previously defined native spanning forest preserves source connectivity.
One additional declared lookup target was not found in the source graph and is
not included as a graph protein. Approved, unambiguous HGNC mapping links 3,139
present proteins to unique Ensembl genes; unresolved mappings abstain.

The new candidate puts **one binary co-complex-context flag** first, followed
by the complete unchanged human-experimental/combined-confidence/pair-ID order.
The comparison includes all six original rankings: native combined confidence,
human experimental support, Network Enhancement, degree product, edge-masked
MPS and experimental support including transfer. There are no fitted weights,
new thresholds, outcome-selected pathways or extra evidence votes.

We reused the official [Pathway Commons 12 Reactome extended SIF](https://download.baderlab.org/PathwayCommons/PC2/v12/),
not a custom BioPAX projection. Its metadata pins Reactome 69, May 2019; the
release was distributed in September 2019. Its 2019 content and the actual
December 2018 STRING weights precede the experimental study's December 2021
preprint. Historical context is used only for this temporal comparison; the
current app source layer is not replaced by an old database.

The projection's ambiguous or mixed gene-product nodes are excluded: 100 pure
protein nodes have multiple HGNC symbol cross-references and two disagree with
their participant symbol. Exactly one matching symbol plus a strict human
HGNC/baseline mapping is required. Of the eligible baseline pairs, 16,407 have
this released co-complex context. The [native relation definitions](https://www.pathwaycommons.org/pc2/formats)
and [Paxtools method](https://doi.org/10.1371/journal.pcbi.1003194) distinguish
co-complex from direct binding. Family expansion, merged gene products and lost
proteoform/compartment states limit the projection. Reactome already contributes
to Pharos/STRING; this adds context rather than independent corroboration.

The actual released Paxtools 6.0.0 CLI was also checked under Java 21 with a
1 GiB memory cap. Synthetic conversions distinguish complex versus catalytic
relationships and demonstrate family expansion and absent taxon enforcement.
We use the already released 2019 SIF for scoring, not output from a newly
configured converter. Shaded runtime dependencies retain their own licenses.

## External reference and fixed readout

[Replogle et al. 2022](https://pmc.ncbi.nlm.nih.gov/articles/PMC9380471/)
measured transcriptional responses to nominal gene knockdowns. We used the
[original author-normalized pseudobulk files](https://api.figshare.com/v2/articles/20029387):
K562 genome-wide day 8 and RPE1 essential-gene day 7. Author MD5s match; files
are CC BY4.0. The newer third-party reanalysis was held because its catalog
accession does not match the named genome-wide source study.

The primary readout is mean signed Pearson correlation with each query's top
`min(10, measured eligible degree)` neighbours, averaged equally across the
same queries in every arm. This prevents a ranking from improving its mean by
simply dropping difficult query genes. No missing pair is a negative label.

We use all genes retained in the author's normalized files and zero the exact
own-target expression feature before calculating Pearson correlation, following
the published masking convention. This is a declared broader-feature adapter,
**not** exact reproduction of the paper's selected strong-perturbation/HVG
analysis. Targets require one unique Ensembl perturbation row and at least 25
filtered cells; nonfinite/constant profiles abstain in the fixed first pass.
Nominal guide identity does not independently certify on-target activity.

K562 is the primary context; RPE1 is a separate cell-context replication.
`k=1/5`, absolute correlation at `k=10`, and global 80%-budget retention are
declared secondary diagnostics. The main candidate must improve over human
experimental support, native confidence **and** Network Enhancement in both
contexts to meet the project's descriptive positive rule. Query bootstrap
intervals use 2,000 fixed paired draws; shared partners and the single underlying
study prevent treating them as independent biological replicates or IID edges.

The final protocol SHA256 was recorded outside the frozen directory before
opening expression X:
`c9acbfcc50e969553be7c39f17f35adca29a64c4c60e3f9f289900abed082d30`.
Pre-value software-review fixes and the unscored first preparation are preserved.
Paper aggregate examples and annotation/QC metadata had been read during
qualification; this was not a completely blinded reading of the whole study.

## Fixed first-pass result

Values below are **mean query correlations**, not percentages accurate.

| Ranking | K562, 1,508 queries | RPE1, 662 queries |
|---|---:|---:|
| Native STRING combined confidence | **0.08755** | **0.34410** |
| Reactome co-complex then human experimental | 0.08631 | 0.34132 |
| Human experimental, previous primary | 0.08436 | 0.33863 |
| Network Enhancement | 0.06447 | 0.31445 |
| Degree-product control | 0.06441 | 0.28430 |
| Edge-masked MPS | 0.06210 | 0.29503 |
| Experimental including transfer | 0.08500 | 0.33727 |

Candidate minus previous primary is +0.00195 in K562 (descriptive query
interval 0.00112 to 0.00281) and +0.00268 in RPE1 (0.00083 to 0.00455).
Candidate minus native confidence is −0.00124 (−0.00248 to 0.00001) and
−0.00278 (−0.00561 to −0.00005), respectively. The predeclared overall positive
rule is **not met**. A favourable secondary `k=1` result in RPE1 does not
replace the negative primary comparison.

The equal global pruning budget changes only 13 retained pairs relative to the
previous experimental-priority view. In the first-pass measured subset, the
candidate's conditional mean correlation is 0.10822/0.33049, versus
0.10823/0.33047 for the previous primary. This is no demonstrated meaningful
pruning improvement. Network Enhancement covers more measured queries with a
higher conditional retained-pair mean, while prioritizing neighbours less well
on the fixed per-query primary. Different endpoints have different denominators;
do not select a universal winner from whichever diagnostic looks favourable.

## A known processing capability recovered reference coverage

Independent inspection found positive infinity already present in the original
normalized files. It affects 458 of 1,986 initially eligible K562 profiles over
73 genes and 64 of 734 RPE1 profiles over two genes, ATF3 and CCL2. The original
predeclared rule excluded those whole profiles; it did not impute values.

Before inventing a remedy, we inspected the paper-linked author's framework.
[`CellPopulation.where(..., dropna=True)`](https://github.com/thomasmaxwellnorman/Perturbseq_GI/blob/3b25109aeb9c0c2026bd70abd50304a0ad4e5395/perturbseq/cell_population.py#L316-L318)
already replaces infinity with missing values and drops affected **gene columns**.
Its normalization divides by control standard deviation without a zero-SD guard.
That is consistent with the observed infinities, but the deposited bulk files
lack the exact denominators, so the cause is not proven. We do not assert that
the authors used this optional column policy in their published analysis.

A separate **post-exposure technical sensitivity** applies that native operation
across the entire author pseudobulk file before choosing graph targets. The mask
is the same for every arm, with no feature selection by performance. All source
rankings and budgets remain fixed; no value is replaced with zero or a cap.

| Ranking after documented column-QC sensitivity | K562, 1,962 queries | RPE1, 728 queries |
|---|---:|---:|
| Native STRING combined confidence | **0.08621** | **0.34703** |
| Reactome co-complex then human experimental | 0.08421 | 0.34477 |
| Human experimental | 0.08192 | 0.34138 |
| Network Enhancement | 0.06097 | 0.31696 |

The mask retains 8,175/8,248 K562 features and 8,747/8,749 RPE1 features. All
1,986/734 eligible target profiles then have finite, nonconstant values; some
targets still have no measured eligible graph neighbour. The result agrees
with the first-pass conclusion. This closes a **reference-processing coverage
gap**, not a graph-accuracy gap. Discarded features can carry important biology;
missingness need not be random. It is not a new untouched confirmation.

The original sensitivity-policy text also mentioned absolute correlation, which
that adapter did not compute. No such QC result is claimed. The original policy,
executed source and signed results remain preserved with an explicit wording
erratum; the current adapter text accurately describes its outputs.

## Verification and consequences

Nine optional synthetic tests check Pearson against SciPy, target masking,
identifier ambiguity, equal query budgets, exact two-context requirements,
freeze tampering and literal equivalence to the author's Pandas nonfinite-column
operation. An independent agent recomputed 3,584 first-pass and 2,107 sensitivity
pair correlations with SciPy; all sampled query means agree within `1e-12`.
Every original source/ranking/reference hash still matches its freeze. No
production data, model, Neptune configuration or hosted application was changed.

We keep native confidence as a strong task-dependent baseline and keep richer
Reactome context for interpretation. This study does not reverse the earlier
OpenCell retention trade-off, where the experimental priority retained three
more strict positive pairs than native confidence. There is no general winner
across all biological tasks, and this new reference is now consumed.

Whole-graph biological accuracy still needs claim-compatible labels for a
representative sample of the actual heterogeneous graph. Source-annotation
existence, causal regulation, complex membership and conditional therapy
response need different label semantics. Public curations can label compatible
subsets; unlabelled claims must remain unknown under the existing stratified
estimator. The new SNOOPPI review does not close this gap: exact sequence-specific
direct-interaction labels do not directly score the graph's broad annotation
records, and current-cohort coverage/lineage is unqualified. A sequence/construct
eligibility audit must precede opening those labels or fitting a predictor.

The next prediction increment requires a justified method change and a new
unopened reference, selected before outcomes. The evidence here does **not**
justify adding a larger learned model, tuning a Reactome weight until it wins,
or automatically deleting low-ranked source claims as biologically false.
Team UX feedback and expert biological adjudication remain separate activities.

[Aggregate machine-readable results](perturbation_transfer_20261113_summary.json)
and the [optional reusable runner](../../tools/perturbation_transfer/README.md)
contain all arms and operating-point coverage. Original author bytes, protocol,
exposure receipts, exact executed code, numerical reviews and both result sets
remain under Git-ignored `runs/scientific_next_20261113/` with their source terms.
The current protected AWS reviewer site remains available; Brev/GPU inference
is not needed for this completed CPU evaluation.
