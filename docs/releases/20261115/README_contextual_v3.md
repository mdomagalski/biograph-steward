# November 15 private review candidate

Use the current files in the existing private
[draft review release](https://github.com/mdomagalski/biograph-steward/releases/tag/untagged-28e4edec341d2cb39dab):

| Current file | Purpose |
|---|---|
| `biograph_steward_core_software.zip` | Tested standalone MIT core; synthetic demonstration, no real datasets. |
| `biograph_steward_contextual_assessment_20261115_v3.zip` | Open `START_HERE.html` after extraction: the original fixed study, both separate development follow-ups and source/sequence/context qualifications. |
| `BioGraph_Steward_Challenge_Presentation_20261115_v5.pptx` | Nine editable slides: original eight preserved, plus the clearly labeled current-data development appendix. |
| `SHA256SUMS_CURRENT_20261115_v3.txt` | Checksums for those three current artifacts. |

All current remote sizes and SHA256 digests match the
[latest delivery receipt](github_review_delivery_v3.json). All ten remote
assets were retained and verified. The [v2 receipt](github_review_delivery_v2.json)
and [original receipt](github_review_delivery.json) preserve earlier checkpoints.

[Draft PR #1](https://github.com/mdomagalski/biograph-steward/pull/1) holds the
current work on **`codex/contextual-gain-delivery`**. Use that branch for the
current checkout; `main` is still the older October 26 checkpoint. Draft assets
require repository write access. Other repository readers can use the branch's
tracked reports, slides, testing guide and source. Main and private visibility
are unchanged. Final public release and submission remain separate actions.

The [current packet receipt](../../evaluations/contextual_assessment_review_v3_20261115_summary.json)
verifies all 68 archive members and every offline HTML link/anchor. The packet
is 711,421 bytes; SHA256
`1e8b9284f6d7ec32a1fd7cb5cf9cdf04e1de3cb032489f856f195d1fb583db07`.
It was built from committed aggregate source at `d143c4a`. Raw cases, draw
vectors, forecast matrices, weights, credentials and the mixed-source graph
are excluded. The tested software and protected graph are separate deliverables.

The [original fixed comparison](../../evaluations/CONTEXTUAL_COMBINATION_RESULTS_20261115.md)
supports bounded primary recovery gains over retained LocalPlus. Current
annotation refresh also helps; extra primary BP learning benefit remains
uncertain. Direct nonexperimental GOA is not clearly beaten for MF and is
better for CC. The [prior-preservation follow-up](../../evaluations/ANNOTATION_PRIOR_DEVELOPMENT_RESULTS_20261115.md)
is a trade-off. The [current-data refit](../../evaluations/CURRENT_REFIT_DEVELOPMENT_RESULTS_20261115.md)
did not establish an improvement over the original selected model. Both
follow-ups remain consumed-reference development and are not adopted.
[Chronology](../../evaluations/CONTEXTUAL_SOURCE_CHRONOLOGY_20261115.md),
[sequence similarity](../../evaluations/CONTEXTUAL_SEQUENCE_SIMILARITY_20261115.md)
and [opposite-polarity source context](../../evaluations/CURRENT_REFIT_SOURCE_QUALIFICATIONS_20261115.md)
qualify interpretation without creating biological prune labels.

The [corrected-link testing guide](../../../output/pdf/BioGraph_Steward_Team_Review_Guide_20261115.pdf)
preserves its dated November 13 testing content. Hosting stays separately
pinned to `a6a05ff`. Its HTTPS login remains reachable; no new authenticated
browser acceptance is claimed. Brev is stopped after verified research
backups. Keep the separate AWS reviewer service available for teammate feedback.

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

## Follow-up replay preservation

The consumed-reference development report/source receipts, all 36 new curves
and 36 contribution files, and the exact sequence-source/search replay are
held in separately verified private local archives (10.86 MB, 4.45 MB and
7.26 MB). They include case-level material and were not uploaded to GitHub.
The original 46 raw forecast arrays and six new development arrays remain on
the persistent Brev disk. All owned CPU jobs and transfers have finished;
stopping compute preserves a separate need to retain that disk. The model
server is unnecessary for saved-data review. Keep the AWS reviewer site
available for teammate feedback.


## Current-data refit recovery

The final refit model, exact three averaging states, executed source and
receipts are retained in a separately verified private 4,047,813-byte archive
(SHA256 `88664f548be3ef608be5bb4727eb379a50647071f7b4c3943a7b9a4c11bcd7ad`).
All 18 new native curves and 18 contribution files, the completed report and
operators are retained in a 21,167,911-byte archive
(SHA256 `d573306989b06d48ce03887ec93cf4d44277b01ff9d4c8e43e6298b240be14bd`).
The [safe execution](../../evaluations/current_refit_development_20261115/execution_qualification.json)
and [numerical replay](../../evaluations/current_refit_development_20261115/numerical_replay_receipt.json)
receipts report their verified scope. These private archives were not uploaded
to GitHub. Three new dense forecasts and their feature caches remain on the
persistent Brev disk; stopping compute does not replace disk preservation.
