# Automatic task qualification

`qualify-task` creates a separate graph for **source-reported direct human
phosphorylation/dephosphorylation**. It checks explicit native SIGNOR fields,
writes one decision for every original evidence record, and materializes a
retained graph through the existing Gold interface. No source is deleted or
rewritten. This is automatic task qualification, not a biological-false-edge
classifier or an accuracy score.

## Fixed profile

The profile is `source-reported-direct-human-phosphoregulation.v1`:

| Decision | Native source conditions |
| --- | --- |
| Keep for this task | `DIRECT=t`, mechanism phosphorylation/dephosphorylation/autophosphorylation, experimental `TAX_ID=9606` |
| Prune from this task view | Explicit `DIRECT=f`, a recognized nonhuman experimental species, or one of the explicitly recognized incompatible mechanisms below |
| Abstain and retain | Unknown directness/mechanism, in-vitro code `-1`, unreported organism, or an unrecognized literal, unless another field already establishes incompatibility |

The recognized incompatible mechanisms are binding, transcriptional regulation,
acetylation, ubiquitination and polyubiquitination. Other mechanism strings do
not silently become negatives. Records outside the SIGNOR profile receive
abstain-and-retain decisions. There is no fitted threshold or removal budget.

The v1 taxon vocabulary uses the already captured NCBI metadata for mouse
(`10090`), African green monkey (`9534`), pig (`9823`) and rat (`10116`). Other
numeric IDs remain unknown. A [TaxId can identify a higher taxonomic group](https://www.ncbi.nlm.nih.gov/datasets/docs/v2/data-processing/taxonomy-processing/taxonomy/),
so an unfamiliar ID is not automatically nonhuman. The profile records this
bounded vocabulary and its source binding; expanding it requires verified
taxonomy metadata rather than guessing from a numeric mismatch.

**Keep does not mean biologically accepted.** It means the supplied metadata
fit this profile. Directness is source-reported; it does not establish purified
catalysis. Human participant identifiers do not establish a human experiment,
and the experimental-organism field does not prove a particular human cell,
endogenous state, colorectal context, isoform or canonical site. A valid binding
observation can be excluded from a phosphorylation question while remaining
useful evidence for another question.

The retained graph keeps unknown and outside-profile evidence as background.
Only the records marked **keep** by this policy form its explicitly eligible
source core. Do not describe every retained edge as direct human
phosphoregulation or scientifically validated evidence.

## Existing methods and verified implementation gap

[INDRA's assembly tools](https://indra.readthedocs.io/en/latest/_modules/indra/tools/assemble_corpus.html)
already implement mechanistic filtering and evidence-aware curation. Its
reviewed 1.24.0 `filter_direct` defaults unknown directness to direct, and its
human filter checks participant grounding rather than experimental organism.
Those defaults do not implement this strict profile. Curation belief updates
also must not be interpreted as experimental truth.

This adapter therefore reuses the project's already verified native SIGNOR
reader and Gold APIs, adding only the explicit task gate. It verifies the
publication, complete source bytes, native record/ordinal/raw row, observation
and exact graph edge before writing decisions. Gold rebuilds surviving
assertion support and preserves the complete original baseline. There is no
new grounder, literature classifier or confidence formula. See the
[SIGNOR source contract](BIOLOGICAL_SOURCE_UPDATE.md) and
[PhosphoSIGNOR publication](https://doi.org/10.1093/nar/gkaf1237).

## Run

Use an authorized complete source packet containing the verified SIGNOR layer.
Use new output directories:

```sh
python3 app.py gold-export --run runs/crc_biological_workspace_20261112 \
  --out runs/my_source_packet
python3 app.py qualify-task --packet runs/my_source_packet \
  --out runs/my_direct_human_phosphoregulation
```

Core Python 3.10+ is sufficient; no model, network request, GPU or Brev is
needed. The command writes:

- `task_qualification.json`: fixed profile, full-family coverage, exact source
  bindings, per-source decisions and explicit interpretation limits.
- `decisions.json`: all original evidence-edge decisions with reasons and null
  numeric confidence.
- `retained/retained_graph.json`: the new task-qualified graph.
- `retained/edge_dispositions.jsonl`: the exhaustive decision ledger.
- `retained/baseline_packet/`: the complete original source baseline.

This is a derived Gold projection, not an ordinary source run to replace the
workbench's default workspace. Review states remain unchanged for unchanged
assertions; changed support follows the existing Gold revision rules.
Unreviewed or rejected evidence is never accepted merely because it fits the
task. Other source support for the same pair is not removed with an excluded
record. Original sources and their separate redistribution terms remain.

The [executed CRC assessment](evaluations/AUTOMATIC_QUALIFICATION_20261112.md)
records the first full graph, independent replay and remaining scientific gaps.

The subsequent [GO qualification workflow](SCIENTIFIC_QUALIFICATION.md) adds
native context recovery and a separate ontology-currentness view. It does not
change this phosphoregulation profile or combine its exclusions by default.
