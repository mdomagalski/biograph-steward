# Literature gate: qualified Lambourne assay observations

Review date: 2026-10-25. Decision: proceed with a bounded publisher and viewer for
the already audited author observations. This is an evidence-representation
increment, not a new prediction experiment or a claim that graph accuracy has
improved. It does not authorize silently adding unqualified PPI edges to ordinary
Pharos runs or treating this consumed panel as a fresh validation set.

## Established approach and remaining gap

The proposed evidence layer follows an established molecular-interaction curation
model. IMEx records retain the publication, interaction and participant detection
methods, host organism, construct details, modifications and source locations.
Protein identity is represented at the level actually supported by the source,
including isoforms where available. A gene-level pair alone loses relevant
experimental detail. See the consortium's [2020 primary paper](https://www.nature.com/articles/s41467-020-19942-z)
and its [participant curation instructions](https://github.com/intact-portal/intact-portal-documentation/blob/master/docs/curation-manual/participant.md).

Lambourne et al. distinguish binary evidence from co-complex association and merge
duplicate literature evidence using the pair, publication and identical or
ancestor-related PSI-MI method terms. This supports keeping assay observations
separate from aggregate Pharos links, and avoiding the fiction that a second
database is automatically an independent experiment. Their paper also reports
substantial assay sensitivity limitations. See [the paper, Methods and Data
availability](https://www.nature.com/articles/s41467-026-70942-x).

The verified local gap is access to these qualified, traceable observations
alongside the frozen Pharos comparison. The outcome adapter and comparison already
exist; they must be reused. We do not need another extractor, a new confidence
score, or a broad database ingestion to publish this result accurately.

## Existing curated artifact checked first

The paper states that interaction data were submitted through IntAct under
**IM-30553**. That is a study-level accession, not a license to manufacture an
IMEx interaction accession for each local row.

We checked the official, documented IntAct advanced search endpoint,
`POST /intact/ws/interaction/findInteractionWithFacet/body`, including positive
and negative records, without a restrictive MIscore threshold. The public API
specification is available [here](https://www.ebi.ac.uk/intact/ws/interaction/v3/api-docs);
the official [API documentation](https://github.com/intact-portal/intact-portal-documentation/blob/master/documentation/technical_corner/apis.md)
and [MIQL field guide](https://github.com/intact-portal/intact-portal-documentation/blob/master/documentation/user-guide/advanced_search.md)
were inspected.

| Query | Records returned by the index |
| --- | ---: |
| `pubid:32296183` — known HuRI positive control | 162,719 |
| `pubid:41935050` — Lambourne publication | 0 |
| `pubid:IM-30553` | 0 |
| `interaction_id:IM-30553*` | 0 |
| `IM-30553` | 0 |
| `pubid:"10.1038/s41467-026-70942-x"` | 0 |

These checks found no reusable matching records in the queried public index.
They **do not establish that curation has not occurred**, or that this study has
no deposited human records. The official FTP `current` directory served January
2026 timestamps, before the April 2026 publication; its 2026 publication listing
contained an unassigned record but no file named for PMID 41935050. IMExCentral
could not be inspected because certificate verification failed. The old PSICQUIC
URL returned an HTML application shell and was not treated as an empty result.
The basic search endpoint does not interpret fielded `pubid` queries correctly;
only the documented advanced endpoint with a successful positive control is
used in the table above.

Exact requests, response bytes, HTTP statuses, retrieval times and hashes are
preserved in the ignored run directory
`runs/lambourne_assay_evidence_preparation_20261025/source_receipts.json`.
Public-index availability remains a bounded limitation, not a reason to wait
indefinitely or to claim new biological discovery. Reuse the published author
records now, label them as such, and retain IM-30553 as the paper-reported deposit
reference pending a future exact reconciliation.

## Mapping decisions

The [current official PSI-MI vocabulary](https://github.com/HUPO-PSI/psi-mi-CV)
and [MITAB 2.7 definitions](https://psicquic.github.io/MITAB27Format.html)
provide the existing terms and representation model. The retrieved OWL bytes are
saved with a hash; the repository's older OBO file is not assumed to be current.

| Source field or result | Bounded representation |
| --- | --- |
| Y2H assay | `MI:0018` — two hybrid; retain the authors' Y2H-v1 label separately. |
| DB construct | Preserve its CCSB ORF ID and orientation; `MI:0496` bait is the documented two-hybrid role. |
| AD construct | Preserve its CCSB ORF ID and orientation; `MI:0498` prey is the documented two-hybrid role. |
| CCSB construct name | Retain the literal author identifier; `MI:0345` denotes an author-assigned name. Do not invent a public accession namespace. |
| UniProt accession | Preserve the audited source accession and mapping provenance; do not infer an isoform, exact sequence or human tissue context from a gene symbol. |
| Sequence confirmation | Preserve the original branch-specific values and adapter decision; this is not evidence of protein expression or a calibrated confidence score. |
| Detected | A locally typed, source-qualified assay observation, linked to the pair and source row. |
| Not detected | A qualified nondetection observation in this assay; not an unconditional negative interaction. |
| Failed, autoactivating or sequence-unconfirmed | Retain status and reason as non-evaluable observations; never convert to negative PPI evidence. |

Do not assign `MI:1356` (validated two hybrid) merely because a construct passed
sequence confirmation: that term describes more extensive experimental
re-analysis. Do not assign `MI:0407` (direct interaction) automatically. The
[IMEx primary curation paper](https://pmc.ncbi.nlm.nih.gov/articles/PMC3703241/)
reserves that interaction type for evidence of actual contact from in-vitro
methodologies and explicitly distinguishes yeast two-hybrid support. The current
increment uses a local observation predicate rather than claiming a curated
interaction type. A future exchange export would require its own mapping and
validation, with `MI:0915` physical association considered conservatively rather
than promoting the assay into direct-contact proof.

## Negative evidence and duplicate evidence

The [May 2024 IntAct curation manual](https://raw.githubusercontent.com/intact-portal/intact-portal-documentation/master/assets/intact-curation-manual.pdf)
requires experimental support and complementary positive data for its negative
interaction cases. The 2020 IMEx paper additionally describes expression controls
for negative interactors. Our source-specific eligible nondetections do not
establish those full curation requirements. Therefore they stay in the observation
ledger and cannot prune Pharos relationships or become blanket MITAB
`negative=true` entries. Failed assays remain distinct from nondetection.

The [online validator help](https://www.ebi.ac.uk/intact/validator/help.xhtml)
still says negative interactions are outside IMEx. That statement conflicts with
the later consortium paper and current curation manual; it must not be presented
as current scientific policy. Likewise, running a syntax validator would not
certify that these observations were curated by IMEx.

The [IntAct duplicate-data guidance](https://github.com/intact-portal/intact-portal-documentation/blob/master/docs/curation-manual/special-cases.md)
identifies the primary publication when data are represented in multiple studies.
For this single panel, preserve source-row identity and all raw locators; do not
count supplementary-table and raw-file appearances as independent experiments.
AD/DB orientation and assay context remain part of observation identity even
when the protein-pair lookup is unordered.

Existing reusable exchange tooling includes [PSI-JAMI](https://github.com/MICommunity/psi-jami)
(Apache-2.0; Java readers/writers for PSI-MI XML and MITAB) and the
[PSI-MI validator](https://www.ebi.ac.uk/intact/validator/start.xhtml). A new
exchange framework or dependency is unnecessary for the bounded local viewer;
these tools should be considered if a later increment actually exports PSI-MI.

## Fixed acceptance criteria and stop point

1. Reuse the sealed, replay-verified comparison and preserve all **3,222** selected
   author pairs, including every nondetection and non-evaluable observation.
2. Preserve participant roles, source identifiers, assay and construct context,
   confirmation values, original result, qualification decision, study and row
   provenance. Show unknown context explicitly rather than inferring it.
3. Preserve the frozen baseline and comparison bytes. Verify the derivative
   against them; do not rerun the assessment as if it were unexposed.
4. Make no automatic pruning decisions and no unconditional positive or negative
   biological assertions from these assay rows.
5. Report the 42 detected pairs without a scoped Pharos match as bounded evidence
   candidates, not globally novel discoveries or an independent accuracy gain.
6. Publish one inspectable derivative/report and stop. No additional source,
   learner, prompt search or GPU run is required for this increment.

This closes the literature gate for a traceable observation publisher. It does
not close independent biological validation of a changed graph. Any subsequent
claim of predictive or scientific improvement needs a separately justified
reference and evaluation design; this panel is already consumed.
