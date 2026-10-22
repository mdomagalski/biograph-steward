# Scientific claim verification and biomedical evidence processing

Reviewed October 21, 2026. This is a structured landscape review, not an exhaustive systematic review or a new model evaluation. It covers 14 primary method/resource publications and their official artifacts. No new benchmark labels were consumed, models executed, references relabeled, or graph records changed. The companion registry is [verification_sources_20261021.json](verification_sources_20261021.json).

## What our task is called

BioGraph Steward combines **biomedical knowledge integration**, **scientific claim verification**, and **evidence synthesis support**. These are separate tasks with different references:

| Task | Question being answered | Appropriate evidence of success |
|---|---|---|
| Retrieval | Did we find the relevant source records and passages? | Relevant-document/passage recall under a fixed corpus, query and access policy |
| Extraction and context binding | Which population, intervention, comparator, outcome and result belong together? | Correct spans and complete relations, retaining study/arm/time/unit identity |
| Source-relative verification | Does this supplied evidence support, contradict, or leave the claim unresolved? | Independent claim–evidence judgments, class-specific errors and coverage |
| Scientific appraisal | How credible and applicable is the underlying finding? | Study-design and risk-of-bias assessment; population and endpoint applicability |
| Synthesis | What conclusion follows across the eligible body of evidence? | Correct treatment of disagreement, uncertainty, dependence and missing studies |
| Biological prediction | Does the enriched graph improve prediction of a specified outcome? | Separate experimental/clinical reference and appropriate held-out split |

This decomposition is our synthesis of the sources below, not a claim that any single publication implements the whole workflow. A correct citation can support a biased study's statement. An entailed sentence can omit a crucial qualification. Several database rows can originate from the same trial. These are reasons to retain separate measures rather than collapse everything into a single scientific-accuracy score.

## Primary source map

| ID | Publication and checked contribution | What it does not establish for Steward |
|---|---|---|
| VER01 | [SciFact, 2020](https://aclanthology.org/2020.emnlp-main.609/): expert-authored scientific claims, abstract evidence and sentence rationales establish a useful retrieval-plus-verification task. | Abstract-relative labels do not establish population-level clinical truth or complete literature coverage. |
| VER02 | [SciFact-Open, 2022](https://aclanthology.org/2022.findings-emnlp.347/): expanding retrieval to 500,000 abstracts exposes generalization loss and evidence supporting only a restricted version of a claim. | Pooled judgments are not exhaustive annotation of every possible evidence document. |
| VER03 | [MultiVerS, 2022](https://aclanthology.org/2022.findings-naacl.6/): joint stance and rationale selection use the full supplied document context. | Its abstract-oriented evidence units do not validate full-paper table reasoning, trial-arm arithmetic or our CRC questions. |
| VER04 | [Evidence Inference 2.0, 2020](https://aclanthology.org/2020.bionlp-1.13/): inference is explicitly conditioned on intervention, comparator and outcome, with supporting evidence. | Increase/decrease/no significant difference are effect-direction labels; no significant difference is not an insufficient-information label. |
| VER05 | [EBM-NLP, 2018](https://aclanthology.org/P18-1019/): approximately 5,000 trial abstracts provide population/intervention/outcome span annotations. | Finding mentions is not the same as binding a result to the right arm; comparator mentions are within the intervention representation. |
| VER06 | [NLI4CT, 2023](https://aclanthology.org/2023.emnlp-main.1041/): trial-section inference and evidence selection include numerical and cross-trial challenges. Gold-evidence-only baselines did not significantly solve inference. | Binary entailment/contradiction does not validate abstention or a three-way scientific verifier. |
| VER07 | [NLI4CT-P, 2024](https://aclanthology.org/2024.semeval-1.271/): perturbations distinguish answer stability from responsiveness to meaning changes. | Perturbations share roots with the original test. Neutrality is a benchmark convention, particularly for appended definitions. |
| VER08 | [CIViC-Fact, 2025 preprint](https://pmc.ncbi.nlm.nih.gov/articles/PMC12458922/): structured cancer-variant claims, curated source selections, revision histories and augmentation address curation auditing. | Benchmark agreement, curation revisions and scientific contradiction are not interchangeable. Version-specific labels matter. |
| VER09 | [MedCPT, 2023](https://doi.org/10.1093/bioinformatics/btad651): PubMed-log-trained query/article encoders and a cross-encoder provide biomedical retrieval and reranking. | Relevance scores are not entailment scores, study-quality scores or calibrated probabilities of truth. |
| VER10 | [CliniFact, 2025](https://doi.org/10.1038/s41597-025-04417-x): claims derived from clinical hypothesis-testing results offer another clinical-research task. | It is not yet qualified as an independent reference for our variant–therapy task; construction, class mapping and study overlap need inspection. |
| VER11 | [MS², 2021](https://aclanthology.org/2021.emnlp-main.594/): review-linked study collections support multi-document summarization research. | A generated review summary is not an automatic evidence-grade judgment or meta-analysis. |
| VER12 | [Medical summary metric audit, 2023](https://aclanthology.org/2023.acl-long.549/): common automatic metrics disagreed with human quality rankings on evaluated medical summaries. | ROUGE/BERTScore or an unvalidated model judge cannot substitute for demonstrated claim-level fidelity. |
| VER13 | [RobotReviewer evaluation, 2015/2016](https://pmc.ncbi.nlm.nih.gov/articles/PMC4713900/): predicts risk-of-bias domains and extracts justification text from trial reports. | This is assistance for appraisal, not a source-truth oracle; original judgments lagged the human comparison. |
| VER14 | [CIViC MCP, 2026](https://doi.org/10.1093/bioadv/vbag209): an upstream natural-language interface exposes curated CIViC evidence and assertions. | Retrieving curated interpretations is not independently verifying their publications, and tool result limits can affect completeness. |

## Reuse assessment

**MultiVerS is a concrete candidate, not a new discovery or an installed replacement.** Its [official repository](https://github.com/dwadden/multivers) links checkpoints and training/inference code; the code is MIT licensed. Requirements pin Python 3.8-era dependencies, including Torch 1.7.1 and Transformers 4.2.2. Training includes FEVER, weak PubMedQA/Evidence Inference supervision and target datasets such as SciFact. Exact checkpoint membership and preprocessing must be audited. Its fit is better for the three-way stance-plus-rationale contract than a binary NLI head, but transfer remains untested.

**Evidence Inference supplies an established context-binding task.** [Code and annotation files](https://github.com/jayded/evidence-inference) are available, with an MIT code license; end-to-end compatibility and downloadable inference weights were not verified. It is a candidate for a bounded comparative-outcome task, not a universal parser. The [MS² implementation](https://github.com/allenai/ms2) links trained artifacts but explicitly drops the comparator in its adapted Evidence Inference task. That adaptation must not be imported unchanged to fix our comparator-binding errors. MS² code is Apache-2.0; the data have separate Semantic Scholar terms.

**MedCPT is a retrieval baseline worth considering if retrieval is the measured bottleneck.** [NCBI's repository](https://github.com/ncbi/MedCPT) provides three public checkpoints and a public-domain software/database notice. Its underlying PubMed user logs are not released for privacy reasons, limiting complete training-membership inspection. Our existing lexical/full-text retrieval should remain the baseline; adding this model would not by itself verify a claim.

**CIViC MCP deserves an upstream capability comparison before custom tools.** The [official fork](https://github.com/griffithlab/civic-mcp-server) supplies `get_variant_evidence` and `get_variant_assertions`; its README describes a 50-EID response limit and a released 100-triplet QA evaluation. It uses Cloudflare Workers/MCP with local-host examples. Its license is modified MIT with an academic citation condition. We should inspect paging/filtering and provenance before adopting it, and distinguish its published QA benchmark from our reserved evaluation. No endpoint was called or package installed here.

**RobotReviewer and EBM-NLP are reference methods, not immediate production integrations.** RobotReviewer's [implementation](https://github.com/ijmarshall/robotreviewer) has Docker instructions but also legacy Python 3.6/TensorFlow 1.12 installation guidance; it needs a pinned compatibility review. Code is GPL-3.0. [EBM-NLP](https://github.com/bepnye/EBM-NLP) releases annotations and baselines, but a definitive artifact-wide license was not identified in the inspected repository. The official download page warns that hierarchical expert labels were attached to supplied crowd-derived spans; that is not gold end-to-end span extraction.

**CIViC-Fact is already used in our project.** Its [model card](https://huggingface.co/creisle/BioMedBERT-CIViC-Fact-2025.03.25) declares MIT for the checkpoint and the old SUPPORTS/REFUTES/NEI task. The [current dataset specification](https://github.com/creisle/civicfact/blob/master/data_builder/README.md) uses REVISIONS in its label schema and retains augmentation metadata. Its evidence text inherits individual article licenses; the stated most restrictive license for the full March 2025 build is CC BY-NC-SA. Model licensing does not license the evidence corpus. These are material version and redistribution distinctions.

## What the project already learned

Read alongside [Scientific validity review](../EXPERIMENT_HISTORY.md#reopening-an-archived-file "Archive file: docs/SCIENTIFIC_VALIDITY_REVIEW_20261021.md"), [combination feasibility](../EXPERIMENT_HISTORY.md#reopening-an-archived-file "Archive file: docs/evaluations/CLAIM_CHECK_COMBINATION_FEASIBILITY_20261021.md"), [NLI4CT-P result](../EXPERIMENT_HISTORY.md#reopening-an-archived-file "Archive file: docs/evaluations/NLI4CT_ROBUSTNESS_20261021.md"), and [context-prompt pilot](../EXPERIMENT_HISTORY.md#reopening-an-archived-file "Archive file: docs/evaluations/NLI4CT_CONTEXT_PILOT_20261021.md").

- BioMedBERT's strict-majority development agreement was 29/45, with six false supports and four correct supports. Those examples are consumed development material.
- Our deterministic parser recognized none of the 74 training and 47 development claims, so combining it with BioMedBERT changed no predictions. Adding a voting rule cannot repair that applicability gap.
- The current FLAN verifier scored 383/500 on the consumed NLI4CT test and 3,530/5,000 on related perturbations. These are task-specific benchmark results, not graph-wide scientific accuracy.
- The longer context prompt changed 106/128 correct labels to 103/128 on model-exposed train/development cases and failed the preset adoption rule. It supplies no reason to promote a longer prompt.
- “Previously correct supports” in that report means agreement with benchmark labels. Subsequent unblinded inspection raised possible reference issues in two changed cases; those flags are not expert adjudication, and no labels or scores were changed.

All failed runs, original labels, exposure records and frozen splits remain part of the evidence. A new dataset name does not ensure independence: PMID, NCT, claim variants, reviews and reused study populations may connect datasets. Unknown pretraining exposure must remain unknown.

## Verified gaps and decision rules

1. **Coverage is not completeness.** Audit full-text/table/supplement access and source release scope before interpreting an absent result. SciFact-Open and CIViC-Fact provide reasons to expect missing or narrower evidence.
2. **Binding is distinct from retrieval.** Maintain trial, arm, population, intervention/comparator, endpoint, time, units and denominators through extraction and verification. Evidence Inference provides a reusable task framing; its labels cannot be silently converted to ours.
3. **Evidence relevance is distinct from inference.** Development-only oracle-evidence experiments can diagnose a bottleneck, but NLI4CT demonstrates that correct evidence may be insufficient. They do not constitute a deployable method or fresh holdout gain.
4. **Faithfulness is distinct from appraisal.** Preserve study-design and risk-of-bias information rather than interpreting an NLI label as credibility. RobotReviewer is an established assistance approach; our system currently lacks validated appraisal.
5. **Synthesis needs dependence and applicability.** Do not count repeated database entries as independent support or generate an overall clinical conclusion from a majority of stance labels. MS² is a research resource, not authorization for autonomous clinical synthesis.
6. **Evaluate the intended output.** Retrieval recall, complete binding accuracy, false support, support precision/recall, abstention/coverage and summary qualifications require separate accounting. Generic text similarity is insufficient.

The recommended next work is a source/version and task-contract audit, then one bounded reuse decision. This review does not select a replacement model, recommend another broad ingestion, or establish that any candidate will improve Steward.

## Search and screening record

Searches were performed on October 21, 2026 through web search, followed by primary publisher/ACL/PMC pages and authors' GitHub/Hugging Face documentation. Venues checked include EMNLP, NAACL Findings, ACL, BioNLP, SemEval, Bioinformatics, Bioinformatics Advances, JAMIA and Scientific Data. Forward searches included 2025/2026 work; historical sources were retained for reproducible released artifacts. The following are exact representative queries used in this workstream:

```text
site.aclanthology.org scientific claim verification SciFact MultiVerS evidence inference biomedical review
CIViC Fact scientific claim verification BioMedBERT 2025 paper
NLI4CT 2024 benchmark numerical reasoning perturbations clinical trials official code
site.aclanthology.org SciFact Open Wadden 500K
site.nature.com CIViC-Fact benchmark claim verification 2025
site.ncbi.nlm.nih.gov MedCPT contrastive pre trained transformers 2023 retrieval
site.aclanthology.org EBM NLP corpus annotating PICO abstracts 2018
CIViC-Fact proof concept framework AI assisted verification cancer variant interpretations PMC
MedCPT 2023 github ncbi license
CliniFact scientific data 2025 github dataset license
site.aclanthology.org 2025 scientific fact checking evidence verification biomedical benchmark
"CliniFact" github
"EBM-NLP" github license
"RobotReviewer" risk bias github license trialstreamer
"Multi-document Summarization of Medical Studies" MS2 ACL
"RobotReviewer" "2015" risk bias validation PMC
"CIViC MCP" "2026" "Bioinformatics"
"CliniFact" "claim" "p-value"
```

Sources were selected for direct task relevance, primary methods/evaluation, or an official reusable artifact. Unrelated PHAROS systems, generic leaderboards, secondary blog summaries and claims without a traceable primary source were excluded as evidence. FEVER is retained only as training provenance; general-domain verification is not a replacement reference for biomedical curation. ConTRoL, newer generic agents, and additional benchmarks were not comprehensively screened. No claim of search saturation or complete 2026 coverage is made.

Primary pages blocked by access challenges were handled through indexed primary text, paper PDFs where accessible, and official repositories. CliniFact construction was only partially inspected because the publisher full text was inaccessible; it remains a screened candidate, not a qualified baseline. PMC's archived CIViC-Fact title/abstract differs from a later indexed preprint revision; results from those versions were not pooled. Artifact availability means a documented link/code path was inspected, not that large checkpoint downloads were attempted or hash-verified. No new example-level data files were downloaded. This single-workstream review has no independent duplicate screening or formal study-quality adjudication.
