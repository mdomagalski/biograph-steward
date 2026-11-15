# November 15 review candidate and core software checkpoint

The tested core ZIP, aggregate-only assessment ZIP, editable v3 presentation
and checksums are now uploaded to the existing private repository's
[draft review release](https://github.com/mdomagalski/biograph-steward/releases/tag/untagged-28e4edec341d2cb39dab).
[Draft PR #1](https://github.com/mdomagalski/biograph-steward/pull/1) preserves
the current work on `codex/contextual-gain-delivery`; main and public visibility
are unchanged. GitHub draft releases require repository write access; ordinary
repository readers can use the branch checkout and its tracked report/slides.
All four remote asset sizes and SHA256 digests match the
[delivery receipt](github_review_delivery.json). This is review preparation,
not final public publication or challenge submission.

The [latest completed scientific result](../../evaluations/CONTEXTUAL_COMBINATION_RESULTS_20261115.md)
and [editable v3 presentation](../../../output/presentations/BioGraph_Steward_Challenge_Presentation_20261115_v3.pptx)
are repository deliverables. The self-contained aggregate assessment ZIP is
`runs/contextual_gain_20261115/final_delivery_v1/biograph_steward_contextual_assessment_20261115.zip`
(573,822 bytes; SHA256 `db6f04932a3ebc3cfc492b875313cbf4518e0153cef5a5abab9b79f058e093d5`).
It contains 20 checked files: all results/controls, figures and aggregate
source/numerical audits, without raw reference cases, source archives or weights.
The [archive receipt](../../evaluations/contextual_assessment_archive_20261115_summary.json)
records its boundary. Hosting remains separately pinned to `a6a05ff`.

The later [source-chronology addendum](../../evaluations/CONTEXTUAL_SOURCE_CHRONOLOGY_20261115.md)
and reusable known-mask/archive readers are tracked on the review branch.
They verify source consistency and qualify novelty without changing the
immutable primary summary or its original report ZIP.

## Tested core software

The folder identifier uses November 15 UTC. This is a locally tested standalone core subset at commit `9bf202f84949c76904ba8e51a5f83b68f2d58843`, separate from the last verified AWS runtime and completed research comparisons.

[Download the prepared core ZIP](../../../runs/software_delivery_core_20261115/biograph_steward_core_software.zip). It is 661,594 bytes with 124 files; SHA-256:

```text
aa00f7fc2c8cebc24e63ab0b0f0659bba8de74793a0a37055c0a4d818be12c94
```

The archive contains `app.py`, `biograph_steward/`, the project license, retained upstream vendor notices and a standalone `README_DEMO.md`. It contains no real source datasets, credentials, benchmark labels, model weights or Git history. Optional research and deployment scripts remain in the full repository; they are omitted from this core subset. The unchanged allowlisted source-release builder's full runtime tar remains [separately preserved](../../../runs/software_delivery_core_20261115/runtime_release/release.json).

Unzip into a new folder and follow `README_DEMO.md`. Python 3.10+ runs the core app without pip, GPU, cloud or model access. The offline example is explicitly invented. Real workspaces and native GO/QC sources require separately supplied authorized data.

The [acceptance receipt](../../evaluations/software_release_core_20261115_summary.json) records clean Python 3.12.14 execution without site packages: invented graph construction, a cited answer, actual complete graph/decision and answer ZIP downloads, exhaustive decision verification, fresh extraction of the exported baseline, and identical saved-answer replay after restarting the isolated server. No source retrieval, inference or cloud calls were made. This checks portability and preservation, not browser usability or scientific correctness.

The unchanged ZIP is also an uploaded private draft-release asset. The local
link above requires the operator's ignored `runs/` folder; use the draft page
for the uploaded copy when you have the required repository write access.
Public release remains pending. Earlier indexes and checksums remain dated
checkpoints. See the [submission overview](../../SUBMISSION_OVERVIEW.md) and
[delivery status](../../DELIVERY_STATUS_20261115.json) for the product boundaries.

## Optional research recovery

The supporting contextual-combination study has two separate, operator-held
recovery archives. Neither is part of the core software ZIP or a published
release asset.

| Archive under `runs/contextual_gain_20261115/` | Contents | Bytes / SHA-256 |
|---|---|---|
| `learned_models_source_recovery_v1/learned_models_source_recovery_v1.tar.gz` | Seven final learned checkpoints, selected averaging states, actual executed source/license files and metadata. No datasets, reference tables or forecast matrices. | 16,455,644 / `c793ad7e88d7f2659930b505a775903e9a55bca3c260a55154636b9d69c67209` |
| `reference_inputs_recovery_v1/temporal_reference_inputs_20261115.tar.gz` | The six exact public GOA/GO/Swiss-Prot inputs, source manifest and notices. Includes source annotations; no derived ground-truth tables, predictions, model weights or credentials. | 220,892,955 / `4f197ba2556fbcbb174b335d790e5edd1353305272edac46f9f6d6b50a009a17` |

Both archives were copied locally and their contents hash-verified. They retain
the methods and source bytes independently of the Brev disk. The newest input
URLs point to mutable current releases; matching local source files work with
the [reference-input guard and recipe](../../../tools/contextual_combination/reference_recipe/README.md).
Preservation does not make a later URL immutable or a consumed benchmark fresh
again. Source data and optional research code retain their own terms. The
mixed-source Pharos demonstration graph is a different packet.

The [private numerical-replay receipt](../../evaluations/contextual_numerical_replay_20261115_summary.json)
also verifies a local 177,886,035-byte archive containing all 636 evaluation
files, complete source-support provenance, reference masks, executed source,
seals and 46 forecast-axis metadata files. Every one of its 1,024 members was
streamed and hash/size checked without local extraction. This archive includes
case/reference data and was **not uploaded to GitHub or cloud storage**.
The exact historical graph, 2023 seeds and model ontology were already present
locally and match their frozen input hashes. The 46 raw forecast arrays
(11.03 GB) remain on the persistent Brev research disk; stopping compute does
not replace a separate disk/data preservation decision. This is numerical and
source replay preservation, not a complete VM backup.
