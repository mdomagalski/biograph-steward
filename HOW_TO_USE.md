# How to use BioGraph Steward

Use BioGraph Steward to follow a biological question to its graph, inspect the
supporting source records, and share a result someone else can check.
The reviewer example covers **99 primary human protein targets** from a captured
Pharos cohort, with additional qualified protein-association and location data.
This is a frozen research workspace; [source dates](docs/SOURCE_NOTES.md#current-reviewer-graph-and-source-dates)
are recorded separately from the date the app was updated.

**[Open the reviewer app](https://bi-3a117d5e2b3942678dc518fce65ab5d2.ecs.us-east-2.on.aws/)**
and sign in with the token supplied privately. No AWS account, installation or
running model is needed. Prefer to watch first? Use the
[3:58 narrated walkthrough](output/walkthrough/BioGraph_Steward_Walkthrough.mp4)
or its [transcript](output/walkthrough/BioGraph_Steward_Walkthrough.txt).

The shared site replays actual completed agent work and checks its saved sources.
It does not make new model calls, retrieve new data or apply review edits. New
questions can be run in an authorized [operator installation](docs/SOURCE_AGENT.md#operator-cli).

## 1. Open the recorded question

[Open the recorded KRAS example directly](https://bi-3a117d5e2b3942678dc518fce65ab5d2.ecs.us-east-2.on.aws/?run=native_evidence_workspace_20261115&question=native_physical_KRAS_question_v3_20261115&agent_job=source_agent_eval_dc7b597201da_S01&view=data).

In **Start here → Agent workflow**, use the designated recorded KRAS run.
If it is not already open, expand **Open a recorded agent run**, select the
verified KRAS model record and choose **Replay the recorded run**.
Allow the recorded run to finish loading before continuing; the app checks its
saved sources before displaying the result.
A spinner and message identify what is loading. If a load fails, the spinner
stops and the error stays visible.

The question asks which proteins in the saved cohort have physical-association
records with **KRAS**. KRAS is the protein at the centre of this example; the
answer covers the selected workspace rather than every protein in biology.

## 2. Follow the four agent steps

Use the numbered step tabs, or each **Continue** button.

| Step | What to inspect | What you should learn |
|---|---|---|
| **1. Question & plan** | The question, KRAS identity, native physical source and limit of eight results. | The model proposed a source query that the app checked before executing. |
| **2. Evidence graph** | The graph and cited answer. Find **CDC42BPB**. | Eight of 14 matching partners are displayed under this run's limit. The separate manual KRAS answer displays all 14. |
| **3. Source inspection** | Expand **Inspected citation [E002]**, then **Native physical source coverage and identity**. | This KRAS–CDC42BPB source pair was absent from the captured baseline. |
| **4. Review proposals** | The proposal linked to E002. | **Retain candidate context** keeps the record available for review; it does not accept the claim or change the graph. |

For E002, find **baseline pair present: false** and
**integration state: new_workspace_pair**. This is one of **87** qualified
physical-association pairs absent from the captured Pharos graph. It is an
addition to this saved evidence collection, rather than a newly discovered
biological interaction.

The same source passport preserves **STRING 12.5**, its score of **203/1000**,
and protein-identity checks. Physical association can mean proximity or a shared
protein complex; it does not establish direct binding. A provider score is not
a measured probability that the biological claim is true.

For more detail, use **All returned source citations → Inspect this claim
manually**. The model prioritized three citations, but all eight returned results
remain available. Every source assertion grouped under a selected citation was
inspected; complete technical details are available in the disclosures.

## 3. See what changed and what was measured

[Open the qualified TP53 example directly](https://bi-3a117d5e2b3942678dc518fce65ab5d2.ecs.us-east-2.on.aws/?run=source_faithful_workspace_20261113&question=question_20261113T075313Z_1a76b00f&view=ask).

Return to **Start here** and choose **Review applied graph qualifications**.
This opens the matched retained TP53 example, which has a different source
collection from the KRAS candidate example. Open **What changed**.
The page heading is **Graph changes and assessment**: it explains applied
qualifications and measured scientific results for the saved data.

- **Applied qualification:** 16,985 input records become **16,687 retained**.
  The **298 exclusions use obsolete Gene Ontology identifiers**. Original
  records and reasons are preserved; unresolved records stay retained.
- **Location-reference comparison:** using the same ontology-qualified mapping,
  captured Pharos recovers **41/51** known labels and the native source view
  recovers **44/51** among 31 matching proteins. The previously used OpenCell
  reference changes from **30/40 to 31/40** among 23 matching proteins.

Read the whole comparison table, including its controls. These measurements
show known-label recovery under defined source views; shared sources and prior
reference use limit independence. The separate, larger
[protein-function prediction study](docs/evaluations/CONTEXTUAL_COMBINATION_RESULTS_20261115.md)
has its own graph, methods and comparisons. It is not the recorded agent's score.

A diagram is a focused answer, not the complete workspace. For example, the
native workspace contains **9,724 entities and 19,310 evidence records**;
the displayed KRAS graph selects only the records relevant to that question.

## 4. Download the result you need

| Download | Use it for |
|---|---|
| **Download this verified agent record** | The question, model/tool trace, source inspections and review proposals. Its source workspace is also needed for replay. |
| Focused answer ZIP | The selected question, cited answer and focused graph. |
| **Export → Download run ZIP** | The complete saved workspace graph, source files and provenance. |

In the **retained TP53 example**, the run ZIP also contains
`source_retained_package`: `retained_graph.json` is the resulting graph,
`edge_dispositions.jsonl` holds each input record's decision and reason, and
`baseline_packet` holds the original graph and sources. An undecided record
remains retained. The native KRAS ZIP contains its candidate graph and sources;
it does not include the separate TP53 qualification decisions.

For the challenge graph-and-ledger package and its separate Pharos-only
comparator, use the [protected graph downloads](docs/GOLD_SET_INTERFACE.md#protected-downloads).
Those assessment packages are separate from the focused answer and ordinary
workspace downloads above.

## Try another question or give feedback

Recorded examples also cover EGFR physical associations, TP53 locations and BRAF
archived pathway context. For BRAF, first open **Review applied graph
qualifications**, then choose its recorded run in that retained workspace.
Select an available recorded run; its attached source tools determine what can
be answered. **Candidate** means available for review;
**accepted** means explicitly accepted in the local review state. An empty
accepted-only answer does not mean there is no biological evidence.

To run a new agent question or construct a new cohort, follow
[operator instructions](docs/SOURCE_AGENT.md#operator-cli) or
[cohort construction](docs/CONSTRUCTION.md). Those are separate from the
read-only shared review above.

For usability feedback, send the step where you got stuck, what you expected,
and what happened. A screenshot is useful if it shows no token. Can you identify
one added connection, trace its source, distinguish a proposal from an applied
decision, and find the files another researcher would need?
