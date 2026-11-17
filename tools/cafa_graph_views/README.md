# Paired graph-view function prediction

This optional secondary experiment asks whether the project's **existing graph
interventions** improve later GO annotation recovery under the **same** published
FastSinkSourcePlus predictor. It complements the separately frozen algorithm
comparison in `tools/cafa_prediction/`; it cannot replace that primary candidate
after outcomes are inspected.

The preserved native-confidence, human-experimental and Network Enhancement
80% selections already existed before this CAFA assessment. The existing shared
forest safeguard, rankings, tie rules and protected pairs are reused exactly.
No threshold, edge weight, forest or ranking is fitted to CAFA labels. All views
retain all 3,172 graph proteins and the same 1,294 partial-knowledge target IDs,
even if an edge mask isolates a target. Each numerical view retains 71,404 of
87,688 qualified historical STRING weights. The full-source safeguard and the
weighted numerical graph have different scopes; actual numerical components and
isolates are recorded instead of assuming identical connectivity.

The source and label versions, author code, isolated runtime, fixed predictor
parameters and training sets come from the parent prediction freeze. This
adapter invokes the same unchanged author functions; no ML method is rewritten.
Network Enhancement's [primary paper](https://doi.org/10.1038/s41467-018-05469-x)
evaluated gene-function prediction, making this a better aligned transfer test
than treating every binary assay nondetection as a false functional association.
The completed official-CAFA comparison is summarized in the
[scientific results](../../docs/evaluations/SCIENTIFIC_RESULTS_20261114.md): none
of these three pruning views has a paired BPO recovery interval excluding zero
against the unpruned comparator. They remain optional sparsification views.

Preparation verifies the original graph-view receipt and membership bytes,
checks their exact network qualification against the parent, and rejects altered
weights, missing or duplicate pair IDs, changed nodes or unequal retained edge
budgets. It accepts no future reference labels. Prediction rechecks the frozen
source and code pins before and after execution.

```sh
python -m unittest tools.cafa_graph_views.test_views -v
python -m tools.cafa_graph_views.run prepare \
  --parent PARENT_FROZEN --parent-sha256 PARENT_PROTOCOL_FILE_SHA \
  --mask-protocol EXISTING_SAFEGUARD_PROTOCOL \
  --membership EXISTING_MEMBERSHIP --output NEW_FROZEN
python -m tools.cafa_graph_views.run predict \
  --frozen NEW_FROZEN --protocol-sha256 NEW_PROTOCOL_FILE_SHA \
  --output NEW_PREDICTIONS
```

Use the same pinned NumPy/SciPy runtime documented by the parent adapter.
The resulting graph-view TSVs and parent unpruned FSS output are evaluated on
the same later-curation population. Standard CAFA partial-knowledge masking,
ontology propagation, information accretion, coverage and paired uncertainty
must be shared. Unknown/unannotated biology is not asserted false. A gain here
would be a bounded function-prediction gain, not a whole-graph biological truth
percentage or permission to apply universal biological pruning.

These previously developed masks have already been evaluated against other
assays. That history stays disclosed; only the CAFA endpoint is newly assessed.
Original graphs and all earlier failed comparisons remain intact.
