# Contextual combination: fixed evaluation rules

The question is whether an established context-aware combiner improves later
human GO annotation recovery over LocalPlus. This supporting function task is
separate from the challenge's same-learner graph-enrichment comparison.

The scientific implementation and rules were committed as `a06af0b` before
reference opening. Every final forecast was sealed before the independent
opening audit. The complete machine-readable rules are
[protocol.py](../../tools/contextual_combination/protocol.py). They take
precedence over this explanation.

## Reference and endpoint

Use the pinned LAFA/democafa reference-construction helpers without changing
their evidence, sequence or ontology rules. The actual human GAF dates are
**April 10 and November 4, 2026**. Available GO-basic content dates are March 25
and July 26. The later GAF names a newer GO-plus release, so retain two views:

- **Native:** each epoch uses its captured ontology.
- **Fixed T0:** construct both epochs on the March 25 ontology, retaining the
  same primary terms-of-interest mask.

The forecast frame retains all **3,300** native target identities, including
proteins without an old graph prediction. The primary endpoint is **PK
biological-process ordinary micro-Fmax**. PK excludes functions already known
at T0. Keep all PK/NK/LK by MF/BP/CC cells in both views, including unavailable
cells. These settings and aspects have different eligible populations.

A declared gain over a comparator requires a positive observed difference and
a paired 95% interval wholly above zero in **both** primary views. Use 2,000
paired whole-protein bootstrap draws, seed 20261113, after per-protein counts
reproduce every ordinary native curve column within `1e-12`. Intervals are
conditional and unadjusted. The final threshold grid is `.001`–`.999`.
Resample the complete native parsed protein frame. The unchanged evaluator can
retain rows whose positives are all removed by the known-term/TOI masks; their
predictions can still contribute false positives under its convention. Report
the raw frame and the smaller residual-positive population separately.

## Learning and fair controls

Reuse the source-pinned ProtBoost zero-layer MLP and eight-layer GCN with the
author's batch size, optimizer, 20 epochs and three-checkpoint parameter
averaging. Inputs combine LocalPlus, the released DeepGO-SE ensemble and
nonexperimental GOA context. One additional BPO GCN uses the author's richer
evidence/relation feature construction, with explicitly qualified file-schema
adaptations. Its 40 channels describe one GOA source.

Training uses 4,040 allowed proteins. Model/checkpoint and mixture-weight
selection use 797 previously consumed validation proteins. Exclude final
accessions, identical full sequences and identical first-1,022-residue model
inputs. Select each aspect's context model by its full-precision validation
score, with the fixed simplicity tie rule. New reference terms cannot affect
selection. Model axes remain historical; evaluator projection is separate.

Retain complete original parent heads and precision, matched soft-processing
parents, equal and validation-weighted mixtures, both context architectures,
full T0 nonexperimental annotations and training-label frequency. In addition:

- **Matched seed update:** original LocalPlus seeds plus exactly the full
  fitting repertoire for the same 4,040 training proteins. The graph/scorer stay
  fixed. Keep raw and matched-soft forecasts.
- **Current-T0 curated LocalPlus:** replace historical seeds with the complete
  eligible reviewed-human April repertoire using unchanged native helpers and
  the same graph/scorer. Preserve its newer heads. Forecast final targets only;
  evaluating April seeds on the older validation would look ahead.

Report the stacker's performance against each control. Report the fixed
source-update contrasts separately. A successful source update does not
replace an unsuccessful stacker endpoint. The practical current-T0 control also
changes annotation/ontology scope; the 4,040-protein update isolates the added
training supervision more closely.

## Interpretation

This experiment uses the established historical 20,412-protein graph, not the
99-target demonstration workspace. It measures curator-annotation recovery,
including experimental codes **and IC/TAS**. Source dates can describe curation
rather than experiment dates. The provenance audit is descriptive and cannot
change labels, thresholds or model choices.

The study is retrospective and not wholly developer-blind. Homology,
publication and base-checkpoint training independence are unestablished. The
original stacker used out-of-fold parents; this is a qualified temporal
adaptation. Missing curator matches are not biological-negative labels. No
whole-graph accuracy percentage, automatic pruning or app-default promotion
follows from these measurements.

Source revisions, adaptations and the optional reference-reproduction recipe
are in the [implementation guide](../../tools/contextual_combination/README.md).
