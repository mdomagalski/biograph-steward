# Current project alignment

Assessment updated October 26, 2026, against the organizer materials, proposal and Slack excerpts supplied by the user. The excerpts have no message dates or direct source permalinks here and were not independently retrieved from Slack. This is a functional crosswalk, not a claim of organizer approval. Older assessments and experiment implementations are on the [archive branch](EXPERIMENT_HISTORY.md).

## Organizer requirements

The supplied brief asks for an agent-built contextualized graph and the **same graph-learning method on baseline and enriched graphs to predict held-out experimentally measured relationships**. The newly supplied Slack excerpts mention a Pharos gold set, but its artifact and scoring contract have not been received or inspected. Current graph size, verifier scores and export quality do not demonstrate prediction gain or agreement with that reference.

## Organizer clarifications supplied October 23

| Supplied statement | Consequence for this project |
|---|---|
| Open source should have an MIT- or Apache-2-licensed GitHub repository | The tracked software LICENSE is MIT. That does not relicense upstream data. This checkpoint includes the guided-construction and IntAct increments; GitHub publication of the latest work remains pending. |
| Other data may be included as long as Pharos is represented | Pharos plus CIViC and a bounded ontology addition are within the stated source scope; there is no instruction to restrict the project to structured Pharos alone. |
| Evaluation is partly predefined in introductory materials | Keep the supplied judging criteria, but do not infer missing executable scoring rules or submission formats. |
| PyTorch Geometric subgraph extraction would be nice | Treat a tested interoperability adapter as useful, not as a requirement to replace PyKEEN or the app. |
| Gold set for Pharos; judges for additional data, in response to pruning/usability questions | Obtain the actual reference and determine what it labels. Do not assume it is an experimentally measured PPI prediction test or that it certifies added-source biology. |
| Brev credits sent; AWS credits expected later | This describes credit provisioning, not an AWS deployment requirement. The excerpts do not supply dates from which to calculate availability. |

Those October 23 excerpts left the graph-versus-decisions choice unanswered.
The [additional organizer update received October 26](ORGANIZER_UPDATE_20261026.md)
now says subgraphs will be compared with the whole graph and asks to ideally send
both. In context, prepare both the resulting graph and an edge-decision ledger.
The specific baseline/version, comparison unit, scope, formats and confidence
handling remain unspecified. A numeric confidence requirement cannot be inferred
from the participant's question. Do not manufacture scores or use local review
states as gold labels.

The verified midpoint template is due EOD October 27, with final submission on
November 17. AWS credits have been received according to the user; deployment
is still untested and is not a newly stated judging requirement.

**Priority adjustment:** demonstrating biological value remains the main
unresolved scientific objective. The immediate pre-report work closes a complete
construction/export demonstration and starts a user walkthrough; those are
functionality and usability advances, not proof of biological improvement.
Reflect the organizer evaluation contract in the submission exports once
clarified. The [completed INMC/GO
comparison](evaluations/INMC_COMPARISON_20261023.md) is a complementary measured-PPI
study; it found no consistent hierarchy gain and does not stand in for the official Pharos evaluation.
If the gold set evaluates pruning rather than link prediction, these remain
separate evaluations. The INMC outcomes were opened after its full freeze and
prediction run; they are now consumed. Do not invent an official protocol while
the organizer contract is unknown or relabel this panel as unseen after tuning.

The [deterministic construction/publication flow](CONSTRUCTION.md) now accepts
1–25 exact protein accessions, reuses existing retrieval/normalization code and
publishes an inspectable graph, cited answer and replayable source-bound bundle
without an invented disease assertion. The
[real publication check](evaluations/CONSTRUCTION_PUBLICATION_20261023.md)
demonstrates that boundary. The optional [construction planner](CONSTRUCTION_AGENT.md)
now selects permitted retrieval requests and preserves its provenance through
the published graph. Local integration is tested. JSON v3 matched none of four
supported development requests, followed by one of four for tool V1. The
[latest tool V2 comparison](evaluations/construction_planner_tool_v2_20261026_summary.json)
matched three of four, while admitting two of eight unsupported requests. Keep
the planner experimental. The current UI/API now requires exact form choices,
shows them alongside the model proposal, blocks mismatches and requires explicit
plan review before execution. This wrapper retains the unchanged JSON v3 model
prompt/provider; tool V2 remains outside production execution. The live
comparison did not exercise the new guard, so its measured results remain
unchanged. The guard does not validate arbitrary free-text conditions. Actual
user usefulness and cohort-compatible
maintenance/evidence-action policies remain functional gaps.
AWS/Neptune, a UI rewrite and more agents are not prerequisites.

The [gold-reference handoff](GOLD_SET_INTERFACE.md) now covers source-bound graph
and decision exports plus exact alignment of a declared reference table. It
preserves raw labels, qualifications and unassessed edges. This implements source and decision handoff, not a complete submission:
the [retained graph and qualified source package](evaluations/SUBMISSION_DEMO_20261026.md)
are now materialized and verified. The unknown official schema/scoring contract
and biological validation gap remain. The [standard-export increment](STANDARD_EXPORT.md) adds a
bounded KGX Reactome projection while preserving the complete source bundle.
Official validator and JSONL round-trip checks are recorded, with the upstream
category-array schema and predicate-domain issues left explicit; full Biolink
conformance is not claimed.

The [Lambourne assay corroboration](evaluations/LAMBOURNE_CORROBORATION_20261025.md)
is complete under the frozen [reference/comparator decision](literature/REFERENCE_COMPARATOR_DECISION_20261025.md).
It retains all 3,222 nominations: 2,676 are assay eligible and 2,674 comparator
eligible. Detection is 334/1,966 (17.0%) among Pharos-represented pairs and 42/708
(5.9%) among resolved no-matches; without observed HuRI/INMC pair overlap, rates
are 74/1,619 (4.6%) and 16/650 (2.5%). Exact imported study lineage remains
unavailable, so these conditional assay results are not certified independent
validation or a test of Steward improvement. The panel is consumed; no new
prediction, enrichment or protocol tuning may treat it as unseen. The completed
[qualified assay publication](ASSAY_EVIDENCE.md) preserves all 3,222 observations
in a standalone immutable layer and offline viewer: 2,676 qualified observation
edges, 3,173 protein nodes and 546 excluded assays retained in the audit.
The 42 detected bounded no-matches are an inspection filter, not independently
validated new interactions. Study/construct context, nondetections and original
Pharos records remain explicit, without automatic acceptance or pruning. See the
[publication record](evaluations/ASSAY_EVIDENCE_PUBLICATION_20261025.md).
The [ordinary workbench attachment](ASSAY_WORKBENCH.md) now preserves selected
cohort observations, source-bound review and full run downloads. Qualified
gold-packet export now preserves those sources. KGX mapping and cohort
maintenance for attached runs remain unsupported.
This does not replace the organizer reference or incremental-prediction evaluation.

The [IntAct development flow](INTACT_EVIDENCE_WORKBENCH.md) now uses the same
attachment, review and export framework. A real four-protein Pharos run retains
its original graph and adds four separately qualified records across two pairs.
All four eligible records pass source-fidelity checks through a readable answer
and complete gold packet. These consumed positive co-IP records do not establish
biological accuracy, novelty or prediction gain. Four reserved interaction files remain
unopened; provenance/overlap assessment and final-study suitability remain open.

The [official XML development check](evaluations/INTACT_XML_PROVENANCE_20261026.md)
now verifies the richer provenance route on those four consumed studies.
Corresponding checked fields agree; two explicitly spoke-expanded RNA-containing
rows map to one three-participant XML interaction. The four eligible protein
records are unchanged. Experiment/figure context and a source-curation caveat
are preserved, without certifying study independence or biological accuracy.

The follow-up [development provenance audit](evaluations/INTACT_DEVELOPMENT_PROVENANCE_AUDIT_20261026.md)
now identifies three curated experiments behind the four eligible records and
closes the bounded development inventory with independence unverified.
[Final assessment rules](evaluations/INTACT_FINAL_EVALUATION_RULES_20261026.md)
are specified and metadata-checked; the executable full-flow freeze and reserved
overlap assessment remain pending. The assisted user correctly selected the
construct crosswalk and found its accession, then reported difficulty relating
the export to the app graph. UI guidance now explains whole-workspace versus
question-view scope; its independent usability effect is unmeasured.

## Functional coverage

| Function | Current implementation | Remaining gap |
|---|---|---|
| Ingest heterogeneous biomedical evidence | Scoped Pharos/CIViC retrieval, reusable adapters, exact-cohort publication with optional bounded model selection, qualified assay attachments and a frozen restricted learner projection | Latest experimental planner matched 3/4 supported development requests but admitted 2/8 unsupported requests; deployed source/study lineage remains unresolved |
| Filter for the question and limit graph size | Exact disease choice, scoped queries, relation/row budgets, coverage disclosures; explicit protein-cohort choices checked against model proposals with visible plan review | Arbitrary free-text conditions remain unverified; broader agent-controlled retrieval under explicit budgets |
| Normalize and trace assertions | Qualified assertions, stable source locators, original context, separate local review, immutable snapshots and bounded KGX export with the source bundle retained | Resolve documented standard-validation issues; complete source/study lineage only where authoritative metadata permits |
| Clean erroneous or irrelevant links | Structural checks, exact deduplication, explicit review states | Scientifically justified filtering with measured false removals; no automatic model pruning is enabled |
| Maintain the graph | Saved snapshots, explicit comparison and guarded review carryover | Cohort-compatible maintenance/evidence-action policy and controlled source-change/withdrawal validation |
| Compare baseline and enriched graphs | Frozen Pharos/GO projection, native PyKEEN four-arm/three-seed run, authenticated assay reconciliation and paired metrics on 1,751 measured pairs; completed Lambourne full-panel Pharos/assay corroboration | No consistent hierarchy gain. Lambourne corroboration does not establish independent improvement; both panels are consumed. A justified graph change, independent evaluation and official judging alignment remain |
| Explain and support users | Guided questions, compact graphs, deterministic cited summaries, source passports and context exports | Actual biomedical-user evaluation; source fidelity is not scientific truth |

The supplied judging weights are usability 40%, accuracy/pruning 30%, explainability 20% and standards 10%. Those weights make preservation, usable inspection, measured prediction/pruning and interoperability separate deliverables.

## Proposal commitments and implementation choices

| Promised capability | Current status |
|---|---|
| Plain-language/scoped question to graph and answer | Guided saved-graph queries plus exact-protein construction/publication and cited cohort answers. The UI/API now checks unchanged v3 proposals against explicit form choices and requires visible plan review. Experimental tool V2 remains outside production execution, with the same 3/4 supported and 2/8 unsupported-admitted development result. The new guard has local integration checks; live contribution, free-text semantic correctness and intended-user usefulness remain unestablished. |
| Qualified, versioned assertions and review lifecycle | Implemented local assertion identity, evidence revisions, review events and immutable runs. Local acceptance differs from upstream curation status. |
| CIViC, CPTAC/PDC and PubMed/PMC evidence | CIViC integration is active. Literature and processed CPTAC adapters remain reusable; general PDC-native ingestion and dependable automatic extraction are not implemented. |
| Entity and ontology harmonization | Supported explicit identifiers and registry mappings; unresolved/multiple mappings preserved. This is a bounded subset, not comprehensive HGVS/SO/ChEBI/NCIt/ECO normalization. |
| Biolink/LinkML, KGX/JSON-LD, SSSOM and PROV-style traces | Bounded KGX Reactome projection with source bundle, official checks and JSONL round trip. Category-array schema and predicate-domain findings remain explicit. Full conformance and formal SSSOM/PROV/JSON-LD delivery are not claimed. |
| Agent orchestration | Optional NeMo saved-graph query wrapper and bounded model-selected construction executed by deterministic code. An autonomous maintenance/research loop is not implemented. |
| Evidence strength and confidence | Source-native observations and qualifications are preserved. No validated combined confidence or certified independent-study count is available. |
| Reproducibility and deployment | Core Python app, tests, synthetic demo, Docker/Brev configuration and pinned optional model setup. An isolated committed-snapshot build/install with the declared backend and installed synthetic graph/answer/export replay passes; packaged UI assets are preserved. Actual GitHub clone, intended-user real-data replay and cloud deployment remain unverified. Real source data and historical runs remain local/ignored. |

Current substitutions are deliberate: the lightweight web UI fills the inspection role without Streamlit; local JSON-backed graphs support the bounded workload without Neptune; the tested NVIDIA model is served through vLLM rather than NIM. Installing proposed brands would not itself close a functional gap. AWS, OpenSearch or additional serving backends should be introduced only for a concrete requirement.

## Reuse decisions that guide the next increment

- **Measured task and learner:** the [INMC/PyKEEN review](literature/MEASURED_LINK_BENCHMARK_REUSE_20261022.md) checks experimental meaning, released artifacts, licenses and runtime. The [input-readiness audit](evaluations/INMC_INPUT_READINESS_20261022.md) records unresolved assay, identity and source-overlap issues before training.
- **Reference/comparator:** the [finite decision](literature/REFERENCE_COMPARATOR_DECISION_20261025.md) closes the import-lineage investigation as unresolved; the [baseline-only retrospective assay report](evaluations/LAMBOURNE_CORROBORATION_20261025.md) and [standalone qualified observation publication](ASSAY_EVIDENCE.md) are complete. Do not tune new prediction, enrichment or eligibility rules on this consumed panel. Source-preserving integration is not evidence of prediction gain; additional predictive enrichment remains unselected.
- **Evidence assessment:** the [IntAct/IMEx preparation](INTACT_FIDELITY_PREPARATION.md) pins eight publication artifacts and a frozen source-fidelity protocol, with a mandatory semantic amendment. Official-reader controls, four-study development inspection and the real workbench/answer/export comparison are complete. All four eligible development records pass source fidelity. The original implementation remains frozen at `bca13a7`. A separate [official XML provenance check](evaluations/INTACT_XML_PROVENANCE_20261026.md) now reconciles the consumed development rows with richer source context and explicit n-ary grouping. Four reserved interaction files remain unopened; shared-study provenance, pair overlap and final-path readiness remain unresolved. Biological accuracy and prediction gain remain unestablished.
- **Interoperability:** the [bounded export](STANDARD_EXPORT.md) uses existing [KGX](https://biolink.github.io/kgx/) checks and documents what remains unresolved. Continue to respect [Biolink qualifiers](https://biolink.github.io/biolink-model/association-examples-with-qualifiers/), [LinkML validation](https://linkml.io/linkml/data/validating-data.html) and [SSSOM](https://mapping-commons.github.io/sssom/) semantics. A passing round trip or a standard-looking label is not full conformance.
- **Additional graph sources:** ROBOKOP, OptimusKG and direct Reactome are conditional candidates. Existing Pharos content and upstream reuse must be checked first; another aggregator does not imply independent evidence. See the [integration review](literature/BIOMEDICAL_INTEGRATION_REVIEW_20261021.md).
- **Agent and cloud guidance:** NeMo and the organizer's Neptune examples may help orchestration and deployment, but generated example data must remain synthetic. Current data/query contracts remain the scientific boundary.

The submitted proposal copies differ in the usability answer: one later copy repeats an ontology list. The current product and planned user testing provide a concrete usability account regardless of that form discrepancy; this audit does not infer which copy was submitted.

The [build plan](BUILD_PLAN.md) is the active sequence. The [literature knowledge base](LITERATURE_REVIEW.md) preserves known limitations and reuse checks. Closed extraction, verifier and prompt-comparison sequences are historical evidence, not an active task queue.
