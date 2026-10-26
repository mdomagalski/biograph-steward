# Gold-reference handoff verification

October 23, 2026. Engineering verification only; no organizer gold artifact,
scientific labels or reserved assay outcomes were used.

## Result

Implemented and exercised five commands: `gold-export`, `gold-verify`,
`gold-decisions`, `gold-reference-template` and `gold-align`. The [interface
guide](../GOLD_SET_INTERFACE.md) describes the local contracts and limitations.

- Full suite: **411 tests discovered, 409 passed, 2 optional-dependency skips**.
- New interface tests: **34 passed**, including source tampering, conflicting
  metadata, stale decisions, incomplete qualifications, ambiguous matches,
  collisions and byte-preserving portable outputs.
- Review found a source-version binding gap in the older replay helper. The
  interface now checks run-manifest, graph and Pharos/CIViC snapshot metadata
  explicitly; resealing conflicting metadata does not bypass those checks.
- No model calls, Brev access, AWS resources or new network retrievals.

## Saved real-data handoff

Used the existing `crc_civic_final_20261015` Pharos/CIViC sources. Its saved
benchmark-readiness wording predates the current transformer, so the original
graph correctly failed exact replay. An explicit new replay was created at
`runs/gold_interface_20261023/live_replay`; the historical run was not rewritten.
Only the `benchmark_readiness` field changed. Nodes, evidence edges, assertions,
context, quarantine and review history remain identical.

| Preserved inventory | Count |
|---|---:|
| Nodes | 9,746 |
| Evidence edges | 15,717 |
| Qualified assertions | 15,712 |
| Context records | 9,152 |
| Quarantined records | 11 |

Pharos database version: `pharos319`. This is a scoped colorectal workbench
graph; it is not the full Pharos release or the larger staged inventory pull.

Packet ID:
`packet:d523a34386272b33f894da9d6a50248691879d991529cfe9cb78ba380c8f02f0`.

The independently verified packet is at
`runs/gold_interface_20261023/live_packet/`. The complete portable disposition
output is at `live_dispositions/`, with **0 keep, 0 prune, 15,717 abstain**.
The reference mapping template in `live_reference_mapping/` remains incomplete
until an actual reference and its metadata arrive.

## Synthetic integration check

An invented graph with 12 nodes, 18 edges and two quarantined records exercised
the full workflow. Explicit fixture dispositions were 1 keep, 1 prune and 16
abstain; the baseline retained every original node and edge.

A three-row invented reference produced two exact matches and one unmatched
row. One label was empty. Labels stayed uninterpreted, `rows_scored` remained zero,
and `metrics` remained null. These counts test identity handling, not accuracy.

The machine-readable local receipt at
`runs/gold_interface_20261023/validation.json` records source/implementation hashes,
packet counts and preservation checks. Run artifacts are ignored by Git; this
tracked note records the verification without bundling upstream source data.

## Remaining boundary

We can now hand off a preserved graph and explicit decisions and inspect exact
reference coverage. The organizers' actual identifiers/schema, label meanings,
baseline compatibility, splits and scoring policy still require inspection.
Upstream identifier crosswalks, formal KGX/Biolink validation and official scoring
must not be inferred from this local adapter. Refresh-run ancestry export is
also explicitly unsupported in this increment.
