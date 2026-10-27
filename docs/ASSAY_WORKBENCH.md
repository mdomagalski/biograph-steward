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

## Source-preserving evaluation handoff

`gold-export` now accepts an attached or reviewed assay cohort:

```sh
python3 app.py gold-export \
  --run runs/assay_workbench_20261026 \
  --out runs/assay_gold_packet_20261026
```

The packet includes every combined evidence edge and assertion, a separate
`assay_observations.jsonl` ledger including failed assays, the attachment
sidecar, and the complete byte-identical publication under
`source/assay_source/`. Original source licenses and all experiment, construct,
orientation, outcome and row-location qualifications remain intact. Zero
selected observations still preserves the full publication and reports a
zero count; absence from the chosen cohort is not a negative result.

Export verifies ordinary source/review replay. Offline packet loading checks
nested receipts, source bindings and the existing observation projection, plus
qualified assertion and review identities, without reconstructing or replacing
the saved Pharos graph. Original input directories and network access are not
needed. This is a project-local preservation format, not an official gold set,
KGX/PSI-MI conformance claim, or a rerun of the historical scientific assessment.

Every edge defaults to `abstain` with unknown confidence, including observations
that received an ordinary human-review acceptance. Failed assays have no edge
and remain in their source ledger rather than becoming negative decisions.
The decision export also carries the complete packet; see the
[decision handoff contract](GOLD_SET_INTERFACE.md).

When the cohort was selected by the bounded construction planner, its saved
`construction_planner_trace.json` also travels byte-for-byte through attachment,
review, replay and gold export. The trace is bound to the exact constructed
request and its saved-run manifest. A missing marked trace or a trace for another
request is rejected. This preserves what selected the retrieval tools; it does
not claim that the model's interpretation of the question was scientifically
correct.

## Explicit limits

- The ordinary guided neighborhood question still excludes assay-qualified
  observations. It must not convert a nondetection into a positive interaction
  path. Inspect the dedicated assay ledger and passports for these records.
- Cohort refresh and the restricted Reactome KGX profile still reject attached
  runs. Use the source-preserving gold packet or complete ordinary run ZIP.
  Qualified standard export is a separate mapping increment; silently exporting
  only the baseline would be misleading.
- The assay panel is consumed. Its own outcomes cannot independently validate
  adding this layer. No scientific improvement, clinical relevance, independent
  experiment count or automatic pruning is inferred.
- Agent-selected construction and intended-user task evaluation remain next
  steps. Source integrity and import fidelity do not substitute for them.

For an external reference, the [public-resource audit](literature/PUBLIC_REFERENCE_OPTIONS_20261026.md)
selects IntAct/IMEx for bounded evidence-fidelity preparation. Organizer final
labels may remain hidden; their task, baseline, label meanings and scoring
interface are the information needed for the official handoff.

The [IntAct adapter and dedicated source-evidence question](INTACT_EVIDENCE_WORKBENCH.md)
now reuse this attachment and export framework. They preserve the MITAB evidence
model and use a separate inspector; the Lambourne construct and frozen-lookup
explanation is not applied to IntAct records. The real source publication is
available offline. The real Pharos-attached import, readable answer and gold
export now pass source fidelity on all four eligible development records.
The small positive-only panel does not establish biological accuracy or gain
over Pharos; four reserved studies remain unopened.
