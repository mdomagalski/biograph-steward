# DepMap feasibility and source-leakage audit — October 20, 2026

**Decision: the processed data can support a scoped experiment. A fair graph-improvement comparison is not ready yet.** This increment runs the coverage/leakage audit proposed after the [context/cohort follow-up](CRC_CONTEXT_COHORT_20261020.md). It calculates no dependency rankings, biological prediction metrics or scientific gold labels.

## Release and observed coverage

The current DepMap portal required browser verification. The audit instead uses Broad's separate, openly published [24Q4 v1 archive](https://doi.org/10.25452/figshare.plus.27993248.v1), with all nine selected source files verified against publisher byte counts and MD5s and independently hashed with SHA-256. This is a historical feasibility result, not a statement of current-release coverage. Publisher metadata dates this archive version December 10, 2024 and grants CC BY 4.0. The [24Q4 release notes](https://forum.depmap.org/t/announcing-the-24q4-release/3564) document processing changes; release-specific corrections must not be treated as interchangeable with later releases.

| Observation | Result |
|---|---:|
| Model metadata rows | 2,105 |
| Screened model rows in the gene-effect matrix | 1,178 |
| Matrix gene columns | 17,916 |
| Eligible colorectal adenocarcinoma cell lines in metadata | 95 |
| Selected colorectal lines actually screened | 63 |
| Included QC-passing 2D screens for those 63 models | 80 |
| Recorded tissue-sample groups for the 63 models | 61 |
| Other cell-line models with documented included 2D context | 1,100 |
| Original CPTAC rows accounted for | 6,422 |
| Unambiguous genes matched by stable identifiers | 6,273 |
| Matched genes observed in all 63 colorectal models | 6,153 |
| Identified genes absent from this matrix | 142 |
| Original ambiguous measured-gene names kept unresolved | 7 |

All 6,273 matches have reviewed protein context in the frozen cohort. Thirty displayed symbols differ between the 2024 release and current registry; stable HGNC/NCBI Gene IDs resolve them without symbol guessing. The other 120 matched genes have partial colorectal coverage, with at least 31 observed models per matched gene. The full matrix has 20,924,741 finite observations and 180,307 missing entries; missingness is retained.

The exact colorectal selector excludes small-bowel cancer, neuroendocrine and organoid models. The 32 eligible metadata lines missing from the effect matrix are not screened non-dependencies. Related pairs COLO 201/COLO 205 and HCT-15/DLD-1 share recorded PatientID/tissue-sample groups; they must not cross later partitions. Eighty screens are not 80 independent colorectal models. Distinct tissue-sample group IDs do not by themselves prove independent donor origins.

Only **44 protein entries / 43 measured gene rows** from the existing disease-selected 99-protein Pharos baseline match this joint CPTAC/CRISPR population. PRKDC's CPTAC row has no matched gene-effect column in this pinned matrix; absence is not a negative result. CUX1's two protein links still share one measured gene identity.

## Source overlap and leakage findings

The scoped Pharos snapshot records Harmonizome source flags for **96/99 proteins** and CCLE flags for **99/99**. These flags do not mean dependency matrices were imported. Four materialized publication titles mention RNAi/CRISPR; they are discovery references in other experimental contexts, not verified support for this endpoint. No literal DepMap/Achilles/Chronos program reference was found in the bounded materialized target/CIViC records, which does not establish global Pharos or upstream independence.

The separately preserved October 14 KRAS probe does contain **Achilles Cell Line Gene Essentiality Profiles** through Harmonizome. Its description specifies **shRNA knockdown**, and the attribute supplies a count/metadata summary. It is related perturbation evidence, not a retrieved modern Chronos CRISPR matrix. The count is not a set of independently verified assays and does not identify a release-matched overlap with the 24Q4 screens.

The exported feature-policy proposal requires withholding dependency, fitness and co-dependency outcomes and derived labels from every predictor arm. Unresolved Harmonizome/CCLE aggregates, source-presence/publication-count signals and outcome-derived QC statistics are excluded as predictors. QC may determine documented assay eligibility; it must not become a ranking shortcut. Broad integrated STRING/PPI, pathway/GO and publication channels remain subject to source-level review. A keyword audit alone cannot certify them independent. The proposal has not changed any existing graph.

## Concrete next increment

Freeze a modest, deterministic hash-selected panel from the mapped measured genes independently of effect direction, and retrieve equivalent Pharos features for every selected gene. The current 99 targets were selected by a disease association; they cannot serve as a neutral comparison population for the other 6,000-plus genes.

Before ranking, freeze the endpoint (general growth dependency versus colorectal selectivity), candidate/condition eligibility, missing-data handling, source exclusions, scoring rule and sample-group partitions. Compare matched Pharos, enriched, and enriched-plus-context-check arms against the same withheld processed outcomes. An outcome-derived common-essential list cannot quietly become a supposedly independent predictor baseline. Published Chronos joint preprocessing also limits claims about independent held-model/library validation. Only then calculate ranking recovery/correlation and uncertainty.

This audit establishes practical coverage and identifies leakage controls. It does not establish clinical response, colorectal selectivity, causal target validity or positive graph-prediction improvement.

## Reproduction

See [workflow and source contracts](../DEPMAP_AUDIT.md). Source files remain at `runs/depmap_feasibility_20261020/source/`, the first local preparation at `audit/`, and the final report at `final_audit/`. No historical report or cohort was overwritten. The [machine-readable record](depmap_feasibility_20261020_summary.json) binds the final audit, source, mapping, Pharos/CIViC controls and code fingerprint. Full source download receipts remain separate from the report; the export contains coverage/provenance, not the large score matrix or effect values.


## Validation and deployment

Implementation commit: `2368256f85911c22f89c2f349a84a7b69591fc1c`. The local Python 3.14 and Brev app-image Python 3.12 suites each ran **341 tests with one optional integration skipped**, with no failures. Test data are invented software fixtures, not scientific labels.

Brev received all nine source files plus publisher metadata/manifest and the report (22 files total). Publisher checksums and all SHA-256 identities passed again inside the container. A separate offline Brev replay reproduced coverage and the gene crosswalk, model inventory, matrix-column inventory, leakage findings and proposed feature policy byte for byte under the identical code fingerprint. The preserved local result was not replaced by its replay.

The app-only rebuild is healthy. Authenticated report/metrics and all 11 report-ZIP files matched saved bytes; anonymous report/ZIP access was rejected. The large gene-effect matrix is preserved separately and omitted from the report export. All five earlier source/cohort/planning reports remained byte-identical. Browser rendering was not independently verified. No model inference, training, GPU-serving changes or graph review actions were performed.

With the existing SSH tunnel active, open the [protected audit report](http://127.0.0.1:8767/api/evaluation/depmap_feasibility_20261020/) or [download its coverage/provenance export](http://127.0.0.1:8767/api/download/depmap_feasibility_20261020). Frozen source files are on Brev at `/data/runs/depmap_source_24q4_v1_20261020/`; the report is at `/data/runs/depmap_feasibility_20261020/` and its validation replay is kept separately in a hidden runs directory.
