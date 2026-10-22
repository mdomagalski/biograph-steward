# Evaluation and scientific evidence quality — methods review

Reviewed October 21, 2026. This is the evaluation component of a scoped literature investigation, not a systematic review of all biomedical methods. Fourteen core source records are in [evaluation_sources_20261021.json](evaluation_sources_20261021.json). Published methods, official guidance and author artifacts are distinguished from our recommendations. No model was run, no reference was relabeled, and no reserved examples were inspected for this review.

## What we are evaluating

BioGraph Steward combines several tasks that need different references. **Biomedical knowledge integration** asks whether identities, relations, qualifications and provenance survive ingestion. **Scientific claim verification** asks whether specified evidence supports a statement. **Evidence synthesis** assesses what a body of relevant studies establishes for a defined question. **Biological prediction** asks whether a model generalizes to measured outcomes. A graph can pass the first task while failing any of the others.

The existing [scientific validity review](../EXPERIMENT_HISTORY.md#reopening-an-archived-file "Archive file: docs/SCIENTIFIC_VALIDITY_REVIEW_20261021.md"), [comparison protocol](../EXPERIMENT_HISTORY.md#reopening-an-archived-file "Archive file: docs/COMPARISON_PROTOCOL.md"), [source-verifier contract](../EXPERIMENT_HISTORY.md#reopening-an-archived-file "Archive file: docs/VERIFIER_PROTOCOL.md"), [benchmark preparation](../EXPERIMENT_HISTORY.md#reopening-an-archived-file "Archive file: docs/VERIFICATION_BENCHMARKS.md") and [CIViC curation audit](../EXPERIMENT_HISTORY.md#reopening-an-archived-file "Archive file: docs/CIVIC_CURATION_AUDIT.md") already establish important boundaries. The verified gap is implementation and reference coverage for the actual research question, not absence of any existing evaluation methodology. The literature does not justify inventing a single numerical score that conflates provenance, model confidence, study quality and biological truth.

## Core evidence map

| ID and source | Finding relevant to our decision | Boundary and reuse decision |
|---|---|---|
| EVAL01 — [Cochrane Handbook, Chapter 5](https://www.cochrane.org/authors/handbooks-and-manuals/handbook/current/chapter-05) | Evidence synthesis must link multiple reports belonging to a study; different reports can contain complementary or conflicting information. | Reuse study/report distinction and documented reconciliation. Matching PMIDs alone does not establish independent patients. |
| EVAL02 — [GRADE framework](https://pmc.ncbi.nlm.nih.gov/articles/2335261/) and [current Cochrane implementation](https://training.cochrane.org/handbook/current/chapter-14) | Certainty is assessed for a body of evidence about an outcome, considering bias, inconsistency, indirectness, imprecision and publication bias. Certainty and recommendation strength are distinct. | Use these dimensions when appropriate; do not assign automated GRADE ratings to arbitrary molecular edges. |
| EVAL03 — [RoB 2](https://www.riskofbias.info/welcome/rob-2-0-tool) | Established assessment is specific to randomized-trial results, with design-specific versions. | Import attributed assessments where available. A language model's judgment is not a validated RoB 2 assessment. Tool terms are CC BY-NC-ND 4.0. |
| EVAL04 — [CIViC curation guidance](https://docs.civicdb.org/en/latest/curating/assertions.html) | Assertions synthesize context-qualified EIDs using applicable clinical interpretation guidelines. Evidence levels and direction have separate meanings. | Preserve upstream scope and interpretation. An imported conclusion cannot also be independent gold for its reconstruction. |
| EVAL05 — [Brière et al., 2026](https://pubmed.ncbi.nlm.nih.gov/42623034/) | Biomedical KGE evaluation can leak through redundant train/test relations; performance on an independent Orphanet task dropped relative to usual splits. | Prioritize author split-audit methods. Degree alone did not explain predictions in their experiments: do not assume a universal mechanism. |
| EVAL06 — [Cappelletti et al., 2024](https://doi.org/10.1093/bioadv/vbae036) | Negative-example selection can inflate random-walk graph classification; degree-aware sampling addresses the tested bias. | Especially relevant: author code includes KG-IDG. The result is model/task/sampling dependent, not proof that all graph prediction is degree lookup. |
| EVAL07 — [Open Graph Benchmark / ogbl-biokg](https://ogb.stanford.edu/docs/linkprop/) | Official evaluation ranks known links against type-compatible sampled alternatives; BioKG uses random splits and includes mixed-confidence source types. | Useful infrastructure, not verified biological negatives or prospective discovery validation. Preserve official scores separately from task-specific splits. |
| EVAL08 — [SciFact](https://aclanthology.org/2020.emnlp-main.609/) | Expert-written claims are paired with abstract judgments and supporting rationales. | Appropriate for source-relative verification; supplied-document evaluation omits retrieval, and cannot establish clinical truth. Already used locally. |
| EVAL09 — [NLI4CT](https://aclanthology.org/2023.emnlp-main.1041/) | Trial inference and evidence selection are separate tasks. Gold-evidence-only baselines did not significantly improve inference in the original experiments. | Useful for trial binding and numerical reasoning. Binary labels do not supply a general NEI policy. Already used locally. |
| EVAL10 — [Evidence Inference 2.0](https://aclanthology.org/2020.bionlp-1.13/) | Comparative result interpretation is conditioned on intervention, comparator and outcome, with evidence annotations. | Reuse the task structure for relevant treatment questions. No significant difference is an outcome judgment, not insufficient information. |
| EVAL11 — [CIViC-Fact](https://pubmed.ncbi.nlm.nih.gov/41000838/) | Cancer-variant verification includes sentence evidence and expert review; the public report presents assistance to curator triage. | Closest domain fit, but benchmark version and label policy matter. The retrieved report is marked preprint; published performance is not our result. |
| EVAL12 — [Guo et al., 2017](https://proceedings.mlr.press/v70/guo17a.html) | Classifier probability calibration can improve with a fitted temperature on separate calibration data. | Reuse calibration evaluation before treating model scores probabilistically. Calibration does not fix incorrect evidence or distribution shift. |
| EVAL13 — [Geifman and El-Yaniv, 2017](https://papers.neurips.cc/paper_files/paper/2017/hash/4a8423d5e91fda00bb7e46540e2b0cf1-Abstract.html) | Selective classification evaluates error against the fraction of cases answered. | Compare systems at matched coverage. Image-classification results are not biomedical-verifier guarantees; semantic NEI is separate from abstention. |
| EVAL14 — [Angelopoulos and Bates, 2023](https://arxiv.org/abs/2107.07511) | Conformal methods construct prediction sets with stated coverage properties under assumptions about calibration/test data. | Candidate only after adequate separate calibration data and dependence analysis. Marginal coverage is not individual scientific truth or guaranteed subgroup coverage. |

The two graph-bias studies are complementary: one demonstrates sampling-dependent degree bias in a particular setting; the other finds no degree-only explanation for its evaluated KGE predictions. Our control design should diagnose the actual mechanism instead of assuming either result transfers unchanged.

NLI4CT's original paper explicitly states in §9.1 that reported checkpoints were selected for highest **test** F1. That published choice must not be copied into our evaluation protocol. Keep selection on development data and evaluate the frozen system on an unconsumed reference. This observation concerns the paper's reported baseline-selection procedure, not a new analysis of its held-out cases. See the [paper, §§9.1–9.3](https://aclanthology.org/2023.emnlp-main.1041.pdf).

## Controls to retain or adopt

These are project recommendations derived from the methods map, not claims that one publication provides a complete Steward protocol.

1. **Declare the unit and endpoint first.** Separate records, reports, studies, cohorts, qualified claims and user questions. Count source preservation at record level; evaluate claim support at claim/evidence level; assess answer utility per question. Treat study/cohort dependence in uncertainty estimation.
2. **Compare equal information as well as added information.** Use A: scoped Pharos; B: Pharos plus the same complete external source records in a simple view; C: those same inputs through Steward. A–C measures the combined addition. B–C isolates representation/workflow value. For biological prediction also retain added-source-only, coverage/degree and appropriate shuffled-feature controls with equal tuning budgets.
3. **Audit independent references.** Record who supplied judgments, exact release, label definitions, disagreement, source context, and training/development exposure. Upstream acceptance, a parser round trip and an AI-generated corruption test answer different questions. Flag suspected reference errors without silently changing gold after viewing predictions.
4. **Group related material before splitting.** Keep inverse/duplicate graph relations together where required. Keep paraphrases, claim families, reports and known shared studies together for inference assessment. Entity-disjoint and temporal evaluation test additional forms of generalization; neither automatically establishes independent underlying experiments. The existing [TDC split utilities](https://tdcommons.ai/functions/data_split/) provide cold-start and combination splits, while its fixed benchmark groups differ from freely chosen split settings.
5. **Do not turn unknowns into measured negatives.** Record absence, failed retrieval, source exclusion, insufficient evidence, an explicit negative assay and a contradictory finding separately. Sampled graph negatives support a declared ranking/classification protocol; they are not experimentally verified absence. For clinical predictive EIDs, [CIViC explicitly includes inconclusive results under Does Not Support](https://docs.civicdb.org/en/latest/model/evidence/direction.html).
6. **Report coverage and harm-relevant errors together.** Include all eligible questions, complete supported answers, unsupported claims, omitted qualifications, invalid responses and access failures. For verifiers, include class-wise errors and evidence completeness, then false support versus coverage. A model that answers nothing must not appear highly successful because it makes no positive claims.
7. **Use diagnostic comparisons before replacements.** A supplied-document test separates retrieval from interpretation. Oracle evidence on development cases can estimate a possible retrieval bottleneck, but is not deployable performance. Existing task-compatible author models should precede another custom prompt. Preserve all failed experiments and consumed-test status.
8. **Separate uncertainty types.** Data missingness, label disagreement, model probability, sampling intervals and certainty of the underlying science require different fields. Fit thresholds and calibrators outside final test data. No confidence method can compensate for an invalid reference or an unrecognized population change.

## Concrete gap register

| Gap | Current evidence/status | Existing method to reuse | Next completion criterion |
|---|---|---|---|
| Independent scientific-answer reference for our exact question | Source fidelity and benchmark agreement exist; whole-graph scientific accuracy is unset. | EVAL04, EVAL08–11; existing local reference/exposure manifests. | A fixed question scope with compatible attributed references, explicit unavailable labels and a reserved evaluation partition. |
| Study/cohort dependence across sources | Citation and trial IDs can flag possible overlap; metadata absence cannot establish independence. | EVAL01; existing CIViC source/trial inventory. | A study/report/cohort mapping with confirmed and unresolved dependencies; grouped analysis on those units. |
| Whole-context result binding | Existing records preserve qualifiers, but population, complete regimen, comparator, endpoint, time and denominators are not always structured. | EVAL10 and CIViC EID guidance. | Targeted source-context coverage report; no automatic inference of missing fields. |
| Provenance versus source reliability | Raw assertions and upstream curation are preserved; no universal risk-of-bias assessment exists. | EVAL02–04. | Display attributed assessment type, scope, author/version and unassessed status; do not fabricate comparable scores across study designs. |
| Reference quality and evolution | Known reviews include disagreement; model/task versions have different labels. | EVAL08–11; local amendment records. | Versioned label policy and discrepancy queue; any future re-adjudication disclosed and independent of candidate selection. |
| Generalization of biological prediction | Historical holdouts are consumed; retrospective features may postdate outcomes. | EVAL05–07 and TDC split utilities. | New declared endpoint plus relation/source/time/entity overlap audit and frozen fresh evaluation; no rerun presented as untouched. |
| Open-world missingness and negative sampling | Missing graph records cannot be treated as biological counterevidence. | EVAL06–07. | Negative provenance and sampling assumptions reported, alongside degree/coverage controls where relevant. |
| Software-added value | Imported reference-tuple recovery is an integration check. | Existing local three-arm comparison design, above. | Paired B–C comparison with identical evidence and reader/model budget, evaluating complete answers and errors. |
| Calibration and abstention | No verified deployment calibration follows from current small or exposed benchmarks. | EVAL12–14. | Enough independent calibration units, frozen operating point, and evaluation of risk/coverage under relevant scope changes. |
| Reuse readiness | Public artifacts exist but differ in runtime and license. | Registry's artifact/license fields. | Pin versions and verify task, preprocessing, metrics, permissions and exposure before execution; avoid installing every candidate now. |

## Applying clinical evidence frameworks without misusing them

Clinical synthesis frameworks help us ask whether a result applies to the requested population, intervention and outcome. They do not supply a universal hierarchy for every protein interaction, binding assay, gene-expression observation or mechanistic claim. RoB 2 is not an assay-quality rubric. GRADE certainty is not a softmax probability. A curated variant-actionability tier is not interchangeable with either. For molecular experiments, the relevant source's assay methods and curation rules need their own review; that is an explicit remaining knowledge gap, not permission to invent a conversion formula.

This distinction also explains why source-supported text can be scientifically weak: an accurate summary may faithfully describe a biased, indirect or inconclusive study. Conversely, a useful mechanistic experiment may be inappropriate evidence for a clinical efficacy claim. Keep the claim's scope and the evidence assessment's scope visible.

## Reuse priorities

**First:** consolidate reference/exposure accounting, study identity and the equal-information comparison using existing local machinery. This requires no GPU or model change. **Next, conditional on the remaining task:** assess the published verifier/extraction baselines already identified, with unchanged failed experiments as historical evidence. **For a renewed prediction task:** adapt established leakage and sampling controls before selecting a model. **Later:** calibration or conformal methods after a suitable independent calibration set exists. None of these methods licenses automatic scientific approval of graph edges.

Author code availability is not execution readiness. The calibration demonstration repository explicitly says it is unmaintained and targets PyTorch 0.3. The KG leakage code describes a Python 3.10/TorchKGE/PyG workflow; the negative-sampling code uses GRAPE and GPL-3.0. These are reasons for bounded compatibility review, not ad hoc reimplementation. See the registry for exact links and unresolved permissions.

## Search record and limits

Search date: October 21, 2026. Discovery used web search across PubMed/PMC, Bioinformatics/Bioinformatics Advances, BMJ/Cochrane, ACL Anthology, PMLR/NeurIPS/arXiv, and official project documentation/repositories. This was not a direct systematic MEDLINE/Embase export or exhaustive citation-network crawl. General-result pages and secondary summaries were used only to locate primary or official sources. Repository READMEs, license metadata and method documents were inspected; benchmark examples and label files were not opened.

Exact discovery queries included:

- `site.academic.oup.com bioinformatics btag608 data leakage knowledge graph biomedical`
- `site.cochrane.org handbook chapter 5 multiple reports study unit`
- `site.bmj.com GRADE emerging consensus rating quality evidence strength recommendations 2008`
- `site.bmj.com RoB 2 revised tool assessing risk of bias randomised trials 2019`
- `"btag608" biomedical knowledge graph leakage`
- `"GRADE: an emerging consensus" quality evidence recommendations 2008`
- `"Therapeutics Data Commons" 2021 datasets benchmarks github license`
- `"Open Graph Benchmark" ogbl biokg negative sampling license`
- `"CIViC-Fact" scientific claim verification 2025 paper`
- `site.proceedings.mlr.press "On Calibration of Modern Neural Networks"`
- `"Selective Classification for Deep Neural Networks" github 2017`
- `"Conformal Prediction: A Gentle Introduction" Angelopoulos Bates 2023 exchangeability`
- `site.github.com NLI4CT "License" Mael Jullien SemEval`
- `site.academic.oup.com/bioinformatics/article/42/8/btag608 "leakage" "independent"`
- `site.cochrane.org handbook chapter14 certainty risk bias inconsistency indirectness imprecision publication bias`
- `"Benchmarking the impact of data leakage" "independent" "cold"`
- `"Benchmarking the impact of data leakage" "DL1" "DL2"`
- `biomedical knowledge graph evaluation negative sampling open world leakage benchmark primary study`
- `"Node-degree aware edge sampling" full text github`
- `"Node-degree aware edge sampling" doi`
- `"Benchmark datasets for biomedical knowledge graphs with negative statements" github`

Primary links already recorded in local methods documents were followed directly for SciFact, NLI4CT, Evidence Inference and CIViC. Fourteen core sources were selected for direct relevance, established task definitions or reusable controls; this count is a reading-map inventory, not a PRISMA screening count. Cochrane chapters and official artifacts are grouped with their relevant source record rather than inflated into separate papers. TDC is a supplementary implementation link, not a fifteenth core source.

Some publisher full-text routes returned access errors. For EVAL05–06, claims here rely on PubMed's author abstracts and official repositories, not an asserted complete full-text review; the degree-aware paper's complete methods remain an adoption prerequisite. RoB 2's tool site and indexed paper summary were accessible, but direct BMJ full text was blocked. For NLI4CT the full paper's experimental sections were inspected. Conformal assumptions were checked in the author's full-text version. No systematic retraction/correction sweep, exhaustive new-model survey, independent dual-review screening or formal risk-of-bias appraisal of all methodological papers was performed. License summaries are scoped observations, not blanket redistribution clearance.
