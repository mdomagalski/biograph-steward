# Source claims, experimental signatures and an external reference

This follow-up qualifies specific source claims and selects a separate public
experiment for a future comparison. It does not report a new biological
performance gain. The completed kinase comparison and the app graph are
unchanged.

## What the primary review resolved

All five previously flagged SIGNOR records have a source-protein/citation
mismatch. Their literal-accession kinase/site assertions must stay out of a
new inference prior. The original source observations remain preserved; an
identifier replacement would require a separately qualified assertion.

| Claim group | What the accessed primary evidence supports | What remains unresolved |
| --- | --- | --- |
| SIGNOR-171005: MST1 → H2BC3 Ser15 | The paper studies the STE20-like MST1 kinase, not hepatocyte growth factor-like MST1. It also uses generic H2B in a kinase assay/control. | Exact H2BC3 product and canonical Ser15 are not established by the accessed experiment. |
| SIGNOR-277178/-277179: MST1 → PKCα Thr228/Ser226 | The detailed site experiments use Mst2, including an immunoprecipitated kinase preparation. | Mst1-specific catalysis, exact assayed protein accessions and fully purified two-protein catalysis are not established. |
| SIGNOR-114289: MST1 → STK4 Thr183 | The accessible primary abstract describes activation-loop phosphorylation/localization of an MST kinase. | It does not establish the catalytic enzyme, autophosphorylation or exact site/construct. |
| SIGNOR-250265: PDK1 → PKN2 Thr816 | The primary title/abstract explicitly identifies phosphoinositide-dependent PDPK1 and PRK1/2 phosphorylation. | Exact Thr816, construct and assay-control qualification require unavailable primary methods/figures. |

The primary sources are the [MST1/Sirt1 study](https://pmc.ncbi.nlm.nih.gov/articles/PMC3044949/),
[Mst1/Mst2 macrophage study](https://pmc.ncbi.nlm.nih.gov/articles/PMC4618176/),
[MST activation-loop study](https://pubmed.ncbi.nlm.nih.gov/11805089/) and
[PDPK1/PRK study](https://pubmed.ncbi.nlm.nih.gov/10753910/).

The H2B result refines the earlier review: H2B is more than a background mention.
Its experimental use still does not identify a particular histone gene or
justify a mature-protein-to-canonical-site conversion. The inaccessible H2B
supplement was not inferred from its title.

Four kinase-named counterpart records already occur in the old prior. They
share a paper/site with flagged records; they are not independent replications
or automatically validated replacements. The source's `DIRECT=t`, a matching
reference residue and a valid identifier are separate from experiment-specific
support. No whole-node MST1 or PDK1 renaming is justified.

## An existing grounding tool helps when supplied correctly

We checked the official [Gilda service](https://grounding.indra.bio/) rather than
building a new entity grounder. The hosted page advertises **1.4.1**, whereas
the reviewed package documentation describes **1.6.1**; no equivalence between
their builds or resources is assumed. Seven initial development requests used
public names/source sentences, followed by two fixed title-and-abstract checks.

For the inspected MST1 cases, the service ranks the curated STK4 gene grounding
first even without context. For PDK1, the abbreviated source sentence about
pyruvate dehydrogenase incorrectly suggests PDPK1. Using the actual primary
title and abstract instead ranks mitochondrial PDK1 first; PDPK1 remains first
for the PRK paper. The pyruvate context is supported by the
[primary PDH study](https://pubmed.ncbi.nlm.nih.gov/16436377/).

Longer citation context is already supported by the
[Gilda API](https://gilda.readthedocs.io/en/latest/modules/index.html) and
[INDRA grounding integration](https://indra.readthedocs.io/en/latest/modules/preassembler/grounding_mapper.html).
This resolves the observed short-context failure without a new classifier or
prompting scheme. It does not establish general accuracy: the cases were
selected after review, training-paper overlap is unknown, and gene groundings
do not establish protein constructs, sites or catalytic truth. Both the failed
short-context result and the successful citation-context result are retained.
The method is suitable for proposing conflicts for review, not automatic
protein-ID substitution. Its ranking scores are not scientific-truth probabilities.

## Signature eligibility is separate from a direct reaction

The official publisher link for the [Sugiyama in-vitro screen](https://doi.org/10.1038/s41598-019-46385-4)
provided a valid S5 workbook after the NCBI supplement route had returned a
proof-of-work page. Following the publisher's actual supplement link resolved
that access gap. It identifies human EGFR cytoplasmic-domain and full-length MAPK12
constructs, including reference accessions and expression/activation metadata.
Some source lot/catalog labeling and lot attribution remain ambiguous.

The [iKiP reanalysis](https://doi.org/10.1021/acs.jproteome.2c00198) can therefore
support a separately typed kinase-gene-labelled, site-centric in-vitro signature
layer. It does not convert those signatures into endogenous human-cell reactions or independent
validation of the parent experiment. Exact experimental constructs remain
distinct from current canonical proteins.

The [2025 kinase-inference benchmark](https://doi.org/10.1038/s41467-025-59779-y)
supports a curated-first comparator and evaluates iKiP separately. Its minimum
of five measured target sites per kinase is an eligibility rule, not an accuracy
guarantee: a few additional matches do not establish a reliable activity readout.
iKiP is a bounded secondary source, not the default remedy for every missing
score. Reproducing the curated
combination requires the publication-bound artifacts; the published GPS5.0
description and current repository's GPS6.0 wording must not be silently mixed.

iKiP's CC BY-NC4.0 source workbook and row-derived audit remain private and
Git-ignored. No restricted source rows or private candidate match counts are
included here. Sugiyama, iKiP and PTMsigDB representations of that screen count
as one underlying experiment.

## A separate public experimental reference is selected

The [HCT116 CRISPR-knockout study](https://doi.org/10.1080/19768354.2026.2625524)
is selected for a small **exploratory external target/signature-recovery**
comparison. MAPK1/ERK2, PLK1 and PAK4 are the three protein-kinase targets;
PIK3CA is a separate pathway-context endpoint because protein phosphorylation
does not directly measure its lipid-kinase activity.

Selection was frozen before downloading the quantitative workbooks. Exact
author files and visible table headers are now preserved; quantitative outcome
rows have not been decoded for scoring. The S2 workbook's first sheet is a
hidden protein sheet, so a reader must select the exact visible phosphosite
sheet rather than assume that sheet one is the intended data.

This experiment differs from the consumed Hijazi drug study and the Sugiyama
in-vitro screen. The reference still has important limits: stable knockout
adaptation, two biological samples per group in one TMT10plex, unspecified
independent-clone replication and elapsed time, and unverified localization/FDR
thresholds. Paired total-protein data can support an abundance-confounding
check where correspondence is qualified. These limits permit a bounded
exploratory check, not a general scientific-accuracy or catalytic-truth claim.

Do not use the paper's inferred KSEA activities as independent truth. Use its
declared interventions, report all target abstentions, and never label every
other kinase a confirmed negative. Block this study's citation and any linked
parent origin from every input layer. An exact zero citation intersection does
not prove absence of untagged reuse. Prior work on HCT116/BioPlex cell context
is acknowledged; this is not completely blinded biological knowledge.
Search snippets also exposed qualitative study conclusions; the quantitative
tables and author-inferred kinase-score rows were not inspected.

An acute VRK1-degradation study was assessed as a reserve. Its official repository
has conflicting mouse/human processing metadata and no advertised ready-to-use
quantitative matrix in the inspected file manifest. It is held rather than
silently repairing the organism or starting a new raw-proteomics pipeline.

## What is ready and what remains

The five source flags now have scoped primary-evidence dispositions. The
signature construct-access gap is partly resolved, the existing grounding
strategy has been exercised, and a separate experimental reference is selected.
No new model installation, Brev work, app complexity or automatic graph review
state was introduced.

Before the external comparison, freeze the source/signature layers and study
exclusions, measured-site eligibility, exact table/sequence mapping,
protein-adjustment policy and fixed comparator. Then run all three declared
protein-kinase interventions together, retaining every exclusion and abstention.
The old drug study can support development diagnostics only. Biological
performance improvement remains unproven until the new comparison is executed.

See the [machine-readable summary](source_claim_qualification_20261112_summary.json)
for the source, model-check and metadata-selection bindings. Full primary
receipts and privately held author workbooks remain under
`runs/source_claim_qualification_20261112/`.
