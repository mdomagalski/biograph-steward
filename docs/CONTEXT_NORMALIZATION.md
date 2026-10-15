# Qualified Pharos annotation assertions — v0.3

The scoped Pharos context now participates in the assertion, passport and human-review workflow. This increment uses project-local annotation predicates because the returned fields do not justify more specific biological claims. Raw snapshots remain v1; derived graphs are v3. No network retrieval is needed to normalize a saved snapshot.

## Assertion meanings

| Family | Predicate | Identity and preserved context |
|---|---|---|
| GO | `biograph:has_go_annotation` | Seed protein, GO ID and P/F/C aspect. Assigning source, evidence code and ECO code remain in each evidence record. |
| Interaction | `biograph:has_interaction_annotation` | Canonically ordered, undirected pair of seed proteins. Source bundles, original endpoint views and all property values are preserved. |
| Drug listing | `biograph:has_drug_listing` | Protein and the explicit Pharos ligand ID with `isdrug=true`. The local ligand ID remains marked as needing external mapping. |
| Expression observation | `biograph:has_expression_observation` | Protein, anatomical context, source observation ID, assay, exact tissue/cell label and measured value or qualitative result. Units remain unknown. |

GO annotations are represented as annotations rather than positive `enables`, `involved_in` or `located_in` statements: the retrieved fields omit the original relation, negation and annotation extensions. The [GO annotation specification](https://geneontology.org/docs/go-annotations/) explains those distinctions. A valid identifier and source code establish the structure of this annotation record; they do not establish biological truth or validate the term against a downloaded ontology release.

Interaction annotations can include functional associations. They do not establish physical binding. Drug listings do not establish mechanism, indication, variant response or resistance. Expression observations retain “Not detected,” zero values and distinct tissue/cell labels; they are not converted to positive `expressed_in` claims. HPA, HPM and Jensen measurements retain their original scales without numeric aggregation. Species, disease, variant, treatment and cell-line qualifiers remain null unless explicitly supplied by the source adapter.

Publications remain discovery records and create no scientific assertion or supporting citation automatically. An explicit PMID on an expression source record attaches only to that observation. GO evidence codes, target-linked papers and publication counts are not substitutes for claim-specific references.

## Records, duplication and review

Exact repeated context rows share an evidence entry while retaining every original snapshot locator. GO records for the same protein/term/aspect share an assertion, with source evidence preserved separately. Reciprocal PPI records with the same source bundle become one evidence group under one undirected assertion. Different source bundles remain separate groups; differing score values remain visible in the original views and are never averaged or assigned to an individual provider by inference. Source names and record counts are not independent experiment counts.

Malformed records, invalid GO IDs/aspects, conflicting GO aspects, unconfirmed drug flags, missing expression observations and partners outside the selected cohort are accounted for in input quarantine. Unresolved ligand/tissue identifiers and missing GO provenance are explicit review issues. New structurally usable annotation assertions begin as candidates; human acceptance remains a separate, recorded decision. Local predicates describe exactly what was reviewed: acceptance of a source annotation does not turn it into a causal or therapeutic claim.

The seven legacy qualifier slots retain their identity representation. Additional non-null qualifier slots are `go_aspect`, `tissue_label`, `assay`, `observation_id`, `measurement_value`, `measurement_qualifier` and `measurement_unit`. New optional null slots do not change legacy IDs. An observation's value, qualitative result and context are part of its qualified statement; changes produce a different statement. PPI score changes change evidence revision while retaining the same pair assertion ID.

The existing disease/pathway claim IDs and evidence revisions are preserved. Exact-snapshot reviews still replay; new evidence is not automatically accepted. Original snapshots and previous output directories remain intact. Reopening a saved URL applies the current transformer; its existing ZIP remains the saved historical artifact. Use a new replay directory to export the updated representation.

## Traceability and use

`context_records[].assertion_ids` and `normalized_evidence_edge_ids` link each retained source entry to its normalized passport. `source_response_locators` identify matching raw response rows, response hashes, original retrieval times and cache status. Normalized evidence includes those pointers, the aggregator/database version, raw source record(s), source scores, interpretation notes and original snapshot locators. Unknown upstream source-release versions are not invented.

The browser adds a normalization summary, assertion-family and protein filters, annotation nodes in the graph, qualified expression context in the table and a **Review normalized assertion** link from source records. Either PPI endpoint can be used for filtering, including in the accepted view. The accepted view remains empty until decisions exist. Publication discovery stays available separately.

```bash
python3 app.py replay --snapshot runs/crc_scoped_verified_20261014/snapshot.json \
  --out runs/crc_normalized_01
```

`normalization_report.json` describes input rows, exact duplicates, normalized evidence groups, qualified assertion counts, reciprocal views and quarantine/discovery statuses. Existing graph/edge/assertion exports now include the new predicates and qualifiers. Context TSV includes crosswalk IDs; edge TSV includes observations, source-row counts and retrieval provenance. The pipeline trace and run manifest identify the normalization policy.

## Validation against the saved cohort

The original 99-protein snapshot, SHA-256 `7caee0c53c57972c5510a52d65b3346a9b95375670cdc48500f13302e71a7dc0`, was replayed locally into `runs/crc_normalized_verified_20261014/` without changing its bytes or making API calls.

| Family | Source rows | Evidence groups | Qualified assertions |
|---|---:|---:|---:|
| GO annotations | 4,078 | 4,078 | 4,078 |
| Protein interactions | 1,436 | 718 | 718 |
| Drug listings | 174 | 174 | 174 |
| Expression observations | 1,061 | 1,061 | 1,061 |
| Publication discovery | 2,403 | 0 | 0 |

That adds **6,031 candidate assertions** to the existing 9,640 disease/pathway assertions, for **15,671** total. All 718 reciprocal interaction views are combined, every retained context record resolves to raw source response rows, and no source context is quarantined in this saved dataset. All legacy IDs/revisions and benchmark pair counts remain unchanged. The 174 drug-listing assertions retain their local-ID review issue; scientific validation and external chemical mapping remain pending.

All **104 tests pass**. Tests cover evidence and identity stability, duplication, reciprocal score differences, absence/zero preservation, context separation, malformed records, outside-cohort partners, exact source tracing, citation isolation, legacy reviews and new-family review persistence. Browser checks verify family/protein filtering, incoming PPI views, expression context and source-record-to-passport links. QA uses an explicitly synthetic fixture for saving/reopening an accepted PPI review; no live biomedical assertion was accepted by that check.

Remaining work includes ontology/chemical mappings, complete GO relation/negation retrieval, claim-specific citation recovery, source/study overlap accounting, conflict adjudication and the focused question workflow. These annotations remain Pharos baseline data for the eventual comparison.
