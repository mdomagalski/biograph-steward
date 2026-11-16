# BioGraph Steward | Challenge submission

BioGraph Steward helps a researcher turn a supported question into a focused
Pharos evidence graph, a readable cited answer and a reproducible handoff.
Each connection retains its original source and conditions. The researcher can
see what was added, what was excluded and what remains uncertain.

**Start with the [five-minute judge walkthrough](JUDGE_WALKTHROUGH.md)** and
[protected reviewer site](https://bi-3a117d5e2b3942678dc518fce65ab5d2.ecs.us-east-2.on.aws/).
The workspace token is supplied privately. No AWS account, graph-query language,
GPU or model server is needed for saved review. The
[delivery status](DELIVERY_STATUS_20261115.json) identifies accepted deployments;
the [3:42 narrated screen tour](../output/walkthrough/BioGraph_Steward_Walkthrough.mp4)
uses actual hosted-app captures, focused crops and captions. The
[seven-slide overview](../output/presentations/BioGraph_Steward_Overview.pptx)
provides its presentation.

## One research cohort, two useful tasks

Both examples concern **99 primary protein targets from a captured colorectal
cancer cohort**. They demonstrate different operations, with different source
collections; their total record counts are not a paired before/after comparison.

| Task | What a reviewer can see | Concrete outcome |
|---|---|---|
| **Explore added source context** | A KRAS question, small graph, cited answer and preserved native STRING source record | 14 candidate result proteins. The full added physical source has 330 qualified pairs: 243 already represented in the captured graph and 87 absent there. Native GO adds 3,309 records describing 429 protein-location concepts across 94 targets. Additional rows are not automatically independent experiments or accepted claims. |
| **Review applied graph qualifications** | A TP53 pathway question using the graph after explicit qualification decisions | 16,985 input records become 16,687 retained records. The 298 excluded records have obsolete GO identifiers in the pinned ontology. All original rows and decisions remain recoverable; 11,636 abstained records stay retained. This is identifier qualification, not 298 experimentally disproved biological links. |

The pathway example supports contextual multihop reasoning: TP53 and another
protein connect through an exact cited model. Shared model membership does not
assert direct binding. Native archived models preserve connections that a
current-only flat list can omit, and unresolved source claims are not pruned
merely because a current lookup fails.

## Evidence for the judging criteria

The organizer brief assigns the following weights and permits autonomous
**or semi-autonomous** software. This is our evidence map, not an official score.

| Criterion | Visible demonstration | Evidence and boundary |
|---|---|---|
| **Usability (40%)** | Start here → Question & graph → Inspect sources → What changed → Export | Guided real examples answer a concrete question without graph syntax. A small graph and readable claim lead to the source. Independent intended-user feedback is still pending. |
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

The app now puts richer source context into the actual question, inspection and
export flow, alongside applied source qualification. The public-reference
assessment gives a bounded measure of the added information:

- **Known protein locations:** among 31 matching proteins, the captured Pharos
  view recovers 41 of 51 positive reference labels; qualified native annotations
  recover 44 of 51. These fixed source views are not a newly scored union of the
  full integrated graph. Shared-source context remains explicit.
- **OpenCell source-exclusion check:** among 23 matching proteins, positive
  label recovery changes 30 of 40 to 31 of 40. The gain remains after the stated
  HPA/OpenCell source exclusions. This already-exposed reference is a
  sensitivity check, not new blind validation or a new biological discovery.
- **Later curator function recovery:** a fixed historical comparison improves
  over retained LocalPlus in its primary views. Refreshing the baseline's
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

Optional Nemotron planning, a NeMo Agent Toolkit wrapper and a bounded
source-audit agent were implemented and evaluated. Their recorded results are
available in the [NVIDIA integration record](NVIDIA_INTEGRATION_STATUS_20261113.md).
The model planner remains experimental, and the audit agent did not outperform
the specialist baseline. Consequently, explicit choices and deterministic
source checks are the dependable path; model outputs do not automatically
accept or biologically prune claims. The entry is semi-autonomous, not a claim
of validated unrestricted autonomous scientific curation.

Versioned snapshots, guarded comparison and review history support maintenance;
unattended literature monitoring is outside the delivered scope. A working
bounded pipeline is supplied instead of claiming every platform or autonomous
role listed in the original proposal.

## Reuse and handoff

The native KRAS workspace ZIP includes its candidate graph and preserved source
files. In the applied-qualification TP53 example, the workspace ZIP also
includes the retained graph, complete keep/prune/abstain ledger and original
baseline/source packet. The small answer diagram and focused answer ZIP are
separate views. Original and retained graphs stay distinguishable, and
abstentions do not disappear.

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
provide judges the graph, ledger and baseline through a permitted access route.
