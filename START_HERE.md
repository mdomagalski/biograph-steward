# Start here

BioGraph Steward lets the team inspect scoped biomedical evidence and follow each answer back to its source. The workbench is usable now. A bounded graph-prediction comparison is complete; it did not demonstrate a consistent benefit from adding GO hierarchy.

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

For a declared protein cohort, use **Build from a protein cohort**. Enter
1–25 exact UniProt accessions, select the focus protein and source profile, then
build. The graph and a cited candidate answer are saved together. The synthetic
construction example exercises the same path without network access. See
[construction and replay](docs/CONSTRUCTION.md) for limits and commands.

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

The [INMC comparison](docs/evaluations/INMC_COMPARISON_20261023.md) is complete and its test panel is consumed. The subsequent [Lambourne assay corroboration](docs/evaluations/LAMBOURNE_CORROBORATION_20261025.md) is also complete: all 3,222 nominated pairs are retained, with 2,676 assay eligible and 2,674 comparator eligible. Detection is 334/1,966 (17.0%) among Pharos-represented pairs versus 42/708 (5.9%) among resolved no-matches. Without observed HuRI/INMC pair overlap, rates are 74/1,619 (4.6%) versus 16/650 (2.5%). Study independence remains unresolved; this measures bounded assay concordance, not improvement caused by Steward. Both panels are now consumed.

The construction flow connects a declared protein cohort to retrieval, an
inspectable graph and a cited answer. The optional
[construction planner](docs/CONSTRUCTION_AGENT.md) is experimental: the live
development check still failed all four supported planning tasks. Use the explicit
cohort form for construction; inspect any optional model plan before building. The **Graph and
decision export** button prepares the complete source baseline, retained graph
and an all-undecided ledger without inventing pruning judgments. See the
[team walkthrough](docs/USER_WALKTHROUGH_20261026.md) for tasks to try.
The [delivery sequence](docs/BUILD_PLAN.md#delivery-sequence-and-completion-criteria)
separates product delivery, biological evaluation and the unknown official
scoring contract. Earlier experiments and outcomes remain in the
[archive ledger](docs/EXPERIMENT_HISTORY.md).

The [standards audit](docs/STANDARD_EXPORT.md) now publishes a bounded KGX
projection with the full original source packet. It reports upstream schema
and domain conflicts explicitly, so it is not a full conformance claim.
The [reference decision](docs/literature/REFERENCE_COMPARATOR_DECISION_20261025.md)
limits the completed assessment to retrospective corroboration; the lineage
audit could not certify an independent prediction test. The completed
[assay evidence publication](docs/ASSAY_EVIDENCE.md) exposes all 3,222 observations
in a standalone immutable layer and offline viewer, with 2,676 qualified edges,
3,173 protein nodes and all 546 excluded assays retained. Its 42 detected
Pharos no-matches remain a bounded inspection filter. The
[publication record](docs/evaluations/ASSAY_EVIDENCE_PUBLICATION_20261025.md)
preserves study/construct context, nondetections and original Pharos evidence;
it does not automatically prune or accept interactions. Qualified attachment to
saved live protein cohorts is implemented, as described below. Independent improvement
evaluation remains separate, and this consumed panel cannot become an unseen
test after prediction, enrichment or eligibility tuning.

## Inspect qualified assay observations

A saved live protein cohort can now attach the completed assay publication.
Open **Qualified assay evidence**, choose a saved publication, and attach it
to a new run. The panel preserves detected, nondetected and excluded observations
for pairs within that cohort. Source downloads and review decisions retain their
publication bindings. See [the attachment guide](docs/ASSAY_WORKBENCH.md) for
commands, source requirements and current export limits. This is an evidence
inspection workflow, not a new scientific-accuracy result.
