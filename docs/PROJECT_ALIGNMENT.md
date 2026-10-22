# Current project alignment

Assessment updated October 22, 2026, against the organizer materials and proposal supplied by the user. This is a functional crosswalk, not a claim of organizer approval. Older assessments and experiment implementations are on the [archive branch](EXPERIMENT_HISTORY.md).

## Organizer requirements

The challenge asks for an agent-built contextualized graph and the **same graph-learning method on baseline and enriched graphs to predict held-out experimentally measured relationships**. No separate organizer dataset was supplied. Current graph size, verifier scores and export quality do not demonstrate that required prediction gain.

| Function | Current implementation | Remaining gap |
|---|---|---|
| Ingest heterogeneous biomedical evidence | Scoped Pharos and bounded CIViC retrieval; reusable literature, CPTAC and identity adapters | A declared measured relationship task and consistent task-specific context |
| Filter for the question and limit graph size | Exact disease choice, scoped queries, relation/row budgets, coverage disclosures | Broader agent-controlled retrieval under explicit budgets |
| Normalize and trace assertions | Qualified assertions, stable source locators, original context, separate local review and immutable snapshots | Complete source/study lineage and qualified formal standard validation |
| Clean erroneous or irrelevant links | Structural checks, exact deduplication, explicit review states | Scientifically justified filtering with measured false removals; no automatic model pruning is enabled |
| Maintain the graph | Saved snapshots, explicit comparison and guarded review carryover | Prospective source-change/withdrawal validation and broader maintenance workflow |
| Compare baseline and enriched graphs | INMC preparation and upstream PyKEEN runtime checks | Frozen assay/label/source policy, biological training and matched results |
| Explain and support users | Guided questions, compact graphs, deterministic cited summaries, source passports and context exports | Actual biomedical-user evaluation; source fidelity is not scientific truth |

The supplied judging weights are usability 40%, accuracy/pruning 30%, explainability 20% and standards 10%. Those weights make preservation, usable inspection, measured prediction/pruning and interoperability separate deliverables.

## Proposal commitments and implementation choices

| Promised capability | Current status |
|---|---|
| Plain-language/scoped question to graph and answer | Two guided query families and one bounded model planner over saved graphs. Broader question-to-retrieval construction is incomplete. |
| Qualified, versioned assertions and review lifecycle | Implemented local assertion identity, evidence revisions, review events and immutable runs. Local acceptance differs from upstream curation status. |
| CIViC, CPTAC/PDC and PubMed/PMC evidence | CIViC integration is active. Literature and processed CPTAC adapters remain reusable; general PDC-native ingestion and dependable automatic extraction are not implemented. |
| Entity and ontology harmonization | Supported explicit identifiers and registry mappings; unresolved/multiple mappings preserved. This is a bounded subset, not comprehensive HGVS/SO/ChEBI/NCIt/ECO normalization. |
| Biolink/LinkML, KGX/JSON-LD, SSSOM and PROV-style traces | Some labels and local provenance/mapping records exist. Full versioned conformance and qualification-preserving standard exports remain pending. |
| Agent orchestration | Optional NeMo wrapper around one bounded planner/query workflow. A governed construction/maintenance loop is still missing. |
| Evidence strength and confidence | Source-native observations and qualifications are preserved. No validated combined confidence or certified independent-study count is available. |
| Reproducibility and deployment | Core Python app, tests, synthetic demo, Docker/Brev configuration and pinned optional model setup. Real source data and historical runs remain local/ignored. |

Current substitutions are deliberate: the lightweight web UI fills the inspection role without Streamlit; local JSON-backed graphs support the bounded workload without Neptune; the tested NVIDIA model is served through vLLM rather than NIM. Installing proposed brands would not itself close a functional gap. AWS, OpenSearch or additional serving backends should be introduced only for a concrete requirement.

## Reuse decisions that guide the next increment

- **Measured task and learner:** the [INMC/PyKEEN review](literature/MEASURED_LINK_BENCHMARK_REUSE_20261022.md) checks experimental meaning, released artifacts, licenses and runtime. The [input-readiness audit](evaluations/INMC_INPUT_READINESS_20261022.md) records unresolved assay, identity and source-overlap issues before training.
- **Interoperability:** inspect [Biolink qualifiers](https://biolink.github.io/biolink-model/association-examples-with-qualifiers/), [LinkML validation](https://linkml.io/linkml/data/validating-data.html), [KGX](https://biolink.github.io/kgx/) and [SSSOM](https://mapping-commons.github.io/sssom/). A label resembling a standard is not conformance.
- **Additional graph sources:** ROBOKOP, OptimusKG and direct Reactome are conditional candidates. Existing Pharos content and upstream reuse must be checked first; another aggregator does not imply independent evidence. See the [integration review](literature/BIOMEDICAL_INTEGRATION_REVIEW_20261021.md).
- **Agent and cloud guidance:** NeMo and the organizer's Neptune examples may help orchestration and deployment, but generated example data must remain synthetic. Current data/query contracts remain the scientific boundary.

The submitted proposal copies differ in the usability answer: one later copy repeats an ontology list. The current product and planned user testing provide a concrete usability account regardless of that form discrepancy; this audit does not infer which copy was submitted.

The [build plan](BUILD_PLAN.md) is the active sequence. The [literature knowledge base](LITERATURE_REVIEW.md) preserves known limitations and reuse checks. Closed extraction, verifier and prompt-comparison sequences are historical evidence, not an active task queue.
