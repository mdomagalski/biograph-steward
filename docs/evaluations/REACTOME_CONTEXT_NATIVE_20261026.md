# Native two-arm Reactome learner verification

The fixed Reactome adapter passes invented CPU controls with the installed
PyKEEN 1.11.1 / torch 2.6.0 runtime. This is engineering evidence only. The
prepared real graph has been validated without fitting or scoring; its exact
device resource proof and execution freeze remain pending.

The [native receipt](reactome_context_native_20261026_summary.json) binds the
final synthetic run, implementation, installed source hashes and checks.
The [source-bound graph pair](REACTOME_CONTEXT_GRAPH_20261026.md) and
[selected scientific contract](../literature/REACTOME_CONTEXT_INTERVENTION_20261026.md)
remain unchanged. The original INMC assay panel is consumed development data.

## Verified reuse and integration gap

The historical runner already uses native basis R-GCN, interaction-only
supervision, ordinary native minibatches, typed negative proposals and exact
identity filtering. Its four-arm GO-hierarchy validator cannot accept this
two-arm membership comparison. `scripts/run_reactome_context.py` is a separate
fixed adapter; historical scripts and receipts are preserved.

The review checked the installed sources and versioned official
[message-passing implementation](https://pykeen.readthedocs.io/en/v1.11.1/_modules/pykeen/nn/message_passing.html),
[training loop](https://pykeen.readthedocs.io/en/v1.11.1/_modules/pykeen/training/training_loop.html)
and [pseudo-typed sampler](https://pykeen.readthedocs.io/en/v1.11.1/_modules/pykeen/sampling/pseudo_type.html).
The receipt fingerprints the actual installed Python modules. These hashes and
package versions bind the inspected implementation; they do not fingerprint
every compiled numerical kernel or establish bitwise equivalence across devices.

Specific native behavior verified in this runtime:

- Both context factories and supervision keep the same complete dense union
  entity/relation IDs, without inverse triples or ID compaction. Conversion
  rejects unknown IDs and checks the actual mapped set/count against input.
- R-GCN receives each arm's context factory. Both the training-loop constructor
  and `train()` receive only interaction supervision. The complete relation
  vocabulary includes context-only relations whose typed sampler intervals are
  empty; only the observed interaction relation is sampled.
- Constructing edge/self-loop dropout at zero creates native zero-probability
  self-loop modules. The representation's supported `edge_dropout=None` branch
  avoids adjacency-dependent unused random draws made at numeric zero. No
  native implementation is patched.
- Native `train()` resets parameters. The first `pre_batch` records named
  parameters after that reset. Batch callbacks observe proposals and masks
  without drawing randomness or changing them. Callback counts are checked
  against final Adam step counters and complete per-epoch supervision coverage.
- `sampler=None`, `num_workers=0`, `drop_last=False` and disabled automatic memory
  optimization preserve the tested ordinary native batching path, including
  isolated IDs. Native advisory warnings are retained in each attempt's log.

## Invented proof

The fixture contains a six-gene interaction ring, two original gene-to-product
links, two products sharing one invented pathway, an endpoint with no context
and an isolated pathway ID. It includes literal candidate/development exclusions
and an additional equivalent-identity mask, in both orientations. No biomedical
input, assay outcome or pretrained weight is used.

The trained models use the selected three layers, 32 dimensions, four bases,
ReLU, SoftplusLoss, Adam 0.001 and 16 typed proposals per positive. For the tiny
fixture only, two epochs at batch size eight give **four optimizer updates per
arm/seed, 24 total**, across seeds 17/43/101. This is explicitly separate from
the real budget. For every seed both arms have identical fingerprints for
actual initial parameters, positive minibatches, negative proposals, filter
masks and accepted negatives. Every loss and prediction is finite; query
identities/order are exact and forward/reverse DistMult scores agree.

A separate analytical transport probe sets controlled positive weights inside
the **same native 32-dimensional, four-basis, three-layer architecture**. Passive
layer hooks observe pathway → product → gene signal after two layers and
other product → pathway → product → gene signal after three. It isolates these
relations from alternative interaction-ring routes. Missing/isolated context
receives no signal. The complete gene → product → pathway → product → gene
route takes four hops; this does not claim that three layers span that route.
The native post-parameter-update hook invalidates cached representations;
`eval()` alone retains a populated cache.

31 Reactome projection/runner controls, 17 existing runner controls (with
`BIOGRAPH_TEST_GRAPH_ML=1`) and three existing hierarchy controls pass with no
skips. No static typecheck is configured and no UI changed. Earlier synthetic
attempts and failed test logs remain saved; only the receipt below binds the
final runner.

## Commands and pending gates

Final synthetic evidence is at
`runs/reactome_context_native_20261026_final/report.json`. To reproduce it, use a
new output directory:

```sh
runs/reactome_context_runtime_20261026/venv/bin/python scripts/run_reactome_context.py --synthetic-check --output-dir runs/reactome_context_native_REPLAY
```

Dry real-packet validation has passed:

```sh
runs/reactome_context_runtime_20261026/venv/bin/python scripts/run_reactome_context.py --validate runs/reactome_context_graphs_20261026_final
```

The unchanged 99,394 supervised triples produce 25 ordinary batches per epoch:
20 epochs give **500 updates per arm/seed and 3,000 across six full runs**. Full
execution rejects a different schedule, changed source/graph/code, unsafe
paths, incomplete arm/seed output and mismatched paired fingerprints. It
requires a separate sealed `execution.json` binding the graph, native runtime,
implementation, scorer, outcome adapter and complete passing proofs. The
prepared graph is never rewritten to assert a freeze.

The next real-resource command is recorded here but **has not been run**. It
must be announced as the subsequent compute phase first:

```sh
runs/reactome_context_runtime_20261026/venv/bin/python scripts/run_reactome_context.py --graph runs/reactome_context_graphs_20261026_final --output-dir runs/reactome_context_resource_20261026_cpu --device cpu --resource-check
```

That check fits both arms for one epoch at seed 17: 25 updates each, 50 total.
It constructs no candidate or development queries and writes no predictions.
It is not a final freeze, biological comparison or assay assessment. The later
full run requires `--execution-packet` and retains all 3,276 nominations;
the later scorer must apply the unchanged original 1,751 eligible-pair
denominator. No cohort, seed, feature or budget search is authorized.

No real graph fitting, real candidate scoring, outcome loading, reserved IntAct
access, Brev access or paid compute occurred in this story. Local checks do not
need the Brev instance. Prediction gain and source independence remain
unmeasured; a valid mixed or negative later comparison is a complete result.
