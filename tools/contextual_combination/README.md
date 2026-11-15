# Source-qualified contextual score stacking

This optional research adapter reuses the published ProtBoost graph stacker.
It changes no app dependency, graph, forecast or acceptance decision. No new
scientific result follows from passing its runtime fixtures.

The verified gap after the global-alpha comparison is narrower than building a
new protein predictor: two saved predictors contain complementary information,
but a single weight per GO aspect does not use a protein's existing annotation
context or neighboring GO-function predictions. A learned graph stacker is an
established way to combine those inputs. It remains an empirical hypothesis
that this richer integration improves this project's task over LocalPlus.

## Reused implementation

- [ProtBoost primary paper](https://arxiv.org/abs/2412.04529), December 2024.
- [Author repository](https://github.com/btbpanda/CAFA5-protein-function-prediction-2nd-place/tree/52dce6c471337f2820550f779a6a1bb201353b2a),
  commit `52dce6c471337f2820550f779a6a1bb201353b2a`, Apache-2.0.
- The unchanged `GCNLayer` and `GCNStacker` bodies run from the separately
  captured author `protnn/stacker.py`. Every source/license file is SHA-256
  checked before execution.
- The unchanged `StackDataset`, `Propagator`, CPU `propagate`, native edge
  builder and `get_depths` bodies are selected from the same pinned sources.
  The original metric module initializes CuPy kernels at import, although its
  depth function uses Pandas only. Source-symbol isolation avoids importing
  unused kernels. It does not rewrite the ontology traversal or feature math.
- The original CUDA-only batch-placement code is adapted to an explicit
  device. Its flags, clipping, logit conversion, axis swaps and edge tensors
  must reproduce the original native loader on an invented fixture.

The full upstream training driver is **not** run. It hard-codes five component
models and validates checkpoints against supplied competition label files.
Its paths and label roles do not identify our current final holdout. Reusing
that driver unchanged would not preserve this project's validation boundary.
It also reads out-of-fold base predictions. This project adapts the method to
saved historical parents rather than retraining those parents in folds. Known
T0 annotations are legal context and remain excluded from PK evaluation;
nevertheless, possible in-sample base-label exposure can affect learned
calibration. No unseen-base-protein or full ProtBoost reproduction claim follows.
The original final submission also averages model variants and supplied
competition annotation files. Those stages are excluded. Its pure ontology
postprocessing is reused separately as described below. Its submission script
is not a source of independent final labels for this project.

## Feature and label contract

For each parent, the original dataset builds four channels: a missing-head
indicator, a raw score/prior, and two prior/conditional-propagation views.
LocalPlus and DeepGO-SE are **marginal**, not conditional, predictors. They
must be marked `cond=False`. The author propagator leaves all three observed
score channels unchanged for available heads. Missing-head priors receive its
native conditional transformations. Marking a marginal model conditional just
to produce more diverse features would change the method's meaning.

Head availability is a property of the actual producer's output-head list.
It is not inferred from whether one protein has a positive score. An observed
zero score and an unavailable head must remain distinct. Inputs are reindexed
to an explicit ordered model GO axis before this module is called. Native
float32 feature conversion and logit clipping are retained; original forecast
controls remain separately preserved in their original precision.

One additional channel contains qualified, historical, nonexperimental GOA
annotation membership. This is source context, not independent experimental
truth or another count of corroborating studies. The author pipeline uses
`no_kaggle`: evidence codes outside its experimental/CAFA set
`IDA IMP TAS IPI IEP IGI IC EXP HTP HDA HMP HGI HEP`, followed by closure.
This CAFA group contains curator inference (`IC`) and traceable author
statements (`TAS`) alongside eleven experimental codes; it is not uniformly
direct experimental evidence.
Its legacy parser ignores GAF qualifiers. This project instead prepares a
strict, source-frozen native nonexperimental baseline, including NOT exclusion.
That source-admission difference is an explicit adaptation. A released
all-evidence control must not silently be called a nonexperimental feature.

The author `p_goa` argument does **not** implement feature dropout in the
qualified revision: its masking conditional is commented out. Passing 0.5 is
not evidence that missing GOA context has been simulated.

Training positives represent the complete known repertoire for fitting
proteins: include appropriate known-at-T0 experimental positives together with
their allowed development additions. Do not feed a PK-only delta as a binary
full-repertoire target and thereby teach known positive functions as negatives.
Native training uses mean `BCEWithLogitsLoss` across all nodes. The author
driver fits only proteins positive for that namespace's literal GO root. The
I/O view applies the same row selection after validating full targets; priors
still use all 4,040 allowed fitting proteins. The root is found by its GO ID,
with no assumption it occupies column zero. Selected and excluded protein IDs
are recorded. Its treatment
of unlabeled entries as 0 is a benchmark learning convention, not a verified
negative biological label. Native evaluation can still exclude known terms.

The native prior construction starts from upward-closed training labels. It
sets a nonroot cell to NaN where every parent label is 0. Conditional prior is
the non-NaN mean, missing fraction is the NaN fraction, and marginal prior is
`conditional_prior × (1−missing_fraction)`. Priors require a declared fitting
or historical source frame. Final-reference or validation outcomes cannot
silently enter them.

## Model axis and matched control

The preferred declared architecture keeps a **fixed historical model ontology
and output axis** at training and every inference. This preserves the native
learned per-term embedding, size 8. Current T0 annotations are projected onto
that model axis with explicit identifier rules and unmapped-content counts;
exported old GO identifiers then enter the separately pinned current-ontology
evaluator. The contemporary annotation control may retain its complete current
ontology axis. No learned embedding is silently reordered or extended to new
nodes.

The unchanged class supports `n_layers=0` as a same-input control without
message passing. It retains the same features, per-term embedding and native
input ReLU, so call it a zero-layer MLP control rather than a linear model.
The eight-layer native graph architecture also adds depth, residual blocks,
dropout and parameter capacity across its three direction streams. A difference
between these models therefore does not causally isolate useful GO topology.

The pinned native evaluator exposes adjacency as sets, while the published
stacker expects integer lists. `sequence_edge_graph` copies those containers
without changing a term identity, index, traversal order or directed edge.
List order is retained and set edges are sorted. Invented-data parity tests
cover the feature pipeline and postprocessor; the original graph is unchanged.

Published author configuration: hidden size 16, eight graph layers, embedding
size 8, 20 epochs, batch size 32, Adam learning rate 0.001, gradient-value clipping
0.1 and weight decay 0. It stores ten best checkpoints and uniformly averages
the best three. Any selection metric, physical batch size, loss weighting or
checkpoint strategy different from the author pipeline must be declared.
All selection belongs to allowed development/validation data, never the new
final reference. Full failed runs and controls remain preserved.

## Runtime and API

```python
from tools.contextual_combination.native_stacker import (
    load_author, make_dataset, make_model, collate_rows, validate_model_axis,
)

author = load_author(captured_author_root, jit_backend='numba')
dataset = make_dataset(
    author, proteins=protein_ids, terms=fixed_model_go_ids, graph=native_graph,
    predictions=[(localplus_head_scores, localplus_head_indices),
                 (deepgo_head_scores, deepgo_head_indices)],
    prior_raw=historical_marginal_priors,
    prior_cond=historical_conditional_priors,
    goa_indices=qualified_nonexperimental_goa_indices,
    targets=full_allowed_training_positives,
)
model = make_model(author, n_terms=len(fixed_model_go_ids),
                   terms=fixed_model_go_ids, n_layers=8, embed_size=8).cuda()
validate_model_axis(model, fixed_model_go_ids)
batch = collate_rows(author, dataset, row_indices, device='cuda')
logits = model(batch)
```

The original embedded model retains its CUDA index placement; supported
`embed_size=0` can run directly on CPU, but is not automatically another
experimental arm. CPU fixtures intercept only native `.cuda()` placement
inside their scoped test context. They do not modify source bodies or GPU
services.

The actual project inference runtime, Python 3.10.12/Torch 2.0.1+cu117/
NumPy 1.26.1, was used for qualification. Original Numba 0.57.1 does not support
that NumPy release. Official Numba 0.59.1 supports Python 3.9–3.12, NumPy 1.22–1.26
and llvmlite 0.42.x. Publisher-verified wheels were installed into a separate
research overlay; the existing runtime and services stay unchanged.

Invented-data tests cover exact source bytes,
full native feature scope, original-loader parity, fixed identity axes,
no-message control, finite native forward/backward and explicit JIT behavior.
The native JIT/no-JIT feature difference on the fixture is 0. A separate actual
CUDA fixture passes with 18,248,192 bytes peak tensor allocation, a 1 GiB process
cap and CPU/CUDA forward difference `1.49e-7`. This qualifies execution only.
The full 27,942-term BPO, batch-32, eight-layer forward/backward/Adam fixture
needs 27.14 GB peak tensor allocation. It exceeds the memory available beside
the running language model. The fixed training run therefore uses a bounded,
isolated phase that pauses and exactly restores that existing service; it does
not lower the published batch size, depth or numerical precision.

## Other published avenues

[GOLabeler](https://doi.org/10.1093/bioinformatics/bty130) establishes learning
to rank multiple component scores; it does not provide trained weights for
this project's different components. A ranker would be an alternative method,
not a reason to tune on the now-consumed LAFA outcome.

[PU-GO](https://doi.org/10.1093/bioinformatics/btae237) provides a published
positive-unlabeled ranking formulation with ontology-derived priors. It
addresses label incompleteness more directly than declaring absent labels
negative. It is not a post-hoc accuracy correction and does not make a biased
or reused validation set independent. Its exact released objective, priors and
classifier would need separate qualification before becoming another arm.

The author CAFA6 follow-up describes richer evidence-relation features and
cross-ontology labels, but warns that literature-derived features risk temporal
leakage. Current publications, current InterPro or future GOA cannot be inserted
into historical training inputs merely because they are available today.

## Isolated training driver

`training.py` executes the original source-pinned `train`, `SWA` and
`make_raw_prediction` bodies. Its memmap dataset only supplies cached native
features and full binary targets; the unchanged native loader still performs
logits, axes and graph-edge preparation. A physical known-positive mask must
confirm that the full target array retains every known T0 positive.

Model training uses the qualified Torch 2.0.1/NumPy 1.26.1 runtime. Every epoch's
validation predictions are scored in a **separate** Python 3.10.12/
NumPy 1.26.4/SciPy 1.13.1/Pandas 2.2.3 evaluator process. Its raw reference pins
are hard-bound to the already-consumed LAFA September 2025–March 2026 release;
a fresh reference role or content hash is rejected before label parsing.
The fixed validation metric is ordinary native micro-Fmax on a 0.01 grid,
after the fixed published soft postprocessing. This objective and selecting
checkpoints on deployed soft scores are explicit adaptations: the author
checkpoint loop used its supplied competition objective on raw model scores.
No fresh final reference enters checkpoint selection.

All 20 epoch parameter snapshots, predictions and validation curves are kept
in addition to the native SWA top-ten directory. The final checkpoint is the
unchanged source's uniform average of its best three **parameter states**.
An independent parameter check verifies the operation; it is not an average
of sigmoid predictions. Both native eight-layer graph and zero-layer MLP
models are trained on the same source data. Their best-three SWA models are
compared only on consumed validation, with the zero-layer model winning an
exact tie. Parent orchestration must freeze this choice before final scoring.

The I/O adapter uses zero DataLoader workers to avoid forking initialized CUDA
contexts; this is an execution adaptation, not a different classifier. The
published batch size 32 and 20 epochs remain fixed. Full-ontology/batch memory
must be checked separately: the tiny CUDA fixture is not a capacity estimate.

## Fixed published postprocessing and controls

`postprocessing.py` selects the unchanged pure-GO traversal bodies from the
pinned author `step.py` and executes their elementwise MAX/MIN kernels with a
qualified NumPy backend. Both directions begin with independent copies of the
same raw float32 probabilities. The executed notebook recipe sets 0.7 times
the closed scores plus 0.3 times raw scores in each direction, then averages
the two results equally. This is the notebook's explicit rate, rather than
the CLI's different default. It **does not guarantee** parent probability is
at least child probability. Calling it strict ontology correction is incorrect.

Both contextual models, both matched soft parent controls and both mixtures
receive that identical recipe on the fixed historical ontology before current
native identifier intake and `fill`. Raw original-precision model-axis LocalPlus
and DeepGO-SE remain additional matched controls. They have already undergone
historical canonical-ID intake and do not contain every original source head.
Separate complete source-head LocalPlus and DeepGO-SE controls protect the
primary parent comparison. A label-free sample of 16 old
LocalPlus rows per aspect has no hierarchy violations; the soft result differs
by less than `9e-8` from its original float64 scores because of rounding. This
sample does not establish exact identity for the full array. No clipping,
top-500 truncation, test-time augmentation or competition annotation merge is
performed. Native raw and deployed soft contextual forecasts are both saved.

`controls.py` reuses the existing convex mixing and eleven-weight alpha selector
on the exact same consumed validation proteins. It applies the shared soft
recipe before the ordinary micro-Fmax objective and keeps the smallest alpha
on a tie. Its final forecasting phase accepts no evaluation/reference settings.
It outputs two original-precision model-axis parents, two soft parents, equal
mixture and the preselected development-alpha mixture, with source and numeric
pins. The final assessment separately requires complete source-head parents.

The ProtBoost implementation remains an external Apache-2.0 source capture.
Optional research wrappers integrating the GPL-3.0-only native CAFA evaluator
retain their own GPL-3.0-only headers. These tools are isolated from the app
runtime; this does not relabel the evaluator or the entire repository as MIT.

## Source-derived context feature variant

The same native model and loader already accept multiple GOA inputs.
`context_io.py` supplies separately pinned bool `(protein, channel, GO)`
sidecars. Only fetched rows become float32. The original eight parent channels
and their logit transform remain bitwise unchanged; forty GOA channels replace
the default one rather than being appended to it. Both ordered GO identities
and ordered context names are frozen in the model and forecast metadata.
Same-width channel reordering is rejected.

The separate BPO feature profile follows the author's
[CAFA6 source update](https://github.com/btbpanda/CAFA6-updates/tree/0ee85d2f07f724be1721ea39211f1b364535f976).
It distinguishes raw/propagated annotation membership, evidence-code groups,
annotation-relation groups and thresholded ontology-branch support. Source
fixtures found two file-handling defects: evidence/relation `other` filenames
collide, and purported raw category inputs read propagated paths. The declared
variant uses forty distinct names and true raw/propagated paths, retaining the
original grouping and exact branch-count kernel. This is a disclosed
source-derived adaptation, **not** a literal reproduction of the released
thirty-eight-file pipeline. Branch counts do not count independent studies:
one annotation in a diamond can yield two root branches.

`training_context.py` permits one additional BPO eight-layer model, retaining
the fixed epoch/batch/optimizer/seed/SWA/postprocessing recipe and existing
fitting labels, known-positive masks and prior universe. Model choice uses only
the consumed validation frame. The original one-context models and complete
parent controls remain separate. Passing its invented-data native training,
prediction and channel-identity tests establishes execution, not a gain in
scientific accuracy.

## Matching training knowledge and simple controls

The historical LocalPlus parent uses the original global known-at-2023 seeds.
The context models additionally learn from allowed 2025 curator labels on the
4,040 fitting proteins. A gain over the retained parent alone therefore cannot
isolate the value of learned integration from the value of fresher labels.

The fixed freshness control keeps the identical strict graph, native algorithm
and original seeds, then unions exactly that fitting repertoire. It preserves
all 988,439 original pairs and adds 44,680 upward-closed annotation cells on
fitting proteins only, retaining 322 newly eligible heads. Validation and final
protein annotations are not added. These cells include related ontology terms;
they are not counts of new experiments. The raw updated predictor and its
matched fixed-soft version remain separate from the original parent.

The separate `current_annotation.py` control answers a practical question:
how well does the same graph and LocalPlus perform with the complete available
current curated repertoire? It runs the unchanged democafa
`filter_gaf → retrieve_terms(Experimental,IC,TAS) → propagate_and_ia` pipeline
on the April 10, 2026 GAF, dated reviewed-human SwissProt identities and March
25 ontology. Exact graph-ID intersection supplies 903,293 closed annotation
cells on 17,104 graph proteins. Current seeds replace historical seeds;
withdrawn historical annotations are not unioned back. All eligible current
heads and all 3,300 final queries remain. This control makes **no earlier
validation predictions**: April knowledge would look ahead relative to that
September 2025–March 2026 task. It cannot influence model selection.

The second simple control broadcasts the existing full-fitting marginal prior
vectors unchanged. This is a Naive-style label-prevalence control, with no
parameter selection. It uses the same 4,040-protein universe as the stacker's
prior construction, before aspect/root filtering. It is not a reproduction of
the official multi-species Naive baseline.

The fixed primary PK/BPO comparison reports paired updated-versus-original
LocalPlus intervals as well as the contextual-model contrasts, in both native
and fixed-T0 reference views. More input positives can increase raw scores
without improving prediction quality; monotonicity is an integration check.

This separation follows the [CAFA4 assessment preprint, version 2, June 12,
2026](https://pmc.ncbi.nlm.nih.gov/articles/PMC13174626/), section 2.4: it uses
common ontology terms and older baseline versions to distinguish larger
training datasets from methodological progress. Its discussion also cautions
that curation patterns and text-derived information can affect temporal
benchmarks. The report has not yet been peer reviewed.

## Temporal reference and reproduction

The later human reference uses the unchanged LAFA/democafa construction helpers
on April 10 and November 4, 2026 source snapshots. Native epoch-specific and
fixed-T0-ontology views share the same primary term intersection and complete
3,300-protein prediction union. The available later ontology has July 26
content, despite an August 5 build URL; that projection limit remains explicit.
Model selection uses the already-consumed September 2025–March 2026 reference.

The [optional reference recipe](reference_recipe/README.md) preserves the exact
executed wrapper snapshots, public-source hashes, external-helper versions and
native CLI calls. It describes the separate runtime/path requirements and
accepts matching archived files. Mutable current-release URLs must match the
recorded source hashes; a later download must not silently redefine this study.
No upstream helper source, benchmark cases or model weights are bundled.

Final scores open only after a complete forecast/model-choice/source seal. The
case-level reference-positive score ledgers preserve every eligible pair, with
no threshold-based selection. They support a separate source-provenance audit
and stay distinct from aggregate-only presentation artifacts.
