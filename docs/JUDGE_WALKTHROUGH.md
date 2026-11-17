# Judge review route

Use the **[single step-by-step user guide](../HOW_TO_USE.md)** for operating the
app. This page identifies the evidence to assess against the supplied rubric.
The [current submission overview](SUBMISSION_OVERVIEW.md) explains the measured
improvements; the [full alignment crosswalk](PROJECT_ALIGNMENT.md) separates
requirements, delivered features and remaining release actions.

## Open the real example

[Open the public demo](https://bi-3a117d5e2b3942678dc518fce65ab5d2.ecs.us-east-2.on.aws/?run=native_evidence_workspace_20261115&question=native_physical_KRAS_question_v3_20261115&agent_job=source_agent_eval_dc7b597201da_S01&view=data)
directly, with no sign-in. The recorded KRAS run uses real saved
sources, with no new inference during replay. Reviewers need no AWS account,
local setup or running model. New operator-run questions are documented in the
[source-agent guide](SOURCE_AGENT.md#operator-cli).

One application offers **Added source context workspace**, used by the KRAS
example, and **Qualified Pharos workspace**, opened through **Review applied
graph qualifications**. These are two saved examples with different inputs.
The historical function-prediction study is a separate assessment.

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
| **Accuracy and pruning — 30%** | Results & evaluation; Qualified Pharos workspace; linked scientific comparisons | Known-label recovery increases 41/51 → 44/51 under the same mapping. The Qualified Pharos workspace applies 298 obsolete-ID exclusions to its own input. Keep source additions, identifier checks and the separate function-prediction benchmark distinct. |
| **Explainability — 20%** | E002 source passport, model/tool trace and exported decision reasons | Provider/version, baseline membership, exact identity evidence, review state and uncertainty remain inspectable. A proposal is separate from an applied decision. |
| **Standards — 10%** | [Export audit](STANDARD_EXPORT.md), [mapping/overlap audit](EVIDENCE_OVERLAP.md) and graph/source files | Inspect stable identifiers, declared predicates, source provenance and the validated bounded profiles. Their full-graph conformance limits are recorded. |

The weights come from the supplied brief; this is an evidence map, not a
predicted judging score. The [same-learner graph comparisons](PROJECT_ALIGNMENT.md#scientific-comparisons-and-their-distinct-scopes)
remain part of the submission record. The positive function-prediction result
has its own task and controls and does not replace that endpoint.

## Inspect the graph handoff

The Added source context workspace and Qualified Pharos workspace contain
different source collections in the same 99-target cohort. Their total record
counts are not a before/after comparison. Use each graph with its own source
baseline and decision ledger; the [Gold interface](GOLD_SET_INTERFACE.md)
explains retained graphs, complete dispositions and abstentions.
The [five-item final folder](DELIVERY.md#final-submission-folder) supplies the
report, narrated demonstration, slides, **START_HERE.txt** and a private
**BioGraph_Steward_App_Data_and_Exports.zip**. The ZIP contains the complete
KRAS app/source workspace and graph/ledger inspection exports for both examples,
including the primary 19,310-row undecided ledger and exact captured Pharos
comparator. Qualified Pharos exports preserve its input, retained graph and
decisions; its full source-recovery packet remains a separate optional replay
asset. Source terms govern this organizer data handoff. The public demo does not
expose the bulk graph/ledger packages.

[How to use → Download the result you need](../HOW_TO_USE.md#4-download-the-result-you-need) distinguishes the focused answer,
recorded-agent trace and full workspace. The [delivery index](releases/20261115/README.md)
identifies current reviewer artifacts and separate source-packet access.

## Watch or present

The **[narrated tour](../output/walkthrough/BioGraph_Steward_Walkthrough.mp4)**,
[transcript](../output/walkthrough/BioGraph_Steward_Walkthrough.txt) and
[seven-slide overview](../output/presentations/BioGraph_Steward_Overview.pptx)
are the current presentation files. The tour uses actual browser screenshots,
a precomputed app assessment and a separately labelled rendering of existing
prediction-result tables. It makes no new model calls or statistical experiment.

| Chapter | What it shows |
|---|---|
| Added context | What Steward adds to the captured Pharos baseline |
| Source inspection | Actual addition: KRAS–CDC42BPB and its source |
| Location reference | More published location labels recovered |
| Agent workflow | The agent's question-to-source workflow |
| Function prediction | Separate measured function-prediction gain |
| Graph qualification | Applied identifier qualification |
| Interpretation | How to read the comparisons |
| Graph exploration | All-result overview, pair focus and searchable connected-path examples |
| Local continuation | Complete editable workspace and review saved in a new run |
| Reuse | Inspectable results and graph handoff |

The [deployment record](DELIVERY_STATUS_20261115.json) keeps server/API checks
separate from browser and human usability checks. [Source notes](SOURCE_NOTES.md)
record the actual snapshot and upstream annotation dates. Earlier media and
research results remain in their labelled history.
