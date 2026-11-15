# Context-aware prediction: completed later-annotation comparison

**The preselected context model improves on retained LocalPlus in both fixed
primary reference views. Updating LocalPlus's annotations also helps.
The learned model's primary biological-process advantage over fully updated
LocalPlus remains uncertain; secondary function and location results improve.**

This November 15 assessment closes the previously pending comparison. It tests
recovery of later human Gene Ontology (GO) curator annotations, a supporting
function-prediction task. It does not measure the correctness of every Pharos
edge or replace the challenge's separate same-learner graph-enrichment tests.

## Main result

The fixed primary endpoint is ordinary micro-Fmax for **partially known (PK)
biological-process functions**. PK removes functions already known at the
starting snapshot. Higher Fmax means better recovery under this benchmark;
it is not an accuracy percentage or a deployed confidence threshold.

| Primary reference view | Retained LocalPlus | LocalPlus with current annotations | Selected context model |
|---|---:|---:|---:|
| Epoch-specific ontologies | 0.05473 | 0.05884 | **0.07343** |
| Starting ontology held fixed | 0.17155 | 0.18277 | **0.21009** |

| Paired difference in Fmax | Epoch-specific view: difference [95% interval] | Fixed-ontology view: difference [95% interval] |
|---|---:|---:|
| Context model − retained LocalPlus | **+0.01870 [0.00240, 0.03507]** | **+0.03854 [0.00803, 0.06914]** |
| Current-annotation LocalPlus − retained LocalPlus | **+0.00411 [0.00096, 0.00754]** | **+0.01122 [0.00421, 0.01766]** |
| Context model − current-annotation LocalPlus | +0.01459 [−0.00190, 0.03200] | +0.02732 [−0.00424, 0.05957] |

The predeclared rule requires a positive point difference and an interval
entirely above zero in **both** views. The first two comparisons pass; the
third does not. These are conditional, unadjusted paired intervals from 2,000
whole-protein resamples, not independent-study replication or a guarantee of
future performance.

The selected model also passes both primary views against the matched
4,040-training-protein annotation update, the flat nonexperimental-annotation
control and the development-selected global mixture. Complete forecasts,
unfavorable controls, all 18 cells and source slices remain in the
[full report](contextual_combination_20261115/report.md) and
[aggregate JSON](contextual_combination_20261115/summary.json).

The larger PK secondary groups also favor the selected model against the
**complete current-annotation** control:

| Secondary aspect | Native Δ Fmax [95% interval] | Fixed-T0 Δ Fmax [95% interval] |
|---|---:|---:|
| Molecular function | +0.11945 [0.07825, 0.17536] | +0.15973 [0.10969, 0.21228] |
| Cellular component | +0.09286 [0.07417, 0.11129] | +0.09692 [0.07836, 0.11479] |

These are encouraging aspect-specific findings, with 229/228 and 1,230/1,230
residual-positive proteins respectively. They remain secondary and do not
replace the primary biological-process gate. The
[complete nine-setting contrast table](contextual_combination_20261115/current_annotation_contrasts.md)
also retains uncertain biological-process and sparse no-knowledge results.

## What improved, and why the controls matter

We reused the published **ProtBoost** context-aware stacker and the authors'
**CAFA6** source update. The selected biological-process GCN combines graph
and sequence forecasts with evidence-code, relation and ontology-context
features. Its 40 namespaced channels describe different views of the **same
GOA source**; they are not 40 new databases or independent studies. Qualified
file/schema adaptations and unchanged native mathematical operations are
recorded in the [implementation guide](../../tools/contextual_combination/README.md).

Seven fixed fits used the authors' training recipe. Aspect-specific model
selection used 797 previously consumed validation proteins. The new 3,300
target forecasts, all controls and their source hashes were sealed before the
new reference was opened. No deployed threshold, model or input was selected
from these results; Fmax uses the predeclared evaluation threshold grid.
The [fixed protocol](CONTEXTUAL_COMBINATION_PROTOCOL_20261115.md)
and machine-readable rules preserve the exact boundary.

Two annotation controls address different explanations:

- The **matched fitting update** adds the allowed annotation repertoire for
  the same 4,040 fitting proteins while keeping LocalPlus's graph and scorer.
  It does not reliably improve the primary endpoint in both views. The
  selected context model does outperform it.
- The **complete current-annotation control** replaces historical seeds with
  all eligible reviewed-human curated annotations available at the April
  starting snapshot. This improves LocalPlus in both views. Its broader source
  coverage and ontology scope are practical changes, rather than an isolated
  test of the combiner's training supervision.

The defensible conclusion is that **source freshness and contextual
combination both matter relative to the retained baseline**. Additional
primary biological-process benefit from learning beyond a fully refreshed
baseline is unresolved. A
GCN/MLP contrast also changes depth and capacity, so it does not isolate a
causal effect of ontology message passing.

## Data details that change the interpretation

The actual human GOA snapshots are **April 10–November 4, 2026**. Available
GO-basic content is dated March 25 and July 26. The ontology sensitivity uses
the same starting term-of-interest mask, without substituting a favorable
later vocabulary. All 3,300 target identities were retained, including missing
old-graph predictions. Exact accessions, full sequences and the first 1,022
residues supplied to the sequence model were separated across the stacker's
fitting, validation and final accession frames. This does not establish
independence from the base models' original training proteins or the graph.

The unchanged native evaluator retains **1,954** primary protein rows, of
which **322** retain positive labels after its masks. The other 1,632 rows can
still contribute false positives. The fixed-ontology view has **319/319** raw
and residual-positive rows. Bootstrap samples preserve each complete native
frame. This population difference explains why absolute scores across the
two views must not be read as a direct before/after comparison.

The graph is the historical **20,412-protein** source used by the reference
methods, with retained 2023 annotations. It is not the current **99-target**
Pharos demonstration. The source contexts preserve their dates. Later curator
annotations can cite older experiments; the native reference includes eleven
experimental evidence codes **plus IC and TAS**. No unmatched prediction is
declared biologically false.

The [complete primary-label provenance audit](contextual_combination_20261115/provenance/README.md)
traces all 3,254/3,243 positive protein/function pairs to eligible captured
source rows. Those pairs draw on only 475/472 distinct annotation rows and
272/271 literal publication identifiers. Most label-to-row links are inherited
ontology ancestors, rather than separate experiments. Experimental, IC and TAS
support links are counted separately. This checks the reference's source
traceability; it is not independent confirmation of every label. Publication
ages remain unverified, and annotation dates are not used as experiment dates.

All PK/NK/LK and molecular-function/biological-process/cellular-component
results are reported. The new NK biological-process reference contains only
eight positive proteins; sparse secondary cells cannot establish broad
transfer. Near-homology, publication overlap, base-checkpoint training
independence and independent-study replication remain unestablished. The
study is retrospective and not wholly developer-blind. This qualified
temporal stacker adaptation also differs from the original author's
out-of-fold parent-training design.

## Verification and retained artifacts

An independent numerical audit within this development session checked all
18 cells, 49 aspect/arm forecasts, native curves and contribution counts,
all five bootstrap families, all eight success flags, all 134 source pins and
the seal → admission → reference-opening order. It is an arithmetic/source
audit, not an independent biological expert assessment.

- [Compact audit receipt](contextual_combination_20261115/numeric_audit.json).
- [All primary control intervals](contextual_combination_20261115/figures/contextual_pk_bpo_forest.png) and [separate annotation-refresh intervals](contextual_combination_20261115/figures/source_update_pk_bpo_forest.png).
- [Standalone aggregate HTML report](contextual_combination_20261115/report.html).
- [Reproduction recipe and source-date guards](../../tools/contextual_combination/reference_recipe/README.md).
- Raw aggregate result SHA256: `2dfebc4e855df8682335484cb39b5100f518363fa74b1b24b66ca3c4cdffdf98`.
- Public summary SHA256: `b29079b576756272b3098ed3cbaf8eb60e9415693edb75d3d524a429209481a2`.
- Pre-opening scientific checkpoint: `a06af0b`.

Exact source archives, fitted checkpoints and averaging states have been
copied back from Brev and hash-verified locally. They remain separate research
recovery artifacts, not part of the dependency-light core application ZIP.
No graph, pruning rule or app default was automatically changed.

## Delivery decision

Present this as a **supported, bounded function-recovery gain** alongside the
working evidence app. Preserve the negative enriched-graph and pruning
comparisons. Finish reviewer feedback, the permitted graph-plus-baseline
handoff and the final public release. A stronger future claim needs a new
untouched window or independent benchmark, with the current-annotation
baseline fixed from the outset; refitting on this now-consumed window would
not supply that evidence.

The method choice follows the [ProtBoost paper](https://arxiv.org/abs/2412.04529)
and [author code](https://github.com/btbpanda/CAFA6-updates/tree/0ee85d2f07f724be1721ea39211f1b364535f976).
The separation of annotation growth from algorithmic gain follows the
[CAFA4 assessment preprint, June 2026 revision](https://pmc.ncbi.nlm.nih.gov/articles/PMC13174626/).
