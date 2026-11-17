# Run, explore and reuse BioGraph Steward

## Open the public demonstration

[Open the recorded KRAS example](https://bi-3a117d5e2b3942678dc518fce65ab5d2.ecs.us-east-2.on.aws/?run=native_evidence_workspace_20261115&question=native_physical_KRAS_question_v3_20261115&agent_job=source_agent_eval_dc7b597201da_S01&view=data)
in a browser. No sign-in, AWS account, installation, GPU or running model is
needed. [How to use BioGraph Steward](../HOW_TO_USE.md) follows the visible
controls step by step.

A scientist can follow a question to a focused graph, read a cited answer,
inspect its sources and examine proposed decisions without writing graph-query
syntax. The recorded Nemotron workflow has four steps: **Question & plan**,
**Evidence graph**, **Source inspection** and **Review proposals**.

| Activity | What to open |
|---|---|
| See added source context | In the KRAS run, inspect **E002, KRAS–CDC42BPB**. Its source passport shows a pair absent from the captured Pharos graph, STRING 12.5 score 203 and preserved identity checks. |
| Inspect applied qualification | Open the matched **TP53** example, then **What changed**. It explains the 298 record exclusions and links them to the retained graph. |
| Understand the measured results | Read the comparison tables under **Graph changes and assessment**. Source recovery and the separate historical prediction study retain their own controls. |
| Reuse a recorded result | Download the verified agent record. It contains the question, focused graph, model/tool trace, inspections and proposals. Complete source packets are separate. |

The public site replays completed real agent work over two designated saved
workspaces and five recorded-agent examples. New construction, retrieval, model
calls and review edits are disabled. Read-only graph exploration and source
inspection remain available. Proposals accept no assertion and change no graph.

## Run new questions or construct a graph

Use a local or authorized operator installation for new work:

- **Construct a Pharos graph:** follow [cohort construction](CONSTRUCTION.md#build-through-the-app).
  Supply an explicit list of 1–25 proteins. This retrieves bounded Pharos data
  and builds a graph with a cited answer. Internet access is required. A model
  or GPU is not required.
- **Ask a new agent question:** follow [source-agent execution](SOURCE_AGENT.md#operator-cli).
  Supply a complete source workspace and configure a live model endpoint. The
  agent uses only source tools actually attached to that workspace. Supported
  tools cover native physical associations, native locations and exact archived
  pathway context.
- **Open saved work locally:** use [local setup](../START_HERE.md#local-setup).
  Keep the workspace and saved-question folders beside one another, with their
  original names and complete source files. A graph JSON alone is not a complete
  replay packet.

For a complete real-data launch, use the separately supplied
`BioGraph_Steward_APP_PSEN_Example.zip`. Its **OPEN_EXAMPLE.txt** selects the
actual recorded APP location-agent job. The runtime, complete sources and
saved result work offline. This local three-protein example is separate from
the public site's two 99-target workspaces. The [worked example](evaluations/GENERALIZATION_EXAMPLE_20261117.md)
also runs the unchanged localization comparisons with all controls and coverage
denominators preserved.

The Python core needs **Python 3.10+**. Saved replay needs no pip install, GPU or
API key. A fresh checkout includes an explicitly invented software example.
The real-data demonstration uses separately preserved source packets under
their source terms. The [small CC0 Reactome example](../examples/reactome_context_20261113/README.md)
provides an included real-source inspection example.

## Project files

| File | Purpose |
|---|---|
| [Project report PDF](../output/pdf/BioGraph_Steward_Final_Report.pdf) · [Word copy](../output/docx/BioGraph_Steward_Final_Report.docx) | Scientific purpose, approach, architecture, results, scope and reusable deliverables. |
| [Narrated walkthrough](../output/walkthrough/BioGraph_Steward_Walkthrough.mp4) | A 3:58 explanation of source additions, the agent workflow, measured outcomes and recoverable decisions. |
| [Transcript](../output/walkthrough/BioGraph_Steward_Walkthrough.txt) and [captions](../output/walkthrough/BioGraph_Steward_Walkthrough.vtt) | The same explanation in readable and timed text. |
| [Slides](../output/presentations/BioGraph_Steward_Overview.pptx) | A concise illustrated overview of the question-to-evidence workflow. |
| [Software ZIP](../output/software/BioGraph_Steward_Software.zip) | Portable Python core, launch instructions and upstream notices. No source snapshots, credentials, reference labels or model weights. |
| [Graph and source packages](GOLD_SET_INTERFACE.md#protected-downloads) | Complete graph, decisions, preserved input and exact Pharos-only comparator. Separate authorized assets under source terms. |
| `BioGraph_Steward_APP_PSEN_Example.zip` | Self-contained local APP/PSEN example, with code, real source data and the recorded APP location-agent job. See its **OPEN_EXAMPLE.txt**. |
| `BioGraph_Steward_Source_Verifier_Code.zip` | Code-only research adjunct. **README_REPRODUCTION.txt** specifies its matching checkout, optional runtime and separately licensed pinned inputs. It contains no reference cases or model outputs. |

The video uses actual local-app screenshot states on verified saved real data,
readable crops and synthetic narration. Its prediction scene renders unchanged
scientific-report tables. Capture runs no new inference or source retrieval.
[Delivery status](DELIVERY_STATUS_20261115.json) and the
[release index](releases/20261115/README.md) identify exact artifact checksums.

## Graphs and scientific scope

| Saved workspace | Scope and use |
|---|---|
| Native candidate-evidence view | **99 primary targets, 9,724 entities and 19,310 evidence records**. It preserves 15,671 captured Pharos records and adds 3,309 native GO annotation rows and 330 STRING physical associations. Use the KRAS question and location-source comparison. |
| Retained graph after qualification | **99 primary targets, 9,865 entities and 16,687 retained records**. Its 16,985-record input, 298 records with obsolete GO identifiers, and every keep, remove or unresolved decision remain preserved. Use the TP53 pathway example. |

The native source profile was assembled November 15 from an October 14
**Pharos319** capture. The GO annotation file was generated July 28 and uses the
July 26 ontology. STRING is **12.5**. [Source dates](SOURCE_NOTES.md#current-reviewer-graph-and-source-dates)
distinguish source releases from assembly dates. Updating the application does
not refresh those datasets.

The workspaces have different source collections. Their total counts are not
a paired before/after experiment. The private Neptune mirror holds the retained
companion graph. Ordinary saved answers use their own preserved workspace files.
The separate APP/PSEN packet uses a new November 17 UTC capture reporting
Pharos319. Its three primary proteins, 466 entities and 696 records are not
added to the public site's graph or treated as another version of the 99-target
cohort. All source additions remain candidates.

Native physical integration supplies **87 pairs absent from the captured graph**
and 243 overlapping pairs. Native location integration supplies **68 additional
protein–location concepts** and 361 overlapping concepts. Additional rows are
candidate source context, not independent experiments or new biological discoveries.
Physical association can describe a shared complex without direct binding.

Using the same ontology-qualified mapping, native annotations recover **44/51**
HOU location labels against captured Pharos's **41/51** among 31 matching proteins.
The already-used OpenCell reference changes **30/40 to 31/40** among 23 proteins,
including after the specified source exclusions. The coarse-map HOU control
also reaches 44/51 with more truth-unknown outputs. Shared sources and prior
reference exposure limit independence. The [full location comparison](evaluations/PUBLIC_GOLD_REFERENCE_RESULTS_20261115.md)
retains the complete controls and coverage denominators.

The [separate ProtBoost-based function study](evaluations/CONTEXTUAL_COMBINATION_RESULTS_20261115.md)
uses a historical 20,412-protein graph. It improves the retained Pharos-derived
predictor in both primary reference views for additional biological-process
annotations in proteins already annotated in that aspect (partial knowledge).
Refreshing annotations also helps,
and added primary benefit over that stronger baseline remains uncertain.
Same-learner graph-prediction and literature-audit comparisons did not show
consistent superiority over their strongest controls. These source, prediction
and workflow endpoints are not pooled into a whole-graph accuracy percentage.
The [forecast coverage note](evaluations/final_delivery_20261117/prediction_coverage_feasibility.md)
explains that all 3,300 eligible temporal-gainer proteins were forecast: 3,297
in the graph and three retained outside it. Further temporal testing requires later labels.

The separate [source-verifier comparison](evaluations/SOURCE_VERIFIER_COMPARISON_20261117.md)
retains adverse supported-claim exclusions and the partial Evidence-input
qualification. Corrected-input diagnostics are distinct from those preserved
results. No current app assertion has the complete native INDRA inputs needed
for this verifier, and it has not been adopted for automatic Pharos pruning.

## What each graph package preserves

- **Answer ZIP:** focused answer, selected paths and cited evidence.
- **Run ZIP:** complete saved workspace and attached source files. Saved
  questions have separate ZIPs and open beside their workspace.
- **Graph and decision handoff:** `retained_graph.json`, every decision in
  `edge_dispositions.jsonl`, and the preserved input in
  `baseline_packet/source/graph.json`. Unresolved records stay retained. That
  input may already contain source extensions, so its “baseline” label does
  not always mean Pharos-only.

The designated primary handoff records all **19,310** native-view records as
unresolved and includes an exact same-snapshot **Pharos-only comparator**.
The retained TP53 package separately records the applied obsolete-ID exclusions.
The [protected-download receipt](evaluations/final_prod_ui_20261116/protected_graph_downloads.json)
records complete archive/member verification. These bulk graph, source and
recovery archives are not anonymous public-demo downloads.

## Reproducibility and source terms

The agent's [fixed comparison](evaluations/SOURCE_AGENT_RESULTS_20261116.md)
preserves complete deterministic query results, answers and focused graphs
across five supported queries. The [software check](evaluations/democratization_delivery_20261116/software_acceptance.json)
records clean Python execution, exports, recovery and saved replay. The
[public server](evaluations/public_demo_20261117/hosted_acceptance.json),
[browser workflow](evaluations/public_demo_20261117/hosted_browser_acceptance.json)
and [source-preservation check](evaluations/public_demo_20261117/final_operations.json)
record deployment operation separately from scientific validation.
[KGX/SSSOM export](STANDARD_EXPORT.md) describes supported profiles and their limits.

The software is MIT licensed. Each source dataset and reused tool keeps its
own terms and attribution. Mixed-source graph verification does not grant a
blanket redistribution license. The saved graph includes **1,588 KEGG pathway
membership records**. [KEGG's terms](https://www.kegg.jp/kegg/legal.html) require
separate attention to applicable use and hosting permissions. Complete source
packets remain authorized assets rather than a blanket public data release.

Project repository: [github.com/mdomagalski/biograph-steward](https://github.com/mdomagalski/biograph-steward).
The [research appendix](RESEARCH_APPENDIX_20261115.md) and
[experiment history](EXPERIMENT_HISTORY.md) preserve full methods, stronger
controls and unsuccessful comparisons.

<details>
<summary>Earlier verified checkpoints and recovery records</summary>

## Earlier verified checkpoints

The following dated records describe earlier runtimes and packages. Their exact
checksums, source scopes and recovery boundaries remain preserved. They do not
substitute for the current acceptance receipt.

The [November 13 delivery index](releases/20261113/README.md) joins the designated
runtime, graph and answer archives, exact checksums and access/source
boundaries. Its [manifest](releases/20261113/manifest.json) separates the updated
hosted runtime `5362b50` from the preserved `902699e` software/private archives and lists relative local
artifact paths. Preparing the index publishes no assets and changes no graph.

The checkout also includes the small [CC0 Reactome annex](../examples/reactome_context_20261113/README.md)
for offline real-source inspection. The optional
[expert-grounding evaluation](evaluations/EXPERT_GROUNDING_20261113.md) has a
[sanitized result](evaluations/expert_grounding_20261113_aggregate.json) and
[reproduction tools](../tools/grounding_claims/README.md). These later additions
do not replace the pinned runtime inside the already prepared archives below.

The scientific demonstration at that November 13 checkpoint is the
[source-faithful workspace](evaluations/SOURCE_FAITHFUL_WORKSPACE_20261113.md),
`source_faithful_workspace_20261113`: **99 primary Pharos targets, 9,865 entities
and 16,687 retained evidence records**. Its complete ZIP preserves the original
16,985-record baseline, explicit keep/prune/abstain ledger and native historical
source proof. Saved questions have separate ZIP downloads. It is live in the
sign-in-protected AWS workbench and private Neptune. The [dated assessment](evaluations/SCIENTIFIC_DELIVERY_20261113.md)
reports source-support coverage and the negative controlled biological results.

The earlier [GO rollout receipt](evaluations/hosted_native_go_20261113_summary.json)
records code `ea5752e` with the approved separate 12-file native GO/QC packet.
The November 13 `5362b50` checkpoint added its separately verified download; the original files remain unchanged.
The [earlier hosted update](evaluations/hosted_polish_update_20261113_summary.json)
installed the 16-file aggregate publication
`scientific_assessment_delivery_20261113` (`09e50f8e…`), retained as a dated publication. The existing
TP53 answer and all 13 question/export files are unchanged after a real service
restart; native replay, publication APIs and complete Neptune parity/read checks
passed. The former runtime is retained for rollback. That source-attachment
update added no public access, permissions or compute resources; the later
approved reviewer gateway is described above. Deployment does not establish
biological accuracy or extend the earlier backup-recovery claim.

That earlier v3 publication shows grounding plus the 92-query/3,968-pair
exploratory comparison. The [negative 128-gene/7,648-pair transfer](evaluations/PROSPECTIVE_GENE_TRANSFER_20261113.md)
remains separately reported. The [native GO inspector](NATIVE_GO_CONTEXT_WORKBENCH.md)
exposed preserved qualifiers, references and recorded QC beside a selected
claim in the hosted app. Current native context remains separate from the
historical Pharos record; it supplies no new biological truth or pruning label.
The [November 14 hosted assessment](evaluations/scientific_hosted_delivery_20261114_summary.json)
is `scientific_assessment_reference_20261114` (v4), including the saved historical
function inspector and BioRED aggregates. Its authenticated browser check,
source-preserving backup and isolated recovery are recorded separately.
The newer [context-aware prediction assessment](evaluations/CONTEXTUAL_COMBINATION_RESULTS_20261115.md)
is a separate aggregate-only repository/presentation deliverable. Its
[standalone HTML report](evaluations/contextual_combination_20261115/report.html)
does not require raw references, a model or the private demonstration packet.
It did not replace the hosted publication or change the source graph at that
checkpoint. The later aggregate assessment is identified above.

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
verification, separate from the
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


## Earlier offline handoff (November 15 checkpoint)

At this earlier checkpoint, the code-only download was
`runs/software_delivery_cached_review_20261115/biograph_steward_core_saved_review_software.zip`
at commit `47a2e5a`, verified by the
[clean extracted check](evaluations/software_release_cached_review_20261115_summary.json).
The [release index](releases/20261115/README.md) records its checksum and exact
core-only scope. Optional research/deployment scripts remain in the full
repository. The hosted app then had its separately accepted `47a2e5a` checkpoint; real source
packets, native GO/QC attachments and aggregate publications remain separately
supplied data.
The earlier `9bf202f` code-only ZIP remains an asset in the existing private
[draft review release](https://github.com/mdomagalski/biograph-steward/releases/tag/untagged-28e4edec341d2cb39dab),
with the completed aggregate study and slides. Repository writers can review
those draft assets. That handoff used the tracked `codex/contextual-gain-delivery`
review branch while the default main retained an older checkpoint. Neither
main nor repository visibility changed at that point. These preserved packages
do not replace the current software ZIP described above.
The GO attachment is absent from this ZIP and fresh installations leave its
inspector and native packet download disabled until the source paths are configured.
The earlier `5362b50` software ZIP and its
[acceptance receipt](evaluations/software_release_native_go_export_20261113_summary.json)
remain preserved in the [November 13 index](releases/20261113/README.md).
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

The [source repository](https://github.com/mdomagalski/biograph-steward) supplies
the software. Dataset permissions and organizer submission are separate from
these historical package-verification records.

</details>
