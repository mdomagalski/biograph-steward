# BioGraph Steward

BioGraph Steward helps researchers inspect and qualify biomedical knowledge
from **NIH Pharos**. Ask a focused question, read its evidence graph, follow a
claim to its original source, and export the graph with every recorded decision.

**[Open the reviewer app](https://bi-3a117d5e2b3942678dc518fce65ab5d2.ecs.us-east-2.on.aws/)**
using the workspace token supplied privately. Start with the
**[3:42 narrated tour](output/walkthrough/BioGraph_Steward_Walkthrough.mp4)** or
the **[five-minute walkthrough](docs/JUDGE_WALKTHROUGH.md)**.
The [seven-slide overview](output/presentations/BioGraph_Steward_Overview.pptx)
provides a concise presentation.

The hosted demonstration uses real saved data for a 99-protein colorectal-cancer
cohort. It replays completed work so reviewers can inspect the same evidence.
It needs no AWS account, local installation or model server.

## A short tour

| In the app | What to do | What it demonstrates |
|---|---|---|
| **Start here** | Open the real-data example. | One current entry point and an explanation of the task. |
| **Question & graph** | Read the KRAS answer and select a cited relationship. | A focused answer linked to its graph paths. |
| **Inspect sources** | Inspect the source, identity checks and interpretation. | Where the evidence came from, what it means and what remains unresolved. |
| **What changed** | Inspect measured comparisons and the retained-graph example. | Added context, applied qualifications and the limits of each result. |
| **Export** | Download the answer or complete workspace. | The result, its decisions and the original input remain traceable. |

Two examples serve different review questions. The **KRAS evidence example**
shows additional GO annotations and sequence-qualified STRING physical
associations. Additions remain candidates. The **retained TP53 example** shows
the graph after identifier qualifications, with exclusions and original inputs
preserved. These are different graph products within one workflow.

## Results and their scope

| Assessment | Captured Pharos | Native GO source view | Coverage and interpretation |
|---|---:|---:|---|
| HOU known location labels | 41/51 recovered | **44/51 recovered** | 31/99 proteins matched. Two proteins improve. Shared HPA provider exposure remains. |
| OpenCell imaging categories | 30/40 recovered | **31/40 recovered** | 23/99 proteins matched. The gain survives exclusion of HPA support and explicit OpenCell references. Prior reference exposure remains. |

Separately, applied identifier qualification retains **16,687 of 16,985 input
records**. The 298 exclusions use obsolete GO identifiers; these are
identifier-currency decisions, not 298 experimentally disproved relationships.

Label recovery measures how much known reference information the graph retrieves.
The two location rows compare fixed source views, rather than a newly scored
union of the complete integrated graph.
It does not give a percentage of scientifically correct edges across the whole
graph. Reference-unavailable cases remain unknown. Added source rows and repeated
records do not count as independent experiments.

The separate historical function-prediction study improves fixed-ontology Fmax
from **0.17155 to 0.21009** over the Pharos-derived LocalPlus baseline. Updating
annotations also helps. The enriched graph has not consistently beaten the
stronger controls in matched graph-learning experiments. Biological pruning
can lose supported positives, so the product keeps uncertain evidence and does
not automatically treat a missing reference match as false.

Read the [product and submission summary](docs/FINAL_SUBMISSION.md) for the
judging-criteria map. The [research appendix](docs/RESEARCH_APPENDIX_20261115.md)
and [experiment ledger](docs/EXPERIMENT_HISTORY.md) preserve the complete results,
including unsuccessful methods and controls.

## What is integrated

- Pharos disease and protein cohorts with frozen source snapshots and retrieval coverage.
- Native GO annotations, ontology context and recorded source qualifications.
- STRING physical associations with exact identifier and full-sequence admission.
- CIViC molecular profiles and complete therapy sets in the clinical examples.
- Qualified assay, SIGNOR, MAP-IT and pathway sources in their respective examples.
- Candidate and accepted states, review history, explicit graph decisions and source-preserving exports.
- Optional NVIDIA planning and source-audit agents, plus evaluated specialist methods. The shared reviewer site uses saved guided workflows, with model calls and edits disabled.

The private AWS app hosts reviewer access. Its Neptune inspector verifies the
separate retained Pharos graph against its saved source. Ordinary questions
read their saved workspace files. Source availability depends on the example;
the app does not silently substitute one source profile for another.

## Running the software locally

For reviewing the real dataset, use the hosted app above. A fresh repository
checkout contains software and **invented offline fixtures**, rather than the
complete mixed-source research packet. The fixture demonstrates software
operation and provides no biological evidence.

Python 3.10 or newer runs the core app without pip, a GPU or an API key:

```sh
python3 app.py
```

Open `http://127.0.0.1:8765/`. If authorized real workspaces are present, the app
offers the real saved example. Otherwise explicitly open the offline software
demonstration. [START_HERE](START_HERE.md) explains these routes. A small
[CC0 Reactome example](examples/reactome_context_20261113/README.md) is also
included for real-source inspection outside the full dataset.

The current development is on the private
[`codex/contextual-gain-delivery` branch](https://github.com/mdomagalski/biograph-steward/tree/codex/contextual-gain-delivery).
The [delivery status](docs/DELIVERY_STATUS_20261115.json) records accepted hosted
checkpoints and remaining publication actions. The [release index](docs/releases/20261115/README.md)
separates tested software from protected source data and research artifacts.

## Technical documentation

[Construction](docs/CONSTRUCTION.md) · [Scoped retrieval](docs/SCOPED_RETRIEVAL.md) ·
[Source qualification](docs/NATIVE_PHYSICAL_SOURCE.md) · [Export and standards](docs/STANDARD_EXPORT.md) ·
[Graph and decisions](docs/GOLD_SET_INTERFACE.md) · [Testing](docs/TESTING.md) ·
[Deployment](docs/PORTABILITY.md)

The core software is MIT licensed. Source datasets and reused tools retain
their own licenses and notices. Mixed-source public redistribution requires
its own permissions and is separate from publishing the software.
