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
   is complete. Structural correction reduced invalid plans, but supported task
   selection still failed. Keep the planner experimental. Use the verified
   deterministic example for a short team walkthrough, recording answer/source
   discovery, decision interpretation and export obstacles. This is an initial
   usability pilot, not a replacement for intended-user evaluation.
4. Prepare the selected [IntAct/IMEx public reference](literature/PUBLIC_REFERENCE_OPTIONS_20261026.md)
   for a defined curation/evidence-fidelity task and audit overlap. Public
   references remain useful; neither a different database nor these new Slack
   statements establish source independence or general scientific accuracy.

These statements narrow the submission deliverable; they do not invalidate the
completed evaluations or justify starting another model/source sweep. The INMC
comparison and Lambourne corroboration remain consumed, task-specific results.

## Remaining clarification to request

“We will prepare both a resulting subgraph and a full decision ledger for its
retrieved Pharos baseline. Could you specify the whole-graph baseline/version,
comparison unit, identifiers/file formats, and how out-of-scope edges,
abstentions and uncalibrated confidence should be represented? Is the ledger
expected to cover our submitted source scope or the entire organizer graph?
We do not need access to hidden final test labels.”

This is suggested wording only. No email or Slack message was sent.
