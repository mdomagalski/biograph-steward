# Fuller scoped Pharos retrieval

Implemented and live-verified on October 14, 2026 against Pharos `pharos319`. This is broader **Pharos baseline coverage**, not external enrichment or a biological result.

## Use it

In the browser, choose Live Pharos, the exact disease, **Fuller scoped context**, and a target cap. Tissue words are optional and explicit; leaving them empty skips expression. Inspect the coverage table and filter the separate context browser by protein and family. Accepted assertions remain a distinct review view.

```bash
python3 app.py build --disease "colorectal adenocarcinoma" --max-targets 100 \
  --profile scoped --tissue-term "colon rectum" --out runs/crc_scoped_01
```

The CLI retains `preview` as its default for compatibility. The UI defaults to scoped retrieval with a 100-target cap. Neither changes the selected disease or merges related terms. Use a new output directory for every run. `python3 app.py queries --out queries` exports the preview, inventory and scoped-family query templates; exact variables and responses are saved with each run.

## Scope and budgets

| Family | Default per-protein cap | Selection and interpretation |
|---|---:|---|
| Pathways | 2,000 | All sources; paginated and reconciled with pathway counts. |
| GO | 500 | Original term, aspect, evidence code, ECO code and assigning source. |
| PPI | 2,000 | Confidence filter 400 on the Pharos API scale. Scan neighbors, retain selected-cohort partners only. |
| Drugs | 100 | `isdrug: true` target-linked listings; no activity, indication or resistance claim inferred. |
| Expression | 2,000 scanned | Retain case-insensitive whole-word matches to any explicitly supplied tissue word. Keep source values and “Not detected” records unchanged. |
| Publications | 25 | Target-linked PMID/title/date/journal in API order. These are discovery candidates, not citations supporting a disease claim. |

Override caps with `--pathways-limit`, `--go-limit`, `--ppis-limit`, `--drugs-limit`, `--expressions-limit` and `--publications-limit`. Zero skips a family. Maximum caps are respectively 5,000 / 2,000 / 5,000 / 500 / 5,000 / 200. A 200,000-row global scan budget bounds a build; raw excluded rows count toward it. Earlier families can consume that budget, so a large cohort may leave later families budget-limited.

Metadata is collected in batches of five proteins. Ordinary pages contain at most 500 rows per protein. PPI uses one bounded list per protein because upstream score ordering lacks a unique tie-breaker; the live multi-page probe overlapped four neighbor IDs across PIK3CA and GRK2 pages. The verified pull avoids those boundaries. The deployed expression text search failed with `ER_FT_MATCHING_KEY_NOT_FOUND`; expression is therefore scanned and filtered locally. Neither workaround silently drops evidence or disables a check.

`complete` means retrieved rows match the reported count for that family and seed protein, without detected count changes or page overlap. `exhausted` means a short page was observed when a usable count was unavailable. `capped`, `budget_limited`, `inconsistent` and `not_requested` remain explicit. Null fields and GraphQL partial errors fail the build; they are not empty-success responses. Repeated pages fail; overlapping stable identifiers or count mismatches prevent a complete status. Source offsets and count checks cannot guarantee a transactionally consistent upstream snapshot.

Counts for PPI sources overlap: only its `Total` count is the denominator. Expression counts describe all scanned tissues, not the retained tissue subset. Unknown counts stay null. Completeness is relative to the selected seed cohort and API filters; a target-capped disease cohort remains incomplete even if every fetched protein's annotations are complete.

## Verified local result

Exact disease: **colorectal adenocarcinoma, MONDO:0005008**; all **99 of 99** reported targets. Local run: `runs/crc_scoped_verified_20261014/`.

| Family | Reported rows before local filtering | Scanned | Retained |
|---|---:|---:|---:|
| Pathways | 9,540 | 9,540 | 9,540 |
| GO | 4,078 | 4,078 | 4,078 |
| PPI | 30,870 | 30,870 | 1,436 |
| Drug listings | 174 | 174 | 174 |
| Expression | 74,025 | 74,025 | 1,061 |
| Publication discovery | 61,717 | 2,403 | 2,403 |

The first five families have complete observed API coverage for all 99 seed proteins under these settings. Publications are capped for 90 proteins and complete for nine. The retained PPI records describe **718 unique unordered pairs**, with both endpoint views preserved. These are source-record and annotation counts, not independent experiments or newly discovered relationships. The pathway increase is from the earlier 806-row sample to 9,540 source rows; source/identifier overlap still needs semantic normalization.

The run contains 9,152 distinct context records after exact-row grouping. All 163 saved source-response hashes and the snapshot hash were verified. Snapshot SHA-256: `7caee0c53c57972c5510a52d65b3346a9b95375670cdc48500f13302e71a7dc0`.

Development runs `runs/crc_scoped_20261014/` and `runs/scoped_probe/` are **not validated outputs**: an early implementation mutated target response objects while adding context, invalidating their source-envelope hashes. They were preserved; the verified run was rebuilt from untouched cached responses with target copies. Current replay rejects those invalid envelopes. Use only the verified run named above for this checkpoint.

## Exports, validation and remaining work

- `retrieval_coverage.json` / `.tsv`: per-protein/family reported, scanned, retained and excluded counts; statuses, limits, issues and pointers to exact source response pages.
- `context_records.json` / `.tsv`: typed source-context entries, raw records, original snapshot locators and interpretation limits. Exact duplicate rows share an entry while retaining every locator.
- `context_metadata.json`: source inventory and affiliate links. A LinkedOmicsKB link does not mean CPTAC measurements have been downloaded.
- Snapshot, raw envelopes, manifest and existing graph/assertion artifacts remain replayable. Original upstream timestamps survive cache reuse. Response hashes are validated as well as the outer snapshot hash.

The retrieval checkpoint initially exposed new families as source context. Version 0.3 now normalizes GO, PPI, drug and expression records into qualified candidate assertions, while preserving the raw input and keeping publications as discovery records. See [the normalization contract and results](CONTEXT_NORMALIZATION.md). Acceptance, biological validation, chemical mapping and claim-specific citation support remain separate work.

GTEx's separate endpoint, non-drug ligands, drug activities, GWAS, LINCS, GeneRIF text/full text and community API datasets are explicitly unrequested. GO negation/context not exposed by these fields is not inferred. The separate [CIViC workflow](CIVIC_EVIDENCE.md) provides bounded variant–therapy annotations; underlying-study independence remains unresolved.

All **85 tests passed**, including local HTTP tests. The suite covers pagination, caps, missing/changing counts, page overlap, null/error handling, cohort boundaries, tissue filtering, unchanged source envelopes, replay, exports and citation isolation. Browser checks passed for a live scoped build, saved-run loading, KRAS publication provenance, tissue filters, context pagination and the 9,640-record assertion table. No browser console errors were reported. Live data and generated reports remain ignored by Git and are not bundled as redistributable fixtures.

API field and resolver references: [NCATS schema](https://github.com/ncats/pharos-graphql-server/blob/master/src/schema.graphql), [NCATS TCRD implementation](https://github.com/ncats/pharos-graphql-server/blob/master/src/TCRD.js), [NCATS resolvers](https://github.com/ncats/pharos-graphql-server/blob/master/src/resolvers.js).
