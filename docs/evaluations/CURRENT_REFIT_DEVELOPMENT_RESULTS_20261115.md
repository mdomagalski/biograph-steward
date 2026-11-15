# Current-annotation refit: completed development comparison

**The fixed refit did not establish an improvement over the original context
model. Its intervals against current-annotation LocalPlus still cross zero.
The original model and application defaults are retained.**

This follow-up tests a verified source-age difference using the already
consumed April–November reference. It provides development evidence, with no
independent confirmation or new adoption gate. The original fixed study and
its supported gain over retained LocalPlus remain unchanged.

## Main readout

Ordinary micro-Fmax for partially known biological process (PK BP):

| Method | Native ontology view | Fixed-T0 ontology view |
|---|---:|---:|
| Retained LocalPlus | 0.05473 | 0.17155 |
| LocalPlus with complete current curated annotations | 0.05884 | 0.18277 |
| Original selected context model | **0.07343** | **0.21009** |
| Current-annotation context refit | 0.07306 | 0.19683 |
| LocalPlus with retained and current curated seed union | 0.05595 | 0.17692 |
| Direct current nonexperimental prior | 0.02548 | 0.14617 |
| Direct prior with retained curated memberships added | 0.02353 | 0.13397 |

Compare methods within a view. The native frame has 1,954 protein rows, of
which 322 retain positive labels; the fixed-T0 frame has 319/319. Fmax measures
later annotation recovery under this benchmark, rather than a percentage of
biologically correct graph records.

| Refit minus comparator | Native paired 95% interval | Fixed-T0 paired 95% interval |
|---|---:|---:|
| Original selected context model | [−0.00966, +0.00805] | [−0.02737, +0.00048] |
| Current-annotation LocalPlus | [−0.00201, +0.03045] | [−0.01747, +0.04573] |
| Retained/current curated union LocalPlus | [−0.00008, +0.03229] | [−0.01100, +0.05111] |
| Direct source-union prior | [+0.03588, +0.06709] | [+0.04357, +0.08502] |

These are copied conditional, unadjusted intervals from the same 2,000 paired
whole-protein draws. They describe this consumed-reference follow-up. Every
PK, NK and LK cell, all 22 methods and all 192 declared contrasts remain in
the [complete report](current_refit_development_20261115/report.html) and
[aggregate JSON](current_refit_development_20261115/summary.json), including
unfavorable comparisons.

The no-knowledge and limited-knowledge point scores increase slightly over the
original selected model, but all their intervals against that model and
current-annotation LocalPlus cross zero. These groups have only eight and 59
residual-positive proteins respectively. They do not establish an improvement for sparsely annotated proteins or justify selecting another model from this result.

## What this resolves

The fitting update preserved all 208,835 historical positive memberships and
added 1,941 pre-cutoff memberships across 161 of the original 4,040 proteins.
Fitting context was rebuilt from current T0 source, and priors were recomputed
consistently for fitting and final features. Existing final context and raw
parent forecasts retained their exact bytes. The model kept its published
architecture, training settings and one fixed checkpoint
schedule; no current validation score was computed. All 3,300 forecasts were
complete before this assessment began. The [frozen plan](CURRENT_REFIT_DEVELOPMENT_PLAN_20261115.md)
records the adaptation and its limits.

This update does not demonstrate a remedy for the remaining primary comparison.
It also does not establish that updated context, additional fitting labels or
the fixed checkpoint schedule caused the observed change; those components
were not isolated in separate ablations.

The source controls give a useful additional finding. Adding retained curated
memberships to the current nonexperimental prior lowers its Fmax in both
views, with paired intervals of **[−0.00312, −0.00067]** and
**[−0.01958, −0.00395]**. Retaining historical and current curated seeds also
gives lower LocalPlus point scores than current-only seeds; its fixed-T0
interval is below zero and its native interval crosses zero. More retained
memberships therefore did not improve these prediction inputs. Unmatched
historical annotations are not thereby established as biologically false.

Historical evidence should remain available for audit. Choosing a prediction
input requires its source date, curator state, identity scope and measured
performance. GO describes annotations as a changing account of knowledge and
warns against treating missing annotations as biological negatives.
[GO annotation principles](https://www.geneontology.org/docs/go-annotations/)

The LocalPlus union control receives the candidate's exact augmented fitting
targets and complete retained/current curated seeds. The GCN also uses
DeepGO-SE and 40 nonexperimental context channels. This is a stronger
annotation control; it does not isolate learning as the sole difference.
All 40 channels are views of one GOA source.

## Data-context limits

The [source qualification](CURRENT_REFIT_SOURCE_QUALIFICATIONS_20261115.md)
reproduces 22 positive/NOT target flags. Sixteen also have current direct
curated positives, and recorded form/extension fields do not resolve them.
They remain review flags. The retired RCA evidence code contributes no BP
context to this refit. No labels were flipped or removed to improve a score.

The native full-repertoire loss still treats unlabelled target entries as
zero, a benchmark convention rather than verified negative biology. The fixed
old output ontology, in-sample parent-calibration limitations, curation lag,
shared studies and unresolved base-model exposure remain. The
[sequence audit](CONTEXTUAL_SEQUENCE_SIMILARITY_20261115.md) qualifies family
overlap without establishing distant-family transfer.

The implementation reuses [ProtBoost](https://arxiv.org/abs/2412.04529) and the
[author's CAFA6 source features](https://github.com/btbpanda/CAFA6-updates/tree/0ee85d2f07f724be1721ea39211f1b364535f976).
Transferring the original three SWA epoch positions after refreshing source
data remains a disclosed development adaptation. It is not presented as a
published, independently validated training recipe.

## Verification and delivery decision

The [scalar-copy audit](current_refit_development_20261115/source_to_public_audit.json)
checks all 132 method rows and 192 contrast rows against the completed private
report. All 18 new native curves agree with their contribution counts.
The [execution receipt](current_refit_development_20261115/execution_qualification.json)
records the fixed fit, complete forecasts and exact healthy restoration of
the original Nemotron service. Final weights, three averaging states, source,
counts and numerical receipts are retained privately; dense forecasts and
feature caches remain on the persistent Brev disk.

- Completed private report SHA256: `b7792b0737835d374f2335735aa254e90a609d9a73bf0bfd9f99f9586065eac0`.
- Public summary SHA256: `d2c00101234cfcb1146188b52e3dbad9be60b244301d7c5a892e2af1b69b3f2f`.
- Original public summary remains `b29079b576756272b3098ed3cbaf8eb60e9415693edb75d3d524a429209481a2`.
- Earlier prior-preservation summary remains `a72b4c75282edbb6acf9b7a832a3ff4fdef8655ff5d9bf5bebc89c01cbb39ec7`.

Keep the original qualified model and its bounded claim. Finish the reviewer
handoff and final release. A stronger claim against current-annotation
LocalPlus needs a newly untouched assessment, with current-source controls,
family/study separation and base-model exposure qualified before opening.
This follow-up changes no graph, biological review, pruning policy or hosted
application checkpoint.
