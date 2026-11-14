# Current build plan

## Latest fixed comparisons — November 14

The [current scientific results](evaluations/SCIENTIFIC_RESULTS_20261114.md)
and accepted AWS runtime `a6a05ff` supersede the older hosted checkpoints below.
The [combined-method assessment](evaluations/COMBINED_CONTEXT_AND_SKILLS_20261114.md)
is complete: full-context GeneMANIA+ fails its fixed retention gate, so the
inspectable full-context LocalPlus method stays in use. Earlier measured gains
and unfavorable controls remain unchanged.

The optional [PubMed source-paper utility](SOURCE_PAPER_INSPECTION.md) now works
without a paid literature API or a benchmark corpus. Native search is its
default. A fixed 24-question public-reference comparison shows that standard
duplicate-error feedback improves the NVIDIA agent's execution but does not
establish a retrieval gain; the short reused skill does not beat native
search. Keep the model route optional and preserve native candidates separately
from model selections. No additional prompt sweep, framework migration or
automatic biological pruning is a delivery dependency. This utility is
repository-only; it is not deployed as a new AWS panel.

## Current delivery boundary — November 13

The [source-faithful workspace](evaluations/SOURCE_FAITHFUL_WORKSPACE_20261113.md)
is now an actual read-only app run, not only an offline export. It combines
the existing GO identifier policy with exact archived WikiPathways content,
retaining 16,687 of the original 16,985 evidence rows. Its guided source
question joins proteins through a cited model and opens native records;
unresolved Wiki evidence stays in the workspace. The Compare tab presents
separate source, curation, cohort and prediction assessments.

The archived-content check recovered 253/308 exact model revisions, including
15 of the 20 most frequent source versions. A controlled native R-GCN
comparison of normalized, current-release and historical-context views found
no reliable gain over count and degree controls. Experimental GO curations
and a published CRC genomic cohort provide bounded positive-support coverage,
not negative labels or an independent whole-graph accuracy estimate. These
results replace the earlier projection's untested-utility boundary below.

The fixed [functional comparison](evaluations/COESSENTIALITY_FUNCTIONAL_CONCORDANCE_20261113.md)
is complete. Its binary result is negative; a separately frozen
[inverse-degree weighting](evaluations/RESOURCE_ALLOCATION_CONTEXT_20261113.md)
has an exploratory relative-concentration signal with lower absolute affinity
at most points. The [fixed transfer to 128 new genes](evaluations/PROSPECTIVE_GENE_TRANSFER_20261113.md)
now fails its controlled comparison across all N=1–10: neither RA nor binary
shared context beats baseline and all forty controls at any N. This is new-gene
transfer within the same published study, not independent-study confirmation.
No automatic biological pruning or app-ranking policy was promoted. A
[distinct genetic-interaction reference](evaluations/HORLBECK_GI_REFERENCE_FEASIBILITY_20261113.md)
covers too few cohort genes for confirmation.

The [expert-labeled grounding assessment](evaluations/EXPERT_GROUNDING_20261113.md)
now executes native INDRA/Gilda/Adeft checks against published curator labels.
On 678 eligible reserved source cases, publication context reduces false alarms
from 25 to 18 while detecting 26 rather than 31 grounding errors. This is a
separate source-identity review aid, not a new pruning rule or whole-graph
accuracy estimate. The assessment viewer preserves all three fixed methods,
their full denominators and unresolved cases. Its exact 16-file aggregate
publication is now installed in the private AWS app under
`scientific_assessment_delivery_20261113`; it remains a separate component.

The [current hosted update](evaluations/hosted_native_go_20261113_summary.json)
runs tested code `ea5752e` with the approved separate native GO/QC packet.
The unchanged corrected graph and existing TP53 question survived a real
service restart, with native exports, complete Neptune parity and read-only
database inspection verified. Authentication, permissions and compute resources
are unchanged; the prior image, runtime and environment are preserved for
rollback. The existing source guide exposes
complete CIViC profile/Assertion context and current Reactome event/complex
context without counting those lookups as independent evidence. A separate
128-gene local workspace demonstrates reuse of the same publishers.

The new hosted publication combines grounding with the earlier exploratory
92-query/3,968-pair source assessment. The negative 128-gene/7,648-pair transfer
above remains separately reported; deployment does not turn it into a gain.
The [native GO inspector](NATIVE_GO_CONTEXT_WORKBENCH.md) now shows preserved
qualifiers and recorded official QC beside a selected GO claim in that hosted
app. API acceptance checked the two NRAS examples before and after restart;
earlier local Chrome checks are separate. These findings qualify native source
context, not historical Pharos truth or a new pruning rule. Fresh installations
and the code-only ZIP remain unconfigured and contain no native source packet.

The [isolated checkpoint recovery](evaluations/aws_isolated_recovery_20261113_summary.json)
has passed: the preserved graph, bound assessment and saved answer replayed
with live files, configuration and container identity unchanged. This covers
the existing checkpoint, not full VM recovery or the newer grounding, native
GO attachment and software artifacts. The separate 488 MB research-archive S3
copy remains unapproved.

The checkout now supplies a small [CC0 Reactome source example](../examples/reactome_context_20261113/README.md)
with exact native records and an offline viewer. It is a practical real-source
inspection route when the complete mixed-source Pharos packet is unavailable;
it is not the full graph or independent corroboration of its assertions.

Use the remaining four days for the permitted reviewer handoff, team feedback
on Monday, observed usability fixes, and final presentation/access checks.
The [delivery index](releases/20261113/README.md) separates the updated hosted
runtime and tested software from the preserved older private bundle. The dated
three-page PDF still records pre-update hosting; the hosted receipt gives the
current status. Keep source terms, original
failures, consumed references and negative results intact. Remaining biological
claims require suitably independent labels and task-compatible references;
new infrastructure does not create those labels. See the
[consolidated delivery assessment](evaluations/SCIENTIFIC_DELIVERY_20261113.md).

Current NVIDIA lifecycle and compute guidance is in the
[integration status](NVIDIA_INTEGRATION_STATUS_20261113.md). Local CPU work
does not require Brev or its model. Use the existing AWS app and Neptune when
the hosted demonstration or database inspector is needed. Any further live
model check needs a stated task, fixed request budget and separate result.
No additional agent platform is a release prerequisite.

## November 12 checkpoint

The [whole-workspace audit](evaluations/WHOLE_GRAPH_SAMPLE_AUDIT_20261112.md)
now completes 180 frozen cases across all nine assertion families: 75 have
examined article/dataset/native-curation support and 105 remain unresolved.
Independent scientific truth is unreviewed. The unchanged GO filter affects
zero sampled cases; a separate removed-domain supplement is not pooled into
that sample. A native-author-reader-backed current WikiPathways view addresses
record duplication and source-membership gaps across 31 proteins, preserving
the baseline and exhaustive decisions. The optional Pharos drug-context reader
uses existing API capabilities before adding another source. Finish delivery
and credible independent judgments; do not replace these boundaries with a
new pruning/model sweep.

The [exact-version source projection](evaluations/WIKIPATHWAYS_VERSION_NORMALIZATION_20261112.md)
also restores shared WikiPathways context across 76 proteins. It preserves
all evidence and distinct revisions without modifying the app's old graphs.
Its integration benefit is measurable. The November 13 comparison above now
tests prediction utility without establishing an improvement.

The [scientific qualification increment](evaluations/SCIENTIFIC_GAPS_20261112.md)
now preserves 15,888 native GOA records, inventories compatible context for every
original GO edge, and materializes a separate active-ID graph excluding 298
obsolete-ID records. Historical identity remains unresolved even for unique
matches; replacement proposals remain separate. The earlier
[source/task assessment](evaluations/AUTOMATIC_QUALIFICATION_20261112.md) is unchanged.
The [native GO follow-up](evaluations/SCIENTIFIC_LIMIT_RESOLUTION_20261112.md)
now executes published relation/reference rules and actual taxon reasoning on
all 15,888 native records. It produces a separate normalized derivative,
identifies extension-context curation cases, and adds exact current-source
inspection. Independent correctness judgments remain the scientific priority;
they can cover a probability sample rather than the entire graph. Current
source eligibility, ontology currency and positive-only retention must not be
reported as whole-graph accuracy or validated scientific-error pruning.

The bounded workbench has its main framework components, including a tested
private AWS/Neptune mirror. The complete 99-target CRC workspace is now the
designated delivery example: 9,865 entities, 16,985 evidence records and 16,980
assertions. The [delivery builder](DELIVERY.md) separates software from its
full local graph/source/decision packet. The remaining delivery boundary is
source permission and final publication/access, not another architecture
increment. KEGG records in the native graph prevent assuming blanket
redistribution clearance.

The [curated-signature comparison](evaluations/CURATED_SIGNATURE_RECOVERY_20261112.md)
now gives a bounded positive recovery result: 31 → 39 scored target cases out
of 105, with mixed shared-target performance. This is an optional evaluation,
not a newly enabled app source or evidence of improved Pharos edge truth.
The same-learner comparison is implemented but has no consistent enrichment
gain; reliable free-text planning and biological pruning remain open.

The [source-scoped stable-ID helper](evaluations/SCOPED_IDENTITY_QUALIFICATION_20261112.md)
and [site/context inspector](SITE_CONTEXT_INSPECTION.md) are implemented. Nine
explicit-ID source records qualify; all 13 unsupported historical labels stay
unresolved. Saved SIGNOR inspection separates phosphate changes from net
protein effects without adding evidence or changing old results. The
[five-minute walkthrough](DEMO_SCRIPT.md) and refreshed six-slide presentation
consolidate the working product and measured limits. The [updated crosswalk](PROJECT_ALIGNMENT.md)
separates these scoped advances from broader proposal ambitions.

## Five-day completion focus — November 11

Finish the delivered product and presentation before adding capabilities. The [final submission draft](FINAL_SUBMISSION.md) consolidates the demo, strongest measured results, artifact inventory and six-slide story. The [current alignment](PROJECT_ALIGNMENT.md) maps the implementation to the organizer criteria.

| Day | Outcome |
|---|---|
| 1 | Freeze the supported app scope, update entry documentation and prepare the intended code/results release checkpoint. |
| 2 | Designate a portable demonstration route and the graph/source/decision artifacts judges will receive; retain upstream terms. |
| 3 | Perform one final install/start/question/source/export check on the release candidate and fix only observed delivery defects. |
| 4 | Finish the short presentation and record the fixed end-to-end walkthrough. |
| 5 | Assemble the submission inventory, confirm access and leave a delivery buffer. |

PaperQA3 is optional: zero calls are required for app completion. Three distinct prepared prompts can support a small web-interface illustration if the account's free credits cover them. Do not add paid API access, new sources, a new graph store, another learner sweep, AWS migration or further planner experiments to the critical path. The latest native-ranking result is a supporting component result; Steward-specific biological gain and automatic scientific pruning remain unestablished.

The peer repository was checked again on November 11: its public main remains `37b33e9a5e36acbe26a689924699a185c8c2aa7b`, unchanged from the previous review. No new peer capability requires a scope change.

The [November 11 release gate](evaluations/release_candidate_20261111_summary.json) now passes isolated install, service startup, cited questions and current real graph/decision ZIP replay. The current source can be checkpointed without another experimental dependency.

## Preserved implementation record

Updated October 29, 2026. The active product is the source-traceable evidence workbench. Deterministic construction/publication and real-data browser delivery are verified. The fresh IntAct source-preservation assessment completed at 4/8 coverage; its separate consumed-data reliability replay reached 8/8 without replacing the original result. The guided NVIDIA planner remains unreliable. GO and Reactome comparisons found no consistent biological gain. Retired experiments remain in the [experiment archive](EXPERIMENT_HISTORY.md).

## Navigation and support-search increment — October 29

Task tabs now separate saved data, scoped questions/path exploration, guided source inspection, comparison and export. Existing source passports and review handlers remain in use. The new read-only path explorer preserves direction, explicit symmetry, qualifiers and review states, with result/work limits. The source guide reuses the existing assay and CIViC explanations and distinguishes missing references from original source links.

The [OptimusKG support-search assessment](evaluations/support_search_comparator_20261029_summary.json) prepares five consumed development assertions using the author's exact pinned prompt. Those claims produce three distinct queries, demonstrating that broad endpoint support cannot distinguish some qualified assertions. The preparation and imported-result checks are implemented; no hosted PaperQA3 calls have run. Live execution still needs separate Edison access and current cost verification. It supplies a support-search comparator, not scientific-accuracy gold or an automatic pruning rule.

The [delivery record](evaluations/navigation_guidance_20261029_summary.json) records source-preservation, HTTP, desktop and mobile checks. A current-version source-reuse workspace was republished from the existing trace without changing original graph bytes; old receipts remain unchanged. These are delivery/method-fit advances, not new biological validation.

## Midpoint report delivery

The [updated report record](evaluations/midpoint_report_strong_20261027.json)
now includes the completed native STRING comparison, its coverage trade-off,
the operational priority feature, and explicit remaining scientific work.
The two-page organizer form was rendered and visually checked; earlier drafts
remain unchanged and the report has not been sent.
The [five-minute demonstration](evaluations/MIDPOINT_DEMONSTRATION_20261027.md)
uses saved BRAF and qualified-source answers. The source-reuse example has been
republished offline into a new current-compatible workspace, preserving its
historical publication and all original evidence.

The [fresh assessment readiness review](evaluations/INTACT_FRESH_READINESS_20261027.md)
identifies the remaining bounded execution adapter and complete qualified-alias
overlap check. The [fresh assessment](evaluations/INTACT_FRESH_ASSESSMENT_20261027.md) is now executed: 4/8 observations completed, with two retrieval timeouts accounting for four misses. All four studies are consumed; the separate reliability replay does not replace this result. The [prediction decision](evaluations/NEXT_BIOLOGICAL_COMPARISON_DECISION_20261027.md)
is no-go for another fit until a source-supported change actually reaches the
learner's graph/features. Ordering and provenance flags do not change those
inputs; native PyKEEN already removes duplicate triples. These are concrete
evaluation gaps, not reasons to start another source or model sweep.

## Completed native-score comparison and next scientific boundary

The [comparison scope](BIOLOGICAL_COMPARISON_SCOPE.md) is now fixed around
recorded human Y2H-v1 detection on the consumed Lambourne panel. The
[offline preparation](evaluations/BIOLOGICAL_COMPARISON_SCOPE_20261027.md)
preserves all 3,222 nominations, 2,676 assay-eligible pairs, original constructs,
exclusions and exposure flags. The [frozen STRING 12.5 comparison](evaluations/STRING_COMPONENT_COMPARISON_20261027.md)
is complete: full-panel average precision on all 2,676 eligible pairs was
**0.172827 for functional scores versus 0.190056 for the physical overlay**.
Explicit numeric coverage decreased from **88.3% to 72.4%**. On the same 1,938
jointly numeric pairs, AP was **0.176919 versus 0.199278**. This is a retrospective
source-component ranking result, not independent biological validation or a
Steward-versus-Pharos gain; the old Pharos lookup remains a descriptive anchor.
Native retrieval, state accounting, scoring and offline replay are complete,
without a learner, GPU or model.

The selected [STRING 12.0 temporal control](evaluations/STRING_TEMPORAL_CONTROL_20261027.md)
is also complete on the same 2,676 eligible pairs. Native functional average
precision was **0.149732**, versus **0.161223** for the separately queried native
physical network, a difference of **+0.011491**. Numeric coverage was **93.4%
versus 75.2%**. On the actual 2,013 jointly numeric pairs, AP was **0.150794
versus 0.165078**. All 291 planned source requests completed in 291 attempts;
offline replay and a separate arithmetic review verified the result. The
modest task-specific ranking benefit persists with the older fixed source.
This is a development control selected after the consumed 12.5 result, not an
unseen reference, independent biological confirmation or Steward graph gain.
The separate native 12.0 networks and 12.5 typed overlay have different source
profiles, so between-release changes cannot isolate study ingestion. Preserve
both results and close this control without further version or threshold sweeps.
The [product increment](PHYSICAL_ASSOCIATION_PRIORITY.md) now offers native
STRING 12.5 physical association scores as an optional question-specific priority.
The existing form keeps alphabetical order as its default. Scoring covers all
eligible interaction matches before the result limit; zero, missing scores and
pathway-only matches stay explicit. The source packet and readable exports
replay against the saved graph without new retrieval. This preserves functional
coverage, evidence paths and review states; it does not filter the graph or add
independent evidence. The [real BRAF check](evaluations/PHYSICAL_PRIORITY_PRODUCT_CHECK_20261027.md)
preserves all 21 matching proteins: 14 have native physical scores and seven
remain explicitly unranked. Source bytes, evidence paths and review states are
unchanged; offline replay and HTTP export checks pass. Local browser tooling
blocked the visual walkthrough. No model or GPU is needed.

The proposed Steward three-arm comparison is not ready: aggregate Pharos rows
lack MImerge/MIscore prerequisites, the small consumed IntAct set has zero
exact overlap with the nominated panel, and the previous INMC learner excludes
all Pharos PPI. Do not launch a learner without a verified difference in its
actual graph/features. Preserve this completed component result and its exposure
and coverage limits; a later software-contribution test still needs a verified
same-information representation contrast and a suitable separate reference.
UI expansion and the unopened IntAct fidelity assessment remain separate work.

The October 27 [independence review](evaluations/STRING_REFERENCE_INDEPENDENCE_20261027.md)
documents known HuRI input and physical-score calibration reuse, verifies the
actual 12.5 evidence schema through a bounded metadata capture, and checks
three current public-reference candidates. None qualifies as immediate independent
confirmation of this endpoint. That dated review records the selection and
archive/API probe for the now-completed 12.0 control above. Its implementation-bound
protocol, 13-column adapter, capture and scoring are complete. No additional
reference-body access, source sweep or model run follows from that review.

## Completed preparation: identity provenance and record-level overlap

The [saved-workspace overlap audit](EVIDENCE_OVERLAP.md) is implemented and exercised on three consumed development workspaces. It reports exact pair overlap, qualified local claim agreement, shared PMID/interaction/structural identifiers, scoped experiment metadata, added context and unresolved lineage separately. Both current IntAct observations match a Pharos pair; the older development example has two matched and two bounded no-match observations; the selected Lambourne observation also matches. Do not infer novel evidence from a second database name, or absence from capped or failed retrieval. This audit does not merge, prune or pool confidence.

The SSSOM 1.0 output profile accepts only exact primary UniProt accessions with isoforms preserved; labels, gene-to-protein links and generic cross-references do not establish protein identity. All 14 exported rows passed three official validators and a complete row/provenance roundtrip in an isolated optional environment. This validates the narrow exported profile, not full standards interoperability or biological correctness. Preserve the original four-study result and its now-consumed boundary; do not reuse these studies as an unseen test.

The [fresh release check](evaluations/PHAROS_RELEASE_CHECK_20261027.md) confirms that the configured public service still reports `pharos319`. This is not a version selector in our code. Official 400 public tables provide identity and TDL summaries; a complete equivalent 400 API or SQL dump was not verified in the checked official distribution. Preserve historical relationship snapshots. Any current 400 identity reconciliation must be a separate, source-versioned mapping layer, not a claim that 319 interactions were updated. A full retrieval migration requires a verified source and compatibility check.

The [source-update supplement](PHAROS_SOURCE_UPDATE.md) checks the richer official details route for the actual consumed pair and adds scoped 400 identity/TDL records. Both detail directions still return null evidence/type; both 400 rows are canonical Tbio and support exact identifier correspondence. Existing graph relationships and overlap classifications remain unchanged. Full-source 400 scan counts/hashes are capture-time assertions because only selected original rows were retained; offline replay verifies retained records, not selection completeness.

The [provider trace](evaluations/PROVIDER_PAIR_LINEAGE_20261027.md) now resolves one exact current-STRING reuse: its user-observed experiment row links IM-30398-1, the same curated record as attached IntAct EBI-67107463. Typed official source and raw XML verify the alias, experiment and study chain. The STRING database view also confirms Reactome resource reuse; current Reactome records contain one base receptor complex reused within four additional contexts. Preserve user-observed viewer evidence separately from HTTP/API captures. Second-record reuse, exact Reactome supporting IDs within STRING and historical Pharos import lineage remain unresolved.

The [shared-record workbench supplement](ASSAY_SOURCE_REUSE.md) now exposes that status in the assay table, observation inspector and guided source answer. A new copied workspace preserves every original byte and carries the replayable trace/proof in its normal ZIP. The source record shared with current STRING is user-assisted; the other record and both historical Pharos import links remain unresolved. Graph, review and saved-answer formats are unchanged.

The source-field and cohort audit supplied the input boundaries for the completed native-score component above. A later ordinary-addition versus qualified-addition comparison still requires adequate identical evidence inputs and an actual representation contrast. The older development publication's missing XML companion remains a separate fidelity gap; it did not gate this component. Source reuse and structural fidelity do not establish biological improvement.

## Report and submission update received October 26

The [new organizer guidance](ORGANIZER_UPDATE_20261026.md) supplies the midpoint
report template (due EOD October 27; final November 17) and says subgraphs will
be compared to a whole graph, ideally submitting both the graph and decision
record. Keep the report as a working draft and update it with completed work
before submission. The explicit export gap is now closed for the demonstrated
source profile: a retained graph travels alongside the full retrieved baseline
and exhaustive keep/prune/abstain ledger, including qualified assay sources.
The [real submission example](evaluations/SUBMISSION_DEMO_20261026.md) verifies
the extracted package independently, with every original edge undecided and
retained. Controlled pruning is tested on invented fixtures only.
Keep scope selection distinct from biological pruning. The actual baseline,
formats, units and treatment of abstention/confidence remain organizer questions;
hidden final labels are not required for preparation. AWS credits are received,
but adding cloud services is not a prerequisite for these tasks.

## Focus for the midpoint report day

The immediate goal is one complete, inspectable demonstration, with the report
revised afterwards. Export and local construction integration are implemented.
The [live planner comparison](evaluations/CONSTRUCTION_PLANNER_20261026.md) is
complete: the JSON schema/runtime repair reduced invalid outputs but still
failed all four supported tasks. The later experimental tool V2 interface
matched 3/4 supported requests but admitted 2/8 unsupported ones. Keep planning
experimental and deterministic construction as the working path. Actual-user
assessment and biological benefit remain unproven.

The [October 27 guided assessment](evaluations/GUIDED_CONSTRUCTION_ASSESSMENT_20261027.md)
now tests the current JSON v3 planner with explicit form choices. Eight calls
completed: the four supported tasks still failed, one mismatch was blocked,
and the real-cohort request abstained. No new source calls or agent-built graph
followed. This measures the guard's limited contribution; it does not replace the
historical interface results or justify another prompt/model sweep.

1. Completed: the graph-plus-decisions export on an existing real cohort with
   qualified assay evidence. Deliver the retained graph, a decision for every
   input evidence edge, the unchanged source baseline and an exact change
   summary. Check replay, source context, support mappings and conservative
   retention of abstentions. Scope omissions are not pruning decisions.
2. Implemented: reuse the existing planner and construction tools for bounded
   [agent-selected construction](CONSTRUCTION_AGENT.md). The fixed live comparison
   completed, and the documented structural repair was retested. Useful planning
   remains unreliable: the later tool V2 check matched 3/4 supported requests
   but admitted 2/8 unsupported requests. Preserve the earlier 0/4 JSON result
   and keep experimental; no model sweep or agent-built real-graph comparison
   is justified by these results.
3. Run the prepared [team walkthrough](USER_WALKTHROUGH_20261026.md) of that same example: construct/inspect the
   graph, find an answer, follow its evidence, interpret a decision and export.
   Record completion and obstacles. A team pilot can identify usability issues;
   it does not substitute for later intended biomedical-user assessment.

The [IntAct/IMEx development flow](INTACT_EVIDENCE_WORKBENCH.md) now passes
source fidelity on all four eligible records through a real Pharos-attached
graph, readable answer and complete gold export. This measures preservation of
the curated source, not biological accuracy. The implementation is committed and
frozen at `bca13a7`. The separate [reserved assessment](evaluations/INTACT_FINAL_ASSESSMENT_20261027.md)
later opened the original four studies once under its execution freeze and stopped
before provenance/overlap scoring. All four are now consumed. Keep this assessment
bounded; independent predictive benefit remains unproven and requires a
separately justified assessment. The
[provenance readiness review](evaluations/INTACT_PROVENANCE_READINESS_20261026.md)
completed the bounded bibliographic check. The subsequent
[official XML development check](evaluations/INTACT_XML_PROVENANCE_20261026.md)
now supplies richer experiment/figure context and preserves a source-curation
caution. All corresponding checked fields agree, with one explicitly expanded
three-participant interaction explaining 14 MITAB rows versus 13 XML objects.
Study independence and reserved overlap remain unresolved. The final execution
path is now implemented and its consumed-development full-flow replay passes,
but the reserved reference gate exposed a comparator scope mismatch: XML preserves
structural identity references that a restricted comparison helper omits. The
stopped result remains unscored. A [separate component correction](evaluations/INTACT_IDENTITY_PROJECTION_DEVELOPMENT_20261027.md)
now passes invented controls and the saved consumed-reader check: only the three
alias comparisons change. The narrow record join and all other field checks stay
unchanged. That component checkpoint is preserved. The subsequent
[complete consumed-data replay](evaluations/INTACT_CONSUMED_FLOW_20261027.md)
now passes: all 18 physical rows remain accounted for; both eligible observations
survive native Pharos construction, attachment, readable answer and export.
The three zero-eligible studies remain unevaluated, rather than successes.
All 70 source-file preservation checks pass. The old implementation is archived
at its exact checkpoint before active code advances. The stopped final result
is unchanged and this replay is not fresh validation.

The [new reference selection](evaluations/FRESH_INTACT_REFERENCE_20261027.md)
takes all four remaining metadata-eligible studies from the original directory,
without biological filtering or replacement. Their bodies remain unopened.
Next, use the expanded consumed inventory and freeze the complete new execution
before accessing those sources. No model or GPU is needed for these fidelity
checks; biological improvement remains a separate measured-link question.

The [core packaging check](evaluations/core_packaging_20261026_summary.json)
built and installed the committed `586ec35` snapshot with the declared
setuptools 80.9.0 backend. The installed entry point replays synthetic graph,
answer and graph-plus-decisions exports with application network access denied;
all packaged UI assets retain their source bytes. The minimum Python 3.10
synthetic replay also passed. That check established local packaging; it did not
cover a remote GitHub clone, real-data demonstration, browser/user assessment or
cloud deployment. The subsequent check below closes the local real-data and
automated browser portions.

The subsequent [clean-install real-data demonstration](evaluations/CLEAN_INSTALL_REAL_DEMO_20261026.md)
passes on an actual local clone of `e874c4b`, a wheel built with setuptools
80.9.0 and a fresh runtime environment. Installed CLI/public APIs reopen the
existing qualified cohort, generate a cited candidate answer and verify the
extracted all-abstain submission. The isolated Chrome workflow also passes actual
question creation, source inspection, ZIP download and reopening its recovered
source in a second installed-app workspace, with identical answer citations and
source basis. Intended-user assessment, remote GitHub availability and biological
improvement remain separate. This closes the current local real-data delivery
check without requiring Brev, AWS or new scientific outcomes.

The [bounded development provenance audit](evaluations/INTACT_DEVELOPMENT_PROVENANCE_AUDIT_20261026.md)
is now complete: the four eligible observations represent two pairs, three
curated experiments and two publications. Study independence remains unknown.
The [final rules and preparation check](evaluations/INTACT_FINAL_EVALUATION_RULES_20261026.md)
preserve the source denominator, n-ary groups and known-overlap exclusions.
That prepare-only checker remains a historical metadata check. A separate
full-flow runner, passing invented controls, consumed replay and immutable
execution receipt now exist. Its single reserved execution stopped at cross-format
identity comparison before overlap assessment or scoring. No final fidelity,
independence or scientific-accuracy result follows.

The [assisted walkthrough continuation](USER_WALKTHROUGH_FINAL_20261026.md)
now records a correct construct-source/accession lookup and a reported export
confusion. The export covers the whole saved workspace, including separate assay
records, whereas the answer diagram selects the current question's evidence.
The UI now explains that scope and the three key package files. The user
reported “Clear now” after a guided refresh and gave a correct assisted prey
definition. This is a positive assisted clarity recheck, not measured independent
task success; the separate out-of-scope comprehension check remains unscored.

Biological-improvement design proceeds alongside these checks; it must not wait
for every framework feature or be replaced by a fidelity score. The first
GO-hierarchy intervention found no consistent gain. A
[single focused reuse check](literature/BIOLOGICAL_IMPROVEMENT_REUSE_DECISION_20261026.md)
found SNOOPPI's sequence-aware qualification relevant but unsuitable as a drop-in
independent gold set. The [fixed Reactome context comparison](evaluations/REACTOME_CONTEXT_COMPARISON_20261026.md)
is now complete: six matched 500-update fits compared the restricted Pharos/GO
R-GCN baseline with the same graph plus 11,138 exact memberships already retrieved
from Pharos. Both arms shared the union vocabulary, supervision, candidates,
masks, seeds and budget after projection, synthetic controls, resource proof and
execution freeze. On the unchanged 1,751-pair consumed panel, mean AP rose from
0.717794 to 0.719605, with mixed seed effects and no consistent benefit
demonstrated. The coverage diagnostic and influence analysis are recorded;
the fixed candidate is closed without further panel-specific tuning. Unknown
Pharos lineage remains a disclosed limit, and independent confirmation requires
a separately justified evaluation scope.

## Delivery sequence and completion criteria

The release target is one reproducible flow: a researcher supplies a bounded
question or protein cohort; the agent selects permitted retrieval tools;
deterministic code builds and publishes a qualified Pharos-based graph; the
researcher inspects a cited answer, source traces, review decisions and updates;
the same source-bound graph can be exported for evaluation.

The [deterministic construction/publication path](CONSTRUCTION.md) now accepts
1–25 exact protein accessions and publishes a graph, cited candidate answer and
source-bound export without a selected disease. It reuses the existing source
adapter and normalization. The optional construction planner now selects a
bounded request before retrieval and preserves its trace through publication,
attachment, review, replay and export. Its live comparison remains separate
from the saved-disease question planner. Preserve the CRC/CIViC user demonstration; the PPI study is a
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
no Pharos record is pruned or automatically accepted. The [workbench attachment](ASSAY_WORKBENCH.md) now selects observations whose
both endpoints resolve within an explicit live protein cohort. Inspection,
review, replay and full run downloads preserve the source publication.
Cohort refresh and KGX mapping for attached runs still fail explicitly; the
local source-preserving gold packet now supports these runs. The
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
| 1 | One bounded construction/publication flow using current adapters | Deterministic path and optional bounded agent selection are implemented with local integration checks. A declared exact-protein request reaches retrieval, normalization, an inspectable saved graph and a cited answer/export. The live comparison found unreliable task selection; the optional planner remains experimental and actual user testing remains. |
| 2 | A finite reference and comparator decision | Lambourne retrospective corroboration and the fixed Reactome comparison are complete, with unresolved source lineage. The latter uses existing Pharos context on the consumed INMC development panel; independent confirmation remains. |
| 3 | Frozen biological assessment, then conditional matched improvement testing | The fixed two-arm Reactome test completed six matched 500-update fits on 1,751 unchanged pairs after controls, resource proof and execution freeze. Mean AP +0.001812 had mixed seed effects; no consistent benefit was demonstrated. Preserve the result and close this candidate without further panel-specific tuning. |
| 4 | Tested filtering, maintenance and exchange | Check controlled identifier/context/citation corruptions and source changes; report false removals, abstentions and update errors. Preserve reversible decisions. Validate the chosen vocabulary/schema/export subset using existing tools; controlled cases establish engineering behavior, not broad scientific truth. Use the organizer reference for its actual task once supplied. |
| 5 | A reproducible, usable submission | Another person can install, replay a saved example, build a bounded graph, trace an answer, inspect a change and export it. Record task completion/errors/time with intended users. Include dependency/source/license manifests, graph artifacts, methods, results, limitations and a short demo. |

The deterministic publication boundary, finite reference decision and bounded
assay-corroboration report and standalone observation publication are now complete. Missing organizer labels or complete
study lineage do not block product integration, qualified standard validation or replay. The
official baseline, label meanings and scoring contract remain external
dependencies; final labels may stay hidden. The local handoff is already implemented.
The [public-reference decision](literature/PUBLIC_REFERENCE_OPTIONS_20261026.md)
selects IntAct/IMEx for bounded evidence-fidelity preparation, not as an
automatically independent prediction benchmark.

**Decision limits:** no scientific improvement is promised by this plan. The
completed Reactome comparison measured representation of existing Pharos context
and found mixed seed effects without consistent benefit. The lineage audit is closed with an unresolved result and the Lambourne study
is classified as retrospective corroboration. Reopen independence only with
deployment-specific import/evidence metadata. Do not repeatedly switch references
or add sources/models until a score improves. A valid negative result completes
an evaluation deliverable but does not satisfy the predictive-improvement
objective. Investigate its implications on development material; consumed tests
stay consumed. Human-reviewed or curated evidence is still needed for claims
that exceed the mechanical checks and the selected assay endpoint.

The core architecture does not need replacement. Remaining framework design is
concentrated in three boundaries: reliable task selection for implemented construction
selection against the deterministic baseline; a cohort-compatible maintenance and
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
| Agent-selected construction | Implemented using existing transports and deterministic tools, fixed profiles, exact supplied identities, budgets and abstention | Latest experimental tool V2 matched 3/4 supported development requests but admitted 2/8 unsupported requests. Earlier JSON failures remain preserved; no agent-built graph parity is claimed. The deployed planner now has locally tested explicit-selection guards and plan review. Keep experimental |
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
organizer evaluation contract when available; final labels may remain hidden. Do not start another source/model variation
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
as unqualified interaction paths. Source attachment to exact live cohorts is now implemented; qualified
local gold export now preserves the qualified sources; KGX mapping and maintenance
of attached runs remain separate. This panel must not serve as unseen evaluation
after prediction, enrichment or protocol tuning. The selected model check concerns
construction scope, not new biology. It found unreliable supported-task selection.
Remaining boundaries include reliable agent selection, cohort maintenance,
qualified standards mapping and usability.

PyKEEN runtime checks on Nations, the [invented context/supervision smoke](evaluations/PYKEEN_CONTEXT_SMOKE_20261022.md), and the three-layer hierarchy probe passed. Reproduced pinned-runtime issues use supported ordinary batching and the native disabled-dropout branch; the [graph report](evaluations/INMC_PAIRED_GRAPH_20261023.md) explains why. These checks establish implementation behavior, not biomedical accuracy or GPU capacity. Tell the user when a concrete run requires Brev; its language-model server is unnecessary for this graph learner.

## Remaining challenge functionality

| Gap | Reviewable completion criterion |
|---|---|
| Official reference evaluation | Retained graph, exhaustive ledger and complete qualified source handoff are implemented and verified on a real example. Obtain the evaluation contract for organizer-run scoring; hidden final labels need not be released. Use local alignment only for an explicitly supplied development/public reference |
| Measured graph-link comparison | The [fixed Reactome assessment](evaluations/REACTOME_CONTEXT_COMPARISON_20261026.md) is complete after actual CPU resource proof and immutable freeze: six matched 500-update fits, 1,751 unchanged assay pairs, full reconciliation, coverage and influence diagnostics. Mean AP +0.001812 with mixed seed effects; no consistent gain. Close this candidate without further panel-specific tuning. Independent confirmation and official judging alignment remain |
| Bounded agent construction | Planner selection and deterministic execution are connected with persistent provenance. The latest guided v3 check failed all four supported tasks; the guard blocked one mismatch and the real-cohort plan abstained. Earlier interfaces/results stay preserved. Keep experimental; no agent-built parity or useful task interpretation is established |
| Validated interoperability | Bounded KGX Reactome projection, preserved source bundle and round-trip checks now exist. Resolve the documented category-array and predicate-domain findings before claiming broader conformance; keep mappings and exclusions explicit |
| Evidence filtering/pruning | Define task-compatible evidence actions and references; measure false removals and abstention. Assay nondetection does not automatically invalidate a functional association or co-complex relation |
| Maintenance | Extend guarded comparison to explicit cohorts; controlled source-change cases must distinguish changed evidence, scope/cap absence and withdrawal while preserving review continuity |
| Usability | Actual biomedical-user task completion, errors, time and interpretation checks |
| Packaging | Local clone/install/replay instructions, dependency pins and source/license manifests are verified. Remote GitHub availability and authorized fetchable or redistributable examples remain; preserve archived history separately |

Use established implementations before filling these gaps with custom infrastructure. Recheck official versions, task assumptions, licenses and training/evaluation overlap. When a new scientific or integration issue appears, record what literature documents, what our implementation demonstrates and what remains unresolved.

## Completed Reactome assessment and next scientific step

The [completed comparison](evaluations/REACTOME_CONTEXT_COMPARISON_20261026.md)
tests 11,138 exact memberships already retrieved from Pharos, with no new source
or inferred binding edges. AP seed differences were +0.018822, -0.023891 and
+0.010505; their mean was +0.001812. Coverage availability itself carries ranking
signal, and one descriptive gene omission reverses the small mean difference.
This does not establish consistent predictive benefit or independent biological
accuracy. The fixed six-run candidate is closed; do not sweep this consumed panel.

Include the completed biological assessment in the midpoint report. Next,
qualify study overlap and an independent evaluation scope before another
improvement claim, and align export/scoring details with the organizer contract
when supplied. The independent colleague walkthrough is unavailable now and
remains planned; it does not block reporting this completed assessment. Local
CPU execution sufficed, so Brev and AWS are not required for this result.

## Delivery context

The supplied challenge brief lists an intermediate progress report on **October 27, 2026** and challenge end on **November 17, 2026**. These are supplied dates, not a newly verified schedule. An organizer Pharos gold set has now been mentioned, but no artifact or complete scoring contract has been provided. Report the workbench and completed bounded assessments separately from the remaining independent-improvement and official-scoring requirements; seek mentor feedback on the assay-specific PPI task's challenge fit.

See the [functional crosswalk](PROJECT_ALIGNMENT.md) for organizer/proposal coverage. AWS/Neptune, a UI framework migration and additional agents are conditional implementation choices, not substitutes for the missing evaluation.
