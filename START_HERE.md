# Start here

## Review the real application

1. Open the [shared reviewer app](https://bi-3a117d5e2b3942678dc518fce65ab5d2.ecs.us-east-2.on.aws/).
2. Sign in with the workspace access token supplied privately.
3. Follow **Start here**, then **Read the cited answer**, **Inspect its source**
   and **What changed**. The [five-minute guide](docs/JUDGE_WALKTHROUGH.md)
   explains the example and what to look for.

Prefer to watch first? The
[3:42 narrated tour](output/walkthrough/BioGraph_Steward_Walkthrough.mp4)
shows the actual hosted workflow with captions. A
[short presentation](output/presentations/BioGraph_Steward_Overview.pptx) is also available.

The hosted example uses real saved Pharos data and separately recorded source
context. It replays the completed workflow. Reviewers can inspect questions,
sources, results and downloads. It does not run new model calls, retrieval,
pruning or review edits during this shared session.

No AWS account, Brev instance, local tunnel or installation is needed. Repository
access alone does not include the full real-data packet. If you see an
**invented offline demo**, you have opened the software test route. Use the
shared app above for biological review.

## What to assess

- Can you state the question and find its answer?
- Can you follow one claim to its source and explain its review state?
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
