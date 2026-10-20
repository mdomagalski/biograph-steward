# Frozen measured-gene panel and matched Pharos retrieval

This prepares comparable inputs for a future Pharos versus Pharos+CPTAC experiment. It does not calculate a dependency ranking, train a predictor or establish biological improvement. The initial experiment remains a general growth-dependency question; it must not silently become a clinical response or colorectal-selectivity claim.

## Freeze membership before retrieval

```sh
python3 app.py matched-panel-prepare \
  --audit runs/depmap_feasibility_20261020/final_audit \
  --mapping runs/crc_adjudication_mapping_20261020/published_cohort \
  --out runs/matched_pharos_panel_20261020/frozen_panel
```

The verified parent artifacts establish stable HGNC/NCBI Gene identities, reviewed human protein context and measurement availability. Eligibility requires an observed value in every selected screened colorectal model. The selection function receives availability counts and identifiers, not dependency effect values, CPTAC abundance summaries, disease associations or source popularity. Parent mapping verification reproduces its existing CPTAC crosswalk; its abundance values do not enter panel selection or Pharos retrieval.

Eligible genes are ordered by SHA-256 of canonical JSON containing the fixed policy `crc-complete-measurement-hash-panel.v1` and HGNC ID. The first 256 form the panel. There is no seed search or replacement based on Pharos coverage. This is an outcome-blind sample within the complete-measurement CPTAC/DepMap intersection, not a representative sample of all human genes. Historical 24Q4 missingness and prior cohort eligibility constrain its scope.

`panel.json` binds the parents, registry, eligibility population, members, screened-model/sample groups and retrieval limits with hashes. `members.tsv` is a readable identity list. All reviewed product candidates remain attached to their gene; multiple products do not duplicate the gene-level measured outcome. All output directories must be new.

## Retrieve the same context for each fixed gene

```sh
python3 app.py matched-panel-retrieve \
  --panel runs/matched_pharos_panel_20261020/frozen_panel \
  --out runs/matched_pharos_panel_20261020/retrieval
```

The adapter resolves explicit UniProt IDs with no disease filter or disease-association fields. Null and mismatched responses remain visible and do not trigger replacements or symbol guessing. Every resolved product receives the same per-product caps: 2,000 pathway, 500 GO, 2,000 PPI and 2,000 expression records; drug/publication discovery is skipped. The global row reservation is the sum of those caps times all requested products, so late genes do not lose their equal reservation to the earlier generic 200,000-row ceiling.

Expression retrieval scans the bounded source list and retains whole-word `colon` or `rectum` matches locally. It preserves the reported tissue, assay/source, zero, missing and not-detected observations. This endpoint does not include the separate GTEx measurements API. Colon/rectum tissue matches are not automatically tumor measurements. PPI retrieval uses the existing confidence-400 source filter and a single bounded neighbor list to avoid unstable score-tie pagination; retained interactions must have both products in the resolved panel. Raw responses also preserve excluded outside-panel neighbors. Endpoint counts, retrieved counts, caps, inconsistencies and not-requested families remain explicit. “Complete” describes observed API coverage for that requested family, not complete biology.

The client pins a dedicated panel-specific cache, preserves original retrieval timestamps and raw response hashes, and records database versions before and after the pull. It does not silently fall back to a prior disease-selected snapshot or synthetic responses. Source/version changes and partial failures cannot establish scoring readiness; a failed attempt must remain separate from any resumed immutable result using the same membership.

## Raw sources and provisional features

`snapshot.json` preserves raw response envelopes, product resolution, source licenses, metadata and retrieved annotations. It is an explicit-ID panel artifact; it is not a disease graph with invented disease edges.

`feature_candidates.json` has exactly one container for every selected gene, including empty ones. The provisional source policy permits Reactome/WikiPathways membership, selected GO assigning sources, BioPlex/Reactome interactions and selected tissue-expression sources. It withholds dependency-related records, unresolved Harmonizome/CCLE/CTD2 summaries, integrated STRING and other unreviewed interaction channels, shared products without gene-specific attribution and other sources outside the allowlists. All metadata/source counts, target names/descriptions/TDL, disease annotations, PPI score properties and discovery publication/drug fields stay outside this view. Identity fields and record locators remain for traceability, not an automatically approved feature matrix.

`feature_exclusions.json` records reasons and source-record hashes. Every retained or excluded record points to an actual JSON location in `snapshot.json`; coverage pages identify the underlying request index and response pointer. `feature_policy.json` explains the provisional allowlists and remaining provenance review. Keyword/source filtering cannot establish independence of underlying studies. Repeated annotations, reciprocal interactions and multiple product records are source views, not additive independent measurements. No deduplication, imputation, cross-source scaling or ranking is silently applied.

`report.html`, `metrics.json`, `gene_coverage.json` and `retrieval_coverage.json` expose membership, resolution, family coverage, exclusions and unresolved readiness. To verify without network calls:

```python
from biograph_steward.matched_panel import load_panel, verify_retrieval
load_panel('runs/matched_pharos_panel_20261020/frozen_panel')
verify_retrieval('runs/matched_pharos_panel_20261020/retrieval')
```

Verification checks immutable bytes, panel membership, raw response hashes, explicit-ID resolution and reconstruction of the provisional feature view. Existing reports remain historical even if later code changes.

Before examining dependency values, freeze source provenance decisions, gene-level deduplication/aggregation, transformations and missing-data handling, the endpoint, ranking rule, simple baselines and tissue-sample partitions. Use identical genes, sources and outcome handling in the matched arms. CIViC therapy-response evidence remains separate from the growth-dependency endpoint. The processed Chronos matrix also retains upstream joint corrections, limiting claims of fully independent model/library validation.
