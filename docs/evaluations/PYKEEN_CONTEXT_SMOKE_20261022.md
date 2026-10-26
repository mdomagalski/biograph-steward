# Native PyKEEN context/supervision smoke

October 22, 2026. **The proposed library wiring passed on a tiny invented graph.**
This is an engineering check, not a biological comparison or accuracy result.
No INMC, Pharos, assay outcomes, pretrained embeddings, GPU or Brev instance were
used. It does not freeze the scientific protocol.

The [script](../../scripts/smoke_pykeen_context.py) reuses PyKEEN **1.11.1** and
PyTorch **2.6.0** in the existing isolated CPU environment. It has only an output
directory argument; all input triples are invented constants. The
[summary receipt](pykeen_context_smoke_20261022_summary.json) binds the script and
local runtime artifacts. Full logs and synthetic scores are retained under
`runs/pykeen_context_smoke_20261022/attempt2/`. The earlier successful attempt is
also retained; the second adds an initial-parameter equality check.

## Existing capabilities exercised

PyKEEN accepts the graph factory used by R-GCN's representation separately from
the factory passed to its native `SLCWATrainingLoop`. This permits contextual
edges to affect message passing while keeping target-relation supervision
identical. The model's saved adjacency buffers were checked against each
intended context factory. No trainer or sampler was replaced.
[Pinned R-GCN implementation](https://github.com/pykeen/pykeen/blob/v1.11.1/src/pykeen/nn/message_passing.py),
[training API](https://github.com/pykeen/pykeen/blob/v1.11.1/src/pykeen/training/training_loop.py).

| Arm | Adjacency triples | Supervised triples | Actual optimizer steps |
|---|---:|---:|---:|
| R-GCN scaffold | 12 | 12 | 2 |
| R-GCN context | 18 | 12 | 2 |
| R-GCN enriched context | 21 | 12 | 2 |
| ComplEx scaffold control | No message passing | 12 | 2 |

All arms retain the same eight-entity and three-relation identifier dictionaries,
including vocabulary absent from an arm's edges. R-GCN initialization hashes
match across its three arms. The native graph-based `schlichtkrull` sampler is
used on the common supervision factory. The smoke uses one full supervision
batch per epoch: sorted positive-batch contents match across all arms, and Adam
state confirms two updates. This does not verify matching arbitrary minibatch
schedules or identical negative draws.

Every factory uses `create_inverse_triples=False`, as required by native R-GCN's
internal inverse message passing. Both directions of the undirected supervised
relation are explicit fixture records; held-out directions are absent from every
training graph. Those explicit relation records are distinct from creating
extra inverse relation types.

The existing `PythonSetFilterer` is initialized with supervised positives and
both orientations of invented reserved/development pairs. It is passed as an
instance into the native `PseudoTypedNegativeSampler`. Direct checks reject all
four held-out triples and retain an allowed corruption; a sampling probe
actually proposes and filters **325** held-out triples. Every observed training
batch also has its retained negative samples checked against the exclusion set.
The pseudo-typed probe only proposes gene endpoints for the interaction
relation. This demonstrates a reusable exclusion mechanism, not ontology
validation or measured negative evidence.
[Pinned sampler](https://github.com/pykeen/pykeen/blob/v1.11.1/src/pykeen/sampling/negative_sampler.py),
[exact filter](https://github.com/pykeen/pykeen/blob/v1.11.1/src/pykeen/sampling/filtering.py).

Native `predict_triples` scores the fixed held-out triple list in both
orientations. All scores are finite; R-GCN/DistMult is symmetric within floating
point tolerance, while the ComplEx control can differ by orientation. The
script records the arithmetic mean for each invented undirected pair. No
ranking or classification accuracy is calculated.
[Pinned prediction API](https://github.com/pykeen/pykeen/blob/v1.11.1/src/pykeen/predict.py).

## Warnings and limits

The runtime emits an R-GCN layer `reset_parameters` warning. Source inspection
shows that the enclosing model recursively resets child modules; the local
representation also emits a warning for its layer container. We preserved the
warning and verified equal actual starting parameter hashes across R-GCN arms,
instead of patching initialization or treating the warning alone as an observed
failure. The prediction helper also warns about CPU automatic memory sizing;
the fixture is tiny and the prediction batch is explicitly bounded at two.
[Pinned recursive initialization](https://github.com/pykeen/pykeen/blob/v1.11.1/src/pykeen/models/nbase.py).

Dropout is disabled and dimensions are small for this wiring check. These are
not selected biological hyperparameters. Matched optimizer updates are not
equal runtime cost: larger adjacency is more expensive. Full-graph CPU/GPU
scaling, study leakage controls, an independent development split, actual source
enrichment, uncertainty and scientific results remain untested. The separate
context/supervision design remains a declared evaluation adaptation, not a
reproduction of an INMC submission.

Reproduce using the already installed isolated environment and a new directory:

```sh
runs/link_prediction_reuse_audit_20261022/venv/bin/python \
  scripts/smoke_pykeen_context.py \
  --output-dir runs/pykeen_context_smoke_repeat
```

The script refuses to overwrite results, requires the pinned PyKEEN/PyTorch
versions, and confines default caches to its output directory. It does not
install dependencies or start compute. **Brev remains unnecessary for this
engineering smoke and ordinary Pharos retrieval.**
