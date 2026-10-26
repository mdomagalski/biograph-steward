# Restricted Pharos/GO comparison: measured result

October 23, 2026. **The fixed comparison completed and the assay reference
reconciled. Adding GO hierarchy produced a negligible mean change, with mixed
direction across seeds; an incremental improvement is not demonstrated.**

This measures ranking of recorded Y2H detection among the selected INMC pairs.
It is not clinical accuracy, universal physical-interaction truth, a full-Pharos
evaluation, or the organizers' still-unavailable gold-set score.

## Result

The [prepared and frozen graphs](INMC_PAIRED_GRAPH_20261023.md) share 10,350 nodes,
99,394 supervised triples and 2,570 retained Pharos product–GO annotation pairs.
The enriched arm adds only 315 official GO `is_a` edges. All Pharos PPI records
are excluded from every learner arm. Original gene identities, coverage gaps,
reserved equivalents and development masks are unchanged.

Metrics use the same **1,751 complete-scored off-diagonal pairs** in every arm
and seed: 737 recorded detections and 1,014 nondetections. Average precision (AP)
is the primary ranking metric; it is not the fraction of assertions proven
correct. Values below are arithmetic means across seeds 17, 43 and 101.

| Fixed model/input | Mean AP | Mean ROC-AUC |
|---|---:|---:|
| ComplEx, HuRI scaffold | 0.411944 | 0.501958 |
| R-GCN, HuRI scaffold | 0.683878 | 0.799690 |
| R-GCN, scaffold + restricted Pharos context | **0.719833** | **0.817317** |
| Same R-GCN + GO hierarchy | **0.720135** | **0.818691** |

The hierarchy difference is **+0.000301 AP** (0.030 percentage points) and
**+0.001374 ROC-AUC** on average. Per-seed differences reveal the limitation:

| Seed | Baseline AP | Hierarchy AP | AP change | ROC-AUC change |
|---|---:|---:|---:|---:|
| 17 | 0.731083 | 0.726398 | −0.004686 | −0.000863 |
| 43 | 0.704732 | 0.706623 | +0.001891 | +0.002347 |
| 101 | 0.723685 | 0.727383 | +0.003699 | +0.002639 |

The restricted Pharos context arm has higher mean AP than scaffold-only R-GCN
by 0.035955, but also loses to that control at seed 17. This is a descriptive
secondary observation, not a general claim that Pharos enrichment improves
prediction. Scaffold-only R-GCN ranges from 0.640055 to 0.738595 AP across these
seeds. ComplEx is weak at this fixed budget; these results do not compare
optimally tuned model families. The primary population's positive fraction is
0.420902, included as a class-balance reference rather than a separately fitted
random model.

The predeclared leave-one-original-gene-out diagnostic does not reverse any
seed's AP-change sign: ranges are −0.007269 to −0.002351 (17), +0.000450 to
+0.003059 (43), and +0.002660 to +0.005691 (101). These are sensitivity ranges,
not confidence intervals; no model is retrained for this calculation. Shared
genes make pairs dependent. Three initialization seeds and this diagnostic do
not establish population uncertainty or statistical significance.

## Reference and coverage accounting

The untouched author `Fig.6` workbook contains 1,177 distinct positive pairs.
All **2,038** complete-scored pairs, including self-pairs, agreed with that
reference: 863 detections and 1,175 nondetections. The remaining 314 author
positives lie outside our complete-scored subset. They were not converted into
eligible outcomes. No negative labels came from the positive-list complement.

| Population | Pairs | Detected | Not detected |
|---|---:|---:|---:|
| All nominations | 3,276 | — | — |
| Primary: off-diagonal, all three assays definitive | 1,751 | 737 | 1,014 |
| Off-diagonal with a failed/unscored assay; excluded | 1,030 | — | — |
| Self-pairs, complete assays; reported separately | 287 | 126 | 161 |
| Self-pairs with a failed/unscored assay; excluded | 208 | — | — |

The primary set is 62.96% of the 2,781 off-diagonal nominations. Eligibility was
fixed before outcomes were opened. Complete-scored selection may be biased;
no random-missingness assumption is made. All code-pattern counts and raw
orientations are preserved in the local outcome artifact; there are no duplicate
panel rows. `freq` remains opaque provenance.

All candidates received finite scores in all 12 runs. Among the 1,751 primary
pairs, 498 have no endpoint with retained qualified GO context, 831 have one,
and 422 have two. Twelve primary pairs include an endpoint with zero scaffold
training degree. They remain in the denominator. Absent qualified GO context
does not mean absent Pharos data or absent biological relevance.

## What is established, and what remains unknown

The implementation can now execute a source-audited, reproducible graph
comparison against recorded experimental outcomes using existing PyKEEN and
scikit-learn components. The restricted R-GCN graphs rank this selected assay
endpoint substantially better than the weak fixed-budget ComplEx control.

The result gives no persuasive reason to promote hierarchy enrichment as a
performance improvement. It does not identify the causal reason for the small
effect. Redundant information, limited retained context, the particular
representation and training budget are hypotheses, not demonstrated failures.
We will not change settings and reuse this panel as an unseen test to chase a
larger result.

Source limitations from the [preparation report](INMC_PAIRED_GRAPH_20261023.md)
remain: Pharos and GO postdate the assays; many source references and polarity
fields are unavailable; current-GOA diagnostics do not recover historical row
identity; reviewed-product links do not establish assayed constructs; and the
method-nominated panel is selected. Direct-pair masking does not establish
complete source independence. A nondetection is specific to the recorded assays.

The next useful work is to review source coverage and existing-method fit on
development material, and carry this evidence into the challenge progress
report. Any new model/source intervention needs a separately justified protocol
and an independent reference before a new improvement claim. Additional tuning
on this panel must be labelled development. The organizer gold-set interface
remains the route to an official challenge score when its reference arrives.

## Reproduction and exposure receipt

- Prepared graph: `runs/inmc_paired_graphs_20261023/qualified_v2/`.
- Frozen comparison: `runs/inmc_paired_graphs_20261023/frozen_cpu/`; frozen
  **2026-10-23 14:54:38 UTC**, before reserved predictions or label decoding.
- Unlabelled predictions/checkpoints: `runs/inmc_comparison_20261023/cpu/`.
  All four arms × three seeds completed 20 epochs, 500 updates each, **6,000
  total updates**, in 704.72 seconds on local CPU. No Brev or language model used.
- Reference, coverage and metrics: `runs/inmc_comparison_20261023/scored/`.
  First outcome access: **2026-10-23 15:10:21 UTC**. Scoring completed at
  **15:10:34 UTC**. This panel is now consumed as an unseen holdout.
- Compact tracked result: [inmc_comparison_20261023_summary.json](inmc_comparison_20261023_summary.json).
- Commands: [scripts guide](../../scripts/README.md); direct dependencies:
  [requirements-inmc-evaluation.txt](../../requirements-inmc-evaluation.txt).

The runner used Python 3.12.4, PyKEEN 1.11.1, torch 2.6.0, NumPy 2.5.4,
SciPy 1.18.1 and scikit-learn 1.9.1. Native openpyxl 3.1.5/et_xmlfile 2.0.0
were supplied from a separate temporary dependency directory for workbook
parsing; the trained runtime was not modified. Prediction, source, scorer,
protocol and output hashes are recorded. Earlier preparation/smoke attempts
and the source files remain unchanged.

Validation: the application suite passed 450 tests with 17 optional dependency
skips. The pinned optional environment also passed 13 graph-projection,
three hierarchy, 14 outcome/metric and 16 scoring-gate tests; the runner's
17 synthetic tests and nine freeze tests passed during implementation.
Independent reviews covered graph identity/qualifier semantics, freeze gates
and scoring/exposure boundaries. Initial application HTTP failures were caused
by localhost requests entering the environment proxy; the documented Python
`no_proxy` setting resolved them without changing application code.
