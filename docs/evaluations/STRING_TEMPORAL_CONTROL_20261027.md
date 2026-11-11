# Archived STRING temporal control: completed

October 27, 2026. **The physical-ranking advantage also occurs in the archived
12.0 source.** On the same 2,676 measured human Y2H-v1 pairs, functional AP is
0.149732 and physical AP is 0.161223, a difference of **+0.011491**. Physical
numeric coverage is lower. This closes the one selected temporal control;
no further version, threshold or model sweep is selected.

This is a modest retrospective source-component ranking result. The panel was
already consumed, earlier HuRI/shared evidence remains possible, and no Steward
graph intervention was tested. It is not unseen independent confirmation or a
measurement of universal scientific accuracy.

## Fixed comparison and result

Both primary arms use all **2,676 eligible pairs**: 376 recorded detections and
2,300 recorded nondetections. All 3,222 nominations / 3,173 accessions remain
accounted for. The unchanged author-consistent rules exclude 27 failed tests,
41 autoactivators and 478 failed sequence confirmations. The two historically
Pharos-unresolved pairs remain eligible for this native-source comparison.

| Native STRING 12.0 network | Full-panel average precision | Numeric pairs | Numeric coverage |
|---|---:|---:|---:|
| Functional | 0.149732 | 2,499 / 2,676 | 93.4% |
| Physical | **0.161223** | 2,013 / 2,676 | 75.2% |
| Physical minus functional | **+0.011491** | −486 | −18.2 percentage points |

AP measures ranking of recorded assay detections, not the fraction of correct
biological assertions. The predeclared jointly numeric comparison uses the
same **2,013 pairs** for both 12.0 views: 317 detections and 1,696 nondetections.
AP is **0.150794 versus 0.165078**, difference **+0.014284**. This is a
release-specific conditional population, not the 1,938-pair 12.5 subset, and
does not replace the full-panel denominator.

| Eligible source state | Functional | Physical |
|---|---:|---:|
| Explicit numeric score | 2,499 | 2,013 |
| No native row in its validated query response | 170 | 656 |
| Unmapped endpoint | 7 | 7 |
| Total | 2,676 | 2,676 |

Six accessions were unmapped; no ambiguous/collapsed mapping occurred. Each
view's absence is preserved independently. No physical-only row occurred in
this capture, but the adapter and tests permit it rather than assuming a subset
relationship. No native numeric zero occurred; its preservation is tested.
Legitimate unranked states tie below native scores at an ordinal −1. This is
the fixed retrieval-ranking rule, not an inferred native confidence or negative
biological assertion. Technical failures never become absent evidence.

## Exposure accounting

| HuRI flag | INMC flag | Eligible | Detections | Functional AP | Physical AP | Difference |
|---|---|---:|---:|---:|---:|---:|
| No | No | 2,271 | 90 | 0.044879 | 0.051293 | +0.006414 |
| No | Yes | 6 | 1 | 0.250000 | 0.250000 | 0 |
| Yes | No | 399 | 285 | 0.711896 | 0.715284 | +0.003388 |
| Yes | Yes | 0 | 0 | Unscorable | Unscorable | — |

The original flags and identities are unchanged. **285/376 detections have a
HuRI overlap flag.** The unflagged stratum is not a certified independent test
set, and pair mappings do not establish construct/isoform equivalence. All
strata are reported; none was selected after scoring as the primary reference.

## Literature and existing capabilities used

The [STRING 12.0 primary paper](https://pmc.ncbi.nlm.nih.gov/articles/PMC9825434/)
distinguishes locus representatives, functional associations and separately
computed physical/co-complex scores. Physical proximity is not guaranteed
direct binding. Those semantics support a task-specific comparison, while
preserving functional associations and assay context.

The [official version history](https://string-db.org/cgi/access) dates 12.0 to
July 26, 2023; the [release documentation](https://string-db.org/help/scores/)
states that networks remain fixed within a release. The
[Lambourne methods](https://www.nature.com/articles/s41467-026-70942-x) describe
panel selection from 2024 predictions. This is the basis for the earlier-source
control. It does not certify every underlying source cutoff, novel pairs or
complete training independence.

We use the [official archived API](https://version-12-0.string-db.org/help/api/)
with separate native network calls, documented best-match mapping, species 9606,
`required_score=0` and `add_nodes=0`. The 13-column format is validated explicitly.
The established exact reference/construct joins and scikit-learn 1.9.1 AP are
reused. No new confidence formula, assay label protocol, negative-sampling rule,
predictor or model prompt was introduced. No new resource was added to the
product graph. The
[pre-execution rules and replay guide](../STRING_TEMPORAL_CONTROL.md) document
the finite adaptation and scope.

The prior [12.5 component result](STRING_COMPONENT_COMPARISON_20261027.md)
remains AP 0.172827 versus 0.190056. The direction agrees, but the newer result
uses a typed physical overlay whereas this control queries separate native
networks. Release changes also alter data and scoring methods. The difference
between releases cannot isolate study ingestion or a Steward improvement.

## Capture, checks and artifacts

The first frozen protocol completed **291 logical requests / 291 HTTP
attempts**, all successful, with **3,172,718 response-body bytes** and no retries.
All 3,222 predictions are preserved; 3,167 accessions resolved. Captured inputs
were sealed before metric computation. Across all nominations, 2,574 ranking
values and 618 source states differ between views; the comparison is not an
input no-op.

**51 targeted tests passed**: 21 native-adapter tests, 12 independent capture
tests and 18 scoring tests. Capture/scoring replay passed. A standalone review,
written before inspecting the result and importing no production app code,
independently reconstructed mappings and both networks from raw TSVs. It
reproduced every prediction, exact source/construct join, exclusion/state count,
full/common AP, all four exposure strata and ranking fingerprints. Original
12.5 packets, historical outcomes and frozen implementation hashes remained
unchanged. This is source-projection/arithmetic verification, not a human
biological audit.

| Artifact | Raw report-file SHA-256 |
|---|---|
| `runs/string_temporal_protocol_20261027_attempt_01/protocol.json` | `393c2ee5410b229e8a50715c31fee5765d152dd1ce92d57b938533915239758b` |
| `runs/string_temporal_capture_20261027_attempt_01/report.json` | `584811e1baaa3acb60c0cfd1e9acccccb9416c565458e668979277d3cbdd0e02` |
| `runs/string_temporal_result_20261027_attempt_01/report.json` | `844458e9b2f7a90504c5f3be107548aa3ed8a3fdba4fe9d0b20421eb4c640d2b` |
| `runs/string_temporal_arithmetic_review_20261027/report.json` | `c8c9dce59a3aaed7139ce1c65314ced1ce3b827beecc25412502a135fab58c78` |

The [tracked summary](string_temporal_control_20261027_summary.json) contains
exact metrics, source states, paths, hashes and content seals. The readable
local result is `runs/string_temporal_result_20261027_attempt_01/report.html`.
Real source packets are supplied separately and are not bundled in a fresh
code clone. Replay commands are in the linked guide.

## Decision

Close this temporal control. The matching direction supports retaining native
physical scores as a question-specific prioritization candidate for physical
association exploration, with visible numeric coverage and the original source
context. Preserve functional relationships; Y2H nondetection does not justify
deleting them. A future product integration should expose this distinction
without presenting the physical view as universally more correct.

The remaining stronger evaluation is a verified same-information graph
intervention with a suitable separate reference. This control does not supply
that intervention or an independent gold set. No additional version/threshold
sweep, learner run or new data-source expansion follows from this result.
The four reserved IntAct study bodies remain unopened. Brev/AWS, a language
model and app navigation changes were unnecessary for this increment.
