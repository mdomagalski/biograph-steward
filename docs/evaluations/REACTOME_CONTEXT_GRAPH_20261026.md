# Source-bound Reactome graph pair

The selected intervention now has an outcome-blind prepared graph pair. This
closes the missing learner projection; it does **not** demonstrate biological
benefit or complete the execution freeze. Historical GO results and protocols
are unchanged.

The [selection](reactome_context_intervention_20261026_selection.json) and
[literature decision](../literature/REACTOME_CONTEXT_INTERVENTION_20261026.md)
remain the governing scientific contract. The
[preparation receipt](reactome_context_graph_20261026_summary.json) binds the
saved packet, code, original graph and declared Pharos snapshot members.

## Measured preparation

| Item | Count |
| --- | ---: |
| Saved pathway rows dispositioned | 29,593 |
| Eligible exact Reactome memberships | 11,138 |
| Reviewed product nodes with Reactome context | 982 |
| Human Reactome pathway nodes | 1,490 |
| Original panel genes with membership through frozen product mappings | 985 / 1,805 |
| Original nominations retained | 3,276 |
| Shared union entities / relations | 11,840 / 5 |
| Baseline / Reactome adjacency triples | 103,768 / 114,906 |
| Unchanged supervised directed triples | 99,394 |

All 11,138 available source memberships are eligible under the exact saved
identity mappings. No duplicate membership, invalid human stable ID, stable-ID
label conflict or Pharos-local-ID conflict was found. The other 18,455 pathway
rows remain in the disposition ledger with `outside_selected_Reactome_source`;
they are not learner inputs.

For **all nominations**, 712 have no endpoint with Reactome context, 1,207 have
one and 1,357 have two. Among the 2,781 off-diagonal nominations those counts are
457, 1,207 and 1,117. These are outcome-independent coverage inventories, **not**
the final scoring population. The original 1,751 complete-scored off-diagonal
pair denominator remains unchanged and is applied only by the later assay
scorer. Absence of context does not remove a candidate or assert biological
absence. A shared product supplies context to distinct original gene nodes; it
does not merge them or establish assayed construct/isoform identity.

## Preserved boundaries

Both arms use the same ordered union entity/relation vocabulary. The baseline
TSV, original supervision, candidates, development split, transitive-equivalence
masks and assay contract are byte-identical copies of the pinned originals.
Only `UniProtKB:... → pharos_reactome_membership → REACT:R-HSA-...` triples are
added. No protein-pair implication, Pharos PPI, additional GO hierarchy,
IntAct observation or assay outcome enters the projection.

Every source row retains its raw fields and hash, retained and raw-response
locators, disposition, reasons and unresolved qualifications. Validation rebuilds
the eligible ledger from only the original manifest's declared chunks, checks
the exact graph difference and rechecks coverage and documented totals. The
Pharos snapshot postdates the assay; Reactome import release and study lineage
remain unknown. This is consumed retrospective development material, not an
independent reference.

## Commands and next gate

Use the pinned project interpreter:

```sh
runs/reactome_context_runtime_20261026/venv/bin/python scripts/prepare_reactome_context_graphs.py --validate runs/reactome_context_graphs_20261026_final
```

To reproduce preparation, use `--out` with a **new**, absent output directory.
Existing packets cannot be overwritten. Earlier local preparation drafts at
`runs/reactome_context_graphs_20261026` and
`runs/reactome_context_graphs_20261026_verified` are preserved; their code bindings
predate final receipt hardening and they are not the execution handoff.

Sixteen invented-source controls and the 13 existing GO projection and 34 saved
Pharos inventory/source controls pass in the installed native environment, with
no optional dependency skips. These establish source and graph behavior only.
The next story verifies native two-arm message passing and paired training
invariants on invented CPU data. Actual-device resource proof, execution freeze,
six real fits and assay scoring remain pending. No Brev access, model fitting,
outcome loading or reserved IntAct access occurred during this preparation.
