# Biological improvement assessment, November 12

The completed comparison shows a small, bounded improvement in retaining
author-reported OpenCell coassociations at the same pruning budget. It does not
establish whole-graph accuracy, pruning precision, direct binding or a
colorectal-cancer prediction benefit. A separate CRC workspace now exposes
source-reported regulation, experimental context and literature qualifications
without changing the original Pharos records.

## Experimental reference result

The preselected primary ranks organism-native STRING experimental support,
then native combined confidence, then the canonical pair identifier. Controls
and budgets were fixed before the first reference outcomes were opened. No
learner, label fitting, channel recombination or outcome-selected threshold is
used. The published Network Enhancement and edge-masked MPS implementations
provide additional comparators; MPS is exploratory.

| Fixed graph view | Strict positive pairs retained | Entry-family sensitivity |
| --- | ---: | ---: |
| Original source graph | 284/284 | 385/385 |
| Organism-native experimental support, fixed primary | **272/284 (95.8%)** | **364/385 (94.5%)** |
| Native combined STRING confidence | 269/284 (94.7%) | 359/385 (93.2%) |
| Degree-product control | 258/284 (90.8%) | 344/385 (89.4%) |
| Network Enhancement | 272/284 (95.8%) | 364/385 (94.5%) |
| Edge-masked MPS, exploratory | 267/284 (94.0%) | 353/385 (91.7%) |
| Experimental support including transfer, exploratory | 277/284 (97.5%) | 376/385 (97.7%) |

Each ranked view retains exactly **65,132 of 81,416 eligible pairs** and all
8,249 protected or quarantined pairs: **73,381 total pairs** among 3,172 source
proteins. Relative to native confidence, the primary rescues four strictly
mapped positives and loses one. All nine distinct discordant cases across both
identity scopes were inspected. Network Enhancement ties the primary on these
micro-retention endpoints. The better exploratory transfer-channel result does
not replace the primary after evaluation.

The current check uses the author's pinned **29,922-row processed OpenCell
table**, with explicit target ENSG and per-call prey accessions. Its SHA-256 is
`a9422ca12b8b5fce52439f247a7439fbc693cb34b4ca45ced597aa02d267e376`.
Author portal code links this export to Supplementary Table 4; binary equality
to the final journal supplement has not been independently certified. Most
rows remain outside strict mapping because a protein group has multiple
possible identities. Missing and ambiguous identities never become negatives.
Entry-family projection is a declared sensitivity, not exact isoform,
sequence, gene-of-origin or construct identification.

This is a **same-study QC correction**, not another untouched confirmation.
The initial, separately preserved October 2021 figure-data assessment had
292 eligible positive pairs and retained 281 for the primary, 276 native,
264 degree-product and 277 Network Enhancement. It was evaluated once after
selection freeze. Its source artifact is not asserted equal to the final
processed interactome. The correction changes neither original rankings nor
the primary, and does not erase that assessment.

OpenCell measures IP-MS coassociation in HEK293T cells. The reference contains
author-called positives, not a qualified complete negative set. Pair and bait
counts do not imply independent samples. There is no accuracy, precision,
specificity or clinical claim. The tiny original CRC overlap showed no
between-view difference and cannot support a CRC-specific improvement claim.

Sources: [OpenCell primary study](https://doi.org/10.1126/science.abi6983),
[author processed table](https://opencell.sf.czbiohub.org/data/datasets/opencell-protein-interactions.csv),
[pinned original figure-data artifact](https://github.com/czbiohub-sf/2021-opencell-figures/blob/e0bedae07e6c1870f54c501bfa9a9120c8c38e09/data/ppi_analysis/precision_recall/opencell.csv).

## Why the historical source is defensible for this question

All 89,665 original pairs, provider assignments and native weights match the
complete archived PPI source used here. Of 88,073 weighted STRING pairs, 87,729 match the
fixed December 2018 STRING v11 file exactly. The later archive date alone was
not treated as evidence of temporal independence.

The qualification excludes 344 unattested weighted records and 41 weighted pair
records affected by two noninjectively mapped participants from every ranking adjacency.
Affected original records remain in the retained graph as abstentions. The
result is 87,688 qualified weighted background pairs and 81,416 rankable pairs.
Historical STRING loaders and identifier changes do not justify silently
forcing a current mapping onto old scores. This source restriction enables a
later-study test; it does not suggest that the historical graph should replace
the current source layer in the app.

Sources: [STRING v11 paper](https://doi.org/10.1093/nar/gky1131),
[published Network Enhancement](https://doi.org/10.1038/s41467-018-05469-x).

## Structural safeguard and actual graph delivery

A subsequent development check adds one shared native-score maximum spanning
forest to all six rankers, then fills each unchanged budget in its original
order. NetworkX supplies the established implementation. The shared native
prior is explicit; this is not a prior-neutral method comparison. The forest
requires 763 eligible connections after contracting mandatory retained edges.
It restores all original connected components with 29 primary-view
replacements, retaining the same 73,381 edges and 3,172 nodes. The primary's
27 newly isolated proteins are avoided. Network Enhancement already contains
the forest and is unchanged.

This is a development safeguard after observing structural loss. Rechecking
the consumed reference is descriptive, not new independent confirmation.
Connectivity preservation does not prove biological correctness.

The unguarded primary and native graphs have been materialized and fully
replayed using the existing Gold packet APIs on the running Brev instance.
Both include the complete baseline and an exhaustive ledger: 65,132 keep,
16,284 prune and 8,249 abstain. The downloaded archive's 65 files and about
9.99 GB of uncompressed contents passed streaming hash/inventory verification.
No large graph was silently substituted with a summary-only export.

Source: [statistical limits of global weight thresholds and network backbones](https://doi.org/10.1073/pnas.0808904106).

## CRC biological interpretation

`crc_biological_workspace_20261112` has 9,865 entities and 16,985 evidence
records, retaining the 99 primary Pharos targets. Every original node,
evidence record and assertion matches the baseline exactly. The additions are
858 versioned STRING records, 120 qualified MAP-IT tissue-proximity observations
and **290 SIGNOR regulatory records**. They remain candidates.

The SIGNOR records cover 95 distinct nonself endpoint pairs: 82 already occur
in the original scoped Pharos graph. Of the other 13, seven already occur in
the added STRING layer, leaving **six additional endpoint pairs** beyond the
combined original/STRING/MAP-IT workspace. Directed mechanisms and conditions
remain useful additions for shared pairs. Endpoint overlap is not claim
equivalence or independent study support; the layer counts must not be summed
to estimate unique relationships. Each adapter's prepared overlap summary is
relative to the original baseline, before the layers are composed.

SIGNOR preserves direction, effect, mechanism, residue, sequence, source
directness, cell/tissue context, publications and source experimental organism.
Its experimental organism is distinct from the human participant identifiers:
SIGNOR explicitly maps some nonhuman results to human orthologues. Treating
TAX_ID as participant taxonomy would incorrectly omit 59 records here. No
unknown assay host, identity or mechanism is guessed.

Twenty-four records have source-bound, agent-assisted literature notes; 266
are explicitly unexamined. These notes qualify interpretation and never
automatically validate or prune an assertion. Examples include BRAF inhibitory
autophosphorylation with variant/construct limits, EGFR beta-catenin kinase
assays, a citation-direction mismatch and inhibitor-dependent MCC
phosphorylation in CRC cell models.

The MCC–PRKDC association already occurs in the saved STRING 12.5 capture at
0.292, below the workspace's 0.4 inclusion threshold. Its experimental channel
is 0.28 and physical score is unknown. The new layer supplies source-reported
direction, sites and experimental context; it is not presented as discovery of
a previously unknown pair. Reuse of the underlying study is still unresolved.
The paper reports partial inhibitor effects and does not establish purified
PRKDC direct catalysis at every reported site.

Sources: [SIGNOR portal and current documentation](https://signor.uniroma2.it/),
[MCC primary study](https://pubmed.ncbi.nlm.nih.gov/21779472/),
[BRAF inhibitory phosphorylation study](https://pubmed.ncbi.nlm.nih.gov/27345148/).

## Unresolved and negative results

- The previous Lambourne superiority gate remains failed; the MAP-IT pruning
  endpoint remains unscorable. Those results are unchanged.
- MPS raises local ranking AP on consumed development data but loses many
  source-present detections at the fixed global budget. It is not promoted.
- A proposed structure-backed Complex Portal reference stopped **before
  protein-member access**: recent primary-structure citations alone do not
  certify that every curated member belongs to that experiment. Only two of
  24 selected records explicitly linked the exact primary PDB as whole-complex
  identity, below the fixed five-paper coverage floor. Resolving the
  membership-to-experiment boundary is required before a fresh pair-level
  claim. No result is manufactured by relaxing the floor.
- Whole-graph error rates, removal precision and CRC-specific predictive gain
  remain unestablished. Imported source records cannot independently validate
  their own integration.

## Reopen and reproduce

In the app, open **Compare & assess → Experimental reference comparison**.
This historical source-graph comparison is distinct from the selected CRC
workspace. Its report and original/current protocol downloads preserve the
assessment boundaries. In **Evidence & sources**, select **Regulation and
experimental context** and the MCC, BRAF or citation-scope preset.

The saved data are outside Git. Public result packets contain aggregates and
commitments; native OpenCell tables and row-level ledgers are not redistributed
without verified source terms. Core code uses Python 3.10+ and no new runtime
dependency. Republish the aggregate view from the saved inputs:

```sh
python -m biograph_steward biological-comparison-publish \
  --assessment runs/biological_improvement_8h_20261111/opencell_results \
  --frozen runs/biological_improvement_8h_20261111/opencell_frozen \
  --qualification runs/biological_improvement_8h_20261111/qualified_input \
  --selection runs/biological_improvement_8h_20261111/preselected_views \
  --processed-qc runs/biological_improvement_8h_20261111/processed_opencell_qc \
  --out runs/my_experimental_comparison
```

Durable machine-readable receipts are under
`runs/biological_improvement_8h_20261111/`. No language-model inference was needed
for these results. Brev supplied existing CPU/memory for the pinned published
method and full graph publication; no additional compute instance was created.
