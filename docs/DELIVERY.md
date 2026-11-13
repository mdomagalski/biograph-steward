# Delivery and reviewer access

## Shared reviewer site

[Open the saved TP53 example](https://bi-3a117d5e2b3942678dc518fce65ab5d2.ecs.us-east-2.on.aws/?run=source_faithful_workspace_20261113&question=question_20261113T075313Z_1a76b00f&view=ask).
Use the existing workspace token, supplied separately and privately. Reviewers
need a browser; AWS credentials, Brev and local setup are unnecessary. The
[testing guide](TEAM_REVIEW_GUIDE_20261113.md) gives the weekend tasks.

This authenticated route supports saved questions, source inspection, the native
GO inspector and downloads. Construction, fresh retrieval, model calls and review
edits are blocked. The shared token admits the valid saved workspaces; it does
not create individual reviewer roles. Neptune remains private. The
[delivery receipt](evaluations/reviewer_https_delivery_20261113_summary.json)
records HTTPS authentication/route checks, full exported GO replay, preserved
source bytes and a cold Neptune read through the gateway after restart.
The saved TP53 answer also opened in Chrome. Independent teammate feedback and
independent whole-graph biological accuracy remain outstanding.

The [November 13 delivery index](releases/20261113/README.md) joins the designated
runtime, current graph and answer archives, exact checksums and access/source
boundaries. Its [manifest](releases/20261113/manifest.json) separates the updated
hosted runtime `5362b50` from the preserved `902699e` software/private archives and lists relative local
artifact paths. Preparing the index publishes no assets and changes no graph.

The checkout also includes the small [CC0 Reactome annex](../examples/reactome_context_20261113/README.md)
for offline real-source inspection. The optional
[expert-grounding evaluation](evaluations/EXPERT_GROUNDING_20261113.md) has a
[sanitized result](evaluations/expert_grounding_20261113_aggregate.json) and
[reproduction tools](../tools/grounding_claims/README.md). These later additions
do not replace the pinned runtime inside the already prepared archives below.

The current scientific demonstration is the
[source-faithful workspace](evaluations/SOURCE_FAITHFUL_WORKSPACE_20261113.md),
`source_faithful_workspace_20261113`: **99 primary Pharos targets, 9,865 entities
and 16,687 retained evidence records**. Its complete ZIP preserves the original
16,985-record baseline, explicit keep/prune/abstain ledger and native historical
source proof. Saved questions have separate ZIP downloads. It is live in the
sign-in-protected AWS workbench and private Neptune. The [current assessment](evaluations/SCIENTIFIC_DELIVERY_20261113.md)
reports source-support coverage and the negative controlled biological results.

The earlier [GO rollout receipt](evaluations/hosted_native_go_20261113_summary.json)
records code `ea5752e` with the approved separate 12-file native GO/QC packet.
Current `5362b50` adds its separately verified download; the original files remain unchanged.
The [earlier hosted update](evaluations/hosted_polish_update_20261113_summary.json)
installed the 16-file aggregate publication
`scientific_assessment_delivery_20261113` (`09e50f8e…`), which remains in use. The existing
TP53 answer and all 13 question/export files are unchanged after a real service
restart; native replay, publication APIs and complete Neptune parity/read checks
passed. The former runtime is retained for rollback. That source-attachment
update added no public access, permissions or compute resources; the later
approved reviewer gateway is described above. Deployment does not establish
biological accuracy or extend the earlier backup-recovery claim.

The hosted v3 publication shows grounding plus the earlier 92-query/3,968-pair
exploratory comparison. The [negative 128-gene/7,648-pair transfer](evaluations/PROSPECTIVE_GENE_TRANSFER_20261113.md)
remains separately reported. The [native GO inspector](NATIVE_GO_CONTEXT_WORKBENCH.md)
now exposes preserved qualifiers, references and recorded QC beside a selected
claim in the hosted app. Current native context remains separate from the
historical Pharos record; it supplies no new biological truth or pruning label.

The November 12 `crc_biological_workspace_20261112` source and its portable
all-abstain CRC package remain supplementary, reproducible earlier artifacts.
They combine the saved Pharos/CIViC workspace with source-qualified STRING,
MAP-IT and SIGNOR records. The optional private BioPlex context workspace is
not part of this delivery. The [five-minute script](DEMO_SCRIPT.md) uses the
supported guided workflow, not the experimental model planner.

The [initial November 13 software-only archive check](evaluations/software_release_20261113_summary.json)
pins the preserved `902699e` runtime. The extracted
archive launches with clean Python 3.12 and no site packages, creates a synthetic
graph, answers a supported question and reopens the saved result after restart.
No retrieved data or credentials enter that archive. Its local file is
`runs/software_delivery_20261113/v2/biograph_steward_software.zip`; it has not been
published or sent to judges.

For the corrected graph, use its existing **Export → complete workspace ZIP**
and keep every saved source folder together. The all-abstain builder below
prepares the earlier unqualified example; it does **not** reconstruct the
corrected decisions or substitute for its source-faithful package. Both real
data packages remain private and subject to their source terms.

The [actual hosted handoff check](evaluations/hosted_workspace_export_20261113_summary.json)
downloaded the corrected graph's complete ZIP and its TP53 question ZIP through
the normal app routes. All 394 source files matched the existing workspace
byte-for-byte, and the extracted graph, Gold decisions, historical source proof
and adjacent saved question replayed successfully. This is portable app-export
verification, separate from the now completed
[isolated checkpoint recovery](evaluations/aws_isolated_recovery_20261113_summary.json).
That recovery replays the existing backup's source workspace, bound scientific
publication and saved question; it does not restore the latest software,
grounding assessment or full VM.

To reopen this corrected example locally, extract the **graph ZIP and question
ZIP beside one another** into a `runs/` directory. Keep both top-level folder
names intact, then run the software with `--runs-dir runs`. The graph ZIP alone
reopens the complete graph but does not silently contain other saved questions.
Use the question ID supplied with your packet in the URL. The checked local
files are under `runs/hosted_workspace_export_20261113/`; data access and source
terms still apply.

## Current offline handoff

For the latest code-only download, use
`runs/software_delivery_native_go_export_20261113/biograph_steward_software.zip`
at commit `5362b50`, verified by the
[clean extracted check](evaluations/software_release_native_go_export_20261113_summary.json).
The [release index](releases/20261113/README.md) separates its checksum and
assessment viewer from the earlier combined demonstration below. The current
hosted code matches this software checkpoint; its real source packets, native
GO/QC attachment and aggregate publication remain separately supplied data.
The GO attachment is absent from this ZIP and fresh installations leave its
inspector and native packet download disabled until the source paths are configured.
The [closing fixes](DELIVERY_POLISH_20261113.md) preserve saved source bytes
while reducing HTTP transfer size and removing scratch files from path verification.

The preserved private combined bundle is
`runs/source_faithful_delivery_20261113/biograph_steward_source_faithful_private.zip`.
It contains the separately pinned `902699e` runtime, corrected graph with its full baseline
and decisions, historical proof and saved TP53 answer in one layout. Unzip into
a new directory and follow its `README_DEMO.md`:

```sh
python3 app.py serve --runs-dir runs --host 127.0.0.1 --port 8765 --no-browser
```

Open `http://127.0.0.1:8765/?run=source_faithful_workspace_20261113&question=question_20261113T070731Z_1079c2ac`.
Python 3.12 was checked without site packages. No model, GPU, AWS login or new
source retrieval is needed. The [acceptance summary](evaluations/source_faithful_offline_delivery_20261113_summary.json)
records stream verification of every archive entry and actual app checks from
the byte-identical assembly. A further full physical extraction was omitted to
preserve local disk headroom. This data-bearing bundle remains private and is
not cleared for redistribution. The separate software-only archive contains no
retrieved source data.

## Preserved November 12 package builder

`scripts/prepare_judge_demo.py` reuses the existing committed-runtime release
builder and verified graph/decision interface. It retrieves no data, runs no
model and creates no cloud resources. Its output contains:

| Package | Contents and purpose |
| --- | --- |
| `biograph_steward_software.zip` | Core MIT runtime, launch instructions and an offline synthetic example recipe. No retrieved source data, credentials or Git history. The full repository also supplies tests, optional evaluation tools and documentation. |
| `biograph_steward_crc_local.zip` | The same runtime plus the complete saved CRC workspace, cited BRAF answer, site/context answer and full graph/decision handoff. Prepared and verified locally; redistribution is **not cleared**. |
| `delivery.json` | Code revision, source packet identity, graph counts, saved-answer hashes and archive byte inventories/checksums. It records source preservation, not scientific validation or data permission. |

The data package preserves these relationships:

- `runs/crc_judge_demo/` is the complete source workspace the app opens.
- `runs/question_judge_focus/` is a saved candidate answer about BRAF. Its diagram
  is a question-specific selection, not the whole graph.
- `handoff/retained_graph.json` retains the entire graph. Every original edge has
  an **abstain** disposition; none is silently accepted or pruned.
- `handoff/edge_dispositions.jsonl` accounts for every original evidence record.
- `handoff/baseline_packet/source/graph.json` is the original source graph;
  surrounding source files preserve replay and provenance.

The retained graph carries retention metadata. Its nodes, edges and assertions
match the reopened workspace; its entire JSON need not be byte-identical to the
original graph. The original source files remain byte-preserved.

## Build from an authorized saved workspace

Commit the intended runtime first: the software archive is built from Git,
not uncommitted working files. Use new output directories:

```sh
python3 app.py gold-export --run runs/crc_biological_workspace_20261112 \
  --out runs/my_crc_source_packet
python3 scripts/prepare_judge_demo.py --packet runs/my_crc_source_packet \
  --focus UniProtKB:P15056 --site Ser614 --ref HEAD \
  --out runs/my_crc_delivery
```

Preparation verifies the packet, writes all-abstain decisions, reopens the
complete source workspace, extracts each ZIP and checks its file inventory.
The final release check must also launch the extracted committed app and replay
its answer/site API. Synthetic builder tests do not establish compatibility
with an arbitrary older `--ref`.

The [November 12 v3 delivery check](evaluations/DELIVERY_READINESS_20261112.md)
completed this actual extracted-app replay for the full CRC graph and separate
software archive. Its aggregate summary binds the code revision and archive
checksums; locally generated archives are not stored in Git.

Unzip an authorized real package, open a terminal in that directory and run:

```sh
python3 app.py serve --runs-dir runs --host 127.0.0.1 --port 8765 --no-browser
```

Open `http://127.0.0.1:8765/?run=crc_judge_demo&question=question_judge_focus`.
The software-only package instead starts with:

```sh
python3 app.py demo --out runs/synthetic_demo
python3 app.py serve --runs-dir runs --host 127.0.0.1 --port 8765 --no-browser
```

Open `http://127.0.0.1:8765/?run=synthetic_demo`. Python 3.10+ is sufficient;
the core flow needs no package installation, model, GPU, account or cloud.
Keep the terminal running; Ctrl+C stops the local server.

## Real source availability and permissions

The full CRC graph contains **1,588 KEGG pathway membership records**. Pharos
provider metadata does not supply a blanket data redistribution license.
[KEGG's published terms](https://www.kegg.jp/kegg/legal.html) distinguish academic
use, service provision and non-academic licensing. Consequently, local package
verification does not authorize a public upload or controlled judge transfer.
Software MIT licensing does not relicense upstream data. Preserve the native
terms and attribution and resolve any applicable permissions before sharing
the real packet or hosting those data for others.

The independently usable route is the software-only archive/repository and
bounded retrieval by the user. In **Data & saved work → Pharos disease cohort**,
search `colorectal`, choose the exact returned disease and retrieve a bounded
cohort. Inspect coverage and upstream terms. This produces a new snapshot; it
does not reproduce the frozen graph byte-for-byte or automatically include
the separately qualified extension sources. See [scoped retrieval](SCOPED_RETRIEVAL.md)
and [source enrichment](BIOLOGICAL_SOURCE_UPDATE.md).

The [source repository](https://github.com/mdomagalski/biograph-steward) is private
during preparation and is intended to become public at final submission
(planned for November 17, 2026). Repository visibility, source permission and
the actual organizer handoff remain separate delivery actions. Do not claim an
official score while the organizer's final scoring contract is unavailable.
