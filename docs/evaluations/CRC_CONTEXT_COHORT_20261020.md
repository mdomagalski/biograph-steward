# CRC context adjudication and measured cohort mapping — October 20, 2026

This follow-up preserves the [first source-value pilot](CRC_EVIDENCE_VALUE_20261020.md) and records two separate outputs: an AI-assisted inspection of CIViC item 947's context and a complete row-accounting crosswalk for the processed CPTAC matrix. It makes no new source-verifier calls and creates no scientific gold labels or graph assertions.

## Source-context adjudication

[Dunn et al., PMID 20956938](https://pubmed.ncbi.nlm.nih.gov/20956938/) supports the cetuximab/dasatinib combination response in the tested KRAS-mutant LS180, LoVo and HCT116 preclinical models. Wild-type SW48 and CaCo2 responded to cetuximab alone. That control result does not refute the scoped mutant finding, but the annotation's wording can misleadingly pool all five lines under a combination-only conclusion.

The proposed local summary separates mutant experiments from wild-type controls. It retains mild monotherapy effects, PDL/laminin-dependent culture results, the more modest HCT116 response and the preclinical boundary. Clinical benefit and the full annotation's somatic-origin qualification are not independently established here. No formal synergy analysis is claimed.

The [AI-authored decision](crc_947_context_decision_20261020.json) has six scoped findings and exact source-text hash references. Fourteen relevant cached results/discussion/methods/caption blocks were inspected out of 42 available abstract/body/caption blocks, including 35 cached body blocks. Figure images, supplements and raw data were not independently analyzed. This is not an exhaustive review or an independent expert judgment. The original augmented `CONTRADICT` and abstract `NOT_ENOUGH_INFORMATION` verdicts and their traces remain intact, alongside the new scope-warning overlay. The original CIViC source text and graph state are unchanged.

## Measured cohort

The unchanged PDC000116/LinkedOmics processed matrix contains **6,422 gene rows × 96 sample columns**, with **551,952 observed values and 64,560 missing values**. No zero filling, row aggregation or disease-label selection was performed. Registry sources are the HGNC complete set retrieved October 20 (Last-Modified October 16, 2026; 45,277 records) and UniProt reviewed human release **2026_03**, dated September 2, 2026 (20,431 entries).

| Mapping outcome | Rows |
|---|---:|
| Exact approved HGNC symbol | 6,176 |
| One gene through exact registry previous/alias/UniProt names | 239 |
| Ambiguous registry names, retained outside the usable cohort | 7 |
| Uniquely identified gene cohort | 6,415 |
| Identified genes with confirmed reviewed protein context | 6,399 |
| Identified genes with multiple candidate products | 19 |

The 16 identified rows without confirmed reviewed products are readthrough records. All seven ambiguity sets remain visible:

| Reported symbol | Approved gene candidates |
|---|---|
| AIM1 | AURKB, CRYBG1, SLC45A2 |
| HIST2H2AA4 | H2AC18, H2AC19 |
| HN1L | CRAMP1, JPT2 |
| MPP6 | MPHOSPH6, PALS2 |
| QARS | EPRS1, QARS1 |
| SARS | SARS1, SARS2 |
| SEPT2 | SEPTIN2, SEPTIN6 |

Resolving these requires original assay identifiers, protein groups or peptide evidence; choosing the most familiar symbol is not verification. The crosswalk is complete as an accounting of all measured rows, not a claim of 100% unique resolution.

**CUX1 is resolved at gene level:** HGNC:2557 / NCBI Gene 1523 links to both reviewed human [P39880](https://www.uniprot.org/uniprotkb/P39880/entry) and [Q13948](https://www.uniprot.org/uniprotkb/Q13948/entry). Both links remain; the one source measurement is not assigned separately to either product. All **44 previously symbol-matched measured rows now have unique gene identities**, linking to **45 Pharos protein entries**. This improves identity/granularity accounting, without adding new measured coverage of the 99-protein Pharos subset. The other Pharos proteins have no unambiguous measured-gene match in this matrix, not negative biological labels.

## Artifacts and verification

Workflow and reproduction commands: [measured cohort mapping](../COHORT_MAPPING.md). Local outputs are under `runs/crc_adjudication_mapping_20261020/`: `registry/`, `published_cohort/` and `context_adjudication/`. Earlier preparation outputs remain separate and were not published as the final result. The [compact machine-readable record](crc_context_cohort_20261020_summary.json) binds the final artifacts to the first pilot and source registry identities.

The mapping ZIP contains all matrix rows, all gene/product candidates, frozen registry TSVs and receipts, cohort IDs, the original matrix and the bounded Pharos identifier list. The adjudication ZIP contains original item/assessments/traces, the AI decision and source-bound text references. Verification replays identifier joins from frozen inputs and confirms historical pilot hashes without rewriting the historical engine identity. Test fixtures are invented software cases, never scientific gold.

Implementation commit: `e0310380a1d615aafdb00b41b588257d3384c0c8`. Both the local Python 3.14 suite and the Brev Python 3.12 app-image suite ran **333 tests with one optional integration skipped**, with no failures. The initial local attempt encountered an existing loopback integration test through Squid; the explicit loopback proxy bypass passed. Source-rights provenance was then added and the final complete local suite passed again.

Brev received 20 files in two separate immutable report roots. The app-only rebuild is healthy; no new verifier requests or GPU model changes were made. Mapping reproduction and all artifact hashes passed inside the container. Protected HTTP checks matched report/metrics and every ZIP member to the local bytes; anonymous report/ZIP access was rejected. The original evidence pilot and both historical planning reports were byte-identical. Browser rendering was not independently verified.

With the existing SSH tunnel active, open these protected reports in Chrome:

- [Context adjudication](http://127.0.0.1:8767/api/evaluation/crc_context_adjudication_20261020/)
- [Complete measured cohort crosswalk](http://127.0.0.1:8767/api/evaluation/crc_cohort_mapping_20261020/)
- [Cohort export, including matrix and registry inputs](http://127.0.0.1:8767/api/download/crc_cohort_mapping_20261020)

Independent scientific labels remain **zero**, scientific accuracy remains **null**, and graph improvement remains **unestablished**. A prediction experiment still needs a defined biological endpoint, defensible labels, target-appropriate baseline features and source/study leakage controls. This increment supplies the measured identifier population and a traceable context correction proposal; abundance alone does not establish causal disease or drug-response truth.
