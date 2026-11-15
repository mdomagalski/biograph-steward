# Five-minute challenge demonstration

For the independent weekend teammate review, use the
[testing guide](TEAM_REVIEW_GUIDE_20261113.md) and its
[PDF](../output/pdf/BioGraph_Steward_Team_Review_Guide_20261115.pdf).
This page is the shorter presentation script.

Use the [portable CRC package](DELIVERY.md) only where source access and use are
authorized. Otherwise use the software-only synthetic walkthrough in
[START_HERE](../START_HERE.md), explicitly labeling its records as invented.
The [source-faithful workspace](evaluations/SOURCE_FAITHFUL_WORKSPACE_20261113.md)
is the current delivery example when its separately supplied packet is
available. No model or GPU is needed for saved-data questions. The
[shared reviewer example](https://bi-3a117d5e2b3942678dc518fce65ab5d2.ecs.us-east-2.on.aws/?run=source_faithful_workspace_20261113&question=question_20261113T075313Z_1a76b00f&view=ask)
uses a browser and separately supplied workspace token. Operators can still use
the authorized private Session Manager route.
The checkout also includes a [CC0 Reactome example](../examples/reactome_context_20261113/README.md)
with an offline viewer and exact native records. This is a separate current
source-inspection example, not the complete Pharos graph or its historical
baseline. The [current software index](releases/20261115/README.md) and
[preserved data index](releases/20261113/README.md) distinguish the supplied
software, research and mixed-source demonstration.

The accepted AWS runtime is `a6a05ff`, including the saved historical
function-context inspector: six queries and 36 traceable hypotheses. The
[November 14 results](evaluations/SCIENTIFIC_RESULTS_20261114.md) describe the
hosted scientific checkpoint. Select `scientific_assessment_reference_20261114` in
**Compare & assess**; its protected hosted API and source downloads passed acceptance.
The newer [standalone comparison](evaluations/contextual_combination_20261115/report.html)
is a separate repository/presentation artifact, summarized in the
[updated results note](evaluations/CONTEXTUAL_COMBINATION_RESULTS_20261115.md).
Open it in advance if presenting the latest scientific result; it is not yet
the hosted catalogue's assessment.
The separate [current-data refit](evaluations/CURRENT_REFIT_DEVELOPMENT_RESULTS_20261115.md)
is the completed development follow-up in presentation appendix 9. It does
not improve the original selected model and has not changed the hosted app.
Earlier delivery receipts and combined archives describe their own checkpoints.
Allow about 1–2 minutes for a cold load of the existing 99-target graph/answer.
The separate saved function queries respond in under a second on the tested
host; these are different tasks, not a direct speedup comparison.

1. **Open the question — one minute.** Open the supplied
   `source_faithful_workspace_20261113` run. In **Ask & explore**, choose
   **Qualified WikiPathways source context**, TP53 and eight results. Keep native
   support selected and find the source paths. The scope is 99 protein products
   from a frozen Pharos319 colorectal cohort. Candidate review status remains
   visible; an empty result never means biological absence.
2. **Follow the graph — one minute.** Select a TP53 path to AKT1 or ATM. Both
   proteins point to one exact cited pathway model. Explain that shared model
   context does not assert direct protein binding. Open the native source
   passport and distinguish a literal protein xref from a gene-level match.
   The original assertion IDs, evidence and review states remain accessible.
3. **Verify the source — one minute.** Inspect the full pathway version, archive
   and original GPML download. A current redirect is not the historical model.
   Model-wide references and element-attached references have different scope;
   a citation is not automatically evidence for every protein. Explain the
   recovered 253/308 exact revisions and the unresolved remainder. Five
   historically encoded connections excluded by a current-only view are kept.
4. **Present the measured result — one minute.** Switch to the preopened
   standalone report or slide 4 of the updated presentation. The fixed primary
   biological-process result improves over retained LocalPlus in both ontology
   views: **0.05473 → 0.07343** and **0.17155 → 0.21009**, with paired intervals
   above zero. Refreshing LocalPlus's annotations also helps. Extra learned
   benefit over fully updated LocalPlus is uncertain for primary biological
   process. Secondary molecular-function and cellular-component contrasts improve
   over LocalPlus, but direct nonexperimental GOA is not clearly beaten for MF
   and is better for CC. Fmax measures later curator-annotation recovery, not graph accuracy.
   All 3,300 forecasts preceded reference opening. Keep the earlier negative
   graph, pruning and agent results distinct. If staying entirely inside the
   hosted app, use its explicitly dated November 14 assessment and one saved
   function query instead; do not call it the new comparison. Follow a saved
   neighbor/source contribution as an explanation, never as accepted biology.
5. **Show the handoff — one minute.** In **Export**, download the complete
   workspace ZIP. The answer diagram is a question-specific view; the workspace
   retains 16,687 evidence rows. Locate `source_retained_package/retained_graph.json`,
   `edge_dispositions.jsonl` beside it and the preserved `baseline_packet`.
   All abstained rows stay retained. The 298 excluded rows use obsolete GO
   identifiers in the pinned ontology; they are not 298 proven biological errors.
   Native source terms remain separate from the MIT software license.

The existing `crc_judge_demo` route and SIGNOR BRAF-site explanation remain
supplementary demonstrations. The new standalone results and
[editable v4 presentation](../output/presentations/BioGraph_Steward_Challenge_Presentation_20261115_v4.pptx)
are the latest scientific handoff. The older negative 128-gene coessentiality transfer remains a separate
result, not a description of every subsequent transfer task.

For a question about claim verification, use the separate
[expert-grounding result](evaluations/EXPERT_GROUNDING_20261113.md). Its saved
publication `scientific_assessment_delivery_20261113` is now installed and
API-verified in the private AWS app. A fresh checkout does not contain that
separately supplied publication. On 678 eligible
expert-labeled source cases, publication context reduces false alarms 25→18
but true error flags 31→26. It supports assisted review, with unresolved cases
visible; it does not validate or automatically prune the Pharos graph.
This v3 publication also retains the earlier 92-query/3,968-pair exploratory
comparison. Retain its separately reported negative 128-gene/7,648-pair transfer when
discussing that earlier method; do not pool it with CAFA5 annotation recovery.

For a source-quality question, the hosted [native GO inspector](NATIVE_GO_CONTEXT_WORKBENCH.md)
is available on demand. In **Evidence & sources**, search `GO:0005794`, select
NRAS, open the source guide and inspect the preserved native GO annotations.
Show the original native `part_of` relation beside the recorded `located_in`
derivative. For NRAS/`GO:0070062`, distinguish a context warning from biological
falsity and note that no native row matches all five available Pharos fields.
Neither example changes the Pharos graph or accepts a claim. The source/QC packets
remain separate private data; a fresh code-only installation has neither.

The [existing checkpoint recovery](evaluations/aws_isolated_recovery_20261113_summary.json)
also passed exact graph, saved-answer and export replay without changing the
live service. Its scope is the older graph/assessment/question checkpoint,
not full VM recovery or the later grounding, native GO attachment and software
artifacts.

The private AWS/Neptune mirror and [NVIDIA integration](NVIDIA_INTEGRATION_STATUS_20261113.md)
can be described in questions. The instance and model server are unnecessary for saved-data review;
any separate research CPU jobs have their own recorded status. Keep the AWS reviewer
site available. Saved inspection needs no model calls or fresh retrieval.
Use the [current scientific results](evaluations/SCIENTIFIC_RESULTS_20261114.md)
and delivery receipts for scope; older PDFs/slides remain dated checkpoints
until replaced.

The [November 14 delivery receipt](evaluations/scientific_hosted_delivery_20261114_summary.json)
records a fresh native backup and isolated replay of the accepted workspace,
eight-answer question, final assessment, function inspector and native GO
attachment. It is checkpoint verification, not a VM/Neptune restore.
