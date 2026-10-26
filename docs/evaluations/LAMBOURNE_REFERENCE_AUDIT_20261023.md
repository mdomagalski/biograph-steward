# External human interaction reference: identity and source audit

October 23, 2026. **This is a usable external-study candidate, but it is not yet
a qualified independent performance test.** We reproduced its 3,222 published
nominations, checked their identities against our saved inputs, and recovered
the authors' preprocessing. The new assay outcome values remain undecoded.
No model, Brev instance, fresh Pharos pull or biological scoring was used.

**Subsequent follow-up:** the separate [focused Pharos lookup](LAMBOURNE_PHAROS_LOOKUP_20261023.md)
has now queried the full accession inventory. It finds 2,325 represented pairs,
including all 647 below. This report preserves the earlier scoped result;
neither increment decoded assay outcomes or established study independence.

## What the audit establishes

The [Lambourne study](https://www.nature.com/articles/s41467-026-70942-x) tests
human interaction predictions in Y2H-v1. Its human panel should not be confused
with the paper's yeast GPCA/MAPPIT validation. The human figure caption's v4
label conflicts with the Methods and author filenames, which support v1.

The pinned [official repository](https://github.com/CCSB-DFCI/ai-interactome-experimental-assessment/tree/fb05ab3ca2cc0fcaf402bb0df568e95a5158178b)
and publisher Supplementary Data 22 have the same nine-column schema. The
repository export contains 4,775 rows, including controls and prepublication
nominations. Selecting both `source_dataset` columns as `Zhang_et_al` and
`in_published_version=True` gives exactly **3,222 distinct unordered UniProt
pairs, 3,173 proteins, no self-pairs and no duplicate pairs**. This uses only
identities and nomination metadata, not assay eligibility or outcomes.

Every published nomination agrees with the supplied experimental-ORF crosswalk
under an unordered comparison. UniProt A/B are alphabetically ordered, not
AD/DB assignments; the author code establishes this convention. The Ensembl
crosswalk is less complete: 2,914 pairs have single-gene mappings at both ends,
294 have an ambiguous endpoint, and 14 have a missing endpoint. These mappings
flag potential gene-level overlap; they do not establish equivalent isoforms.

Controls remain separate. Two control rows lack a UniProt identity, and 179
whole-export rows do not reconcile to the supplied ORF map. The historical
export also uses private control mappings, so those discrepancies do not prove
incorrect source records. No private database was accessed or control mapping
invented.

## Existing-input overlap

We verified the saved Pharos manifest and every chunk, then reconciled raw and
retained PPI counts per queried protein. The audit uses all **203,054 raw PPI
views**, including neighbors outside the original inventory, not only the
23,968 retained views. Those retained records are 11,984 unordered pairs.

| Published nominated pairs | Count | Interpretation |
|---|---:|---|
| Present in saved raw Pharos PPI responses | **647** | Existing representation; not proof of the same underlying experiment |
| Present in the smaller retained Pharos graph | 146 | Using this graph alone would miss 501 already retrieved matches |
| HuRI match under either checked gene/product mapping | **442** | Potential training exposure; mappings are not construct equivalence |
| Previously evaluated INMC pair under either mapping | **7** | Previously consumed reference-pair overlap |
| Not found, both endpoints previously queried | 38 | Absence only under the declared API profile |
| Not found, one endpoint previously queried | 207 | Same bounded absence, with asymmetric retrieval coverage |
| Neither endpoint previously queried | **2,330** | Unassessed in this archive; cannot be called new to Pharos |

The first four rows overlap and must not be added. The 647 observed, 38
both-queried absent, 207 one-queried absent and 2,330 unqueried categories form
the complete 3,222-pair partition. Only **432 of the 3,173 proteins** were
queried previously; 2,741 need a separate lookup to assess this whole panel.

Using the frozen reviewed-product registry flags 442 HuRI matches; the authors'
Ensembl crosswalk flags 440, with union 442. Both flag the same seven INMC
matches. Many-to-many mappings remain explicit instead of selecting a convenient
gene or collapsing original identities.

Only **20 pairs** have both endpoints queried and no observed overlap through
any checked route. This is an exposure diagnostic, **not** an approved test set,
sample-size justification, or certification of independent evidence. The 2,342
pairs without any observed pair overlap include unassessed Pharos coverage.

## Reusing the authors' definitions

The latest tree lacks the human raw-to-processed transformation. We recovered it
from the [historical author script](https://github.com/CCSB-DFCI/ai-interactome-experimental-assessment/blob/ec477f7043195c46ce1787cbd7e09fd407d21b97/notebooks/generate_supplementary_data_tables.py#L139).
Its [removal commit](https://github.com/CCSB-DFCI/ai-interactome-experimental-assessment/commit/2da299c4e3756939e5ab9c2b3b7a4a0f9dec30c6)
explains that it reads an internal database. We preserved a nonexecuted excerpt
and source hash. This resolves a documented implementation gap without a custom
scientific labeling rule:

- Assigning a new `source_dataset` and renaming `category` creates duplicate
  headers. We retain both by position; they agree on all 4,775 rows.
- The export distinguishes `Positive`, `Negative`, `Test failed`,
  `Autoactivator`, and `Failed sequence confirmation`.
- Positive and negative raw results use different sequence-confirmation fields.
  The code rejects confirmation equal to False; its nullable edge case remains
  untested on the actual rows. Universal sequence confirmation is not established.
- Export occurs before published-nomination filtering and control-orientation
  selection. The processed file favors nonmissing control results and deduplicates
  unordered ORF pairs after a fixed shuffle. Controls must not be treated as a
  representative sample or pooled into the primary nominated population.

Only explicit Positive/Negative states are candidates for a future evaluable
endpoint, subject to a frozen mechanical consistency check. Negative means
nondetection under this assay. No outcome adapter or performance runner was
added in this increment.

## Independence and baseline limitations

The [Zhang nomination study](https://pmc.ncbi.nlm.nih.gov/articles/PMC13281779/)
uses UniProt cellular-compartment keywords and prior interaction evidence from
sources including STRING and BioGRID. The resulting panel is conditioned on
existing biological information. This is not proof of exact duplication of our
GO features, and it cannot establish proteome-wide performance.

The saved Pharos source catalog identifies providers, but not their imported
release versions. No study-level reference properties appear in the retrieved
PPI projection. Source labels therefore cannot certify that the new experiment
or its derivatives are absent from Pharos. Conversely, direct pair overlap does
not prove contamination from this experiment: separate measurements of known
pairs can still be informative corroboration.

STRING's score concerns association; its [documentation](https://string-db.org/help/getting_started/)
distinguishes evidence channels. BioPlex AP-MS probabilities have different
[documented meanings](https://ccb-hms.github.io/BioPlex/articles/BioPlex.html).
They must not be pooled into a calibrated probability of Y2H detection. The
reviewed Pharos resolver applies its 400 threshold to STRING-only rows and
omits zero-valued score properties through truthiness checks. Mixed-source
records and missing scores therefore need explicit handling. The pinned source
code is consistent with saved records, but is not an attestation of the deployed
API commit.

## Decision and next bounded work

**Do not score this as a new independent improvement comparison yet.** Keep it
as an external assay-validation candidate. The verified remaining work is:

1. Perform one declared PPI-focused lookup for the 3,173 exact author accessions,
   preserving unresolved identities, count limits and source receipts. Keep the
   new retrieval separate from the immutable INMC baseline. A prepared identity
   inventory is saved locally; this retrieval has not started.
2. Establish an existing-Pharos lookup comparator with separate provider scores.
   Preserve observed, unqueried, unresolved and bounded-not-found states; none
   of the latter states is a measured negative.
3. Use upstream evidence records and version metadata to assess study overlap.
   STRING already provides [evidence-set and publication linkage](https://string-db.org/help/database/).
   If the actual imported release/lineage cannot be established, disclose that
   uncertainty and call the result supporting external corroboration, not a
   certified independent prediction test.
4. Freeze the candidate strata, assay consistency checks, exclusions and matched
   comparison before decoding outcomes. Existing-knowledge corroboration and
   novel-link prediction answer different questions. Selecting only pairs absent
   from Pharos would make a direct-presence comparator constant by construction;
   it would not establish improvement over the whole existing graph.

The prior restricted GO comparison remains unchanged and must retain its narrow
name. This audit found a coverage/provenance problem to resolve, not a reason to
try another model or claim that the proposed source adds new biological facts.

## Artifacts and validation

- [Reproducible audit](../../scripts/audit_lambourne_reference.py) reuses existing
  Pharos receipt verification, source iterators and registry mapping. The new code
  is an identity/exposure join, not a new annotation or assay protocol.
- [Aggregate receipt](lambourne_reference_audit_20261023_summary.json) records
  versions, source/output hashes and counts. Full source files stay in ignored
  `runs/lambourne_reference_audit_20261023/`.
- Final identity audit: `identity_audit_v3/`; earlier attempts remain preserved.
  The initial orientation-specific ORF check was corrected using the author code,
  and incomplete/unresolved coverage handling received regression tests.
- **20 synthetic tests passed**, including deliberately undecodable outcome
  fields, ambiguous mappings, raw-versus-retained exposure, per-protein count
  reconciliation and source-integrity failures. No real new assay labels were
  decoded to perform these tests.
- Repository MIT license was inspected. This does not grant redistribution rights
  to every third-party input or the Pharos source records. This change distributes
  aggregate findings and synthetic tests, not the experimental outcome table.

See the [scripts guide](../../scripts/README.md) for the local reproduction command.
