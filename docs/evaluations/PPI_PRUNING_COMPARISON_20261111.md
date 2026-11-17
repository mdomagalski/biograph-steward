# Fixed PPI pruning comparison — November 11, 2026

**Status: completed.** All graph packages passed full replay and were frozen
before outcome access. The official scorer passed its complete pre/post-score
verification, and every metric matches the local replication and independent
row-by-row arithmetic recount. The result is a **tradeoff, not a clear NE pruning
advantage under the fixed decision rule**.

This is a concrete selection of existing PPI graph edges, extending the earlier
answer-ordering feature. It preserves the source graph and publishes separate,
reversible views. The [workflow guide](../PPI_PRUNING.md) gives runnable commands;
the [methods and literature decision](PPI_PRUNING_METHODS_20261111.md) explains
the fixed task, comparator and limits.

## Completed source and method execution

The existing audited Pharos319 inventory was replayed offline, preserving its
source properties, raw responses, exact identities and provenance. No fresh
Pharos retrieval, language-model call or GPU computation was required.

| Source inventory | Count |
| --- | ---: |
| Requested exact protein accessions | 3,173 |
| Resolved canonical graph proteins | 3,172 |
| Unresolved requested accession, retained in the numerical index as an isolate | 1 |
| Canonical PPI evidence edges | 89,665 |
| Preserved source views | 179,330 |
| STRING-containing pairs with a native `Score` | 88,073 |
| Exact STRINGDB-only pairs eligible for selection | 81,756 |
| Protected mixed-provider or non-STRING pairs | 7,909 |

NE consumed the same 88,073 weighted source edges and all 3,173 numerical node
entries, including the 24 nodes isolated in that weighted network. The unchanged
author implementation completed in **57.51 seconds** of CPU algorithm time and
returned all 88,073 original-edge scores. It used the published defaults,
hash-pinned author revision `8662284871274b805ed82f725af54ab76dc79e53`, and the
immutable GNU Octave 11.3.0 container. The external author files and their
GPL-3.0 license remain separate from the MIT application; the adapter does not
reimplement the algorithm.

The [original NE study](https://www.nature.com/articles/s41467-018-05469-x)
evaluated biological gene-function prediction across tissue networks. Its
results motivate testing network utility here; they do not establish improvement
on binary Y2H detection. This increment evaluates that transfer explicitly.

## Fixed selections before assay scoring

Each scored arm retains `floor(4 × 81,756 / 5) = 65,404` eligible pairs, ranked
by either native STRING score or NE score. The 80% operating point was fixed
without outcome tuning. Exact pair IDs break cutoff ties; score ties remain
intact in any separately declared raw-score ranking assessment.

| View | Eligible pairs retained | Eligible pairs removed | Protected pairs retained | Verified full view edges |
| --- | ---: | ---: | ---: | ---: |
| Unpruned control | 81,756 | 0 | 7,909 | 89,665 |
| Native score, top 80% | 65,404 | 16,352 | 7,909 | 73,313 |
| NE score, top 80% | 65,404 | 16,352 | 7,909 | 73,313 |

The selections exchange **9,815 retained pairs in each direction**. This is an
actual graph difference, rather than another run on identical inputs. At the
native cutoff of **0.48**, 153 pairs share the boundary score and the fixed ID
rule retains 100. These are source-only selection diagnostics; they do not establish
which arm preserves more useful biological evidence. The budget
applies to the whole eligible graph, so retained assay-panel counts may differ.

## Verified graph utility

All three views preserve the same 3,172 canonical protein records. The baseline
has 17 isolated proteins, 18 components and a largest component of 3,155 proteins.
NE preserves all three counts after pruning. Native-score pruning produces
38 isolates, 40 components and a largest component of 3,132 proteins. This is a
connectivity result, not evidence of improved assay detection or scientific truth.

## Measured development result

The reference is the **previously consumed Lambourne human Y2H-v1 panel**:
3,222 nominations, including 2,676 assay-eligible pairs (376 detections and 2,300
conditional nondetections). Of these, 1,966 pairs are present in the source graph:
334 detections and 1,632 nondetections. The 710 uncovered pairs include another
42 detections; pruning cannot recover absent edges. The remaining 546 nominees
are excluded by the unchanged author-assay rules: 478 failed sequence confirmation,
41 autoactivators and 27 failed tests. [Primary study](https://www.nature.com/articles/s41467-026-70942-x),
[author code](https://github.com/CCSB-DFCI/ai-interactome-experimental-assessment).

| View | Measured pairs retained | Detections retained | Detections removed | Conditional nondetections removed | Detection fraction among retained measured pairs |
| --- | ---: | ---: | ---: | ---: | ---: |
| Unpruned | 1,966 | 334 | 0 | 0 | 16.99% |
| Native top 80% | 1,896 | 326 | 8 | 62 | 17.19% |
| NE top 80% | 1,954 | 334 | 0 | 12 | 17.09% |

Both pruned graphs have the same 73,313 edges, but their measured-subset coverage
is different. NE preserves eight additional detections and 50 additional
nondetections relative to native-score pruning. Its retained detection fraction
is slightly lower. The interpretation rule fixed before scoring required more
retained detections **and no lower retained detection fraction** for a bounded
NE advantage. That gate is **false**; report the tradeoff rather than declaring
NE the superior pruning policy.

Within the 1,142 pruning-eligible measured pairs, native selection retains
154/162 detections and 918/980 nondetections; NE retains 162/162 detections and
968/980 nondetections. The eight native detection losses all score strictly
below the 0.48 cutoff, so they do not depend on cutoff tie-breaking. Five have
known HuRI pair exposure; three have neither HuRI nor INMC exposure flags.
An unflagged record is not certified independent.

The three unflagged detections removed by native pruning but retained by NE are
source rows 3,130 (`P28676–P30626`), 3,307 (`P08754–Q9UGC6`) and 3,527
(`P22674–P38936`, CCNO–CDKN1A). Row 3,527 is the previously consumed walkthrough example,
with AD construct `100063977` and DB construct `3192`; it is a traceable illustration,
not a newly selected independent validation case.

**Secondary raw-score ranking:** full-panel average precision increases from
**0.152396936 to 0.175440454** (absolute +0.023043519), with identical numeric
coverage of 1,952/2,676 pairs. The other 724 scores remain explicitly missing
and tied below numeric values. This assesses transformed-score ranking on the
unpruned inputs, including protected mixed-STRING pairs. It is not AP of the
pruned graph and does not override the primary tradeoff decision.

This is not a new best ranking result across our project. The earlier native
STRING 12.5 physical overlay achieved AP **0.190056** on the same consumed panel,
compared with 0.172827 for its functional scores. Its source release and coverage
differ from this frozen Pharos-score experiment, and it did not provide these
whole-graph pruning packages. It remains the strongest measured source-component
ranking result; the NE comparison does not establish superiority over it.
[Prior fixed source comparison](STRING_COMPONENT_COMPARISON_20261027.md).

STRING functional associations, physical/co-complex proximity and direct
binding are different relationships. The
[earlier STRING component comparison](STRING_COMPONENT_COMPARISON_20261027.md)
tested functional scores against a physical overlay; this experiment instead
compares native versus NE ranking of the same frozen source edges. An assay
nondetection is conditional on its constructs and experimental conditions; it
does not show that a discarded functional association is false. The captured
Pharos source does not establish its upstream STRING release or complete
study-level reuse. Consequently, this remains retrospective development and
cannot establish independent scientific accuracy.

**Decision:** preserve both optional development views and the unchanged baseline.
Do not promote NE to a default or claim general biological accuracy. The measured
ranking gain, preservation of observed detections and connectivity are useful
bounded findings; the whole-graph pruning policy remains unconfirmed independently.
Most removed graph edges were not assayed in this panel, so zero detected-pair
loss here does not certify all 16,352 removals as biologically safe.

## Reproducibility and publication

The source publication passed the existing packet replay on a temporary AWS CPU
worker with **64 GiB RAM**. Local attempts exposed memory pressure while several
large source and semantic graph copies coexisted. Bounded fixes index outgoing
edges once, compare the same semantic fields per assertion, checkpoint completed
source files, and release unused objects before further replay. Exact equality,
source-binding and packet checks remain in place. These engineering changes do
not alter graph content, scores or biological decisions.

- Sealed source protocol: `8242b89d0bed054d4df81e5a7590b45e82f858142ca206c7238d87c92203beec`.
- Unchanged canonical graph: `cd442cc59ac195e38dd50fcffb09263a72223236a77b67f3584a01bf92d0d370`.
- Source and numerical tables: `runs/ppi_pruning_preparation_20261111_attempt_02/`.
- Verified NE manifest and scores: `runs/ppi_pruning_20261111/aws_verified/ne_full/`.
- Completed result: `30e2d3d4a035df0d988fe16047e50d6421dfc2c43a6496ae045af31e1a409c2c`.
- Human-readable report: `runs/ppi_pruning_20261111/results/report.html`.
- Original author files, mappings, MIT license and source receipts are preserved
  in the separate reference-provenance sidecar, without changing frozen inputs.
- The frozen comparison binds its materialized graph packages, exact
  reference bytes, operating rules and implementation hashes before explicit
  consumed-outcome access. Its protocol is
  `67ea2c2e6134ea29eec06e1324762666f11c355af38c6a6ce415134a139be5b2`. The runner is
  [`assess_ppi_pruning.py`](../../scripts/assess_ppi_pruning.py).

The complete archive is `runs/ppi_pruning_20261111/ppi_pruning_results.tar.gz`
(1,891,081,545 bytes), verified after download against SHA-256
`69deca1d2e7e3fcb0793dd7d8fe8fb3ca8348aed7ee8ca4f30585e3bd19f6873`.
The temporary AWS worker was terminated after archive verification; the existing
app and Neptune database were preserved. No Brev GPU or model server was needed.

It contains exact execution code/inputs under `repo/`, all three graph packages
and results under `output/`, and the original author-provenance sidecar under
`reproducibility/`. `artifact_index.json` describes the layout. The archive also
has an encrypted, versioned copy in private project storage.

Large source records and execution receipts remain private, ignored run
artifacts. This tracked result note records the completed operations and current
assessment boundary without distributing the source inventories.

## Saved app preview

The completed comparison is available in **Compare & assess** as a separate,
read-only assessment. The November 11 delivery passed 16 focused preview tests,
11 existing exploration/workspace tests and a Chrome walkthrough covering policy
switching, the eight native detection losses, uncovered/excluded/unassessed
pairs, pagination and saved downloads. The AWS workbench serves the same preview;
authenticated checks confirmed the frozen CRC source graph and saved answer were
unchanged. No new model calls, assay scoring or graph mutations were performed.
The preview checks saved-file integrity and frozen edge commitments; it does not
repeat the full retained-graph replay or establish independent biological validity.

The subsequent [removed-pair audit](PPI_REMOVAL_AUDIT_20261111.md) accounts for
all 26,167 pairs removed by either policy and traces 20 assayed cases to their
original source rows. It finds that 99.89% of NE removals are unassessed in the
panel, and documents biochemical support for a nondetected pair removed by NE.
Those findings reinforce the task-specific interpretation and unchanged
decision against promoting either policy as biologically superior.
