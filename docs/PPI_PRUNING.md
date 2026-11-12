# Optional PPI pruning comparison

For the separate source-context policy, see [automatic task qualification](AUTOMATIC_TASK_QUALIFICATION.md).
It creates a direct human phosphoregulation view without a ranking budget.
Its source-eligibility result does not validate the PPI rankers described here
or classify excluded relationships as globally false.

This CLI workflow creates separate, reproducible graph views and measures their
utility on an already-consumed human Y2H assay panel. It preserves the original
source graph and does not change the app's default graph or enable automatic
pruning in the workbench.

The fixed comparison retains 80% of eligible **exact STRINGDB-only graph pairs**,
ranked either by native source score or Network Enhancement (NE). Mixed-provider,
non-STRING and unresolved evidence abstains and remains in every view. Equal graph
budgets do not imply equal numbers of retained pairs from the measured panel.

Use a working repository, Python 3.10+ and Docker on a CPU host with enough RAM
for the graph and its provenance replay. NE uses dense matrices; larger graphs
need additional memory. No language model, GPU or Brev model server is required.
The commands below use example destinations; replace `/path/to/...` inputs with
the existing audited files. Preserve old runs and choose new output directories.

## 1. Publish the audited source graph

The preparer consumes a completed PPI inventory and its source-only lookup audit;
it does not retrieve new data or read assay outcomes.

```sh
python3 scripts/prepare_ppi_pruning_graph.py \
  --retrieval /path/to/completed_ppi_inventory \
  --lookup-audit /path/to/source_only_lookup_audit.json \
  --output runs/ppi_pruning_example/source
```

This produces the ordinary source run, node/pair tables, a `gold_packet` and a
sealed `source_protocol.json`. Omit `--no-packet` for the complete comparison.
`--resume-existing` can finish an interrupted, unsealed preparation without
replacing its saved source files.

## 2. Run the published denoising implementation

The hash-pinned **GPL-3.0 author code** is fetched into an external ignored run
directory, with its license preserved. The MIT adapter invokes it without
reimplementing the algorithm or tuning its published defaults. Pull the immutable
official Octave image once; execution itself is offline.

```sh
python3 scripts/run_network_enhancement.py fetch-author \
  --out runs/ppi_pruning_example/external_author
docker pull docker.io/gnuoctave/octave:11.3.0@sha256:185db7993e000d4f3f6e7bbbf7fb3f999f52e799ea52231ad8a15353381e0dcb
python3 scripts/run_network_enhancement.py prepare \
  --nodes runs/ppi_pruning_example/source/network_nodes.tsv \
  --pairs runs/ppi_pruning_example/source/weighted_pairs.tsv \
  --author-source runs/ppi_pruning_example/external_author \
  --out runs/ppi_pruning_example/ne
python3 scripts/run_network_enhancement.py run \
  --author-source runs/ppi_pruning_example/external_author \
  --out runs/ppi_pruning_example/ne
```

`run` continues the prepared NE directory. Its `scores.tsv` covers original
weighted edges only; `manifest.json` binds source, input and runtime hashes.
These outputs contain scores, not biological verdicts.

## 3. Freeze the graph views, then explicitly score

Freeze verifies inputs, materializes all three retained graph packages and binds
the existing reference files before parsing outcomes:

```sh
python3 scripts/assess_ppi_pruning.py freeze \
  --source runs/ppi_pruning_example/source \
  --ne-output runs/ppi_pruning_example/ne \
  --candidates /path/to/unchanged_candidates.json \
  --assessment-rows /path/to/consumed_assessment_rows.json \
  --reference-predictions /path/to/unchanged_reference_predictions.json \
  --out runs/ppi_pruning_example/comparison
```

Optional `--with-ap` declares raw-score ranking analysis using the pinned sklearn
runtime; it is not AP of the pruned graph. `--decision-policy FILE` also binds a
separately reviewed interpretation policy. Declare these options before scoring.

After reviewing the frozen protocol, use its printed `content_sha256` in place
of `REVIEWED_PROTOCOL_SHA256`:

```sh
python3 scripts/assess_ppi_pruning.py score \
  --freeze runs/ppi_pruning_example/comparison \
  --protocol-sha256 REVIEWED_PROTOCOL_SHA256 \
  --out runs/ppi_pruning_example/results \
  --allow-consumed-outcome-access
```

Each `unpruned/`, `native_top80/` and `ne_top80/` package contains
`retained_graph.json`, `edge_dispositions.jsonl` and a complete `baseline_packet/`.
The retained graph is the full source workspace after that view's decisions;
the baseline preserves its original nodes, edges and provenance. An abstained
edge remains retained. `results/report.html` explains the comparison, while
`metrics.json` and `pair_accounting.jsonl` preserve denominators and pair states.

STRING functional association is different from direct physical binding. Assay
nondetection is conditional; source-absent pairs are uncovered, not pruned.
This retrospective panel and unresolved upstream study reuse cannot
establish independent scientific accuracy or universal false-edge labels.

See the [methods and literature rationale](evaluations/PPI_PRUNING_METHODS_20261111.md)
and the [comparison record](evaluations/PPI_PRUNING_COMPARISON_20261111.md).

## 4. Inspect the saved comparison in the app

Publish a compact preview from the completed results and their original frozen
inputs. This verifies saved files and edge commitments; it does not rerun the
assessment or replay the full source graph. The optional targets table must be
the one bound by the source protocol, so displayed protein names are traceable.

```sh
python3 scripts/publish_pruning_preview.py \
  --results /path/to/completed/results \
  --protocol /path/to/frozen/comparison/protocol.json \
  --groups /path/to/frozen/pair_groups.json \
  --targets /path/to/ordinary_run/targets.tsv \
  --source-protocol /path/to/source/source_protocol.json \
  --decision-policy /path/to/decision_policy.json \
  --output runs/pruning_assessment_example/pruning_preview
```

Open **Compare & assess → Review a saved pruning assessment**. Original is the
default view; switching to Native score or Network Enhancement changes only the
saved preview. Search for a protein, inspect removed pairs, or use the
CCNO–CDKN1A walkthrough. The pair diagram, assay observation and source trace
show why a policy decision needs biological qualification. Unassessed, excluded,
nondetected and source-absent pairs have separate labels.

The three-view table always shows the full assessment's counts; search results
are a paginated subset. Saved-assessment downloads describe this comparison,
not the currently loaded workspace. Preview pair choices are not a complete
retained-graph export: the original comparison packages preserve those graphs
and full edge ledgers. No preview control applies pruning, changes a question,
calls a model or retrieves more evidence. Brev is not needed to browse it.
