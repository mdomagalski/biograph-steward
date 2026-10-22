# Start here

BioGraph Steward lets the team inspect scoped biomedical evidence and follow each answer back to its source. The workbench is usable now; the matched graph-prediction comparison is being prepared separately.

## Start locally

From the repository directory:

```sh
python3 app.py
```

Use Python 3.10 or newer. No pip installation is needed for the core app. Open `http://127.0.0.1:8765/` and keep the terminal running; Ctrl+C stops it.

## Try the evidence workflow

1. Choose **Offline demonstration**, then **Build synthetic demonstration**. This contains invented records and is for software inspection only.
2. Select **Inspect candidates**. New assertions have no local scientific approval; the accepted view may be empty.
3. Open a protein or assertion, then its source passport. Inspect identifiers, qualifications, raw evidence and provenance.
4. Ask a supported question in **Ask a scoped question**. Follow **Question → Graph → Answer → Sources** and open a citation.
5. On the synthetic example, record a review with a reviewer and reason to test the workflow. It creates a new run and preserves the earlier version.
6. Download the graph or question ZIP. New answer exports include the source context and review state.

If real runs already exist, **Open a saved real example** or **Saved graphs and answers** opens them directly. A fresh checkout does not include live source snapshots.

## Retrieve actual Pharos evidence

Choose **Live Pharos API**, search for `colorectal`, and select the exact returned disease. Related disease names are not automatically equivalent.

For the existing CRC demonstration, select **colorectal adenocarcinoma**, **Fuller scoped context**, and a cap of **100 targets**. Use `colon rectum` as tissue words only for this explicit expression scope. After retrieval, inspect **Retrieval coverage** for caps, omitted families and errors. A failed request stops with an error; it never becomes synthetic evidence.

A smaller **Quick pathway preview** with 25 targets is useful for checking connectivity. The CLI diagnostics are:

```sh
python3 app.py doctor
python3 app.py search colorectal
```

[Scoped retrieval](docs/SCOPED_RETRIEVAL.md) describes the data boundaries. [CIViC evidence](docs/CIVIC_EVIDENCE.md) describes the supported molecular-profile/therapy query and bounded retrieval. Inspect complete profiles and therapy sets; a multi-drug annotation does not establish a single-drug effect.

## Review, reopen and compare

Source editorial status and our local review state are separate. A model output is not a human review. Empty accepted-only answers can be correct when no local assertions have been accepted; candidate exploration remains explicit.

Saved URLs reopen the graph and question. **Comparison history** provides read-only access to saved snapshot comparisons. File integrity and compatibility with the current implementation are checked separately; an older comparison may require its original source version for replay. See [snapshot comparison](docs/SNAPSHOT_REFRESH.md).

## Optional planner and hosting

The **Plan a research question with one model agent** panel requires a configured model. It selects one supported read-only query or abstains; application code executes the query and renders the cited answer. It does not retrieve new sources or decide scientific truth. See [planner configuration](docs/PLANNER_PROTOCOL.md).

For Docker/Brev and token-protected access, use [portability](docs/PORTABILITY.md). The local demonstration and current input audits need no GPU or AWS account.

## Where development stands

The active research task is the [INMC input-readiness investigation](docs/evaluations/INMC_INPUT_READINESS_20261022.md), followed by a frozen Pharos-versus-enriched graph comparison if the assay and source-overlap gates pass. Earlier experiments and their outcomes are in the [archive ledger](docs/EXPERIMENT_HISTORY.md), not the active product menus. The [build plan](docs/BUILD_PLAN.md) lists remaining work and challenge limitations.
