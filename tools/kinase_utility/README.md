# Optional kinase utility harness

This offline tool compares frozen Pharos kinase–kinase PPI masks within an
otherwise fixed phosphosite-based RoKAI workflow. Its endpoint is recovery of
author-annotated perturbation targets and agreement with their expected
direction. It does not establish PPI truth, whole-graph accuracy, CRC-specific
benefit or directly measured kinase activity.

The application core remains dependency-free. This directory is optional and
is not included in the application wheel or the core `tests/` discovery path.
No benchmark data or source-prior builder is bundled. The configured workbook
runner below adds direct signature scoring; the historical seven-arm RoKAI
transport remains unchanged.

## Environment and invented tests

The evaluated Python environment is **Python 3.12.4, NumPy 2.5.4 and SciPy
1.18.1**, with **openpyxl 3.1.5** for configured workbook reads. Use an existing
matching environment or install the optional dependencies:

```sh
PILOT_PY=/absolute/path/to/python3.12
"$PILOT_PY" -m pip install -r tools/kinase_utility/requirements.txt \
  -r tools/kinase_utility/requirements-measurements.txt
PYTHONPATH=. "$PILOT_PY" -m unittest discover -s tools/kinase_utility -p 'test_*.py' -v
```

Run from the source-checkout root. These tests use invented identifiers,
measurements and references, with fabricated numeric outputs; they do not run
RoKAI propagation or access real benchmark files. The driver imports the
checkout's existing `biograph_steward.cohort_mapping` and sibling helpers.

## Required frozen inputs

Create a new pre-access execution freeze using the driver's
`biograph-steward.pilot-execution-freeze.v1` contract. It must pin absolute paths
and SHA-256 values for all supplied inputs and `pilot_driver.code_paths()`,
the source/protocol content seals, exact condition/cell/prefix rules, and an
opaque `reference_csv_sha256` commitment. Keep the reference CSV itself out of
`files_sha256` and `sealed_json`: preparation verifies every file pin. Keep
reference rows closed until predictions are sealed. Existing execution freezes contain their original absolute paths;
byte-identical copied code requires its own path-bound freeze before a new run.

The source prior is supplied separately and must contain:

- `enzyme_roster.json`: sorted, injective list of `{enzyme, gene, hgnc_id}`.
- `links.jsonl`: binary links with `enzyme`, `site_host`, one-letter `residue`,
  positive digit-string `position`, `phosphorylation_incidence: 1` and provenance.
- Four TSVs named as below, with exact columns `pair_id, subject, object, weight`
  separated by tabs and unchanged native weights in `[0,1]`.
- `receipt.json`: content seal, output hashes, matching registry seal and pinned
  upstream inputs/modules. Complete registry and reference-sequence captures
  are also required. Gene/canonical-coordinate correspondence does not resolve
  experimental proteoforms; unmapped evidence is not a biological negative.

### Audit of explicit source-protein identities

Source annotations that supply a literal primary UniProtKB protein can be audited with
`source_identity.resolve_source_protein_context`. It checks captured human
protein, HGNC and sequence-reference context directly. Another gene's alias or
an additional product of the same gene does not replace that supplied protein.
Missing secondary GeneID corroboration is recorded separately from conflicting
or nonunique cross-references. Isoforms, secondary accessions and site coordinates
are not rescued by this function.

This is an audit helper, not an alternative validation mode in `pilot_driver`.
It does not establish that the supplied identifier matches the protein studied
in the citation, or that the source's catalytic claim is correct. Investigation
found such a distinction for MST1/STK4. Source-only candidates remain on hold
for grounding qualification; no automatic accession replacement is performed.
The driver, gene-only measurement/reference rules and completed comparison remain
unchanged.

See the [coverage and grounding follow-up](../../docs/evaluations/KINASE_COVERAGE_GAPS_20261112.md)
for the source flags, assay limitations and candidate HOLD decision.

## Configured workbook comparisons

`measurement_adapter.py` uses an explicit visible-sheet, positional-column and
descriptor-grammar contract. Full workbook transport reuses **openpyxl 3.1.5**;
limited header/descriptor inspection uses selective XML before outcome access.
Install the additional optional reader dependency with
`pip install -r tools/kinase_utility/requirements-measurements.txt`.

`signature_comparison.py` accepts arbitrary declared sample groups and target
cases. It implements positive-intensity mean-log contrasts, explicit duplicate
and host-protein eligibility, the published raw RoKAI z-score, and descriptive
signed average-tie target ranks. It has no fixed cell-line, drug or target names.
It does not perform graph propagation. A partial signature catalogue is
ineligible for complete-catalogue ranking.

`source_eligibility.py` applies explicit reviewed source-record dispositions
before link support is collapsed. Reviews bind the release, source bytes,
record ID, ordinal and canonical raw-row digest. Other eligible supporting
records survive; unreviewed assertions and abstentions are preserved. The
helper never maps names globally or judges biological truth.

Run a new, fully pinned execution plan with:

```sh
PYTHONPATH=. "$PILOT_PY" tools/kinase_utility/run_signature_comparison.py \
  --plan /absolute/new-execution-plan.json --output /absolute/new-output
```

The runner validates source roles, candidate contexts, runtime versions,
workbook contracts and source profiles before opening quantitative rows.
Optional corroboration may remain unavailable only under a declared field
contract; missing secondary annotation is not evidence of zero biology.
Formula/error cells stay unavailable for their own samples; they do not
invalidate unrelated intervention contrasts when the identity descriptors
qualify. The output preserves source-cell locators, unresolved rows, missingness,
per-case abstentions and the prediction seal. Original workbooks remain intact.

New studies need explicit sample/measurement contracts and assay-appropriate
eligibility rules. A kinase-signature five-site rule is not a general threshold
for PPI, clinical or literature claims. Unknown semantics require source review,
not a silent repair. Synthetic tests cover different workbook layouts and
single-/multi-condition designs; these establish software portability, not
biological accuracy across all questions.

`signal_diagnostics.py` adds post-scoring background and score-sign summaries.
It receives no expected signs and changes no predictions or normalization.
Available-candidate counts are reported with ranks; neither a small catalogue
nor a condition-wide sign shift establishes target-specific recovery.

See the [completed external check](../../docs/evaluations/HCT116_EXTERNAL_COMPARISON_20261112.md)
for the preserved initial run, explicitly labelled technical replay and limits.

## Published curated-library source comparison

`library_adapter.py` adapts the released benchmarKIN curated CSV with the
existing gene/product and canonical-site correspondence checks. Present 15-mer
flanks must agree with the captured reference; explicitly unavailable flanks
remain unreported. Duplicate membership adds no weight. The separate author
measurement grammar is `gene|site|ENSG|ENSP`: ENSG must corroborate the captured
HGNC relation and ENSP remains unverified protein-isoform context. These checks
do not certify catalytic truth or independent source support.

`run_source_comparison.py` is byte-identical to the working frozen comparison
runner. It accepts explicit source profiles, candidate genes, conditions,
parent studies and file/runtime pins. It seals predictions before decoding
reference targets/signs, keeps missing-target penalties, weights conditions
within parent studies, and reports a separate common-finite sensitivity. The
supported CSV schemas are explicit; it does not guess a reader for new studies.

```sh
PYTHONPATH=.:tools/kinase_utility "$PILOT_PY" tools/kinase_utility/run_source_comparison.py \
  --plan /absolute/new-source-comparison-plan.json --output /absolute/new-output
```

The [completed comparison](../../docs/evaluations/CURATED_SIGNATURE_RECOVERY_20261112.md)
shows increased coverage/recovery but mixed ranking on shared targets. It
preserves the initial failed transport and labels the corrected execution as
a technical replay after exposure. The whole reference compilation is consumed.
Synthetic integration checks cover the actual registry loader, four-field
transport, changed input bytes, an empty qualified measurement set, prediction
sealing and hierarchical weighting. No native library or reference data are
bundled, and the core app and its default dependencies remain unchanged.

The author library lacks per-edge citations and contains historical name/isoform
projections. Upstream redistribution terms remain separate from the repository
license. This is a private source-choice comparator, not an automatic graph
import, replacement, acceptance rule or redistributable source catalogue.

## Driver commands

The following placeholders require an independently reviewed, frozen input set:

```sh
PYTHONPATH=. "$PILOT_PY" tools/kinase_utility/pilot_driver.py prepare \
  --execution-freeze /absolute/new-freeze.json \
  --measurement-csv /absolute/measurements.csv \
  --condition-roster /absolute/conditions.json \
  --registry-directory /absolute/registry \
  --sequence-reference /absolute/reviewed-human-sequences.tsv \
  --prior-directory /absolute/prior \
  --ppi-unpruned /absolute/prior/unpruned_native_weighted_kinase_PPI.tsv \
  --ppi-native /absolute/prior/native_top80_native_weighted_kinase_PPI.tsv \
  --ppi-primary /absolute/prior/human_experimental_top80_native_weighted_kinase_PPI.tsv \
  --ppi-ne /absolute/prior/ne_top80_native_weighted_kinase_PPI.tsv \
  --output /absolute/prepared

PYTHONPATH=. "$PILOT_PY" tools/kinase_utility/pilot_driver.py seal \
  --prepared-directory /absolute/prepared \
  --output-mat /absolute/numeric-output/activities.mat --output /absolute/sealed

PYTHONPATH=. "$PILOT_PY" tools/kinase_utility/pilot_driver.py score \
  --sealed-directory /absolute/sealed \
  --reference-csv /absolute/references.csv --output /absolute/scored
```

Between `prepare` and `seal`, a separately controlled numeric step consumes only
the prepared MAT file. The wrapper uses GNU Octave syntax and the fixed seven
mean/z-score arms. The evaluated runtime is GNU Octave 11.3.0, image
`gnuoctave/octave@sha256:185db7993e000d4f3f6e7bbbf7fb3f999f52e799ea52231ad8a15353381e0dcb`.
Stage `run_numeric_batch.m` beside `src/rokai/` containing the three vendored
functions, with their LICENSE. The wrapper accepts `/input/<name>.mat` and
`/output/<name>.mat`; its repository location is not that staged packet layout.
All output directories must be new. The driver preserves missingness, zero
values, source context, graph-arm bindings and the prediction/reference boundary.

## Code identity and attribution

The transport, pilot tests and vendor files are byte-identical to commit
`ac5dd24`, used in the completed comparison, whose execution freeze is
`daf125a55c4d9129a7998fe0f829b7004d9c5955320a0dd3061bd001313e3887`.
The separate source identity audit and its tests were added afterward; they
were not used to produce that comparison. Use the historical commit or saved
frozen analysis sources for exact replay; do not retarget or reseal the old study.

The three unchanged RoKAI functions are from
[Serhan Yılmaz and colleagues' official repository](https://github.com/serhan-yilmaz/RoKAI/tree/179c23e5090350e619e82e2536aaf0af9a714137),
revision `179c23e5090350e619e82e2536aaf0af9a714137`.
Their [MIT license](rokai_source_metadata/LICENSE), copyright 2020 Serhan Yılmaz,
is retained. Cite [Yılmaz et al., Nature Communications 2021](https://doi.org/10.1038/s41467-021-21211-6).
The SIGNOR alternative prior and zero site–site ablation do not replicate the
authors' original PhosphoSitePlus/PTMcode network. Data-source terms apply
separately; no benchmark library or reference rows are bundled here.
