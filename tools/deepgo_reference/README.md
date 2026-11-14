# Optional DeepGO-SE comparison

This package runs the published DeepGO-SE sequence/ontology predictor in an
isolated runtime, then reuses the project's existing CAFA evaluator. It is a
research comparison; it does not insert biological facts, prune a graph, change
review decisions or replace the hosted workbench's retained LocalPlus profile.

The current comparison uses **6,100 previously evaluated CAFA5 partial-knowledge
(PK) proteins**. Its results are development evidence. Source qualification and
native execution checks do not establish biological accuracy.

See [the method and artifact record](../../docs/evaluations/DEEPGO_SE_20261114.md)
for the primary paper, immutable source, checksums, runtime differences and
measurement rules. The primary fill comparison is complete: all four BPO
paired intervals favor retained LocalPlus, so its adoption rule failed and the
app profile stays unchanged. MFO Fmax improvements and mixed CCO results remain
visible. The completed exploratory secondary supplement has four positive MFO intervals across both
existing cohorts/readouts and four CCO intervals crossing zero; it is post-hoc,
unadjusted and is not used for model adoption. The completed separate
common-max sensitivity also has four negative BPO paired intervals; it cannot
replace that primary. All 12 MAX cells remain visible in the linked method
record and its static appendix.

## Sources and setup

Use [archived author code v1.0.0](https://doi.org/10.5281/zenodo.10369694),
[published model data](https://doi.org/10.5281/zenodo.10369249), and the
[maintainer's corrected cellular-component models](https://github.com/bio-ontology-research-group/deepgo2/issues/16#issuecomment-6435122743).
The original model archive contains incorrectly packaged CCO weights; retain it
for provenance and use the separate correction for CCO inference. Do not infer
namespace correctness from tensor dimensions alone.

The optional inference runtime is Linux x86_64/Python 3.10 with the seven pinned
scientific dependencies in the method record. Keep it separate from the
workbench, language-model server and CAFA measurement runtime. The first ESM
extraction needs a suitable GPU; large archives, features and forecasts should
remain on the compute volume.

1. **Index and select sources.** `archive.py index` verifies the publisher's
   archive size and MD5 before streaming its member metadata. `archive.py extract`
   requires that index's FILE SHA and an explicit JSON mapping of exact source
   members to new relative paths. Select only the fixed MFO/BPO models, ordered
   terms and ontology texts from the main archive; select CCO models/terms from
   the correction. Select only `uniprot_sprot.fasta.gz` from the dated Swiss-Prot
   archive. Selected links, sparse entries, traversal and collisions are rejected;
   unselected links are inventoried without following them. No training,
   neXtProt or reference labels are selected.
2. **Assemble the model view.** `modelview.py` accepts the two extraction receipts
   and their FILE hashes. It creates a new ordinary-file view with the exact
   published model memberships, preserves the correction's lineage and rejects
   cross-namespace identical checkpoint hashes.
3. **Stage dated sequences.** `sequences.py` uses Bio.SeqIO on the pinned
   Swiss-Prot 2023_03 FASTA and exact 1,294/4,806 target lists. It writes
   accession-only inference headers and keeps original headers, sequence hashes,
   missing IDs and truncation metadata in its receipt. All targets remain in the
   evaluation frame. The completed run preparation covers all 6,100 targets.
4. **Pin local ESM files.** Supply both the official ESM2 3B checkpoint and its
   co-located `-contact-regression.pt` file. Native name-based loading can fetch
   weights; this adapter instead requires explicit local file hashes and a fresh
   feature output.
5. **Create the input configuration.** Copy [INPUTS.example.json](INPUTS.example.json),
   replace every example path and zero hash, and use the actual verified receipts.
   The example contains no cases, model weights, private operator paths or keys.
   `code_intake` is the sealed ledger for the verified author ZIP and its ordinary
   code members. `evaluation_plan` pins the already declared comparisons and
   earlier LocalPlus contribution arrays. These are required prepared inputs;
   this package does not silently download or invent them.

Each output directory must be new. The command-specific flags are available via
`python -m tools.deepgo_reference.MODULE --help` for `archive`, `modelview`,
`sequences`, `run`, `native_jobs`, `evaluate` and `collect`.

## Freeze, check and predict

```text
python -m tools.deepgo_reference.run prepare --config INPUTS.json --output FREEZE
python -m tools.deepgo_reference.run parity --frozen FREEZE --expected PROTOCOL_FILE_SHA --output PARITY
python -m tools.deepgo_reference.run predict --frozen FREEZE --expected PROTOCOL_FILE_SHA --parity-file PARITY/parity.json --parity-sha256 PARITY_FILE_SHA --output PREDICTIONS
```

The execution device is fixed to `cuda:0`. `prepare` binds source files, the
actual runtime, fixed native parameters, prior label exposure and the evaluation
plan before the new forecasts. `parity` runs the unchanged author CLI on three
fixed source-selected proteins and compares its default `>=0.1`, three-decimal
outputs against the adapter's presentation. It shares a checked native feature
cache. Full prediction requires that exact passed parity receipt.

`native.py` checks every archived source member and the paths of imported
`deepgo.*` modules. It calls the unchanged author extractor, normal-form loader
and `DeepGOModel`. It retains the first 1,022 residues, length-based batching,
exact six-model memberships/order, batch size 32, eval/no-grad forwards and
sequential float32 averaging. Features are joined by literal accession because
native batching can reorder rows.

`scores.py` exports every raw score cell before the CLI's cutoff and rounding;
the native presentation is used only for equivalence checks. The producer does
not recalibrate scores, propagate them through a replacement ontology, train a
model or choose a favorable test threshold. The released inference archives do
not provide a compatible MLP/GAT control. No such checkpoint is invented or
retrained here.

## Measure the sealed forecasts

Use the earlier **separate CAFA runtime**: Python 3.10.12, NumPy 1.26.4,
SciPy 1.13.1 and Pandas 2.2.3. DeepGO inference uses author NumPy 1.26.1 and
Pandas 1.5.0. This separation preserves the existing benchmark implementation.

After a complete forecast seal, `native_jobs.py` joins exact gzip members per
cohort without changing their decompressed values and prepares the unchanged
native point/count adapters. It uses the existing `adapters/remote_author.py`,
full previously released references, known masks, ontology and IA. `evaluate.py`
checks that source-frozen plan and calls the existing paired bootstrap.
`collect.py` retains all six new cohort/aspect cells and all 246 prior outcomes,
including negative and unavailable results.

The fixed comparison uses 2,000 shared protein bootstrap draws and both ordinary
and IA BPO micro-Fmax. All MFO/CCO, macro/IA, Smin and fixed-0.5 results stay
visible. Fmax's optimal benchmark threshold is not an application confidence or
a prospectively validated acceptance rule. Missing native coverage stays an
explicit missing status; it is not filled with invented precision/recall.

## Compare a fixed review budget

The separate [shortlist protocol](../../docs/evaluations/DEEPGO_SHORTLIST_20261114.md)
compares up to three benchmark-qualified terms per protein/aspect from the same
saved DeepGO and strict Local forecasts. The primary quantity is curator-supported
slots per fixed three-slot budget, with PPV among returned terms reported
separately. It reuses native parsing/confusion counts and SciPy paired bootstrap;
ancestor-pair/IA diagnostics never rerank the candidates. This remains exposed-label
development work, with the earlier BPO decision and app default unchanged.
The completed comparison has a positive MFO interval only in the additional
cohort; the original MFO interval crosses zero, while all BPO/CCO intervals
favor LocalPlus. The protocol links all outcomes and redundancy/IA diagnostics.

`shortlist.py` requires the source-frozen config and existing isolated CAFA
runtime; it performs no GPU/model calls. `publish_shortlist.py` accepts only the
sealed aggregate and matching freeze, preserving all 12 profile cells and six
paired differences through the existing path sanitizer.

## Lower-knowledge development extension

The [NK/LK assessment](../../docs/evaluations/DEEPGO_NK_LK_20261114.md) reuses
547 existing targets and the native **no-exclusion** evaluation branch; it does
not substitute the PK known-mask adapter. All 36 earlier rows plus six DeepGO
outcomes and eight MFO intervals remain visible. MFO improves versus strict
LocalPlus in both settings/readouts; every interval against the official
nonexperimental control crosses zero. No consumer or default changes.

`nonpk_evaluate.py` gates complete bound forecasts and exact service restoration
before calling existing point/count/bootstrap helpers. `nonpk_publish.py`
sanitizes only saved aggregates, retaining all 42 outcomes and eight intervals.
The method record documents exposed-reference, small-population and training
limitations; these are not whole-graph scientific-accuracy measurements.

## Publish the saved comparisons

The primary publisher reads only sealed aggregates and preserves all 252
outcomes, the fixed retention rule and the complete earlier controls:

```text
python -m tools.deepgo_reference.publish --source PRIMARY_FILL/report.json --expected PRIMARY_REPORT_SHA --previous-report PREVIOUS_COMBINATION/report.json --old-report PREVIOUS_240/report.json --output NEW_PUBLIC_PRIMARY_DIRECTORY
```

To include the separate completed MAX appendix in that new publication, add
`--max-source MAX/report.json --max-expected MAX_REPORT_SHA --max-execution
MAX/execution_started.json --max-execution-expected MAX_EXECUTION_SHA`.
The execution receipt must bind the same completed fill primary. This adds
separate MAX JSON/HTML; it cannot replace the primary outcomes or retention rule.

### Exploratory secondary supplement

`publish_secondary.py` is an aggregate-only companion to the existing primary
publisher. It accepts the sealed secondary report, its post-hoc source freeze,
and the original fill aggregate, each with an explicit FILE SHA-256. It reuses
the existing sanitizer and static table renderer. It reads no raw forecast,
reference case, sequence or checkpoint, and does not call the model/evaluator.

```text
python -m tools.deepgo_reference.publish_secondary --source SECONDARY/report.json --expected SECONDARY_REPORT_SHA --freeze SECONDARY/source_freeze.json --freeze-expected SECONDARY_FREEZE_SHA --primary PRIMARY_FILL/report.json --primary-expected PRIMARY_REPORT_SHA --output NEW_PUBLIC_SECONDARY_DIRECTORY
```

The new directory contains `secondary_uncertainty.json`, static
`secondary_uncertainty.html`, a reviewable `secondary_uncertainty.md` insertion,
and `publication_manifest.json`. All eight MFO/CCO × cohort × readout intervals,
including negative results, are required. Exposed-point, post-hoc and unadjusted
labels, native count/point agreement, source pins and the unchanged primary
retention decision are preserved. A favorable secondary aspect cannot replace
the failed BPO gate or add a model consumer.

The separately captured execution sources have local archival refs
`codex/archive-deepgo-max-20261114` (`bc41b2a6d2291f48c576e405f1ca1009ec232795`)
and `codex/archive-deepgo-secondary-uncertainty-20261114`
(`431206b9d53dc299870078b53182cb2ef219c0fe`). The latter preserves unexecuted
preparations alongside the final v3 full-parser operator. These refs are
local-only until explicitly pushed; the maintained publisher does not depend
on checking them out or importing their execution scripts.

### Shareable comparison figure

`create_figure.py` follows the existing Matplotlib aggregate-plotting tools.
It requires the two public manifest FILE hashes, shows all twelve fill
contrasts, and distinguishes the four fixed BPO intervals from all eight
post-hoc MFO/CCO intervals. Dots use observed point differences, with saved
conditional intervals; bootstrap means are retained separately in its JSON.

```text
python -m tools.deepgo_reference.create_figure --publication PUBLIC_PRIMARY --manifest-sha256 PRIMARY_PUBLIC_MANIFEST_SHA --secondary PUBLIC_SECONDARY --secondary-manifest-sha256 SECONDARY_PUBLIC_MANIFEST_SHA --output NEW_FIGURE_DIRECTORY
```

The output contains PNG/SVG, plotted aggregates and a source-pinned receipt.
Matplotlib is an optional presentation dependency; rendering does not invoke
the model or evaluator or change their separately pinned runtimes.

## Recovery and tests

The extractor writes its full feature cache after all batches; it has no
per-batch restart checkpoint. Preserve successful parity receipts, full feature
caches and failed output directories. A later cache resume requires explicit
source/runtime/identity binding in a new execution record. Never silently admit
an unrelated cache or overwrite a failed run.

Run the invented-data checks in a Python environment with NumPy installed
(the import preflight prevents counting optional NumPy skips as full coverage):

```text
python -c "import numpy"
python -m unittest discover -s tools/deepgo_reference -t . -q
```

They exercise source/archive boundaries, identity/order/float32 behavior,
metadata pins, the real evaluator-directory layout and saved-summary handling.
No biomedical reference case or model is loaded by these tests.
