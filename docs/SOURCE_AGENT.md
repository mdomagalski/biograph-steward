# Current-source agent workflow

BioGraph Steward's current-source agent turns a supported research question
into a source-bound focused graph, cited answer, inspected evidence and review
proposals. It uses the configured model to direct the workflow. The graph query,
source statements, identity checks and permitted proposal meanings come from
the existing source adapters.

This is the current agent route in the application and operator CLI. The older
one-call question planner and BioRED literature-audit experiment are separate
components; their recorded results have not been replaced. Live evaluation and
hosted availability have separate receipts; a completed local evaluation does
not establish hosted availability. See the
[NVIDIA integration record](NVIDIA_INTEGRATION_STATUS_20261113.md) and
[fixed evaluation protocol](evaluations/SOURCE_AGENT_PROTOCOL_20261116.md).

## Recorded fixed check — November 16

The [current-tool assessment](evaluations/SOURCE_AGENT_RESULTS_20261116.md)
completed five supported executions with exact full-query, cited-answer and
focused-graph agreement against explicit deterministic execution. Four returned
source evidence; the accepted-only control returned a valid empty result.
Three additional unsupported requests were stopped by preflight guards with
zero model calls. Together these passed eight predeclared behavioral checks.

The supported cases used **13 Nemotron calls and 972 completion tokens**.
Application code grounded every identity; most planning schemas allowed one
query tool plus abstention. The TP53 location case allowed two query tools.
This does not establish general free-text routing or scientific accuracy.
Original source, full-graph and review hashes stayed unchanged. See the
[aggregate receipt](evaluations/source_agent_20261116/summary.json).

The featured job is `source_agent_eval_dc7b597201da_S01` in
`native_evidence_workspace_20261115`. Its eight-result limit differs from the
separate manual KRAS answer's 14 displayed partners. It is now available on the
protected reviewer site after the accepted runtime update and real restart,
with the original graphs, sources and reviews preserved. See the
[hosted acceptance receipt](evaluations/source_agent_20261116/hosted_acceptance.json).
New inference remains disabled on that shared site. The source-bound replay
path is:

```text
/?run=native_evidence_workspace_20261115&question=native_physical_KRAS_question_v3_20261115&agent_job=source_agent_eval_dc7b597201da_S01&view=data
```

## What happens when it runs

1. **Plan:** the model receives the question, exact proteins, attached source
   tools and explicit limits for the open workspace. The controller checks its
   proposed tool and arguments. A wrong identity, evidence view, result cap or
   source qualification is rejected, without rewriting the proposal.
2. **Query and inspect:** an existing source engine executes the validated
   query and constructs the focused graph and deterministic cited answer. The
   model selects up to three returned citation groups for inspection. Every
   underlying source assertion in a selected group is inspected, up to 32 per
   group. Complete passports and explicit coverage are retained. Compact model
   context identifies omissions and binds back to those full passports.
3. **Propose review:** the model selects only review options justified by the
   inspected adapters. **Retain candidate context** keeps an eligible source
   claim in its current state; **Needs review** identifies an unresolved issue.
   Neither accepts evidence nor prunes the graph. No free-form model claim
   replaces the cited source statements.

All query results remain available, including citations the model did not
prioritize. Inspection priority is not a hidden filtering or confidence rule.
An oversized source group fails explicitly rather than substituting only its
first record. The budget is at most three model calls, each capped at 1,200
output tokens, one bounded query and three citation-group inspections. A valid
empty query can finish earlier.

## Available source tools

The application advertises only tools actually attached to the selected saved
workspace. It supports both explicit protein cohorts and disease-derived
cohorts; cohort membership does not make every native record disease-specific.

| Tool | Source scope | Interpretation retained |
|---|---|---|
| Native physical | Saved native STRING physical associations within the exact mapped cohort | Proximity or shared-complex support; not a direct-binding, assay-specific or disease-mechanism claim. |
| Native location | Positive active GO cellular-component `located_in` profile with all admitted evidence codes | Keep source evidence codes, references and assigning databases. This is neither all GO context nor experimental-only evidence. |
| Archived pathway | Native-supported exact-revision WikiPathways context in a qualified retained workspace | Shared source-model context; compatible gene references do not establish an exact historical protein form or a direct protein interaction. |

The main native-evidence workspace exposes physical and location tools. Its
matched retained companion exposes the archived pathway tool. The agent does
not silently switch workspaces or combine their record totals. Native archived
support remains required for the pathway query.

Both **candidate** and **accepted** views are supported. These are local review
states. An accepted-only answer can be empty while candidate source evidence
is still available; this is not a biological rejection. State the requested
view consistently in the question and the controls.

The interface binds exact mentioned protein identifiers or symbols. It uses
bounded scope checks, not general natural-language or biological verification.
Unsupported conditions—such as direct binding, an assay, tissue specificity,
experimental-only source filtering or clinical recommendations—must not be
silently replaced by a broader query. A preflight rejection makes zero model
calls and is reported as a controller decision, not model reasoning.

## Use the application

Open an authorized saved workspace and find **Agent workflow** on **Start
here**. Its source-tool list is checked without inference. In a live operator
installation, choose the evidence view, name one exact cohort protein in the
question and select **Run the source agent**. Examples include:

- “Inspect candidate native STRING physical associations with KRAS.”
- “Show candidate native GO location annotations for TP53.”
- In the retained companion: “Show candidate archived pathway context for BRAF.”

The resulting record separates the model plan, complete cited answer, focused
graph, actual source inspection and proposed review actions. Model planning
reasons are labelled unverified rationale; source facts remain deterministic.
Errors, abstentions and partial outcomes remain distinguishable from completed
runs.

A shared saved-data reviewer site disables live inference and new agent jobs.
Use **Open a recorded agent run** and **Replay the recorded run** instead.
Replay verifies the saved result against its current source and deterministic
tools without calling a model. Recorded live-model runs are distinguished from
injected development/test records. A manual cited answer is not presented as a
recorded agent run.

## Operator CLI

The core requires Python 3.10+ and no third-party package installation. Real
source workspaces must be supplied separately with their complete authorized
source packets; a fresh code checkout contains no such packet. First inspect
what is actually available, without creating a model client:

```sh
source_run=runs/native_evidence_workspace_20261115
python3 app.py source-agent-catalogue --run "$source_run"
```

For live execution, configure the existing model transport described in
[Local model setup](LOCAL_MODEL.md). The current agent reuses the
`BIOGRAPH_PLANNER_*` connection settings and the same `JSONModelClient`; the
legacy `BIOGRAPH_PLANNER_PROTOCOL` does not select this new controller.
Once the intended model service is ready, run:

```sh
python3 app.py source-agent-run \
  --run "$source_run" \
  --question 'Inspect candidate native STRING physical associations with KRAS.' \
  --view candidates --max-results 8 --max-paths 2 --go-limit 10
```

The command prints the new job path, status, provider identity, whether an
actual model run was recorded, model/tool counts and progress directory.
Immediate request-intent, response and tool-result events survive interruption
in a separate new directory. An incomplete attempt is not published as a
successful run. Prior events and jobs are never overwritten.

To replay the job, substitute its printed path for the example below:

```sh
python3 app.py source-agent-verify \
  --job runs/source_agent_RECORDED_ID --runs-dir runs
```

This command reports recorded model calls separately from verification model
calls, which are zero. The source graph, review state, query, focused graph,
passports, proposal options and model-input commitments are checked. A changed
source or altered saved result fails verification.

Optional `--constraints` accepts a bounded JSON object. It can specify `view`,
`protein_id`, `tool`, `max_results`, `max_paths` and `go_limit`. Command-line
flags cannot contradict or change the type of an explicitly supplied value.
Pathway `source_support` is fixed to `native_supported`; it is not a switch for
dropping native eligibility checks.

## What this establishes

This route makes agent-directed source selection, contextual graph extraction
and source inspection executable in the product. It does not fetch new source
data, enrich the underlying full graph or change learner inputs. If it selects
the same tool and scope as the deterministic workflow, the cited result should
agree; that parity is source fidelity, not a prediction gain.

The separate learned GCN/context-combination study and public-reference
annotation assessments retain their own endpoints. No agent benefit, general
scientific accuracy or automatic biological pruning follows merely from valid
JSON, a cited passage, a successful replay or a model-produced recommendation.

Recorded jobs include source evidence and full passports. Their availability
and redistribution follow the source terms; the software's MIT license does
not relicense those records. Keep complete source packets and original job
files together when transferring an authorized example. Brev/GPU compute is
needed only for new calls to a model hosted there; saved review and verification
use CPU and need no running model server.
