# November 13 delivery index

This index designates the corrected **99-target** demonstration and its existing
delivery artifacts. It joins the code, graph, answer, checksums and availability
records; it does not publish an asset, grant source-data rights or change a
scientific result. The [machine-readable manifest](manifest.json) uses paths
relative to the repository root. Local paths are not download URLs.

## Which revision is delivered

The current **code-only software** now uses commit `ea5752e`. Its separately
tested ZIP is `runs/software_delivery_native_go_20261113/biograph_steward_software.zip`
(900,492 bytes); see the [clean extracted acceptance receipt](../../evaluations/software_release_native_go_20261113_summary.json)
and [current software checksum](CURRENT_SOFTWARE.sha256). It passes synthetic
question/export/reopen checks after an actual process restart with clean Python.
It includes the aggregate grounding viewer and optional native GO source/QC
inspector. GO packets are separate and the inspector is disabled by default;
see its [source and configuration guide](../../NATIVE_GO_CONTEXT_WORKBENCH.md).

The earlier `95d9420` and `0529d2b` software ZIPs and their receipts remain
preserved. Their checksums are recorded in `preserved_checkout_software`;
`CURRENT_SOFTWARE.sha256` identifies the new `ea5752e` ZIP.

The dated presentation packet is the
[three-page final review](../../../output/pdf/BioGraph_Steward_Final_Review_20261113.pdf)
(153,681 bytes), prepared for code `0529d2b`. Its
[review receipt](../../evaluations/final_review_PDF_20261113_summary.json) and the
manifest's `current_review` entry record its exact identity and scope. It remains
a local/repository review artifact; it has not been submitted or published.
It predates the hosted update below and still records the previous hosted
runtime. It is preserved unchanged; the hosted receipt gives the current status.
The original two-page scientific update remains in the preserved assets below.

The private hosted app now runs **`ea5752e`**, verified by its
[GO rollout and acceptance receipt](../../evaluations/hosted_native_go_20261113_summary.json).
The existing TP53 question and all 13 native question/export files remain
unchanged after a real restart, and complete Neptune parity/read checks passed.
The exact 16-file aggregate publication `scientific_assessment_delivery_20261113`
(`09e50f8e…`) is installed and API/catalogue-verified. Its grounding component
and earlier 92-query/3,968-pair exploratory comparison remain separate from
the [negative 128-gene/7,648-pair transfer](../../evaluations/PROSPECTIVE_GENE_TRANSFER_20261113.md).
Its native GO inspector is enabled with an approved separate 12-file source/QC
attachment. Both selected NRAS examples verified through the live API before
and after restart. Current native qualifiers and warnings remain separate from
historical Pharos records; no graph assertions or decisions changed. The
code-only ZIP above includes the inspector, with no source packet and disabled
configuration by default.

The complete private combined demo and original software archive below remain
pinned to **`902699e`**. They were not silently replaced. The previous live
runtime/image (`0529d2b`) is also preserved for rollback. The manifest's top-level
`runtime_commit` describes those original bundles; `current_hosted_runtime`
describes the updated service. The new deployment does not extend the earlier
backup-recovery scope.
Use `CURRENT_SOFTWARE.sha256` for the new code ZIP and the original
`CHECKSUMS.sha256` for the preserved artifacts in the table below.

| Item | Pinned revision or identity |
|---|---|
| Current private hosted runtime | `ea5752e56bad38a7828fcbb3df09303c778470d5` (`0.8.0`; native GO/QC configured separately) |
| Preserved original software/private demo archives and original hosted runtime | `902699ee41861be45529b38adeb2b289cf8300b0` (`0.8.0`) |
| Current code-only software ZIP | `ea5752e56bad38a7828fcbb3df09303c778470d5` (`0.8.0`; GO source packets separate) |
| Dated final-review PDF code checkpoint | `0529d2bc46eb07fcec00acdfe5432c9e5c23147e` |
| Documentation checkpoint before this index was assembled | `47eb36c25bec3858d29766ba9cfb123475bea825` |
| Corrected workspace graph | `e0e664a9a386fd321c2c65ed9fbb6aa61c165536e106b7c61fc75e37c0de69ff` |
| Preserved original baseline graph | `f35f8e0bb66742a3b65d1887ecbc85ead33fd8c5ef9eb5e8015d28934f22d22e` |
| Source capture | Pharos319, October 14, 2026; current publisher lookups have separate versions |
| Offline saved question | `question_20261113T070731Z_1079c2ac` |
| Saved native answer | `5b702dcff2fbc64040414a45ef3d0d99125bae13253dc81c2d3971c745f5766d` |

Later documentation commits do not silently replace the runtime inside an
already prepared archive. The hosted saved question has a different ID but
reproduces the same native-answer hash; the manifest records both IDs.
The graph hashes identify canonical graph content. They are distinct from
the ZIP-file checksums and the byte hash of a materialized retained-graph file
with its own retention metadata.

## Prepared artifacts and access

| Artifact | Bytes | Current availability and purpose |
|---|---:|---|
| `biograph_steward_software.zip` | 885,694 | Prepared and tested locally. MIT runtime with an explicitly synthetic example recipe; no retrieved source data, credentials or Git history. Not yet published as a downloadable release asset. |
| `source_faithful_workspace_20261113.zip` | 198,667,792 | Private complete graph/source/baseline/decision/history export. Source redistribution remains uncleared. |
| `question_20261113T070731Z_1079c2ac.zip` | 2,090,144 | Private saved TP53 answer and native exports. Full replay requires its adjacent complete workspace; original source/model terms remain applicable. |
| `biograph_steward_source_faithful_private.zip` | 201,648,128 | Private one-directory runtime, corrected graph and TP53 answer. It has not been sent to judges or cleared for redistribution. |
| `BioGraph_Steward_Scientific_Update_20261113.pdf` | 149,247 | [Tracked two-page project update](../../../output/pdf/BioGraph_Steward_Scientific_Update_20261113.pdf), with an actual app capture and scientific boundaries. It is separate from the software/data archives. |
| `reactome_context_20261113.zip` | 22,550 | [Standalone real-data annex](../../../examples/reactome_context_20261113/reactome_context_20261113.zip): seven exact native Reactome JSON responses and release-98 text under CC0; a separate MIT static viewer. Prepared locally for the repository, not separately published or sent to judges. |

The original five files were streamed once again when this index was first
prepared; their SHA256 and byte counts agree with the recorded artifacts. The
separate Reactome annex was then assembled from exact allowlisted existing
source bytes and its ZIP members checked individually. The original five
artifacts were not repackaged or changed. See
[CHECKSUMS.sha256](CHECKSUMS.sha256) and the per-artifact receipts linked in the
manifest. Checksum entries use basenames so that permitted received files can
be verified in a common delivery directory. For a single received asset, run:

```sh
shasum -a 256 biograph_steward_software.zip
```

Compare its output with the matching checksum line. A fresh checkout does not
contain the four original local software/mixed-source ZIPs. Do not interpret missing private assets as an
instruction to download another snapshot or substitute a different graph.

## Reviewer routes

**Software-only route:** receive the software archive, unzip it into a new
directory and follow `README_DEMO.md`. It creates the labeled synthetic example
and starts with ordinary Python; no account, model, GPU or cloud is needed.
The [start guide](../../../START_HERE.md) provides the equivalent checkout route.

**Real publisher-context route:** open the [Reactome annex](../../../examples/reactome_context_20261113/index.html)
or receive its [standalone ZIP](../../../examples/reactome_context_20261113/reactome_context_20261113.zip).
Its static page works offline and shows exact native reaction, catalyst,
participant, compartment and ancestor fields with links to the bundled JSON.
No app server, model, account or cloud is needed. The
[annex README](../../../examples/reactome_context_20261113/README.md) and
[manifest](../../../examples/reactome_context_20261113/manifest.json) identify
all eight data responses, capture times, byte hashes and original capture seal.
Reactome's [data policy](https://reactome.org/license) places these native data
and derived data files under CC0; the authored viewer has a separate MIT notice.
It includes no cached publisher HTML, article text/images or full source packet.
This is a small current source-inspection example, not the full Pharos graph,
a replay of its baseline/decisions, an independent biological reference or proof
of the historical Pharos319 Reactome contents. It does not resolve terms for
the complete mixed-source bundle.

**Authorized current-data route:** receive the private combined bundle only
after its applicable source-sharing route is resolved. Unzip into a new
directory and follow its `README_DEMO.md`:

```sh
python3.12 -S app.py serve --runs-dir runs --host 127.0.0.1 --port 8765 --no-browser
```

Open `http://127.0.0.1:8765/?run=source_faithful_workspace_20261113&question=question_20261113T070731Z_1079c2ac`.
Python 3.12 was checked without site packages. Keep the complete source folders
together; copying `graph.json` alone loses replay and provenance. The same
handoff can use the separate graph and question ZIPs extracted beside one
another under `runs/`, alongside the software runtime.

The current graph has 9,865 entities and 16,687 retained evidence records. Its
original 16,985 records and exhaustive keep/prune/abstain ledger remain in the
source-retained package. The 298 removals concern obsolete GO identifiers in
the pinned July 2026 ontology; they are not experimentally disproved relations.
The answer diagram is a selected view of this full workspace. The separate
128-gene research workspace is not included in these private exports. The
B3GALNT2 current Reactome example is supplied only in its separate annex above.

**New-source route:** a user can use the software's bounded Pharos retrieval
under applicable source terms. That creates a new dated snapshot; it does not
reproduce this frozen graph or its qualified extensions automatically. See the
[retrieval guide](../../SCOPED_RETRIEVAL.md).

## Verification and remaining delivery boundaries

- The software archive passed clean extracted startup, a supported synthetic
  question and a real local server restart.
- The normal graph and question ZIPs were physically extracted and replayed
  together; the final standalone runtime reproduced the real native answer.
- Every entry in the combined private ZIP passed stream SHA256/CRC checks. Its
  byte-identical assembly passed actual app/source/question/download checks.
  A further full physical combined extraction was omitted for disk headroom.
- The corrected hosted graph passed complete Neptune parity and a real app
  restart. Its graph answers ordinarily use saved files; database inspection
  uses actual read-only Neptune queries.
- The `0529d2b` hosted update reopened the same saved TP53 question after
  restart, with its source/export inventory unchanged. Both older and new
  aggregate publications verified through normal APIs. Authentication,
  permissions and resources were unchanged; the previous runtime was preserved
  for rollback. This is a code/publication deployment check, not a new backup
  recovery or scientific gain.
- The subsequent `ea5752e` rollout enabled the native GO source/QC inspector
  with 12 separately approved files. Both GO examples, unchanged saved answer,
  native exports and both publications passed API checks across a real restart;
  complete Neptune parity/read checks passed. Only the two GO source-path
  settings were appended; the access token and previous environment bytes were
  preserved. This adds inspectable source context, not new biological pruning.
- The completed private workspace backup passed an
  [isolated three-root checkpoint recovery](../../evaluations/aws_isolated_recovery_20261113_summary.json).
  V2 initially stopped at a missing writable temporary directory; its preserved
  failure was followed by the same native replay with a bounded ephemeral
  `/tmp`. The restored graph, bound publication and saved answer verified with
  the live files, configuration and container unchanged. This is the existing
  checkpoint, not full VM/runtime recovery or recovery of the newer software
  and grounding publication or the later native GO attachment. The separate 488 MB research-archive S3 copy
  remains unapproved and has not been uploaded.

MIT software does not relicense source records. The complete graph contains
1,588 KEGG pathway records, and provider/model terms remain applicable. A
bounded Reactome KGX projection also preserves its full source packet; it is
not automatically a rights-cleared public data bundle. See
[delivery and source permissions](../../DELIVERY.md#real-source-availability-and-permissions).

`scripts/prepare_judge_demo.py` prepares the preserved earlier **all-abstain**
example. It does not reconstruct the current corrected decisions. Use the
designated exports above for this demonstration; retain the older builder and
its results under their documented scope.

The repository remains private during preparation. Public visibility, permitted
complete mixed-source data availability, actual organizer handoff and the editable slide update
remain distinct release actions. The supplied brief permits semi-autonomous
software and imperfect explicit standards references; another paid service or
cloud migration is not required. See the [organizer crosswalk](../../PROJECT_ALIGNMENT.md).

The [scientific assessment](../../evaluations/SCIENTIFIC_DELIVERY_20261113.md)
reports bounded reference-support coverage and the negative controlled transfer.
Packaging, hashes and schema checks do not establish independent whole-graph
accuracy, transferable predictive gain or an official organizer score.
