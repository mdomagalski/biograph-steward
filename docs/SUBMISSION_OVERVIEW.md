# BioGraph Steward | Submission overview

BioGraph Steward turns a supported research question into a focused Pharos
evidence graph, a cited answer and a source-preserving export. A researcher can
follow a connection to its original record, see what was added or excluded,
and carry the graph and its decisions into further work.

**[Open the protected reviewer site](https://bi-3a117d5e2b3942678dc518fce65ab5d2.ecs.us-east-2.on.aws/)**
and follow the **[five-minute judge walkthrough](JUDGE_WALKTHROUGH.md)**.
Use the token supplied privately. Saved review needs only a browser; no AWS
account, local setup, Brev instance or model server is required. Exact accepted
deployment and release identities are recorded in the
[delivery status](DELIVERY_STATUS_20261115.json).

## What to try

The two real examples share a **99-target colorectal-cancer cohort** and show
different operations, rather than interchangeable graph versions:

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

## What is delivered

The working tools cover bounded construction, explicit identifier checks,
versioned assertions, source passports, guided multihop inspection, guarded
snapshot comparison and reproducible graph/decision exports. Stable identifiers,
Biolink references and bounded KGX/SSSOM profiles have recorded limits. AWS hosts
the protected workbench; Neptune supplies a private mirror/inspection route.
The optional Nemotron planner and source-audit agent were evaluated but are
not trusted to make automatic biological acceptance or pruning decisions.
The shared reviewer route replays saved work; live construction, retrieval,
model calls and review edits are disabled there.

The **[final submission summary](FINAL_SUBMISSION.md)** maps these outcomes to
the organizer's 40% usability, 30% accuracy/pruning, 20% explainability and 10%
standards criteria. It links complete results and clearly separates the
preserved research appendix. The
[narrated screen tour](../output/walkthrough/BioGraph_Steward_Walkthrough.mp4)
shows actual hosted-app captures in 3:42, with captions; the
[seven-slide overview](../output/presentations/BioGraph_Steward_Overview.pptx)
provides a concise presentation.

For code or separate operator execution, use [START_HERE](../START_HERE.md) and
[delivery instructions](DELIVERY.md). The code-only synthetic fixture is labeled
as invented data and is separate from the hosted real examples. MIT software
licensing does not relicense source datasets. The repository is private during
preparation and intended for public release at final submission; actual
publication and submission remain actions to record when performed.
