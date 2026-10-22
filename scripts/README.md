# Current investigation scripts

This directory contains preparation tools for the active measured-link investigation. The workbench CLI is `python3 app.py --help`.

| Script | Purpose |
|---|---|
| [audit_inmc_inputs.py](audit_inmc_inputs.py) | Verify the pinned INMC archive, input schema and identifier coverage using the existing frozen HGNC/UniProt registry. Does not derive binary assay labels, select a final cohort or train a model. |
| [smoke_pykeen_reuse.py](smoke_pykeen_reuse.py) | Exercise upstream PyKEEN R-GCN and ComplEx on non-biomedical Nations data, evaluating validation only. Uses the isolated [pinned smoke environment](../requirements-graph-ml-smoke.txt). |

Read the [reuse decision](../docs/literature/MEASURED_LINK_BENCHMARK_REUSE_20261022.md) and [input-readiness report](../docs/evaluations/INMC_INPUT_READINESS_20261022.md) before running either tool. Use new output directories and preserve source receipts. A runtime smoke does not show biological improvement.

Completed growth, extraction, verifier and context-QA study tools have left the active branch. Their exact implementations, protocols and outcomes are preserved at the commit listed in [EXPERIMENT_HISTORY](../docs/EXPERIMENT_HISTORY.md). Reproduce them from that separate checkout with their original packets; do not weaken source-hash checks or reseal an old study to run it against current code.
