# Pharos identity and evidence-source update

This separate supplement checks the richer official PPI route and adds scoped Pharos400 identity/TDL information to one consumed-workspace overlap report. It never rewrites the saved graph, source baseline, observations, review decisions or original overlap.

## Completed example — October 27, 2026

The workspace contains two qualified observations for Q7RTX0–Q8TE23. Its original snapshot and the current API both report `pharos319`.

| Check | Result | Interpretation |
|---|---|---|
| Official `listCrossDetails`, both directions | Same requested pair and Reactome/STRING bundle; evidence and interaction type explicitly null | This route does not recover experimental lineage for this pair. Reciprocal views are not independent evidence. |
| Official 400 table, exact selection | One canonical, reviewed Tbio row for each protein | Both support exact primary identifier correspondence. TDL remains Tbio in both releases for these proteins. |
| Existing SSSOM producer | Two 319-to-400 rows with source/version/row provenance | Identifier equality does not establish sequence, assay or experiment equivalence. |
| Original record-level overlap | Both observations still concern a pair in the baseline; lineage unresolved | No new independent support, scientific accuracy or predictive gain established. |

The scan recorded 166,833 rows and SHA-256 `53075ec817a0d9258836fbba573b95be9b5ff6df70654bd5c5d0715cf4f150f2`. Only two complete selected CSV records were retained, including all 20 columns and absolute logical/physical locators. The full CSV was temporary and deleted under the capture contract. Offline checks verify retained records and receipt bindings; they **do not replay complete-source selection**. The full-file hash and scan counts remain capture-time assertions. Missing matches must not become proof of absence or obsolete identity.

The CSV omits `canonical_isoform_status_source`, `is_canonical` and `protein_group_anchor`; these remain unavailable rather than inferred.

Local report: `runs/pharos_source_update_20261027_attempt_01/index.html`. Both exported mapping rows passed the official `JsonSchema`, `PrefixMapCompleteness` and `StrictCurieFormat` checks plus a complete row/metadata/provenance roundtrip, using the existing isolated `sssom 0.4.21` / `sssom-schema 1.1.0a5` environment. This validates the narrow published 1.0 output profile, not biological correctness or complete standards interoperability. The receipt is `runs/pharos_source_update_sssom_validation_20261027/report.json`, SHA-256 `7c9f74b868cbf2d5efbe52f2ca4a42b70d7c80745a3c9370b2c3977fbe49aab4`.

## Commands

Use new output directories. The first command makes three uncached GraphQL requests: version, the sole saved pair in both directions, version. The second downloads the official full table once (about 87 MB) and retains only exactly selected protein records. It has bounded time/size, no redirects and no retries. Neither needs a model, Brev or GPU.

```sh
python3 app.py pharos-pair-details --overlap runs/existing_overlap --out runs/new_pair_details
python3 app.py pharos400-intake --accessions Q7RTX0 Q8TE23 --out runs/new_400_identity
python3 app.py pharos-source-update --overlap runs/existing_overlap --details runs/new_pair_details --identities runs/new_400_identity --out runs/new_source_update
python3 app.py pharos-source-update-verify --report runs/new_source_update
```

Publishing and verification are offline. The details check intentionally supports exactly one saved pair; it does not widen a cohort. Source errors, version drift, changed returned identities and partial GraphQL errors stop a trusted publication. Failed captures keep separate receipts.

Outputs: `index.html`, `report.json`, `records.jsonl`, `mappings.json`, `mappings.sssom.tsv`, `manifest.json`. The readable page links to the original overlap and captured receipts and compares source-specific TDL values. Input directories remain necessary for replay; this is not a self-contained graph submission package.

Verification checks inventories, hashes, implementation pins and exact recomputation of all outputs. It rejects altered inputs, symlinks, overlapping output directories, changed outputs and resealed incorrect classifications. These are software integrity checks, not scientific validation.

## Identity and provenance boundaries

The [official 400 notes](https://opendata.ncats.nih.gov/public/pharos/pharos400_readme.html) distinguish canonical, isoform and alternate-product rows. Products can share a base accession; internal IFX IDs are source-row identifiers. An anchor need not be biologically canonical.

Every selected row is preserved. Repeated base accessions cannot establish product identity, even on canonical rows. Explicit isoforms retain their suffix and must be consistent and unique within the selected scope. Alternate products, invalid identities and unsupported grouping remain unresolved. Symbols, xrefs and IFX IDs never create protein mappings.

Mappings reuse the [existing SSSOM producer](EVIDENCE_OVERLAP.md#sssom-identity-boundary). This is source-primary identifier correspondence, not general accession-history resolution or evidence merging. External standards validation is separate from built-in replay. Source records retain their upstream terms; the generated mapping license does not relicense downloaded records.

Pair-detail evidence stays raw and source-specific. Free text, provider names and scores do not become invented publication or experiment identifiers. Null establishes only what the capture returned. Matching release labels at different times do not guarantee an atomic or identical upstream snapshot.

## Next evidence question

The richer Pharos route is checked for the actual consumed pair. To pursue experiment lineage, inspect contributing providers' existing evidence links and record identifiers for that pair, preserving source-release uncertainty. Reuse IMEx/MImerge evidence distinctions rather than inventing a combined confidence score. A 400 target table alone cannot answer that question. Keep the fresh IntAct panel unopened until its separate execution freeze.

The subsequent [provider trace](evaluations/PROVIDER_PAIR_LINEAGE_20261027.md) completes that bounded check: one attached IntAct record is explicitly reused in current STRING, and STRING lists Reactome support for the pair. The source trace retains unknown historical Pharos imports and second-record reuse; it does not rewrite this earlier source-update publication.

See the [release assessment](evaluations/PHAROS_RELEASE_CHECK_20261027.md) and [original overlap guide](EVIDENCE_OVERLAP.md).
