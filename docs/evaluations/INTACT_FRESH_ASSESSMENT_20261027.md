# Fresh IntAct source-fidelity assessment

The fresh assessment completed, but the full-flow test **did not pass**:
coverage and strict fidelity were **4/8 (50%)**. Two Pharos read timeouts prevented
construction for four observations. All four observations that reached the
answer/export stage preserved their checked fields: **4/4 conditional fidelity**.
This separates an operational coverage failure from a detected semantic
mismatch; it does not make the missing outputs successful.

The [tracked summary](intact_fresh_assessment_20261027_summary.json) binds the
fixed execution and results. The readable local report is
`runs/intact_fresh_assessment_20261027/index.html`.

## Fixed scope and complete accounting

All four preselected studies were retrieved once, without substitution. Their
16 physical rows include 12 evidence rows; eight observations satisfy the
unchanged explicit human-protein eligibility rules. They describe four exact
protein pairs. No study was removed by the bounded provenance audit.

| PMID | Physical rows | Evidence rows | Eligible observations | Strict fidelity |
| --- | ---: | ---: | ---: | ---: |
| 39938803 | 5 | 4 | 2 | 2/2 |
| 40108405 | 4 | 3 | 2 | 0/2 |
| 40752540 | 4 | 3 | 2 | 2/2 |
| 40088780 | 3 | 2 | 2 | 0/2 |
| Total | 16 | 12 | 8 | 4/8 |

The two failed pair batches each retain two observations in the denominator.
All eight IntAct source requests returned HTTP200. The assessment made 18 actual
Pharos attempts: 16 returned HTTP200 and two ended with a read timeout. It used
no retries, cache fallback, replacement studies, model inference or GPU.

## What the result establishes

The corrected MITAB/XML comparison completed for all four studies, including
the complete qualified interaction-alias check. The ordinary publication,
attachment, readable answer and exported packet passed for two pair batches.
No field disagreement was detected on the four completed observations. All
140 copied-source-file checks and 32 output-inventory checks performed on those
completed batches passed. Missing outputs remain failures in all-eligible
coverage and strict fidelity. The many failed per-field checks on absent outputs
are not separate measured biological errors.

Every eligible row has the source negative-interaction flag set to false and no
complex-expansion annotation. Explicit negatives, default-negative literals and
supplied-expansion strata therefore remain **unevaluated**. Absence of an expansion annotation does
not establish true binary origin or direct binding. The summary retains all
method, interaction-type and missing-context strata, including empty ones.

The bounded audit found no consumed-qualified-alias matches, shared pair or
participant flags, or ambiguous dataset statements. This literal check does
not establish study independence or prove novelty beyond Pharos/STRING. Article
status checks cover preserved IntAct annotations only; missing correction or
retraction annotations are unknown. No selected-publication article body or
abstract was needed for this source-fidelity execution.

## Reliability finding and preserved boundary

The recorded failures are Pharos read timeouts. Their cause remains unresolved:
the exception alone does not distinguish service latency from network, VPN or
proxy conditions. The existing Pharos client already supports bounded retries
and caching; this assessment deliberately fixed retries to zero, cache off and
a 30-second Pharos timeout. No evidence here establishes that retries would
solve the underlying cause. Subsequent engineering can reuse those existing
capabilities or saved responses on these now-consumed inputs.

The original stopped assessment and successful consumed rehearsal remain
separate, unchanged results. This fresh result is not pooled with the earlier
2/2 rehearsal. All four newly assessed studies are now consumed; a repair or
repeat becomes development work and cannot be relabeled unseen confirmation.

This finite assessment measures preservation of supplied curation through the
workbench. It does **not** establish scientific accuracy, biological prediction
gain, clinical relevance or Steward-specific improvement of Pharos. The report
records source fidelity and operational coverage; biological improvement remains
a separate comparison.

## Execution evidence

The complete freeze file SHA-256 is
`ccb4f8d937c27df1ef56397625b0aba9dea983d74dffd1558974d2c58b368e96`.
The captured report SHA-256 is
`12b98cb5c3bcfd3b7b9e062c3470ebddb9ce3ffbbb80db306bfc3f3257d9a5ca`.
The fixed implementation, official reader runtimes, original source eligibility,
semantic amendment, work budgets and all-denominator rules were sealed before
access. Invented controls, consumed rehearsal and a separate automated
pre-access review passed. The [independent automated post-execution audit](../../runs/intact_fresh_assessment_20261027/independent_result_audit.json)
confirmed the source accounting, all eight eligible row locators, four missing
outputs and reported partial failure. Its file SHA-256 is
`18e6e57eea2118eb5c24eea0449d60b9c5607015b9c6086de9267249129a6599`.
This read-only artifact audit did not rerun the assessment or establish
independent biological validation.
