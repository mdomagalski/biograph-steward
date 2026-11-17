# Native STRING component comparison

October 27, 2026. **Completed fixed retrospective comparison:** the native
physical overlay ranks recorded human Y2H-v1 detections better than the
functional scores, with lower numeric coverage. This is a modest, task-specific
source-component result. Independent biological validation and a contribution
specific to Steward remain unestablished.

## Result

The same **2,676 assay-eligible pairs** enter both primary arms: 376 recorded
detections and 2,300 recorded nondetections. Average precision (AP) measures
ranking of these detections; it is not the fraction of scientifically correct
assertions.

| Native STRING 12.5 view | Full-panel AP | Explicit numeric scores | Numeric coverage |
|---|---:|---:|---:|
| Functional | 0.172827 | 2,363 / 2,676 | 88.3% |
| Physical overlay | 0.190056 | 1,938 / 2,676 | 72.4% |
| Physical minus functional | **+0.017229** | −425 | −15.9 percentage points |

The predeclared secondary comparison uses the **same 1,938 jointly numeric
pairs**, including 317 detections and 1,621 nondetections. Functional AP is
0.176919 and physical-overlay AP is 0.199278: difference **+0.022359**. This
conditional result supports the ranking difference but does not replace the
full-panel result or its coverage accounting.

All 3,222 nominations and 3,173 accessions were retained. The unchanged
author-consistent eligibility rules exclude 546 tests: 27 failures, 41
autoactivators and 478 failed sequence confirmations. The two historically
Pharos-unresolved pairs remain in the eligible population. A nondetection
under these constructs and assay conditions is not a universal noninteraction.

## Missingness and source exposure

| Eligible source state | Functional | Physical overlay |
|---|---:|---:|
| Explicit numeric score | 2,363 | 1,938 |
| No functional row in a validated complete query | 306 | 306 |
| Physical annotation absent/below the requested profile | — | 425 |
| Unmapped endpoint | 7 | 7 |
| Total | 2,676 | 2,676 |

Six accessions were unmapped; seven eligible pairs contain them. No ambiguous
or collapsed mapping occurred in this capture. Provider resolution remains a
best-match locus correspondence, not proof of construct/sequence identity.
No native numeric zero occurred; the tested parser preserves zero explicitly.
Legitimate unranked states tie below all native scores at an ordinal −1 for AP.
This is a fixed retrieval-order policy, not a native confidence, biological
negative label or necessarily conservative estimate. Technical failures stop
capture and are never converted into absent evidence.

All pre-existing exposure strata are reported:

| HuRI flag | INMC flag | Eligible | Detections | Functional AP | Physical AP | Difference |
|---|---|---:|---:|---:|---:|---:|
| No | No | 2,271 | 90 | 0.053606 | 0.060373 | +0.006767 |
| No | Yes | 6 | 1 | 0.250000 | 0.250000 | 0 |
| Yes | No | 399 | 285 | 0.729056 | 0.733192 | +0.004136 |
| Yes | Yes | 0 | 0 | Unscorable | Unscorable | — |

**285 of the 376 detections have a HuRI exposure flag.** Current STRING import
and calibration lineage relative to this panel remains unresolved. An unflagged
pair is not certified independent of STRING. All outcomes were already consumed
in the earlier assessment; a new execution freeze does not make them unseen.

## Established methods and the implemented boundary

The [fixed scope](../BIOLOGICAL_COMPARISON_SCOPE.md) selected a compatible
source qualification before whole-panel access. The
[official STRING API](https://string-db.org/help/api/) supplies both scores;
the typed response contains functional-network rows with physical annotations.
This is not a demonstrated comparison of two complete native networks.
Mapping uses documented `get_string_ids` parameters with exact query echoes.
The fixed network profile is species 9606, `required_score=0`, `add_nodes=0`,
`network_type=functional`, `network_flavor=typed`, `typed_physical_edges=1`
and `typed_regulatory_edges=0`.

The [Wright interactome evaluation](https://link.springer.com/article/10.1038/s44320-024-00077-y)
informs task-specific utility and coverage controls. We use
[scikit-learn's AP implementation](https://scikit-learn.org/stable/modules/generated/sklearn.metrics.average_precision_score.html)
without fitting a predictor, modifying ties or tuning thresholds. Existing
MImerge/MIscore was checked during scope selection; insufficient cohort-level
record/method metadata prevented its justified use here. No replacement
confidence formula was invented.

The subsequent [independence review](STRING_REFERENCE_INDEPENDENCE_20261027.md)
documents known source/calibration reuse, the actual release schema and the
public-reference decision. It preserves this completed result and selects a
separate older-source temporal development control; it supplies no new score
or independence certificate for this packet.

Capture completed on its first protocol attempt: **161 logical requests,
161 HTTP attempts, all HTTP 200**, with 4,552,998 response-body bytes and no
retries. All 3,222 candidate predictions are accounted for; 3,167 accessions
resolved. Before scoring, the native capture recorded 1,905 different ranking
values and 521 different source states across the two views. The comparison
therefore has an actual input contrast. Incidental edges returned in the fixed
queries do not expand the candidate population.

No reference study body was newly opened, no outcome determined request
selection, no graph was pruned, and no model, GNN, Brev or AWS compute was used.
The four reserved IntAct study bodies remain unopened. The older GO/Reactome
results and original Lambourne inputs are unchanged.

## Verification and replay

The new adapters, capture checks and scorer pass **50 targeted tests**. The
capture replays offline; scoring reproduces the sealed metrics. An independent
arithmetic review used a standalone implementation without importing the
production parser/scorer. It reproduced raw TSV projections, exact pair and
construct joins, all exclusions/states, coverage, full/common AP and every
exposure stratum. It also verified unchanged historical outcome bytes and
capture/result inventories. This is arithmetic/source-projection review, not
an independent biological audit.

| Local artifact | Role | Raw report-file SHA-256 |
|---|---|---|
| `runs/string_component_protocol_20261027_attempt_01/protocol.json` | Frozen code, rules, population and copied reference bindings | `18ebd6c85ff6d45612daa8fa6465ccc315d50029514172826abc460d49d9cc20` |
| `runs/string_component_capture_20261027_attempt_01/report.json` | Raw TSVs, receipts, mappings, predictions and complete file inventory | `5c5f365279f67273f2b676582d24e119af131ac2196a83687fc2dcc81c1f0216` |
| `runs/string_component_result_20261027_attempt_01/report.json` | Metrics and readable report manifest | `607bb97b7a63422e73b3f4d76bce5dcf499340ab74377ec2d323b9351ba7b192` |
| `runs/string_component_arithmetic_review_20261027/report.json` | Standalone arithmetic/source-projection review | See the [tracked summary](string_component_comparison_20261027_summary.json) |

The tracked summary preserves exact values, paths, raw hashes and internal
content seals. The real-data packets are local, separately supplied artifacts;
a fresh repository clone does not contain them. The
[reproduction guide](../STRING_COMPONENT_COMPARISON.md) documents capture and
runtime requirements. Existing packets can be checked without source access:

```sh
python3 scripts/run_string_component.py verify \
  --capture runs/string_component_capture_20261027_attempt_01
runs/reactome_context_runtime_20261026/venv/bin/python \
  scripts/score_string_component.py --verify \
  --capture runs/string_component_capture_20261027_attempt_01 \
  --out runs/string_component_result_20261027_attempt_01
```

## Decision and remaining gap

Retain the physical overlay as a measured candidate for task-specific
prioritization, while preserving functional associations and explicit coverage.
The result does not justify deleting functional edges after Y2H nondetection.
There is no confidence interval or unseen-generalization claim for this selected,
shared-protein panel.

The next scientific claim needs source/reference independence checks and a
compatible confirmation reference. A later Steward-specific comparison also
needs baseline, ordinary-addition and qualified-addition arms operating on
identical information with an actual verified graph-input difference. This
completed component study does not establish either requirement, scientific
accuracy, direct binding, cancer relevance or novel information beyond Pharos.
