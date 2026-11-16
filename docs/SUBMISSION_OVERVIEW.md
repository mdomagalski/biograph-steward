# BioGraph Steward | Submission overview

BioGraph Steward uses a bounded NVIDIA Nemotron agent to guide a research
question through supported source tools. It returns a focused Pharos evidence
graph, a cited answer, inspected source records and grounded review proposals.
A researcher can trace a connection, inspect qualifications and reuse the
graph with its source context.

## Improvements over the captured Pharos baseline

| Improvement | Demonstrated result | What it gives a researcher |
|---|---|---|
| Additional qualified connections | **87 physical-association pairs** and **68 protein–location concepts** absent from the captured annotations | More candidate connections to investigate, with source and identity checks preserved. Overlapping connections remain identified separately. |
| More known locations recovered | **41/51 → 44/51** positive labels across 31 matched proteins, using the same ontology-qualified mapping | Additional reference-supported location context. The OpenCell source-exclusion check also improves **30/40 → 31/40** across 23 proteins. |
| Better later function recovery in a separate prediction study | Fixed-ontology Fmax **0.17155 → 0.21009** over retained Pharos-derived LocalPlus; paired gain interval **[+0.00803, +0.06914]** | A measured improvement from adapting an established context-aware prediction method. This historical 20,412-protein study has its own controls and is separate from the 99-target app. |
| Applied identifier qualification | **298 obsolete-GO-ID exclusions**, with originals and every decision retained | A current-identifier view that colleagues can inspect, export and revise. |

**See an actual addition:** in the recorded KRAS agent run, inspect citation
**E002, KRAS–CDC42BPB**. Its existing source passport reports **baseline pair
present: false** and **integration state: new workspace pair**, alongside native
STRING 12.5 score 203 and sequence-identity checks. This is one of the 87 pairs
absent from the captured graph. The [saved-artifact audit](evaluations/source_agent_20261116/demonstrated_additions.json)
also verifies that the complete KRAS result has three such pairs among 14;
the agent's fixed eight-result answer contains one.

These results measure different improvements, with their scopes preserved:
added source context, positive-label recovery, a separate function-prediction
benchmark and identifier qualification. Source additions compare exact captured
protein pairs or protein–GO-term concepts; the location assessment compares
mapped reference categories. These endpoints are not pooled into a graph-wide
accuracy score. The location references retain shared-source/prior-use limits;
the prediction study includes a stronger annotation-refreshed baseline. Full
controls and qualifications remain in the linked reports below.

The agent's actual development comparison, portable software acceptance,
narrated local demonstration and protected hosted replay are complete. The
[hosted acceptance](evaluations/delivery_readiness_20261116/hosted_acceptance.json)
and [delivery status](DELIVERY_STATUS_20261115.json) record the verified deployment;
the tour remains explicitly filmed in the local application.

**[Open the protected reviewer site](https://bi-3a117d5e2b3942678dc518fce65ab5d2.ecs.us-east-2.on.aws/)**
and follow **[How to use BioGraph Steward](../HOW_TO_USE.md)**. The
[judge evidence route](JUDGE_WALKTHROUGH.md) maps that workflow to the rubric.
Use the token supplied privately. Saved review needs only a browser; no AWS
account, local setup, Brev instance or model server is required. Exact accepted
deployment and release identities are recorded in the
[delivery status](DELIVERY_STATUS_20261115.json).

## What to try

The two real examples share a **99-target colorectal-cancer cohort** and show
different operations, rather than interchangeable graph versions:

- **Follow the recorded agent:** inspect its question, validated tool plan,
  cited results, complete selected-source inspections and proposed review
  decisions. The primary KRAS agent run displays eight of 14 matching proteins
  under its fixed cap, while the older manual answer displays all 14. Proposals
  retain candidate context or request review; they apply no graph decisions.
  Four sequential tabs separate the plan, evidence graph, inspections and proposals.
- **Explore added source context:** read the KRAS answer, follow one of its 14
  candidate protein connections and inspect its native STRING source. Start
  with CDC42BPB to see an actual connection absent from the captured baseline.
  Of 330 physical pairs, 243 already share a pair with the baseline and 87 do
  not. Native GO supplies 3,309 rows representing 429 protein–location concepts
  across 94 targets; 361 concepts overlap the captured annotations and 68 are
  additional. These are pair/concept counts, not independent-study counts.
- **Review applied graph qualifications:** inspect the TP53 pathway example
  after explicit qualification decisions. Its 16,985 input evidence records
  become 16,687 retained records; 298 obsolete-GO-identifier exclusions have
  reasons, while uncertain records remain available. This is applied identifier
  qualification, not 298 proven biological errors.
- **Read the measured result and export:** inspect the featured comparison,
  then distinguish the focused answer from the retained graph, complete
  decision ledger and original baseline/source packet.

Among 31 proteins with matching location-reference labels, the captured Pharos
view recovers 41 of 51 positive labels and qualified native annotations recover
44 of 51. These are fixed source-view comparisons, not a newly scored union of
the full graph. Coverage and shared-source limits remain explicit. A separate
source-exclusion sensitivity check recovers 30 of 40 to 31 of 40 labels among 23
OpenCell-matched proteins. These are known-annotation recovery results;
they do not measure the fraction of the whole graph that is correct.
The challenge's same-learner link-prediction panels did not show a reliable
enriched-graph advantage. A separate historical function-recovery study
improved retained LocalPlus in both primary views. Updating the baseline's
annotations also helped, and additional primary benefit over that stronger
baseline was uncertain. These [learned-model results](evaluations/CONTEXTUAL_COMBINATION_RESULTS_20261115.md)
retain their own endpoints and controls; the current agent check does not
claim their gains.

The [current-source agent comparison](evaluations/SOURCE_AGENT_RESULTS_20261116.md)
completed all eight fixed behavioral checks: four nonempty queries and one
valid accepted-only empty query matched the deterministic query, cited answer
and focused graph exactly. Three unsupported or unresolved requests stopped at
preflight without calling a model. These results demonstrate bounded execution
and source fidelity. Most requests already fixed one tool and protein; only
the TP53 location case offered two tool choices. The agent changed no source
graph or learner input and therefore supplies no new prediction-gain result.

## What is delivered

The working tools cover bounded construction, explicit identifier checks,
versioned assertions, source passports, guided multihop inspection, guarded
snapshot comparison and reproducible graph/decision exports. Stable identifiers,
Biolink references and bounded KGX/SSSOM profiles have recorded limits. AWS hosts
the protected workbench; Neptune supplies a private mirror/inspection route.
The current-source Nemotron agent orchestrates these existing tools and source
inspections. Its adapter-grounded proposals remain for a reviewer. Earlier
planner and literature-audit experiments retain their separate results and
limits; the auditor did not outperform its specialist control. No model result
automatically accepts or biologically prunes evidence.
The shared reviewer route replays saved work; live construction, retrieval,
model calls and review edits are disabled there.

The **[final submission summary](FINAL_SUBMISSION.md)** maps these outcomes to
the organizer's 40% usability, 30% accuracy/pruning, 20% explainability and 10%
standards criteria. It links complete results and clearly separates the
preserved research appendix. The
[narrated screen tour](../output/walkthrough/BioGraph_Steward_Walkthrough.mp4)
shows the actual local app using verified saved real data in 3:58, with
synthetic narration, captions and edited screenshot states; the
[seven-slide overview](../output/presentations/BioGraph_Steward_Overview.pptx)
provides a separate project overview. Hosted deployment and its
acceptance remain separately recorded. Earlier files remain in the
[dated media history](../output/history/20261115_guided_review/README.md).

For code or separate operator execution, use [START_HERE](../START_HERE.md) and
[delivery instructions](DELIVERY.md). The code-only synthetic fixture is labeled
as invented data and is separate from the hosted real examples. MIT software
licensing does not relicense source datasets. The repository is private during
preparation and intended for public release at final submission; actual
publication and submission remain actions to record when performed.
