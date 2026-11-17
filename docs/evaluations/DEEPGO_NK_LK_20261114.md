# DeepGO on the existing lower-knowledge reference

**Complete; no automatic adoption.** This is a
development extension on the previously evaluated CAFA5 no-knowledge (NK) and
limited-knowledge (LK) populations. The 133 NK and 414 LK identities remain
unchanged. These categories describe the benchmark's curated knowledge state;
they do not prove that a protein was absent from model pretraining or supervised
training.

The [qualified DeepGO source/method record](DEEPGO_SE_20261114.md) remains in
force: archived sequence/ontology predictor, six fixed checkpoints per aspect,
corrected CCO artifact, dated Swiss-Prot 2023_03 sequences and native
first-1,022-residue processing. Of the 547 targets, 210 literal forecasts reuse
the sealed earlier calculation and 337 use new native inference. All three new
CLI presentations match the qualified raw-score adapter. No score calibration,
new model fit, GAT reconstruction or sequence fallback is introduced.

The forecast freeze is FILE SHA-256
`694908cd8c0ca66279c6a470ed7a0dc651520fb530e1e075878b4c41eb399738`.
The complete forecast manifest is
`2c3837bc3cd49eb506dcda0190862f6089f30b1fa529360c3f284ba0232aa518`.
It retains all 547 targets and 16,976,692 raw target/head values. Native head
counts, namespaces and ordered hashes exactly match the sealed parent profile.
The original language-model service was verified healthy with its exact
configuration restored before evaluation began; no GPU/model call is made by
the evaluator.

This comparison reuses the established no-exclusion CAFA pipeline:
**`exclude=None`, `fill`, `norm=cafa`, the same ontology/IA/terms of interest,
no-orphans policy and 0.001 threshold grid.** The PK known-mask count adapter is
not used. The project's native no-exclusion count worker already supports an
explicit namespace, so molecular-function counts reuse that capability rather
than implement a new scoring formula. Native ordinary and IA micro-F curves
must reproduce the saved unchanged author point curves within the existing
10⁻¹² bound. All raw numeric-column differences remain separate diagnostics.

The designated focus is MFO, fixed before these new scores. Both settings and
all three aspects remain visible: six new outcomes plus every earlier control
and state, for 42 total rows. The previously established eligible populations
are:

| Setting | BPO ordinary / IA | MFO ordinary / IA | CCO ordinary / IA |
| --- | ---: | ---: | ---: |
| No knowledge |44 / 44|39 / 39|118 / 118|
| Limited knowledge |227 / 227|60 / 60|197 / 197|

Fresh MFO counts are generated for DeepGO, retained strict-source LocalPlus and
the official nonexperimental-annotation control in both settings. The existing
paired bootstrap uses 2,000 shared protein draws with seed 20261113 and retains
all eight ordinary/IA contrasts against both controls. No favorable aspect,
control or threshold can be selected instead. Micro/macro and IA Fmax, Smin,
fixed-0.5 precision/recall/F1, source pins and missing native outcomes remain
part of the result.

The evaluation source freeze is
`0e306ebe4e3173437ea9438770de52e07bcae8bf17b1da8666084506752417be`.
Its earlier unexecuted preparation is preserved: inspection of the actual
producer manifest corrected a flat-head-metadata assumption before any point
calculation. The corrected gate requires the exact sealed parent head metadata;
no scientific recipe or producer was changed.

This is exposed-reference development work, not fresh-reference confirmation
or independent-study replication. Small MFO populations, incomplete curator
labels, model/resource vintage differences, unreconstructed training/homology
overlap and shared source/graph dependence remain. Fmax optimizes a benchmark
threshold; it is not scientific accuracy or a calibrated acceptance
probability. The original failed PK BPO adoption rule and existing app default
remain unchanged; no new DeepGO consumer or accepted graph fact follows.

## Completed outcomes

The [static report](deepgo_nonpk_20261114/report.html) and
[complete sanitized aggregate](deepgo_nonpk_20261114/report.json) retain all
42 point rows, eight MFO intervals, native count checks and source/runtime
pins. The original 36 rows remain exactly unchanged.

DeepGO has higher MFO ordinary and IA micro-Fmax than the strict LocalPlus
profile in both existing settings, with all four paired intervals positive.
However, **all four intervals against the official nonexperimental-annotation
control cross zero**. This is a bounded improvement against one network-based
profile, not a demonstrated gain beyond the strongest information-resource
control or independent biological validation.

| Setting / profile | Ordinary micro-Fmax | IA micro | Macro | IA macro | Smin | IA Smin |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| NK / DeepGO |0.558882|0.470539|0.475259|0.455906|4.347269|8.314709|
| NK / Strict LocalPlus |0.400000|0.309022|0.307976|0.280905|5.585390|10.110704|
| NK / Nonexperimental |0.521600|0.444222|0.490167|0.491387|5.450211|9.620394|
| LK / DeepGO |0.599418|0.460653|0.538285|0.490618|5.207073|10.579486|
| LK / Strict LocalPlus |0.422316|0.308903|0.409520|0.362702|7.303747|12.921726|
| LK / Nonexperimental |0.597970|0.483136|0.578292|0.541006|6.167500|11.707755|

These are saved point estimates; bootstrap mean differences below are separate
summaries. Smaller Smin is favorable. MFO Smin is lower for DeepGO than both
controls in both settings, whereas its macro/IA-macro Fmax remains below the
nonexperimental control. These metric trade-offs remain visible rather than
being replaced by a single scientific-accuracy percentage.

| Setting | Comparator | Readout | Paired 95% interval | Bootstrap mean difference |
| --- | --- | --- | --- | ---: |
| NK | Strict LocalPlus | ordinary | [0.048819, 0.277460] | 0.162361 |
| NK | Strict LocalPlus | IA_weighted | [0.069460, 0.266464] | 0.164270 |
| NK | Nonexperimental | ordinary | [-0.032327, 0.121488] | 0.047800 |
| NK | Nonexperimental | IA_weighted | [-0.050895, 0.117751] | 0.037408 |
| LK | Strict LocalPlus | ordinary | [0.065819, 0.260132] | 0.166588 |
| LK | Strict LocalPlus | IA_weighted | [0.070120, 0.220895] | 0.147175 |
| LK | Nonexperimental | ordinary | [-0.060253, 0.070932] | 0.006625 |
| LK | Nonexperimental | IA_weighted | [-0.081427, 0.052170] | -0.014332 |

All six new aspect outcomes are also retained:

| Setting / aspect | Ordinary micro-Fmax | IA micro | Macro | IA macro | Smin | IA Smin |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| NK / BPO |0.362058|0.300513|0.403024|0.357743|14.800394|14.252842|
| NK / MFO |0.558882|0.470539|0.475259|0.455906|4.347269|8.314709|
| NK / CCO |0.694507|0.479243|0.747496|0.587711|3.844152|4.250652|
| LK / BPO |0.338556|0.307044|0.392178|0.365280|19.046924|16.407099|
| LK / MFO |0.599418|0.460653|0.538285|0.490618|5.207073|10.579486|
| LK / CCO |0.695279|0.471727|0.743958|0.573815|3.828973|4.431890|

BPO/CCO point values do not acquire new confirmatory intervals from this MFO
analysis. Fixed-0.5 precision, recall, F1 and coverage for every profile remain
in the complete aggregate. No score threshold, ensemble or favorable setting
was fitted after these values were observed.

All six MFO profile/setting count checks reproduce the ordinary/IA micro-F
curves within 2.8×10⁻¹⁶, below the unchanged 10⁻¹² bound. The original
no-exclusion semantics and native populations remain intact. This comparison
supports further task-specific research; it does not change the retained app
profile, the earlier PK/shortlist findings or accepted graph facts.

Completed source aggregate FILE SHA-256:
`3d4d269bd23b92c3d2bf830f0031df9c067d1a00ae7c9e9b15fc5a6accd8230d`.
Raw forecasts, reference rows and per-protein arrays remain on Brev; only
aggregate results and small execution receipts were returned locally.

An independent saved-array review reproduced all 12 bootstrap score
distributions bitwise from the retained native counts, verified both seeded
protein-sampling frames and all eight paired summaries exactly, and confirmed
the native point/count gates. Large arrays stayed on Brev; no raw reference or
forecast rows were needed for that review. Its receipt FILE SHA-256 is
`4b6f35d0e1e4260b6214743e8e02394b63e600835a00f818c6aed41220454b56`.
