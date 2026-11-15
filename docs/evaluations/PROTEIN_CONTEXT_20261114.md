# Sequence-context assessment — 14 November 2026

The new source-guide view recovers sequence information omitted from our earlier imports and exposes two useful annotation-quality issues: a retired cross-reference and an entry description with unreviewed AI provenance. It preserves the original graph and review decisions.

This assessment uses three existing walkthrough examples, selected before inspecting their InterPro results. It measures source completeness and faithful display. These examples are not a representative biological accuracy sample.

## Recovered context

All three earlier saved snapshots lacked the sequence, the five queried cross-reference families and sequence-annotation records. Fresh Pharos responses supplied **48 cross-reference rows** across InterPro, Pfam, PROSITE, SMART and PANTHER, plus **66 sequence-annotation rows**. The returned Pharos database version was `pharos319`; this records the endpoint's response, without asserting that it is the newest downloadable release.

The new capture queried the official hosted InterPro MCP using the MD5 of each exact Pharos sequence. Matches API 0.6.0 / InterPro111.0 metadata was unchanged before and after capture. Per-signature library versions remain separate.

| Existing example | Sequence length | Recovered Pharos cross-reference rows | Native match records | Native locations / fragments | Site records / residue-position records |
| --- | ---: | ---: | ---: | ---: | ---: |
| EGFR / P00533 | 1,210 | 22 | 143 | 171 / 171 | 98 / 189 |
| CCNO / P22674 | 350 | 12 | 23 | 28 / 28 | 0 / 0 |
| TAS1R2 / Q8TE23 | 839 | 14 | 40 | 79 / 82 | 4 / 53 |
| Total | — | 48 | 206 | 278 / 281 | 102 / 242 |

These are provider records and can overlap or repeat. They are not counts of unique domains, validated residues or independent experiments. Three TAS1R2 locations contain discontinuous fragments; the display retains those fragments instead of presenting the outer span as continuous support. Forty-five signature accessions have multiple method/library-version variants across these examples, including conventional matches and InterPro-N predictions. Every variant remains inspectable.

Pharos already contained the recovered cross-references. This increment improves our retrieval and source inspection; it does not establish resource-level novelty. Pharos itself also describes an embedded ProtVista sequence viewer. [Pharos2023](https://pmc.ncbi.nlm.nih.gov/articles/PMC9825581/)

The same generic capture was then extended to the **98 remaining primary proteins** in the source-faithful workspace's exact 99-target snapshot scope. Together with the existing EGFR packet, saved sequence context now covers **99/99 primary targets**; this does not include all graph neighbors or the whole human proteome. All 98 new sequences were available and found in the precomputed lookup. Their source packet preserves **7,908 native match records**, 12,852 locations, 13,010 fragments and 4,864 site records, plus 1,608 Pharos cross-reference rows and 3,771 sequence-annotation rows. These overlapping provider records include computational predictions and do not measure biological accuracy or independent support. Registration order remains explicit; the earlier packet still supplies EGFR and the two separate assay examples.

## What the source comparison revealed

Among the three walkthrough examples, 27 target–InterPro memberships occur in the captured Pharos cross-references; **26 also occur in the current exact-sequence results**. Their recurrence is explicitly treated as reused context.

Across the **99 primary targets**, Pharos supplies **824 distinct protein–InterPro identifier memberships** and the sequence lookup supplies **934**. There are **790 shared memberships**, **34 found only in the captured Pharos cross-references** (29 distinct entry IDs), and **144 found only in the sequence results** (107 distinct entry IDs). Repeated signatures and methods do not add memberships or supporting votes. These are exact identifier comparisons, not annotation-version identity or independent corroboration. Absence from a sequence-match response alone does not establish retirement, an incorrect annotation or biological absence. Sequence-only identifiers likewise do not establish new biology or experimental support.

A targeted native entry lookup then qualified **all 29 Pharos-only identifiers**, covering all 34 affected memberships:

| Native entry response | Distinct entry IDs | Protein–entry memberships |
| --- | ---: | ---: |
| HTTP200: current entry record supplied | 8 | 11 |
| HTTP410: explicit entry-retirement record supplied | 20 | 21 |
| HTTP204: no content; remains unresolved | 1 | 2 |

The no-content identifier is `IPR017986`; the application preserves its empty response and displays an unresolved state without fabricating a JSON annotation. Current entry existence leaves the absence of a sequence match unexplained. Retirement qualifies the entry identifier's currency; protein functions, historical annotation correctness and relationships remain unadjudicated. The app retains the source identifiers and makes no automatic remapping or biological pruning.

For the **8 current identifiers / 11 memberships**, we also checked native `entry.parent` fields and every directed path in the eight captured entry hierarchies. None of the Pharos-only identifiers was a reported parent or captured ancestor of a same-protein matched entry. Two paths ran in the reverse direction: PIK3CA had matched `IPR015433` above Pharos-only `IPR008290`, and PTEN had matched `IPR000387` above Pharos-only `IPR000340`. These broader matches do not validate the more-specific Pharos membership. The other nine memberships had no captured path in either direction. Direct-match counts remain unchanged.

The remaining CCNO cross-reference, `IPR028864`, has a native HTTP410 record with deletion date **25 August2022**. Its former PANTHER signature history is preserved. No replacement is supplied, so the app retains the source identifier and shows the lifecycle warning without remapping or pruning a biological claim. [Native deletion record](https://www.ebi.ac.uk/interpro/api/entry/interpro/IPR028864/?format=json)

EGFR has two additional current entry identifiers. `IPR049328` links to Pfam `PF21314`; `IPR050122` links to PANTHER `PTHR24416`. The latter's native metadata records `is_llm=true` and `is_reviewed_llm=false`. Both return no GO mapping. These distinctions qualify the entry descriptions and prevent an integrated identifier from being presented as automatically curator-reviewed or as new experimental evidence. [Native entry metadata](https://www.ebi.ac.uk/interpro/api/entry/interpro/IPR050122/?format=json), [InterPro2025](https://doi.org/10.1093/nar/gkae1082)

Entry turnover is an established integration issue. InterPro's official release91 notes document its decision to stop integrating changing PANTHER subfamilies and focus on families. That explains why lifecycle checks are necessary; the exact cause of this individual deletion is not asserted. [Official release notes](https://proteinswebteam.github.io/interpro-blog/2022/10/20/InterPro-91.0-latest-developments/)

InterPro's published lifecycle analysis also describes annotation loss following changes to member signatures, sequence coverage and functional specificity. Removal alone therefore cannot label the earlier protein-function assertion incorrect. Our lifecycle lookup records the source's current status while preserving the original annotation. [Sangrador-Vegas etal.,2016](https://doi.org/10.1093/database/baw027)

## Source-fidelity verification

An independent offline replay verified all eight recorded InterPro raw/parsed response pairs. The application reader was then exercised against the three actual saved workspaces, spanning pathway membership and assay-observation selections:

- All **206/206 native match records** and their nested signature, version, location, fragment and site fields survived unchanged.
- All **206/206 displayed source pointers** resolved back to their exact native records.
- All **48/48 Pharos cross-reference rows** and the 66 sequence-annotation rows were retained.
- All three sequence hashes and retrieval times matched their source envelopes. The three optional lifecycle/editorial records matched the separately captured native responses.
- Source files and saved graph files remained byte-identical. Inspection made zero source requests and zero model calls.

An additional independent offline audit replayed all five raw/parsed response pairs in the 98-protein packet, reusing the unchanged official parser for MCP/SSE envelopes. It verified all 98 exact source identifiers and sequence hashes, and checked every native match object against the reader output. The only executed MCP tool was `matchSequences`, using sequence MD5 strings. All 99 primary targets were covered by the explicit registration index, while the original workspace's snapshot, graph, manifest and qualification receipt remained byte-identical. This establishes source coverage and fidelity, without adding graph assertions or validating the matched biology.

The separately dated entry extension copied all **111 original source files**, the 98 protein records and all 7,908 native matches unchanged. Its independent replay verified 28 native JSON response pairs and the one empty HTTP204 response, reconciled all 34 memberships to those entry outcomes, and confirmed that registration still covers 99/99 primary targets. The extension repeated no Pharos retrieval or sequence-MD5 lookup and made no model calls. A prior strict capture stopped after 12 of the 29 requests, leaving 17 unattempted. Its raw responses and partial audit remain preserved as failed operator evidence; it was never registered as an application source.

Invented regression cases additionally cover missing sequence versus unknown MD5 versus known-empty results; exact isoform identifiers; source/hash/release corruption; coordinates outside the bound sequence; native HTTP204 metadata with empty bytes and no fabricated JSON; and native GOA AND/OR groups, NOT qualifiers, taxa and product forms. The existing GAF wrapper supplies the GOA records. InterPro2GO-derived `IEA` / `GO_REF:0000002` lineage is shown as annotation reuse. [GO method reference](https://geneontology.org/GO_REF/0000002)

A separate actual EGFR selection in the source-faithful workspace verified the native GOA lineage for `GO:0004713` (protein tyrosine kinase activity). All **21 returned native annotation records** were preserved unchanged, including one `IEA` / `GO_REF:0000002` record with separate With/From alternatives `IPR016245` and `IPR020635`, both present in the sequence results. The selected historical Pharos row instead records `IDA` assigned by UniProtKB. Shared protein, term and entry identifiers establish inspectable annotation context; they do not identify that historical row, equate its sequence version or add independent experimental support. The assay selections have no GO claim to bind, so no GO lineage is inferred for them.

Human comprehension remains for the reviewer walkthrough. The delivered improvement is inspectable source context and explicit qualification of reused, retired and generated annotations; scientific accuracy and prediction performance require their separate controlled evaluations.

## Reproduction and evidence

The maintained implementation is `biograph_steward/protein_context_source.py`, the entry-only enrichment helper `biograph_steward/protein_context_entries.py`, the offline reader `biograph_steward/protein_context.py` and the view `biograph_steward/protein_context.js`. The generic producer and reader operate on explicitly selected exact protein identifiers; they contain no rules specific to these three proteins. The [upstream qualification](INTERPRO_QUALIFICATION_20261114.md) records method, source and license details.

Real public source payloads remain ignored operator data. Aggregate receipts are:

| Artifact | SHA-256 |
| --- | --- |
| `runs/protein_context_20261114_v2/protein_context.json` | `6d14718af6105bfcc49cc1c864261352c72ae168d3cc5a31cb621a6841dbea59` |
| `runs/interpro_qualification_20261114/source_assessment_v1.json` | `0b04b1b99f3a464737bb776cf7e1280425da23c53c3b53fc9e7b047435b4984e` |
| `runs/interpro_qualification_20261114/current_packet_assessment_v1.json` | `ee9c8f9cf361724011ddf1d8525eac98f4ebacd1d0ae75748f238aa4a2999944` |
| `runs/interpro_qualification_20261114/ui_examples.json` — actual GO-lineage replay and exact saved selections | `cc81779d6cac5534f1f54e4c3a6f915aa6278cb3f60c70bef1ab44cc1aa069c2` |
| `runs/protein_context_primary_20261114_v1/protein_context.json` — remaining 98 primary targets | `7f1205265f9d34a90888940459bb6b8b0d3e423ce5c8a2af38f293cee614fb0e` |
| `runs/interpro_qualification_20261114/primary_cohort_assessment_v1.json` — independent 98-protein and 99-target coverage audit | `1d6cd7e8a5db16f8dbee595603a8a86c28cb87a4fa4a11263b0758df28528407` |
| `runs/interpro_qualification_20261114/primary_identifier_overlap_v1.json` — exact identifier overlap across all 99 primary targets | `e77fb94376f562a29c7c0d055ef5c2a394aec9e250e7ad0e3d90a46c833755dd` |
| `runs/protein_context_primary_entries_20261114_v2/protein_context.json` — immutable native entry extension | `1ed8db27268cbb00c899e77f72be53e63682739ff2e388c02d163a6129becf89` |
| `runs/interpro_qualification_20261114/primary_entry_lifecycle_assessment_v1.json` — independent 29-entry / 34-membership reconciliation | `b6c5873b09ed4b78c1abf8c83f8bd04cf510b112d12a3e789540374e19c48e08` |
| `runs/interpro_qualification_20261114/hierarchy_scope_check_v1.json` — native parent and directed-hierarchy check for 8 current IDs / 11 memberships | `40428b631e1aa5dff70749d2f5f60cd07102992f403361d4c8fae72a328540c1` |
| `runs/interpro_qualification_20261114/partial_entry_lifecycle_assessment_v1.json` — preserved first 12 requests; 17 unattempted | `d0032b1cf4187e1bc54235967923aaf7d5a56d453c1efd343207d82e1f7ec5f3` |
| `runs/interpro_qualification_20261114/lifecycle_ui_examples_v1.json` — exact FBXW7 unresolved and DCC retired-entry walkthrough selections | `25f9fd8b06d15ca88110b8e14d964c4fade4d7d0b25ceabef1d2175e07b984c4` |

The pinned receipts record exact source files, unchanged-parser identity, reader code pins and replay totals. The audit performed no biological label selection, prediction fitting or graph intervention.
