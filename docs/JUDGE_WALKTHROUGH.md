# Judge review route

Use the **[single step-by-step user guide](../HOW_TO_USE.md)** for operating the
app. This page identifies the evidence to assess against the supplied rubric.
The [current submission overview](SUBMISSION_OVERVIEW.md) explains the measured
improvements; the [full alignment crosswalk](PROJECT_ALIGNMENT.md) separates
requirements, delivered features and remaining release actions.

## Open the real example

[Open the protected reviewer site](https://bi-3a117d5e2b3942678dc518fce65ab5d2.ecs.us-east-2.on.aws/)
and use the token supplied privately. The recorded KRAS run uses real saved
sources, with no new inference during replay. Reviewers need no AWS account,
local setup or running model. New operator-run questions are documented in the
[source-agent guide](SOURCE_AGENT.md#operator-cli).

Follow **Question & plan → Evidence graph → Source inspection → Review
proposals**. In **E002, KRAS–CDC42BPB**, find **baseline pair present: false**
and **integration state: new_workspace_pair**. That is an actual source-qualified
addition to the captured graph. Its STRING 12.5 score 203 and identity checks
remain visible. The [addition audit](evaluations/source_agent_20261116/demonstrated_additions.json)
preserves the original baseline comparison and all counts.

## Match the supplied scoring criteria

| Criterion | Where to look | Evidence to assess |
|---|---|---|
| **Usability — 40%** | The user guide, four-step agent workflow and result downloads | Can a reviewer find what was added, trace a source and share the right result without graph-query syntax? Record loading/access problems and unclear next actions. |
| **Accuracy and pruning — 30%** | What changed; applied qualification companion; linked scientific comparisons | Known-label recovery increases 41/51 → 44/51 under the same mapping. The separate companion applies 298 obsolete-ID exclusions. Keep source additions, identifier checks and the separate function-prediction benchmark distinct. |
| **Explainability — 20%** | E002 source passport, model/tool trace and exported decision reasons | Provider/version, baseline membership, exact identity evidence, review state and uncertainty remain inspectable. A proposal is separate from an applied decision. |
| **Standards — 10%** | [Export audit](STANDARD_EXPORT.md), [mapping/overlap audit](EVIDENCE_OVERLAP.md) and graph/source files | Inspect stable identifiers, declared predicates, source provenance and the validated bounded profiles. Their full-graph conformance limits are recorded. |

The weights come from the supplied brief; this is an evidence map, not a
predicted judging score. The [same-learner graph comparisons](PROJECT_ALIGNMENT.md#scientific-comparisons-and-their-distinct-scopes)
remain part of the submission record. The positive function-prediction result
has its own task and controls and does not replace that endpoint.

## Inspect the graph handoff

The primary native-source example and the applied-qualification companion are
different source collections in the same 99-target cohort. Their total record
counts are not a before/after comparison. Use each graph with its own source
baseline and decision ledger; the [Gold interface](GOLD_SET_INTERFACE.md)
explains retained graphs, complete dispositions and abstentions.
The [prepared primary package](evaluations/delivery_readiness_20261116/primary_graph_handoff.json)
binds its 19,310-row abstention ledger and exact captured Pharos comparator;
the complete mixed-source packet uses permitted private access.

[How to use → Download the result you need](../HOW_TO_USE.md#4-download-the-result-you-need) distinguishes the focused answer,
recorded-agent trace and full workspace. The [delivery index](releases/20261115/README.md)
identifies current reviewer artifacts and protected source access.

## Watch or present

The **[3:58 narrated tour](../output/walkthrough/BioGraph_Steward_Walkthrough.mp4)**,
[transcript](../output/walkthrough/BioGraph_Steward_Walkthrough.txt) and
[seven-slide overview](../output/presentations/BioGraph_Steward_Overview.pptx)
are the current presentation files. The tour uses actual local-app screenshots,
a precomputed app assessment and a separately labelled rendering of existing
prediction-result tables. It makes no new model calls or statistical experiment.

| Chapter | What it shows |
|---|---|
| 0:00 | What Steward adds to the captured Pharos baseline |
| 0:30 | Actual addition: KRAS–CDC42BPB and its source |
| 1:00 | More published location labels recovered |
| 1:29 | The agent's question-to-source workflow |
| 2:04 | Separate measured function-prediction gain |
| 2:42 | Applied identifier qualification |
| 3:11 | Interpretation of the comparisons |
| 3:33 | Inspectable results and reusable graph handoff |

The [deployment record](DELIVERY_STATUS_20261115.json) keeps server/API checks
separate from browser and human usability checks. [Source notes](SOURCE_NOTES.md)
record the actual snapshot and upstream annotation dates. Earlier media and
research results remain in their labelled history.
