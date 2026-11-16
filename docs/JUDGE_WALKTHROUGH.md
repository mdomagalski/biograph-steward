# Five-minute judge walkthrough

> The protected reviewer site now replays the recorded agent workflow. The
> narrated tour demonstrates the same workflow in the actual local application
> using verified saved real data. [Hosted acceptance](evaluations/source_agent_20261116/hosted_acceptance.json)
> is recorded separately from the local filming provenance.

**Question:** Which retrieved proteins have physical-association records with
KRAS, and what can their evidence justify?

BioGraph Steward starts with a captured Pharos workspace covering **99 primary
human protein targets**. The current agent proposes a supported source query,
prioritizes citations for inspection, and returns grounded review proposals.
Existing source tools supply the graph and cited statements.

[Open the protected reviewer site](https://bi-3a117d5e2b3942678dc518fce65ab5d2.ecs.us-east-2.on.aws/)
and use the privately supplied token. You need only a browser. This review opens
an actual recorded model run and verifies its saved sources; it makes no model
requests, retrieves no new data and changes no graph or review decisions.

## 1. Follow the recorded agent run

In **Start here → Agent workflow**, open the designated recorded KRAS run.
If needed, expand **Open a recorded agent run**, choose its verified model
record and select **Replay the recorded run**.

In **1. Question & plan**, read the research question and validated tool plan. The run names
KRAS's exact protein identity, the native physical source, the candidate view
and its limits. The application validates this plan before executing it. The
model's explanation of its scope remains an unverified rationale.
Here **native** means the provider's separately saved record, with its own
release and identity checks, rather than only its summary inside Pharos.

**Find:** the selected tool and the result cap of eight.

## 2. Read the answer and inspect the agent's evidence

Choose **Continue: Evidence graph**. The recorded query displays **eight
of 14 matching proteins**. Six remain outside this recorded display limit.
The older manual KRAS question displays all 14 under its different cap.
Neither count measures biological truth or local acceptance.

Read the AKT1 statement, then choose **Continue: Source inspection** and
expand **Inspected citation [E001]**. The agent
selected this returned citation for inspection; the application checked every
source assertion grouped under it. All returned results remain in the saved
answer, including citations the agent did not prioritize.
`[E001]` identifies preserved database evidence. A publication link appears
only when the source supplies one.

For fuller source context, expand **All returned source citations** and choose
**Inspect this claim manually**. Read the native STRING source explanation.
The KRAS–AKT1 record preserves score **459** on its provider's 0–1000 scale.
That score describes source confidence, not a probability of scientific truth.
Physical association can mean proximity or a shared protein complex. It does
not establish direct binding, an assay result or a cancer-specific mechanism.
STRING already contributes to Pharos, so another row is not automatically
another independent experiment.

**Find:** one source qualification and one scientific limit.

## 3. Understand the proposed decision

Return to the recorded run and choose **4. Review proposals**.
**Retain candidate context** keeps eligible source evidence available for
review. **Needs review** identifies an unresolved issue. These proposals name
their inspected citations. They accept no assertion, remove no edge and
change no local review state.

**Find:** the citation supporting one proposal. Explain whether it changes the
graph. A valid source inspection supports traceability; it does not independently
prove the biological claim.

## 4. Check actual qualification and measured benefit

From **Start here**, open **Review applied graph qualifications**. This matched
TP53 companion has a different source collection. In **What changed**, find
the applied reduction from **16,985 input records to 16,687 retained records**.
The **298 exclusions use obsolete Gene Ontology identifiers**. Originals and
reasons remain available. Abstained records stay retained. This checks identifier
currency rather than identifying 298 experimentally disproved relationships.

Then read the featured location-reference comparison. Among **31 matching
proteins**, Pharos recovers **41/51** known positive location labels and the
qualified native GO view recovers **44/51**. The already-used OpenCell reference
changes **30/40 to 31/40** among **23 matching proteins**. These are fixed source
views, not a newly evaluated union of the whole graph. Shared-source context
and prior reference exposure remain explicit.

The [saved assessment report](https://bi-3a117d5e2b3942678dc518fce65ab5d2.ecs.us-east-2.on.aws/api/scientific-assessment/scientific_assessment_public_reference_20261115_v3/report)
also shows the complete fixed location-reference table and its source limits.

In the fixed development comparison, four nonempty queries and one valid
accepted-only empty query preserved the deterministic tool's complete result.
Three unsupported or unresolved requests stopped before any model call. This
checks source fidelity and scope guards. The agent adds no source data or
learner inputs, so these results do not measure a prediction gain. Positive-label recovery likewise does not
measure the fraction of the entire graph that is scientifically correct.

## 5. Take away a reproducible result

Use **Download this verified agent record** for its question, model/tool trace,
inspections and proposals. The source workspace must accompany it for replay.
The focused answer ZIP and complete workspace ZIP serve different purposes.

For the retained TP53 example, **Export → saved workspace ZIP** also preserves
`source_retained_package` with:

- `retained_graph.json`, the graph after the recorded decisions;
- `edge_dispositions.jsonl`, every input record's decision and reason;
- `baseline_packet`, the preserved input graph and source records.

An abstention retains its record. The native KRAS workspace ZIP preserves its
candidate graph and sources; it does not acquire the separate TP53 decisions.

For feedback: Can you identify the agent's tool, read its answer, explain one
source limitation and distinguish a proposal from an applied decision? Can you
find the measured result and the files another researcher would need?

See [Current-source agent](SOURCE_AGENT.md), the
[recorded evaluation](evaluations/SOURCE_AGENT_RESULTS_20261116.md) and
[submission summary](FINAL_SUBMISSION.md) for precise scope and limitations.

## Watch or present the work

The [3:54 narrated screen tour](../output/walkthrough/BioGraph_Steward_Walkthrough.mp4),
[transcript](../output/walkthrough/BioGraph_Steward_Walkthrough.txt) and
[seven-slide overview](../output/presentations/BioGraph_Steward_Overview.pptx)
are the current reviewer files. The video uses actual local-app captures of
verified saved real data, including the existing assessment report. It combines
edited screenshot states and focused crops with synthetic narration; it is
not a continuous interaction recording. Authentication stays off camera and
loading waits are omitted. Capture and replay make zero model requests,
retrieve no new scientific source data and apply no review decisions. The
depicted primary job records three actual model calls; the separate frozen
comparison records 13. See the [media receipt](../output/walkthrough/BioGraph_Steward_Walkthrough.receipt.json).

| Chapter | What it shows |
|---|---|
| 0:00 | One real research question |
| 0:26 | The agent's validated tool plan |
| 0:58 | The capped answer and its evidence graph |
| 1:29 | Source inspection and grounded review proposals |
| 2:04 | Measured source recovery and its interpretation |
| 2:46 | Applied identifier qualification |
| 3:19 | Saved agent work and graph handoff |

[Earlier guided-review media](../output/history/20261115_guided_review/README.md)
remains preserved with its original scope and dates.
