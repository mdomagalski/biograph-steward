# INMC input readiness

**Current status — November 13:** this is the preserved first input-readiness
audit. The [restricted Pharos/GO comparison](INMC_COMPARISON_20261023.md)
subsequently completed, reconciled the author reference and consumed the panel.
The later [Reactome comparison](REACTOME_CONTEXT_COMPARISON_20261026.md) is
also completed development reuse. The unopened and pending statements below
describe this original checkpoint, not a fresh reference or current blocker.

Date: October 22, 2026. **Identifier and existing-source audits completed; assay-label contract and full-panel Pharos baseline remain pending.** No biomedical model was run.

**Subsequent follow-up:** the [assay and identity review](INMC_READINESS_FOLLOWUP_20261022.md) declares a narrower complete-scored assay task and separates shared products from missing context. The updated inventory contains 1,797 accessions linked to 1,800 original genes. The dated counts and gaps below describe the first audit; its saved receipt remains unchanged.

This follows the [dataset/learner reuse decision](../literature/MEASURED_LINK_BENCHMARK_REUSE_20261022.md). The [machine-readable receipt](inmc_input_readiness_20261022_summary.json) records source hashes, counts, exposure and remaining gates. Local raw artifacts are under `runs/inmc_readiness_20261022/` and `runs/link_prediction_reuse_audit_20261022/`.

## What the released inputs support

The file named `PPI_prediction_validation_result_20210624.xls` is actually a tab-separated text file. Its six fields are `source`, `target`, `freq`, and three assay-score fields. Standard text parsing is sufficient; no Excel conversion or new spreadsheet dependency was needed.

| Input check | Result |
|---|---:|
| Unique unordered candidate pairs | 3,276 |
| Self-pairs, kept separate | 495 |
| Off-diagonal candidate pairs | 2,781 |
| Distinct candidate gene identifiers | 1,805 |
| Released HuRI training edges / genes | 52,548 / 8,272 |
| Candidate genes present in that training network | 1,805 |
| Candidate pairs already present in that training network | 0 |

These are identity/scaffold counts, **not positive/negative label counts**. The source identifiers are Ensembl genes. Their connection to current protein context does not recover the specific ORF or isoform assayed in Y2H. Keep the benchmark's original identities and the context mappings distinct. [Ensembl stable identifiers](https://mart.ensembl.org/info/genome/stable_ids/index.html).

## Mapping: reuse the existing registry, preserve disagreements

The audit reuses `load_registry()` and `Registry.products()` from the existing [cohort mapper](../../biograph_steward/cohort_mapping.py), with an exact index over approved HGNC `ensembl_gene_id` values. The symbol resolver is not used on Ensembl identifiers. No fuzzy matches, arbitrary protein choice or automatic replacement was introduced.

| Frozen-registry result | Count |
|---|---:|
| Unique approved HGNC matches | 1,801 |
| Unresolved Ensembl identifiers | 4 |
| Single confirmed, unshared reviewed UniProt product | 1,777 |
| Multiple confirmed products | 4 |
| Mapped genes without such a product | 20 |
| Off-diagonal pairs with both exact gene mappings | 2,771 |
| Off-diagonal pairs with single unshared products at both ends | 2,753 |

These are feasibility strata, not a selected evaluation cohort. The four unresolved genes are additional to the 20 mapped genes without confirmed products.

For the unresolved IDs, we checked the official [Ensembl archive API](https://rest.ensembl.org/documentation/info/archive_id_get) and [external-reference API](https://rest.ensembl.org/documentation/info/xref_id). The archive response marks `ENSG00000184258` as non-current, last seen at release 99, with no suggested replacement. The other three are current at release 116. A missing HGNC index match therefore does not imply that a gene is obsolete.

One current identifier, `ENSG00000268500`, links from Ensembl to HGNC:10874/SIGLEC5, while the frozen HGNC record declares `ENSG00000105501`. The other two current identifiers return no HGNC reference. Temporary service errors and subsequent successful retries were recorded separately from empty results. These observations do not establish which representation should replace the source identifier; the frozen mapping counts remain unchanged. Retain the source discrepancy until its construct/locus history is understood.

## Assay interpretation: a verified documentation gap

The three assay fields use `Positive`, `Negative`, `Auto-activator`, `Not tested` and `Not scored`. `freq` uses `1`, `2` and `NULL`. Vocabulary inspection exposes no association between a candidate pair and its outcomes.

The main paper accepts detection in at least one complementary assay as positive. Its prose qualifies negative calls by successful testing, whereas Figure 5 describes all-three negativity. Autoactivation denotes an interfering control result; not-tested cases include failed experimental procedures. We found no definition for `Not scored` or `freq` in the checked methods. The supplementary precision calculation excludes unsuccessful tests. [Primary paper](https://doi.org/10.1038/s41467-023-37079-7); [official supplementary files](https://www.ebi.ac.uk/europepmc/webservices/rest/PMC10033937/supplementaryFiles).

The 45-page supplementary information and archived method code were checked. No released validation adjudicator was found. The newer repository's AUROC/AUPRC demo creates synthetic labels and scores; it does not specify how to combine these three assay columns. The experimental README is effectively empty. These are gaps in exact benchmark reuse, not evidence that the study's biological findings are wrong. [Official repository](https://github.com/spxuw/PPI-Prediction-Project); [frozen release](https://zenodo.org/records/7681817).

The official Source Data workbook supplies a stronger **positive** reference: `Fig.6` contains a two-column `source,target` table with 1,177 data rows, corresponding to the paper's positive-pair description. Those pair records remain unopened. `Fig.5` contains only per-method aggregate counts. Structure/header inspection of the 13 sheets found no negative-pair table, codebook or explanatory notes resolving partial failures. Preserve this author-generated positive list for controlled reconciliation; do not infer negatives as its complement. The workbook is `41467_2023_37079_MOESM4_ESM.xlsx`, SHA-256 `ddd4428ceb28f224802217509a740f86c824631623c9f805bf212904987d2b21`, saved unchanged under the local audit's `author_sources/` directory. [Official supplementary download](https://www.ebi.ac.uk/europepmc/webservices/rest/PMC10033937/supplementaryFiles).

**No binary outcomes have been materialized.** Neither missing, unscored nor interfering assays are converted to negatives. A future restriction to explicitly unambiguous assay patterns would be a declared adaptation with its own population and coverage report, not an exact reproduction of the authors' full panel. The decision must precede outcome-driven selection or model results.

## Existing Pharos context is insufficient and contains target-pair exposure

The checked `pharos319` snapshot is the old 512-target CRC pull. It includes only **43 of the 1,805 panel genes as directly retrieved seed targets**. Only three off-diagonal pairs have both single mapped products among those seeds. Incidental PPI neighbors cover more identifiers but do not provide consistent target-level context.

| PPI inspection | Retained graph views | Raw source-response views |
|---|---:|---:|
| Directed views inspected | 3,950 | 81,787 |
| Unique protein pairs | 1,975 | 79,812 |
| Direct candidate-pair overlap | 0 | 2 |
| Panel genes reached as endpoints | 39 | 1,337 |

The two raw overlaps carry `BioPlex,STRINGDB` and `Reactome,STRINGDB` source bundles. We did not inspect their assay labels, and do not assert that they reproduce positive outcomes or derive from the validation paper. They establish that candidate-pair information is already available in current context. Zero overlap in the retained graph is not evidence of source independence; the old scope discarded relevant raw neighbors.

STRING explicitly integrates HuRI in its experimental channel, and the HuRI paper identifies an IntAct deposition. Thus an “experimental” source filter cannot establish independent evidence. The exact upstream releases represented in frozen `pharos319` remain unidentified. [STRING score documentation](https://string-db.org/help/scores/); [HuRI primary paper](https://www.nature.com/articles/s41586-020-2188-x).

All bulk PPI properties were already requested, yet none of the 81,787 saved raw views contains `Evidence`. The saved schema offers pair-level `ppiTargetInteractionDetails`, including `interaction_type` and `evidence`; that path could add detail, but it has not been exercised in this audit and declares no explicit release or PMID fields. Do not equate additional retrieval with recovered study independence.

Reuse the existing explicit-panel retrieval and context normalization. Do not inherit CRC tissue filters, DepMap allowlists or gene/protein collapse rules. Mask held-out pair equivalents across raw responses, retained assertions and derived features before learning. Preserve generic interaction-annotation semantics: a STRING functional relationship is not automatically a demonstrated binary binding event.

## Validation and repository boundary

The original input-audit increment passed seven new audit tests and nine existing identifier tests. It verifies archived bytes before reading members and refuses to overwrite output directories. Tests cover accidental outcome decoding, wrong identifiers, ambiguous genes, multiple/conflicting products and altered archives. No live model or GPU was used.

The accompanying small test-fixture cleanup was subsequently superseded by main-branch consolidation. Closed experiment implementations, tests and protocols now reside on the separate archive branch described in [EXPERIMENT_HISTORY](../EXPERIMENT_HISTORY.md). Their original source hashes and saved packets remain unchanged. The current [script inventory](../../scripts/README.md) contains only the INMC audit and upstream runtime smoke.

Reproduce the input audit from the repository root, with a new output directory:

```sh
python3 scripts/audit_inmc_inputs.py \
  --archive runs/link_prediction_reuse_audit_20261022/inmc_release_v1.zip \
  --registry runs/crc_adjudication_mapping_20261020/registry \
  --output-dir runs/inmc_readiness_repeat
python3 -m unittest discover -s tests -p 'test_inmc_input_audit.py' -v
```

The [audit script](../../scripts/audit_inmc_inputs.py) adds a small source-format adapter and reuses the existing mapper. It does not implement another training framework or scientific scoring rule.

## Next action

Use the author-provided positive reference for later controlled reconciliation. Finish the negative/failure inclusion contract, or explicitly bound the task to unambiguous source outcomes and document the change before deriving labels. Resolve mapping exceptions without silently replacing benchmark identities. Then retrieve consistent Pharos context for the fixed panel, audit raw-source overlap, and freeze the shared-scaffold comparison. Do not start another model run from the old CRC snapshot.

The audit processed assay code vocabulary but displayed no per-pair outcomes, derived no binary labels and generated no predictions. Published aggregate results were already known. No graph assertions, source approvals or scientific-accuracy claims were added.
