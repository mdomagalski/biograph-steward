# Measured relationship benchmark: dataset and implementation audit

Date: October 22, 2026. Status: **candidate selected; upstream learner smoke-tested; biomedical preparation and comparison pending**.

**Subsequent preparation:** the [input-readiness audit](../evaluations/INMC_INPUT_READINESS_20261022.md) now records actual identifier/scaffold coverage, raw Pharos pair overlap, and an available author-exported positive reference. Partial-negative/failure semantics remain unresolved. Assay vocabulary was processed in that later audit without displaying per-pair outcomes or deriving binary labels. Statements below describe this earlier selection-stage exposure.

## Decision

Advance the **International Network Medicine Consortium (INMC) experimentally tested human protein-pair panel**, using **PyKEEN 1.11.1's native R-GCN** as the fixed graph learner. Keep ComplEx as a secondary embedding control and inspect the released MPS topology baseline for an additional reference. Train new models from the permitted graph; do not import pretrained biomedical embeddings.

This is a conditional selection for preparation, not permission to treat the panel as ready-made ground truth. The assay-code, mapping and source-leakage gates below must pass before biological training. Combining this panel with PyKEEN is our evaluation adaptation; it is not a reproduction of an INMC winning model.

The specific question is: **does audited additional context improve recovery of measured interaction outcomes among the same nominated human protein pairs, using the same learner?** This addresses the challenge's missing graph-link comparison. It does not answer whether our verifier became accurate, establish CRC treatment response, or replace the existing CRC evidence workbench.

Evidence accompanying this decision:

- [Machine-readable receipt and runtime results](../evaluations/measured_link_reuse_20261022_summary.json).
- [Small upstream-API smoke script](../../scripts/smoke_pykeen_reuse.py), [optional direct dependencies](../../requirements-graph-ml-smoke.txt), and [resolved macOS dependency lock](../third_party/pykeen_smoke_macos_20261022.lock.txt).
- Raw metadata, archive and logs in the ignored local directory `runs/link_prediction_reuse_audit_20261022/`. The archive contains experimental labels, but individual label records have **not been decoded or inspected** in this audit. Published aggregate results have been read.

## Why this panel, and what it actually measures

The INMC paper evaluates network-prediction methods and reports a union of **3,276 nominated pairs** and **1,177 experimentally detected interactions**. Its validation uses yeast two-hybrid assays. Technical failures, spontaneous autoactivation and not-tested results require separate handling. The text describes negatives over successfully tested assays, while the figure caption says all three assays: that difference must be resolved against the released outcome fields before encoding labels. **Do not infer a negative count by subtraction.** The paper also reports **495 self-interactions among cGAN's 500 nominations**. Its candidate pool is selected by prediction methods, not sampled uniformly from human proteins. [Wang et al., 2023](https://doi.org/10.1038/s41467-023-37079-7); [author-hosted paper](https://www.barabasi.com/media/Wang_XW._Madeddu_L._Spirohn_K._et_al._Assessment_2023.pdf).

Our resulting scope decisions, made before examining individual outcomes:

- Make **off-diagonal pairs** the primary endpoint. Keep self-interactions visible as a separate stratum rather than silently pooling or discarding them.
- Preserve assay-negative, failed, ambiguous and untested states. A negative is assay-specific; it is not evidence that two proteins can never interact.
- Report selection, mapping and connectivity exclusions. The nominated panel cannot support proteome-wide or CRC-specific accuracy claims.
- Use current Pharos only for a **retrospective source-blocked comparison**. Because current databases postdate the experiment, masking direct labels cannot guarantee that all downstream effects of the publication have disappeared.

The paper's strong topology methods justify retaining a simple reference. They do not establish that R-GCN will outperform it, or that richer context will help. A measured lack of benefit is an acceptable outcome.

## Alternatives examined

| Candidate | Experimental meaning / reusable artifacts | Decision for this increment |
|---|---|---|
| **INMC panel** | Tested protein pairs; archived labels, training interactomes and prediction methods | Primary preparation candidate. Most direct match to the missing edge task; assay semantics and later-source contamination remain gates. |
| **IDG-DREAM kinase challenge** | 824 affinity measurements; kinase/compound scope, historically blinded rounds, published analysis and scoring artifacts | Strong reserve. Requires chemical identity, concentration censoring and an affinity-versus-binary task choice in addition to graph integration. |
| **Davis / KIBA** | Established drug–target affinity datasets and molecular prediction baselines | Not the first KG comparison. KIBA aggregates assay types; popular preprocessing releases differ; current-source overlap needs auditing. Molecular graphs are not our biomedical KG. |
| **BindingDB** | Detailed binding records and assay provenance | Useful future task source, but a current dump is not an independent test set. Source-specific licensing, censoring and duplicate studies need a declared extraction. |
| **BioPlex HCT116 / HuRI** | Cell-context AP-MS associations / binary interaction positives | Useful potential training or context sources. Absent pairs are not measured negatives; Pharos overlap must be checked. Co-complex membership is not direct binding. |
| **DepMap / GDSC / PRISM** | Genetic dependency or drug–cell viability | Different endpoints. Preserve our consumed DepMap cohorts as historical development evidence. |
| **OGB BioKG / OpenBioLink** | Released heterogeneous graph-completion benchmarks, loaders and evaluation conventions | Useful infrastructure references, but not a substitute for a defined experimentally measured outcome. |

IDG-DREAM includes 95 compounds and 295 wild-type kinases across two experimental rounds. The assay selection followed strong single-dose screening, so its population is also selected. Its published potency threshold and censoring policy should be reused if that task is chosen, rather than invented locally. The official Zenodo record is accessible and lists CC BY 4.0; its `source_data.zip` is 30,694,116 bytes. Metadata was verified; that archive and the model containers were not reproduced here. [Challenge paper](https://pmc.ncbi.nlm.nih.gov/articles/PMC8175708/); [archive](https://zenodo.org/records/4648011); [official scoring repository](https://github.com/Sage-Bionetworks/IDG-DREAM-Drug-Kinase-Challenge).

Other primary references checked: [DeepDTA and its data preparation](https://pmc.ncbi.nlm.nih.gov/articles/PMC6129291/), [official DeepDTA data files](https://github.com/hkmztrk/DeepDTA/tree/master/data), [BindingDB record format](https://bindingdb.org/rwd/bind/chemsearch/marvin/BindingDB-TSV-Format.pdf), [BioPlex releases](https://bioplex.hms.harvard.edu/interactions.php), [HuRI releases](https://www.interactome-atlas.org/download), [OGB BioKG](https://ogb.stanford.edu/docs/linkprop/#ogbl-biokg), and [OpenBioLink](https://github.com/OpenBioLink/OpenBioLink). Dataset sizes and semantics must be tied to a specific release, not mixed across these packages.

## Artifact and license checks

| Artifact | Observed result |
|---|---|
| INMC archived release | [Zenodo 7681817](https://zenodo.org/records/7681817), `PPI-Prediction.zip`, 5,666,524 bytes; downloaded successfully |
| Integrity | Upstream MD5 `ccf0f64bb4581b467cbbdcefca6f0e72` matches; SHA-256 `2200fce435e0705470dda73f1dc870e6b6a7b9bee621c8697099dfd38b49ae62` |
| Archive contents | Experimental `.xls`, training interactomes, and method sources present. Experimental README is effectively empty, so it supplies no codebook. |
| Rights | Zenodo deposit metadata: CC BY 4.0. Included software LICENSE and current repository: MIT. Retain both attributions; do not infer all data rights from a software license. |
| Current repository snapshot | Tree SHA `5e2f7beb596987de7b97a0cf48900915a64aad99`; current experimental file is 205,543 bytes. Current tree and archived release are separately recorded, not treated as identical. |
| Published MPS | Java topology extraction and Python ranking source inspected in the archive. The topology-only ranker uses two named features. Complete extraction/ranking pipeline has **not** been run. |
| PyKEEN | Version 1.11.1, MIT, installed and executed locally. Native R-GCN requires no separate PyG installation for this smoke. |

Sources: [official INMC repository](https://github.com/spxuw/PPI-Prediction-Project), [MPS release documentation](https://github.com/spxuw/PPI-Prediction-Project/blob/master/Prediction%20methods/MPS/readme__PPI_CHALLENGE__version_0.pdf), [PyKEEN release metadata](https://pypi.org/project/pykeen/1.11.1/).

## Existing implementations: what we can reuse

**PyKEEN provides the learner and evaluation machinery.** Its native R-GCN constructs message-passing representations from the training triples factory. The pipeline can evaluate validation instead of test data and applies established known-positive filtering. The default R-GCN decoder is DistMult: its symmetry is suitable for an explicitly undirected target, but limits representation of directed context. ComplEx is a separate established control, not a GNN substitute. [Pinned pipeline](https://github.com/pykeen/pykeen/blob/v1.11.1/src/pykeen/pipeline/api.py); [pinned R-GCN](https://github.com/pykeen/pykeen/blob/v1.11.1/src/pykeen/models/unimodal/rgcn.py); [DistMult contract](https://pykeen.readthedocs.io/en/stable/api/pykeen.models.DistMult.html).

**A library does not supply our scientific split.** We still need an adapter from qualified assertions to stable entity/relation IDs, permitted training edges and fixed candidate-pair scores. PyKEEN's sampled nonedges are a training convention, not experimentally established negatives. Its pseudo-typed sampler infers support from training relations; it is not an ontology validator. Use its existing APIs instead of creating another trainer, while checking symmetric-pair handling and eligible protein candidates before the biological run. [TriplesFactory](https://pykeen.readthedocs.io/en/stable/api/pykeen.triples.TriplesFactory.html); [sampling documentation](https://pykeen.readthedocs.io/en/stable/reference/sampling.html).

Other implementations were inspected before choosing this engine:

- **GraphDTA:** consumes molecular graphs and protein sequences. Its ordinary training example selects by test MSE; a separate validation example exists. This is a task mismatch and an example-usage issue, not a solution to our KG comparison. [Official code](https://github.com/thinng/GraphDTA).
- **Otter-Knowledge:** relevant KG-enrichment research with MIT code. Its released pretrained graph exposure and arbitrary-graph training path need further verification; importing its pretrained representation could contaminate our comparison. [Paper](https://ojs.aaai.org/index.php/AAAI/article/view/28924); [official code](https://github.com/IBM/otter-knowledge).
- **PyG R-GCN example:** useful teaching implementation, but it prints test scores repeatedly during training and uses simple corruptions. Do not copy it unchanged as a sealed evaluation runner. [Official example](https://github.com/pyg-team/pytorch_geometric/blob/master/examples/rgcn_link_pred.py).
- **Published biomedical leakage benchmark:** relevant duplicate/inverse, degree and cold-start diagnostics. At commit `b08dabac07253dfe6bdc10f641a23f3c2c26f57e`, cleanup sorts all endpoint pairs and an entity-coverage function can move held-out triples into training. Reuse applicable diagnostics after inspection, not its whole preprocessing pipeline. This is a reuse finding, not a rejection of the paper. [Primary paper](https://doi.org/10.1093/bioinformatics/btag608); [pinned cleanup code](https://github.com/galadrielbriere/data_leakage_kge_benchmark/blob/b08dabac07253dfe6bdc10f641a23f3c2c26f57e/dev/my_data_redundancy.py).
- **KGATE 1.0.0:** relevant maintained alternative. Static inspection of commit `413643f7c0d3a8f464b111ca0a35f351f54b397a` found evaluation calls without a training-edge mask and initial split-mask aliasing. These are potential defects requiring runtime reproduction, not proven failures. Do not adopt that GNN evaluation path until checked. [Evaluator](https://github.com/BAUDOTlab/KGATE/blob/413643f7c0d3a8f464b111ca0a35f351f54b397a/src/kgate/evaluators.py); [graph implementation](https://github.com/BAUDOTlab/KGATE/blob/413643f7c0d3a8f464b111ca0a35f351f54b397a/src/kgate/knowledgegraph.py).

## Local reproduction completed

An isolated environment used Python **3.12.4**, PyKEEN **1.11.1**, PyTorch **2.6.0**, macOS arm64, **CPU only**. Both learners completed two training epochs on PyKEEN's bundled **Nations** dataset and returned finite validation metrics. The training factory contained 1,592 triples, 14 entities and 55 relations. No optimization search was performed.

| Check | Outcome |
|---|---|
| ComplEx, dimension 16 | Passed |
| Native R-GCN, dimension 16, one layer, two bases | Passed |
| Validation-only scoring | `use_testing_data=False`; built-in loader may still load the Nations test file |
| Biological labels or graph used | None |
| Brev GPU, CUDA portability, app integration | Not exercised |
| Scientific prediction improvement | Not measured |

The first smoke failed before training because PyStow attempted to create its default cache outside the writable workspace. The second used its **documented `PYSTOW_HOME` configuration** and passed without modifying library code. Both attempt logs and the failure receipt remain saved. [Upstream configuration](https://pystow.readthedocs.io/en/latest/installation.html#configuration).

Reproduce in a new directory from the repository root:

```sh
python3.12 -m venv runs/graph_ml_smoke/venv
runs/graph_ml_smoke/venv/bin/python -m pip install -r docs/third_party/pykeen_smoke_macos_20261022.lock.txt
PYSTOW_HOME="$PWD/runs/graph_ml_smoke/cache" runs/graph_ml_smoke/venv/bin/python scripts/smoke_pykeen_reuse.py --output-dir runs/graph_ml_smoke/results
```

The lock is a record of the tested macOS environment, not a tested Linux/CUDA lock. A Brev environment needs a separate documented PyTorch/CUDA selection and smoke before biomedical execution. The script refuses to overwrite an existing result directory. The small Nations scores in the JSON receipt are engineering diagnostics and should not be presented as biomedical performance.

## Preparation gates and the matched comparison

This is the proposed application of existing methods. It is **not yet a frozen protocol or a claim that the data pass these checks**.

1. **Assay-code gate.** Inspect workbook structure and published methods, reconcile partial tests, autoactivation and failures, and preserve source outcomes. Derive labels mechanically only after the rule is fixed. If the artifact cannot distinguish the states, stop at feasibility rather than silently inventing a negative class. Separate metadata/codebook inspection from individual outcome review.
2. **Identity and population gate.** Map original protein/ORF identifiers using existing versioned mappings; preserve one-to-many and unmapped cases. Define unordered pair equivalence and the off-diagonal cohort. Measure graph coverage without inspecting prediction performance. Freeze minimum coverage/support criteria before any outcome-driven selection; never drop difficult pairs to improve scores.
3. **Training-scaffold gate.** Reuse the released human training network after checking its identity and provenance. Use the identical permitted experimental training scaffold in both arms. Explain that the baseline is **Pharos context plus the shared training scaffold**, not literally an unmodified Pharos dump. Keep a separate scaffold-only topology control. Do not train on the panel reserved for evaluation.
4. **Leakage gate.** Remove evaluation-pair equivalents, reverse assertions and target-revealing features across all direct interaction predicates and providers in both graphs. Block the validation publication, PMID **36949045**, and identifiable derivatives. Do not pass held-out outcomes into GNN adjacency, text embeddings or enrichment retrieval. Insufficient source lineage may require conservative exclusions; unresolved leakage restricts the claim.
5. **Enrichment gate.** Identify a specific missing context field or evidence qualification by tracing Pharos's existing content first. Compare the complete scoped baseline with an audited addition; do not count the same source twice under different provider names. A simple source-addition arm may be needed to separate extra information from Steward's normalization or filtering contribution. Freeze the actual source and policy before results, rather than trying sources until one wins.
6. **Learner and scoring gate.** Reuse PyKEEN training and pair scoring; test the adapter on synthetic fixtures. Validate symmetric target handling, relation semantics, fixed entity mappings and typed candidate eligibility. Preserve all target assignments. No automatic split repair may move panel outcomes into training. Smoke the released topology implementation separately before using its scores as a comparator.
7. **Evaluation freeze.** Choose development data independently of the reserved panel. Declare paired seeds, training budget, hyperparameter selection, fixed off-diagonal test population and abstention/missing-score policy. Equal epochs alone do not mean equal optimization work when one graph is larger. Prefer threshold-free average precision as the primary panel metric, with ROC analysis secondary, using established implementations and specified tie handling. Sampled nonedges cannot establish an assay-calibrated decision threshold or replace measured evaluation negatives. This is a different scoring task from the smoke's all-entity filtered MRR. Define uncertainty and shared-protein dependence before results; estimates from this selected single-study panel cannot establish between-study generalization.

The next bounded increment is **a label-code, identifier-coverage and source-overlap audit**, followed by a frozen protocol if it passes. It does not require the Brev model to remain running. AWS is not needed for this preparation.

## Limits and preserved history

The public test panel is not independently hidden from the scientific community. We have read published aggregate outcomes and selected this task after earlier, different experiments. Even a clean local freeze cannot turn it into a new prospective experiment. Report performance as retrospective assay-panel recovery, with explicit overlap limits.

No prior failed verifier or extraction run was deleted or reinterpreted. The consumed 512-gene DepMap panel and reserve remain consumed; they are not fresh tests for this work. This audit adds no biomedical assertions, no automated scientific approval, no new model judgment about a CRC claim and no graph-utility result.
