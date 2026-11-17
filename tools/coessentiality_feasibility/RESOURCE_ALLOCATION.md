# Separate resource-allocation readout

This optional extension reuses the completed source/reference packet. It is
declared after the original experimental outcomes were consumed. It does not
change the graph or rerun a learner. Read [ra_contract.md](ra_contract.md) before
execution; all weights and results must follow its separate freeze.

Use the reviewed optional runtime containing NumPy and NetworkX3.7. The fixed
hash seed controls the native common-neighbor set summation order. The original
source verifier also needs its previously pinned author XSwap runtime.

```sh
PYTHONHASHSEED=2026111301 python -m tools.coessentiality_feasibility.resource_allocation freeze \
  --source-frozen ORIGINAL_FROZEN_SOURCE \
  --captured ORIGINAL_NATIVE_COLUMN_CAPTURE \
  --prior-scored ORIGINAL_BINARY_RESULTS --out NEW_RA_FREEZE
PYTHONHASHSEED=2026111301 python -m tools.coessentiality_feasibility.resource_allocation evaluate \
  --frozen NEW_RA_FREEZE --out NEW_RA_RESULTS
python -m tools.coessentiality_feasibility.resource_allocation_report \
  --scored NEW_RA_RESULTS --out NEW_RA_READABLE_REPORT
```

Native `networkx.resource_allocation_index` runs on each full-frame simple
gene/model incidence graph with an explicit gene-pair list and CPU backend.
It never infers missing edges or supplies biological negatives. Model degree
means observed degree within the fixed measured-gene frame, not complete
pathway size. Gene and model namespaces are distinct; source revisions remain
distinct; duplicate incidences are rejected. Isolated queries stay present.

Original native GLS ranks, fractional ties, reference-availability masks, all
87 source arms and all N=1…10 points are preserved. The query-matched expected
weighted score is reported beside observed score, their means and enrichment.
Zero expected score remains undefined; an incomplete fixed query frame is
UNKNOWN. Twenty count/degree draws per type give descriptive ranges, not
confidence intervals or evidence of a uniform null.

The saved readout shows a favorable exploratory full-curve concordance result,
with the denominator tradeoff made explicit. It supports investigating an
interpretation/ranking feature; it does not prove independent whole-graph
accuracy or justify automatic biological pruning. Full results and limitations:
`docs/evaluations/RESOURCE_ALLOCATION_CONTEXT_20261113.md`.

No additional source retrieval, paid compute, model or GPU is required.
