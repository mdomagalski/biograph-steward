# BioGraph Steward | Challenge submission

BioGraph Steward uses a bounded NVIDIA Nemotron agent to guide a supported
research question through existing source tools. It returns a focused Pharos
evidence graph, a cited answer, inspected source records and grounded review
proposals. Each connection retains its original source and conditions.

The actual current-source agent comparison, narrated local demonstration and
protected hosted replay are complete. The
[hosted acceptance](evaluations/final_prod_ui_20261116/hosted_acceptance.json)
and [delivery status](DELIVERY_STATUS_20261115.json) record the verified deployment;
the tour's local filming provenance remains separate.

The final shared interface now includes loading/error feedback and keeps current
assessment results while hiding development dashboards. Its
[partial hosted desktop checks](evaluations/final_prod_ui_20261116/hosted_browser_acceptance.json)
covered the agent, sources, qualification and export controls. Two browser
transport interruptions left the final return/mobile recheck incomplete; the
cause is unresolved. This does not change the separately passed server/source
acceptance or establish a completed independent user walkthrough.

**Start with [How to use BioGraph Steward](../HOW_TO_USE.md)**, the
[judge evidence route](JUDGE_WALKTHROUGH.md), and
[protected reviewer site](https://bi-3a117d5e2b3942678dc518fce65ab5d2.ecs.us-east-2.on.aws/).
The workspace token is supplied privately. No AWS account, graph-query language,
GPU or model server is needed for saved review. The
[delivery status](DELIVERY_STATUS_20261115.json) identifies accepted deployments;
the [3:58 narrated screen tour](../output/walkthrough/BioGraph_Steward_Walkthrough.mp4)
uses actual local-app captures of verified saved real data, edited screenshot
states and synthetic narration. It makes no new model requests. The
[seven-slide overview](../output/presentations/BioGraph_Steward_Overview.pptx)
provides its presentation.

## One research cohort, connected research tasks

Both examples concern **99 primary protein targets from a captured colorectal
cancer cohort**. They demonstrate different operations, with different source
collections; their total record counts are not a paired before/after comparison.

| Task | What a reviewer can see | Concrete outcome |
|---|---|---|
| **Follow the agent's work** | A recorded model plan, validated tool call, complete selected-citation inspections and source-bound review proposals | The primary KRAS run displays eight of 14 matching proteins under its frozen cap. Three selected citations lead to three original source inspections. Proposals retain candidate context without applying decisions. The complete returned answer remains available. |
| **Explore added source context** | A KRAS question, small graph, cited answer and preserved native STRING source record | 14 candidate result proteins. The full added physical source has 330 qualified pairs: 243 already represented in the captured graph and 87 absent there. Native GO adds 3,309 records describing 429 protein-location concepts across 94 targets. Additional rows are not automatically independent experiments or accepted claims. |
| **Review applied graph qualifications** | A TP53 pathway question using the graph after explicit qualification decisions | 16,985 input records become 16,687 retained records. The 298 excluded records have obsolete GO identifiers in the pinned ontology. All original rows and decisions remain recoverable; 11,636 abstained records stay retained. This is identifier qualification, not 298 experimentally disproved biological links. |

The pathway example supports contextual multihop reasoning: TP53 and another
protein connect through an exact cited model. Shared model membership does not
assert direct binding. Native archived models preserve connections that a
current-only flat list can omit, and unresolved source claims are not pruned
merely because a current lookup fails.

The recorded agent work appears in four sequential tabs: **Question & plan**,
**Evidence graph**, **Source inspection** and **Review proposals**. Continue
buttons keep one step visible at a time; source records and technical traces
remain available through disclosures.

## Evidence for the judging criteria

The organizers' final-presentation email makes **democratization** the central
goal: scientists should be able to use agents to build knowledge graphs without
being KG specialists. It also asks teams to demonstrate generalizability and
provide a hosted or launchable demonstration, or a short video/writeup with the
graph. Our evidence is the guided question-to-graph workflow, readable answers
and source inspections, reusable cohort construction, protected hosted examples,
portable software, narrated tour and downloadable graph/comparator packages.
The supplied email is the source of this clarification. Its linked response
document could not be read without access; no additional rules are inferred.

The organizer brief assigns the following weights and permits autonomous
**or semi-autonomous** software. This is our evidence map, not an official score.

| Criterion | Visible demonstration | Evidence and boundary |
|---|---|---|
| **Usability (40%)** | Question, agent plan, tool execution, inspected sources and proposed decisions | A recorded model run leads to a readable cited answer without graph syntax. Teammate feedback has informed control/navigation fixes. A structured independent walkthrough remains pending. |
| **Accuracy & pruning (30%)** | Review applied qualification and its exhaustive decisions | 298 obsolete-ID exclusions are applied and reversible; unknowns remain retained. Public-reference recovery measures additional support. Automatic biological error removal and whole-graph correctness are not established. |
| **Explainability (20%)** | Select an answer citation and inspect its source passport | Provider/version, original fields, exact identifiers, sequence or native-model checks, missing context and local review state remain visible. Database agreement is not counted as independent experimental replication. |
| **Standards (10%)** | Inspect identifiers/categories and export the graph with provenance | UniProt, GO, MONDO/Reactome and explicit Biolink references are used. Bounded KGX and SSSOM profiles have recorded validation and mapping limits; full interoperability is not claimed. |

The [alignment crosswalk](PROJECT_ALIGNMENT.md) maps the complete brief and
proposal to delivered functions and unresolved commitments. Organizers also
asked for experimentally measured held-out links, tested with the **same graph
learner** on baseline and enriched graphs. Those comparisons were executed;
they do not establish consistent enriched-graph superiority over Pharos and
the strongest controls. The separate function-recovery results below do not
replace that endpoint.

## What improved, and what the measurements mean

The agent now orchestrates actual source tools and inspections. In the
[frozen development comparison](evaluations/SOURCE_AGENT_RESULTS_20261116.md),
four nonempty queries and one valid accepted-only empty query preserved the
deterministic tool's complete query, answer and focused graph. Three unsupported
or unresolved requests stopped at preflight with zero model calls. All eight
behavioral checks passed, using 13 calls and 972 reported output tokens, with
no retries or repairs. The refusals establish controller guards, not learned
model refusal. Only the TP53 location request offered two source-tool choices;
the other supported requests already constrained the tool and exact protein.

Captured Pharos alone lacks these separately attached native-source contracts;
that is a source-availability distinction, not a biological-error label.
Agent and deterministic execution use the same fixed sources and result caps.
Neither changes the source graph or learner inputs, so this comparison measures
source fidelity and workflow execution rather than prediction improvement.

The separate public-reference assessment measures information recovered by
the source views:

- **Known protein locations:** among 31 matching proteins, the captured Pharos
  view recovers 41 of 51 positive reference labels; qualified native annotations
  recover 44 of 51. These fixed source views are not a newly scored union of the
  full integrated graph. The additional admitted location annotations supply
  the gain under the same ontology mapping; obsolete-ID exclusions alone do
  not improve recovery. The coarse-map control also recovers 44 labels, with
  more truth-unknown outputs. Shared-source context remains explicit.
- **OpenCell source-exclusion check:** among 23 matching proteins, positive
  label recovery changes 30 of 40 to 31 of 40. The gain remains after the stated
  HPA/OpenCell source exclusions. This already-exposed reference is a
  sensitivity check, not new blind validation or a new biological discovery.
- **Later curator function recovery:** a fixed historical comparison improves
  over retained LocalPlus in its primary views. We reused the published
  **ProtBoost** context-aware stacker and the authors' CAFA6 update to combine
  graph and sequence forecasts with GO evidence-code, relation and ontology
  context. These are qualified views of one GOA source. Refreshing the baseline's
  annotations also helps; additional learned benefit over that refreshed
  baseline remains uncertain for the primary task. Stronger direct-annotation
  controls and unfavorable results are retained.

Positive-reference recovery counts known labels found by a view. Unmatched
proteins and unreported labels remain unknown, so these results do not identify
the fraction of the full graph that is biologically correct. See the
[public-reference result](evaluations/PUBLIC_GOLD_REFERENCE_RESULTS_20261115.md),
[applied qualification result](evaluations/SOURCE_FAITHFUL_WORKSPACE_20261113.md)
and [fixed function comparison](evaluations/CONTEXTUAL_COMBINATION_RESULTS_20261115.md)
for complete scopes, controls and denominators.

## Construction and agents

Clinical evidence inspection is also implemented through a separate, bounded
**CIViC** workflow for KRAS and colorectal cancer. It preserves the complete
molecular profile, whole therapy set and interaction type, disease, response
direction, evidence level, publication and source curation status rather than flattening a clinical
claim into a generic protein–drug edge. Source editorial acceptance remains
distinct from local review. CIViC is not an input to the current native
GO/STRING agent demonstration or the separate historical function-prediction
comparison; those gains are not attributed to it.

The executable workflow retrieves bounded structured Pharos data, resolves
explicit identifiers, constructs versioned assertions and publishes the graph,
source snapshots and answer. Source-specific extensions retain their own
records, mapping proof and provenance. The
[construction recipe](CONSTRUCTION.md) documents local execution and replay.
Three additional fixed questions also completed through the existing engines:
EGFR physical partners, TP53 native location records and BRAF archived pathway
context. This [applicability check](evaluations/VARIED_QUESTION_CHECK_20261115.md)
preserves source distinctions, result caps and empty accepted-only views. It
tests reusable execution within the same cohort, separately from scientific accuracy.
The shared reviewer site is deliberately a **saved-workflow demonstration**:
fresh construction, retrieval, model calls and review edits are disabled there.

The [current-source agent](SOURCE_AGENT.md) uses up to three model calls:
propose a tool plan, prioritize returned citations for complete source
inspection, then select adapter-grounded review proposals. The application
validates the plan and preserves the deterministic cited answer. **Retain
candidate context** and **Needs review** change no assertion or local decision.
All selected citations retain every original source assertion, with explicit
inspection coverage; compact model context binds to the complete passports.

The earlier one-call planner, NeMo Agent Toolkit wrapper and literature-audit
agent retain their separate [NVIDIA integration record](NVIDIA_INTEGRATION_STATUS_20261113.md).
The literature auditor did not outperform its specialist baseline and has not
become an automatic acceptance or biological-pruning authority. Its result
does not replace the new current-source workflow evaluation. This is bounded
semi-autonomous research support, with explicit source and decision limits.

Versioned snapshots, guarded comparison and review history support maintenance;
unattended literature monitoring is outside the delivered scope. A working
bounded pipeline is supplied instead of claiming every platform or autonomous
role listed in the original proposal.

## Reuse and handoff

The [four-page final report](../output/docx/BioGraph_Steward_Final_Report.docx)
preserves the organizer's form layout and section order, with final limitations
and delivered outputs replacing help requests and a future work plan. Its
two-page supplement explains methods, CIViC's separate role, measured gains and
the demonstrated scope of reuse. The [format and review receipt](evaluations/final_prod_ui_20261116/final_report.json)
records it as prepared for user review, not submitted. The
[code-only software ZIP](../output/software/BioGraph_Steward_Software.zip)
has [clean acceptance for tested source `d05f54f`](evaluations/final_prod_ui_20261116/software_acceptance.json);
its deployment status is tracked separately.

The native KRAS workspace ZIP includes its candidate graph and preserved source
files. The **designated primary submission package** also has its own complete
19,310-row abstention ledger and an exact same-snapshot Pharos-only comparator;
its [protected-download receipt](evaluations/final_prod_ui_20261116/protected_graph_downloads.json)
records both actual HTTPS archives and complete member checks. The
[download instructions](GOLD_SET_INTERFACE.md#protected-downloads) require only
sign-in at the reviewer site. All primary records remain unassessed; these
abstentions are not biological acceptance. In the applied-qualification TP53 example, the workspace ZIP also
includes the retained graph, complete keep/prune/abstain ledger and original
baseline/source packet. The small answer diagram and focused answer ZIP are
separate views. Original and retained graphs stay distinguishable, and
abstentions do not disappear.

The verified agent-record download preserves its question, plan, model/tool
trace, source inspections and proposals. It replays beside the original source
workspace; that small record does not silently include the full source packet.

- [Code and build instructions](../START_HERE.md): MIT software with a local
  synthetic demonstration, explicitly labeled as invented data.
- [Delivery and source-access instructions](DELIVERY.md): tested code release,
  protected real examples and separate source packets under their own terms.
- [Standard export](STANDARD_EXPORT.md) and [mapping/overlap audit](EVIDENCE_OVERLAP.md):
  declared vocabularies, admitted mappings and known compatibility limits.
- [Submission overview](SUBMISSION_OVERVIEW.md) and
  [delivery checklist](evaluations/DELIVERY_COMPLETENESS_20261115.md): current
  handoff and remaining release/access actions.
- [Preserved research appendix](RESEARCH_APPENDIX_20261115.md): the former long
  narrative, retained verbatim with historical experiments and their outcomes.
  It is supporting evidence, not the app's primary navigation.

The repository is private during preparation and is intended to become public
for final open-source submission. Publication and actual submission must be
recorded when performed. Software licensing does not relicense upstream data;
the graph, ledger and baseline use the protected access route above.
