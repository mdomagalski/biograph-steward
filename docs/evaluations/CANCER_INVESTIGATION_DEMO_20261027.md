# Coherent cancer investigation demonstration

October 27, 2026. **A complete saved-source journey now connects BRAF protein
context, KRAS, the exact KRAS G12D molecular profile, qualified colorectal-cancer
therapy evidence and reproducible exports.** It uses the existing
`crc_civic_final_20261015` source, existing question engines and existing graph
exporters. No model, new biomedical retrieval, new scientific assertion or
keep/prune judgment was introduced.

Open the [standalone guide](../../runs/cancer_investigation_demo_20261027/index.html).
It has four steps, direct app buttons, readable saved reports and local
downloads. It does not change production navigation. App links default to port
8794; the guide's port control supports a later restart on another local port.
The saved reports and local downloads work without the server.

## Five-minute journey

1. **BRAF neighborhood.** Open the [saved BRAF answer](http://127.0.0.1:8794/?run=crc_civic_final_20261015&question=question_20261027T180832Z_781f7543)
   and select KRAS, the third ranked result. This is a candidate Pharos path
   requiring review. Native STRING physical priority is 0.999; the score orders
   a reported association and does not prove direct binding. All 21 matches
   remain: 14 numerically scored and seven explicitly unranked.
2. **Explicit variant question.** Follow the guide to the
   [KRAS G12D answer](http://127.0.0.1:8794/?run=crc_civic_final_20261015&question=therapy_cancer_demo_20261027).
   Check complete profile `CIViC.molecularprofile:79`, raw expression `#VID79`,
   variant G12D, human KRAS `NCBIGene:3845`, and somatic origin. This is an
   explicitly selected question, not a response inferred from the BRAF–KRAS path.
3. **Qualified evidence.** Inspect all three eligible assertions and their
   passports. Complete therapy members, source interaction types, direction,
   significance, levels, source descriptions and local states remain visible.
4. **Export.** Download the two question packages and the qualified therapy TSV.
   Then download the separate full scoped graph-and-ledger handoff. Distinguish
   the selected three-assertion answer from the entire saved workspace.

Pharos's colorectal adenocarcinoma (`MONDO:0005008`) and CIViC's Colorectal Cancer
(`DOID:9256`) remain separate source conditions. No disease equivalence, subtype
transfer, clinical recommendation or treatment-response inference from protein
proximity is made.

## What the source annotations actually contain

| CIViC item | Complete therapy members | Interaction | Source direction / significance | Level | PMID |
| --- | --- | --- | --- | --- | --- |
| 2207 | Cetuximab | Not supplied | SUPPORTS / RESISTANCE | B, Clinical evidence | 20619739 |
| 6316 | Panitumumab; Cetuximab | SUBSTITUTES | SUPPORTS / RESISTANCE | C, Case study | 19223544 |
| 2193 | Panitumumab | Not supplied | SUPPORTS / RESISTANCE | C, Case study | 20619739 |

These are **three assertions, three CIViC items and two distinct cited PMIDs**,
not three independent studies. Source editorial status is ACCEPTED; every local
assertion remains candidate. A one-drug source list does not establish
monotherapy; SUBSTITUTES preserves alternatives without resolving individual
exposure. The saved descriptions retain mixed study conditions and co-treatments.
The display does not certify original-paper entailment or scientific accuracy.

## Verified source-to-export fidelity

The original October 22 therapy answer exactly replays with the current engine.
It was republished **offline in a new question directory** because its older
TSV predates the expanded qualification columns. The historical answer and
exports remain unchanged. The new export verifies all three raw evidence records
against the saved CIViC snapshot and preserves 24 checked qualification/trace
fields, including complete profile/variants, disease, therapy members,
interaction type, evidence level, source/local states, descriptions and locators.
No matching assertion is omitted by the selected display limits.

Both app questions and their downloaded ZIPs returned HTTP 200 and equal their
saved artifacts. The guide's local links, JavaScript syntax and local-port
selection passed checks. This is artifact/HTTP verification; a current visual
browser or independent user walkthrough remains outstanding.

## Full scoped graph and undecided ledger

The existing exporters produced **9,746 nodes, 15,717 evidence edges and 15,712
assertions**, including all 41 variant–therapy assertions in the saved 99-target
retrieval. Every edge has an explicit abstention with null confidence:
**0 keep, 0 prune, 15,717 abstain**. All nodes, edges, assertions and original
review states remain retained. Quarantine and context remain in the audit.
The approximately 36 MB ZIP includes `retained_graph.json`,
`edge_dispositions.jsonl`, the complete `baseline_packet/`, and a byte-identical
copy of the historical source graph. The extracted handoff verifies offline.

The initial strict export correctly rejected the historical graph because three
readiness-disclosure strings had changed: current code recognizes the existing
CIViC enrichment and its unresolved independence. The established `replay`
command published a **new** current workspace before export. The receipt records
exactly those three diagnostic differences; nodes, edges, assertions, source
snapshots, reviews and question basis remain equal. No replay guard or pin was
relaxed, and all original source-directory bytes remain unchanged.

This is the complete **scoped retrieval**, not the whole Pharos resource or an
organizer-approved final format. Abstention is unassessed retention, not
scientific acceptance. Neither this export nor the coherent journey measures a
Steward-specific biological gain.

The [machine summary](cancer_investigation_demo_20261027_summary.json) links the
actual hashes and checks. Local evidence is under
`runs/cancer_investigation_demo_20261027/`: `verification.json`,
`http_verification.json`, `graph_handoff_verification.json`, both answer packages
and the full handoff ZIP. The source-component
[assessment](STRING_COMPONENT_COMPARISON_20261027.md) and
[temporal control](STRING_TEMPORAL_CONTROL_20261027.md) retain their existing
consumed-development interpretation.
