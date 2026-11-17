# Record-level overlap and identity mappings

This audit asks what a qualified assay record adds to an existing Pharos workspace: a pair already represented there, additional experimental context, a shared source record, or unresolved evidence lineage. It keeps those questions separate. A second database, publication or identifier does not by itself establish an independent experiment.

The commands inspect a **saved workspace and its attached qualified assay publication**. They do not retrieve new sources, modify the workspace, prune evidence, merge records, pool confidence scores or call a model. Use already consumed development material; the four metadata-selected fresh IntAct studies remain unopened.

## Run and inspect

From the repository root, substitute the paths to an existing saved workspace and a new output directory:

```sh
python3 app.py evidence-overlap --run runs/existing_workspace --out runs/overlap_new
python3 app.py evidence-overlap-verify --report runs/overlap_new
```

| Output | Purpose |
|---|---|
| `index.html` | Readable report and source limitations |
| `report.json` | Audit scope, counts and qualifications |
| `records.jsonl` | Record-level observations and the evidence behind each flag |
| `mappings.sssom.tsv` | Inspectable identity mappings targeting SSSOM 1.0 |
| `mappings.json` | Corresponding mapping data |
| `manifest.json` | Output inventory and integrity information |

Local verification checks the audit's recorded artifacts and internal constraints. It does not establish that mappings or scientific claims are correct. The completed upstream validation below is separate from this local verification.

## Completed development checks — October 27, 2026

The offline command and verifier ran on three existing saved workspaces. These are consumed development examples, not a new benchmark or the unopened reference panel.

| Saved workspace report | Observations inspected | What the report establishes |
|---|---:|---|
| `runs/evidence_overlap_intact_20261027_attempt_02` | 2 | Both source-qualified records describe the same pair already represented in Pharos. They share a publication and add detailed context. The baseline projection exposes no supporting experiment identifiers, so independence from its aggregate evidence remains unknown. |
| `runs/evidence_overlap_development_20261027_attempt_01` | 4 | Two observations match the bounded Pharos baseline; two do not, despite complete retrieval within the declared scope. This older publication has no captured XML-reader companion, so experiment-identity comparison is unavailable. The no-matches are not validated novel biology. |
| `runs/evidence_overlap_lambourne_20261027_attempt_01` | 1 | The selected cohort observation matches a Pharos pair and adds assay/construct context. This report covers one selected observation from a publication with 3,222 source observations; it is not a fresh full-publication overlap assessment. |

The reports leave experimental lineage unresolved for every inspected observation. No independent corroboration, scientific accuracy or predictive gain was established. No source record was automatically merged, pruned or assigned a combined confidence score. The CLI workflow was exercised; browser display and independent user interpretation have not been certified by this increment.

**All 14 exported mapping rows passed three official checks and a preservation roundtrip:** `JsonSchema`, `PrefixMapCompleteness` and `StrictCurieFormat`. The isolated environment used `sssom 0.4.21`, `sssom-schema 1.1.0a5`, and Python 3.12.14. The output targets the published SSSOM 1.0 subset; using the installed prerelease schema does not establish complete interoperability or biological mapping validity. Row counts, mapping slots, metadata, CURIE expansions, graph-release labels and sidecar provenance links were preserved.

The validation receipt is `runs/evidence_overlap_sssom_validation_20261027/report.json`, SHA-256 `bf6b8cb8950540306660fcecabdefe4de61428290efa11527d2cc36dd4b1668e`. It records the commands and all three input hashes. An inverted strict-parser metadata guard was verified in the installed version and its official source archive. No monkeypatch was used: validation used the official default parser, the three validators and explicit preservation checks. The audit itself retains the standard-library-only core; this optional isolated validation environment is not a new runtime dependency.

## What the flags mean

Flags are orthogonal and can coexist. Their counts must not be added as mutually exclusive categories.

| Observation | Supported interpretation | Limit |
|---|---|---|
| Exact protein pair occurs in retrieved Pharos PPI records | The bounded baseline already represents that pair | A functional association is not necessarily the assay's physical interaction claim |
| Same qualified local claim | Equivalent local claim fields are present in the inspected material | Agreement does not prove independent experimental support |
| Shared PMID | The records cite the same publication | A publication can contain many different experiments |
| Shared IntAct or IMEx interaction accession | A common curated record identifier is present | Preserve the source namespace and accession; study-level deposits are not interaction IDs |
| Shared PDB/EMDB or other external structural identity | A common external identity reference is present | A shared structure identifier alone is not a shared experiment or an independent observation |
| Shared scoped experiment metadata | Matching metadata exist within the recorded source scope | Local experiment identifiers must not be treated as globally unique identifiers |
| Additional experimental context available | The attached record exposes fields absent from the inspected baseline representation | Added detail is useful enrichment, but it may describe an experiment already aggregated upstream |
| Unknown lineage | Available source identifiers do not settle experimental origin | Unknown does not mean independent, novel or duplicated |
| No pair in a complete bounded PPI retrieval | No match was found within the declared retrieval scope | Caps, failed pages or missing coverage cannot support absence; even complete bounded absence is not biological noninteraction |

Source pointers and original record context remain available for inspection. Missing metadata are recorded as missing, rather than filled by a label match, a database name or a plausible biological story. Eligible nondetections remain assay-specific observations, not reasons to prune functional associations.

## SSSOM identity boundary

The initial mapping profile uses only **exact primary UniProt accessions**, retaining any isoform suffix. It does not derive mappings from labels, gene symbols, gene-to-protein relationships or generic cross-references. A canonical accession and an isoform accession are not silently interchangeable. Unresolved or unsupported identities remain visible without creating a mapping.

The exported `owl:sameAs` rows associate the identical source-primary UniProt CURIE across the supplying records, with `semapv:LexicalMatching` justification. They are not a newly resolved cross-release accession map or an assertion that constructs, sequences or experimental evidence are identical. Source/version slots name the supplying graph and its release, not an inferred UniProt registry release; stable sidecar links retain the individual record locators.

The [versioned SSSOM 1.0 specification](https://mapping-commons.github.io/sssom/1.0/spec-model/) requires a subject, object, mapping relation and justification. The exported mapping information also preserves the source context needed to interpret the assertion. SSSOM represents a mapping decision and its provenance; it does not validate that decision biologically. Broader accession-history reconciliation, sequence equivalence and Pharos400 migration require separate source-supported mappings.

## Pharos release boundary

The [October 27 release check](evaluations/PHAROS_RELEASE_CHECK_20261027.md) made a fresh uncached query: the configured public API still reports `pharos319`. Our client queries that value; it does not select 319 from documentation. The [official NCATS directory](https://opendata.ncats.nih.gov/public/pharos/) offers Pharos400 identity/TDL tables, but no equivalent complete 400 graph API or SQL dump was verified in the checked official materials.

Keep those release scopes distinct. A separately downloaded 400 identity table could support a versioned SSSOM crosswalk; it cannot relabel 319 PPI evidence as 400 or establish that underlying experiments are independent. The [400 release notes](https://opendata.ncats.nih.gov/public/pharos/pharos400_readme.html) document changed canonical/isoform/alternate-product grouping. Historical snapshots, readers and evaluation results remain unchanged.

## Established methods and remaining gap

The [scoped source-update supplement](PHAROS_SOURCE_UPDATE.md) now adds a separate 400 layer for the current consumed pair. Its richer Pharos details capture still returns null evidence/type; two 400 canonical rows yield two exact identifier correspondences. Both TDL values remain Tbio. The original overlap and graph remain unchanged, with experimental lineage unresolved.

- [MImerge/MIscore](https://pmc.ncbi.nlm.nih.gov/articles/PMC4316181/) already address redundant interaction evidence using community-standard identifiers, methods and interaction types. We follow the distinction between an interacting pair and its supporting evidence. We are not reimplementing MIscore or applying a new confidence threshold. Complete MImerge-style reconciliation is limited by the provenance actually exposed in Pharos's aggregate records.
- The [IMEx consortium paper](https://www.nature.com/articles/s41467-020-19942-z) documents both detailed curation and reuse by STRING and other aggregators. Resource names therefore cannot serve as independent evidence counts. This audit exposes identifiable overlap and leaves unresolved lineage explicit.
- [Brière et al., 2026](https://pubmed.ncbi.nlm.nih.gov/42623034/) demonstrate that redundant relations can inflate biomedical link-prediction evaluation. Their [author implementation](https://github.com/galadrielbriere/data_leakage_kge_benchmark) informs the split audit; its preprocessing is not adopted wholesale. Matching record identifiers does not eliminate all indirect or publication-derived leakage.

This increment supplies an inspectable overlap account, not a new biological performance result. The immediate unresolved issue is the experiment provenance absent from the inspected baseline projection, plus the missing XML companion in the older development publication. Check existing official records and source bindings before extending retrieval or claiming that a source lacks those details. A later improvement assessment needs a defined intervention, a simple-addition control using the same information, defensible source separation and a frozen evaluation. Previously consumed panels remain development material.

The later [provider trace](evaluations/PROVIDER_PAIR_LINEAGE_20261027.md) resolves one exact user-assisted current-STRING record match. The [workbench supplement](ASSAY_SOURCE_REUSE.md) displays it beside preserved assay context and exports its copied proof. It leaves this earlier audit and historical Pharos lineage unchanged.
