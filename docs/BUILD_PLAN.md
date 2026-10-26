# Current build plan

Updated October 25, 2026. The active product is the source-traceable evidence workbench. Deterministic construction/publication, the bounded Lambourne assay-corroboration report and its standalone qualified observation publication are complete; study independence remains unresolved. The first bounded measured PPI comparison found no consistent incremental hierarchy benefit. Both assessed panels are consumed. Retired experiments and old next-step proposals are preserved in the [experiment archive](EXPERIMENT_HISTORY.md).

## Delivery sequence and completion criteria

The release target is one reproducible flow: a researcher supplies a bounded
question or protein cohort; the agent selects permitted retrieval tools;
deterministic code builds and publishes a qualified Pharos-based graph; the
researcher inspects a cited answer, source traces, review decisions and updates;
the same source-bound graph can be exported for evaluation.

The [deterministic construction/publication path](CONSTRUCTION.md) now accepts
1–25 exact protein accessions and publishes a graph, cited candidate answer and
source-bound export without a selected disease. It reuses the existing source
adapter and normalization. The current model planner still selects a read-only
query over a saved disease graph; agent-selected construction remains a separate
gap. Preserve the CRC/CIViC user demonstration; the PPI study is a
separate link-prediction component evaluation and does not validate oncology
treatment claims.

The [publication check](evaluations/CONSTRUCTION_PUBLICATION_20261023.md) records
a real three-protein graph, direct source traces on every evidence group,
offline reconstruction and a cited answer/export. It closes the deterministic
publication boundary, not agent-selected construction or biological validation.

The [reference/comparator decision](literature/REFERENCE_COMPARATOR_DECISION_20261025.md)
has now been executed as a [frozen Lambourne assay-corroboration report](evaluations/LAMBOURNE_CORROBORATION_20261025.md).
All 3,222 nominations remain accounted for; 2,676 are assay eligible and 2,674
comparator eligible. Detection is 334/1,966 (17.0%) among represented pairs and
42/708 (5.9%) among resolved no-matches. In the prespecified stratum without
observed HuRI/INMC pair overlap, rates are 74/1,619 (4.6%) and 16/650 (2.5%).
These are conditional assay-concordance results. Provider import releases and
study lineage could not be bound to deployed Pharos rows, so independence
remains unresolved and Steward improvement was not tested. The panel is now
consumed; no new predictive enrichment or protocol tuning may reuse it as unseen.
The [qualified assay evidence publication](ASSAY_EVIDENCE.md) is complete as a
standalone immutable layer and offline viewer: 3,222 observations, 2,676 qualified
edges and 3,173 protein nodes, with 546 excluded assays retained in the audit.
Its 42 detections without a bounded Pharos match are a filter over the complete
source collection. Study/construct context and nondetections remain explicit;
no Pharos record is pruned or automatically accepted. General attachment to
ordinary workbench runs is not yet implemented. The
[publication record](evaluations/ASSAY_EVIDENCE_PUBLICATION_20261025.md) establishes
source-preserving integration, not independently demonstrated prediction gain.

The [bounded standard export](STANDARD_EXPORT.md) preserves the complete source
bundle and exposes a Reactome projection with official KGX checks and a JSONL
round trip. This is qualified interoperability, not full Biolink conformance:
the checked upstream category-array schema and `participates_in` domain issues
remain explicit. Resolving those mappings must not silently change biological
meaning or remove the source qualifications.

| Order | Deliverable | Completion evidence |
|---|---|---|
| 1 | One bounded construction/publication flow using current adapters | Deterministic path complete: a declared exact-protein request reaches retrieval, normalization, an inspectable saved graph and a cited answer/export. Calls, budgets, identities, qualifications and exclusions are recorded. Agent-selected construction remains separate. |
| 2 | A finite reference and comparator decision | Decision complete: use the frozen full-panel Pharos presence comparator for retrospective Lambourne assay corroboration, with unresolved source lineage. No-go for a new predictive enrichment comparison until an additional information source/change is justified independently of these outcomes. |
| 3 | Frozen biological assessment, then conditional matched improvement testing | Lambourne baseline corroboration complete: author-consistent adapter, eligibility, full candidate inventory, strata and report frozen before outcome decoding; all 3,222 pairs reconcile. This is not an improvement test and the panel is consumed. A future enrichment test must separately fix exclusions, projections, development/test boundaries, metrics, dependence treatment, seeds and budget; use matched learners/candidates and a simple-addition control. Preserve results even without gain. |
| 4 | Tested filtering, maintenance and exchange | Check controlled identifier/context/citation corruptions and source changes; report false removals, abstentions and update errors. Preserve reversible decisions. Validate the chosen vocabulary/schema/export subset using existing tools; controlled cases establish engineering behavior, not broad scientific truth. Use the organizer reference for its actual task once supplied. |
| 5 | A reproducible, usable submission | Another person can install, replay a saved example, build a bounded graph, trace an answer, inspect a change and export it. Record task completion/errors/time with intended users. Include dependency/source/license manifests, graph artifacts, methods, results, limitations and a short demo. |

The deterministic publication boundary, finite reference decision and bounded
assay-corroboration report and standalone observation publication are now complete. Missing organizer labels or complete
study lineage do not block product integration, qualified standard validation or replay. The
official gold artifact, label meanings and scoring contract remain external
dependencies; the local handoff is already implemented.

**Decision limits:** no scientific improvement is promised by this plan. The
specific enrichment that adds useful information beyond Pharos remains
unselected. The lineage audit is closed with an unresolved result and the study
is classified as retrospective corroboration. Reopen independence only with
deployment-specific import/evidence metadata. Do not repeatedly switch references
or add sources/models until a score improves. A valid negative result completes
an evaluation deliverable but does not satisfy the predictive-improvement
objective. Investigate its implications on development material; consumed tests
stay consumed. Human-reviewed or curated evidence is still needed for claims
that exceed the mechanical checks and the selected assay endpoint.

The core architecture does not need replacement. Remaining framework design is
concentrated in three boundaries: agent selection of permitted construction
tools against the deterministic baseline; a cohort-compatible maintenance and
evidence-action policy; and qualified standard mappings with explicit treatment
of unresolved validation findings. Biological acceptance criteria, actual-user
testing and submission packaging remain work as well. AWS, a new graph store
and more agents are conditional choices, not prerequisites. The completed
assay assessment ran locally; any later Brev-dependent test will be announced first.

## Gap closure and biological validation

The [October 25 literature follow-up](LITERATURE_REVIEW.md) supports the current
design direction, not a claim that the implementation improves scientific
accuracy. The following are concrete closure criteria rather than a request
for another framework redesign:

| Boundary | Work under our control | Completion evidence or external limit |
|---|---|---|
| Agent-selected construction | Reuse the existing planner and construction tools with fixed profiles, exact identities, budgets and abstention | On a frozen request set, compare supported scope/tool selection, resulting graph, provenance, cost and failures against deterministic execution; announce before the live model run |
| Explicit-cohort maintenance | Extend the existing snapshot/review rules to cohort graphs; retain source changes and reversible decisions | Controlled changes in identity, context, evidence and source withdrawal are detected; incompatible reviews do not carry over; missing or old evidence is not silently declared biologically false |
| Qualified exchange | Maintain the audited subset and source-preserving ledgers; extend only documented semantic mappings | Exact roundtrip and appropriate upstream checks pass for every claimed profile; full conformance remains dependent on resolution of the recorded model/schema constraints and adequate source semantics |
| Bounded biological assessment | Complete: tested author-consistent assay adapter, frozen eligibility and full-panel Pharos comparator, one assessment and offline replay | All 3,222 nominations reconcile; 2,676 assay eligible, 2,674 comparator eligible. Detection/nondetection, failures, unresolved identities and exposure strata are recorded. This is retrospective assay concordance, not general Pharos accuracy or an improvement effect; the panel is consumed |
| Independent improvement claim | Select a specific biological change before examining a fresh evaluation; match inputs, task and learner controls | Requires defensible source/reference separation and relevant labels. Adding information needs a simple-addition control. Missing deployed source lineage and the organizer gold contract cannot be manufactured by code |

The baseline biological assessment completed before agent construction,
maintenance and wider standards mapping, without a new model, GPU or laboratory
experiment. Published experimental outcomes support that bounded question;
they cannot establish treatment validity or prove that all graph relations are
true. The standalone qualified evidence publication exposes the observations and their
limitations, but cannot be evaluated as an improvement using these same consumed
outcomes. Broader claims require their own suitable reference
and, where the task cannot be mechanically scored, qualified domain review.
Researcher-task usefulness remains a separate acceptance test.

## Priority after the organizer clarification

The [Slack excerpts supplied October 23](PROJECT_ALIGNMENT.md#organizer-clarifications-supplied-october-23)
mention a Pharos gold set but do not supply its artifact, baseline release,
label semantics or scoring contract. Resolve that interface before treating the
INMC/GO study as the submission's principal benchmark. Gold-based pruning and
measured link prediction may require different references; neither establishes
general biomedical correctness.

The [local reference handoff](GOLD_SET_INTERFACE.md) is now implemented: strict
saved-run export, portable source-bound inventories, explicit dispositions and
exact reference alignment. Labels remain opaque and no official score is
computed. Completing the official adapter still requires the actual artifact
and its documentation; no reserved biological outcomes were used for this work.

Preserve the prepared sources, frozen comparison and consumed-holdout boundary.
The deterministic product boundary now includes bounded construction through
existing adapters, graph publication, traceable exports and replay. While the
organizer interface remains unknown, complete the remaining agent, maintenance,
qualified-standard and user-task checks. A small tested
PyTorch Geometric export/subgraph adapter can address the organizer's stated
preference without replacing the learner. Do not expand cloud infrastructure,
model variants or source integrations solely to occupy this gap.

The scientific sequence below records the completed supporting study. Its
source audits and exclusions remain useful independently of the official
evaluation. The [measured result](evaluations/INMC_COMPARISON_20261023.md) is
task-specific and cannot replace the missing organizer reference.

## Current product

Maintain the guided question → evidence graph → cited answer → source-passport flow, complete molecular-profile/therapy context, explicit source and display coverage, local reviews and saved-version comparison. The optional planner may select a bounded read-only query; it does not accept or prune graph assertions.

Source fidelity, usability, claim verification and biological prediction have different evaluation targets. The workbench's structural checks and source preservation do not establish scientific accuracy. Keep that distinction in the app, exports and progress report.

## Completed scientific increment and next boundary

The [reuse review](literature/MEASURED_LINK_BENCHMARK_REUSE_20261022.md) selects the INMC experimentally tested protein-pair panel for preparation with PyKEEN R-GCN and simpler controls. The [input audit](evaluations/INMC_INPUT_READINESS_20261022.md) and [assay/identity follow-up](evaluations/INMC_READINESS_FOLLOWUP_20261022.md) established:

- 3,276 candidate pairs, including 495 self-pairs that need separate treatment; all 1,805 genes occur in the released training network and no candidate pair is a training edge.
- 1,801 exact HGNC gene mappings; 1,800 genes have confirmed reviewed context across 1,797 accessions. Shared and multiple products remain explicit, and five original gene nodes lack frozen-registry product context.
- The old CRC pull directly covered only 43 panel genes. The [new uniform bounded pull](evaluations/INMC_PHAROS_UNIFORM_20261022.md) resolves 1,794 accessions and covers 1,798 original genes. One expression cap and seven genes without resolved Pharos context remain explicit.
- The raw/retained source audit identified 277 reserved off-diagonal gene pairs already represented in Pharos interactions. The prepared learner graphs now exclude all Pharos interactions, including those exposures.
- An author-provided positive reference and a declared, narrower complete-scored assay subset. Partial-failure semantics remain unresolved and are excluded symmetrically from the primary endpoint. The initial audits generated no binary labels or predictions; the later frozen comparison did.

The completed sequence and its preserved constraints are:

1. **Assay interpretation is bounded.** Preserve the [declared contract](evaluations/inmc_assay_contract_20261022.json): all three scores must be definitive, any positive denotes detection, all negative denotes nondetection under these assays. Do not reinterpret failed/unscored tests or change eligibility after results. Materialization occurred only after the full comparison freeze and all predictions completed; all 2,038 complete-scored pairs reconciled with the author reference.
2. **Identity exceptions are documented.** Preserve original gene nodes, shared products and unresolved context gaps. Historical/current external links remain recorded candidates rather than silent replacements; they do not establish assay-construct identity.
3. **Uniform source staging is complete.** The 72 immutable chunks preserve the frozen inventory, all-tissue expression within caps and global PPI cohort. This is GraphQL `pharos319`, not a complete current Pharos release or a published workbench graph. Keep cap/version/identity gaps visible; they must not remove test pairs.
4. **Paired graph construction is complete.** The [prepared graph report](evaluations/INMC_PAIRED_GRAPH_20261023.md) records 10,350 shared nodes, 2,570 retained Pharos annotation pairs and exactly 315 added GO `is_a` edges. Both arms apply the same conservative exclusions; 37 initially eligible rows are removed for unresolved GOA diagnostic qualifications. Original genes, missing context, isolated nodes and all nominations remain explicit. Current-GOA protein annotations and all Pharos PPI stay outside learner inputs. Reserved/development identities and their transitive product equivalents are masked. Unknown references/polarity prevent complete derivative-evidence exclusion; this is retrospective, not independent temporal validation.
5. **Matched comparison completed.** After the native path/resource checks and graph/runner/scorer/runtime freeze, all four arms × three seeds completed the fixed 20-epoch budget locally, without HPO or early stopping. On 1,751 primary pairs, mean AP was 0.719833 without hierarchy and 0.720135 with it; seed differences were mixed. No consistent hierarchy benefit is demonstrated. Standard AP/ROC-AUC, coverage and descriptive gene-removal influence are recorded in the [result](evaluations/INMC_COMPARISON_20261023.md). This panel is now consumed and cannot be reused as unseen validation after tuning.

Next, include the measured result and limitations in the progress report, review
source coverage and reusable-method fit on development material, and obtain the
organizer reference when available. Do not start another source/model variation
on this test panel as though it were fresh. Any new improvement claim needs a
separately justified protocol and independent reference. Product construction,
qualified interoperability and user-task validation remain distinct work below.

The [external human panel lookup](evaluations/LAMBOURNE_PHAROS_LOOKUP_20261023.md)
now covers all 3,173 requested author accessions (3,172 exact resolutions).
It identifies 2,325/3,222 nominations already represented in Pharos, preserving
all prior exposure flags and unresolved identities. The
[closed reference decision](literature/REFERENCE_COMPARATOR_DECISION_20261025.md)
uses this lookup as the fixed presence comparator, preserving its 895 bounded
no-matches and two unresolved pairs. The [completed assay report](evaluations/LAMBOURNE_CORROBORATION_20261025.md)
reconciles all nominated raw and published outcomes after the adapter/protocol
freeze. Source independence remains unverified and this panel is consumed.
The [completed observation publication](ASSAY_EVIDENCE.md) retains nondetections,
failures and full assay context in a standalone layer and offline viewer.
It leaves original Pharos records intact and does not expose these observations
as unqualified interaction paths. General attachment to ordinary workbench runs
remains separate. This panel must not serve as unseen evaluation after prediction,
enrichment or protocol tuning. No new model run is selected; the remaining
product boundaries are bounded agent construction, cohort maintenance, qualified
exchange and usability.

PyKEEN runtime checks on Nations, the [invented context/supervision smoke](evaluations/PYKEEN_CONTEXT_SMOKE_20261022.md), and the three-layer hierarchy probe passed. Reproduced pinned-runtime issues use supported ordinary batching and the native disabled-dropout branch; the [graph report](evaluations/INMC_PAIRED_GRAPH_20261023.md) explains why. These checks establish implementation behavior, not biomedical accuracy or GPU capacity. Tell the user when a concrete run requires Brev; its language-model server is unnecessary for this graph learner.

## Remaining challenge functionality

| Gap | Reviewable completion criterion |
|---|---|
| Official reference evaluation | Local handoff is implemented; obtain the actual gold artifact and contract, validate its mapping, then add task-specific scoring |
| Measured graph-link comparison | First retrospective restricted comparison and Lambourne baseline corroboration complete; no consistent hierarchy gain or independently demonstrated Steward improvement. Both panels are consumed; independent prediction validation, justified enrichment and official judging alignment remain |
| Bounded agent construction | Deterministic cohort retrieval/publication is implemented with recorded calls and budgets. Agent selection and its comparison against the deterministic path remain |
| Validated interoperability | Bounded KGX Reactome projection, preserved source bundle and round-trip checks now exist. Resolve the documented category-array and predicate-domain findings before claiming broader conformance; keep mappings and exclusions explicit |
| Evidence filtering/pruning | Define task-compatible evidence actions and references; measure false removals and abstention. Assay nondetection does not automatically invalidate a functional association or co-complex relation |
| Maintenance | Extend guarded comparison to explicit cohorts; controlled source-change cases must distinguish changed evidence, scope/cap absence and withdrawal while preserving review continuity |
| Usability | Actual biomedical-user task completion, errors, time and interpretation checks |
| Packaging | Fresh-clone instructions, source/license manifests, dependency pins, fetchable or redistributable examples and separate archived history |

Use established implementations before filling these gaps with custom infrastructure. Recheck official versions, task assumptions, licenses and training/evaluation overlap. When a new scientific or integration issue appears, record what literature documents, what our implementation demonstrates and what remains unresolved.

## Delivery context

The supplied challenge brief lists an intermediate progress report on **October 27, 2026** and challenge end on **November 17, 2026**. These are supplied dates, not a newly verified schedule. An organizer Pharos gold set has now been mentioned, but no artifact or complete scoring contract has been provided. Report the workbench and completed bounded assessments separately from the remaining independent-improvement and official-scoring requirements; seek mentor feedback on the assay-specific PPI task's challenge fit.

See the [functional crosswalk](PROJECT_ALIGNMENT.md) for organizer/proposal coverage. AWS/Neptune, a UI framework migration and additional agents are conditional implementation choices, not substitutes for the missing evaluation.
