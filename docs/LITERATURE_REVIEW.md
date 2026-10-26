# Literature knowledge base for BioGraph Steward

**October 25 recency and validation follow-up:** a focused check of recent
primary work supports the design principles below, without demonstrating a
benefit for this implementation. This was not an exhaustive systematic update.

- [Brière et al., Bioinformatics, August 2026](https://academic.oup.com/bioinformatics/article/42/8/btag608/8767164)
  evaluate train/test redundancy and test-selection effects across biomedical
  graphs; performance on an independent Orphanet reference can be much worse
  than on conventional splits. The [author repository](https://github.com/galadrielbriere/data_leakage_kge_benchmark)
  provides an MIT-licensed implementation. This supports our source-overlap
  checks and restrained external-validity claims; it does not establish that
  our frozen panel is independent. The code was inspected as a methods source,
  not installed as a replacement learner or adopted as a new benchmark.
- [Wang et al., DeepEvidence, July 2026](https://www.nature.com/articles/s42256-026-01266-0)
  use question-driven exploration and explicit evidence graphs. Task-specific
  benchmarks and expert rubrics assess different capabilities separately;
  contextual conflict handling and uncertainty remain limitations. Our inference
  is that an evidence graph and bounded tool selection are defensible design
  choices. Their results do not transfer to our model, sources or task. Its
  [official code](https://github.com/RyanWangZf/BioDSA/tree/main/biodsa/agents/deepevidence)
  is a candidate for a future scoped reuse review, not a selected dependency.
- [Lambourne et al., April 2026](https://www.nature.com/articles/s41467-026-70942-x)
  distinguish interaction interpretations and evaluate experimental detection
  with assay-specific sensitivity. This supports preserving assay context and
  keeping nondetection separate from universal falsity. Reading public methods
  and aggregate findings does not make our panel prospectively hidden; no
  individual assay outcome table was opened in this follow-up.

The practical conclusion is to execute the frozen, bounded corroboration
assessment while closing engineering gaps separately. The [closure criteria](BUILD_PLAN.md#gap-closure-and-biological-validation)
distinguish code-controlled acceptance tests, source/standard dependencies and
the stronger reference requirements for demonstrating improvement.

**October 25 decisions:** the [export-standard investigation](literature/EXPORT_STANDARD_REUSE_20261025.md)
checks the actual pinned KGX/Biolink implementation, identifies reproduced
schema/domain limits and adopts plain interchange rows with complete evidence
sidecars. The [reference/comparator decision](literature/REFERENCE_COMPARATOR_DECISION_20261025.md)
closes the Pharos PPI import-lineage audit as unresolved and selects retrospective
assay corroboration against the frozen lookup, without certifying an independent
prediction test or selecting another enrichment. These are dated additions to
the earlier review, not a new literature census or biological result.

**October 23 implementation follow-through:** the [restricted Pharos/GO graph report](evaluations/INMC_PAIRED_GRAPH_20261023.md)
records the applied GAF-informed exclusions, original-identity masks, shared
graph vocabulary and native three-hop R-GCN checks. Two reproduced PyKEEN 1.11.1
integration issues use supported library paths, with pinned-source explanations.
This implements the selected bounded study; it does not expand the historical
literature census or establish biological improvement by itself.
The [completed comparison](evaluations/INMC_COMPARISON_20261023.md) subsequently
measured nearly unchanged AP with mixed seed effects. Hierarchy enrichment is
not promoted as an improvement; the consumed panel cannot support fresh tuning
claims.

**Repository scope note (October 22):** this is a dated source/methods review. Its historical observations remain useful; the [current build plan](BUILD_PLAN.md) supersedes old next-step proposals. Closed study implementations and reports are preserved in the [experiment archive](EXPERIMENT_HISTORY.md).

Review date: **October 21, 2026**. Status: structured literature and methods review, with primary papers, official documentation and artifact checks. It is not an exhaustive systematic review, an independent scientific audit of our graph, or a new performance result.

**October 22 follow-up:** the [INMC assay and identity review](evaluations/INMC_READINESS_FOLLOWUP_20261022.md) records primary-methods support for a complete-scored Y2H endpoint, official shared-gene/product semantics and identifier-history evidence. It also checks the 2026 experimental assessment of AI interactome mapping for assay sensitivity and source-independence limitations. These are additional dated sources outside the original 47-family census; no new biological performance result was generated.

**October 22 source and library follow-through:** the [GO qualification reuse review](literature/PHAROS_GO_QUALIFICATION_REUSE_20261022.md)
verifies the Pharos319/400 delivery boundary, missing annotation qualifications,
the official GAF representation/parser and known GO–PPI source confounding.
The [native PyKEEN context smoke](evaluations/PYKEEN_CONTEXT_SMOKE_20261022.md)
demonstrates separate adjacency and supervision factories, reserved-pair negative
filtering and fixed-pair scoring on invented data. These are source and
engineering findings, not an enriched biological graph or prediction result.

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

**October 23 external-reference follow-through (G03/G04/G10):** the
[Lambourne human panel audit](evaluations/LAMBOURNE_REFERENCE_AUDIT_20261023.md)
reproduced 3,222 published nominations without decoding assay outcomes. It found
647 pairs already represented in saved raw Pharos responses, 442 potential HuRI
matches and seven INMC overlaps; these counts overlap. Neither endpoint had
been queried for 2,330 pairs. The author repository history supplies the missing
assay export transformation, including failed-test states and sorted identity
semantics. A separate paper is therefore an external-study candidate, not an
automatically independent test. Provider-specific source lineage and coverage
remain unresolved; no model or new performance experiment was run.

**October 23 coverage follow-up:** the [focused PPI lookup](evaluations/LAMBOURNE_PHAROS_LOOKUP_20261023.md)
closes the unqueried-inventory gap: 3,172/3,173 exact resolutions and 2,325/3,222
represented pairs, with all source counts reconciled. The supported Pharos
pair-details and data-version queries were checked before proposing external
retrieval. Five sampled details recover explicit null/zero values but no study
lineage; the checked version response lacks PPI provider releases. Upstream
study provenance remains unresolved, and no missing score or pair was relabeled
as a negative. See that report for pinned official code, probes and limitations.

For each future increment, cite the relevant source IDs and record the verified remaining gap. Recheck upstream version-dependent facts when implementation begins. Add a dated note when new evidence changes a conclusion; preserve prior evaluations. Record whether artifacts were merely described, inspected, reproduced or evaluated on our task. A failed reproduction is a result to retain, not a reason to replace the benchmark repeatedly.

**October 25 assay follow-through (G03/G04/G10):** the
[completed Lambourne corroboration](evaluations/LAMBOURNE_CORROBORATION_20261025.md)
reused the official historical preprocessing, verified its nullable semantics
with pandas 1.4.3 on synthetic cases, then froze the comparator before opening
pair outcomes. All 3,222 nominations reconciled. Among eligible pairs,
334/1,966 Pharos-represented and 42/708 resolved no-match pairs were detected;
without the prespecified HuRI/INMC flags, the fractions were 74/1,619 and
16/650. These are local observations, not a literature-established effect.
They retain the documented distinction between assay detection, source
representation and biological truth. Imported-study independence remains
unresolved; no graph-change effect was tested. The public panel is now
consumed. A qualified assay evidence overlay is a concrete next candidate,
but its imported observations cannot also serve as its independent accuracy
test. This adds an execution record, not a new broad literature-search count.

**October 25 evidence-representation follow-through (G03/G04/G11):** the focused
[IMEx/PSI-MI reuse gate](literature/ASSAY_EVIDENCE_REUSE_20261025.md) confirmed the
existing method/participant/publication representation and conditional-negative
curation limits. The paper's IM-30553 deposition was checked through documented
public interfaces with a positive control; matching records were not returned,
without concluding that curation had not occurred. The
[bounded observation publication](evaluations/ASSAY_EVIDENCE_PUBLICATION_20261025.md)
therefore reuses the verified author tables, preserving all 3,222 observations
and their assay/construct/source qualifications. It introduces no new learned
score, pruning rule or benchmark. Its standalone inspection view makes source
context available; user benefit and independent biological improvement remain
unmeasured. This closes that finite implementation step rather than opening
another source/model search.

**October 26 product integration and public-reference decision:** the
[qualified workbench attachment](ASSAY_WORKBENCH.md) reuses that source
representation and the existing assertion lifecycle. Both endpoints must resolve
inside a declared live cohort; source material, failures and review bindings
remain intact. It adds no biological score or new prediction experiment. The
[finite public-reference audit](literature/PUBLIC_REFERENCE_OPTIONS_20261026.md)
selects IntAct/IMEx for bounded evidence-fidelity preparation. Public reference
data can support local assessment while organizer final labels remain hidden;
source overlap and endpoint compatibility still determine which scientific
claims are defensible. No new reference outcomes were downloaded in this audit.

No scheduled monitoring was created. The original broad review added documentation
only. Dated follow-through notes above disclose later execution and outcome
access; they do not change the original review's scope.

## Relationship to earlier project reviews

This review extends the [Pharos construction audit](PHAROS_CONSTRUCTION_AND_VALUE.md) and [scientific validity review](EXPERIMENT_HISTORY.md#reopening-an-archived-file "Archive file: docs/SCIENTIFIC_VALIDITY_REVIEW_20261021.md"). Historical implementation assessments and benchmark reports remain evidence of their dated state, not current completeness guarantees. The [CIViC curation audit](EXPERIMENT_HISTORY.md#reopening-an-archived-file "Archive file: docs/evaluations/CIVIC_CURATION_AUDIT_20261021.md") and [failed context pilot](EXPERIMENT_HISTORY.md#reopening-an-archived-file "Archive file: docs/evaluations/NLI4CT_CONTEXT_PILOT_20261021.md") supply local observations; literature findings do not retroactively change their outcomes.
