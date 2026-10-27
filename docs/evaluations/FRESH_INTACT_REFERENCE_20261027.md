# Fresh IntAct reference: metadata selection, not an assessment result

Prepared October 27, 2026. Use **all four remaining metadata-eligible studies
from the original saved IntAct directory** for a separately frozen source-fidelity
assessment. Their source bodies remain unopened. The corrected comparator must
first pass its complete development flow. No Brev model or GPU is needed.

The [selection receipt](intact_fresh_reference_20261027_selection.json) records
the exact metadata, selection rule, historical exposure and outstanding gates.
It is a prospective selection record, **not an executable assessment freeze**.
No newly selected interaction body, selected-study article abstract/full text,
protein identity or outcome was retrieved, inspected, listed, hashed or queried
for this preparation. Official method/resource papers and format documentation
were reviewed.

## Why reuse this reference

IntAct already supplies experimentally curated evidence with the context this
tool must preserve. Its resource paper describes the importance of experimental
conditions and detailed records, and the richer PSI-MI XML representation.
That fits an integration-fidelity assessment without introducing another
annotation framework. [IntAct resource paper](https://academic.oup.com/nar/article/50/D1/D648/6425548).

The IMEx model supplies distinct experimental evidence records and sequence-level
identities. It also documents reuse by STRING and other aggregators. Therefore
different database names do not establish scientific independence from Pharos.
The data are available under CC BY 4.0 with attribution. [IMEx paper](https://www.nature.com/articles/s41467-020-19942-z).

The present verified gap is in our comparison of identity projections, not a
need for a new scientific resource. The official format permits database-qualified
interaction identifiers, while distribution guidance separates identities from
other cross-references. The new comparator must preserve that distinction.
[MITAB 2.7 specification](https://psicquic.github.io/MITAB27Format.html),
[distribution guidance](https://psicquic.github.io/DataDistributionBestPractices.html).

## Finite selection before source access

The original October 26 metadata capture contains 56 numeric publication files;
12 pass its displayed-size band of 4–64 KiB. The original salted filename hash
ordering selected ranks 1–8. All eight studies are now consumed. Ranks 9–12 are
the entire remaining eligible set:

| Original metadata rank | Publication PMID | Directory size display |
|---|---|---|
| 9 | 39938803 | 63K |
| 10 | 40108405 | 12K |
| 11 | 40752540 | 13K |
| 12 | 40088780 | 14K |

The saved directory SHA-256 is
`a58c6311b8904314426333ac4c1f83059b6497128c364f197f323b5e6519ed6b`.
The release URL remains
`https://ftp.ebi.ac.uk/pub/databases/intact/2026-10-17/psimitab/pmid/2025/`.
The original salt remains `biograph-intact-fidelity-v1\n`; ordering is ascending
SHA-256 of the UTF-8 salt plus filename, with filename as tie-breaker.

This is a **new assessment chosen after a documented technical failure**. It
was not predeclared in the original eight-study protocol. It does not replace
any stopped, ineligible or unfavorable study in that assessment. The original
failure and component diagnosis remain unchanged. No selection uses biological
identity, human eligibility, positive/negative outcome, Pharos absence, method
or performance. Taking every remaining entry avoids another favorable subset.
The filename hash rule is our reproducible sampling choice, not a published
scientific benchmark.

The size display is rounded metadata. Later MITAB transport must retain the
original strict maximum of 65,536 actual bytes. A too-large, unavailable,
malformed or zero-eligible file is reported without replacement. If no rows
qualify, the assessment is not evaluable; do not widen the size/year/source pool
after looking at the result. The size band may favor smaller studies, so four
files cannot represent all IntAct or human biology.

The saved directory timestamps are October 23, later than the named release
date. A release pathname alone is not an immutable snapshot. Any later fixed
execution needs exact HTTP/body hashes, bounds and reader input receipts; the
present receipt contains **no hash of an unaccessed source body**.

## Known exposure and unknown overlap

The new PMIDs do not equal any of these recorded publication identifiers:

- Original consumed development: 40075158, 40404733, 40071126, 40739265.
- Original reserved, now consumed: 39833857, 40211762, 39972491, 40555359.
- Historical INMC/Lambourne/PPI anchors already recorded in the bounded
  inventory: 41935050, 36949045, 32296183, 31467278.

This proves only literal PMID disjointness from those anchors. DOI aliases,
primary/subsidiary study reuse, evidence and experiment identities, participant
and pair overlap with the unopened panel are not audited. At selection time,
the old inventory covered only the first four IntAct studies plus four historical
anchors. The subsequent [expanded consumed inventory](intact_consumed_inventory_v2_20261027.json)
now covers all eight opened IntAct studies, with exact participant, pair and
qualified evidence identities. A future execution must pin that inventory.
Broader historical CIViC,
Pharos/STRING lineage and model exposure remain incomplete.

Under the existing rules, explicitly consumed-linked study components are
excluded without replacement; ambiguous potential dataset reuse stops the
claim pending adjudication. Shared proteins/pairs are reported exposure flags,
not automatic study exclusions. Missing lineage is unknown, never proof of
independence. Article correction/retraction checks also need an explicit scope;
the source resource itself describes updates and retractions. [IntAct resource
paper](https://academic.oup.com/nar/article/50/D1/D648/6425548).

## Gate before any new source access

1. Integrate the standards-supported identity projection into the new complete
   development path and pass invented controls plus consumed-source rehearsal.
   Preserve all frozen v1 behavior and the original stopped result.
2. Pin the expanded bounded consumed inventory. Freeze the full actual code,
   runtime/readers, original eligibility and semantic amendment, every field and
   denominator rule, exact source URLs and transport caps, deterministic
   questions/order/batching and Pharos retrieval policy.
3. Only then permit one new fixed execution with exclusive access/exposure
   markers. Preserve all physical/evidence rows and separate source eligibility
   from study-qualified assessment eligibility. Stop unresolved parser/reference
   semantics; subsequent repairs are development and consume exposed sources.
4. Report every selected study, including zero eligible rows, all eligible-row
   coverage and strict fidelity, conditional fidelity, critical/field errors,
   publication counts and unevaluated empty strata. No unseen source may be
   substituted because it gives more favorable coverage or results.

The old preparer deliberately accepts only its original eight-study contract.
Do not weaken its guard or pass these four files to it as though they were its
original reserved split. The new metadata receipt is a small declarative input
for a separately reviewed execution path; it is not permission to bypass the
existing freeze and exposure protections.

Even a successful future score establishes preservation of supplied curation
through import, answer and export. It cannot establish biological truth,
prediction improvement, new knowledge beyond Pharos or an organizer score.
