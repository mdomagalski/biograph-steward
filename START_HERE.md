# Start here

## Follow the recorded agent workflow

The current-source agent has completed its fixed local check: five supported
queries matched deterministic source execution, including an empty accepted-only
view; three unsupported requests were stopped by the controller without model
calls. This used 13 Nemotron calls and 972 completion tokens. These are workflow
checks, not scientific-accuracy or graph-prediction scores.

**The recorded agent workflow is available on the protected reviewer site.**
Its actual service restart, saved-source replay and private Neptune parity
passed; [delivery status](docs/DELIVERY_STATUS_20261115.json) links the receipts.

1. Open the [reviewer site](https://bi-3a117d5e2b3942678dc518fce65ab5d2.ecs.us-east-2.on.aws/)
   and sign in with the token supplied privately.
2. In **Start here**, open **Agent workflow** and the verified
   recorded KRAS run. Replaying checks saved sources without calling a model.
3. Follow its **question → plan → evidence → review proposals**. Check the
   complete answer and source passports; inspection priority does not remove
   other results. Start with **E002, KRAS–CDC42BPB**: its source passport shows
   **baseline pair present: false**, making one actual addition visible.
   The [agent guide](docs/SOURCE_AGENT.md) explains the steps.
4. Use **Review applied graph qualifications** and **What changed** to inspect
   the separate retained TP53 example and biological-reference measurements.
   These are distinct from agent execution checks.

The featured recorded job is `source_agent_eval_dc7b597201da_S01`. It uses the
99-target native-evidence workspace and an eight-result cap. The separate saved
manual KRAS answer displays all 14 matching partners. Do not interpret those
caps as a change to the source evidence.

The [3:58 narrated tour](output/walkthrough/BioGraph_Steward_Walkthrough.mp4),
[five-minute walkthrough](docs/JUDGE_WALKTHROUGH.md) and
[two-page team guide](output/pdf/BioGraph_Steward_Team_Review_Guide.pdf) explain
the current workflow. The [short presentation](output/presentations/BioGraph_Steward_Overview.pptx)
provides the project context. The tour uses actual local-app screenshot states
and saved evidence; it does not make new model calls.

Shared review needs only a browser—no AWS account, repository setup, Brev or
running model. It allows saved inspection and downloads; new retrieval,
inference and review edits are disabled. In an authorized local operator
installation, **Run the source agent** makes a new bounded model run and records
its actual outcome; see the [operator instructions](docs/SOURCE_AGENT.md).

Repository access alone does not include the full real-data packet. An
**invented offline demo** is a software fixture, not the real agent example.
Use the authorized real workspace for source review.

## What to assess

- Can you follow the question, model plan and executed tool to the cited answer?
- Can you follow one claim to its source and distinguish a review proposal from acceptance?
- Can you distinguish added evidence, an applied qualification and a measured result?
- Can you find an unresolved limitation and export the workspace?

Send the team the step where you got stuck, what you expected and what happened.
A screenshot is useful if it contains no token. Weekend feedback is due Monday,
November 16. Biological expertise is not required for the usability questions.

Read the [submission summary](docs/FINAL_SUBMISSION.md) for the capabilities,
results and judging criteria. Detailed unsuccessful approaches remain in the
[research appendix](docs/RESEARCH_APPENDIX_20261115.md).

## Run the software separately

Use the current review branch rather than the older `main` checkpoint:

```sh
git fetch origin
git switch codex/contextual-gain-delivery
git pull --ff-only origin codex/contextual-gain-delivery
python3 app.py
```

Open `http://127.0.0.1:8765/`. Keep the terminal running. Python 3.10+ is enough
for the core app and no pip install is required.

If the checkout has no authorized real workspace, expand the local software
builder and explicitly select the invented offline demonstration. It tests
navigation, questions and exports. Its records are synthetic and establish no
biological result. A separate [small CC0 Reactome example](examples/reactome_context_20261113/README.md)
contains real native source records that can be inspected without a server.

For real source construction, use the exact-accession or disease-cohort forms
and follow [construction](docs/CONSTRUCTION.md) and [retrieval](docs/SCOPED_RETRIEVAL.md).
These operations require source access and are disabled on the shared reviewer
site. Keep complete source folders together when opening supplied workspaces.
Copying only a graph JSON loses the evidence needed to verify its answer.

The [delivery guide](docs/DELIVERY.md) and [release index](docs/releases/20261115/README.md)
cover code, authorized data access and exports. Research methods and optional
model services have their own requirements. They are unnecessary for the shared
review above.
