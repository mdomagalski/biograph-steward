# DepMap coverage and leakage audit

This audit establishes whether a processed CRISPR dataset can supply a scoped biological endpoint. It does not rank genes, create dependency labels, train a model, run an agent or modify the graph. The [recorded result](evaluations/DEPMAP_FEASIBILITY_20261020.md) uses the explicitly pinned **DepMap 24Q4 Public, Figshare article 27993248, version 1**, DOI [10.25452/figshare.plus.27993248.v1](https://doi.org/10.25452/figshare.plus.27993248.v1), under its CC BY 4.0 terms.

## Source acquisition and freezing

The current portal and documented metadata route presented a browser-verification page during this task. That access requirement was not bypassed. This historical archive is a separate openly published dataset, not a current-release substitute. Its coverage and processing policy must stay attached to every result.

The versioned publisher record is available at `https://api.figshare.com/v2/articles/27993248/versions/1`. Save its exact JSON as `article_27993248_v1.json` and download the nine named files from the URLs in that record into a sibling `downloads/` directory. The actual task retrieval receipts remain in `runs/depmap_feasibility_20261020/preparation/`.

| File | Publisher file ID | Purpose |
|---|---:|---|
| README.txt | 51065795 | Release-specific data contract |
| Model.csv | 51065297 | Model lineage/type and tissue-sample groups |
| Gene.csv | 51065183 | Release HGNC/NCBI Gene crosswalk |
| CRISPRGeneEffect.csv | 51064667 | Processed model × gene effects; coverage only |
| ModelCondition.csv | 51065300 | Assayed conditions and treatment flags |
| CRISPRScreenMap.csv | 51065159 | Screens incorporated into each model |
| AchillesScreenQCReport.csv | 51063569 | Published screen inclusion/QC flags |
| CRISPRInferredModelEfficacy.csv | 51064994 | Preserved release processing metadata |
| ScreenSequenceMap.csv | 51065828 | Preserved screen/sequence provenance |

These files total about 447 MB. The whole release is not required. The latter two tables are preserved but their efficacy/sequence values are not used to select genes or calculate scores.

```sh
python3 app.py depmap-freeze \
  --downloads runs/depmap_feasibility_20261020/preparation \
  --out runs/depmap_feasibility_20261020/source
```

The freezer requires the exact release/version/DOI, file inventory and publisher download identities. It verifies every byte count and publisher MD5 before freezing the copies, records SHA-256 and preserves the publisher metadata/license. A mismatched or incomplete file fails; no alternate release or synthetic fallback is used. The source directory is immutable. `load_depmap(path)` rechecks every file, including the large matrix.

## Run the audit

```sh
python3 app.py depmap-audit \
  --source runs/depmap_feasibility_20261020/source \
  --mapping runs/crc_adjudication_mapping_20261020/published_cohort \
  --pharos-run runs/planning_challenge_20261020/suite/sources/pharos \
  --enriched-run runs/planning_challenge_20261020/suite/sources/enriched \
  --probe runs/pharos_coverage_20261014/metadata_request.json \
  --out runs/depmap_feasibility_20261020/final_audit
```

The input cohort and Pharos hashes must agree; the optional enriched arm must reuse the identical Pharos snapshot. The historical probe's response hash is checked and its source/date remain distinct from the actual baseline inputs. All output directories must be new and outside the inputs.

Gene matching requires explicit numeric NCBI Gene IDs, the release's approved HGNC map and agreement with the frozen current cohort identity. Release strings such as `3845.0` are accepted only when they represent exact integers. Symbols are retained for display and change tracking, never used to guess a match. Ambiguous input genes, missing matrix genes and identifier disagreements remain explicit.

The model selector requires exact `OncotreeLineage=Bowel`, `OncotreePrimaryDisease=Colorectal Adenocarcinoma`, `ModelType=Cell Line` and no annotated engineering/cultured drug resistance. The screened denominator comes from matrix rows, not all Model.csv entries. Screen/model/condition identities, published inclusion/QC flags, 2D screen types and condition drug flags are inspected separately. Missing condition details remain visible. Multiple screens do not become independent models. The README defines PatientID as models derived from the same tissue sample; those groups must stay together in later splits, without claiming that distinct groups establish independent donors.

Numeric matrix values are checked for finite/missing validity and immediately discarded. Outputs contain per-gene observed/missing counts, matrix identities and model metadata, not effect sizes, medians, thresholds, labels or rankings. Missing values are never zero-filled or interpreted as non-dependency. The already processed Chronos matrix is not an independent reanalysis of raw screens; upstream joint corrections remain part of its provenance.

## Outputs and limits

`report.html` and `metrics.json` summarize coverage and readiness. `gene_coverage.json`/`.tsv` account for every original measured row; `matrix_columns.json` retains release identifiers; `model_inventory.json` preserves model, sample-group and screen/condition joins. `leakage_inventory.json` contains exact matched source values and locators from materialized records, raw response inventory and the separate historical probe. Reference counts are not independent-study counts or proof of leaked measurements.

`feature_policy.json` proposes exclusions and controls; it is **not applied automatically to existing graphs**. It excludes endpoint-derived dependency/co-dependency information and unresolved Harmonizome/CCLE summaries from future predictor arms. Integrated PPI/STRING, GO/pathway and publication provenance still need review. `source_manifest.json`, the source README and the historical probe are retained with hashes. `verify_audit(path)` verifies output hashes and inventories without requiring the large input matrix; recomputing the full audit requires the separately preserved source and controls.

The protected app can serve the output as `/api/evaluation/depmap_feasibility_20261020/`, with a ZIP under `/api/download/depmap_feasibility_20261020`. The report export omits the 447 MB source directory and full historical Pharos/CIViC snapshots; their identities and reproduction paths remain recorded. Raw data should stay outside Git.
