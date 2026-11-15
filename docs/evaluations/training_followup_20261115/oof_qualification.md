# Cross-fitted graph and prevalence inputs: source qualification

**Source review supports one bounded development candidate. It is not ready for
GPU fitting until native CPU parity, actual source admission and resource
checks pass.** The candidate uses existing licensed implementations and keeps
the native model, loss, optimizer and checkpoint averaging unchanged.

The proposed profile has two explicit parents: **LocalPlus and fitting-label
prevalence**, followed by the original 40 source-derived GOA channels. The
graph and prevalence features for each fitting protein are generated without
that protein's fitting fold. DeepGO-SE is absent from this new profile. This
is a combined source/profile change, not an isolated test of cross-fitting or
a full reproduction of ProtBoost.
The exact LocalPlus/prevalence/40-context combination is an untested adaptation
of these established components; source compatibility does not establish a
prediction improvement.

## What the upstream methods establish

The [ProtBoost paper](https://arxiv.org/html/2412.04529v1) describes five-fold
training grouped by identical sequences, followed by a separate stacking
holdout. In the inspected author revision
`52dce6c471337f2820550f779a6a1bb201353b2a`, `train_gcn.py` reads each component's
`oof_pred.pkl` for fitting and `test_pred.pkl` for the stacking validation
frame. The captured source/license hashes are in the
[qualification receipt](oof_source_qualification.json).

Our current adaptation uses fixed historical LocalPlus and published
DeepGO-SE forecasts. The [DeepGO-SE paper](https://doi.org/10.1038/s42256-024-00795-w)
reports Swiss-Prot 2021_04 supervision. Actual checkpoint training and selection
identities have not been reconstructed. That is an unresolved exposure
boundary, not a demonstrated future-label leak. The existing inference intake
deliberately did not select the author's training, validation, test or
neXtProt tables.

The [published model-data record](https://zenodo.org/records/10369249) provides
a separate 7,062,285,322-byte training archive, with publisher MD5
`b3123c103e81ca37aae334ae3ad99df1`. Its metadata specifies CC-BY 4.0. Archived
DeepGO code uses BSD-3-Clause; ProtBoost uses Apache-2.0; the reused LocalPlus
implementation uses GPL-3.0. Optional research adapters must retain their
license scope separately from the MIT core application.

No source-qualified, identity/axis-compatible OOF artifact for our exact
LocalPlus plus six-member DeepGO-SE ensemble has been identified. A generic
author OOF filename does not establish that compatibility. Retraining the
fixed six BP ensemble members for five folds would entail at least 30 base
fits, before the downstream stacker. It is not one additional fit, and its
source-membership, validation and runtime requirements remain unqualified.

## Why one marginal parent needs care

The native `GCNStacker` constructor and dataset support a variable number of
parents. Our source-qualified I/O currently requires two. Constructor support
alone does not show that the one-parent feature semantics are suitable.

For an available marginal parent, the native loader sends
`[0, logit(p), logit(p), logit(p)]` through `LayerNorm(4)` before adding GOA
context. Using the documented [Torch 2.0.1 LayerNorm formula](https://raw.githubusercontent.com/pytorch/pytorch/v2.0.1/torch/nn/modules/normalization.py),
scores 0.01 and 0.10 differ by only approximately **0.00000738** after this
normalization at initialization. The three repeated channels make scores on
the same side of 0.5 nearly scale-invariant, apart from epsilon. This
analytical, invented-vector check is not a trained-model result or an actual
Torch-runtime qualification.

The two-slot proposal keeps the original input width and normalization. Its
second parent is the existing Naive-style `fit_label_frequency` control,
defined by the native marginal fitting prior. It is an explicit forecast
component, with honest parent-axis metadata. It must not be stored under a
DeepGO label or represented as an unavailable DeepGO component.

## Exact preparation boundary for one candidate

1. Preserve the original **4,040 fitting**, **797 consumed-validation** and
   **3,300 final** identities and the January 2023 **27,942-term BP** model
   axis. Use the original full fitting targets, including all known positives
   and allowed `2025_03` additions. Do not substitute the later positive union.
2. Partition fitting proteins into five folds using exact full-sequence
   groups and an explicitly pinned `GroupKFold` implementation. Every fitting
   identity must occur in exactly one held-out fold, with no exact-sequence
   group crossing folds. This does not establish distant-family independence.
   [Version-specific API](https://scikit-learn.org/1.3/modules/generated/sklearn.model_selection.GroupKFold.html)
3. For each fold, remove that fold's fitting identities from the historical
   graph seed table. Keep other legitimate historical graph knowledge and
   the graph/normalizer unchanged. Call the unchanged native `runLocal`.
   The existing `core.run_term` nonempty-positive guard does not cover a
   fold-empty head; native `runLocal` itself accepts empty positives and
   emits zeros. That normal case requires an explicit native parity check.
4. Keep the complete frozen LocalPlus source-head axis in every fold. A head
   with no remaining seed emits an **observed zero**, not a missing-head
   indicator. Reuse native primary/alternative-ID projection and MAX merging.
   The Naive parent emits every fixed model head, including observed zero
   frequencies. Head availability must not be inferred from positive scores.
5. Compute conditional/marginal priors from the full training complement
   **before** native root-positive filtering. Broadcast the complement's
   native marginal vector as the Naive parent for held-out fitting rows.
   Its source must exclude those rows. Reuse `priors_from_full_fit`, rather
   than approximating the author formula. Native BP fitting still selects
   the same 3,557 original root-positive rows after feature admission.
6. Use all 4,040 fitting rows for the validation/final priors and Naive parent.
   The first parent there is the original full-source LocalPlus forecast.
   **Rebuild validation and final feature caches:** their second parent is
   now prevalence, so old caches containing DeepGO scores cannot be reused.
   The original literal context sidecars can be reused unchanged.
7. Preserve the original dated fitting/validation/final GOA context:
   **May 18, 2023 / September 4, 2025 / April 10, 2026**. Do not insert April
   2026 context or labels into the earlier validation task. The original
   full fitting labels and source-derived context retain their own source
   and calibration limitations.
8. Run one original eight-layer, 40-context native model with the original
   seed, 20 epochs, batch 32, optimizer, clipping and postprocessing. Normal
   checkpoint/SWA selection on the already consumed September 2025–March
   2026 validation is temporally compatible with these historical inputs.
   Current April–November outcomes cannot select checkpoints or settings.

LocalPlus computes one neighbor average, `P @ y`; our graph constructor rejects
self edges, and the author normalizer only rescales existing entries. Thus
there is no direct own-seed copy when the admitted graph has zero diagonal.
Cross-fitting changes available neighboring annotations. It addresses a
methodological exposure concern and tests a training regime; it is not a
verified correction of an own-label-copy bug. Actual graph-diagonal and
source-replay checks remain required.

GOA channels are dated source features, not independent studies. Cross-fitting
these two supervised inputs does not establish absence of family overlap,
indirect source reuse, curation lag or future generalization. Missing labels
remain zero under the unchanged benchmark loss; this candidate does not claim
to implement PU-GO or resolve positive/NOT context.

## Existing functions and bounded compute

- Graph and scorer: `core.adjacency`, author
  `normalizeGraphEdgeWeights`, author `runLocal`; source-head grouping from
  `freshness_controls.by_head` and native projection from `prepare`.
- Prevalence and native features: `prepare.priors_from_full_fit`,
  `make_dataset`, `write_feature_memmap`, and the existing Boolean-context
  dataset. Preserve the ordered parent axis in new manifests/model metadata.
- Training: `training.training_author`, `root_positive_rows`, native trainer
  and SWA, with the existing separate consumed-validation evaluator.

The full BP caches have known dimensions: fitting is approximately 4.06 GB,
validation 0.80 GB and final 3.32 GB at nine float32 base channels. New fitting
parent arrays add storage. Existing 40-channel Boolean context files need not
be copied or rebuilt. Require an actual CPU/disk preflight with sufficient
headroom; no wall-time claim is made from source review alone.

The proposed two-slot native architecture has the same tensor shapes as the
qualified BP model, whose earlier full-batch forward/backward fixture needed
27.14 GB GPU tensor memory. That is a useful planning observation, not a new
resource pass. Run the actual forward/backward gate before the one fit; the
existing Nemotron service must be paused and restored exactly if it is running.
No new LLM inference is required.

Before fitting, freeze the candidate, sources, fold assignments, contexts,
parameter budget, validation roles and complete comparison. Retain the old
selected model and all failures. Any new April–November measurement remains
**consumed-reference development**, with every earlier control preserved and
no independent-confirmation, automatic-pruning or default-promotion claim.
