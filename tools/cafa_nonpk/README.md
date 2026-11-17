# Native CAFA5 no-knowledge and limited-knowledge transport

This optional adapter transports the locked historical LocalPlus model to the
official CAFA5 no-knowledge (NK) and limited-knowledge (LK) tasks. It follows the
already observed partial-knowledge (PK) comparison; it is not a new fit,
independent-study replication, or replacement for that frozen comparison. The
[completed results](../../docs/evaluations/SCIENTIFIC_RESULTS_20261114.md) explain
findings across all tasks.

## Sources, task and runtime

Use the separately qualified [CAFA5 v2 deposit](https://zenodo.org/records/22381862)
(CC BY 4.0), its [primary paper](https://doi.org/10.64898/2026.04.27.716980), and the
unchanged [author evaluator](https://github.com/claradepaolis/CAFA-evaluator-PK/tree/e386b085e204ccfbd75a4f52c1a8b25987d8b465)
(version 1.2.1). NK has no admitted annotation in any aspect at t0; LK is assessed
in an aspect without such annotation but has prior knowledge elsewhere. An LK
protein can also be PK in another aspect. The reference admits EXP-family codes
plus TAS and IC, rather than exclusively direct-assay labels.

The unchanged [published LocalPlus/GeneMANIA+ methods](https://doi.org/10.1093/bioinformatics/btaa885)
come from [official code](https://github.com/Murali-group/multi-species-GOA-prediction/tree/c45c21b9c937c3372eae03248f49fb008d4cb0cf).
Inputs are the strict historical 20,412-node, 985,863-weight STRING graph,
December 2018 weights/January 2019 alias support, UniProt2023_03 known annotations
and January 2023 GO ontology. UniProt2025_03 outcome terms are evaluation only.
No current GOA annotations enter prediction. Developers had already inspected
newer GOA material: this is a public retrospective benchmark, not a claim of
complete developer blindness or checkpoint-unseen biology.

Run from a **repository checkout**: `tools` is excluded from the application
wheel. Use isolated Python 3.10 with NumPy 1.26.4, SciPy 1.13.1, Pandas 2.2.3 and
tqdm 4.67.1. SciPy 1.13.1 retains the native solver's `tol` API. The app needs
none of these packages. Keep author code, archives, predictions and raw references
in ignored run directories; this README neither embeds nor downloads them.
`evaluate.py` and `counts.py` are optional GPL-3.0-only evaluator adapters; see
[NOTICE](../cafa_reference/NOTICE.md) and the
[license](../cafa_reference/LICENCE.GPL-3.0.txt). Dataset terms remain separate.

## Reproduction order

Use new output paths and record each manifest's **file SHA256** before the next
step. Commands require existing source-qualified inputs and explicit pins;
`--help` describes their full arguments.

```sh
python -m tools.cafa_nonpk.run prepare --strict STRICT_PACKET \
  --strict-sha256 STRICT_PROTOCOL_SHA --identities IDENTITY_ONLY_DIRECTORY \
  --author AUTHOR_DIRECTORY --author-receipt AUTHOR_RECEIPT --output NEW_FROZEN
python -m tools.cafa_nonpk.run predict --frozen NEW_FROZEN \
  --protocol-sha256 FROZEN_PROTOCOL_SHA --author AUTHOR_DIRECTORY \
  --author-receipt AUTHOR_RECEIPT --output NEW_PREDICTIONS
python -m tools.cafa_nonpk.run controls --frozen NEW_FROZEN \
  --protocol-sha256 FROZEN_PROTOCOL_SHA --archive BASELINE_ARCHIVE \
  --qualification BASELINE_QUALIFICATION --output NEW_CONTROLS
python -m tools.cafa_nonpk.evaluate freeze --frozen NEW_FROZEN \
  --protocol-sha256 FROZEN_PROTOCOL_SHA --predictions NEW_PREDICTIONS \
  --predictions-sha256 PREDICTIONS_MANIFEST_SHA --controls NEW_CONTROLS \
  --controls-sha256 CONTROLS_MANIFEST_SHA --parent-pk-config PK_CONFIG \
  --parent-pk-config-sha256 PK_CONFIG_SHA --output NEW_EVALUATION_CONFIG.json
```

Preparation reads only accession/aspect metadata and audits zero matching-aspect
t0 seeds. The completed frame contains 547 unique IDs (NK 133; LK 414). The five
fixed arms are strict LocalPlus, native BLAST, weighted ProtT5 cosine-three-neighbor
transfer, non-experimental annotations and Naive frequency. Scores are not
rescaled and controls are not chosen by their outcomes.

The separate GeneMANIA+ supplement was chosen after its PK result but before
NK/LK label release. Run `python -m tools.cafa_nonpk.gm_supplement preflight`, pin
its receipt, then `predict` with the same frozen frame, author source and explicit
`--preflight-report`/`--preflight-sha256` (see `--help`). It retains native alpha 1
and tolerance `1e-5`. Seal its protocol and prediction manifests before release:

```sh
python -m tools.cafa_nonpk.evaluate release --config NEW_EVALUATION_CONFIG.json \
  --config-sha256 EVALUATION_CONFIG_SHA --output NEW_RELEASE \
  --supplement COMPLETED_GM_DIRECTORY --supplement-protocol-sha256 GM_PROTOCOL_SHA \
  --supplement-predictions-sha256 GM_PREDICTIONS_MANIFEST_SHA
```

Release rechecks source/code/prediction pins, records a durable access event,
then decodes only the frozen **protein/aspect** pairs, preserving native row
bytes. Omitting the optional supplement leaves the original five-arm protocol
intact. Opened labels cannot become a fresh test by rerunning this procedure.

Use the Python API `evaluate.execution_jobs(...)` to create execution jobs with
an explicit old-path-to-execution-path map covering exactly its pinned files;
this is not a CLI subcommand. Generate a supplement job separately with
`supplementary_only=True`. Then use the existing drivers:

```sh
python -m tools.cafa_reference.remote_author --config EXECUTION_JOBS.json \
  --output NEW_NATIVE_POINTS
python -m tools.cafa_nonpk.counts --config PINNED_BPO_COUNT_JOBS.json \
  --output NEW_CHECKED_COUNTS
python -m tools.cafa_reference.paired_bootstrap --config PINNED_BOOTSTRAP_JOBS.json \
  --output NEW_INTERVALS
```

Jobs explicitly identify the pinned author source, isolated Python/dependencies,
ontology/IA/TOI, released references and method files. Count jobs additionally
pin every exact point curve and `native_outcomes.json`. Bootstrap jobs pin each
counts NPZ and agreement receipt, set 2,000 shared protein draws/seed `20261113`,
and declare every contrast. Use one worker/BLAS thread per job; the driver
expands one gzip prediction into a private temporary directory at a time.

Scoring uses native **`exclude=None`**, `fill`, `cafa`, no-orphans and thresholds
0.001–0.999. All 36 method/setting/aspect slots retain ordinary/IA micro and macro
Fmax, Smin, the fixed 0.5 point, native denominators and explicit missing-curve
status. Never impute an absent author curve as zero. For BPO uncertainty,
`counts.py` calls native `compute_confusion_matrix`, not the PK exclusion adapter.
Ordinary and IA micro-F must agree at **every** threshold within `1e-12` before
the existing bootstrap is admitted. Local-versus-four controls is the original
family; GM-versus-Local/controls is exploratory.

The count-job configuration now accepts an explicit native `namespace` for a
separately frozen aspect-specific comparison. Omission retains the original
`biological_process` default. This changes neither native arithmetic nor the
point-agreement tolerance; prior execution sources and results remain preserved.

## Preserved integration corrections

The first GM wrapper rejected tiny negative native conjugate-gradient roundoff,
although the author solver passed its residual tolerance. Its source, partial
output and failure remain preserved and unscored. V2 uses the unchanged author
API with native convergence plus an M-matrix/residual error bound; it neither
clips scores nor changes the positive-only writer. This corrects our integration,
rather than demonstrating a published-method failure.

The first counts adapter also imposed an extra all-29-column absolute check.
Large weighted raw Smin-related counts differed by about `4.55e-12` while the
predeclared micro-F endpoints agreed. V2 retains that failed receipt and all
29-column differences, enforcing the original endpoint gate unchanged.
[NumPy's reduction-order behavior](https://numpy.org/doc/1.26/reference/generated/numpy.sum.html)
matters here. Raw weighted Smin-count bitwise identity is explicitly **not**
certified; point curves, arrays, thresholds and resamples were unchanged.

## Completed interpretation and receipts

All six populations were retained: NK BPO/MFO/CCO N=44/39/118; LK N=227/60/197.
LocalPlus improves on several BPO sequence/frequency controls, but neither graph
method establishes an advantage over the non-experimental annotation control
on these BPO frames. Other aspects favor different controls: there is **no
universal winner**. Fmax is not a calibrated probability or whole-graph accuracy
percentage. Shared neighbors, transductive seeds, studies, incomplete annotation
and prior source exposure limit protein-bootstrap interpretation; unannotated
does not mean biologically false.

The preserved ignored run is `runs/cafa_nonpk_transport_20261114/` (freeze,
prediction/control manifests, release event, native aggregates, failed/v2
diagnostics and both BPO bootstrap reports). The aggregate-only standalone
publication is `runs/cafa_nonpk_transport_assessment_20261114/`, separate from the
PK 240-slot app publication. Those artifacts must be supplied separately for
exact byte replay; the tracked [results summary](../../docs/evaluations/SCIENTIFIC_RESULTS_20261114.md)
provides the deliverable interpretation. This is same-study transductive
transport, not an inductive unseen-gene or independent-study validation.

```sh
python -m unittest tools.cafa_nonpk.test_evaluate \
  tools.cafa_nonpk.test_gm_supplement tools.cafa_nonpk.test_counts -v
```
