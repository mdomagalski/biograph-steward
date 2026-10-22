# Study and treatment context display — v0.6.2

**October 21 follow-up:** the [ten-record source-to-answer trace](EXPERIMENT_HISTORY.md#reopening-an-archived-file "Archive file: docs/evaluations/CIVIC_ANSWER_TRACE_20261021.md") found intact source descriptions and an export disclosure gap. Current guided/planned answers, text/HTML exports and evaluation reports now state how many eligible assertions and profiles are omitted by display limits. New answers carry `display_coverage`; current renderers derive the same notice for older answer JSON. Scientific content and local acceptance are unchanged. The v0.6.2 verification below remains a historical result.

CIViC summaries now show each underlying source item separately alongside the claim. Previously a summary could combine levels B and D and leave its study descriptions inside the evidence passport. The new display lists the evidence ID, original level, level label and cited study title, with an expandable source description and direct CIViC/PubMed links. The planner's answer and the guided answer use the same context display.

Level labels follow [CIViC's definitions](https://docs.civicdb.org/en/latest/model/evidence/level.html). They remain source categories. A level does not supply a trial design, experimental species, assay, treatment regimen or a new local scientific approval. These details are not extracted from prose in this increment. Original descriptions and therapy lists remain unchanged.

A single drug listed in CIViC is explicitly distinguished from confirmed monotherapy. Combination, substitute and sequential sets retain their source semantics; sequence order remains unspecified. The display does not add chemotherapy ingredients found in descriptions to the structured therapy list. An ingredient filter still cannot answer monotherapy-only questions.

The displayed-source count and shared references make repeated citations visible without claiming independent experiments. Non-PubMed sources retain their CIViC source identities; missing source identity remains unresolved and is not merged with other missing references. Counts cover displayed items, so changing the display cap can change these counts. Empty accepted views still contain no candidate evidence and explicitly avoid implying biological absence.

## Saved example

Open `http://127.0.0.1:8766/?run=crc_civic_final_20261015&question=civic_g13d_context_20261015` while the local app is running. The G13D/cetuximab candidate answer retains the existing three-assertion display budget. Its six source items cite five distinct sources; items 145 and 306 share PMID 20978259 while retaining their individual D/B levels. The descriptions remain as reported and require source-paper review.

The answer ZIP now includes `evidence_context.tsv`, one row per displayed citation/source item, in addition to `question.json`, `summary.txt`, `paths.tsv` and the HTML report. Context rows retain source descriptions, evidence IDs, direction/significance, complete therapy labels, raw-snapshot locators and source snapshot hashes. Context is included in text, HTML and evaluation reports. Saved answers from earlier versions remain historical; rerun their question to obtain the added context.

**October 22 export follow-up:** newly written `evidence_context.tsv` files are self-contained. Each row also includes the complete molecular-profile ID, name, raw logical expression and variant list; the CIViC disease name and DOID; separate `local_review_state` and editorial `source_status`; and the full therapy-set ID, names, stable CIViC therapy IDs and raw member records (including any supplied NCI IDs). The interaction type and its interpretation note remain attached to the complete set even when the question filters on one ingredient. Missing structured metadata stays empty; study design, monotherapy and sequence order are not inferred.

Rows additionally retain the assertion revision, evidence edge ID, CIViC evidence/source links and identities, source citation, retrieval provenance, source-run ID and answer/graph-basis hashes. List/object cells use JSON inside the TSV, following the existing export writer. The disease is the source assertion's disease, not the selected Pharos disease. Fields come from the saved answer and its source records; exporting does not change its content hash, review decisions or claims. Existing saved exports are not rewritten. Save a fresh answer to receive the expanded columns.

## Verification

The 24 prior live plans were replayed without new model calls through the same frozen source bytes. The new suite is `runs/evaluation_suite_context_20261015/` and the result is `runs/evaluation_context_replay_20261015/`. Its trace is explicitly `recorded_replay`, with a provenance file linking the original live evaluation. The previous live suite/result and three-case human worksheet packet remain unchanged.

All 72 workflow observations retain the previous statuses, returned source units, claim text and graph/review basis. The new context does not change normalized assertions, assertion IDs/revisions, review states, selection, filtering or planner scope. Scientific judgments remain pending. This is evidence-preservation verification, not a measured improvement in scientific accuracy or reviewer usability.

All **187 tests pass**. Checks cover mixed clinical/preclinical categories, shared-source accounting, complete therapy sets, unknown levels, non-PubMed sources, text/HTML/TSV preservation and HTML escaping. Browser checks exercise the saved answer, source-description expansion and download export. The local answer ZIP was checked for six context rows, separate B/D levels and the original mixed-treatment description.
