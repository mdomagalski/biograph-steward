# Review the new evidence example | 10 minutes

Please send feedback by **Monday, November 16**. We need to know whether the
question, answer, sources and limitations are understandable. You do not need
biological expertise or to decide whether a protein relationship is correct.

This supplements the [team review guide](TEAM_REVIEW_GUIDE_20261113.md). Use the
same protected AWS reviewer site and privately supplied workspace token. A
browser is sufficient; you need no AWS account, local installation, Brev instance
or model. Keep the token out of feedback and screenshots.

**Deployment status at drafting: pending.** Marcin will supply the confirmed new
links after the hosted update passes its checks. The deployment receipt will
record those URLs at the existing reviewer-site address. The paths below
identify the intended examples; they are not confirmation that rollout is live.

| Example | Saved path at the existing reviewer-site address |
|---|---|
| New KRAS candidate answer | `/?run=native_evidence_workspace_20261115&question=native_physical_KRAS_question_v3_20261115&view=ask` |
| Same question, accepted evidence only | `/?run=native_evidence_workspace_20261115&question=native_physical_KRAS_accepted_v3_20261115&view=ask` |
| New comparison page | `/?run=native_evidence_workspace_20261115&view=compare` — select `scientific_assessment_public_reference_20261115_v3` |

The older saved real example remains a separate workspace. Open the supplied new
link for these tasks. Allow loading time separately from the ten-minute review;
if a task stays blocked for about two minutes, record the message and move on.

## What is included

The new example preserves the original **99-protein Pharos cohort** and adds two
separately recorded source views:

- **STRING physical associations:** 330 candidate protein-pair annotations from
  the separate STRING 12.5 physical network. Of these, 243 connect pairs already
  represented in the original workspace and 87 connect pairs absent there.
  These are additional versioned source records and new workspace pairs,
  respectively—not independent experiment counts or new biological discoveries.
  Exact alias and sequence checks admit 77 of the 99 proteins; unresolved
  identities and unlisted pairs stay unknown. The original functional
  associations remain available.
- **Native GO locations:** 3,309 source records describe 429 protein–location
  concepts across 94 of the 99 targets. A concept can have several supporting
  rows. Rows can reuse databases, papers or studies; counts are not independent
  evidence votes. These annotations remain candidates.

**Compare & assess** separately reports reference comparisons. It shows measured
recovery, coverage, source reuse and adverse results. The comparison data are
not used as new evidence records in the example graph.

## Five short tasks

1. **Find the KRAS answer — 2 minutes.** Open the new candidate-answer link.
   In **Ask & explore**, confirm **Connections to inspect** is
   **Native STRING physical associations**. Follow the graph to **3. Answer**
   and expand one result. The saved answer contains **14 result proteins**.
   Find the candidate/review wording and the warning about direct binding.
   Report whether it is clear what this answer does and does not claim.

2. **Follow one reference — 2 minutes.** In that expanded result, select a
   citation such as `[E001]` using the reference shown in your answer. Inspect its
   source information/passport. Find **STRING**, version **12.5**, and a note
   about identifier or sequence matching. You may open recorded source details;
   no external source website needs to be visited. Report where you found the
   information and which field or term remained unclear. The 243/87 figures
   above describe the whole source addition, not the 14 KRAS results.

3. **Understand candidate versus accepted — 2 minutes.** Open the supplied
   accepted-only answer link. It should show **no accepted result proteins**,
   while the same source has **14 inspectable proteins**. Then return to the
   candidate example, open **Evidence & sources > Native GO locations**, keep
   **Inspect candidates**, and click **Show native GO annotations**. Open a
   source row and find its evidence code and reference identifiers. Try
   **Accepted only** and show the annotations again: this view should be empty.
   Explain what the empty accepted views mean; you are not being asked to accept
   a record.

4. **Interpret one measured result — 2 minutes.** Open **Compare & assess** and
   choose `scientific_assessment_public_reference_20261115_v3` under
   **Saved scientific assessment**. Find either **41/51 → 44/51** location
   labels among **31 matching proteins**, or **30/40 → 31/40** OpenCell labels
   among **23 matching proteins**. Read the nearby source-overlap/context note.
   Explain the counted unit and one limitation. Neither result is a percentage
   of the whole graph that is biologically correct.

5. **Distinguish answer and workspace exports — 2 minutes.** Return to the KRAS
   candidate answer and locate **Download summary, paths and evidence ZIP**.
   Then open **Export > Saved workspace files** and locate **Download run ZIP**.
   Explain which is the focused answer and which preserves the complete saved
   workspace and its source material. Locating and explaining the two controls
   is enough; downloading the larger workspace is optional. Repository access
   alone does not include these complete source packets.

Use the supplied saved answers throughout. If a protected reviewer control is
unavailable, note that rather than changing accounts or setting up compute.

## Terms you may need

| Term | Meaning here |
|---|---|
| Functional association | Proteins are linked through a biological function or process; this can include indirect relationships. |
| Physical association | Source evidence predicts physical proximity or shared-complex membership. It does not necessarily establish direct binding. |
| Native source record | Fields preserved from the original data provider. “Native” here does not mean an experimentally unmodified protein. |
| GO; `located_in` | Gene Ontology supplies standardized biological terms. `located_in` records a protein-location relationship in the supplied annotation. |
| Candidate; accepted | Candidate records await local review. Accepted records have a local review decision; that decision is not a universal scientific truth guarantee. |
| Evidence code; provenance | An evidence code describes the kind of support assigned by a source. Provenance records the provider, version, identifiers and history. Neither alone proves correctness. |
| Reference recovery; unknown | Recovery counts supplied positive reference labels found by a view. Missing reference labels or unmatched proteins remain unknown, rather than automatically wrong. |

## Send back five answers

For each task, mark **clear without help / clear with help / unclear or blocked**.
One or two sentences per answer are enough:

1. What did the KRAS answer claim, and was the physical-association warning clear?
2. Where did you find the source/version, and which source field needs a better explanation?
3. What did the empty accepted views mean to you?
4. What did your chosen comparison count, and what qualification mattered?
5. How do the two exports differ, and what was the most confusing step overall?

Include the saved example name, device/browser, any exact error message, and
whether a glossary or colleague helped. A screenshot of the confusing area is
useful if it excludes the access token. Report loading delays separately from
unclear wording. An honest “I could not find it” is useful feedback.
