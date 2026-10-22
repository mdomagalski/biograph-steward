# Pharos coverage and evidence overlap audit

**Repository scope note (October 22):** this is a dated source/methods review. Its historical observations remain useful; the [current build plan](BUILD_PLAN.md) supersedes old next-step proposals. Closed study implementations and reports are preserved in the [experiment archive](EXPERIMENT_HISTORY.md).

Verified on October 14, 2026 against the live public API, which reported `pharos319`.

## Finding and decision

The application retrieves too little of Pharos to serve as a strong baseline. Adding Reactome pathways through a separate adapter would largely repeat information already available through Pharos. Complete the relevant Pharos retrieval and normalize overlapping assertions before evaluating external enrichment.

BioGraph Steward's product should be a workbench that retrieves evidence, identifies shared underlying studies, preserves context, and explains what a proposed addition contributes. The benchmark evaluates that workbench; it is not the whole product.

## Scope and reproducibility

This audit uses the same 99 proteins returned for **colorectal adenocarcinoma**, `MONDO:0005008`, in `runs/crc_baseline_audited_20261014/snapshot.json`. All 99 target identifiers matched across the baseline, coverage queries, and expanded pathway queries. The broader Pharos term **colorectal cancer**, `MONDO:0005575`, previously reported 2,597 targets; these are different scopes. The current application's 500-target maximum cannot fully retrieve that broader result.

I inspected the live GraphQL schema, 83 source-catalog entries, community API descriptions, target-specific source flags, source-version metadata, and the official NCATS resolver code. Count queries covered all 99 proteins; detailed probes covered KRAS and EGFR. All pathway rows were retrieved for the 99 proteins and reconciled against their individual reported counts. Other relation families were inventoried and sampled, not exhaustively downloaded.

Evidence is saved in `runs/pharos_coverage_20261014/`:

- `coverage_summary.json`: computed results, query timestamps, response hashes and baseline hash.
- `cohort_coverage.json`: per-protein counts and source flags.
- `full_pathways.json`: 9,540 pathway rows, including source IDs and URLs.
- `source_catalog.json`, `metadata.json`, `facet_catalog.json`: source, version and Harmonizome metadata.
- `KRAS_probe.json`, `EGFR_probe.json`: actual publication, PPI, GO, expression, drug and affiliate-link examples.
- `*_request*.json`: 14 successful request/response envelopes, with hashes verified locally.
- `live_schema.json` and saved NCATS source files: deployed schema and implementation reference.

Recompute the summary without a network request from the repository root:

```bash
PYTHONPATH=. python3 runs/pharos_coverage_20261014/summarize.py
```

These are local research artifacts under the ignored `runs/` directory. The expanded pathway pull has **not** been integrated into the application's graph or UI.

## What the current extract misses

Counts below are summed across proteins. They are annotation rows or protein-to-record memberships, not unique global entities, independent studies, or exclusively CRC-specific observations.

| Data available through Pharos | Current 99-protein extract | Live inventory for the same proteins |
|---|---:|---:|
| Associated proteins | 99 | 99 |
| Pathway annotation rows | 806 | 9,540 |
| Reactome pathway rows, included in the row above | 168 | 2,726 |
| PPI neighbor memberships | 0 | 30,870 |
| GO annotations | 0 | 4,078 |
| Expression records | 0 | 74,025 |
| Protein–ligand/drug memberships | 0 | 22,600, including 174 drug memberships |
| GWAS records | 0 | 741 |
| LINCS records | 0 | 1,201,396 |
| Linked publications | 0 | KRAS: 2,902; EGFR: 6,235; cohort total not measured |

The application captured **8.45% of the available pathway rows**. Its fixed first-10 cap also distorts source representation:

| Pathway source | Current rows | Full audit rows |
|---|---:|---:|
| Reactome | 168 | 2,726 |
| WikiPathways | 29 | 3,492 |
| KEGG | 509 | 1,588 |
| PathwayCommons: PID | 47 | 675 |
| PathwayCommons: INOH | 7 | 519 |
| PathwayCommons: Panther | 33 | 316 |
| PathwayCommons: NetPath | 10 | 212 |
| PathwayCommons: HumanCyc | 0 | 9 |
| UniProt | 3 | 3 |

The inspected pathway query has no explicit relevance ordering. The first 10 rows should not be described as the ten most relevant pathways. For this audit, a cap of 1,500 per protein exceeded the largest reported count, 1,085; every protein's retrieved row count matched its reported count.

Interpretation boundaries:

- **PPIs:** counts use Pharos's default confidence filter. Neighbors include proteins outside the 99-protein cohort. STRINGDB, BioPlex and Reactome source bins overlap; a single sampled KRAS–BRAF interaction carries all three source names. Preserve the evidence type and source scores rather than counting three independent confirmations. Reciprocal memberships also need normalization.
- **Expression:** the total covers JensenLab TISSUES, HPA RNA, HPA Protein and HPM Protein. These are heterogeneous measurements/confidence summaries, not all tumor measurements. GTEx is separately exposed. Tissue, assay and units must remain explicit.
- **GWAS and LINCS:** most records are outside the immediate disease question. Select relevant phenotypes, cell lines and perturbations instead of treating volume as useful coverage.
- **Publications:** the earlier absence of explicit citations applies to the 100 returned `diseaseAssociationDetails` records. It does not mean Pharos lacks literature. Target-linked papers must be checked for the exact claim, disease, variant and experiment; they cannot automatically be attached as support for every disease association.

## Overlap extends beyond Reactome

The live catalog includes Reactome pathways and PPIs, STRINGDB, BioPlex, Gene Ontology, ChEMBL, DrugCentral, GWAS, CTD, ClinVar, CCLE, LINCS, HPA, GTEx, PubMed and Harmonizome. A database brand alone is therefore not a useful novelty test.

**LinkedOmicsKB/CPTAC:** all 99 targets carry a LinkedOmicsKB source flag. KRAS and EGFR return gene-specific affiliate URLs, including `https://kb.linkedomics.org/gene/KRAS`. LinkedOmicsKB is absent from the 83-entry global catalog, so that catalog alone is incomplete as an inventory of links. The affiliate description refers to CPTAC. This verifies an existing connection, not that all underlying quantitative matrices are stored in Pharos.

**Harmonizome:** the KRAS response contains 89 dataset attribute summaries, including Achilles cell-line gene essentiality, TCGA differential expression, CORUM protein complexes, PhosphoSitePlus kinase substrates and CCLE measurements. The exposed attribute model contains counts and dataset metadata; it does not establish full retrieval of every underlying relationship. A detailed import could add useful granularity while still deriving from the same experiment. The Achilles dataset description refers to knockdown; it should not be relabeled as modern CRISPR data.

**Community APIs:** Pharos advertises external predicted functional interactions, tissue/cancer-specific coexpression and kinase–cancer predictions. Their presence does not make the predictions experimental evidence. It also means a new coexpression or predicted-network connector needs an overlap check.

## Additions worth pursuing

No external database can be declared entirely independent from Pharos from its name or catalog absence. Separate **newly represented detail** from **a new underlying experiment**.

| Candidate | What it can add | Condition for counting it as an addition |
|---|---|---|
| CIViC qualified evidence items | A molecular profile/variant, disease, therapy, response direction, evidence level and publication in one inspectable assertion | Compare the qualified assertion and source publication against Pharos and its upstream sources. Shared papers remain shared evidence. No equivalent full assertion model was found in the inspected Pharos fields; this is not proof that none of the biology appears elsewhere. |
| CPTAC COAD protein and phosphosite measurements | Sample-level values, tumor/normal contrasts and mutation-associated measurements with study and assay context | Establish which matrices/analyses Pharos only links to, then materialize missing detail. LinkedOmicsKB and PDC deliveries of the same CPTAC study are one evidence origin. |
| Versioned DepMap CRISPR measurements for CRC models | Gene-by-cell-line perturbation effects with assay, release and model identifiers | Compare against the Achilles/CCLE/Harmonizome content already represented. Only a verified new assay, model, measurement or release delta is incremental; a changed portal name is not. |
| Focused new literature | Direct support, contradictions or more specific contexts for selected claims | Verify PMID/DOI, underlying study, experiment and context against the existing record set. A new review or another paper analyzing the same samples is not automatically an independent experiment. |
| Direct Reactome reaction/complex topology | Participants, reaction direction, complex composition and hierarchy beyond flat pathway membership | First show the specific relation is not already accessible in Pharos. Treat it as added structure from an existing source, not independent corroboration. Lower priority than using the existing Pharos relations. |

The first external assertion adapter should target **CIViC** for the submitted variant/therapy use case. For the challenge's measured-protein context, investigate **CPTAC COAD matrices** in parallel with cohort design, preserving the existing LinkedOmicsKB connection. Neither candidate has yet undergone a complete record-level overlap comparison.

The [CIViC evidence model](https://docs.civicdb.org/en/latest/model/evidence.html) documents the qualified assertions and their publications. [LinkedOmicsKB COAD downloads](https://kb.linkedomics.org/download) list tumor/normal proteomics and phosphoproteomics; its [manual](https://kb.linkedomics.org/manual) explains site-level and mutation/phenotype analyses. These establish available data types, not an already implemented import. An [official DepMap model page](https://depmap.org/portal/cell_line/ACH-000312) illustrates versioned CRISPR/Chronos data; a particular release has not yet been selected or downloaded for this project.

## Rules for avoiding double counting

Keep three layers separately:

1. **Source record:** original provider, accession, version, retrieval time, raw record and aggregator chain.
2. **Qualified biological assertion:** normalized subject/predicate/object plus disease, variant, species, tissue/cell line, treatment, assay and direction where relevant.
3. **Evidence origin:** publication, study accession, sample set and experiment/contrast, when available.

Multiple records can describe one assertion. Multiple assertions can come from one experiment. A single paper can contain several experiments. Missing provenance means independence is **unknown**, not established.

The full pathway pull contains **1,508 repeated rows** when grouped within a protein by `(type, sourceID, name)`, leaving 8,032 such keys. For example, KRAS has three WikiPathways rows for `WP437_r105574`, “EGF/EGFR Signaling Pathway,” with distinct local `pwid` values. Also, 1,734 rows have no `sourceID`. Preserve every raw row, use stable source identifiers when available, and review unresolved cases; matching names alone is not sufficient for a universal merge rule. The current graph's local-ID fallback does not resolve this issue.

## Next implementation and completion criteria

1. Extend the Pharos adapter with per-protein, per-relation counts and explicit completion/limit status. Retrieve complete pathways; add bounded PPIs, GO, relevant expression, drug/activity context and citation discovery. Use query contexts that work on the deployed service and preserve errors.
2. Normalize shared assertions and retain their contributing records. Keep general protein function, observational correlations, perturbation results and clinical assertions distinct.
3. Add a coverage view and evidence passport that show missing data, original sources, shared studies, assay context and unknown provenance.
4. Add the qualified external evidence adapter and report each proposed record as duplicate, additional detail, verified new evidence, conflicting evidence or unresolved overlap.
5. Evaluate the tool against the completed, explicitly bounded Pharos baseline. A benchmark against the current 806-pathway extract would risk attributing ordinary Pharos retrieval improvements to external enrichment.

Operational findings: `publicationCount` failed in the disease-filtered target-list query but succeeded in individual `target(q: ...)` probes. Source-version metadata covers only five groups in this deployment; several recorded file dates are in 2024. Do not infer a universal cutoff or freshness guarantee from `pharos319`. Source license fields in the catalog were null and need upstream resolution before redistribution.

The API implementation reference is the official [NCATS schema](https://github.com/ncats/pharos-graphql-server/blob/master/src/schema.graphql), [resolvers](https://github.com/ncats/pharos-graphql-server/blob/master/src/resolvers.js) and [TCRD queries](https://github.com/ncats/pharos-graphql-server/blob/master/src/TCRD.js). The live responses are the evidence for current counts. The public Pharos overview page was inaccessible in this session; no browser inspection of that page is claimed.
