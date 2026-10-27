# Guarded Reactome execution and scoring handoff

Engineering preparation is complete. **The real execution is not frozen.**
The saved graphs remain outcome-free and unchanged. Actual-device resource
proof, final execution freeze, six real fits and consumed-panel scoring are
pending a separately announced compute phase. No real resource fit, assay
outcome access, reserved IntAct access, Brev access or paid compute occurred
while implementing this handoff.

The [readiness receipt](reactome_context_handoff_20261026_summary.json) binds the
current code, saved graph and fresh synthetic proof. The earlier
[native receipt](reactome_context_native_20261026_summary.json) remains historical
evidence; its runner hash predates the added full-fit admission check and cannot
freeze this current implementation. Its proof and all original experiment
receipts are preserved.

## Verified reuse and remaining gap

The original `inmc_outcomes.materialize` and `score_comparison` already enforce
complete-assay eligibility, exact original identities, author-reference
reconciliation, AP/ROC-AUC and descriptive leave-one-original-gene-out influence.
The historical four-arm graph/run/freeze wrapper intentionally rejects this
separate two-arm experiment. The new fixed wrappers reuse those semantics,
file safety and proof helpers while binding the Reactome profile.

Native metrics use the installed scikit-learn 1.9.1 implementation. Its official
[AP documentation](https://scikit-learn.org/stable/modules/generated/sklearn.metrics.average_precision_score.html)
defines non-interpolated average precision; the official
[ROC-AUC documentation](https://scikit-learn.org/stable/modules/generated/sklearn.metrics.roc_auc_score.html)
accepts ranking scores. Coverage scores retain their 0/1/2 ties; no custom metric,
new assay rule, learned threshold or new prediction method is introduced.
Fresh freeze/scoring processes use the same supported
[PyStow cache configuration](https://pystow.readthedocs.io/en/latest/installation.html#configuration)
as the runner, with a writable workspace cache before native imports.

`freeze_reactome_context.py` validates the prepared graph and actual installed
runtime, authenticates the synthetic and resource reports plus their bound
manifests/receipts/artifacts, and writes a separate immutable `execution.json`.
The envelope binds graph/source/code/profile, scorer, outcome adapter, handoff
helpers, reporting contract and both complete native proofs. Missing, corrupt,
stale or synthetic-only resource proof creates no freeze. Full fitting checks
this entire handoff before `_fit`; the scorer checks it again before source
access. The prepared graph never changes to claim a freeze.

`score_reactome_context.py` authenticates all six runs and every candidate and
development query, finite bidirectional means, native adjacency, complete fixed
budgets, checkpoints and all five paired audit fingerprints before opening source
containers. It preserves original eligibility and requires **1,751 off-diagonal
pairs: 737 detected and 1,014 nondetected**. Every nomination has a finite score;
there is no per-arm deletion. Source hashes are checked before decoding; identity
and reconciliation failures block metrics. An access-start receipt precedes
semantic access and a failure receipt preserves subsequent errors.

Reporting includes every paired AP and ROC-AUC delta and arithmetic means for
each arm and the deltas, all 0/1/2 Reactome endpoint coverage strata, the tied
coverage-only diagnostic on the same primary denominator, original context and
mapping coverage, and descriptive gene-removal influence. Empty or single-class
strata retain explicit statuses and null metrics. There are no p-values,
significance claims or independent-validation claims.

## Engineering evidence

All **44 Reactome controls** pass with required native dependencies present,
including 13 new handoff controls. The full invented replay runs actual graph
preparation/validation, a no-query resource branch, freeze, six tiny native fits,
authenticated source parsing and reporting. Test-only source-loader, tiny-budget
and declared-population injections are confined to unittest patches; they are
not public execution options and cannot authorize a real freeze. The invented
three-pair primary denominator is explicitly rejected against the real 1,751
contract.

Controls cover missing predictions/checkpoints, incomplete runs, changed masks
and candidates, code/graph/runtime/query/adjacency drift, corrupt or stale proofs,
source and assay failures, stale handoff rejection before fitting, positive,
negative and mixed changes, tied zero coverage, missing context and empty strata.
Original freeze (9), scoring gate (16) and outcome (14) controls also pass,
without skips. No static typecheck is configured; no UI changed.

The fresh current native proof is
`runs/reactome_context_native_20261026_handoff_final/report.json`: invented CPU data
only, six runs at four updates each, actual message passing/cache controls and
matched fingerprints. It authorizes no real graph fitting. Dry validation of
`runs/reactome_context_graphs_20261026_final` checks the unchanged 99,394
supervision triples, 500 updates per arm/seed and 3,000 across six full fits.

## Exact next commands — pending the separate compute announcement

Run these in order from the repository root using the same runtime/device.
Each output must be new. A CPU freeze authorizes only this exact CPU runtime;
a CUDA run would require its own runtime/resource proof and freeze, and scoring
on that same runtime/device. Brev is unnecessary for the local CPU path.

```sh
runs/reactome_context_runtime_20261026/venv/bin/python scripts/run_reactome_context.py --graph runs/reactome_context_graphs_20261026_final --output-dir runs/reactome_context_resource_20261026_cpu --device cpu --resource-check

runs/reactome_context_runtime_20261026/venv/bin/python scripts/freeze_reactome_context.py --graph runs/reactome_context_graphs_20261026_final --synthetic-check runs/reactome_context_native_20261026_handoff_final/report.json --resource-check runs/reactome_context_resource_20261026_cpu/report.json --device cpu --output-dir runs/reactome_context_execution_20261026_cpu

runs/reactome_context_runtime_20261026/venv/bin/python scripts/run_reactome_context.py --graph runs/reactome_context_graphs_20261026_final --execution-packet runs/reactome_context_execution_20261026_cpu --device cpu --output-dir runs/reactome_context_comparison_20261026_cpu/predictions

runs/reactome_context_runtime_20261026/venv/bin/python scripts/score_reactome_context.py --graph runs/reactome_context_graphs_20261026_final --execution-packet runs/reactome_context_execution_20261026_cpu --predictions runs/reactome_context_comparison_20261026_cpu/predictions --archive runs/link_prediction_reuse_audit_20261022/inmc_release_v1.zip --workbook /private/tmp/inmc_official_source_data.xlsx --device cpu --output-dir runs/reactome_context_comparison_20261026_cpu/scored
```

The resource step fits both arms once at seed 17 for one epoch, 25 updates each,
and constructs no candidate/development queries. After its passing proof the
freeze can authorize the fixed six-run comparison. Final outputs are
`execution.json` in the execution directory, `report.json` in the predictions
directory, and `metrics.json`, `outcomes.json`, `exposure_started.json` and
`report.json` in the scored directory. Any failure stops this sequence; preserve
its attempt and resolve integration faults on invented controls.

## Scientific boundary

This is one fixed retrospective development comparison on a consumed panel.
The source postdates assays, Reactome import release and study lineage remain
unverified, and a membership is not a direct-binding assertion. Preserve prior
negative experiments. Report a mixed or negative result as a completed finding,
without changing eligibility, seeds, model, budget or features in response.
Independent predictive benefit, general biological truth, graph-pruning validity,
organizer evaluation fit and usability remain unestablished. The midpoint report
has not been changed to claim any measured improvement.
