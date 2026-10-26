# Qualified assay evidence in the workbench

The existing Lambourne publication can be attached to an ordinary, live Pharos
protein-cohort run. This closes the source attachment and inspection boundary;
it does not create a new biological benchmark or demonstrate prediction gain.
The implementation reuses the published observation projection, the existing
source-sidecar pattern and ordinary assertion review. The scientific mapping
follows the [PSI-MI/IMEx reuse decision](literature/ASSAY_EVIDENCE_REUSE_20261025.md).

## Use the attachment

Open a saved explicit protein cohort in the running workbench. In **Qualified
assay evidence**, choose a saved publication and select **Attach observations in
a new run**. Publication folders must be immediate children of the configured
runs directory. The initial list shows receipt metadata; attachment checks the
full saved source material before publishing a new output.

The equivalent offline command is:

```sh
python3 app.py assay-attach \
  --run runs/assay_cohort_source_20261026 \
  --publication runs/lambourne_assay_evidence_20261025 \
  --out runs/assay_workbench_20261026
```

Inputs must already exist, and the output must be a new directory. Real source
data remain outside Git. A fresh clone needs the complete saved publication
and a compatible cohort, or a newly retrieved cohort. No model, GPU, cloud
account or new source retrieval is required for attachment itself.

Both proteins in an observation must resolve exactly inside the declared
1–25-protein cohort. No identifier aliases or incidental partners expand the
scope. Every matching observation is retained, including excluded assays.
Evaluable detections and nondetections have distinct qualified observation
edges; excluded assays remain in the ledger without an edge. Zero matching
observations is a valid, explicitly reported result.

Filter by cohort protein or outcome and select an observation to inspect its
original assay record, AD/DB constructs, source locators and frozen Pharos
lookup. **That lookup describes the original assessment, not a new lookup of
the current cohort.** Source downloads are returned as data, not executable
pages. The ordinary assertion passport supports local review of eligible
observations. Such acceptance records a person's review, not experimental
truth or a benchmark label.

## Preservation and verification

The new run contains the original Pharos snapshot, combined graph, selected
observation ledger, source-bound attachment sidecar and a byte-identical
`assay_source/` copy of the complete publication. The ordinary run ZIP includes
all of these. Original study-relative source locators resolve under that
directory. The original Pharos records and assertion identities are preserved.
Upstream licensing material travels with the source; the software's MIT license
does not silently license the assay data.

Intake checks receipt/file hashes, the nested frozen-source and result
inventories, source-table bindings and deterministic observation reprojection.
It does **not** rerun the historical scientific assessment under changed code
or authenticate the publisher. Exact historical replay remains available using
[checkpoint `3f7c462`](evaluations/CHECKPOINT_REPLAY_20261026.md); its receipts
have not been modified or weakened.

Reopening checks the saved graph and source bindings. Assay review events bind
both the publication and the cohort selection. Changed evidence cannot inherit
an incompatible old decision. A reviewed run preserves the complete source
publication even when the original directories are unavailable.

For explicit command-line replay, preserve the sidecar and its sources:

```sh
python3 app.py replay \
  --snapshot runs/assay_workbench_20261026/snapshot.json \
  --assay-run runs/assay_workbench_20261026 \
  --reviews runs/assay_workbench_20261026/review_events.json \
  --out runs/assay_workbench_replay_20261026
```

Replay from an attached snapshot's directory without `--assay-run` is rejected
to prevent accidental source loss. Use a new output directory each time.

## Explicit limits

- The ordinary guided neighborhood question still excludes assay-qualified
  observations. It must not convert a nondetection into a positive interaction
  path. Inspect the dedicated assay ledger and passports for these records.
- Cohort refresh and the current gold/KGX packet profile reject attached runs.
  Use the complete ordinary run ZIP. Qualified standard export is a separate
  mapping increment; silently exporting only the baseline would be misleading.
- The assay panel is consumed. Its own outcomes cannot independently validate
  adding this layer. No scientific improvement, clinical relevance, independent
  experiment count or automatic pruning is inferred.
- Agent-selected construction and intended-user task evaluation remain next
  steps. Source integrity and import fidelity do not substitute for them.

For an external reference, the [public-resource audit](literature/PUBLIC_REFERENCE_OPTIONS_20261026.md)
selects IntAct/IMEx for bounded evidence-fidelity preparation. Organizer final
labels may remain hidden; their task, baseline, label meanings and scoring
interface are the information needed for the official handoff.
