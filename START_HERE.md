# Start here

Choose the route that matches what you want to do.

| I want to… | Start here |
|---|---|
| **Use the app and inspect the real examples** | [How to use BioGraph Steward](HOW_TO_USE.md), the single user walkthrough. It links the public browser demo and follows an actual added connection. |
| **Watch the result first** | [Narrated walkthrough](output/walkthrough/BioGraph_Steward_Walkthrough.mp4) · [transcript](output/walkthrough/BioGraph_Steward_Walkthrough.txt) · [short presentation](output/presentations/BioGraph_Steward_Overview.pptx). |
| **Run the software on my computer** | The local setup below. Python 3.10+ is enough. No GPU, API key or pip install is needed for saved replay. |
| **Open a complete real dataset offline** | The separately supplied `BioGraph_Steward_APP_PSEN_Example.zip`. Its **OPEN_EXAMPLE.txt** opens the actual recorded APP location job. See the [worked example](docs/evaluations/GENERALIZATION_EXAMPLE_20261117.md). |
| **Run new agent questions** | [Source-agent operator guide](docs/SOURCE_AGENT.md#operator-cli). Supply an authorized source workspace and configure a live model endpoint. |
| **Construct a new graph or deploy the app** | [Cohort construction](docs/CONSTRUCTION.md) · [portability and hosting](docs/PORTABILITY.md) · [AWS deployment](deploy/aws/README.md). |
| **Understand the approach and results** | [Project report PDF](output/pdf/BioGraph_Steward_Final_Report.pdf) · [Word copy](output/docx/BioGraph_Steward_Final_Report.docx) · [submission summary](docs/FINAL_SUBMISSION.md) · [research appendix](docs/RESEARCH_APPENDIX_20261115.md) · [delivery files](docs/releases/20261115/README.md). |

The public demo opens directly in a browser with no sign-in, AWS account or
running model. It replays completed real agent work;
new inference, retrieval and edits are disabled. The narrated tour uses actual
local-app screenshot states and a labeled saved-report table, with no new
model calls during capture.

## Local setup

If you have the APP/PSEN example ZIP, extract it into an empty directory and use
its **OPEN_EXAMPLE.txt** first. It includes the runtime, complete captured source
files and saved agent result. No model, token or network access is needed for
that replay.

Use the current delivery branch:

```sh
git fetch origin
git switch codex/contextual-gain-delivery
git pull --ff-only origin codex/contextual-gain-delivery
python3 app.py
```

Open `http://127.0.0.1:8765/` and keep the terminal running.
A fresh checkout includes software fixtures rather than the complete real-data
source packet. If no authorized saved workspace is present, explicitly choose
the invented offline demonstration. It demonstrates the software, not a
biological result. For the real-data examples, use the
[hosted app](https://bi-3a117d5e2b3942678dc518fce65ab5d2.ecs.us-east-2.on.aws/)
or keep a supplied authorized workspace and all of its source files together.
A [small CC0 Reactome example](examples/reactome_context_20261113/README.md) is
also included for standalone real-source inspection.

Running a new agent question requires a model service. Saved replay and the
deterministic Pharos cohort constructor do not. The constructor uses internet
access to retrieve the requested proteins. Brev/GPU
compute is needed only when the selected live model is hosted there. See the
[source-agent guide](docs/SOURCE_AGENT.md), [local model setup](docs/LOCAL_MODEL.md)
and [delivery guide](docs/DELIVERY.md) for the operator details.

Research reproduction is separate from app replay. The
`BioGraph_Steward_Source_Verifier_Code.zip` adjunct contains code and
**README_REPRODUCTION.txt**, not reference cases or model outputs. It needs the
matching project checkout and separately licensed pinned inputs. Read the
[source-verifier results and input boundary](docs/evaluations/SOURCE_VERIFIER_COMPARISON_20261117.md)
before interpreting it as a pruning method.
