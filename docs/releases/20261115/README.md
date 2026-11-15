# November 14 core software checkpoint

The folder identifier uses November 15 UTC. This is a locally tested standalone core subset at commit `9bf202f84949c76904ba8e51a5f83b68f2d58843`, separate from the last verified AWS runtime and ongoing research comparisons.

[Download the prepared core ZIP](../../../runs/software_delivery_core_20261115/biograph_steward_core_software.zip). It is 661,594 bytes with 124 files; SHA-256:

```text
aa00f7fc2c8cebc24e63ab0b0f0659bba8de74793a0a37055c0a4d818be12c94
```

The archive contains `app.py`, `biograph_steward/`, the project license, retained upstream vendor notices and a standalone `README_DEMO.md`. It contains no real source datasets, credentials, benchmark labels, model weights or Git history. Optional research and deployment scripts remain in the full repository; they are omitted from this core subset. The unchanged allowlisted source-release builder's full runtime tar remains [separately preserved](../../../runs/software_delivery_core_20261115/runtime_release/release.json).

Unzip into a new folder and follow `README_DEMO.md`. Python 3.10+ runs the core app without pip, GPU, cloud or model access. The offline example is explicitly invented. Real workspaces and native GO/QC sources require separately supplied authorized data.

The [acceptance receipt](../../evaluations/software_release_core_20261115_summary.json) records clean Python 3.12.14 execution without site packages: invented graph construction, a cited answer, actual complete graph/decision and answer ZIP downloads, exhaustive decision verification, fresh extraction of the exported baseline, and identical saved-answer replay after restarting the isolated server. No source retrieval, inference or cloud calls were made. This checks portability and preservation, not browser usability or scientific correctness.

The ZIP is prepared locally and has not been uploaded or published. Repository-only access does not automatically supply files under the ignored `runs/` folder; attach the ZIP as a release artifact when the final handoff is designated. Earlier release indexes and their checksums remain preserved dated checkpoints. See the [submission overview](../../SUBMISSION_OVERVIEW.md) and [delivery status](../../DELIVERY_STATUS_20261115.json) for the product and release boundaries.
