# Organizer update received October 26 2026

This note reconciles the additional Slack excerpts supplied by the user with
the current implementation. The excerpts were not independently retrieved from
Slack and do not include message dates or thread permalinks. October 26 is the
date received here, not an inferred posting date.

## Confirmed report instructions

The linked [midpoint template](https://docs.google.com/document/d/1TZa4ECvzNh39VL9W_cyXvtwFwJBYwIcyjz37hR1GAIw/edit?usp=sharing)
was downloaded through its public Google Docs text and Word exports. It asks for
team name, track, overall status, a two-to-three-sentence summary, three to five
accomplishments, blockers/help needed, and milestones for October 28–November 3,
November 4–10, and November 11–17.

The template says to email the completed form to **berylrab@amazon.com** and
**bbusby@nvidia.com** by **EOD October 27, 2026**. It gives **November 17, 2026**
as the final deadline and says a final template is forthcoming. No deadline
timezone is specified. The organizer's email instruction is source information,
not authorization for this assistant to send a message.

The additional AWS posts say credit codes were provisioned by email, with some
accounts credited directly. This is consistent with the user's confirmation
that credits were received. It does not establish the account balance, verify
redemption or make AWS deployment an evaluation requirement.

## Evaluation statements and their interpretation

Ben's supplied reply is: **“We'll compare subgraphs to whole graph. Ideally send
both!”** It follows questions about the gold set and whether to send a pruned
graph or every Pharos edge with a keep/prune verdict and confidence.

| Status | Consequence |
|---|---|
| Explicit statement | The organizers intend a comparison of submitted subgraphs with a whole graph. |
| Strong contextual interpretation | Prepare both the resulting subgraph and an auditable edge-decision record. “Both” most naturally refers to the preceding graph-versus-decisions question, although the excerpt does not repeat the objects. |
| Still unspecified | Whole-graph artifact and version; whether it is the deployed Pharos resource or a separate organizer representation; disease/cohort scope; scoring unit; label semantics; formats/identifiers; allowed evidence cutoff; treatment of missing or out-of-scope edges, abstentions and confidence. |
| Not implied | Teams must download all Pharos; omitted edges are false; every source edge should receive a numeric confidence; gold contains injected errors; public references are prohibited; or held-out final labels must be released. |

A scoped retrieval and a pruning decision are different operations. An edge
outside our declared cohort or retrieval budget must not be described as
biologically rejected. Added assay evidence also needs to remain distinguishable
from original Pharos evidence and from the organizer's baseline.

## What the current code can actually deliver

The [gold-interface packet](GOLD_SET_INTERFACE.md) preserves every normalized
edge in the **retrieved source graph**, source snapshots and qualifiers. It
validates exactly one keep/prune/abstain disposition per packet edge and copies
the complete baseline packet with the decision ledger. An unchanged template
is all abstentions. Confidence is null; local acceptance is not a calibrated
scientific confidence or an automatic pruning verdict.

The two identified export gaps have now been closed for the demonstrated profile:

1. `gold-decisions` materializes the retained graph by removing only explicit
   prune decisions. It keeps abstentions, isolated nodes and consistent support
   mappings; partial support removal resets the affected review state while the
   full original graph remains available. Differences and decision bindings are
   verified offline. This is a deterministic export, not a biological classifier.
2. The gold packet supports [assay-attached runs](ASSAY_WORKBENCH.md), preserving
   the complete publication, qualifications, exclusions and source-bound review.
   The [real export demonstration](evaluations/SUBMISSION_DEMO_20261026.md)
   verifies an extracted ZIP without changing the source run. Both real example
   edges remain undecided; no pruning judgment was invented.

The existing Reactome KGX subset is a bounded format projection. Its omitted
relations are not a scientifically pruned graph. Full Biolink conformance also
remains unresolved; do not rename the export to imply either property.

## Updated immediate sequence

1. Maintain the midpoint report as a working draft, reporting implemented
   capability, negative/mixed results and remaining risks accurately. Revise it
   after the day's work and team review; do not treat report polishing as a
   blocker to implementation or send it without explicit instruction.
2. Completed the two-part submission export: retained subgraph, exhaustive
   disposition ledger and complete retrieved baseline/source packet. Test
   preservation, explicit abstention and every removal on controlled fixtures.
   Extend packet preservation for qualified assay sources without flattening
   their biological meaning.
3. The [bounded construction-agent comparison](evaluations/CONSTRUCTION_PLANNER_20261026.md)
   is complete. The latest [tool V2 comparison](evaluations/construction_planner_tool_v2_20261026_summary.json)
   matched three of four supported requests, while admitting two of eight
   unsupported requests, including a dropped assay requirement. Keep the
   planner experimental. Use the verified
   deterministic example for a short team walkthrough, recording answer/source
   discovery, decision interpretation and export obstacles. This is an initial
   usability pilot, not a replacement for intended-user evaluation.
4. The selected [IntAct/IMEx preparation](INTACT_FIDELITY_PREPARATION.md) pins
   eight publication artifacts and a frozen curation/evidence-fidelity protocol,
   with a mandatory semantic amendment. The official reader has now passed its
   synthetic controls; the four development studies contain four eligible
   human-protein evidence rows across two publications. The other ten rows
   involve RNA or mouse proteins and remain in the exclusion ledger. Four
   reserved interaction files remain unopened. The [real source-faithful workbench flow](INTACT_EVIDENCE_WORKBENCH.md)
   now passes import, readable-answer and gold-export fidelity on all four
   eligible development records, preserving the original Pharos graph. The code
   was committed and frozen at `bca13a7`. The [bounded provenance review](evaluations/INTACT_PROVENANCE_READINESS_20261026.md)
   resolved bibliographic identifiers but left shared-study provenance and
   reserved pair overlap unresolved. The current final-assessment gap is richer
   publication/experiment provenance plus a separately frozen execution path;
   reserved interaction files remain unopened. Public
   references remain useful; neither a different database nor these new Slack
   statements establish source independence or general scientific accuracy.

These statements narrow the submission deliverable; they do not invalidate the
completed evaluations or justify starting another model/source sweep. The INMC
comparison and Lambourne corroboration remain consumed, task-specific results.

## Report readiness after the assisted walkthrough

One assisted participant has located the answer/status, identified STRINGDB and
its missing paper reference, and found the assay/outcome. Construct terminology
was unclear. The inspector now has a readable table and explanation. A partial
assisted recheck elicited a broadly correct bait definition; prey, mapping-link
identification and use of the revised display remain unverified. Source-table discovery and the export walkthrough
remain unfinished. Record this as early assisted feedback, not established
usability or scientific validation. See the [session record](USER_WALKTHROUGH_20261026.md).

The [NVIDIA interface investigation](literature/CONSTRUCTION_PLANNING_REUSE_20261026.md)
identified a published prompt pattern for the deployed Nano model. The current
JSON-only transport does not reproduce it, and the available BFCL Nemotron
parser targets a different checkpoint. A separately frozen two-request diagnostic
has now returned an exact construction proposal for the supported request and
declined the unsupported treatment request. These are textual responses; nothing
was executed. The first isolated tool adapter matched one of four supported
requests, versus zero for JSON v3, while admitting one unsupported assay-filter
request as an unfiltered plan. Tool V2 subsequently matched three of four
supported requests, correcting pathway-only and subset selection. It still
omitted pathways from a combined request and admitted two of eight unsupported
requests: an ambiguous request and an assay-filter request returned as unfiltered
PPI plans. Those results remain unchanged. The current UI/API now adds an
explicit-selection wrapper around the unchanged JSON v3 planner: selected and
proposed retrieval choices are visible together, mismatches block construction,
and review is required before building. The server validates choices before
inference and checks the current choices against the saved plan before source
access. Tool V2 remains outside production execution. The live comparison did
not exercise this new wrapper; local integration checks do not establish a
live gain or verify arbitrary free-text conditions. No biological gain follows
from these planning checks.
The deployed service is Nano on vLLM; it is
not a verified NVIDIA NIM deployment or reproduced BFCL evaluation.

| Report evidence | Result we can support | Important boundary |
|---|---|---|
| [Deterministic graph and submission demonstration](evaluations/SUBMISSION_DEMO_20261026.md) | Real cohort, qualified assay attachment, retained graph, complete edge decisions and preserved sources reopen from the export. | All example decisions are abstentions; no scientific pruning claim. |
| [Latest construction planner comparison](evaluations/construction_planner_tool_v2_20261026_summary.json) | Tool V2 matched 3/4 supported requests, following 1/4 for tool V1 and 0/4 for JSON v3; it admitted 2/8 unsupported requests, versus 1/8 for V1. | Consumed development cases; five empty tagged calls were rejected, without establishing semantic refusal. Exact selections were not supplied. No tools executed; biological gain and general reliability remain unestablished. |
| [Guided selection and review](CONSTRUCTION_AGENT.md#current-guided-form-and-execution-check) | UI/API integration checks reject mismatched, unreviewed or stale choices, preserving the model proposal and original trace. | The v3 model prompt/provider is unchanged; tool V2 is not promoted. Arbitrary question conditions, live gain and intended-user usability remain unverified. |
| [Prediction comparison](evaluations/inmc_comparison_20261023_summary.json) | No consistent GO-hierarchy gain across three seeds on 1,751 eligible measured pairs. | Fixed task and consumed panel; no general failure or equivalence claim. |
| [Published assay comparison](evaluations/lambourne_corroboration_20261025_summary.json) | 3,222 nominated pairs: 376 detections, 2,300 nondetections and 546 excluded tests. Forty-two detections lacked a match in the bounded saved Pharos lookup. | Additional assay context, not 42 novel or independently validated interactions. Source overlap and incomplete lineage constrain independence. |
| [Assisted walkthrough](USER_WALKTHROUGH_20261026.md) | A participant located key evidence and reported a terminology problem; a partial recheck captured a broadly correct bait definition. Source/export integrity checks passed separately. | One assisted participant and incomplete tasks; no measured usability improvement. |
| [IntAct/IMEx source-fidelity flow](INTACT_EVIDENCE_WORKBENCH.md) | Official-reader-backed records retain source roles, hosts, references and qualifications through the real Pharos-attached graph, readable answer and gold export: 4/4 eligible development records pass fidelity. All 14 source evidence rows remain accounted for. | Two pairs from two eligible publications, all positive co-immunoprecipitation; real negative/default and expanded strata remain unevaluated. Four reserved interaction files remain unopened. Biological accuracy, novelty and prediction gain are not established. |

Before submission, report the completed NVIDIA comparison and keep deterministic
construction as the demonstration path. Prioritize completion of the assisted
source/export walkthrough and a concise demonstration using these existing
artifacts. Do not delay the report for new databases, model sweeps or AWS
deployment. The IntAct development flow is now demonstrated. Keep the
implementation frozen and complete the provenance/overlap audit before reserved-study
assessment; passing source fidelity does not resolve biological validation.

## Remaining clarification to request

“We will prepare both a resulting subgraph and a full decision ledger for its
retrieved Pharos baseline. Could you specify the whole-graph baseline/version,
comparison unit, identifiers/file formats, and how out-of-scope edges,
abstentions and uncalibrated confidence should be represented? Is the ledger
expected to cover our submitted source scope or the entire organizer graph?
We do not need access to hidden final test labels.”

This is suggested wording only. No email or Slack message was sent.
