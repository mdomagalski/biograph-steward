# Pharos construction evidence record — October 20, 2026

This is a source and architecture audit, not a new biological experiment or a complete reconstruction of the deployed database. It builds on the project's [coverage audit](../PHAROS_COVERAGE_AUDIT.md), [scoped retrieval contract](../SCOPED_RETRIEVAL.md) and [matched 256-gene panel](../EXPERIMENT_HISTORY.md#reopening-an-archived-file "Archive file: docs/evaluations/MATCHED_PHAROS_PANEL_20261020.md"). No new Pharos data pull, model inference or training was performed for this record.

## Source identities and temporal boundaries

- **TCRD build code:** official `unmtransinfo/TCRD`, commit [`90d072154fa7afa1eca3dc3449dae709c72cf1b6`](https://github.com/unmtransinfo/TCRD/tree/90d072154fa7afa1eca3dc3449dae709c72cf1b6), committed July 20, 2021. Its [README](https://github.com/unmtransinfo/TCRD/blob/90d072154fa7afa1eca3dc3449dae709c72cf1b6/README.md), build notes and selected loaders describe historical construction. They are not evidence that every loader remains unchanged in the deployed release.
- **Pharos query code:** official `ncats/pharos-graphql-server`, commit [`3feb5ac7e450b3c6b767651f0fe1f39994085380`](https://github.com/ncats/pharos-graphql-server/tree/3feb5ac7e450b3c6b767651f0fe1f39994085380), committed June 12, 2026. Previously saved `TCRD.js`, disease/version models and resolvers match their Git blob identifiers in this commit's tree. Public source identity does not attest which commit the public API runs.
- **Published descriptions:** [Pharos 2017](https://doi.org/10.1093/nar/gkw1072), [TCRD and Pharos 2021](https://doi.org/10.1093/nar/gkaa993), [Pharos 2023](https://doi.org/10.1093/nar/gkac1033) and the [2024 IDG Knowledge Management Center overview](https://doi.org/10.1016/j.drudis.2024.103882). These describe the releases and methods available when written, rather than a current inventory.
- **Observed project inputs:** saved API responses reported `pharos319` on October 14 and before/after the October 20 matched-panel pull. The older coverage audit recorded 83 source-catalog entries. The 2023 paper's 79 sources, and historical README's “70+,” must not be substituted for that observed catalog or treated as current completeness guarantees. Links, imported tables and exposed API records are different inventories.

Pinned metadata and selected source files are retained under ignored `runs/pharos_construction_audit_20261020/`; earlier source/schema observations remain under `runs/pharos_coverage_20261014/`.

## Construction map

The evidence supports this layered model:

**Upstream records → target identity/crosswalks → source-specific ingestion → TCRD tables → Pharos transformations → GraphQL/UI views → BioGraph Steward's scoped graph and features.**

The historical build README establishes that reviewed human UniProt entries are loaded first, followed by source-specific loaders. Inputs include files and APIs; some require preprocessing or manual steps. The 2023 paper describes expression ETL moving into Apache Airflow, checking for new inputs and otherwise copying previously built tables. Consequently, a database release can contain sources with different update dates.

Pharos then exposes normalized and aggregated views. Its [transformation instructions](https://github.com/ncats/pharos-graphql-server/blob/3feb5ac7e450b3c6b767651f0fe1f39994085380/pharos_database_transforms/README.md) describe restructuring ligand/activity data, disease mappings and per-pair PPI records, plus mappings to sources and publications. These instructions now delegate transformations to a `pharos-etl` repository. The expected `ncats/pharos-etl` URL returned unauthenticated HTTP404 during this audit; this does not establish whether the repository is private, moved or named differently. The complete current transformation pipeline was therefore not verified.

## Direct evidence about meaning and aggregation

**Disease scope.** The 2023 paper describes Mondo equivalence mappings and aggregation from descendant diseases into parent-disease queries, and reports incomplete mappings in that historical release. The pinned [disease model](https://github.com/ncats/pharos-graphql-server/blob/3feb5ac7e450b3c6b767651f0fe1f39994085380/src/models/disease/diseaseList.ts) retrieves source-specific association fields through derived disease mappings. Broad disease membership should not silently become an exact subtype, variant, causal mechanism or therapy-response claim. Current mapping completeness was not measured here.

**Interactions.** The historical [STRING loader](https://github.com/unmtransinfo/TCRD/blob/90d072154fa7afa1eca3dc3449dae709c72cf1b6/loaders/load-STRINGDB.py) imports `combined_score`; the [BioPlex loader](https://github.com/unmtransinfo/TCRD/blob/90d072154fa7afa1eca3dc3449dae709c72cf1b6/loaders/load-BioPlexPPIs.py) imports `p_int`, `p_ni` and `p_wrong`. The Pharos transformation instructions describe one interaction row with columns for contributing evidence sources. In pinned [query code](https://github.com/ncats/pharos-graphql-server/blob/3feb5ac7e450b3c6b767651f0fe1f39994085380/src/TCRD.js), the confidence exclusion specifically targets rows whose source label equals `STRINGDB`; mixed-source labels are not subject to that same clause. Thus “confidence 400” is not a universal, calibrated threshold across all returned interactions. These public code semantics were inspected; their deployment was not independently attested.

**Expression and derived scores.** Published Pharos documentation distinguishes RNA expression, antibody-based protein expression, mass-spectrometry expression and TISSUES consensus confidence. Bibliometric novelty, TDL and TIGA-derived association ranks describe other quantities. Pooling their numbers into one biological confidence is an unsupported transformation. The existing retrieval preserves source fields, but units in the retained expression records remain unknown; the matched-panel policy excludes popularity and unresolved dependency-related features.

## Harmonizome: stored detail versus exposed view

The historical [Harmonizome loader](https://github.com/unmtransinfo/TCRD/blob/90d072154fa7afa1eca3dc3449dae709c72cf1b6/loaders/load-Harmonizome.py) iterates gene sets and stores each mapped gene association, including its `thresholdValue`, in `gene_attribute`. It also stores dataset/resource metadata and publication identifiers. This is richer than a source-presence flag, but does not establish storage of raw sample-level matrices.

By contrast, pinned `getGeneAttributesForTarget` reads `hgram_cdf` and returns dataset-type counts/CDF values; its type lookup supplies dataset metadata. The project's inspected GraphQL `GeneAttribute` fields likewise expose `count`, `cdf` and dataset type. Therefore:

- “Not retrieved by our adapter” does not mean “absent from the API.”
- “Not exposed in this API view” does not mean “absent from TCRD.”
- Materializing more detail from the same study is useful representation enrichment, but is not automatically independent evidence.

The present contents of every underlying Harmonizome table were not downloaded or checked. Similarly, the observed LinkedOmicsKB links establish a connection, not the import or absence of all CPTAC measurements.

## Implications for project decisions

The construction audit supports a lineage review of the already retrieved panel before selecting another source. For each proposed addition, compare **source record**, **qualified assertion** and **underlying study/sample/experiment** separately. Distinguish a duplicate, added context or structure, verified new experiment, conflict and unresolved overlap. Shared source labels or publications alone cannot establish independence.

Three testable hypotheses remain proposals, not results: preserving disease/assay context could reduce inappropriate evidence transfer; source-aware normalization could reduce duplicate support counts; and CPTAC protein/phosphosite measurements could improve the fixed growth-dependency task beyond the matched Pharos baseline. The last hypothesis requires an explicit overlap review and frozen transformations before outcome inspection. Greater record counts, schema-valid extraction and improved retrieval coverage do not by themselves demonstrate biological improvement.
