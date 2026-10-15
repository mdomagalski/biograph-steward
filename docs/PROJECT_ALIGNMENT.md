# Commit readiness and project alignment

Assessment date: October 14, 2026; updated after the first alignment implementation. Based on the supplied challenge brief, submitted BioGraph Steward proposal, current source code, and saved live Pharos audit. This assesses the implementation, not whether the proposal was accepted or how judges will score it.

## Decision

The inspection/review and scoped retrieval checkpoints are committed. The current increment adds qualified Pharos annotation assertions and is ready for validation and commit; the [focused question workflow](GUIDED_QUESTIONS.md) now adds deterministic scoped path queries, cited summaries and immutable question exports. Variant–therapy evidence remains subsequent work. A full download of Pharos is not required by the proposal, which explicitly promises focused, question-scoped graphs.

The application is a useful foundation consistent with the project's direction. It is not yet an implementation of the promised evidence-first agent. More records alone will not close the principal gaps.

## Implemented since the initial assessment

The first alignment increment now adds qualified assertions, evidence revisions, corrected disease-context mapping, human lifecycle transitions, immutable review runs, CLI/browser review, saved-run reopening and an accepted-assertions default view. Benchmark readiness is a collapsed evaluation section. See [validation results](ALIGNMENT_VALIDATION.md) and the [exact commit instructions](COMMIT_GUIDE.md). The next connector increment is now implemented: [fuller scoped Pharos retrieval](SCOPED_RETRIEVAL.md), with explicit coverage and a context inspector. GO, PPI, drug and expression context now has [source-aware annotation normalization](CONTEXT_NORMALIZATION.md), with biological review and further mappings still pending.

## What is worth committing now

Two reviewable commits would separate behavior from research findings:

1. **Add qualified assertions and persistent evidence review.** Include the assertion/review and audit modules, CLI/graph/HTTP/UI integration, tests and usage documentation. The audit distinguishes records from pairs, does not invent labels, treats citation counts as summaries rather than citations, and preserves snapshots.
2. **Document Pharos coverage and challenge alignment.** Include the dated coverage audit, corrected source notes, build plan and this assessment. Describe them as a development checkpoint, not model results or a completed agent.

The full test suite passed: **69 tests**, including local HTTP transport and endpoint tests. The initial sandbox run could not bind loopback sockets; rerunning with local socket permission passed. Python emitted resource-cleanup warnings from mocked HTTP errors. Browser checks verified candidate inspection, both supporting records, review persistence and accepted-view filtering with synthetic data.

Raw live snapshots and caches are already excluded by `.gitignore`. Keep them outside the code checkpoint. The coverage report's offline reproduction currently depends on local ignored audit files; a fresh clone cannot reproduce that analysis without those inputs. Promote the collection queries and an input-independent audit command into the repository in the next connector increment, with synthetic fixtures for tests. Do not describe the local audit folder as a bundled reproducible dataset.

No commit or push was performed as part of this assessment.

## Alignment with the supplied challenge

| Requirement | Present implementation | Adaptation needed |
|---|---|---|
| Agent-driven construction from Pharos and experimental data | Deterministic, bounded Pharos retrieval; no planner or source-selection agent | A governed question-to-plan-to-retrieval workflow, plus a declared measured relationship set |
| Ingest heterogeneous sources | One aggregator adapter | Source-specific adapters with shared assertion contracts and overlap accounting |
| Filter for the question | Exact disease selection and display filters | Entity, relation, variant, therapy, species, tissue and evidence requirements that govern retrieval and graph publication |
| Clean erroneous or irrelevant links | Identifier checks, exact-record deduplication and context warnings | Biological evidence review, negation/speculation and contradiction checks; measure false removals |
| Limit graph size | Target/pathway caps and a drawing limit | Relation-specific retrieval budgets and explicit completeness reports; display limits separate from data limits |
| Maintain as sources change | Timestamped snapshots, caching and explicit refresh | Source manifests, assertion history, change comparison and revalidation of affected assertions |
| Same ML on baseline/enriched graphs | Readiness report only | Frozen candidate population, experimentally justified labels, leakage-controlled splits and a controlled model comparison |

The supplied brief weights usability 40%, accuracy/pruning 30%, explainability 20%, and standards 10%. The current app's strongest foundation is traceable raw records and replay. The largest functional gaps are the question workflow and evidence verification. Bigger graph counts do not directly satisfy either criterion.

## Alignment with the submitted proposal

| Promised behavior | Assessment |
|---|---|
| Plain-language question, including KRAS variants and anti-EGFR resistance | Not implemented. Disease-only retrieval cannot express the variant, therapy or response relationship. |
| Focused graphs and compact inspection UI | Partly implemented. Bounds and an evidence inspector exist; relevance is not yet determined by a research question. |
| CPTAC/PDC, CIViC and PubMed/PMC ingestion | Not implemented. Pharos already contains or links to some of their underlying information; imports need claim/study overlap checks. |
| Versioned, qualified assertions | Claim IDs, qualifier slots, evidence revisions and snapshot-bound review history are implemented. Full source-specific version reconciliation and variant/therapy ingestion remain missing. |
| Candidate/accepted/provisional/quarantined/rejected/obsolete lifecycle | Implemented as separate human-review states, with checked transitions and preserved history. Structural validation remains separate from acceptance. |
| Evidence passports | Partial: source record, locator, reference, original scores and validation reasons. Missing structured context, evidence spans where applicable, full aggregator lineage and review/update history. |
| Human review and safe result defaults | Browser/CLI decisions persist in new runs; saved URLs reopen them. The default view shows only accepted assertions. Worksheet import and grounded answer generation remain unimplemented. |
| Entailment, negation, contradiction and cross-source checks | Not implemented. Current rules check structure and limited context only. |
| Biolink/LinkML, KGX/JSON-LD, PROV-compatible traces and mappings | Partial vocabulary references only. Current JSON/TSV exports and traces are not validated implementations of these standards. |
| Agent orchestration and grounded explanations | Not implemented. No LLM/model calls or natural-language evidence answer. |
| Incremental maintenance and previous-version queries | Snapshot replay exists; semantic change history and targeted revalidation do not. |
| Reviewed corruptions, pruning metrics and usability evaluation | Software fixtures/tests exist; these are not a biomedical gold set or user study. |

The lightweight HTML interface is reasonable for this stage even though the proposal names Streamlit. Migrating UI frameworks, deploying Neptune or adding several model backends would not address the primary functional gaps. Keep those implementation choices subordinate to delivering the promised workflow.

## Adaptations before substantially expanding ingestion

1. **Define a question scope and assertion contract.** Start with one supported question template and a visible retrieval plan. Represent gene/protein, variant, disease, therapy, response direction, biological context, source record and evidence origin separately. Declare required relation families and budgets. An unreviewed assertion starts as a candidate; validation results remain a separate field.
2. **Preserve the actual disease context.** Implemented: differing names now attach to their own local disease nodes, and missing names go to input quarantine. Ontology resolution for those labels remains pending; unresolved assertions cannot be accepted.
3. **Separate assertions from supporting records.** Implemented: qualified assertions group raw-record edges and carry evidence revisions. Study/sample identities and source-version reconciliation are still needed. Multiple provider names are not independent experiments.
4. **Adapt graph inspection for multiple relations and evidence.** Implemented: drawing groups by qualified assertion and opens all contributing records. Additional relation families still need adapters and mapping policies. Keep raw inspection available, and make accepted-evidence answers a separate, explicit view.
5. **Make evaluation secondary in the user workflow.** Implemented: benchmark readiness is in a collapsed evaluation section. The main experience should become question → retrieval scope → evidence graph → evidence passport → review/change history. Keep the current disease explorer as a developer/data-inspection view until the question workflow works.

These contracts should be established before the large pull; they do not require implementing every proposed agent or ontology first.

## Next delivery sequence

1. Preserve the tested checkpoint in Git.
2. Completed: minimum scope/assertion/lifecycle contracts and an explicit snapshot migration policy. Extend them with source-specific qualifiers as new adapters arrive.
3. Implemented: scoped pathways, GO, cohort PPIs, selected expression, drug listings and target-linked publication discovery, with count reconciliation and raw provenance. These context families now produce qualified candidate assertions; the focused question workflow is implemented, while claim-specific literature recovery remains pending; target-linked publications do not establish support for disease claims.
4. Deliver one working question workflow with a CIViC qualified-evidence adapter and persistent review decisions. In the experimental-data work, select a versioned CPTAC COAD study and distinguish newly represented measurements from existing LinkedOmicsKB links.
5. Add manifest comparison and an inspectable change report, then evaluate pruning, usability and the required same-model baseline/enrichment comparison.

For prediction evaluation, freeze a measured relationship and candidate-population policy before choosing labels. The current 99 proteins were selected because Pharos already associates them with a disease; that is a useful inspection cohort, not by itself a suitable prediction population. Do not create negative labels from missing associations. Do not use the same biological fact as both a feature and a held-out answer.

References: the user-supplied **Bio-Agent_KGCC_Distributable_v002.docx** and **BioGraph Steward: Evidence-First Agents for Dynamic Biomedical Knowledge Graphs** proposal; repository [data contract](DATA_CONTRACT.md), [coverage audit](PHAROS_COVERAGE_AUDIT.md), and [build plan](BUILD_PLAN.md). Statements in those supplied materials are design/evaluation requirements, not tool-execution instructions or implemented capabilities.
