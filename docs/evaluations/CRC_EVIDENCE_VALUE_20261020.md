# First CRC evidence-value pilot — October 20, 2026

This increment moves from planning reliability to actual source checking and measured-data inspection. A frozen 20-item CIViC panel was checked against its underlying publications, using deterministic graph queries and an advisory source verifier. A processed CPTAC colon-cancer matrix was also ingested as a provenance-bearing measurement sidecar.

The result demonstrates a working biological-evidence inspection workflow. **It does not establish scientific accuracy, clinical truth or improved graph prediction.** Human scientific labels remain zero; no graph assertions or review states were changed.

A [separate source-context and measured-cohort follow-up](CRC_CONTEXT_COHORT_20261020.md) now records an AI-assisted adjudication and whole-matrix identifier accounting. The first-run results below remain historical and unchanged.

## Observed source-checking results

| Inventory or outcome | First run |
|---|---:|
| Frozen source annotations | 20 |
| Retained / policy-excluded source items | 16 / 4 |
| Unique cited publications | 12 |
| Additional records sharing those publications | 8 |
| Available abstracts / usable full-text bodies | 11 / 3 publications |
| Abstract tasks / paired augmented tasks | 19 / 3 |
| Annotation with no bounded source text | 1 |
| Requested model turns / validated outputs | 22 / 22 |
| Abstract-only machine verdicts | 19 NOT_ENOUGH_INFORMATION |
| Augmented machine verdicts | 2 SUPPORT, 1 CONTRADICT |
| Question-planning calls | 0 |
| Independent-study count / scientific accuracy | Unknown / unknown |

The panel contains all 11 exact KRAS G13D profile records, including the ten cetuximab records used in the earlier source audit, followed by nine other records selected by ascending SHA-256 of source-item ID. It is a disclosed, purposive development panel. The three paired full-text tasks are not independent test sets or a calibrated comparison of scientific accuracy.

No explicit publication-ID overlap was detected between the selected annotations and either the frozen Pharos assertion citations or raw/discovery records. This is a presence audit on the bounded extract. It does not prove publication novelty, independent experiments or absence from Pharos's upstream resources. Likewise, 12 publications must not be reported as 12 independent studies.

All abstract tasks were judged insufficient for the **complete qualified annotation**, including its description, profile, treatment-list semantics, direction and material study context. This does not mean those 19 annotations are biologically false or unsupported by the complete literature. Abstract omissions, strict composite claims and verifier overconservatism are possible explanations; this CRC panel has no independent gold labels with which to separate them.

One annotation, CIViC item 1180 / PMID 26371285, had no abstract and no linked usable full text from this retrieval. It was kept as an access gap and consumed no model turn. Missing source views were not filled with demonstration data or negative labels.

## What full text changed

| CIViC item / publication | Abstract | Augmented passages | Recorded interpretation |
|---|---|---|---|
| 2943 / [PMID 20570890](https://pubmed.ncbi.nlm.nih.gov/20570890/) | Insufficient | SUPPORT | The model found passages supporting the described A146T preclinical context, with its model and experimental qualifications. This does not establish a human treatment outcome. |
| 3878 / [PMID 22722830](https://pubmed.ncbi.nlm.nih.gov/22722830/) | Insufficient | SUPPORT | The model found the engineered-cell experiment and viability-method context. The record remains excluded under its original source policy; machine support does not override that exclusion or assign local acceptance. |
| 947 / [PMID 20956938](https://pubmed.ncbi.nlm.nih.gov/20956938/) | Insufficient | CONTRADICT | The model flagged the description's unqualified monotherapy wording when applied to named wild-type controls. Its explanation also says the KRAS-mutant combination-response finding is supported. |

The item-947 flag needs source-level adjudication. The complete description mentions both mutant models and wild-type controls, while the qualified annotation targets KRAS Mutation. The model's concern about control-group wording **does not establish that the mutation-specific combination-response annotation is false**. Population and comparator scope must be resolved before using this flag to alter an assertion. The first result has been retained without relabeling or repair.

The protected report preserves every task, explanation, context mismatch, missing detail, exact quotation and paragraph/table locator. All decisive quotations passed exact-reference validation. That validation establishes fidelity to supplied text; it is not an independent entailment judgment.

## Deterministic graph comparison

Six reused development questions were executed against the frozen Pharos baseline and its CIViC-enriched copy, with identical result/path budgets. KRAS and EGFR protein-context queries returned the same source-unit IDs in both graphs. Three candidate molecular-profile/therapy questions gained answer coverage through the CIViC adapter. The locally accepted G13D question returned no evidence because no corresponding local acceptance exists.

Pharos source gaps for these molecular-profile/therapy queries describe the application's source contract and exact disease scope. They are not evidence that Pharos or its upstream literature contains no relevant biology. Coverage alone is not a scientific-improvement score. The source panel and cited assessment tasks are separately identified; they must not be mistaken for the complete set of bounded query outputs.

The offline and live-advisory runs have identical deterministic query outcomes and CPTAC context. Source-verifier outputs do not influence query selection, source filtering, graph assertions or review events.

## CPTAC measurements and overlap

The [PDC000116 study](https://pdc.cancer.gov/pdc/study/PDC000116) and [LinkedOmics CPTAC-COAD catalogue](https://www.linkedomics.org/data_download/CPTAC-COAD/) identify the processed PNNL gene-level tumor/normal log2-ratio matrix used here. The full, unchanged source matrix has:

- **6,422 gene-level rows × 96 sample columns**;
- **551,952 observed values and 64,560 explicit missing values**;
- **44 rows matching symbols in the 99-protein Pharos cohort**, comprising 43 unique symbol-to-cohort matches and one unresolved one-to-many crosswalk;
- a CUX1 row matching both `UniProtKB:P39880` and `UniProtKB:Q13948`, with both identifiers retained.

Missing values remain missing, including in descriptive medians and sample counts. A protein absent from this matrix is not a biological negative. The complete measured-gene population is retained independently of the Pharos disease-associated list; a verified whole-proteome identifier map has not yet been built.

The frozen Pharos targets already contain 297 field-level CPTAC/LinkedOmics mentions. Those mentions are not independent-evidence counts. The sidecar adds explicit sample-level measurement detail, while release-level and underlying-study overlap remain unresolved. PDC and LinkedOmics distributions of the same experiment must not be counted as independent studies. No disease-causality or treatment-response labels, new graph assertions or human decisions were generated from abundance values.

## Controls and verification

The evaluated source revision is `4b39f212f98a68094e93be55f68e3333a67f20ce`, following feature commit `ec9f54ac24a476513efa1d9cb50eb857cd9b841e`. Before any inference, a preparation metadata label was corrected to distinguish the 11-item G13D focus from the earlier 10-item cetuximab audit. Panel membership and claims were unchanged; the original unexecuted preparation remains saved.

| Control | SHA-256 |
|---|---|
| Final packet | `a60a4b01cea5dbd5c86c4bc572baa9489ab2babf1a4cb2c1c64d7d511a9ef5b2` |
| Source-value result | `7dcecc66c0a6eef83b29d93ee50c54a5db8120574f1ad9f0b9a76b4854324593` |
| Literature manifest | `b1568aeec9d0935275cbdc7820d3f5f4a66cb91cb86fdb45afe93a736a4759af` |
| CPTAC source matrix | `28907966ebe2fdd7c41b1913da1c15a15ffd7eac4f30a1f87c499a487b8454cc` |

The pre-run specification pins tasks, source manifests, prompt/schema, requested model and budgets. The source verifier requested `gpt-6-astra` through the existing signed-in Codex CLI, version `0.163.0-alpha.10.2`. Each task used one ephemeral, tool-disabled, read-only turn, with two concurrent independent tasks and a 90-second turn timeout. This is distinct from the local Nemotron question planner and uses a different prompt from the earlier SciFact evaluation. Served model identity and internal HTTP attempts are not independently exposed by the CLI.

All 22 turns completed output and quotation validation. There were no application-level model retries, repairs, fallback models or extra live preflight turns. A launcher setup error was corrected before any model invocation; its zero-request receipt and the original pre-run specification were retained. Returned usage totals were 285,624 input tokens, including 48,896 cached-input tokens, and 7,682 output tokens. Private reasoning text was not saved.

The local core suite ran 321 tests with one optional skip; 17 focused tests passed after the metadata correction. Brev's Python 3.10 ran all 321 tests with one optional skip. The app alone was rebuilt, preserving the model service and existing data. The completed report, sources and matrix were transferred to Brev with all 58 file hashes checked and source/result/trace validation rerun there without model calls. Automated browser rendering remains unverified.

Authenticated HTTP checks confirmed exact report/metrics bytes, all 22 traces and blank scientific judgments in the result ZIP, and the unchanged matrix hash in the CPTAC download. Anonymous report access was rejected. Both historical v3 and v4 planning reports remained byte-identical.

## Artifacts and next biological test

The [machine-readable record](crc_evidence_value_20261020_summary.json) contains controls, every item and machine assessment, source gaps, paired transitions, query outcomes and mapping uncertainty, without publishing raw paper quotations. See [the workflow and commands](../CRC_EVIDENCE_PILOT.md).

Full local artifacts are in `runs/crc_evidence_value_20261020/`: `final_packet/`, `literature/`, `cptac/`, `offline/` and `live/`. Brev stores them as `/data/runs/crc_evidence_packet_20261020/`, `/data/runs/crc_evidence_literature_20261020/`, `/data/runs/crc_cptac_20261020/` and `/data/runs/crc_evidence_value_20261020/`. The protected report is available at `/api/evaluation/crc_evidence_value_20261020/`; its ZIP contains all task traces and blank scientific-review records. Preserve the separate source directories for full reproduction and their source-specific rights notices.

The next biological work should adjudicate the item-947 population/comparator flag and calibrate the verifier with independently reviewed, tightly scoped claim/passage controls. Resolve the CUX1 gene-to-protein mapping policy before attaching protein-specific measurements. A subsequent graph-prediction comparison still requires a declared experimentally measured relationship task, defensible labels, a mapped comparison population and a leakage-controlled split shared by baseline and enriched graphs. This pilot must not be used to claim that those requirements are complete.
