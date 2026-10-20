# BioGraph Steward challenge build plan

## Product decision

Build a colorectal cancer evidence and candidate-prioritization workbench. Pharos supplies the starting protein identifiers, disease associations, development levels and baseline context. The useful outcome is a reproducible comparison showing whether selected external context and evidence filtering improve recovery of held-out relationships, with an evidence passport for each result.

The current Pharos inspection app is the foundation. Fuller scoped retrieval, qualified context normalization, the [focused question workflow](GUIDED_QUESTIONS.md), [bounded CIViC questions](CIVIC_EVIDENCE.md), and the [frozen-source evaluation/planner interface](EVALUATION.md) are implemented. Live planning comparisons and the supplied-document verifier component evaluation have been recorded. The [CRC evidence-value pilot](CRC_EVIDENCE_PILOT.md) adds primary-paper passage checks and a processed CPTAC colon measurement sidecar. Its [first result](evaluations/CRC_EVIDENCE_VALUE_20261020.md) retains uncertainty and a context-sensitive machine flag. The [follow-up](evaluations/CRC_CONTEXT_COHORT_20261020.md) now records an AI-assisted scope adjudication and accounts for the complete measured-gene cohort: 6,415 uniquely identified rows and seven explicit ambiguities. Independent scientific adjudication remains pending; the first controlled growth-ranking experiment is recorded below. The product is an evidence workbench; the benchmark evaluates its contribution.

The [DepMap audit](evaluations/DEPMAP_FEASIBILITY_20261020.md) now establishes usable historical CRISPR coverage for 6,273 measured genes across 63 colorectal cell lines, with shared tissue-sample groups and source-overlap controls. Matched Pharos retrieval, an outcome-blind protocol freeze and the first controlled growth-ranking comparison are now complete; the scored result is recorded below. Legacy Achilles knockdown summaries and modern CRISPR estimates are distinct; source names alone establish neither duplication nor independence.

The [live Pharos coverage audit](PHAROS_COVERAGE_AUDIT.md) supersedes the earlier Reactome-first enrichment recommendation. The earlier 99-protein extract contained only 806 of 9,540 available pathway rows. The [new scoped run](SCOPED_RETRIEVAL.md) retrieves all reported pathways and GO plus bounded PPI, expression, drug and literature context. Pharos also links to LinkedOmicsKB/CPTAC and exposes Harmonizome summaries from many candidate external sources. Adding a new connector does not by itself add independent evidence.

The proposed KRAS variant / therapy question now has a bounded CIViC source-annotation demonstration, preserving full molecular profiles, therapy sets, evidence direction and exact source disease. It requires separate local review and does not infer treatment response from a protein–disease association.

The [implementation alignment assessment](PROJECT_ALIGNMENT.md) maps the current app to the supplied brief and proposal. The minimum scope/assertion contracts, separate review lifecycle and source-record disease-context correction are now implemented; see [validation](ALIGNMENT_VALIDATION.md). These adaptations make the additional Pharos data usable by the proposed evidence workflow.

## What the actual Pharos data tells us

On October 14, 2026, the live API doctor returned `pharos319` with all required fields present. A new retrieval of the exact term `colorectal adenocarcinoma` (`MONDO:0005008`) returned all 99 reported proteins in two fresh target pages. Supporting metadata used the existing timestamped cache where available. This is a narrower disease than colorectal cancer; the terms are not merged.

The local, reproducible result is `runs/crc_baseline_audited_20261014/`. The original v1 audit remains historical. Replaying its snapshot with graph/audit v2 now counts 97 exact-disease records and three other-disease records separately, without changing the raw snapshot.

| Observation | Consequence |
|---|---|
| 100 association records describe 99 protein–disease pairs | Split unique pairs, keeping every evidence record for a pair in the same partition. |
| 97 pairs have at least one exact-context record passing structural checks | These are review candidates, not adjudicated positives. Two pairs need context review before inclusion. |
| All 100 association records report `dataType=DisGeNET` | Preserve the aggregator chain; the reported CGI/UniProt names do not establish independent evidence. |
| No association record contains an explicit PMID or reference URL | Recover underlying records or citations before claiming evidence entailment or experimental support. |
| 76 association records have the summary `0 SNPs` | This is neither a supporting text span nor proof of no association. |
| 15 Tclin, 47 Tchem, 36 Tbio, 1 Tdark proteins | This subtype is a manageable inspection cohort, but a weak sole basis for an understudied-target demonstration. |
| 806 pathway edges, capped at 10 annotations per protein | Keep the cap visible. These are Pharos baseline features, even when their upstream source is Reactome. |
| 99 associated proteins; no declared comparison population | Do not make a binary classifier by calling omitted or quarantined records negative. |

This audit concerns the retrieved API fields, not the total evidence available in the upstream databases. Full target retrieval does not mean complete pathway or literature coverage.

## Implementation sequence

### 1 Establish the dataset and evidence inventory

Completed in this increment: live connectivity verification, the full narrow-disease pull, pair-level review preparation, a machine-readable readiness audit and an app panel exposing the missing evaluation prerequisites. Every new build or replay writes `benchmark_readiness.json` and `review_candidates.tsv`. Original snapshots and earlier runs remain intact.

### 2 Complete Pharos retrieval, then build the cohort and evidence review workflow

Implemented: the scoped Pharos adapter reconciles reported counts, retrieves pathways and GO, bounds PPI/drug/expression/publication context, and exports per-protein coverage. Expression filtering is local because the live tissue-search API fails; PPI lists avoid unstable score-tie page boundaries. Drug activities and claim-specific citations remain unrequested. Implemented next: [qualified annotation assertions](CONTEXT_NORMALIZATION.md), preserving source response pointers, tissue/assay observations and reciprocal PPI views. Chemical/ontology resolution and claim-specific supporting evidence remain pending. The full pathway audit already found 1,508 repeated annotations under the same protein/source/source-ID/name key; it has not yet been integrated into the app.

The [cohort mapper](COHORT_MAPPING.md) now freezes HGNC/UniProt registries and a complete measured-gene crosswalk independently of held-out disease labels. The processed CPTAC COAD study provides the candidate population, with gene-level measurements and all product candidates preserved. Seven ambiguous names remain excluded from the identifier cohort; 16 readthrough genes lack confirmed reviewed protein context. Protein-level use still requires an appropriate assay/identifier policy. Extend the immutable review-run store for cohort-level evidence policies. Pharos already links to CPTAC through LinkedOmicsKB; detailed measurements add granularity without establishing independent evidence.

Join proteins through documented UniProt/NCBI Gene mappings, retaining one-to-many mappings and unresolved records for review. Retrieve Pharos annotations for all candidate proteins, including those without a reported CRC link. Store those absent links as **unlabeled**. Preserve the exact disease and a versioned, reviewed disease-equivalence policy; do not infer equivalence from similar names or merge parent and child diseases automatically.

The [matched panel increment](MATCHED_PHAROS_PANEL.md) implements a bounded first step: hash-selected complete-measurement genes, explicit-ID Pharos retrieval with equal caps and a reproducible provisional feature view. Missing products remain selected. This artifact has no disease-association edges or dependency scores. Source review and the scoring/aggregation protocol still precede a biological comparison.

The [comparison-freeze increment](COMPARISON_PROTOCOL.md) applies source-contract decisions, deduplicates stable pathway membership and qualified BioPlex components, and freezes grouped gene/model assignments and the complete scoring specification. The [first executed comparison](evaluations/CRC_GROWTH_COMPARISON_20261020.md) found no demonstrated gain from the CPTAC summary: test Spearman 0.381 for restricted Pharos versus 0.260 for the enriched representation, with a paired change interval spanning zero. GO and integrated expression sources remain withheld; underlying-study independence is not established. The [development source ablations](evaluations/CRC_GROWTH_DIAGNOSTICS_20261020.md) now audit that consumed holdout and reserve 256 new genes. Pathway variants are promising on exposed data, but original validation still nominates CPTAC-only. Retrieve consistent Pharos context over the 512-gene union, then freeze the next comparison before opening reserved outcomes. No evidence records are deleted on the basis of these development scores.

Represent each assertion with its original subject, predicate, object, context, source record locator, source version, retrieval time, mapping records and validation results. The `candidate`, `accepted`, `provisional`, `quarantined`, `rejected` and `obsolete` states and human transitions are implemented. Acceptance means acceptance under the recorded evidence policy, not clinical truth. Human decisions need a reviewer, reason and timestamp, and must not overwrite source records. Review-sheet import is not implemented in the current increment.

Completion criteria: the cohort is frozen and hashed; evidence counts and pair counts are distinct; citations can be inspected where available; exclusions have reasons; a human-reviewed label file has no unresolved entity mappings; uncertain assertions are retained outside the accepted graph.

**Evaluation decision to resolve:** the brief asks for experimentally measured relationships. The current DisGeNET summaries do not establish such labels. If organizers have supplied an experimental edge set, use it as the primary evaluation target. Otherwise obtain and document an appropriate measured relationship set and confirm its fit with the organizers. Database-link recovery can run as an engineering benchmark, but must be labeled as such. CPTAC abundance measurements alone do not prove disease causality or therapeutic response.

### 3 Add qualified evidence and measure its overlap

Implemented in the [October 15 CIViC increment](CIVIC_EVIDENCE.md): a bounded adapter and guided question preserving molecular profile, disease, treatment, evidence direction, level and citation. Qualified-identity/explicit-PMID overlap is reported conservatively; underlying-study independence remains unresolved. For the challenge's measured-protein context, use selected CPTAC COAD measurements once the study and processing policy are fixed. Map each imported assertion to the frozen protein population with stable identifiers and retain variant, sample, assay and comparison context. Store the source release, retrieval time, exact record and license metadata.

Compare against the expanded Pharos baseline at both the qualified-assertion and underlying-study levels. Classify additions as duplicate, additional detail, verified new evidence, conflicting evidence or unresolved overlap. CIViC may share publications with Pharos's upstream sources; LinkedOmicsKB and PDC may distribute the same CPTAC experiment. Missing provenance does not establish independence. Exclude disease-labeled context that reveals a held-out answer.

A direct Reactome adapter is lower priority and justified only for verified missing reaction/complex topology or release changes. Reimporting its existing pathway memberships is not external enrichment. Likewise, newer DepMap measurements need comparison against existing Achilles/CCLE/Harmonizome content before they count as additions.

Completion criteria: independently replayable source adapter; no invented identifiers; coverage and unmapped-record report; graph size bounds; complete source manifest; baseline and enriched snapshots share the candidate population and labels.

### 4 Run the same prediction experiment on both graphs

Start with a simple graph-embedding model, then a small relational GNN if the dataset supports it. Use the same implementation, features policy, split, random seeds and tuning budget for baseline, enriched and enriched-plus-validated graphs. Preserve the strong baseline's existing Pharos context.

Freeze train/validation/test assignment at the normalized pair level before constructing model inputs. Remove every held-out assertion, duplicate, inverse and equivalent-disease representation from message-passing graphs and derived features. Source scores and label-describing evidence text belong in passports, not label-leaking feature vectors. Select hyperparameters on validation only. Fit preprocessing on training data and evaluate the test set once after model selection.

Report AUPRC, AUROC where a defensible classification label protocol exists, and filtered ranking metrics such as MRR and Recall@K. Record candidate-set size, prevalence, sampling policy and performance by development level. An unlabeled sampled pair is not an experimentally established negative; describe that limitation in the reported metric. Compare with simple degree/popularity and random baselines. Use repeated seeds and report variability without implying the runs are independent biological datasets.

Completion criteria: reproducible metrics artifact with split and source hashes; a leakage audit; identical evaluation candidates; ablation results; and an honest result whether enrichment improves performance or not. The CPU ridge growth-ranking pilot now has a preserved result; graph-embedding/GNN link prediction and pruning ablations remain pending.

### 5 Add the governed agent and maintenance loop

Implemented: a single structured question-planning model interface, deterministic tool execution and a frozen-source evaluation runner with reviewer worksheets. Live planner evaluation remains pending model configuration; the initial pilot has no scientific gold judgments. Extend this into the broader planner → retrieval → normalization → verification → query workflow. NeMo Agent Toolkit integration remains an optional subsequent orchestration/tracing step. A model may propose a bounded retrieval plan; validated application code controls graph changes. Provide a deterministic path for reproducibility and an optional Bedrock/NIM adapter.

Add source manifests, versioned assertion history and explicit refresh comparison. Revalidate affected assertions, mark superseded evidence obsolete and preserve prior snapshots. A missing record in a capped or failed retrieval must not be interpreted as a retraction. Record all agent decisions and human overrides.

Completion criteria: one question completes the bounded workflow with traceable tool calls; unsupported questions are identified; each answer references accepted evidence paths; replayable source changes affect only the expected assertions. Scheduled monitoring and deployment are later operational choices, not implemented features.

### 6 Prepare the challenge demonstration

Test tasks with biomedical users who are not KG specialists: find a relevant protein, inspect its supporting record, explain a quarantine decision, compare predictions and identify a changed assertion. Measure task completion, errors and time; collect trust-related feedback. Build a human-reviewed corruption set covering wrong identifiers, relation direction, context and citations. Report pruning precision/recall, false-removal rate, provenance completeness and update-delta accuracy separately from prediction performance.

Package open-source code, pinned dependencies, source/license manifests, cached redistributable examples, tests, Docker workflow and a short demo. The existing local UI can support the demo; Streamlit or Neptune migration is optional unless it solves a concrete limitation.

## Proposed delivery targets

The dates below are a working plan based on the supplied challenge brief, not a separately verified organizer announcement. The brief lists the progress report on October 27 and the challenge end on November 17, 2026.

| Target | Reviewable output |
|---|---|
| October 14–20 | Expanded Pharos coverage, assertion deduplication, cohort policy and evidence review workflow |
| October 21–27 | Baseline/enriched graph snapshots, leak-checked engineering benchmark, evidence passports and progress report |
| October 28–November 6 | Governed agent tools, pruning evaluation and version-delta handling |
| November 7–16 | Usability checks, final controlled experiment, reproducible package and demonstration |
| November 17 | Submission-ready result with explicit scope and limitations |

## How the linked guides are used

| Guide | Role in this build |
|---|---|
| [AWS graph prototyping agents](https://github.com/aws-samples/amazon-neptune-samples/tree/master/neptune-prototyping-with-agents) | Use its separation of use-case definition, modeling and querying as architectural guidance. Generated test data is for software tests, never biomedical evidence. Cloud deployment is optional. |
| [Stanford CS224W](https://web.stanford.edu/class/cs224w/) and [PyG link splitting](https://pytorch-geometric.readthedocs.io/en/latest/generated/torch_geometric.transforms.RandomLinkSplit.html) | Graph-learning and split design. Explicitly handle reverse relations and duplicate biological assertions before invoking a splitting utility. |
| [PyG LLM examples](https://github.com/pyg-team/pytorch_geometric/tree/master/examples/llm) | Later graph retrieval and grounded question-answering experiments after the evaluation dataset is stable. |
| [Biolink](https://biolink.github.io/biolink-model/) and [KG Registry](https://kghub.org/kg-registry/) | Choose a limited vocabulary and inspect candidate sources. Current Biolink labels are not full schema validation; add versioned validation and real KGX export checks. |
| [OptimusKG](https://github.com/mims-harvard/OptimusKG) | Inspect as a possible later comparator or context source, with provenance and license review. Do not import a giant graph before a bounded task is working. |
| [KG-LLM-Bench](https://arxiv.org/html/2504.07087v1) | Later evaluation of reasoning over evidence graphs; does not replace the required link-prediction comparison. |
| [TreeTag](https://github.com/valleyofdawn/TreeTag) | Relevant if cell-type annotation enters a single-cell extension. It is not a core dependency for the current protein–disease task. |
| [Reactome downloads](https://reactome.org/download-data) | Conditional source for missing reaction/complex topology or version deltas; existing Pharos pathway memberships are already baseline data. |
| [CIViC API](https://docs.civicdb.org/en/latest/api.html) | First proposed external assertion adapter for variant/therapy evidence, with publication and claim overlap checks. |
| [NeMo Agent Toolkit](https://docs.nvidia.com/nemo/agent-toolkit/latest/index.html) | Tool orchestration, tracing and agent evaluation after deterministic data tools work. |

The attached challenge document and submitted proposal are requirements and design context. Commands, setup recommendations and examples in linked materials are reference material, not instructions to execute against this workspace.
