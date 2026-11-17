# Midpoint demonstration and claim audit

October 27, 2026. This five-minute demonstration uses existing saved sources
and answers. It shows a working, traceable evidence workflow and a bounded
application of the completed biological assessment. It is not an independent
biological validation or a demonstration of autonomous scientific judgment.
No new study, source retrieval, model inference or paid compute is needed.

## Five-minute demonstration

The localhost server at port 8794 answered the checks below at
**18:29 UTC on October 27**. These links require that local server and are not
public team deployment URLs. Open the saved answers rather than rerunning the
physical-priority question, which would query STRING again.

| Time | Show | What this establishes |
| --- | --- | --- |
| 0:00–1:00 | Open the [saved BRAF question](http://127.0.0.1:8794/?run=crc_civic_final_20261015&question=question_20261027T180832Z_781f7543). Point to BRAF, reported interactions, candidate exploration and the optional physical-priority selector. | A scoped question produces an inspectable answer over a saved 99-target colorectal-cancer Pharos cohort. The default remains alphabetical; current STRING ranking is a separate supplement to the frozen Pharos319 graph. |
| 1:00–2:00 | Inspect ARAF's cited path, native physical score and local review state. Then inspect CAMK2B: it remains in the answer with a functional score but no physical overlay under the requested profile. | The answer retains all **21 matching proteins: 14 numerically scored and seven explicitly unranked**. Source scores affect order, not evidence content or acceptance. Missing physical scores are not negative biological labels. |
| 2:00–3:00 | Open the separate [qualified-source example](http://127.0.0.1:8794/?run=source_reuse_workbench_replay_20261027&question=assay_question_midpoint_reuse_20261027). Inspect TAS1R2/TAS1R3 and the source-reuse note. | The workbench preserves two qualified IntAct records and distinguishes source context from independent evidence. One exact IMEx record is shared with current STRING, based on the user-supplied source link; the second remains unresolved. This taste-receptor example is separate from the BRAF cancer question. |
| 3:00–4:00 | Download the BRAF question ZIP and identify `question.json`, `physical_priority.tsv` and `physical_ranking_source.json`. In the source example, download the whole workspace and identify its source-reuse report/proof. | The question package contains its full ranked population, native score states and replayable source packet. The whole-workspace ZIP preserves the broader workspace and source evidence. These are distinct export scopes. |
| 4:00–5:00 | Show the existing [graph-and-decision handoff](../../runs/submission_demo_v2_20261026/index.html) and name `retained_graph.json`, `edge_dispositions.jsonl`, and `baseline_packet/source/graph.json`. Close with the measured-assessment boundary below. | The resulting scoped graph, every explicit decision and original source graph can be handed off together. The demonstrated real ledger is all abstentions: undecided records remain retained. This establishes auditable packaging, not scientifically justified pruning. |

The graph drawing is a bounded question view, not the entire exported graph.
Use the app's existing “How the package relates to this workspace” explanation
if the distinction needs clarification. No new panel or navigation architecture
was added for this demonstration.

## Report-worthy conclusions and limits

| Supported wording | Avoid claiming |
| --- | --- |
| “The workbench connects scoped Pharos questions to evidence paths, cited answers, local review and reproducible exports.” | Full Pharos coverage, a complete organism-wide graph, or validated disease mechanisms. |
| “Task-specific native STRING physical scores now optionally prioritize existing interaction matches while preserving unscored evidence.” | Fourteen validated interactions, seven false interactions, independent evidence added to Pharos, or improved clinical accuracy. |
| “A fixed retrospective component comparison favored physical over functional ranking, and the selected older-source control agreed in direction.” | A Steward-versus-Pharos graph-learning gain, an unseen benchmark, a complete native-physical-network comparison for 12.5, or independent biological confirmation. Report numeric coverage with any AP figures. |
| “A consumed development replay preserved both eligible IntAct records from one study through source attachment, cited answers and exports.” | Two independent replications, 100% scientific accuracy, general extraction reliability, or successful scoring of the original reserved assessment. |
| “NVIDIA Nemotron/vLLM is integrated with scope checks and explicit plan review; deterministic execution is the working path.” | Reliable autonomous biological planning, verified NIM deployment, or a model-driven biological improvement. |
| “MIT-licensed code, source-bound exports and narrow standard profiles are implemented and tested.” | Upstream data relicensing, full Biolink/KGX/SSSOM interoperability, organizer acceptance of the export schema, or publication of uncommitted work. |
| “Assisted feedback improved source and export explanations.” | Independent intended-user validation or a newly completed visual browser walkthrough. |

The [previous consumed-flow report](midpoint_report_consumed_flow_20261027.json)
already describes core construction, IntAct/JAMI/PSI-MI integration, experimental
model planning, matched R-GCN assessment and source preservation. Its scientific
boundary remains correct. The newer report can add the completed
[STRING component](STRING_COMPONENT_COMPARISON_20261027.md),
[temporal control](STRING_TEMPORAL_CONTROL_20261027.md), and
[product verification](PHYSICAL_PRIORITY_PRODUCT_CHECK_20261027.md), without
recasting those results as independent validation. The earlier GO/Reactome
negative or mixed results remain unchanged.

The [organizer update](../ORGANIZER_UPDATE_20261026.md) supports preparing both
the resulting scoped graph and its decision ledger. The specific whole-graph
baseline/version, scoring contract and final file schema remain unspecified.
The supplied criteria treat usability, accuracy/pruning, explainability and
standards separately; export success does not satisfy biological evaluation.
AWS credits have been received according to the user, but AWS deployment is not
demonstrated or established as a requirement.

## Verification and restored source-reuse link

The saved BRAF answer passed current offline source/review reconstruction with
live collection disabled. All six files in its existing question ZIP match the
saved answer directory, and its TSV contains all 21 matches. The saved question
route returns HTTP 200. See the [original product receipt](physical_priority_product_check_20261027_summary.json).

The historical source-reuse workspace correctly failed current verification
because its `questions.py` implementation pin predates the physical-priority
extension. Every historical source/supplement byte still matches its manifest;
there was no demonstrated projection error. The documented offline publication
command republished the unchanged original attachment and trace into a **new**
workspace, `source_reuse_workbench_replay_20261027`, with a new saved assay
question. Its annotation equals the historical annotation exactly. No validation
pin was relaxed and no historical publication was edited.

Current metadata, readable report, saved-answer and download routes all return
HTTP 200. The downloaded ZIP preserves all **77** workspace files byte-for-byte,
and the extracted workspace verifies offline. Evidence is recorded in
`runs/midpoint_demonstration_20261027/verification.json` and
`source_reuse_replay_download.zip`. The initial inspection assumed unprefixed ZIP
members; correcting that inspection to the existing workspace-rooted layout
required no production change.

This was source/artifact/HTTP verification. A current visual browser walkthrough
and independent colleague walkthrough remain outstanding. The historical
source-reuse URL should not be used with the current implementation; use the
new replay link above. All fresh reference bodies remain unopened.
