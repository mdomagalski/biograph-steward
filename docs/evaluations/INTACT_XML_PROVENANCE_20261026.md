# IntAct development XML provenance check

The official PSI-JAMI XML reader is now verified on the four already-consumed
development studies. All 14 MITAB evidence rows align to XML evidence identities,
and all 238 bounded field comparisons agree. This is **not full cross-format
fidelity**: the rows represent 13 XML evidence objects, including one explicitly
spoke-expanded, three-participant interaction. The four originally eligible human
protein records remain unchanged. No reserved interaction body was opened.

The [machine-readable summary](intact_xml_development_20261026_summary.json)
binds the contract, controls, pre-access receipt and actual result. This note is
a follow-through to the [earlier readiness audit](INTACT_PROVENANCE_READINESS_20261026.md),
not a rewrite of its historical findings. The inspection ran October 26 local
time (October 27 UTC).

## Existing capability and verified integration gap

The earlier MITAB projection did not expose the complete qualified experiment
and publication model. The documented graph service routes returned an empty
body for the one consumed interaction checked; that did not establish that the
capability was absent everywhere. The official release offers per-publication
PSI-MI XML, and JAMI 3.9.4 already supports its declared 2.5.4 version. We reused
that reader instead of implementing a biological XML parser.

The [isolated helper](../../tools/intact_xml_reader/README.md) documents the
exact author-source commit, release artifacts and full-list APIs. Source review
identified two integration traps before selected-data access: singular getters
can discard multiple contexts, and JAMI's identifier collection does not retain
physical primaryRef/secondaryRef element origin. The implementation preserves
all model values and joins only exact, unambiguous identity-qualified identifiers;
it does not infer markup origin or study independence. Synthetic controls cover
unresolved references, scoped roles/hosts, malformed input, external-entity
rejection and the actual XML version. The final nine controls passed 283 checks;
20 Python transport/comparator guard tests passed.

## Frozen scope and observed result

The [final contract](intact_xml_20261026_contract.json) was frozen before four
exact official release requests. Runtime, code, source reference and controls
were checked before access. Opaque XML/HTTP receipts precede official decoding;
source hashes are checked before and after it. Previous control and pre-access
attempts remain preserved. The original MITAB protocol, semantic amendment,
panel, rows and eligibility mask were not changed.

| Consumed development PMID | Original MITAB evidence rows | XML evidence objects | Original eligible rows |
|---|---:|---:|---:|
| 40075158 | 2 | 2 | 0 |
| 40404733 | 5 | 4 | 2 |
| 40071126 | 4 | 4 | 2 |
| 40739265 | 3 | 3 | 0 |
| Total | 14 | 13 | 4 |

All four files completed with no parser diagnostics or quarantine. Each MITAB
row has a unique matching XML record. The field comparisons cover evidence
aliases, PMID, exact participant identity/taxonomy/type/roles, detection/type,
reader-valued negative state and host values. No different or unresolved field
comparison was observed. These are 238 field checks over 14 rows, not 238
independent evidence records or scientific confirmations.

The full evidence-object bijection is **false**, explicitly retained in the
result. In PMID 40404733, physical lines 3 and 4 share interaction EBI-70852445 /
IM-30672-3, have different RNA partners and explicitly carry MI:1060 spoke
expansion. Both map to XML object 4 with a protein, a microRNA and an mRNA.
This is a qualified n-ary representation, not duplicate source rows or two
independent experiments. Neither row is eligible for the bounded human
protein-pair flow. They remain in the denominator and audit; no record was
removed, repaired, merged or replaced. An absent expansion annotation on other
rows remains absent; it does not prove binary experimental origin.

The interpretation follows the already-pinned
[official MITAB 2.7 expansion specification](https://github.com/HUPO-PSI/miTab/blob/301904541d716b767d02a67f3413907952844ea1/PSI-MITAB27Format.md)
and the [mandatory semantic amendment](intact_fidelity_20261026_semantic_amendment.json).
A binary row, co-IP observation or bait/prey role does not establish direct
binding. No new conversion or expansion algorithm was introduced.

## What this closes and what remains

Qualified experiment identifiers, publication references, figure annotations and
source cautions are now available in a retained provenance projection, with raw
XML and complete official-reader streams. One explicit caution states that a
relation to LINC01355 was not annotated because the curator could not identify
its correct sequence; it concerns incomplete RNA annotation and does not
automatically disqualify the separate protein records. No cross-study citation
was found in the inspected publication/experiment collections. This does not
establish independence or completeness. This closes the development route and
bounded cross-format check. The original graph/answer/export comparison remains
4/4 eligible records, two pairs in two publications, all positive co-IP evidence.
It is not rerun or relabeled as an independent biological assessment.

The metadata does not certify absence of shared studies or complete annotation.
Reader defaults do not prove explicit source markup. Shared-study lineage,
reserved pair overlap, final-study suitability and the final execution path
remain unresolved. All four reserved interaction artifacts remain unopened and
unhashed. There is no final reserved score, scientific-accuracy estimate,
predictive-improvement claim, ranking change or new pruning decision.

The next bounded step is to complete the development provenance audit and fix
final execution/exclusion rules that preserve n-ary groupings and uncertainty
before any reserved access. Do not turn a missing annotation into independence,
treat expanded rows as replications, or tune on consumed outcomes. This work
used no model, GPU or paid compute.
