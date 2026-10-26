# Focused Pharos PPI lookup for the external human panel

October 23, 2026 (America/New_York; source receipts use October 24 UTC).
**The lookup is complete: 2,325 of the 3,222 published nominated pairs (72.2%)
are already represented in the queried Pharos PPI profile.** The earlier scoped
archive exposed only 647. This closes a retrieval gap; it does not demonstrate
biological improvement or establish an independent test set.

## What was retrieved

The existing Pharos inventory client queried all **3,173 exact author UniProt
accessions** from the outcome-blind [identity audit](LAMBOURNE_REFERENCE_AUDIT_20261023.md).
It used `https://pharos-api.ncats.io/graphql`, database label `pharos319`, the
existing confidence filter of 400 and a limit of 5,000 neighbors per protein.
PPI rows alone were requested; the existing metadata query also returned counts
for other families. No disease filter or gene-to-protein substitution was used.

- **3,172 accessions resolved exactly.** `Q5TEC6` returned null. There were no
  identity redirects. Both nominated pairs involving this accession remain in
  the report, with incomplete identity coverage.
- **552,451 directional raw PPI records** were saved, including neighbors outside
  the panel. **179,330 records** were retained within the full 3,173-accession
  inventory, including links across retrieval chunks.
- All 3,172 resolved proteins reconciled against the actual metadata and PPI
  response counts. No cap, count mismatch or incomplete page was observed.
- The 64 chunks contain 2,033 successful source responses, plus two initial
  version/catalog responses. Before/after version checks stayed at `pharos319`.
  This is a bounded API snapshot, not the complete Pharos database or an atomic
  upstream transaction. Provider import releases are not certified by that label.

The new snapshot is separate from the prior INMC retrieval and comparisons.
The prepared inventory's historical `retrieval_started=false` field is preserved;
the new retrieval manifest records completion. Assay outcomes remain undecoded.

## Pair-level result

| Published nominated pairs | Count |
|---|---:|
| Present in current raw and retained Pharos PPI responses | **2,325** |
| No match under this profile, both endpoints resolved | **895** |
| No match under this profile, one endpoint unresolved | **2** |
| Total, with no candidate removed | **3,222** |

All 647 previously observed Pharos pairs reappear. The fuller lookup reveals
**1,678 additional existing-Pharos matches**, not new biological interactions.
Every matched pair appears in both query directions with the same provider
bundle; its 4,650 directional views are not independent pieces of evidence.

| Exact provider bundle on matched pairs | Pairs |
|---|---:|
| STRINGDB | 1,376 |
| BioPlex,STRINGDB | 571 |
| Reactome,STRINGDB | 237 |
| BioPlex,Reactome,STRINGDB | 121 |
| BioPlex | 20 |

These bundle categories partition the 2,325 matches. They do not count distinct
supporting studies. The earlier **442 HuRI** and **seven INMC** potential pair
overlaps remain attached using both reviewed mapping routes. After combining
current/prior Pharos and those routes, 827 pairs have no observed overlap; 825
have both endpoints resolved. These are diagnostic strata, not a newly approved
test cohort. Missing source matches do not establish biological negatives,
novelty, assay eligibility or study independence.

## Source qualifications and existing capabilities

The lookup keeps the complete `TargetNeighbor.props` list and separates
distributions by exact provider bundle and property name. `Novelty`, TDL and
family remain target metadata. [STRING documents functional associations](https://string-db.org/help/getting_started/),
whereas [BioPlex documents its AP-MS classifier quantities](https://ccb-hms.github.io/BioPlex/articles/BioPlex.html).
Their scores are not pooled into a probability of binary Y2H detection.

The [reviewed Pharos query implementation](https://github.com/ncats/pharos-graphql-server/blob/3feb5ac7e450b3c6b767651f0fe1f39994085380/src/TCRD.js)
applies its threshold to STRING-only rows, not mixed-source bundles. Consistently,
matched STRING-only scores start at 0.4, while BioPlex/STRING matches include a
STRING score of 0.15. Those records are not a filtering failure.

We checked supported alternatives before assuming metadata was inaccessible:

- All 552,451 raw records were inspected. Their property names contain no
  `Evidence`, publication, PMID or reference field.
- The existing `listCrossDetails` Target/Target query exposes explicit
  `evidence`, `interaction_type`, nulls and zeros. Five pairs, selected by
  provider bundle without assay outcomes, returned null evidence and interaction
  type. One explicit `p_wrong=0` was recovered. The
  [property resolver](https://github.com/ncats/pharos-graphql-server/blob/3feb5ac7e450b3c6b767651f0fe1f39994085380/src/resolvers.js)
  omits numeric zeros through truthiness checks; missing properties must stay
  missing. The separate detail probes did not change the frozen lookup.
- An unkeyed `dataVersions` request for P01116 returned five source categories,
  with no PPI provider versions. This checked response is not proof that every
  possible API or upstream metadata route lacks them.

The five probes do not prove evidence is null for every source record. They do
show that simply switching to the available details query did not recover study
lineage in those examples. The public code commit is an implementation reference,
not an attestation of the deployed server commit.

## Consequence for the next comparison

Use the saved pair lookup as the explicit existing-Pharos comparator. Before
opening outcomes, audit source releases and study lineage through upstream
records, including STRING's existing [evidence-set/publication links](https://string-db.org/help/database/).
Keep corroboration of already represented pairs separate from potential
novel-link testing, and freeze assay eligibility/exclusion rules and comparator
definitions using the authors' methods. The selected panel remains conditioned
on its nomination process; it cannot establish proteome-wide performance.

If imported study lineage cannot be established, describe the future result as
external assay corroboration with unresolved source overlap. A pair absent from
this thresholded profile is not automatically independent. Y2H nondetection
alone would also not justify pruning a functional-association or co-complex edge.
No new model or graph-qualification rule was tested here.

## Artifacts and validation

- [Aggregate receipt](lambourne_pharos_lookup_20261023_summary.json) records counts,
  source/code hashes, provider-specific properties and the probe findings.
- Ignored local source snapshot: `runs/lambourne_pharos_lookup_20261023/retrieval/`.
  `audit/report.json` and `audit/pair_lookup.json` preserve every nominated pair,
  full matching records, source locators, hashes, unresolved identities and
  earlier exposure flags. `preparation/evidence_probe/` holds the separate probes.
- The [audit](../../scripts/audit_lambourne_pharos_lookup.py) reuses existing source
  iterators, query builders and count parsing. It checks response/chunk hashes,
  raw identity/count receipts, declared filters, pagination and exact cohort
  retention. Independent review found and fixed a gap in raw-count verification
  before the final audit; no retrieval response or prior packet was changed.
- **40 focused synthetic tests passed:** 24 retrieval tests and 16 lookup-audit
  tests. They cover unresolved identities, zero-neighbor counts, source tampering,
  cross-chunk retention, mismatched filters/locators and nonpooled properties.
  The actual completed snapshot passed the same source reconciliation audit.
- No Brev instance, GPU, language model, outcome decoding or performance scoring
  was used. Raw third-party records remain local; this report distributes
  aggregate findings. See the [commands](../../scripts/README.md#focused-pharos-ppi-lookup).
