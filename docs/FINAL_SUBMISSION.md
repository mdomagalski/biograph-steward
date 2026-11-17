# BioGraph Steward challenge submission

BioGraph Steward helps scientists build and inspect scoped evidence graphs
without writing graph queries. A bounded NVIDIA Nemotron agent plans a supported
question, the application executes existing source tools, and the agent
prioritizes citations for inspection. The result combines a focused Pharos
graph, a cited answer, source records and grounded review proposals. Each
connection retains its original source and conditions.

**Start with [How to use BioGraph Steward](../HOW_TO_USE.md)** and the
[public browser demo](https://bi-3a117d5e2b3942678dc518fce65ab5d2.ecs.us-east-2.on.aws/?run=native_evidence_workspace_20261115&question=native_physical_KRAS_question_v3_20261115&agent_job=source_agent_eval_dc7b597201da_S01&view=data).
No sign-in, AWS account, graph-query language,
GPU or model server is needed for the saved examples. The
[Narrated screen tour](../output/walkthrough/BioGraph_Steward_Walkthrough.mp4)
uses actual local-app captures of verified saved real data, edited screenshot
states and synthetic narration. It makes no new model requests. The
[seven-slide overview](../output/presentations/BioGraph_Steward_Overview.pptx)
provides its presentation.

## One application, two saved examples

The saved-workspace picker names the examples **Added source context workspace**
and **Qualified Pharos workspace**. Both concern **99 primary protein targets
from a captured colorectal-cancer cohort**. They demonstrate different
operations and preserve different source collections; their totals are not a
paired before/after comparison. The historical function-prediction study is a
separate research assessment, not another version of the app graph.

| Task | What a scientist can see | Concrete outcome |
|---|---|---|
| **Follow the agent's work** | A recorded model plan, validated tool call, complete selected-citation inspections and source-bound review proposals | The primary KRAS run displays eight of 14 matching proteins under its frozen cap. Three selected citations lead to three original source inspections. Proposals retain candidate context without applying decisions. The complete returned answer remains available. |
| **Added source context workspace** | A KRAS question, small graph, cited answer and preserved native STRING source record | 9,724 entities and 19,310 source records. The manual question shows 14 candidate result proteins. The added physical source has 330 qualified pairs: 243 already represented in the Pharos capture and 87 absent there. Native GO adds 3,309 records describing 429 protein-location concepts across 94 targets. Additional rows are not automatically independent experiments or accepted claims. |
| **Qualified Pharos workspace** | Choose **Review applied graph qualifications** for a TP53 pathway question using the graph after explicit decisions | Its own 16,985 input records become 16,687 retained records. The 298 excluded records have obsolete GO identifiers in the pinned ontology. All original rows and decisions remain recoverable; 11,636 undecided records stay retained. This is identifier qualification, not 298 experimentally disproved biological links. |

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

The challenge's central goal is **democratization**: scientists should be able
to use agents to build knowledge graphs without being KG specialists. BioGraph
Steward addresses this through guided questions, readable answers and source
inspection. Reusable cohort construction, several supported question types,
portable software and preserved source packets support use beyond one saved
answer. A separate [APP/PSEN example](evaluations/GENERALIZATION_EXAMPLE_20261117.md)
constructs and inspects three proteins outside the original 99. Its recorded
APP location-agent result and unchanged source-view comparisons demonstrate
workflow reuse. Reference coverage is small, and no new accuracy gain or broad
disease-transfer claim is inferred.

The organizer brief assigns the following weights and permits autonomous
**or semi-autonomous** software. This is our evidence map, not an official score.

| Criterion | Visible demonstration | Evidence and boundary |
|---|---|---|
| **Usability (40%)** | Question, agent plan, tool execution, inspected sources and proposed decisions | A scientist can follow a recorded model run to a cited answer without graph syntax. Four sequential steps, readable source records and export explanations make the workflow accessible. An independent usability study would test this designed benefit. |
| **Accuracy & pruning (30%)** | Applied qualifications and controlled source/reference comparisons | Exclusions of 298 records with obsolete GO identifiers are applied and reversible. Location references measure added support. The separate source-verifier comparison preserves adverse supported-claim exclusions under a partial Evidence-input view. It is not adopted as automatic Pharos pruning. |
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

The agent orchestrates actual source tools and inspections. In the
[frozen development comparison](evaluations/SOURCE_AGENT_RESULTS_20261116.md),
four nonempty queries and one valid accepted-only empty query preserved the
deterministic tool's complete query, answer and focused graph. Three unsupported
or unresolved requests stopped at preflight without calling the model:
pull-down binding, TP53 localization specifically in colon tissue, and a protein
outside the saved cohort. Those requests need assay, tissue or cohort support
absent from the available tool contract. These results establish bounded tool
execution and source fidelity. The guard results
do not establish learned model refusal. The linked comparison preserves the
exact source, tool-choice and result-limit controls.

Captured Pharos alone lacks these separately attached native-source contracts;
that is a source-availability distinction, not a biological-error label.
Agent and deterministic execution use the same fixed sources and result caps.
Neither changes the source graph or learner inputs, so this comparison measures
source fidelity and workflow execution rather than prediction improvement.

The separate public-reference assessment measures information recovered by
the source views:

- **Known protein locations:** only 31 of the 99 targets match the published
  human location reference, supplying 51 positive protein-location labels. The captured Pharos
  view recovers 41 of 51 positive reference labels; qualified native annotations
  recover 44 of 51. These fixed source views are not a newly scored union of the
  full integrated graph. The additional admitted location annotations supply
  the gain under the same ontology mapping; obsolete-ID exclusions alone do
  not improve recovery. The coarse-map control also recovers 44 labels, with
  more truth-unknown outputs. The other 68 targets lack matching reference
  labels. Both the reference and some added annotations reuse Human Protein
  Atlas observations, so agreement is not fully independent experimental support.
- **OpenCell source-exclusion check:** among 23 matching proteins, positive
  label recovery changes 30 of 40 to 31 of 40. The gain remains after the stated
  HPA/OpenCell source exclusions. This already-exposed reference is a
  sensitivity check, not new blind validation or a new biological discovery.
- **Additional biological-process function recovery:** a separate historical
  20,412-protein graph supports three parallel fixed arms: retained LocalPlus,
  refreshed LocalPlus and the context model. LocalPlus is the published
  positive-only weighted transfer of known GO labels from direct network
  neighbors ([Law, Kale and Murali, 2021](https://doi.org/10.1093/bioinformatics/btaa885)); we reuse the authors' implementation on this human network.
  The primary timepoint-ontology view gives ordinary micro-Fmax **0.055,
  0.059 and 0.073** across 1,954 proteins with 3,254 positive protein–GO pairs.
  The fixed-starting-ontology sensitivity view gives **0.172, 0.183 and 0.210**
  across 319 proteins with 3,243 positive pairs. Micro-Fmax pools annotation
  decisions and summarizes the best precision–recall balance across the declared
  thresholds, rather than percentage accuracy. The different populations
  prevent direct comparison of absolute scores between views. We reused
  [**ProtBoost**](https://arxiv.org/abs/2412.04529) and the authors' CAFA6 update to combine graph and sequence
  forecasts with GO evidence-code, relation and ontology context. These are
  qualified views of one GOA source. Context improves over retained LocalPlus
  in both views; its extra benefit over the refreshed arm remains uncertain.
  Stronger direct-annotation controls and unfavorable results are retained.

Positive-reference recovery counts known labels found by a view. Unmatched
proteins and unreported labels remain unknown, so these results do not identify
the fraction of the full graph that is biologically correct. See the
[public-reference result](evaluations/PUBLIC_GOLD_REFERENCE_RESULTS_20261115.md),
[applied qualification result](evaluations/SOURCE_FAITHFUL_WORKSPACE_20261113.md)
and [fixed function comparison](evaluations/CONTEXTUAL_COMBINATION_RESULTS_20261115.md)
for complete scopes, controls and denominators. The [forecast coverage note](evaluations/final_delivery_20261117/prediction_coverage_feasibility.md)
explains that all 3,300 eligible temporal-gainer proteins were forecast: 3,297
in the historical graph and three retained outside it. Further temporal testing
requires later labels.

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
The interactive constructor accepts 1–25 selected proteins per request; this
is its current request limit, not a limit on saved-graph size. Pharos GO
annotations in all three aspects remain available. The additional native GO
reader currently qualifies positive cellular-location records. Native process
and function extensions need their own relation, overlap and reference checks.
Three additional fixed questions also completed through the existing engines:
EGFR physical partners, TP53 native location records and BRAF archived pathway
context. This [applicability check](evaluations/VARIED_QUESTION_CHECK_20261115.md)
preserves source distinctions, result caps and empty accepted-only views. It
tests reusable execution within the same cohort, separately from scientific accuracy.
The public site is a **saved-workflow demonstration**:
fresh construction, retrieval, model calls and review edits are disabled there.
Manual questions open an overview of all returned results, with explicit drawing
limits. The KRAS overview shows 14 partners, 15 entities and 14 cited connections.
The summary's **Show in graph** action focuses an individual result, while
**Show all results** restores the overview. **Browse saved workspace** opens
the bounded workspace graph and complete source tables. Searchable start and
reachable-end suggestions, together with three connected-path examples, make
recorded interaction, location and pathway relationships easier to inspect.
**Results & evaluation** introduces the qualifications and separate scientific
comparisons. Expanding a summary result only opens its text.

In an editable local workspace, **Inspect sources → Record evidence review**
opens the reviewer, decision and reason fields. **Save review in a new run**
creates a reviewed copy and preserves the original sources and earlier run.
The public native KRAS workspace offers **Download an editable local copy**.
Its complete ZIP includes the app, exact saved graph, attached sources, saved
question, recorded agent job and `START_EDITABLE_LOCAL.py`. The launcher opens
a free loopback port. Python 3.10+ is sufficient for saved replay and reviews,
with no model, GPU, AWS account or new source retrieval. Editing records
source-review decisions and reasons rather than arbitrary node-and-edge edits.
The separate APP/PSEN example also supports this workflow. A saved agent proposal
remains separate from a scientist's recorded decision.

The [current-source agent](SOURCE_AGENT.md) uses up to three model calls:
propose a tool plan, prioritize returned citations for complete source
inspection, then select adapter-grounded review proposals. The application
validates the plan and preserves the deterministic cited answer. **Retain
candidate context** and **Needs review** change no assertion or local decision.
All selected citations retain every original source assertion, with explicit
inspection coverage; compact model context binds to the complete passports.

Method comparisons guide the delivered workflow. The literature auditor did
not outperform its specialist baseline, and same-learner link prediction did
not show consistent enrichment gains. These results support retaining explicit
source checks and human decision control. The
[research appendix](RESEARCH_APPENDIX_20261115.md) preserves the unsuccessful
approaches and stronger controls. Versioned snapshots and guarded comparisons
support maintenance. Unattended literature monitoring is outside this scope.

The [source-verifier comparison](evaluations/SOURCE_VERIFIER_COMPARISON_20261117.md)
also preserves unfavorable outcomes. Disconfirm scored lower than base under the
partial Evidence-input view, and supported claims were wrongly excluded. The
input-completeness correction is documented separately from the frozen results.
No current application assertion carries the complete native INDRA inputs
required by this verifier.

## Reuse and handoff

The judge-facing [final handoff](DELIVERY.md#final-submission-folder), prepared
locally at `output/final_submission/`, has five files:
**START_HERE.txt**, **BioGraph_Steward_Project_Report.pdf**,
**BioGraph_Steward_Demonstration.mp4**, **BioGraph_Steward_Overview.pptx** and
**BioGraph_Steward_App_Data_and_Exports.zip**. It excludes historical media,
internal review guides and the old combined submission archive. The data ZIP
is a private organizer handoff under the included source terms, not a blanket
public-data release.

The [project report PDF](../output/pdf/BioGraph_Steward_Final_Report.pdf)
([Word copy](../output/docx/BioGraph_Steward_Final_Report.docx))
explains the scientific problem, implemented approach, agent workflow, source
qualification, measured results and reusable deliverables. It distinguishes
CIViC clinical evidence inspection, native-source gains, the separate ProtBoost
prediction study and the source-verifier research comparison. The linked
research reports preserve all controls and denominators. The
[code-only software ZIP](../output/software/BioGraph_Steward_Software.zip)
reuses [clean core acceptance](evaluations/democratization_delivery_20261116/software_acceptance.json)
with [verified interface and packaging updates](evaluations/usability_delivery_20261117/packaging.json).
The [delivery status](DELIVERY_STATUS_20261115.json) records exact software,
deployment and artifact identities. [Public HTTPS](evaluations/usability_delivery_20261117/hosted_acceptance.json)
and [browser evidence](evaluations/usability_delivery_20261117/hosted_browser.json)
document the saved-demo mode. These are functional checks, separate from an
independent usability study.

The native KRAS complete-copy download includes its candidate graph, preserved
attached sources, saved question, S01 agent record and runnable local software.
Its [delivery verification](evaluations/editable_demo_copy_20261117/README.md)
checks exact original bytes and saving a personal review in a new run. It does
not copy hosted assessment pages, optional global GO/QC inspector data or the
private Neptune mirror. The final data ZIP combines this complete primary
app/source copy with graph, decision-ledger and matched-baseline inspection
exports. Those include all 19,310 primary undecided verdicts, the exact
same-snapshot Pharos-only comparator, and the Qualified Pharos graph with its
own original input and every decision. These inspection exports are not a
complete qualified source-recovery packet. That full packet remains a separate
optional replay asset under the [source-access instructions](GOLD_SET_INTERFACE.md#protected-downloads).
All primary records remain scientifically unassessed. The small answer diagram
and focused answer ZIP are separate views. Original and retained graphs stay
distinguishable, and unresolved records remain available.

The verified agent-record download preserves its question, plan, model/tool
trace, source inspections and proposals. It replays beside the original source
workspace; that small record does not silently include the full source packet.

- [Code and build instructions](../START_HERE.md): MIT software with a local
  synthetic demonstration, explicitly labeled as invented data.
- **Download an editable local copy** in the public native KRAS workspace:
  its complete app/source/graph/question/job ZIP, with **OPEN_WORKSPACE** and
  `START_EDITABLE_LOCAL.py` for personal reviews saved as new runs.
- The separately supplied `BioGraph_Steward_APP_PSEN_Example.zip`: a complete
  real-data local runtime, saved APP location-agent job and full source records.
  Its **OPEN_EXAMPLE.txt** selects the recorded location workflow directly.
- The separate `BioGraph_Steward_Source_Verifier_Code.zip` research adjunct:
  code and **README_REPRODUCTION.txt**, requiring a matching checkout, optional
  runtime and separately licensed pinned inputs. Raw reference cases and model
  outputs are not included.
- [Delivery and source-access instructions](DELIVERY.md): tested code release,
  public saved examples and separate source packets under their own terms.
- [Standard export](STANDARD_EXPORT.md) and [mapping/overlap audit](EVIDENCE_OVERLAP.md):
  declared vocabularies, admitted mappings and known compatibility limits.
- [Submission overview](SUBMISSION_OVERVIEW.md) and
  [delivery record](evaluations/DELIVERY_COMPLETENESS_20261115.md): implementation
  scope and reproducible handoff evidence.
- [Preserved research appendix](RESEARCH_APPENDIX_20261115.md): the former long
  narrative, retained verbatim with historical experiments and their outcomes.
  It is supporting evidence, not the app's primary navigation.

Project repository: [github.com/mdomagalski/biograph-steward](https://github.com/mdomagalski/biograph-steward).
Software licensing does not relicense upstream data.
The full graph, ledger, baseline and comparator are separate submission or
authorized operator assets. The public demo offers the recorded-agent JSON
and one prepared complete native KRAS workspace copy for local review. Source
terms and attributions travel with that copy; local reviews do not alter the
shared example.
