# Official CAFA5 reference and evaluator adapter

This optional research track measures temporal protein-function annotation
prediction against the author CAFA5 benchmark. It reuses the released reference,
ontology, known-annotation exclusions and evaluator. It is separate from the
application's source-compatibility census and does not change graph decisions.

The reference is the author [CAFA5 evaluation deposit, v2](https://zenodo.org/records/22381862)
under CC BY 4.0. Its January 2023 GO ontology, historical `known_t0` annotations
and 2025_03 evaluation labels remain distinct. The
[primary paper](https://doi.org/10.64898/2026.04.27.716980) admits the eleven
experimental-family evidence codes **and TAS and IC**. Native evaluation TSVs
do not contain per-row evidence codes; they must not be presented as an
independently filtered direct-experiment-only reference.

The separately preserved [official evaluator](https://github.com/claradepaolis/CAFA-evaluator-PK)
is revision `e386b085e204ccfbd75a4f52c1a8b25987d8b465`, package version 1.2.1,
GPL-3.0. Its publication is
[Piovesan et al., 2024](https://doi.org/10.1093/bioadv/vbae043).
The two `author_*_runner.py` adapters are separately GPL-3.0-only and import
that code only in an isolated research process. No author code is vendored into
the MIT application or added as a core dependency.

Run these commands from a repository checkout: the application wheel excludes
`tools`. Point scoring/counts use separate Python 3.10.12, NumPy 1.26.4 and
Pandas 2.2.3. Historical model prediction also needs SciPy 1.13.1 and tqdm 4.67.1;
the optional query-context proof additionally needs Torch 2.6.0 and
torch-geometric 2.6.1. See the [prediction README](../cafa_prediction/README.md)
for those distinct roles. Keep this runtime separate from the app and the Brev
model server. Raw artifacts and author code are separately qualified, ignored
inputs, rather than files supplied by these README commands.

## Before future labels are opened

`intake.py` matches archive size and publisher checksum, enforces ordinary
archive members, and extracts historical training/ontology inputs. For future
files it decodes **only accession and the independently supplied aspect
column**. The future GO term column stays opaque. Unit tests include an invalid
UTF-8 sentinel in that column to exercise this boundary. Real source captures
are separate Git-ignored artifacts.

The exact 3,172-protein historical graph has 1,294 partial-knowledge reference
targets: 833 biological-process, 525 molecular-function and 445
cellular-component targets before native eligibility filtering. Targets may
appear in more than one aspect. The primary is fixed partial-knowledge BPO
unweighted micro-Fmax; other aspects and macro, information-weighted and Smin
readouts are secondary. These are benchmark annotation metrics, not a
whole-graph percentage of biological truth.

The existing project has already examined newer GOA source corpora. This is a
**public retrospective temporal benchmark**, not a claim that developers never
encountered any test biology. The new learners use only the historical network
and `known_t0` annotations, with fixed author methods/defaults, and all model,
baseline, graph-view and fusion predictions must be sealed before future GO
term labels are opened. Prior-source exposure strata are descriptive only;
they do not change the fixed primary frame.

## Release and exact author scoring

`evaluate_author.py release` requires explicit method/source freeze files,
prediction-file hashes and the exact frozen scoring policy. It records the
release event before decoding future term values. Future rows are selected only
by the already fixed exact protein frame; native bodies are not rewritten.
An optional separately pinned target-ID file can narrow that frame, but cannot
add another protein. It keeps the 4,806 reserved accession identities distinct
from the original 1,294 and leaves every other future target's GO values
undecoded. This is same-study transductive target transfer, not independent-study
replication or a claim that targets were absent from the historical training graph.
The separate after-t0-publication exclusion file is **evaluation only** and is
never available as a training feature.

The author parser reads plain prediction TSVs, so the driver decompresses each
sealed gzip prediction into a temporary per-method directory. It calls the
unchanged author library with `fill`, `cafa`, no orphans, the official IA/TOI
files, exact known exclusions and the fixed 0.001…0.999 threshold grid. The
returned floating-point curves are preserved at full precision in addition to
the author's ordinary rounded exports. Methods with no scored prediction fail
explicitly; they are not silently replaced with invented successful output.
The predeclared score threshold 0.5 is also exported as micro PPV, recall and F1.
It is not selected using test labels and does not make raw model scores calibrated
probabilities. If the author omits that threshold because prediction coverage is
zero, the export records the missing author row rather than inventing a PPV.

Historical known rows are filtered to the fixed protein frame **before** the
author exclusion parser. That parser otherwise constructs dense matrices for
all 137,377 source proteins and then discards proteins outside the ground truth.
Pre-filtering those exact rows preserves its semantics and avoids this large
allocation. The complete source file remains pinned and preserved.

```sh
python -m tools.cafa_reference.intake --help
python -m tools.cafa_reference.evaluate_author release --help
python -m tools.cafa_reference.evaluate_author evaluate --help
```

## Paired uncertainty

The author contribution adapter calls the same source per-protein confusion
function used for point scoring. Its ordinary and IA-weighted micro-F curves
must reproduce the complete author's exact curves to within `1e-12` before
resampling is admitted. The standard paired protein bootstrap uses 2,000 draws,
seed `20261113`, with identical protein multiplicities for all arms. All terms
of a sampled protein stay together; Fmax is recomputed on the same fixed grid.
The bootstrap is a descriptive conditional comparison of this benchmark's
proteins, which share neighbors, sources and studies. It is not independent
study replication or proof that unannotated functions are biologically false.
Fmax's optimized evaluation threshold is not an application acceptance threshold.

Reportable native points, per-protein contributions and resampling use the same
isolated Python 3.10.12 / NumPy 1.26.4 / Pandas 2.2.3 runtime. Earlier local
NumPy 2.3.5 runs are retained as numerical-runtime sensitivities. The unchanged
floating-point threshold grid can differ by a unit in its last place between
runtimes; the strict shared-grid check rejects such a mismatch instead of
loosening its tolerance.

An author-example engineering smoke reproduced all 999 ordinary and weighted
micro-F curve values exactly before any real CAFA5 future term was decoded.
The sample's unit information weights were explicitly invented for that software
test. The actual source evaluation continues to use the author IA file.

```sh
python -m unittest tools.cafa_reference.test_intake \
  tools.cafa_reference.test_evaluate_author \
  tools.cafa_reference.test_paired_bootstrap -v
```

## Complete aggregate delivery

`aggregate_report.py` seals all 240 declared method/frame/setting/aspect slots,
native ordinary and information-weighted eligible denominators, Fmax/Smin,
the fixed 0.5 operating point and completed paired intervals. Pending,
unsupported and negative outcomes remain explicit. It checks the source curves'
hashes and includes the frozen protocol, reference-release and runtime receipts;
it never opens raw reference rows or selects another model or threshold.

`stratified_aggregates.py` applies the unchanged author's normalization to
already checked per-protein contributions. Pharos development levels and prior
selected-source exposure were declared before label release. Historical degree
and known-annotation quartiles are explicitly post-outcome descriptions. Small
strata, shared curation and incomplete annotation prevent interpreting these as
independent subgroup biological-accuracy estimates. The full population remains
the authoritative benchmark.

## Delivery figures

`create_results_pdf.py` renders the short November 14 addendum from its pinned,
sanitized repository aggregate and the saved hosted screenshot. It needs
ReportLab, separate from the application runtime. It reads no raw reference
cases and can run from this checkout. `plot_comparisons.py` renders selected
controlled comparisons with Matplotlib from the completed aggregate receipt;
it does not run a learner or choose another hypothesis.

The separately frozen native NK/LK transport uses non-exclusion scoring and a
distinct label-release gate. Its reproduction order and integration receipts
are documented in [cafa_nonpk](../cafa_nonpk/README.md); its outcomes are not
added to this PK 240-slot inventory. The
[completed results](../../docs/evaluations/SCIENTIFIC_RESULTS_20261114.md) retain
negative primary, pruning and transport findings alongside measured gains.
