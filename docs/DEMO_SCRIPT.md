# BioGraph Steward demonstration

Use the **[step-by-step user guide](../HOW_TO_USE.md)** and
[judge evidence route](JUDGE_WALKTHROUGH.md). Its central
task follows an actual recorded Nemotron run: a research question, validated
source query, cited evidence, complete source inspection and grounded review
proposals. The reviewer can then inspect the applied graph qualifications and
measured reference result.

Introduce **one application with two saved examples**: **Added source context
workspace** for the KRAS/source-addition story, and **Qualified Pharos
workspace**, opened through **Review applied graph qualifications**, for the
applied identifier decisions. Each preserves its own input and exports. The
historical function-prediction study is a separate research assessment, not a
third app version.

Explain why both examples appear before switching between them: the common
workflow is **open or build a source workspace → ask a supported question →
inspect its graph, cited answer and sources → save a review in a new run →
export**. KRAS demonstrates additional evidence and source inspection; the
qualified example demonstrates recorded decisions and the retained graph.
The source-reference and prediction results assess the approach separately.
They are not different applications or studies that users must run to ask a question.

**Lead with the improvement.** Qualified native sources add **87 physical
association pairs** and **68 protein–location concepts** absent from the captured
Pharos annotations. Show one actual addition before explaining tool mechanics:
**E002, KRAS–CDC42BPB**. Its saved source passport explicitly records
**baseline pair present: false**, native STRING 12.5 score **203/1000** and the
identity checks. The [saved-artifact audit](evaluations/source_agent_20261116/demonstrated_additions.json)
separates additions from overlapping pairs and source rows.

The recorded run uses four small steps: **Question & plan**, **Evidence graph**,
**Source inspection** and **Review proposals**. Continue buttons keep one
step visible at a time.

The current-source agent has completed its
[fixed development comparison](evaluations/SOURCE_AGENT_RESULTS_20261116.md).
The current tour demonstrates the actual local application using verified saved
real data. The public site replays the recorded agent workflow, with
[hosted acceptance](evaluations/delivery_readiness_20261116/hosted_acceptance.json)
and the exact [delivery status](DELIVERY_STATUS_20261115.json) recorded separately.

Open the
[public app](https://bi-3a117d5e2b3942678dc518fce65ab5d2.ecs.us-east-2.on.aws/)
without signing in and follow the designated recorded agent run.
The shared session replays genuine saved model work. It does not call a model,
retrieve new source data or apply review decisions during the demonstration.

The primary agent answer displays eight of 14 matching KRAS partners under its
recorded cap. The older manual answer displays all 14 under a different cap.
The agent's citation priorities preserve the complete returned answer.
**Retain candidate context** and **Needs review** are proposals, not acceptance
or graph edits.

In the separate manual KRAS question, start with the overview of all 14 partners
(15 entities and 14 cited connections). Select **Show in graph** on one result
to inspect its pair, then **Show all results** to restore the overview.
**Browse saved workspace** opens the existing bounded graph and full source
tables, rather than drawing all 9,724 workspace entities at once.

Open **Explore paths in this saved graph** and type **KRAS** in the start search.
Start suggestions are sorted proteins first, and the independent end search
offers connected entities within the selected bounds. Run the one-click
**KRAS → CDC42BPB** example to show its interaction annotation. The other
one-hop examples show **TP53 → nucleus** as a location annotation and
**BRAF → ARMS-mediated activation** as pathway membership. Keep the
**Candidates and accepted** scope visible. These paths preserve recorded
relationship meanings; an empty filtered search does not demonstrate biological
absence. **Results & evaluation** introduces the qualifications and measured
comparisons for a first-time reader.

Show the measured outcomes early: the qualified location view recovers
**44/51** positive labels versus **41/51** for the captured Pharos view under
the same mapping, and OpenCell recovery changes **30/40 → 31/40**. Keep the
complete comparison table, including its coarser-mapping control, visible.

The separate [historical function study](evaluations/CONTEXTUAL_COMBINATION_RESULTS_20261115.md)
also has a positive result. Lead with its **primary timepoint-ontology view**:
ordinary micro-Fmax is **0.055** for retained LocalPlus, **0.059** for refreshed
LocalPlus and **0.073** for the context model. Then identify the
fixed-starting-ontology sensitivity check: **0.172, 0.183 and 0.210**.
The primary scores cover 1,954 proteins and 3,254 positive protein–GO pairs;
the sensitivity scores cover 319 proteins and 3,243 pairs. Do not compare the
absolute values across these different populations.

LocalPlus transfers known GO labels from direct weighted network neighbors,
using the published positive-only implementation
([Law, Kale and Murali, 2021](https://doi.org/10.1093/bioinformatics/btaa885)).
Micro-Fmax measures the best pooled precision–recall balance across the declared
thresholds, rather than percentage accuracy. These are three parallel fixed
arms. The context model improves over retained LocalPlus in both views, while
its extra benefit over refreshed annotations remains uncertain. Label this
scene **separate historical 20,412-protein study** and the visual as a rendering
of the saved scientific report. These are prediction-method results, separate
from agent orchestration and the 99-target app.

Then show how the agent makes source investigation usable, the applied
298 obsolete-ID qualifications and recoverable exports. Put the essential
interpretation boundaries together once: defined reference frames, source
sharing/prior reference use, candidate physical associations and the uncertain
extra primary learning gain over fully refreshed annotations. Finish with what
a researcher can inspect and reuse. Show **Download an editable local copy**
and explain that a local evidence review saves a new run with its reviewer,
decision and reason while preserving the original. Saved replay and reviews
need no Brev instance; only new live agent questions need a configured model.

The final judge folder contains **START_HERE.txt**, the report PDF, narrated
demonstration, slides and **BioGraph_Steward_App_Data_and_Exports.zip**. The
private data ZIP supplies the complete KRAS app/source copy and graph/ledger
inspection exports for both examples under their source terms. The full
Qualified Pharos source-recovery packet remains an optional separate replay
asset. [Delivery scope](DELIVERY.md#final-submission-folder) identifies these files.

The [narrated tour](../output/walkthrough/BioGraph_Steward_Walkthrough.mp4)
and [transcript](../output/walkthrough/BioGraph_Steward_Walkthrough.txt) provide
the current recorded presentation. It uses actual browser screenshot states,
including the saved aggregate report, with focused crops and synthetic narration.
One separately labelled visual renders the existing prediction result tables;
it is not app UI or a new experiment.
It is not a continuous recording or a new live model run. Earlier media stays
in the [dated history](../output/history/20261115_guided_review/README.md).

For the scoring map and limits, use the [submission summary](FINAL_SUBMISSION.md).
Detailed method history remains in the [research appendix](RESEARCH_APPENDIX_20261115.md).
The invented local software fixture is a separate test route and supplies no
biological result.
