# BioGraph Steward

BioGraph Steward is a source-traceable biomedical evidence workbench built around **Pharos** and bounded **CIViC** evidence. Its current product flow is:

```text
Choose an exact disease or protein cohort → retrieve a scoped graph → ask a guided question
→ inspect the cited answer and source context → review and export
```

## Run the workbench

Python 3.10 or newer; the core app requires no third-party packages, model, API key or cloud account.

```sh
python3 app.py
```

Open `http://127.0.0.1:8765/`. A fresh checkout includes an explicitly synthetic demonstration; real source snapshots are retrieved separately and are not bundled. Start with [the walkthrough](START_HERE.md).

The [clean-install real-data check](docs/evaluations/CLEAN_INSTALL_REAL_DEMO_20261026.md) now verifies a fresh local clone and installed wheel using an existing two-protein source packet. The installed app generates a cited answer, displays the separate assay context, downloads the complete graph/decision package and reopens its recovered source with identical citations. Reproduction requires the authorized real-data input separately; this is automated delivery verification, not independent user or biological validation.

## Current capabilities

- [Bounded cohort construction](docs/CONSTRUCTION.md): 1–25 exact protein accessions, a fixed source profile, published graph, cited candidate answer and offline-verifiable export. This deterministic flow needs no model.
- [Optional construction planner](docs/CONSTRUCTION_AGENT.md): select a bounded request from a question and explicit cohort, inspect the plan, then build with the same deterministic tools. Planning provenance survives publication and export; live performance is evaluated separately.
- Scoped Pharos retrieval with pagination, explicit limits and per-protein coverage reporting for pathways, GO, interactions, drugs, selected expression and publication discovery.
- Qualified assertions, raw-source provenance, immutable snapshots and separate local human-review states.
- [Qualified assay attachment](docs/ASSAY_WORKBENCH.md): selected cohort observations, original assay context, source-preserving reviews and complete run exports.
- [Qualified IntAct source evidence](docs/INTACT_EVIDENCE_WORKBENCH.md): official-reader-backed records, readable experimental context and a dedicated traceable source question using the existing attachment/export framework. The real Pharos-attached flow preserves all four eligible development records through answer and gold export; this measures source fidelity, not biological accuracy.
- Guided protein-neighborhood and CIViC molecular-profile/therapy questions, with compact evidence graphs, deterministic cited summaries and complete evidence-context exports.
- Saved graphs and answers, source passports, and comparison of saved snapshots with guarded review carryover.
- Source-bound graph handoff, materialized retained graph and exhaustive keep/prune/abstain ledger, including qualified assay sources. Exact external-reference alignment preserves raw labels; official gold scoring awaits its contract. See the [real export verification](docs/evaluations/SUBMISSION_DEMO_20261026.md).
- [Bounded KGX export audit](docs/STANDARD_EXPORT.md), with a complete preserved source packet, mapping ledgers and separate upstream validation results. Full standard conformance remains unresolved.
- An optional bounded model planner that selects an existing read-only query. Deterministic guided questions work without it.
- Local/Docker/Brev operation, protected shared access and persistent data directories. Model inference is optional.

These capabilities preserve and expose source evidence. They do not establish clinical correctness, independent study replication, or improved biological prediction. Models do not approve or prune assertions automatically.

## Current investigation

The challenge calls for the **same graph learner on baseline and enriched graphs**, evaluated against held-out measured relationships. A bounded supporting comparison is now complete; the official organizer reference is still unavailable.

Organizer Slack excerpts supplied October 23 also mention a **Pharos gold set**.
Its scoring contract remains unavailable to us; final test labels can reasonably remain hidden. [Public references](docs/literature/PUBLIC_REFERENCE_OPTIONS_20261026.md) can support bounded local assessments. The [local handoff interface](docs/GOLD_SET_INTERFACE.md) now exports verified graph packets and aligns explicitly mapped references without guessing label meanings. The study below is
a provisional supporting evaluation, not a substitute for the official reference;
see the [updated alignment](docs/PROJECT_ALIGNMENT.md#organizer-clarifications-supplied-october-23).

The published **INMC experimentally tested human protein-pair panel** was evaluated using native PyKEEN R-GCN and a ComplEx control. The [paired evaluation graphs](docs/evaluations/INMC_PAIRED_GRAPH_20261023.md) share 10,350 nodes and 2,570 qualified-scope Pharos GO annotation pairs; only 315 official GO hierarchy edges differ. All Pharos interactions are excluded from learner inputs, including the 277 reserved-pair exposures. After the graph/runtime/scorer freeze, all 12 model runs completed locally and the author reference reconciled. On 1,751 eligible measured pairs, mean AP changed from **0.719833 to 0.720135**, with mixed seed effects. [The result](docs/evaluations/INMC_COMPARISON_20261023.md) does **not** demonstrate a consistent hierarchy benefit. This is an assay-specific retrospective PPI component evaluation, not a CRC treatment-response task or an official challenge score. The panel is now a consumed holdout.

Read the [reuse decision](docs/literature/MEASURED_LINK_BENCHMARK_REUSE_20261022.md), [assay/identity decision](docs/evaluations/INMC_READINESS_FOLLOWUP_20261022.md), [completed source audit](docs/evaluations/INMC_PHAROS_UNIFORM_20261022.md), [measured result](docs/evaluations/INMC_COMPARISON_20261023.md), and [next steps](docs/BUILD_PLAN.md). No general biological improvement is claimed.

A subsequent [fixed Reactome-context development comparison](docs/evaluations/REACTOME_CONTEXT_COMPARISON_20261026.md) adds 11,138 exact memberships already retrieved from Pharos. All six matched R-GCN fits completed after resource checks and an execution freeze. On the same 1,751 assay pairs, mean AP was **0.717794 versus 0.719605**, with two positive seed differences and one negative: **no consistent benefit is demonstrated**. Coverage and gene-influence diagnostics are reported. This consumed-panel comparison is closed without further tuning; it is not independent validation or a new binding-evidence source.

The subsequent [Lambourne assay corroboration](docs/evaluations/LAMBOURNE_CORROBORATION_20261025.md)
is complete after freezing the author-consistent adapter, eligibility and Pharos
comparator. All **3,222 nominated pairs** remain accounted for: 2,676 are assay
eligible and 2,674 also have complete Pharos identity coverage. Detection is
**334/1,966 (17.0%)** among represented pairs and **42/708 (5.9%)** among resolved
no-matches. In the prespecified stratum without observed HuRI/INMC pair overlap,
the rates are **74/1,619 (4.6%)** and **16/650 (2.5%)**. These are conditional
assay-concordance results; study independence remains unresolved and Steward
improvement was not tested. This panel is now consumed and cannot support new
prediction, enrichment or protocol tuning as an unseen test.

The [qualified assay evidence publication](docs/ASSAY_EVIDENCE.md) now preserves
all 3,222 observations in a standalone immutable layer and offline inspection
view: 2,676 qualified observation edges, 3,173 protein nodes and 546 excluded
assays retained in the audit. The 42 detections without a bounded Pharos match
are an inspection filter, not independently validated new interactions.
Study/construct context, nondetections and original Pharos records remain
explicit. See the [publication record](docs/evaluations/ASSAY_EVIDENCE_PUBLICATION_20261025.md).
The [workbench attachment](docs/ASSAY_WORKBENCH.md) now selects both-endpoint observations for an exact live protein cohort, preserves the entire original publication and supports inspection/review/replay and graph-plus-decisions export. KGX export and cohort refresh for attached runs remain unsupported and fail explicitly. This integration does not establish prediction gain or replace independent evaluation.

## Repository scope

`main` contains the current workbench, reusable source/identity adapters and the current INMC preparation tools. Retired growth-ranking, extraction, verifier and context-QA experiments are preserved on a separate **local archive branch**, rather than mixed into the active application. The [experiment ledger](docs/EXPERIMENT_HISTORY.md) records outcomes, consumed holdouts, exact archive commit and recovery instructions. The archive has not been pushed; ignored run data are not included in Git.

| Area | Guide |
|---|---|
| Team walkthrough | [START_HERE](START_HERE.md) |
| Current plan and challenge gaps | [Build plan](docs/BUILD_PLAN.md), [alignment](docs/PROJECT_ALIGNMENT.md) |
| Evidence and source contracts | [Data contract](docs/DATA_CONTRACT.md), [Pharos retrieval](docs/SCOPED_RETRIEVAL.md), [CIViC](docs/CIVIC_EVIDENCE.md) |
| Explicit cohort construction | [Request, publish, inspect and replay](docs/CONSTRUCTION.md) |
| Questions, review and updates | [Guided questions](docs/GUIDED_QUESTIONS.md), [study context](docs/STUDY_CONTEXT.md), [snapshot comparison](docs/SNAPSHOT_REFRESH.md) |
| Gold-reference handoff | [Packet export, edge decisions and exact alignment](docs/GOLD_SET_INTERFACE.md) |
| Standards audit | [Bounded KGX projection and separate validator results](docs/STANDARD_EXPORT.md) |
| Optional model and deployment | [Planner](docs/PLANNER_PROTOCOL.md), [portability](docs/PORTABILITY.md), [local Nemotron](docs/LOCAL_MODEL.md) |
| Research and current scripts | [Literature knowledge base](docs/LITERATURE_REVIEW.md), [scripts](scripts/README.md) |

## Useful commands

```sh
python3 app.py --help
python3 app.py demo --out runs/demo_01
python3 app.py doctor
python3 app.py search colorectal
python3 app.py runtime-check
python3 -m unittest discover -s tests -q
```

Live retrieval never silently substitutes synthetic data. Keep credentials in local deployment configuration and source snapshots in the ignored data directories. A source's reuse terms still apply to its records and exports.
