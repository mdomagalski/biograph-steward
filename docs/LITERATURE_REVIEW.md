# Literature knowledge base for BioGraph Steward

**Repository scope note (October 22):** this is a dated source/methods review. Its historical observations remain useful; the [current build plan](BUILD_PLAN.md) supersedes old next-step proposals. Closed study implementations and reports are preserved in the [experiment archive](EXPERIMENT_HISTORY.md).

Review date: **October 21, 2026**. Status: structured literature and methods review, with primary papers, official documentation and artifact checks. It is not an exhaustive systematic review, an independent scientific audit of our graph, or a new performance result.

## Purpose and decision

Build a durable account of what is already understood before extending BioGraph Steward. Our task is best described as **evidence-aware biomedical knowledge graph curation and maintenance**, with components for semantic integration, source-grounded claim verification and question answering. Evidence synthesis and biological prediction are additional tasks with different references and success criteria.

The literature supports our focus on qualified assertions, provenance and bounded questions. It does not support assuming that a larger graph, a valid schema, more citations, or another prompt makes the answers scientifically reliable. The next implementation decision should follow a source-to-capability crosswalk and a declared evaluation target. A broad data import or further model tuning is not a result of this review.

## How to use this knowledge base

Start with the task map and gap register below. Follow the relevant topic review for primary sources and artifact limitations. Before reusing a method, check its exact input/output contract, current release, license, dependencies, training exposure and evaluation unit. Report whether a proposed fix addresses a known method limitation, a demonstrated integration error, or an untested hypothesis.

| Review | What it answers |
|---|---|
| [Biomedical integration](literature/BIOMEDICAL_INTEGRATION_REVIEW_20261021.md) | Pharos construction and releases, entity identity, ontology mappings, source overlap, provenance and existing KG tools |
| [Scientific claim verification](literature/SCIENTIFIC_CLAIM_VERIFICATION_REVIEW_20261021.md) | Retrieval, context extraction, evidence selection, entailment, abstention, published models and agent interfaces |
| [Evaluation and evidence quality](literature/EVALUATION_AND_EVIDENCE_QUALITY_REVIEW_20261021.md) | Public references, evidence grading, study dependence, leakage, sampling, calibration and incremental value |
| [Evidence models and review method](literature/EVIDENCE_MODELS_AND_REVIEW_METHOD_20261021.md) | ECO, SEPIO, GA4GH VA-Spec, scientific argument models and limits of this literature search |

The [source index](literature/SOURCE_INDEX_20261021.md) contains **47 distinct source families** across 51 topic entries; four resources recur in the verification and evaluation tracks. These include papers, standards and official tools, rather than 47 fully read journal articles. The companion JSON registries preserve stable source IDs, primary URLs, artifact links, checked findings, limitations and reuse status. They contain concise research notes, not copies of articles. Search strings and access limits are recorded in the topic reviews. Research was conducted with AI assistance and checked against accessible primary sources; it has not received independent expert review.

## Distinguish the tasks before measuring improvement

| Task | Unit and question | Suitable evidence of success | Does not establish |
|---|---|---|---|
| Semantic integration | Does this record refer to the intended gene, protein, isoform, variant, disease and therapy? | Versioned identity references; incorrect merges, unresolved mappings and qualification loss | That a correctly linked claim is true |
| Source fidelity | Did we preserve the source observation and its context? | Record/span comparisons; study/arm/outcome binding; retained negation, uncertainty and units | That the original study is unbiased or replicable |
| Claim verification | Does the supplied evidence support, contradict or leave this claim unresolved? | Task-matched expert judgments; false support, omissions and coverage; justified evidence selection | Consensus across the literature or clinical usefulness |
| Evidence synthesis | What conclusion is warranted across comparable studies? | Question-specific interpretation framework, study linkage, design/risk-of-bias and uncertainty assessment | A universal confidence value for every graph edge |
| Biological prediction | Does enrichment improve a specified measured outcome? | Leakage-controlled, paired baseline comparison on independent outcomes | A gain inferred from added nodes or citations |
| Maintenance and usability | Can a researcher inspect and update the answer efficiently? | Correct change impact, review continuity, task completion and user evaluation | Biological accuracy inferred from a successful UI |

These distinctions synthesize the reviewed methods; they are not proposed new ontologies. In particular, our application's review state, an upstream curation status, a source's evidence level, a verifier label and a calibrated prediction probability must remain separate.

## Findings that change our choices

**Check upstream versions and semantics before assuming a missing capability.** Our saved inputs identify Pharos319; official Pharos400 documentation now exists. The integration review also identifies normalization defaults that can conflate genes with proteins. These are reasons for version and configuration checks, not evidence that they caused our previous model failures. [Pharos400](https://opendata.ncats.nih.gov/public/pharos/pharos400_readme.html); [integration review](literature/BIOMEDICAL_INTEGRATION_REVIEW_20261021.md).

**Reuse evidence models before expanding our custom contract.** [ECO](https://evidenceontology.org/) and [GA4GH VA-Spec](https://va-spec.ga4gh.org/en/1.1.0/) offer distinct representation layers. A small field crosswalk could reveal which existing slots are adequate and which qualifications we actually lack. Schema adoption would still require version-specific validation and would not validate the biology.

**Treat published tools as task-specific candidates.** The verification review covers existing source retrieval, three-way claim verification, intervention/comparator/outcome methods and the official CIViC agent interface. An interface can simplify access without expanding source coverage; a benchmark winner can still have the wrong label space. We should assess these candidates against the deterministic workflow before developing another agent or extractor.

**More relevant text is not a complete solution to reasoning errors.** The [NLI4CT paper](https://aclanthology.org/2023.emnlp-main.1041.pdf) reports limited benefit from gold-evidence restriction for its tested models. Our failed context-prompt pilot therefore has a known research backdrop, but the paper does not identify the cause of our particular errors. Model interpretation, arm binding, numerical operations and reference quality still require separate diagnosis.

**Count underlying studies, not appearances of the evidence.** Publications, database entries and aggregator names can repeat the same experiment or cohort. Provenance standards help represent the chain; they cannot reconstruct missing cohort identity automatically. Our existing PMID and trial-link groups are dependence clues, not certified independent evidence counts. See the [evaluation review](literature/EVALUATION_AND_EVIDENCE_QUALITY_REVIEW_20261021.md).

**Evaluate the contribution of the software separately from access to new information.** Compare Pharos alone, Pharos plus complete source records, and Steward operating on the same records. That design tests whether the qualified graph and summaries add value beyond supplying CIViC or other data. It is our proposed evaluation design, not a published result for Steward.

## Knowledge-gap register

“Known” below means documented in sources or observed locally, not solved. “Untested” means there is a plausible next check, not a diagnosed cause. All proposed checks remain future work.

| Gap | Status and evidence | Existing capability to inspect first | Smallest useful next check |
|---|---|---|---|
| G01 — Release coverage and identity changes | Observed: saved Pharos319 inputs; Pharos400 release described upstream | Official canonical comparison and versioned identifier sources | Read-only mapping/TDL comparison for our 512-gene panel; classify replacements and ambiguity |
| G02 — Gene/protein/isoform or chemical conflation | Known normalization design choice; effect on our scope untested | Gilda custom grounders, Translator Node Normalization and SSSOM | Fixed identity panel with explicit settings; measure false merges and unresolved results |
| G03 — Missing GO/PPI/assay qualifications | Observed in retrieved fields; underlying availability incomplete | Source-specific APIs, GO relations/evidence codes, Biolink/PROV/ECO | Trace a small set of existing records to upstream evidence; distinguish missing fields from missing studies |
| G04 — Independent study/cohort identity | Partial publication/trial links; unresolved across sources | CIViC source metadata, trial registries and established study-linkage practice | Trace known trial IDs and shared publications; report unresolved overlap without inventing study counts |
| G05 — Complete claim context | Observed extraction/binding failures | Evidence Inference/clinical extraction task contracts and upstream structured fields | Confirm population, full therapy, comparator, outcome, time and units for a bounded development set |
| G06 — Unsupported versus contradicted | Known label-contract mismatch across datasets | CIViC-Fact, SciFact/MultiVerS and source-specific semantics | Document compatible labels and references before selecting a verifier |
| G07 — Numeric and trial-arm inference | Observed model errors; root causes not isolated | NLI4CT published diagnostics and source-bound evidence annotations | Separate retrieval, binding and arithmetic controls; reserve unseen study groups before intervention |
| G08 — Scientific evidence strength | Not established by our current automated judgments | CIViC interpretation guidance; appropriate study-design frameworks | Define the exact claim and evidence unit; identify public assessments that actually cover it |
| G09 — Reference coverage and disagreement | Public labels exist but do not audit every current CRC assertion | Public expert corpora and upstream interpretation records | Map reference availability, disagreement, exposure and exclusions; keep unlabeled items visible |
| G10 — Leakage and popularity shortcuts | Known risk; not a universal explanation for our results | Biomedical leakage benchmarks, degree-aware controls, grouped/temporal splits | Audit equivalent/reverse relations, shared studies, target selection and negative-sampling policy |
| G11 — Incremental product value | Qualified information represented; independent answer benefit pending | Simple source-record baseline plus current deterministic workflow | Freeze question set and compare equal-information answering, support and qualification preservation |
| G12 — Confidence and abstention | Source confidence/model confidence/reference insufficiency are different | Calibration and selective-prediction methods | Evaluate errors at matched coverage; choose thresholds only on development data |
| G13 — Update/retraction propagation | Snapshot maintenance exists; general real-world behavior not established | PROV revision concepts and source change metadata | Separate changed content, query-scope absence, upstream withdrawal and paper retraction |
| G14 — Agent/tool choice | Bounded planner exists; newer upstream tooling found | Official CIViC MCP and existing APIs | Contract/coverage comparison against deterministic calls before any replacement |
| G15 — Deployment and artifact rights | Portability exists; candidate compatibility varies | Official release metadata and per-artifact terms | Pin runtime, resource needs and licenses for one selected candidate; do not infer data rights from code license |

No finite review prepares us for every limitation. Unresolved areas include unavailable full text/tables, non-public negative results, undocumented cohort reuse, evolving biology, incomplete model-training histories and expert disagreement. Preserve these as uncertainties rather than fill them with an agent's confidence score.

## Prioritized follow-through

**October 22 graph-task follow-through:** the [measured relationship reuse audit](literature/MEASURED_LINK_BENCHMARK_REUSE_20261022.md) compares public experimental panels and existing graph learners. It conditionally selects INMC's measured PPI panel and records successful PyKEEN R-GCN/ComplEx runtime checks on non-biomedical data. The archived labels have not been inspected individually; assay-code, identity and source-leakage checks precede any biological training. This is a new task-specific audit, not an update to the 47-source-family count above or evidence of scientific improvement.

**First completed follow-through (October 21):** a [ten-record CIViC source-to-answer trace](EXPERIMENT_HISTORY.md#reopening-an-archived-file "Archive file: docs/evaluations/CIVIC_ANSWER_TRACE_20261021.md") verified preservation of the sampled source context and identified missing display-cap disclosure in answer exports. The repair uses existing counts and annotations; it does not add biomedical inference. The audit also records prose-only and missing study details. It covers part of G05/G11, not the whole gap register.

1. **Complete a capability crosswalk before more modeling.** Map existing source fields, our assertion contract and review states against the relevant standards and upstream tools. Use a few representative records, including ambiguity and missing context. The output should identify exact preserved, lost, absent and inapplicable fields.
2. **Perform the bounded Pharos release audit.** A version comparison is warranted; migration of the whole graph is not implied. Keep the frozen comparison baseline intact.
3. **Choose one demonstrated gap and its published baseline.** For retrieval, compare the official CIViC interface and our direct API. For three-way source verification, assess a compatible verifier and its exposure. For evidence extraction, verify study/arm bindings before adding numerical tools. Do not run all branches because tools are available.
4. **Freeze the comparison before generating new outcomes.** Specify question population, evidence access, reference unit, grouped partitions, metrics and acceptable coverage. Preserve all failed experiments and consumed holdouts.
5. **Measure software value and biological value separately.** Complete the equal-information answer comparison for the product. Pursue the challenge's measured graph task with its own labels and controls when that endpoint is specified.

This sequence proposes research-led checks. It does not authorize claims of improved scientific accuracy and does not promise that a particular candidate will outperform the current implementation.

## Maintenance rule for this knowledge base

For each future increment, cite the relevant source IDs and record the verified remaining gap. Recheck upstream version-dependent facts when implementation begins. Add a dated note when new evidence changes a conclusion; preserve prior evaluations. Record whether artifacts were merely described, inspected, reproduced or evaluated on our task. A failed reproduction is a result to retain, not a reason to replace the benchmark repeatedly.

No scheduled monitoring was created. This review added documentation only: no model execution, compute start, graph migration, new biomedical assertion acceptance or reserved-label inspection.

## Relationship to earlier project reviews

This review extends the [Pharos construction audit](PHAROS_CONSTRUCTION_AND_VALUE.md) and [scientific validity review](EXPERIMENT_HISTORY.md#reopening-an-archived-file "Archive file: docs/SCIENTIFIC_VALIDITY_REVIEW_20261021.md"). Historical implementation assessments and benchmark reports remain evidence of their dated state, not current completeness guarantees. The [CIViC curation audit](EXPERIMENT_HISTORY.md#reopening-an-archived-file "Archive file: docs/evaluations/CIVIC_CURATION_AUDIT_20261021.md") and [failed context pilot](EXPERIMENT_HISTORY.md#reopening-an-archived-file "Archive file: docs/evaluations/NLI4CT_CONTEXT_PILOT_20261021.md") supply local observations; literature findings do not retroactively change their outcomes.
