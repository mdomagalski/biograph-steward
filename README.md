# BioGraph Steward

BioGraph Steward helps scientists use knowledge graphs without writing graph
queries. A biological question leads to an inspectable evidence graph and a
cited answer. It builds on **NIH Pharos** with
qualified source context. An **NVIDIA Nemotron agent** proposes a supported query,
prioritizes citations for inspection and produces grounded review proposals.
The app preserves the original records and makes applied graph decisions
recoverable.

**[Open the public demo](https://bi-3a117d5e2b3942678dc518fce65ab5d2.ecs.us-east-2.on.aws/?run=native_evidence_workspace_20261115&question=native_physical_KRAS_question_v3_20261115&agent_job=source_agent_eval_dc7b597201da_S01&view=data)**
directly. No sign-in, AWS account, installation or running model is needed.

**[How to use it](HOW_TO_USE.md)** ·
**[Watch the 3:58 walkthrough](output/walkthrough/BioGraph_Steward_Walkthrough.mp4)** ·
[Short presentation](output/presentations/BioGraph_Steward_Overview.pptx) ·
[Project report PDF](output/pdf/BioGraph_Steward_Final_Report.pdf) ·
[Word copy](output/docx/BioGraph_Steward_Final_Report.docx) ·
[Local setup](START_HERE.md#local-setup)

## What we improved

| Improvement | What the recorded results show |
|---|---|
| **Added source context** | In the captured 99-target cohort, **87 physical-association pairs** and **68 protein–location concepts** are absent from the baseline annotations. KRAS–CDC42BPB is an actual inspected example. These are qualified candidate records, not claims of new biological discoveries. |
| **More known location labels recovered** | Under the same ontology-qualified mapping, captured Pharos **41/51 → native source 44/51**. The previously used OpenCell reference changes **30/40 → 31/40**. The full comparison retains source overlap, coverage limits and mapping controls. |
| **A separate biological-process prediction gain** | Using a historical 20,412-protein graph, context-aware learning improves fixed-ontology Fmax **0.17155 → 0.21009** for additional biological-process annotations in proteins already annotated in that aspect (partial knowledge). Both primary reference views improve over the retained Pharos-derived predictor. Annotation refresh also helps. This study is separate from the 99-target app and agent evaluation. |
| **Recoverable graph qualification** | The retained example excludes **298 obsolete-GO-identifier records**, leaving **16,687 of 16,985 input records**. Original sources and every decision remain available. |

The [submission overview](docs/SUBMISSION_OVERVIEW.md) explains these distinct
comparisons. The [addition audit](docs/evaluations/source_agent_20261116/demonstrated_additions.json),
[location assessment](docs/evaluations/public_gold_20261115/report.html) and
[function-prediction report](docs/evaluations/CONTEXTUAL_COMBINATION_RESULTS_20261115.md)
provide the supporting results. Known-label recovery is not whole-graph
precision; shared sources and prior reference use limit independence. Additional
primary learning benefit over fully refreshed annotations remains uncertain.
The [forecast coverage note](docs/evaluations/final_delivery_20261117/prediction_coverage_feasibility.md)
explains the complete 3,300-protein temporal-gainer frame: 3,297 in the graph
and three retained outside it. Further temporal testing requires later labels.

A separate [source-verifier comparison](docs/evaluations/SOURCE_VERIFIER_COMPARISON_20261117.md)
reports the official base/disconfirm methods and learned controls against
released curator labels. Under the partial Evidence-input view, disconfirm
scored lower than base and supported claims were wrongly excluded. The verified
input-completeness gap and any corrected-input diagnostic are reported
separately. Current app assertions do not carry the complete native INDRA inputs
needed by that verifier, so these results do not enable automatic Pharos pruning.

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

Recorded examples also cover EGFR associations, TP53 locations and BRAF
archived pathways. A separate CIViC workflow preserves molecular profiles,
disease and therapy context for clinical evidence inspection. These tasks
demonstrate reusable execution within the captured cohort.
A separate [APP/PSEN worked example](docs/evaluations/GENERALIZATION_EXAMPLE_20261117.md)
reuses the constructor and agent on three proteins outside the original 99.
It includes a complete local real-data packet and the same fixed localization
comparison, with its neutral result and reference-coverage limits preserved.
Download the recorded-agent JSON from the demo. Complete graph and source
packets are supplied separately. [How to use it](HOW_TO_USE.md) explains the
steps and files.

## Current app, saved data and new runs

The public AWS demo is a **read-only replay** of completed agent work over two
real-data workspaces. It supports graph exploration, source inspection and
scientific comparisons without new model calls, source retrieval or edits.
[Deployment](docs/evaluations/public_demo_20261117/hosted_acceptance.json) and
[browser evidence](docs/evaluations/public_demo_20261117/hosted_browser_acceptance.json)
record this saved-example mode.

To ask a new agent question, use a local or operator installation with a complete
source workspace and a configured model endpoint. To construct a new Pharos
graph, the [cohort constructor](docs/CONSTRUCTION.md#build-through-the-app)
accepts an explicit list of 1–25 proteins and needs internet access, but no model
or GPU. The [agent instructions](docs/SOURCE_AGENT.md#operator-cli) explain how
supported source tools execute a new question. These reusable entry points
support evaluation on new cohorts beyond the delivered examples.

The demonstration uses a **captured Pharos319 baseline**, with separately saved
native GO and STRING profiles. It was assembled November 15 from an October 14
Pharos capture. The physical source is STRING 12.5. Exact GO, ontology and other
[source dates](docs/SOURCE_NOTES.md#current-reviewer-graph-and-source-dates)
are recorded separately from assembly dates. This is a fixed 99-target research
workspace. Updating application code does not refresh its upstream datasets. The
[delivery status](docs/DELIVERY_STATUS_20261115.json) identifies the deployed
application and saved artifacts.
The [designated primary graph handoff](docs/GOLD_SET_INTERFACE.md) has its
own verified decision ledger, preserved sources and exact captured Pharos-only
comparator. These full graph/source packets are separate submission assets or
authorized operator downloads; the public demo offers the recorded-agent JSON.

## Run locally

For a complete real-data example, open the separately supplied
`BioGraph_Steward_APP_PSEN_Example.zip`. Extract it into an empty directory and
follow **OPEN_EXAMPLE.txt**, which selects the recorded APP location-agent job
directly. Its runtime, source data and recorded job work offline with Python
3.10+, without a running model. This separate three-protein example does not
replace the public demo's two 99-target workspaces.

The [code-only software ZIP](output/software/BioGraph_Steward_Software.zip)
contains the portable app and launch instructions. The
[release index](docs/releases/20261115/README.md) records software verification,
deployment and artifact checksums.

The core app needs **Python 3.10+**, with no pip install, GPU or API key:

```sh
python3 app.py
```

Open `http://127.0.0.1:8765/`. A fresh checkout includes invented software
fixtures. The complete real-data source packet is supplied separately under
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

The separately supplied `BioGraph_Steward_Source_Verifier_Code.zip` is a
research-code adjunct, not the app or a self-contained benchmark. Its
**README_REPRODUCTION.txt** specifies the matching checkout, optional runtime
and separately obtained, licensed author/reference inputs. Raw cases, source
passages, predictions and fitted models are excluded.

The [submission summary](docs/FINAL_SUBMISSION.md) maps the work to judging
criteria. The [research appendix](docs/RESEARCH_APPENDIX_20261115.md) and
[experiment ledger](docs/EXPERIMENT_HISTORY.md) retain complete comparisons,
stronger controls and unsuccessful approaches. The
[release index](docs/releases/20261115/README.md) separates software, protected
source data and research artifacts.

Project repository: [github.com/mdomagalski/biograph-steward](https://github.com/mdomagalski/biograph-steward).
The core software is MIT licensed. Source datasets and reused tools retain
their own licenses; publishing code does not relicense the mixed-source data.
