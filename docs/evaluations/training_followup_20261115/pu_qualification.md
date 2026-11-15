# Positive–unlabelled training qualification — November 15

**Source qualification is complete. PU-GO is not admitted for the next fit.**
The missing-label problem is real, but the released model is not a compatible
loss replacement for our stacker. This review changes no labels, forecasts,
metric, application code or completed study. No Brev instance, model inference
or fitting was used.

## Verified PU-GO scope

The [primary paper](https://doi.org/10.1093/bioinformatics/btae237) describes a
positive–unlabelled risk/ranking method with frequency-derived GO priors and an
ESM2-15B residual MLP. Its June 2023 Swiss-Prot development set has 79,973
reviewed proteins; its temporal evaluation uses newly annotated January 2024
proteins. Those roles cannot establish an independent assessment of our
already exposed reference. Released training/case identity overlap remains
unqualified because its archive was not downloaded.

The checked [author commit](https://github.com/bio-ontology-research-group/PU-GO/tree/7e6bce9c27ccf48e5f6860af4a815525032f7d82)
has these concrete admission barriers:

| Check | Verified finding and implication |
|---|---|
| Code reuse | Repository metadata reports no license; the license endpoint returns 404, and the full tree contains no LICENSE/COPYING/NOTICE file. `nn.py` has no license header. Permission to copy or redistribute that implementation is not verified. |
| Released data | [Zenodo 11079885](https://zenodo.org/records/11079885) describes a **dataset** under CC-BY-4.0. Its archive is 13,158,312,233 bytes. This metadata does not establish a license for the separate GitHub model code. No archive or weights were downloaded. |
| Feature interface | The released classifier requires 5120-dimensional ESM2-15B features. Our qualified ESM2-3B features have 2,560 dimensions. Padding or relabelling them would not reproduce the released predictor. |
| Resource interface | The author extractor moves the complete 15B model to its requested device without an explicit lower-precision or offload branch. Native feature generation on our L40S has not been qualified. |
| Temporal training | `pu_go_time.py` sets `load=True` inside `main`, irrespective of the CLI flag. Invoking it as a new trainer would load weights rather than perform the expected fit. |
| Formula fidelity | Paper Equation 11 is a pairwise positive-versus-unlabelled ranking term. The released `pu_ranking_loss_multi` uses same-cell sign-masked logits and global positive/unlabelled denominators. These are not literal equivalents. |
| Architecture fidelity | Paper Equation 4 says BatchNorm; released `MLPBlock` uses LayerNorm. This is a recorded reproduction difference, not a silently selected correction. |
| Evaluation interface | The released FASTA predictor thresholds at 0.1 and serializes scores to three decimals. Our full-precision/full-head evaluator would need a separately qualified output adapter. Its native reported scores must not be compared directly to our different metric/frame. |

The [invented algebra witness](pu_objective_witness.json) makes the ranking
issue concrete. With one positive logit 1 and one unlabelled logit −1, the released
unlabelled term is 0.626523 while Equation 11 gives 0.126928. This is a source-level
formula check, not native PyTorch execution or biological evidence. Author
intent and a preferred remedy have not been established.

Both public issues, all tags/releases and the loss-file history were checked.
There are no tags or releases; neither issue resolves these discrepancies.
They concern data access and DIAMOND preparation. The loss file has two January
2024 commits. No author was contacted and no issue was posted.

## One licensed published alternative

[Kiryo et al. nnPU](https://papers.nips.cc/paper/6765-positive-unlabeled-learning-with-non-negative-risk-estimator.pdf)
provides a classifier-independent non-negative PU risk estimator. The
[original author implementation](https://github.com/kiryor/nnPUlearning/tree/3d9769e60dd275e8e4dcf91e1853f3b76c69f39f)
has an inspected MIT permission notice. GitHub labels the file NOASSERTION;
the actual permission text, rather than that label alone, establishes the
recorded reuse terms.

This is a candidate for a future adaptation using existing features, with
these remaining gates:

1. The released implementation is binary Chainer code, with logits (N,1),
   labels (N) and a supplied scalar class prior. It is not a Torch/multilabel
   loss that can be inserted unchanged into our current trainer.
2. Its corrective negative-risk branch deliberately returns one forward loss
   while backpropagating another objective. A simple ReLU replacement would not
   reproduce that algorithm. Value **and gradient** parity must cover both
   branches and their boundary before fitting.
3. The paper assumes a known or estimated positive class prior and samples
   representing its declared positive and unlabelled distributions. Our
   observed curation frequency is not a verified biological prevalence. A
   training-only prior/sampling rule must be justified and frozen; future
   reference labels cannot be used to choose it.
4. Applying it per GO class or to protein/function pairs is a disclosed
   adaptation requiring explicit handling of sparse/no-positive minibatches,
   normalization and ontology dependence. No such adaptation is implemented
   or admitted by this review.

## Decision for the next comparison

Proceed through the separately qualified cross-fitting opportunity first.
Do not copy unlicensed PU-GO source, substitute incompatible embeddings, call
its temporal script a trainer, or choose a new prior from exposed test scores.
A future licensed nnPU adaptation remains possible after estimator parity and
class-prior/sampling qualification. Any further use of the April–November
reference remains development evidence, with no independent-confirmation claim.

The [machine receipt](pu_qualification.json) records exact source hashes,
permission observations, interfaces, actions and remaining gates. Source
captures, the primary article XML and data metadata are retained privately
under the existing ignored research workspace; no benchmark cases are included.
