# BioGraph Steward

BioGraph Steward helps a researcher turn a biological question into an
inspectable evidence graph and cited answer. It builds on **NIH Pharos** with
qualified source context. A **NVIDIA Nemotron agent** proposes a supported query,
prioritizes citations for inspection and produces grounded review proposals.
The app preserves the original records and makes applied graph decisions
recoverable.

**[Open the reviewer app](https://bi-3a117d5e2b3942678dc518fce65ab5d2.ecs.us-east-2.on.aws/)**
with the privately supplied token. No AWS account, installation or running
model is needed.

**[How to use it](HOW_TO_USE.md)** ·
**[Watch the 3:58 walkthrough](output/walkthrough/BioGraph_Steward_Walkthrough.mp4)** ·
[Short presentation](output/presentations/BioGraph_Steward_Overview.pptx) ·
[Local setup](START_HERE.md#local-setup)

## What we improved

| Improvement | What the recorded results show |
|---|---|
| **Added source context** | In the captured 99-target cohort, **87 physical-association pairs** and **68 protein–location concepts** are absent from the baseline annotations. KRAS–CDC42BPB is an actual inspected example. These are qualified candidate records, not claims of new biological discoveries. |
| **More known location labels recovered** | Under the same ontology-qualified mapping, captured Pharos **41/51 → native source 44/51**. The previously used OpenCell reference changes **30/40 → 31/40**. The full comparison retains source overlap, coverage limits and mapping controls. |
| **A separate function-prediction gain** | In the historical 20,412-protein study, context-aware learning improves fixed-ontology Fmax **0.17155 → 0.21009** over the retained Pharos-derived predictor. Both reference views improve; annotation refresh also helps. This is separate from the 99-target app and agent evaluation. |
| **Recoverable graph qualification** | The retained example excludes **298 obsolete-GO-identifier records**, leaving **16,687 of 16,985 input records**. Original sources and every decision remain available. |

The [submission overview](docs/SUBMISSION_OVERVIEW.md) explains these distinct
comparisons. The [addition audit](docs/evaluations/source_agent_20261116/demonstrated_additions.json),
[location assessment](docs/evaluations/public_gold_20261115/report.html) and
[function-prediction report](docs/evaluations/CONTEXTUAL_COMBINATION_RESULTS_20261115.md)
provide the supporting results. Known-label recovery is not whole-graph
precision; shared sources and prior reference use limit independence. Additional
primary learning benefit over fully refreshed annotations remains uncertain.

## Use the app

Start with the recorded KRAS question. Follow **Question & plan → Evidence
graph → Source inspection → Review proposals**. Inspect **E002,
KRAS–CDC42BPB**: its source passport shows **baseline pair present: false**,
the provider record and the identity checks.

The agent's fixed comparison preserved complete deterministic query results,
cited answers and focused graphs across five supported queries, including a
valid empty result. Three additional requests stopped at the scope guard without
model calls. These are [workflow checks](docs/evaluations/SOURCE_AGENT_RESULTS_20261116.md),
not a biological-accuracy percentage. Proposals do not automatically accept
claims or prune the graph.

For another task, inspect recorded location or archived-pathway questions,
review the separate retained TP53 graph, or download the workspace with its
sources. The [single user guide](HOW_TO_USE.md) explains the steps and files.

## Current app, saved data and new runs

The protected AWS reviewer app runs the recorded source-agent workflow. Its
[deployment and restart checks](docs/evaluations/delivery_readiness_20261116/hosted_acceptance.json)
and [hosted four-step browser walkthrough](docs/evaluations/delivery_readiness_20261116/hosted_browser_acceptance.json)
have passed.
The shared site is a **read-only replay**: it verifies saved work without new
model calls, source retrieval or review edits. An authorized operator can
[run a new agent question](docs/SOURCE_AGENT.md#operator-cli) with a complete
source workspace and configured model endpoint.

The demonstration uses a **captured Pharos319 baseline**, with separately saved
native GO and STRING profiles. It was assembled November 15 from an October 14
Pharos capture. The app's GO file was generated July 28 and uses the July 26
ontology; the physical source is STRING 12.5. Exact [source dates](docs/SOURCE_NOTES.md#current-reviewer-graph-and-source-dates)
are recorded separately from assembly dates. This is a fixed 99-target research
workspace. Updating application code does not refresh its upstream datasets. The
[delivery status](docs/DELIVERY_STATUS_20261115.json) identifies the deployed
application and saved artifacts.
The [designated primary graph handoff](docs/GOLD_SET_INTERFACE.md) now has its
own verified decision ledger, preserved sources and exact captured Pharos-only
comparator, prepared privately for permitted organizer access.

## Run locally

The core app needs **Python 3.10+**, with no pip install, GPU or API key:

```sh
python3 app.py
```

Open `http://127.0.0.1:8765/`. A fresh checkout includes invented software
fixtures; the complete real-data reviewer packet is supplied separately under
its source terms. Use the hosted site for the real examples, or open an
authorized saved workspace with all its source files.
[START_HERE](START_HERE.md#local-setup) covers branch selection and setup.

## Developer, operator and research documentation

[Current source agent](docs/SOURCE_AGENT.md) ·
[Graph construction](docs/CONSTRUCTION.md) ·
[Scoped retrieval](docs/SCOPED_RETRIEVAL.md) ·
[Source qualification](docs/NATIVE_PHYSICAL_SOURCE.md) ·
[Graph and decisions](docs/GOLD_SET_INTERFACE.md) ·
[Standard export](docs/STANDARD_EXPORT.md) ·
[Testing](docs/TESTING.md) ·
[Deployment](docs/PORTABILITY.md)

The [submission summary](docs/FINAL_SUBMISSION.md) maps the work to judging
criteria. The [research appendix](docs/RESEARCH_APPENDIX_20261115.md) and
[experiment ledger](docs/EXPERIMENT_HISTORY.md) retain complete comparisons,
stronger controls and unsuccessful approaches. The
[release index](docs/releases/20261115/README.md) separates software, protected
source data and research artifacts.

Development is on the private
[`codex/contextual-gain-delivery` branch](https://github.com/mdomagalski/biograph-steward/tree/codex/contextual-gain-delivery).
The core software is MIT licensed. Source datasets and reused tools retain
their own licenses; publishing code does not relicense the mixed-source data.
