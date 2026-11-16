# BioGraph Steward | Submission overview

BioGraph Steward uses a bounded NVIDIA Nemotron agent to guide a research
question through supported source tools. It returns a focused Pharos evidence
graph, a cited answer, inspected source records and grounded review proposals.
A researcher can trace a connection, inspect qualifications and reuse the
graph with its source context.

The new agent's actual development comparison is complete. Hosted replay,
updated media and refreshed software packaging await their own acceptance.
The protected site and current video still show the preceding guided reader
until the [delivery status](DELIVERY_STATUS_20261115.json) records the update.

**[Open the protected reviewer site](https://bi-3a117d5e2b3942678dc518fce65ab5d2.ecs.us-east-2.on.aws/)**
and follow the **[five-minute judge walkthrough](JUDGE_WALKTHROUGH.md)**.
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
  candidate protein connections and inspect its native STRING source. The full
  addition includes 330 physical associations and 3,309 native GO records across
  94 targets. Source support is distinguished from independent experiments,
  direct binding and local acceptance.
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
Same-learner held-out graph comparisons were executed without establishing
consistent enriched-graph superiority over Pharos and the strongest controls.

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
shows actual hosted-app captures in 3:42, with captions; the
[seven-slide overview](../output/presentations/BioGraph_Steward_Overview.pptx)
provides the preceding guided presentation. Their replacement will show the
actual accepted agent workflow. Earlier files remain in the
[dated media history](../output/history/20261115_guided_review/README.md).

For code or separate operator execution, use [START_HERE](../START_HERE.md) and
[delivery instructions](DELIVERY.md). The code-only synthetic fixture is labeled
as invented data and is separate from the hosted real examples. MIT software
licensing does not relicense source datasets. The repository is private during
preparation and intended for public release at final submission; actual
publication and submission remain actions to record when performed.
