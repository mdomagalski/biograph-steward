# Provider lineage for TAS1R2–TAS1R3

October 27, 2026. **One attached IntAct record is already used by current STRING. STRING also reuses Reactome knowledge for this pair.** The trace resolves specific source reuse, while the provider files behind the historical Pharos319 response remain unknown.

This is a consumed development case for human Q8TE23–Q7RTX0. The graph, source baseline, prior comparisons and review decisions are unchanged. No new scientific-accuracy or prediction comparison was run.

## What is confirmed

| Question | Finding | Evidence unit and limit |
|---|---|---|
| Does STRING use the first attached IntAct record? | Yes: its experimental evidence row links `IM-30398-1`, an identity alias of `EBI-67107463` | User-assisted exact curated-record match, verified against preserved official IntAct XML and typed reader output. It must not be counted again as independent of current STRING. |
| Which study/experiment does that preserved source describe? | PMID 40555359; experiment `EBI-67107458`; method `MI:0410`, 3D electron microscopy | This chain comes from the matched official IntAct record. STRING's aggregate API did not expose the experiment ID directly. |
| Does STRING use Reactome for this pair? | Its user-observed database view explicitly lists Reactome receptor complexes, reaction contexts and pathways | Resource-level reuse confirmed. Exact supporting Reactome IDs were not copied from that view; names alone are not identifier equivalence. |
| Are the current Reactome contexts independent support? | One base complex, `R-HSA-444621.2`, occurs within four additional complex contexts | Five pair-specific contexts total, not five independent experiments. Two generic GPCR set contexts were left unexpanded. |
| Is the second attached record, `IM-30398-5`, also reused? | Unresolved | It was not identified in the inspected excerpt. This is not proof of nonreuse. |
| Do these current records identify Pharos319's original inputs? | No verified build/provider-file link | Current Reactome 97 and STRING 12.5 cannot certify or relabel historical Pharos imports. |

## Exact IntAct identity chain

The user copied `ebi.ac.uk/intact/query/IM-30398-1` from the STRING Lab Experiments row naming TAS1R2/TAS1R3 and 3D electron microscopy. The browser connection could not inspect the page directly, so this link remains explicitly **user-observed**, separate from machine-captured HTTP evidence.

The preserved official source independently establishes:

```text
STRING row — user-observed source link
  → IMEx IM-30398-1 (MI:0662 imex-primary)
  ↔ IntAct EBI-67107463 (MI:0356 identity)
  → source experiment EBI-67107458 (MI:0356 identity)
  → PMID 40555359 (MI:0358 primary-reference)
```

The typed source is `assay_source/provenance/40555359_reader.jsonl`, line 1, in the existing consumed workspace. Its hash is `9ca7ac4aba25bde0e4f3498b8cbb1e5f073b9d391240c44b9e42d6828a4d59a0`. Raw XML interaction 5650150 and MITAB source line 2 corroborate the same interaction identity and exact protein pair. The qualified identity link, rather than a matching method name or confidence label, resolves reuse.

The first overlay observation can still add inspectable assay and structural detail. That is a context contribution, not another independent confirmation over current STRING. Independence from the older Pharos snapshot remains unresolved.

## Reactome record scope

The [base complex](https://reactome.org/content/detail/R-HSA-444621) has immediate components referencing both exact UniProt accessions. Preserve their processed-chain states: TAS1R2 positions 20–839 and TAS1R3 positions 21–852, plasma membrane. These state-specific entities are not identical to unrestricted full-length protein states.

Four additional complex records reuse that same component: `R-HSA-444662.3`, `R-HSA-9728695.1`, `R-HSA-9728706.1` and `R-HSA-9728735.1`. Repeated nested membership is not independent measurement.

[Reaction R-HSA-444606.2](https://reactome.org/content/detail/R-HSA-444606) consumes the pre-existing receptor complex and sweet compounds. It models ligand binding, not assembly of the receptor pair. Four inspected pair-specific reactions have direct citation PMIDs 11917125, 17506496, 21795555, 24360415, 25853419 and 26377607. None equals 40555359 in those specific direct citation slots; this bounded non-overlap does not establish experimental independence. Generic contexts and second-tier summation references were not expanded.

The [official export documentation](https://reactome.org/download-data?id=62&ml=1) explains that interaction rows are electronic projections from complexes/reactions and that `direct_complex` does not establish true pairwise binding. Citation placement and inferred-reaction flags remain in the trace.

## STRING scope and integration cautions

The official versioned pair API returned combined 0.999, experiments 0.979, databases 0.900 and text mining 0.818. These are source-channel scores, not experiment counts or Steward performance gains. STRING's [locus-based identity convention](https://string-db.org/cgi/info?footer_active_subpage=faqs) also prevents treating representative-protein aliases as demonstrated isoform/sequence equivalence.

The API's MITAB/XML exports expose aggregate channels and method templates rather than original pair-study records. XML has eight channel/method descriptions and five aggregate interaction entries; these must not become laboratory experiment counts. Ambiguous namespace labels and repeated local IDs remain uncorrected source-export cautions.

The automated detailed viewer returned HTTP403. The user completed the site's human check and supplied visible evidence. The database lists are truncated and separate human from transferred animal evidence. A later experimental paste included a wider neighborhood; unrelated pairs were excluded. Only the explicit `IM-30398-1` evidence link resolved the record match. No cookies were extracted or access challenge bypassed.

## Artifacts, verification and next use

Consolidated local report: `runs/provider_pair_lineage_20261027_attempt_01/index.html`. It includes `report.json`, an observation-level `record_reuse.jsonl`, an integrity manifest and an offline publication/replay script. Original input directories remain necessary for replay.

```sh
python3 runs/provider_pair_lineage_20261027_attempt_01/publish.py --verify
```

Provider captures remain separately preserved under `runs/reactome_pair_lineage_20261027_attempt_01` and `runs/string_pair_lineage_20261027_attempt_01`. User observations and the pre-analysis preservation scope are under `runs/provider_pair_lineage_20261027_preparation`. Independent review receipts are under `runs/provider_pair_lineage_review_20261027`. Source identities, component paths, citations and unchanged inputs were checked offline; this is software/source verification, not independent biological validation.

The [workbench supplement](SOURCE_REUSE_WORKBENCH_20261027.md) now exposes shared curated-record support alongside additional assay context and carries the copied proof in a new workspace ZIP. Do not pool the scores, prune the association or label every second-source record novel. Resolving historical baseline reuse requires actual imported provider/build provenance. No model or Brev GPU is needed for this source audit.
