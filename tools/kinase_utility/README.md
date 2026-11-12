# Optional kinase utility harness

This offline tool compares frozen Pharos kinase–kinase PPI masks within an
otherwise fixed phosphosite-based RoKAI workflow. Its endpoint is recovery of
author-annotated perturbation targets and agreement with their expected
direction. It does not establish PPI truth, whole-graph accuracy, CRC-specific
benefit or directly measured kinase activity.

The application core remains dependency-free. This directory is optional and
is not included in the application wheel or the core `tests/` discovery path.
No source-prior builder, benchmark data or automatic inference runner is included.

## Environment and invented tests

The evaluated Python environment is **Python 3.12.4, NumPy 2.5.4 and SciPy
1.18.1**. Use an existing matching environment or install the optional dependencies:

```sh
PILOT_PY=/absolute/path/to/python3.12
"$PILOT_PY" -m pip install -r tools/kinase_utility/requirements.txt
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
