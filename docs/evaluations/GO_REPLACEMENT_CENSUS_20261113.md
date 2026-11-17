# Full GO replacement census — November 13

**Later checkpoint, November 13:** the [native GOA recovery publication](NATIVE_GO_RECOVERY_20261113.md)
has now materialized the 24 qualified records in a separate local derived
workspace, preserving old evidence and decisions and recomputing its historical
pathway proof. The audit-only application boundary below records the earlier
checkpoint; it is not the current adapter status. No AWS rollout is implied.

The complete audit identifies **21 distinct protein–GO concepts absent from the
retained graph**, supported by **24 qualifying native experimental annotation
records across 15 proteins**. They are recoverable annotation coverage, not new
biological discoveries or an independently measured accuracy gain.

All 167 explicit replacement proposals were examined. Original source records,
the retained graph, decisions and review states remain unchanged. A standard
GAF2.2 subset preserves the 24 native annotation bodies for a separately sourced
addition; no historical Pharos annotation is silently rewritten.

## Full results

| Audit stage | Proposals | Distinct concepts where applicable |
|---|---:|---:|
| Explicit, unique, active main-term replacements | 167 | 161 |
| Native rows for the exact protein and replacement GO ID | 122 | — |
| Native evidence code, assigning database and aspect also match | 61 | — |
| Qualifying, unopposed experimental-context support | 25 | 23 |
| Qualified concept already represented in retained GO edges | 3 | 2 |
| Qualified concept absent from retained GO edges | **22** | **21** |

The 22 qualifying proposal origins converge on 21 concepts and 24 distinct
native records. Source records and publication identifiers are not independent
experiment counts. Six of the full 167 proposals converge with another
proposal on the same protein/replacement concept; they are not six additional
biological relationships.

Every proposal has one recorded disposition:

| Disposition | Proposals |
|---|---:|
| No native record for the exact protein/replacement term | 45 |
| Protein/term present, but evidence/assigner/aspect differ | 61 |
| Strict native candidates outside the existing experimental/context scope | 36 |
| Qualified experimental support; concept already retained | 3 |
| Qualified experimental support; concept absent from retained graph | 22 |
| **Total** | **167** |

No qualifying strict opposing NOT candidate was found. This is limited to the
declared projection keys and convergent proposals; it is not an exhaustive claim
that no contrary biological evidence exists. Nonexperimental curations are
outside this reference scope, not false or invalid. Missing matches are unknown.

## Existing methods reused

The official [GORULE20](https://github.com/geneontology/go-site/blob/51071321de1ee89b2597e2300a40824a35583016/metadata/rules/gorule-0000020.md)
supports explicit replacements. Its inspected bytes match the project's
previously recorded rule checksum. We reuse the existing ontology classifier;
no alias, ancestor, `consider` suggestion or guessed mapping becomes a repair.
This audit covers the main annotation term, not the full GO repair pipeline's
With/From and extension processing.

The native [GAF2.2 fields](https://geneontology.org/docs/go-annotation-file-gaf-format-2.2/)
are matched using the existing `project_compatibilities()` implementation:
exact UniProt accession, new GO ID, evidence code, assigning database and aspect.
All compatible alternatives remain visible; a unique match does not identify
the historical Pharos record or restore its omitted qualifiers.

The existing experimental-reference gate requires a positive experimental
annotation, one human subject taxon, no distinct product form, no annotation
extension and no With/From context. Eligible opposing NOT rows hold the proposed
concept unresolved, including across convergent proposal origins. These are
conservative compatibility conditions, not a biological-truth classifier.

Deduplication has two separately reported levels. An exact protein/new-term
match in retained GO edges means the **concept is represented**. An exact
five-field match means a projected source key is represented. Neither establishes
identity of complete relations, references, qualifiers or native evidence rows.

## Examples of recoverable coverage

The following examples describe the native curator annotations, not new
experimental conclusions from this project:

| Protein | Native GO concept |
|---|---|
| TP53 | Transcription cis-regulatory region binding; chromatin; regulation of cell cycle |
| ATM | Regulation of cell cycle; mitotic G2 DNA damage checkpoint signaling |
| SMAD4 | DNA-binding transcription activator activity, RNA polymerase II-specific; transcription cis-regulatory region binding |
| AXIN1 | Protein-containing complex assembly; molecular adaptor activity |

All 21 concepts retain their exact GO IDs and native publication identifiers in
the source-bound audit. The qualifying records also include context-specific
terms such as cardiac muscle cell development for TTN. Membership in the CRC
protein cohort does not make every annotation colorectal-cancer-specific.

## Source bindings and verification

The baseline is the existing 99-protein, 16,985-evidence-record source packet.
The audited retained graph has 16,687 evidence records and 16,682 assertions.
All proposals are replayed from the original pinned July26,2026 ontology;
native rows come from the July28,2026 UniProt GAF distributed in the August5
release. These pinned artifacts are not asserted to be today's latest release.

The producer revalidates the complete Gold decision package, original graph,
ontology and native sidecar. The saved GO reader scans all **910,476** source
GAF rows, checking completeness and literal binding of all **15,888** preserved
cohort rows. The candidate export contains only unchanged source annotation
bodies and explicit subset/source-hash comments, under the source CC BY4.0 terms.

An independent agent recounted the results directly from GAF columns, ontology
metadata and retained edges without calling the new classifier. All 167 cases,
161 concept groups, 24 candidate native IDs and every reported count agree.
Twelve synthetic tests cover forged proposals, duplicate/convergent concepts,
strict field mismatches, unknowns, NOT, nonexperimental evidence, product/taxon/
context restrictions, subset fidelity and changed report pins. Existing GO
regression checks pass; the optional Biopython integration check remains
separately labelled when that dependency is absent.

The first census is preserved. A second execution added source-code pins for
the reused eligibility and verification helpers without changing any result.
The delivery execution additionally writes the native GAF subset; its census
and JSONL results are identical. These are deterministic source replays, not
three independent biological evaluations or newly sampled holdouts. No
probability-sample estimate or accuracy confidence interval is derived here.

## Publication and application boundary

The reusable command is
[`audit_replacements.py`](../../tools/go_qualification/audit_replacements.py).
The delivery artifacts are under Git-ignored
`runs/go_replacement_census_20261113_v3/`:

- `proposal_audit.jsonl`: all 167 original proposal origins and their gates.
- `concept_audit.jsonl`: all 161 convergent concept groups.
- `qualified_nonduplicate_native_records.jsonl`: the 24 complete native rows.
- `qualified_recoveries.gaf`: standard native annotation subset.
- `report.json`: complete counts, source/code pins, policy and output hashes.

The [public aggregate receipt](go_replacement_census_20261113_summary.json)
contains counts and delivery bindings without copying the full GAF or local
source inventories into Git.

These additions are **not yet applied to the hosted graph**. The existing
qualified-workspace loader verifies a retained subset of its immutable baseline;
manually appending records would invalidate its provenance and decision ledger.
The existing biological-extension lifecycle is reusable, but currently has no
native-GOA adapter and restricts additional nodes to proteins. Six required GO
nodes are absent. Correct materialization therefore needs a separately sourced
native-GOA addition/derived workspace, with new evidence identities, preserved
native relations and default candidate review state. Original source records
and review decisions must remain intact. This audit does not pretend that
interface gap has already been closed.

No new GAF download, model, paid compute or AWS change was needed. Native
curation can reuse the evidence already aggregated by Pharos; the result is
qualified coverage recovery, not independent experimental replication,
whole-graph biological accuracy or transferable prediction benefit.
