# Held-out learned-combination follow-up

The prespecified success gate **failed**. The held-out frame has 145 pairs in 87 source groups, with 72 supported and 73 unsupported labels.

Both models fitted 373/382 eligible primary pairs. They share 141/145 eligible secondary pairs and 4 abstentions each.

| Arm | Balanced accuracy (95% interval) | Coverage | False support | False exclusion | Error precision | Error recall | Error F1 |
|---|---:|---:|---:|---:|---:|---:|---:|
| Retain all | 50.0% (50.0%–50.0%) | 100.0% | 100.0% | 0.0% | — | 0.0% | 0.0% |
| Official base | 57.9% (50.8%–65.1%) | 97.9% | 39.7% | 40.3% | 59.7% | 58.9% | 59.3% |
| Official disconfirm | 54.5% (43.3%–65.1%) | 98.6% | 41.1% | 47.2% | 55.3% | 57.5% | 56.4% |
| Metadata only | 47.0% (35.5%–58.0%) | 97.2% | 63.0% | 37.5% | 48.1% | 34.2% | 40.0% |
| Learned combination | 53.2% (43.0%–63.5%) | 97.2% | 56.2% | 31.9% | 56.6% | 41.1% | 47.6% |

| Prespecified contrast | Difference | Pointwise 95% interval |
|---|---:|---:|
| Learned combination − Official base | -4.7 pp | -13.7 pp to +3.8 pp |
| Learned combination − Official disconfirm | -1.3 pp | -10.3 pp to +7.8 pp |
| Learned combination − Metadata only | +6.2 pp | -1.6 pp to +14.7 pp |

## Interpretation and source boundaries

The primary 382 pairs were first benchmarked with sealed original predictions, then their labels were consumed for this separately preregistered training follow-up. Both fitted encoders/models and all 145 secondary predictions were sealed before secondary labels were opened.

- The prespecified learned success gate failed. The learned combination and disconfirm did not resolve the false-exclusion problem.
- The original base arm exceeded retain-all balanced accuracy on both selected references, but rejected 78/187 supported primary pairs and 29/72 supported external pairs. These error rates do not justify automatic pruning.
- These are selected human-curator sentence/claim labels, not whole-graph biological truth. Annotator expertise and independent adjudication are not assumed for all curators.
- The primary uses first qualifying correct-only labels; the secondary uses released any-incorrect-wins non-original-pair curator tags. Selection, annotator and aggregation differences remain.
- Both original judgments come from the same small language model and are correlated. The small classifier is not a global biological-confidence model.
- Zero current application assertions qualify for this evaluation-only verifier. No app graph or Pharos assertion was automatically changed.
- No refit, threshold search, prompt change or further tuning used the 145 test labels. Future tuning requires a fresh reference boundary.

The full aggregate JSON contains every arm's confusion counts and denominators. Error-tag tables are descriptive counts for the fixed base arm; secondary tag incidences overlap and are not distinct-case counts.

[Original three-arm study](../report.html) · [Aggregate JSON](aggregate.json) · [Safe protocol metadata](protocol_metadata.json)

## Evidence-input completeness correction

These results measure agreement with released curator labels under a restricted input view. Neither released benchmark JSONL contains the original Evidence metadata. However, the secondary recovery responses already contained curator-supplied Evidence objects, including raw mentions and epistemics. We used only the released sentence/source fields and missed those available objects. This is a verified integration gap; the earlier numbers are a partial-input baseline, not evidence identifying model capacity as the cause of disagreement.

INDRA curation guidance treats a hypothesis as an error unless the Statement already carries a correct hypothesis flag. Source hashes do not encode annotations or epistemics, so hash/text agreement alone cannot establish metadata equivalence. This audit has not linked an omitted field to any individual mistake or explained any false-exclusion count. Original inputs, labels, predictions and numerical results remain unchanged. A separately qualified stored-Evidence view preserves every pair and explicitly leaves unresolved source bindings unavailable.

[INDRA curation guidance](https://indra.readthedocs.io/en/latest/tutorials/html_curation.html) · [Stored curation Evidence contract](https://github.com/gyorilab/indra_db/blob/8e289277fdfd8c5816aebf72b635b33ed0acb5f0/indra_db/schemas/principal_schema.py) · [Author flat reconstruction](https://github.com/gyorilab/indra-belief-model/blob/74e0ffe9ea21f6f11e906cee89a2091f45be2f7d/scripts/external_gold_to_statements_grounded.py).
