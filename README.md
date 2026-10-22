# BioGraph Steward

BioGraph Steward is a source-traceable biomedical evidence workbench built around **Pharos** and bounded **CIViC** evidence. Its current product flow is:

```text
Choose an exact disease → retrieve a scoped graph → ask a guided question
→ inspect the cited answer and source context → review and export
```

## Run the workbench

Python 3.10 or newer; the core app requires no third-party packages, model, API key or cloud account.

```sh
python3 app.py
```

Open `http://127.0.0.1:8765/`. A fresh checkout includes an explicitly synthetic demonstration; real source snapshots are retrieved separately and are not bundled. Start with [the walkthrough](START_HERE.md).

## Current capabilities

- Scoped Pharos retrieval with pagination, explicit limits and per-protein coverage reporting for pathways, GO, interactions, drugs, selected expression and publication discovery.
- Qualified assertions, raw-source provenance, immutable snapshots and separate local human-review states.
- Guided protein-neighborhood and CIViC molecular-profile/therapy questions, with compact evidence graphs, deterministic cited summaries and complete evidence-context exports.
- Saved graphs and answers, source passports, and comparison of saved snapshots with guarded review carryover.
- An optional bounded model planner that selects an existing read-only query. Deterministic guided questions work without it.
- Local/Docker/Brev operation, protected shared access and persistent data directories. Model inference is optional.

These capabilities preserve and expose source evidence. They do not establish clinical correctness, independent study replication, or improved biological prediction. Models do not approve or prune assertions automatically.

## Current investigation

The challenge calls for the **same graph learner on baseline and enriched graphs**, evaluated against held-out measured relationships. That comparison is still pending.

We are preparing the published **INMC experimentally tested human protein-pair panel**, reusing PyKEEN's R-GCN and simpler controls. Runtime smoke tests passed on non-biomedical data. The input audit maps 1,801 of 1,805 panel gene identifiers; assay inclusion, mapping exceptions and consistent Pharos retrieval still need resolution before labels and a comparison are frozen. This is an assay-specific PPI component evaluation, not a CRC treatment-response task.

Read the [reuse decision](docs/literature/MEASURED_LINK_BENCHMARK_REUSE_20261022.md), [input-readiness report](docs/evaluations/INMC_INPUT_READINESS_20261022.md), and [next steps](docs/BUILD_PLAN.md). No biological improvement is claimed.

## Repository scope

`main` contains the current workbench, reusable source/identity adapters and the current INMC preparation tools. Retired growth-ranking, extraction, verifier and context-QA experiments are preserved on a separate **local archive branch**, rather than mixed into the active application. The [experiment ledger](docs/EXPERIMENT_HISTORY.md) records outcomes, consumed holdouts, exact archive commit and recovery instructions. The archive has not been pushed; ignored run data are not included in Git.

| Area | Guide |
|---|---|
| Team walkthrough | [START_HERE](START_HERE.md) |
| Current plan and challenge gaps | [Build plan](docs/BUILD_PLAN.md), [alignment](docs/PROJECT_ALIGNMENT.md) |
| Evidence and source contracts | [Data contract](docs/DATA_CONTRACT.md), [Pharos retrieval](docs/SCOPED_RETRIEVAL.md), [CIViC](docs/CIVIC_EVIDENCE.md) |
| Questions, review and updates | [Guided questions](docs/GUIDED_QUESTIONS.md), [study context](docs/STUDY_CONTEXT.md), [snapshot comparison](docs/SNAPSHOT_REFRESH.md) |
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
