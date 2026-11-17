# ProtNote on the existing lower-knowledge reference

**Complete; no adoption.** The source-qualified ProtNote profile did not
outperform DeepGO or the strong pre-existing annotation baseline on the
predeclared MFO comparison. Its higher MFO point estimates than LocalPlus were
inconclusive under all four paired intervals. Ordinary and IA micro-Fmax point
estimates were also lower than all three comparators in every BPO/CCO cell.
The graph, accepted annotations and existing predictors stay unchanged.

All 547 original targets were scorable against 43,248 independently fixed GO
classes. Admission verified all 23,656,656 protein/class rows for exact
identity/order, completeness and finite probabilities. This separates a
successful native implementation from an unsuccessful prediction improvement;
no target was removed to improve the reported scores.

## Published method and why it fits this question

[ProtNote: a multimodal method for protein–function annotation](https://doi.org/10.1093/bioinformatics/btaf170)
(*Bioinformatics*, 2025) conditions protein-function scores on function text as
well as sequence. Its [author implementation](https://github.com/microsoft/protnote/tree/b29e17fa308d8c0fc1d9692f705b37dff3a8cf5e)
provides a full-sequence ProteInfer encoder, a frozen E5 text encoder and a
classifier for protein/description pairs. This is an established released model
that can score a separately supplied function vocabulary; no new network,
training procedure or biological scoring formula is introduced here.

This tests a different practical profile from the retained DeepGO-SE sequence
profile and Pharos-derived strict-source LocalPlus graph predictor. It does not
establish that the original graph has nothing left to discover, nor does it
isolate the effect of full sequences, text conditioning or training data. Those
components differ together. The graph, accepted annotations and app defaults
are unchanged by this assessment.

## Verified interface gap and bounded integration

The released dataset code derives its amino-acid and class vocabularies from
dataset contents, including labels in FASTA headers. That can define a native
dataset task, but an unlabeled target file does not supply the independent
function universe needed here. We therefore retain the author's unchanged
model classes and forward calculation behind a small explicit-input adapter.
This is an inference-interface adaptation, not a literal reproduction of the
paper's dataset-defined test setting or a change to its learned model.

The prediction inputs are deliberately separate:

- The same dated canonical human Swiss-Prot sequences and 547 literal target
  accessions used by the existing NK/LK comparison. Entire sequences are passed
  through the native 20-channel amino-acid encoding. No 1,022-residue truncation,
  inferred `U`/`X` substitution, modern sequence fallback or target selection is
  applied.
- Every nonobsolete GO2023 term with a native name and definition in the one
  pinned ontology, ordered by canonical GO ID. This yields 43,248 classes and
  86,496 description rows. The axis uses ontology content rather than target
  FASTA labels, future reference annotations or benchmark terms of interest.
- The author's definition cleanup, obsolete-string cleanup, E5 instruction,
  mean pooling and `account_for_sos=True`. The checkpoint's frozen text encoder
  generates a new ontology-specific cache. Native inference averages name and
  definition probabilities; their logits are not averaged instead. Text retains
  the native 510-token limit.

The source code, model and E5 artifacts are MIT licensed. The selected official
[Zenodo release](https://zenodo.org/records/13897920) member is
`data/models/ProtNote/seed_replicates_v9_42_sum_last_epoch.pt`, checkpoint SHA256
`d855e6c40b986294f3f4c852020c58b362ec2d38d806f60ef78e2fef89ab0887`.
All 523 native state tensors matched strict key/shape/dtype loading, including
both encoders. No missing parameters were silently initialized or ignored.
The E5 config/tokenizer revision is pinned to
`274baa43b0e13e37fafa6428dbc7938e62e5c439`; this fixes our preprocessing artifacts
without proving reconstruction of the original training-time tokenizer revision.

## Source and numerical qualification

All 31 captured native source files and all five local E5 config/tokenizer
files are hash-checked. The isolated environment follows the compatible
paper-era core rather than mixing contradictory dependency declarations from
`environment.yml` and `setup.py`. It does not alter the app or existing DeepGO
runtime.

| Component | Qualified producer version |
|---|---|
| Python | 3.10.12 |
| PyTorch / torchvision | 2.0.1 / 0.15.2 |
| Transformers / tokenizers | 4.32.1 / 0.13.3 |
| NumPy / pandas | 1.24.4 / 1.5.2 |
| obonet / Biopython | 1.0.0 / 1.84 |

The required synthetic test uses a 1,200-residue sequence spanning all 20
canonical amino acids and the first 1,025 eligible ontology classes. Native
Dataset/collator features and adapter features match exactly. Under the same
cache, precision and fixed `[1024, 1]` class chunks, native and adapter logits
and probabilities are bitwise equal. Removing, permuting or replacing header
labels does not change adapter predictions. Reordered axes/cache metadata and
modified serialized cache bytes are rejected before scoring. Cached native
sequence embeddings are enabled only after their same-precision bitwise parity
passes across both chunks.

The fixed production schedule is sequence batch1, text batch8 and 1,024 GO
classes per scoring chunk, using native evaluation autocast. This is a
pre-target scheduling choice, not a parameter or accuracy sweep. Forecast
production took 345.21 seconds on the existing Brev GPU after cache generation;
that timing excludes intake, runtime preparation, parity, text caching and
scientific evaluation. It is not an end-to-end performance comparison.

The maintained files are bitwise copies of the source-qualified execution
artifacts:

- [Native adapter](../../tools/protnote_reference/native_inference_adapter.py).
- [Qualification/parity/cache/pilot driver](../../tools/protnote_reference/pilot_driver.py).
- [Native evaluation wrapper](../../tools/protnote_reference/evaluate_driver.py).

## Frozen comparison and original populations

The scientific protocol was frozen before any target forecast, after synthetic
parity and label-cache qualification. Its FILE SHA256 is
`f8a9e6f011a19d4d54d20c0439eb257d72392e52698dd6077d20f265d89b8e04`.
The completed-producer evaluation freeze is
`cd4a070510ae4a12a6a5330a951fe81f04d90d43995d4e9a737572e3b718d5b6`.
Earlier source snapshots, failed investigations and all previously exposed
reference outcomes remain preserved.

| Existing setting | Target population | BPO eligible N | MFO eligible N | CCO eligible N |
|---|---:|---:|---:|---:|
| No knowledge (NK) | 133 | 44 | 39 | 118 |
| Limited knowledge (LK) | 414 | 227 | 60 | 197 |

The native aspect populations overlap; they are not separate experiments.
Both settings retain the original `exclude=None` scoring branch, complete
ground truth, eligible populations, TOI reference-pair extent and original
paired case masks. Missing/noncanonical sequences, native OOM or nonfinite
outputs would have required explicit abstention while retaining these
denominators; none occurred in this run.

The separate evaluator uses the same pinned native parser, `fill` propagation,
`is_a`/`part_of` ontology, roots policy, IA, TOI and `.001` threshold grid as the
earlier comparison. Its numeric runtime remains Python3.10.12,
NumPy1.26.4, SciPy1.13.1 and pandas2.2.3. No evaluator or reference labels enter
the numerical prediction path. Scores are exported in full with roundtripping
`.17g` serialization, without a display cutoff, calibration or producer-side
ontology propagation.

The report retains all six new setting/aspect point cells alongside all42
earlier outcomes, including unsuccessful controls and missing native states.
Ordinary/IA micro and macro Fmax, thresholds, Smin and fixed0.5 operating points
remain separate. MFO is the predeclared focus, with twelve paired contrasts:
ProtNote against DeepGO, strict-source LocalPlus and the official
nonexperimental annotation baseline, ordinary and IA readouts in both settings.
The unchanged NumPy paired-protein implementation uses 2,000 shared resamples,
seed20261113 and percentile intervals. It does not introduce a new formula,
bootstrap search or multiplicity-adjusted confirmation.

Both new native MFO point/count gates passed; the largest absolute curve
difference was `2.22e-16`, within the existing `1e-12` agreement tolerance.

## Results and interpretation

The complete [published assessment](protnote_comparison_20261114/report.html)
retains all48 point outcomes and all12 paired intervals. The
[machine-readable aggregates](protnote_comparison_20261114/report.json) preserve
native thresholds, macro and IA results, Smin, fixed0.5 trade-offs, count gates,
source hashes and every earlier outcome. Values below are rounded for display;
the machine-readable values are unchanged.

Ordinary micro-Fmax:

| Setting | Aspect | Original N | ProtNote | DeepGO | LocalPlus | Existing annotations |
|---|---|---:|---:|---:|---:|---:|
| NK | BPO | 44 | 0.249635 | 0.362058 | 0.320179 | 0.359951 |
| NK | MFO | 39 | 0.487644 | 0.558882 | 0.400000 | 0.521600 |
| NK | CCO | 118 | 0.326939 | 0.694507 | 0.613718 | 0.547751 |
| LK | BPO | 227 | 0.271174 | 0.338556 | 0.329733 | 0.329572 |
| LK | MFO | 60 | 0.531300 | 0.599418 | 0.422316 | 0.597970 |
| LK | CCO | 197 | 0.353399 | 0.695279 | 0.602243 | 0.588556 |

IA-weighted micro-Fmax, with the original IA populations retained:

| Setting | Aspect | Original IA N | ProtNote | DeepGO | LocalPlus | Existing annotations |
|---|---|---:|---:|---:|---:|---:|
| NK | BPO | 44 | 0.223879 | 0.300513 | 0.269298 | 0.334045 |
| NK | MFO | 39 | 0.385691 | 0.470539 | 0.309022 | 0.444222 |
| NK | CCO | 118 | 0.237288 | 0.479243 | 0.361388 | 0.432148 |
| LK | BPO | 227 | 0.244289 | 0.307044 | 0.325878 | 0.332168 |
| LK | MFO | 60 | 0.379866 | 0.460653 | 0.308903 | 0.483136 |
| LK | CCO | 197 | 0.218630 | 0.471727 | 0.368359 | 0.418087 |

All predeclared MFO differences are **ProtNote minus comparator**. Observed
point delta subtracts the two full-frame native Fmax values; bootstrap mean
delta averages the 2,000 resampled differences. Those are different summaries
and are kept separate. Each interval is the saved paired percentile interval,
with no recomputation or selection of favorable contrasts.

| Setting | Readout | Comparator | Observed point delta | Bootstrap mean delta | Paired95% interval |
|---|---|---|---:|---:|---|
| NK | Ordinary | DeepGO | -0.071238 | -0.078142 | [-0.158723, +0.010390] |
| NK | IA | DeepGO | -0.084848 | -0.090138 | [-0.167894, -0.006757] |
| NK | Ordinary | LocalPlus | +0.087644 | +0.084220 | [-0.013136, +0.181575] |
| NK | IA | LocalPlus | +0.076668 | +0.074132 | [-0.025775, +0.180180] |
| NK | Ordinary | Existing annotations | -0.033956 | -0.030341 | [-0.062260, -0.001214] |
| NK | IA | Existing annotations | -0.058531 | -0.052730 | [-0.105469, -0.000953] |
| LK | Ordinary | DeepGO | -0.068118 | -0.070568 | [-0.125873, -0.008857] |
| LK | IA | DeepGO | -0.080786 | -0.081534 | [-0.141813, -0.019289] |
| LK | Ordinary | LocalPlus | +0.108984 | +0.096020 | [-0.001972, +0.188146] |
| LK | IA | LocalPlus | +0.070963 | +0.065641 | [-0.010673, +0.138265] |
| LK | Ordinary | Existing annotations | -0.066670 | -0.063943 | [-0.095546, -0.034470] |
| LK | IA | Existing annotations | -0.103270 | -0.095866 | [-0.142696, -0.052888] |

All four MFO intervals against existing annotations favor that control. Three
of four against DeepGO favor DeepGO; NK ordinary includes zero. All four
against LocalPlus include zero despite higher ProtNote point estimates. These
conditional development results provide no basis for promoting this profile,
claiming a scientific-accuracy gain or changing graph facts. No post-hoc seed,
threshold, model, fusion or sensitivity sweep was added.

The present measurement does not identify the causal reason for lower
performance. Native parity, source/body checks and full forecast admission
address the verified integration concerns; they do not prove that training,
representation, annotation granularity or domain differences are irrelevant.
Nor does an underperforming published model show that the biological question
has no undiscovered answers. It demonstrates that this particular complete
profile did not improve the frozen comparison.

This remains retrospective development on already exposed CAFA5 outcomes.
ProtNote's 2019 ProteInfer split and the E5 release date do not establish
training-unseen or homology-disjoint targets, and dated GO text alone does not
prove prospective independence. NK/LK categories also do not imply Pharos
Tdark. Fmax is a benchmark threshold maximum, not percent scientific accuracy;
reference-unmatched predictions are unresolved rather than established
biological negatives. These scores do not establish whole-graph biological
accuracy, a newly verified function, causal Pharos improvement or an automatic
biological pruning rule.

The [aggregate-only publisher](../../tools/deepgo_reference/publish_protnote.py)
accepted the complete real report with the original native populations,
reference extents, case masks and source bindings intact. Its public HTML/JSON
omit private identities, class arrays, score bodies and operator paths.

| Artifact | FILE SHA256 |
|---|---|
| Completed native source report | `9c7012771215b0f23c586905fedc024e8d55851d58623b91e60fc890811a85b7` |
| Public aggregate JSON | `e0e0c5ed2bd9b6753f02efd5ffe054d0004df19a12530194b4485bd7be151dbb` |

The [publication manifest](protnote_comparison_20261114/publication_manifest.json)
binds both public files. Protocol and evaluation-freeze pins remain recorded
above and in the aggregate receipt. No app/default change or automatic
promotion follows this assessment.
