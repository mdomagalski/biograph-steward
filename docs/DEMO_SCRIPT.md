# Five-minute challenge demonstration

Use the [portable CRC package](DELIVERY.md) only where source access and use are
authorized. Otherwise use the software-only synthetic walkthrough in
[START_HERE](../START_HERE.md), explicitly labeling its records as invented.
The [source-faithful workspace](evaluations/SOURCE_FAITHFUL_WORKSPACE_20261113.md)
is the current delivery example when its separately supplied packet is
available. No model or GPU is needed for saved-data questions. A private AWS
deployment additionally needs its existing authorized Session Manager tunnel.
The checkout also includes a [CC0 Reactome example](../examples/reactome_context_20261113/README.md)
with an offline viewer and exact native records. This is a separate current
source-inspection example, not the complete Pharos graph or its historical
baseline. The [delivery index](releases/20261113/README.md) identifies which
software, data and assessment are actually supplied.

The private AWS app now uses tested code `0529d2b`; its
[update receipt](evaluations/hosted_polish_update_20261113_summary.json) verifies
the existing saved question and native exports after a real restart, with
complete Neptune parity and read-only database access. The earlier private
combined archive remains pinned to `902699e`.

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
4. **Present the assessment — one minute.** In **Compare & assess**, open the
   supplied scientific assessment. Show compatible experimental GO curation
   at 373/4,078 original assertions and CRC cohort support at 32/100 disease
   assertions, with UNKNOWNs retained. These are coverage measurements. Show
   the [128-gene transfer figure](evaluations/PROSPECTIVE_GENE_TRANSFER_20261113.md)
   and state that the fixed views did not beat the baseline and all controls.
   No automatic biological-pruning policy was promoted. Full methods and
   earlier bounded results remain in the receipts; these are not official
   challenge scores.
5. **Show the handoff — one minute.** In **Export**, download the complete
   workspace ZIP. The answer diagram is a question-specific view; the workspace
   retains 16,687 evidence rows. Locate `source_retained_package/retained_graph.json`,
   `edge_dispositions.jsonl` beside it and the preserved `baseline_packet`.
   All abstained rows stay retained. The 298 excluded rows use obsolete GO
   identifiers in the pinned ontology; they are not 298 proven biological errors.
   Native source terms remain separate from the MIT software license.

The existing `crc_judge_demo` route and SIGNOR BRAF-site explanation remain
supplementary demonstrations. The refreshed scientific results should take
precedence over earlier presentation snapshots until those slides are updated.

For a question about claim verification, use the separate
[expert-grounding result](evaluations/EXPERT_GROUNDING_20261113.md). Its saved
publication `scientific_assessment_delivery_20261113` is now installed and
API-verified in the private AWS app. A fresh checkout does not contain that
separately supplied publication. On 678 eligible
expert-labeled source cases, publication context reduces false alarms 25→18
but true error flags 31→26. It supports assisted review, with unresolved cases
visible; it does not validate or automatically prune the Pharos graph.
This v3 publication also retains the earlier 92-query/3,968-pair exploratory
comparison. Present the separately reported negative 128-gene/7,648-pair
transfer above alongside it. The native GO web-inspection/QC follow-up is
local-only and is not part of hosted `0529d2b`.

The [existing checkpoint recovery](evaluations/aws_isolated_recovery_20261113_summary.json)
also passed exact graph, saved-answer and export replay without changing the
live service. Its scope is the older graph/assessment/question checkpoint,
not full VM recovery or the later grounding/software artifacts.

The private AWS/Neptune mirror and [NVIDIA integration](NVIDIA_INTEGRATION_STATUS_20261113.md)
can be described in questions. Saved-data inspection uses CPU only; the Brev
model can stay off. These supporting capabilities do not establish biological
improvement. Use the current delivery index and hosted update receipt for the
latest status. The existing three-page PDF predates this hosted update; the
older editable slide deck also remains a separate artifact until updated.
