# Matched Pharos panel — October 20, 2026

**The neutral comparison inputs are prepared; biological improvement has not been tested.** This follows the [DepMap feasibility audit](DEPMAP_FEASIBILITY_20261020.md) and replaces disease-selected sampling with a frozen measured-gene panel for the forthcoming comparison. Existing graphs and reports remain unchanged.

## Frozen population and retrieval

The fixed stable-ID hash rule selected **256 genes from 6,153 eligible genes**, independently of dependency direction/value, CPTAC abundance, disease associations or Pharos availability. Eligibility still conditions on complete measurement in all 63 selected colorectal models from the historical 24Q4 release. Their 61 recorded tissue-sample groups remain attached for subsequent partitioning. These are not a random sample of all human genes or proof of independent donor origins.

The panel contains **257 reviewed human protein-product candidates**. Pharos resolved 256 products; SCRIB's additional accession `C0HLS1` returned null while its other product `Q14160` resolved. Thus all **256 genes have at least one resolved product**, with full product resolution for 255 genes. Membership was not changed or replaced.

The retrieval used **346 fresh response envelopes, zero cached envelopes**, and database version `pharos319` before and after. Explicit UniProt queries requested no disease-association fields. The same caps and scope applied to every resolved product. All four requested families reconciled to reported API counts, with no capped, inconsistent or budget-limited products in this pull. Version equality and count reconciliation do not make the remote database transactionally atomic or establish complete biological coverage.

| Family | Retrieved rows | Rows retained by panel/tissue scope | Provisional source-policy candidates | Genes with candidates |
|---|---:|---:|---:|---:|
| Pathways | 6,724 | 6,724 | 5,724 | 186 |
| GO | 4,269 | 4,269 | 2,982 | 250 |
| PPI | 39,599 | 926 | 14 | 13 |
| Expression | 156,838 | 2,602 | 2,602 | 256 |

The total is **207,430 retrieved rows**. Counts are source records, not unique biological edges, independent experiments or validated predictors. Reciprocal interactions, repeated annotations and multiple product links remain distinguishable. Drug and publication discovery were intentionally not requested. The tissue view uses whole-word colon/rectum matches and retains missing/not-detected observations without zero imputation or source-scale aggregation. Separate GTEx measurements were not fetched.

## Source exclusions and remaining decisions

The provisional view withholds **1,000 pathway records**, **1,287 GO records** and **912 within-panel interaction records** under its explicit source allowlists. Metadata, source-presence/popularity counts, target descriptions/TDL, PPI score properties and any dependency-related/unresolved cell-model sources are excluded from this candidate view. Underlying-study independence remains unverified; passing a source/name policy is not scientific validation.

The interaction view is particularly conservative: the 926 within-panel records comprise 844 `STRINGDB`, 14 `BioPlex`, 42 `BioPlex,STRINGDB`, 12 `BioPlex,Reactome,STRINGDB` and 14 `Reactome,STRINGDB` labels. Only the 14 unmixed BioPlex records pass the current allowlist. Mixed labels do not establish that the non-STRING contribution is independently identifiable. Before choosing an interaction-based scoring rule, inspect component provenance and the confidence filter; do not silently promote these combined records or treat excluded records as negative interactions.

Raw metadata reports Harmonizome presence for 253 products, CCLE for 249 and LinkedOmicsKB for all 256 resolved products. These flags remain outside predictors. They neither establish that those measurements were imported nor certify independence from the intended comparison endpoint or CPTAC arm.

**Next:** review the provisional sources and mixed interaction channels, then freeze gene-level deduplication/aggregation, transformations and missing-data handling, the exact growth-dependency endpoint, ranking rule, simple baselines and tissue-sample partitions before reading dependency values. The first matched comparison should be Pharos versus Pharos+CPTAC. CIViC therapy-response evidence remains separate from this endpoint. Keep upstream Chronos joint-processing limitations explicit.

## Reproduction and validation

See the [workflow and contracts](../MATCHED_PHAROS_PANEL.md) and [machine-readable experiment record](matched_pharos_panel_20261020_summary.json). Local artifacts are `runs/matched_pharos_panel_20261020/frozen_panel/` and `retrieval/`. Raw source data remain outside Git.

| Artifact | SHA-256 |
|---|---|
| Frozen panel | `b792a19638775e11f65ac9d5febc37cce2452b9c9452dd9a34edc443ae39ba46` |
| Explicit Pharos snapshot | `5f023b3e197915c12c1a5e33a4de63623b6dbbd6f57a8edf1cf8ebe8cad6216c` |
| Retrieval result | `52fe22921415457f34da169242fd47812be8092b27f8f82f34dcf96f31403d9f` |

Implementation commit: `e78fc3cffbd03d962ea92b3617a27047be6c5df2`. Local Python 3.14 and Brev Python 3.12 each ran **349 tests with one optional integration skipped**, with no failures. Invented fixtures test outcome-blind selection, missing/wrong identities without replacement, source exclusions, raw response locators, partial failure and immutable artifacts; they are not biological gold judgments.

Both frozen-panel and retrieval artifacts were transferred to Brev with all 15 file hashes verified. Brev reproduced membership/population/model exports byte for byte from the preserved parent controls and reconstructed the feature view from raw records under the identical code fingerprint. The app-only rebuild is healthy. Authenticated report/metrics and all ten ZIP files matched saved bytes; anonymous access was rejected. Six historical reports remained byte-identical. Browser rendering was not independently verified. No model inference, dependency scoring or GPU-serving changes were performed.

With the SSH tunnel active, open the [protected coverage report](http://127.0.0.1:8767/api/evaluation/matched_pharos_panel_20261020/) or [download the full report/source export](http://127.0.0.1:8767/api/download/matched_pharos_panel_20261020). The 24Q4 dependency score matrix is not part of this export. Brev preserves the panel at `/data/runs/matched_gene_panel_20261020/` and retrieval at `/data/runs/matched_pharos_panel_20261020/`.
