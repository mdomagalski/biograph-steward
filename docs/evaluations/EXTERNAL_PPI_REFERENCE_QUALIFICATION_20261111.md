# External PPI reference qualification — November 11, 2026

**Qualification complete; no independent biological score reported.** MAP-IT is
the selected reference for further controlled preparation because it matches the
original colorectal-cancer application. Its processed results remain unopened.
The current graph captures do not establish separation from its public data.
A verified historical input is required before the proposed independent test.

## Peroxisomal iBRET has too little contrast in the current graph

The CC BY 4.0 author identity inventory contains 98 construct rows and 92 explicit
base UniProt accessions. We extracted identity fields only, excluding annotation
scores. Its bytes and archive checksum are unchanged.

Only **10 accessions** occur in the frozen 3,172-protein PPI graph. Their 45
possible unordered, distinct-accession pairs include 33 source pairs: 19 eligible
and 14 protected. Native selection retains 32; NE retains 33. The only potential
policy contrast is **AGPS–PEX19 (O00116–P40855)**. No NE-removed pair occurs in this
inventory. Regardless of the unopened outcomes, this candidate can distinguish
the unchanged policies on at most one pair. This cannot support a broad
superiority claim.

These are potential accession-level counts, not tested/QC-qualified assay
denominators. Six construct groups share base UniProt identifiers; clone/transcript
IDs are not UniProt isoform suffixes. The source literal `BCfake` remains unresolved
for sequence identity. Exact identifier correspondence does not establish
construct equivalence. Existing SSSOM correspondence and frozen global decisions
were reused without isoform collapse, NE recomputation or subgraph rethresholding.

Repository history contains outcome-named files in April 2023, so the 2026 paper
date cannot establish first measurement availability. The assay measures cellular
proximity; its published gene network merges isoforms. Its aggregate interactome
and calibration controls are not independent truth. [Study](https://pmc.ncbi.nlm.nih.gov/articles/PMC13324248/),
[author archive](https://zenodo.org/records/20443272).

## Existing graph scopes

| Scope | EGFR/P00533 among seeds? | Canonical PPI pairs | Capture |
| --- | --- | ---: | --- |
| Original Pharos CRC disease workbench: 99 seeds | Yes | 718 | October 14 |
| CRC growth panel: 512 resolved products | No | 1,975, previously audited | October 20 |
| Human Y2H-derived comparison: 3,172 resolved products | No | 89,665 | October 24 |

The original disease-first 99-target run predates the Lambourne-derived scope.
Its ordinary source-run verification passed with graph digest
`ec17705538a0f0d2166187e0fa0505ee3f78b05c5d7745c3a5e44460898ccfde`.
It has 46 EGFR-incident PPI pairs, complete bounded retrieval, source locators and
reciprocal records. Of 718 PPI pairs, **624 are exact STRINGDB-only** and **94 are
protected mixed/non-STRING**. All 717 STRING-containing pairs have valid agreeing
reciprocal scores.

This is a useful existing biological cohort. It has no prepared native/NE pruning
views yet. Its other disease, pathway and CIViC evidence must stay distinct from
the PPI method inputs. Missing a reference protein from an induced cohort does
not mean it is absent from all Pharos.

## MAP-IT: biological fit and available artifacts

MAP-IT examines antibody-directed proximity labeling in primary human tissue,
including EGFR in colorectal cancer. It measures proximity enrichment, rather
than establishing universal direct binary binding. This fits a bounded
proximity-evidence retention endpoint on the original disease-first cohort.
[Primary study](https://doi.org/10.1038/s41467-026-79134-z).

- Raw data: MassIVE **MSV000101185**, ProteomeXchange **PXD075907**, publicly
  announced **October 5, 2026**.
- Processed data: Figshare item **31820131**, published **October 6**, 26 listed
  files under **CC BY 4.0**. EGFR colon protein/precursor matrices, sample keys and
  figure source data are available. No experimental table was opened.
- Author analysis: Zenodo **23181000**, v1.0.0, **CC BY 4.0**. The code archive
  checksum was verified; scripts were inspected for schemas and model semantics,
  and were not executed.

These releases precede even the original October 14 graph capture. The November
3 journal date cannot establish independence. Neither this timing nor an earlier
filename proves actual ingestion by Pharos. The captured API rows supply no
study-level import cutoff.

The EGFR analysis uses seven patients, 14 tissue blocks, antibody controls,
repeated measurements, peptide/completeness filters and `duplicateCorrelation`.
The baseline is Primary and the antibody contrast is **Isotype−Primary**:
**negative `Beta_Ab` indicates primary-antibody enrichment**. Reversing the sign
would invert the biological interpretation. The script exports adjusted `Q_Ab`
but does not define a complete binary reference gate. Generic plotting defaults
from another analysis must not substitute for this endpoint. Any later reference
criteria must be justified and fixed before opening tables.

[Official raw metadata](https://proteomecentral.proteomexchange.org/cgi/GetDataset?ID=PXD075907&outputMode=XML),
[processed-data share](https://figshare.com/s/768781da5c392c2dd40a),
[author code](https://zenodo.org/records/23181000).

## Bounded checks of newer publications

Four focused primary-literature queries produced four nominally later candidates.
Their verified histories did not establish whole-study first availability after
the current captures:

| Candidate | Earlier public record |
| --- | --- |
| Cell-surface nanoscale map, journal October 28 | February 17, 2025 preprint; v2 October 23, 2026 |
| FlAsH-ID, journal November 11 | October 24, 2025 preprint |
| Microprotein FlashID, journal November 4 | PXD078337 publicly announced May 14, 2026 |
| MAP-IT, journal November 3 | PXD075907 announced October 5; processed data October 6 |

Dataset announcements do not establish every current experiment/file's release
date. A later-added subset would require version-specific evidence. None was
invented, and no supplementary result table or raw MS file was opened. These
findings do not prove contamination; they prevent a temporal-independence claim
based only on recent publication dates.

## Selected next route

**Keep MAP-IT for controlled historical-source preparation on the original
99-target CRC cohort. Close the reference search.** The official NCATS archive
lists `pharos319.sql.gz` dated **April 29, 2024**, compressed size **2,257,847,063
bytes**. A verified historical Pharos artifact could supply an older input while
keeping Pharos as the baseline resource. It has not been downloaded or replayed
in this step. Its bytes, internal build metadata and extracted graph must be
verified before claiming temporal separation.
[Official archive](https://opendata.ncats.nih.gov/public/pharos/archive/).

Before a new score:

1. Bind the historical source and existing disease-defined target list. Preserve
   absence, protected bundles and original source records. Matching `pharos319`
   labels do not establish that a live capture equals an archive.
2. Reuse the published NE implementation and fixed 80% eligible-pair budget on
   that separately declared source, with original/native/NE comparators. This
   would be a new comparison and would not change the completed Lambourne result.
3. Fix MAP-IT reference criteria, protein-group identity, missingness and sampling
   structure using its own model. Positive-only retention cannot establish
   pruning precision, false-edge correction or direct binding. A binary cutoff,
   if used, must be explicitly justified before seeing the result.
4. Check outcome-blind coverage and policy contrast, bind reference artifacts,
   then record outcome access. Do not tune versions, thresholds or endpoints on
   its result.

The existing archived STRING 12.0 adapter is a fallback for a differently scoped
historical method control. It would not certify the live Pharos graph. No version
sweep or fallback execution is selected.

## Exposure and verification

Peroxisome identity extraction opened no assay outcomes. MAP-IT method review
incidentally encountered illustrated EGFR–ENG and EGFR–PECAM1 pairs in a figure
caption. Another article metadata view returned named examples and aggregate
findings. These exposures are logged; the article review is not described as
wholly outcome-blind. No deposited experimental table, new performance metric,
graph change or policy change followed.

- [Identity preflight and frozen-edge commitments](../../runs/peroxisome_reference_qualification_20261111/identity_preflight/identity_preflight.json).
- [Independent count/parser verification](../../runs/peroxisome_reference_qualification_20261111/identity_preflight/verification.json).
- [Existing graph-scope facts](../../runs/peroxisome_reference_qualification_20261111/identity_preflight/scope_fact.json).
- [Source-cutoff qualification](../../runs/peroxisome_reference_qualification_20261111/source_cutoff/qualification.json).
- [Bounded reference decisions](../../runs/peroxisome_reference_qualification_20261111/source_cutoff/alternatives.json).
- [MAP-IT processed-artifact contract](../../runs/mapit_reference_qualification_20261111/study_contract/processed_metadata/processed_reference_contract.json).

The run artifacts are local and supplied separately from a fresh clone. No Brev,
language model, new paid compute, production deployment or graph publication was
used in this qualification.

## November 12 follow-up

[Complete source verification](PHAROS_TEMPORAL_BASELINE_20261112.md) resolved the
source-cutoff gap without substituting a different baseline: the existing CRC99
PPI computational input exactly matches the April 2024 archive. The original
qualification above is preserved as the decision history. The follow-up records
the fixed comparison and subsequently detected reference-lineage issues.
