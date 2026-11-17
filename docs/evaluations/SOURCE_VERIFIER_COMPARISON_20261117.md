# Source-verifier comparison

The separate [corrected Evidence-input diagnostic](source_verifier_20261117/corrected_input/report.html) restores available stored curator Evidence and compares Nemotron with Qwen. Across all 145 pairs, Qwen with curated Evidence reaches 68.1% balanced accuracy versus 56.5% for Nemotron on that view, a difference of +11.6 percentage points (pointwise 95% interval +2.3 to +20.7). However, it rejects 36/72 curator-supported claims versus 31/72, so the prespecified practical-improvement gate fails. Qwen with the original restricted input reaches 74.4%; all four arms, their coverage, paired contrasts and the fixed 137-pair common-mask analysis remain visible. This consumed-reference diagnostic does not justify automatic Pharos pruning or establish an isolated benefit from restoring metadata. [Aggregate and source/protocol pins](source_verifier_20261117/corrected_input/aggregate.json).

A descriptive [component audit](source_verifier_20261117/corrected_input/component_audit.json) traces six of the 36 full-input Qwen supported-claim rejections to author-native prechecks before inference. It preserves every pair and the failed gate. The documented context-disambiguation API was checked, but the installed model bank has no applicable model for those trigger strings; no further predictions or ablations were run.

The original frozen base/disconfirm comparison is preserved below.

Prespecified hypothesis, not the result: official disconfirm would improve explicit-decision balanced accuracy over official base on the primary frame, with the same contrast assessed separately on the external-curator frame.

The prespecified disconfirm improvement hypothesis was not supported. On the primary reference, balanced accuracy was 56.6% versus 62.2% for base, a difference of -5.6 percentage points (95% interval -10.6 to -0.5). On the external-curator reference, the corresponding results were 54.5% versus 57.9%, a difference of -3.5 points (-12.8 to +5.5). Base exceeded the retain-all control on both selected references, while wrongly rejecting 78/187 and 29/72 supported pairs. These adverse exclusions preclude adopting automatic pruning from this assessment.

## Primary reference

382 pairs in 382 connected source groups: 187 supported and 195 unsupported under the released curator rule.

| Method | Balanced accuracy (95% interval) | Coverage | False support | False exclusion | Error precision | Error recall | Error F1 |
|---|---:|---:|---:|---:|---:|---:|---:|
| Retain all | 50.0% (50.0%–50.0%) | 100.0% | 100.0% | 0.0% | — | 0.0% | 0.0% |
| Official base | 62.2% (57.3%–67.0%) | 99.2% | 32.3% | 41.7% | 62.7% | 67.2% | 64.9% |
| Official disconfirm | 56.6% (52.3%–61.0%) | 97.9% | 17.4% | 65.2% | 56.0% | 79.5% | 65.7% |

All class denominators include abstentions. An undefined precision is shown as —.

| Prespecified contrast | Difference | Pointwise 95% interval |
|---|---:|---:|
| Official disconfirm − Official base | -5.6 pp | -10.6 pp to -0.5 pp |
| Official disconfirm − Retain all | +6.6 pp | +2.3 pp to +11.0 pp |
| Official base − Retain all | +12.2 pp | +7.3 pp to +17.0 pp |

Agreement-only review flags: 188 pairs, including 119 curator-unsupported pairs and 69 supported pairs. Flag precision: 63.3%. Retained label precision: 60.8%, versus 49.0% for retaining all. Unflagged pairs remain unassessed.

## External-curator reference

145 pairs in 87 connected source groups: 72 supported and 73 unsupported under the released curator rule.

| Method | Balanced accuracy (95% interval) | Coverage | False support | False exclusion | Error precision | Error recall | Error F1 |
|---|---:|---:|---:|---:|---:|---:|---:|
| Retain all | 50.0% (50.0%–50.0%) | 100.0% | 100.0% | 0.0% | — | 0.0% | 0.0% |
| Official base | 57.9% (50.8%–65.1%) | 97.9% | 39.7% | 40.3% | 59.7% | 58.9% | 59.3% |
| Official disconfirm | 54.5% (43.3%–65.1%) | 98.6% | 41.1% | 47.2% | 55.3% | 57.5% | 56.4% |

All class denominators include abstentions. An undefined precision is shown as —.

| Prespecified contrast | Difference | Pointwise 95% interval |
|---|---:|---:|
| Official disconfirm − Official base | -3.5 pp | -12.8 pp to +5.5 pp |
| Official disconfirm − Retain all | +4.5 pp | -6.7 pp to +15.1 pp |
| Official base − Retain all | +7.9 pp | +0.8 pp to +15.1 pp |

Agreement-only review flags: 54 pairs, including 32 curator-unsupported pairs and 22 supported pairs. Flag precision: 59.3%. Retained label precision: 54.9%, versus 49.7% for retaining all. Unflagged pairs remain unassessed.

## Interpretation and reproducibility

- This is an evaluation-only comparison, not a deployed app feature. Zero current application source assertions have qualified native inputs for this verifier; it does not automatically prune Pharos or change the application graph.
- The primary reference is a selected completed curation snapshot with unproven sampling randomness. The external source forced class balance. Neither estimates population prevalence or whole-graph biological accuracy.
- The two frames use different released label policies and are reported separately. Human annotators are not all assumed to be independently adjudicated experts.
- The native claim preserves available conditions, sites and all complex members. The primary released input lacks original Evidence metadata. Secondary stored curation payloads already contained annotations, epistemics and raw mentions, but the original runtime view omitted them. Those earlier scores use the same restricted sentence/source fields for both arms; a separate full-Evidence view handles available metadata with explicit binding guards.
- Prior project source/publication/claim/native-family exposure and the author example universe were screened where identifiers were available. Unknown model pretraining and exhaustive biological-family independence are not established.
- The same language model supplies both judgments. Agreement-only flags are conservative review proposals, not independent evidence or automatic biological pruning.
- The 2026 author method/reference artifacts are public releases, not a newly verified peer-reviewed method paper. The task builds on published INDRA source curation and the 2023 assembly work.

The full aggregate JSON preserves all three arms, confusion counts, denominators, uncertainty and source/method hashes. Both frames and every completed prediction envelope were sealed before labels were accessed. No prompt, threshold or calibration was fitted to these outcomes.

To reproduce: retrieve the pinned author source and reference versions, apply the recorded source/exposure admission rules, run the frozen base/disconfirm profiles on the same native claim and released evidence fields, then use the frozen scorer. Access to original data remains subject to its source terms. Individual cases and passages are not redistributed here.

[Author implementation](https://github.com/gyorilab/indra-belief-model/tree/74e0ffe9ea21f6f11e906cee89a2091f45be2f7d) · [Reference descriptions](https://github.com/gyorilab/indra-belief-model/blob/74e0ffe9ea21f6f11e906cee89a2091f45be2f7d/data/benchmark/README.md) · [INDRA curation guidelines](https://indra.readthedocs.io/en/latest/tutorials/html_curation.html) · [INDRA 2023](https://doi.org/10.15252/msb.202211325)

## Subsequent use of the primary reference

After all original predictions were sealed, the primary 382 labels were used to train a separately preregistered learned-combination follow-up. The primary frame is therefore training data for that follow-up. Its two fitted models and all 145 secondary predictions were sealed before secondary labels were opened. The original base/disconfirm comparison and its prespecified metrics remained unchanged.

## Learned combination follow-up

A separately preregistered classifier fitted 373 of the 382 primary pairs and was evaluated on all 145 external pairs in 87 source groups. Both trained arms shared 141 eligible pairs and four abstentions. The learned combination reached 53.19% balanced accuracy, compared with 57.92% for base, 54.46% for disconfirm, and 46.98% for metadata-only. Its three prespecified paired intervals all included zero, so the improvement gate failed. The primary labels were used for training only after the original predictions were sealed. Secondary labels stayed closed until both trained models and every secondary prediction were sealed. No refitting used the test labels.

[Full five-arm results and error-tag counts](source_verifier_20261117/learned_followup/report.html) · [Aggregate JSON](source_verifier_20261117/learned_followup/aggregate.json).

## Evidence-input completeness correction

These results measure agreement with released curator labels under a restricted input view. Neither released benchmark JSONL contains the original Evidence metadata. However, the secondary recovery responses already contained curator-supplied Evidence objects, including raw mentions and epistemics. We used only the released sentence/source fields and missed those available objects. This is a verified integration gap; the earlier numbers are a partial-input baseline, not evidence identifying model capacity as the cause of disagreement.

INDRA curation guidance treats a hypothesis as an error unless the Statement already carries a correct hypothesis flag. Source hashes do not encode annotations or epistemics, so hash/text agreement alone cannot establish metadata equivalence. This audit has not linked an omitted field to any individual mistake or explained any false-exclusion count. Original inputs, labels, predictions and numerical results remain unchanged. A separately qualified stored-Evidence view preserves every pair and explicitly leaves unresolved source bindings unavailable.

[INDRA curation guidance](https://indra.readthedocs.io/en/latest/tutorials/html_curation.html) · [Stored curation Evidence contract](https://github.com/gyorilab/indra_db/blob/8e289277fdfd8c5816aebf72b635b33ed0acb5f0/indra_db/schemas/principal_schema.py) · [Author flat reconstruction](https://github.com/gyorilab/indra-belief-model/blob/74e0ffe9ea21f6f11e906cee89a2091f45be2f7d/scripts/external_gold_to_statements_grounded.py).
