# Pharos reference handoff

Updated October 25, 2026.

Verified on invented fixtures and an existing scoped Pharos/CIViC graph; see the
[verification record](evaluations/GOLD_SET_INTERFACE_20261023.md).

The workbench can now export a source-bound graph packet, record explicit edge
dispositions, and align a declared reference table to that packet. This is the
reusable interface we can complete before the organizers supply their gold set.
It does **not** compute scientific accuracy or implement an official challenge
scoring protocol. The reference artifact, scope, baseline release, label meanings,
split rules and required submission format remain unknown.

Everything here runs locally with the core Python app. It needs no model, Brev
instance, API key, AWS account or new source retrieval. The commands create new
directories and refuse to overwrite existing inputs or outputs.

## Reuse and the remaining gap

The existing app already stores immutable source snapshots, qualified assertions,
source locators, review history, licenses and graph inventories. This interface
reuses that representation, strict replay checks and assertion identity; it does
not introduce a second graph store, biological labeling method or confidence
model.

We checked the official [KGX format](https://biolink.github.io/kgx/kgx_format.html)
and [Biolink qualified association examples](https://biolink.github.io/biolink-model/association-examples-with-qualifiers/).
KGX handles serialization of Biolink-compliant graphs, while qualifications carry
the context needed to distinguish claims. Neither specification supplies this
challenge's missing label or scoring semantics. The current workbench's local
predicates, categories and source records have not undergone full versioned KGX/
Biolink validation. These JSONL files therefore make **no KGX conformance claim**.
The separate [bounded KGX projection](STANDARD_EXPORT.md) now audits the mapped
Reactome pathway subset using pinned upstream tools and preserves this full
packet. Full conformance and wider qualified mappings remain unresolved.

## Export and verify a graph

For a fully offline example, first create an explicitly synthetic run:

```sh
python3 app.py demo --out runs/gold_demo_source
python3 app.py gold-export --run runs/gold_demo_source --out runs/gold_demo_packet
python3 app.py gold-verify --packet runs/gold_demo_packet
```

For real data, replace `--run` with an existing ordinary saved Pharos/CIViC run.
The export requires its saved graph to reproduce exactly from the preserved
snapshots and review events, and requires consistent source metadata. It rejects
drift rather than rebuilding a different graph silently. Historical runs that
need migration must be replayed explicitly to a new run and identified as a new
baseline. Refresh runs and inherited review migrations are currently rejected:
their complete ancestry needs a dedicated extension before they can be handed
off through this interface.

The packet contains:

| File | Meaning |
|---|---|
| `packet_manifest.json` | Packet identity, source/version bindings, implementation hashes, counts and file inventory |
| `source/` | Original snapshot, graph, run manifest, review events and optional CIViC bytes; source licenses |
| `nodes.jsonl`, `edges.jsonl` | Every normalized node and evidence edge, including provenance and qualification |
| `assertions.jsonl` | Qualified claims grouped separately from their supporting evidence records |
| `context.jsonl`, `quarantine.jsonl` | Preserved contextual and quarantined records; neither becomes a pruning verdict |
| `decisions.template.json` | One explicit `abstain` row for every evidence edge; confidence is null |

The same source inputs and implementation produce the same packet ID. Snapshot
and graph content hashes coexist with raw-file hashes, so both content identity
and byte preservation can be checked. Offline verification reads the preserved
packet and does not fetch sources or substitute today's rebuilt graph. Unsigned
hashes detect changes relative to the receipt; they do not authenticate a
publisher, certify biological truth or prove independent evidence.

This is a scoped workbench graph, not a complete Pharos release. Source scope,
retrieval caps, omitted records and data kind remain in the preserved source
files. [Explicit-cohort construction](CONSTRUCTION.md) now publishes scoped
workbench graphs and these packets without inventing disease assertions.
Earlier retrieval-only chunks remain staging artifacts unless published through
that verified construction path.

## Keep, prune or abstain explicitly

Copy `decisions.template.json` outside the sealed packet before editing it. The
packet's inventory must remain unchanged. For each edge, the allowed disposition
is `keep`, `prune` or `abstain`. Retain its exact edge ID and packet ID. Actual
decisions require a named actor, method and reason. Every edge must occur once;
missing, unknown, duplicate or stale IDs fail validation.

```sh
cp runs/gold_demo_packet/decisions.template.json runs/gold_demo_decisions.json
python3 app.py gold-decisions \
  --packet runs/gold_demo_packet \
  --decisions runs/gold_demo_decisions.json \
  --out runs/gold_demo_dispositions
```

The unchanged template is valid and reports all edges as unassessed abstentions.
Local review acceptance, upstream curation status and structural validity are
never converted automatically into dispositions or gold labels. Confidence must
remain `null`; a calibrated score or organizer-required confidence contract has
not been established.

The output includes the full independently verifiable `baseline_packet/`, exact
decision bytes, all original nodes, an `edge_dispositions.jsonl` ledger and
separate keep/prune/abstain ID lists in the report.
The original graph remains available, including pruned and unassessed edges.
This is a reversible handoff, not a newly adjudicated graph or an assertion that
the organizers require this particular format.

## Prepare an external reference mapping

```sh
python3 app.py gold-reference-template \
  --packet runs/gold_demo_packet --out runs/gold_demo_mapping
```

The generated `reference_mapping.template.json` binds the baseline packet and
leaves reference metadata empty. Fill a separate copy only after inspecting the
actual artifact and its documentation:

- Supply its name, source description, version when known, raw file SHA-256,
  and kind: `organizer_reference`, `external_reference` or `synthetic_fixture`.
  These descriptions are recorded declarations, not authenticated provenance.
- Declare `baseline_version` when the reference specifies it. A declared mismatch
  is rejected; an unspecified version is reported as unknown, never compatible
  by assumption.
- Declare `delimiter` as `tab` or `comma` and map the header names explicitly.
  Input must be UTF-8 CSV/TSV with unique row IDs and consistent row widths.
- Select `unit`: `evidence_edge` or `assertion`. A claim label does not adjudicate
  every supporting evidence record. Pair-level prediction needs its own contract.
- Select exact local-ID matching (`match_mode: id`) or complete qualified identity
  (`qualified_identity`). A protein accession alone is not an edge identifier.

In ID mode, columns are `reference_id`, `label` and `target_id`; each value is
the corresponding column name in the input table. The label column may be null
for a reference that supplies only identifiers. In qualified-identity mode,
replace `target_id` with `subject`, `predicate`, `object`, `kind` and `qualifiers`.
The qualifiers cell contains a JSON object with all seven core slots explicit:
`disease`, `variant`, `therapy`, `species`, `tissue`, `cell_line`, `response`.
Use null for a genuinely unspecified slot. Supported additional context slots
remain part of the identity. A missing qualifier is not treated as a wildcard.

The initial adapter deliberately supports only identities already expressed in
the saved graph's local contract. It performs no synonym matching, gene/protein
collapse, disease equivalence, reversal of relations or qualifier removal.
An upstream identifier system will need an explicit reviewed crosswalk; we can
select the appropriate established mapping tool when the actual schema arrives.

```sh
python3 app.py gold-align \
  --packet runs/gold_demo_packet \
  --reference path/to/invented_reference.tsv \
  --mapping path/to/completed_mapping.json \
  --out runs/gold_demo_alignment
```

Synthetic fixtures can align only to explicitly synthetic packets. An organizer
or external biological reference cannot use the demo as its baseline.

## Interpret the alignment report

`report.json` contains identity coverage and input hashes; `alignment.jsonl`
retains each raw row, raw label, exact matches and reasons. A complete baseline
packet and the original reference/mapping bytes travel with the report.

| Status | Meaning |
|---|---|
| `matched` | Exactly one local unit matches exactly one reference row |
| `unmatched` | The exact local ID or complete qualified identity is absent |
| `ambiguous` | Several evidence records share the qualified identity |
| `reference_collision` | Multiple reference rows map to one local unit; excluded from unique coverage |

Empty labels remain empty. An unmatched or unreferenced edge is **not a negative**.
Different raw labels on colliding rows are displayed without guessing whether
they are semantically conflicting. Coverage fractions measure mapping coverage,
not agreement, precision or accuracy. `rows_scored` is zero and `metrics` is null.

Before adding scoring we still need the actual reference's task, scope, label
meanings, baseline relationship, held-out rules and required scoring/submission
format. We must also decide explicitly how abstentions, unmatched rows,
quarantined records and many-to-one mappings enter that protocol. No assay
outcomes or reserved INMC labels are opened by this workflow.

## Qualified assay attachment boundary

The current packet profile rejects runs carrying the new assay attachment.
It must not silently strip those observations or their original source bundle.
Use the ordinary complete run ZIP for these graphs until qualified packet
preservation is implemented. See [the attachment contract](ASSAY_WORKBENCH.md).
Organizer final labels may remain hidden; the official adapter needs their task,
baseline, label meanings, identifiers and scoring interface rather than access
to final answers. [Public references](literature/PUBLIC_REFERENCE_OPTIONS_20261026.md)
remain available for explicitly scoped local evaluation.
