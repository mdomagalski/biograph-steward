# Whole-workspace evidence audit — November 12, 2026

We completed a reproducible probability-sample audit of the full stored CRC
workspace, traced concrete source-integration problems, and executed a separate
current-WikiPathways qualification view. This advances source fidelity,
currentness and interpretation. **It does not establish whole-graph biological
accuracy or a validated biological-error pruning rate.**

The original graph, its reviews, the earlier failed/mixed comparisons and the
first audit outcomes remain preserved. These are optional evaluation tools;
the core workbench still has no third-party dependencies or model requirement.

## What was assessed

The verified source packet contains **99 primary targets, 9,865 nodes, 16,985
evidence records and 16,980 qualified assertions**. Before selecting cases we
froze a stratified simple random sample without replacement, seed
`2026111201`, with every assertion family represented. The population is
stored assertions with their existing identifiers, rather than deduplicated
biological facts. A subsequently discovered pathway-duplication problem does
not change that sampling frame retrospectively.

Each dossier retains the complete assertion, all its source edges, endpoint
identifiers and source inspection. Review separates exact source fidelity,
examined article/dataset/native-curation support and independent scientific
correctness. Missing evidence remains unresolved. An annotation, listing,
proximity observation or functional association is assessed as stored; it is
never silently strengthened to direct binding, causation or clinical efficacy.

| Assertion family | Population | Sample | Examined evidence supports the stored scope | Unresolved |
|---|---:|---:|---:|---:|
| Pathway membership | 9,540 | 60 | 28 | 32 |
| GO annotation | 4,078 | 35 | 22 | 13 |
| Protein interaction annotation | 1,576 | 20 | 1 | 19 |
| Expression observation | 1,061 | 15 | 0 | 15 |
| SIGNOR regulatory observation | 290 | 10 | 2 | 8 |
| Drug listing | 174 | 10 | 10 | 0 |
| MAP-IT tissue proximity observation | 120 | 10 | 10 | 0 |
| Disease association | 100 | 10 | 0 | 10 |
| CIViC therapy-response report | 41 | 10 | 2 | 8 |
| **Total** | **16,980** | **180** | **75** | **105** |

All 180 assertions faithfully preserve the examined original source records.
That is an integration finding, not 100% scientific correctness. Of the 75
supported cases, **60 have native-curation support** and **15 have examined
study/dataset support**; shared upstream sources and repeated studies do not
become independent votes. All 180 independent scientific-correctness fields
remain **unreviewed**. No biologically contradicted claim was established by
this audit; unresolved cases are not negatives.

The first completed audit had 64 supported / 116 unresolved cases. A preserved
follow-up used additional Pharos activity context and native ChEMBL records to
resolve the narrow listing scope of ten drug cases. One further case uses the
examined AURKA–p53 study to support a broad functional association while keeping
the specific positive-effect claim unresolved. These are adaptive evidence
follow-ups, not a new biological benchmark or model improvement result.

Ordinary population weights give **43.90% examined-evidence support and 56.10%
unresolved** after those follow-ups, versus 42.41% / 57.59% initially. These
are design-weighted audit-status summaries, conditional on the supplied reviews
and adaptive follow-up. The conditional design
standard error is approximately 4.17 percentage points for the support fraction;
it does not include annotation mistakes or establish a biological confidence interval.
The unweighted 75/180 fraction must not replace the weighted calculation.

## The fixed GO comparison did not touch a sampled case

The preexisting GO policy removes **298 obsolete-ID assertions**, retaining
all nodes and 16,682 assertions. The exact policy, ontology and graph ledger
were rebound and replayed without threshold tuning. **None of the original
180 sampled assertions is removed**, so this sample cannot measure the
benefit or harm of those removals. We did not reseed it to obtain a favorable
comparison. Ontology currentness is not a biological-false-edge label.

A separate, explicitly supplemental **20/298 removed-domain sample**, seed
`2026111202`, was frozen after that observation. Its conditional inclusion
probability is 20/298; it must not be appended to the 180-case global estimate.
The supplement examines source context and replacement support, rather than
recounting the already known obsolete-ID selection criterion as a discovery.

All 20 removed-domain source records remain faithful to their historical
Pharos projection; primary support for those exact historical claims remains
unresolved. Eleven have a unique explicit active replacement proposal. Eight
of those have exact-subject current native annotations, while three do not;
nine have no safe replacement. Five of the eight supported replacement
concepts already exist in the retained graph, and three would require
separately sourced additions. These current annotations are not historical
row identities or independent experiments. The supplement therefore supports
careful vocabulary maintenance, not a claim that 20 false biological
relationships were removed.

The pinned ontology is GO **2026-07-26**, and the compatible native GAF was
generated **2026-07-28** and archived August 5. They were qualified on November
12; they are **not verified as the latest November releases**. Historical
Pharos annotation identity remains unresolved. Explicit replacement proposals
are not applied or used to backfill historical qualifiers.

## A source problem that can be addressed now

The graph has **3,492 WikiPathways evidence rows but only 2,004 exact
target/provider/full-versioned-source groups**. There are 1,488 excess
representations; different local `pwid` identifiers do not represent new
experiments. No rows or versions were silently merged.

The most conspicuous example is RAD21: **1,060 rows represent 103 distinct
versioned pathways**, rather than 1,060 different pathways. The current native
human GMT explicitly lists its gene in six pathways. Three overlap the stored
source set and three are current-only context; none of those new memberships
was automatically added to the protein graph.

We inspected the official TCRD loader and reproduced a cache-mutation defect:
the unchanged WikiPathways loop creates eight protein/pathway assignments from
an invented input with five valid assignments. Its neighboring Reactome loader
already uses the correct cache branch. This is a verified upstream-code issue
and a reusable fix pattern, **not proof that this code version produced the
deployed Pharos records**. The deployed loader and original GMT vintage remain
unknown.

For one sampled RAD21 record, the exact historical native model
`WP4566_r104315` was recovered. It does not explicitly annotate RAD21 or its
gene identifiers. This establishes a source-attribution gap; absence from a
pathway drawing does not prove the protein has no relevant biological role.

### Executed current-source qualification

The optional [qualification adapter](../../tools/sampled_audit/README.md)
executes the two unmodified, hash-pinned **pywikipathways author reader**
functions under their MIT license. The native November 10 human GMT contains
991 pathways and 40,285 unique pathway–GeneID memberships. Exact current
UniProt/HGNC/GeneID cross-references establish a gene-to-protein relationship,
without asserting gene/protein/isoform identity. Versioned WP identifiers
retain an explicit non-equivalent `dcterms:isVersionOf` relationship.

| Current encoded-membership decision | Raw WikiPathways rows | Exact target/provider/versioned-source groups |
|---|---:|---:|
| Present; keep | 1,558 | 1,289 |
| Not listed in the pinned current model; exclude from this view | 1,892 | 685 |
| Missing pathway or unresolved identity; retain as unknown | 42 | 30 |

The exclusions span **31 proteins**. All other source families are unassessed
and retained. The separate exported graph has **9,865 nodes, 15,093 evidence
edges and 15,088 assertions**, with an exhaustive keep/prune/abstain ledger and
the preserved baseline. Every surviving graph payload was independently
recounted against the source. The original workspace is unchanged.

This is an **exploratory current-source eligibility view developed after the
sample**, not a confirmatory biological-pruning comparison. Not being encoded
in today's gene set does not refute historical membership or biological
function. The reusable native-reference builder requires no cohort judgments;
a separate minimal packet reproduces all 991 pathways exactly.

### Restoring shared source context

A further [exact-version normalization](WIKIPATHWAYS_VERSION_NORMALIZATION_20261112.md)
addresses the remaining local-node fragmentation. The 1,600 retained Wiki
rows originally use 1,600 separate local pathway nodes, although they cite
only 275 exact version URLs. A separate source projection represents those
URLs consistently across 76 proteins, retaining all 1,600 evidence IDs and
1,319 distinct protein/version connections. It exposes 1,133 common-object
source contexts that the separate local nodes could not share.

These are `protein → cited model ← protein` joins, not new PPIs, symmetric
memberships or directed protein-to-protein paths. Revisions, uncertainty,
review history and every original source record remain preserved. The app's
normalizer, original sample and earlier scientific comparisons are unchanged.
This repairs source representation; its downstream biological benefit is
untested.

## More useful Pharos context without another aggregator

The existing Pharos ligand API supplies activity rows, chemical identifiers
and references that the thin drug-listing projection omitted. The new bounded
read-only adapter preserves all returned rows and selects the exact original
target accession, with no name substitution. For the ten sampled listings it
captured **575 activity rows, including 173 exact target–ligand rows**.

Native ChEMBL target/component → activity → assay → document joins were
independently checked for all ten cases. Nine selected records share an exact
Pharos publication; they are not independent evidence. The native context
also reveals review articles, homology-based assay target assignments,
mutant/fusion constructs and unspecified organisms. Historical drug listing
does not certify current approval or availability.

The Pharos activity schema does not supply units or scale. For example, a
source IC50-labelled value of 7.66 aligns with native pChEMBL 7.66, while the
native IC50 is 22 nM. The official ChEMBL loader documents this storage pattern.
Raw Pharos values remain unchanged and are not presented as nanomolar potency
or converted through an assumed universal rule.

A detailed AURKA–TP53 site review also separates mouse Ser312 experiments,
the orthologous human Ser315 coordinate, kinase attribution and net protein
effect. A human signed-effect assertion cannot be validated by joining these
contexts indiscriminately. Its primary-evidence outcome remains unresolved;
the original source row is retained and no opposite-effect claim is invented.
The examined 2004 public figure controls can support the separate broad,
unsigned AURKA–p53 interaction annotation. They do not establish the 2013
human positive Ser315 effect. This contrast demonstrates why evidence support
must be qualified at the assertion level instead of copied across an entire
protein pair. The same paper remains one reused evidence source.

## Method fit and remaining scientific boundary

The sampling design follows [Gao et al., PVLDB 2019, §5.1](https://www.vldb.org/pvldb/vol12/p1679-gao.pdf)
and standard [stratified survey variance/FPC guidance](https://ccsg.isr.umich.edu/chapters/sample-design/appendix-c/).
The [SIGMOD 2025 author sampler](https://github.com/KGAccuracyEval/credible-intervals4kg-estimation)
was inspected: its released SRS implementation draws with replacement and
expects complete binary labels, so it was not substituted for this fixed
SRSWOR/UNKNOWN design. The [2026 LLM-stratification work](https://www.dei.unipd.it/~marches1/papers/mcs-vldb-2026.pdf)
also preserves the distinction between sampling signals and credible labels.
No new uncertainty model or self-certified biological judge was introduced.

Native pathway use follows the [WikiPathways primary description](https://pmc.ncbi.nlm.nih.gov/articles/PMC10767877/)
and [pinned official reader](https://github.com/wikipathways/pywikipathways/tree/2e77a5665f8261b56e2ef61d8b0106c220193ac5).
SIGNOR interpretation follows its [4.0 primary paper](https://doi.org/10.1093/nar/gkaf1237)
and official curation guidance; phosphate addition, site function and net
protein response are different assertions.

The remaining high-value scientific gaps are credible independent correctness
judgments, dated source lineage and study-level support for aggregate
associations. The 105 unresolved cases remain visible. More databases or another
unvalidated LLM vote would not close those gaps. We have not demonstrated that
the optional current-source exclusions improve an experimental prediction
task. The earlier mixed/negative learner and kinase-utility results remain
unchanged.

## Reproduction and delivery

The [optional tool guide](../../tools/sampled_audit/README.md) documents sample
preparation, sealed scoring, current-source qualification, native reference
packaging and bounded drug-context retrieval. Core controls use invented
fixtures. A separate integration test executes the actual MIT-licensed author
reader; no model server, GPU or paid literature API is needed.

See the [aggregate receipt](whole_graph_sample_audit_20261112_summary.json).
The complete local report is
`runs/whole_graph_sample_audit_20261112/report.html`; it links individual
dossiers, evidence reviews and separate graph/decision packages. Raw run files
are Git-ignored and retain their source terms. The full baseline includes KEGG
records and is not cleared for public redistribution merely by the software's
MIT license. Only code, licensed reader fixtures and aggregate results are
included in this repository increment.
