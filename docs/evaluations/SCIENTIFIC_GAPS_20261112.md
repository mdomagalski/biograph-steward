# Scientific qualification: executed GO recovery and pruning

**Follow-up:** the [native GO quality assessment](SCIENTIFIC_LIMIT_RESOLUTION_20261112.md)
subsequently executes the published relation/reference rules and qualified
taxon reasoning, adds exact current-source inspection, and diagnoses the
unmatched historical records. The results below remain the original assessment;
its statement that full native rules were not executed describes that run.

Two reusable commands now address missing native annotation context and
obsolete ontology identifiers. The executed CRC result detects and excludes
**298 obsolete-ID GO records from a separate active-ID view**. This is a
demonstrated semantic-currency improvement. It is not evidence that 298
biological relationships were false, nor a whole-graph accuracy score.

The original 9,865-node, 16,985-evidence-record source graph is unchanged.
The earlier direct-human-phosphoregulation view and all biological comparison
results remain separate and preserved. The two pruning views are not silently
combined or substituted into the default application workspace.

## Native context recovered without guessed joins

The available Pharos GO schema and inspected TCRD loader omit relation,
polarity, references, extensions and product forms. This is an upstream
projection limit. The new adapter reuses Biopython 1.88 to parse native GAF 2.2,
preserves the exact source rows and enumerates all compatible candidates:

| Native GOA/context inventory | Result |
| --- | ---: |
| Original GO evidence edges inventoried | 4,078 |
| Exact original GO subjects with native records | 99/99 |
| Native records preserved | 15,888 |
| Explicit NOT records | 23 |
| Records with annotation extensions | 1,236 |
| Original edges with one compatible native record | 1,021 |
| Original edges with multiple compatible native records | 127 |
| Original edges without a compatible native record | 2,930 |

Compatibility requires exact accession, GO ID, evidence, assigning database
and aspect. A unique candidate still does not establish historical identity.
References, relation, NOT, AND/OR groups, product forms and native taxon fields
remain attached to their own native records. Every original qualifier stays
unchanged; a missing match stays unknown. Product-form fields are present on
all selected native rows; that does not mean all are distinct isoforms.

The 23 native NOT rows are not deletion labels for historical
`has_go_annotation` existence records. Native GOA can reuse the same upstream
curation as Pharos and is not counted as independent corroboration. The current
result therefore recovers usable context for inspection without pretending to
restore all 2,930 unmatched historical records.

## Ontology-qualified graph materialized

The official current GO endpoint was checked on November 12 and still advertised
build **2026-08-05**. Ontology and annotation header sizes/ETags match the existing
pinned artifacts. Their internal versions remain explicit: ontology July 26,
annotations generated July 28. No newer build is inferred from today's date.

The ontology check applies the primary-ID lifecycle part of
[GORULE:0000020](https://github.com/geneontology/go-site/blob/master/metadata/rules/gorule-0000020.md).
Its decisions agree with the captured upstream method under
`repair_obsoletes=False`. This is a bounded method replay, not execution of the
entire ontobio package or GO validation pipeline.

| GO primary-term decision | Evidence records |
| --- | ---: |
| Active ID; retain for this view | 3,780 |
| Explicit obsolete ID; exclude from this view | 298 |
| Missing/unrecognized ontology ID; abstain | 0 |
| Other graph families; abstain and retain | 12,907 |

Of the 298 obsolete-ID records, **167** have a single explicit, active
`replaced_by` target; **131** do not have a safe explicit replacement. Replacement
proposals are separate and unapplied. `consider` suggestions are never promoted
to replacements. The original source assertion and its review cannot simply
be reassigned to a different identifier.

The retained graph has **16,687 evidence records, 16,682 assertions and all
9,865 original nodes**. No retained GO annotation edge points to a term marked
obsolete in the pinned ontology. Original obsolete nodes remain preserved,
including isolated nodes; this is not a node-deletion or connectivity claim.
All 16,985 original evidence records have keep/prune/abstain dispositions.
Other sources, evidence families and original source bytes remain unchanged.

A separate software-agent review independently scanned all 910,476 native GAF
rows and reproduced every selected row and compatibility join without calling
the new classifier. Its raw-ontology recount and full Gold replay reproduced
the pruning result. All retained edge payloads and all 16,682 surviving
assertions match the baseline exactly. This is independent software verification,
not expert human adjudication or experimental replication.

## Independent scientific validation remains a distinct requirement

The reference investigation checked existing published methods and their actual
artifacts before selecting another benchmark:

- Native IntAct negative count queries supply no both-endpoint candidate for
  the current 218-protein graph universe. Physical-interaction negatives also
  do not refute functional association or pathway participation.
- The [HCT116 comparison](HCT116_EXTERNAL_COMPARISON_20261112.md) already completed
  and is consumed. It found no prediction difference from the tested source
  exclusions; it cannot be presented as a new unseen comparison.
- [SNOOPPI](https://doi.org/10.1093/bioinformatics/btag736) provides useful
  exact-sequence curation, but is IntAct-derived and includes altered-construct
  and designed negatives. Its labels cannot automatically refute generic
  canonical-protein associations. Study separation and current CRC coverage
  have not been established.
- [LAFA](https://doi.org/10.1093/bioadv/vbag221) provides a prospective temporal
  GO evaluation design. It does not make older GO labels independent of a
  contemporary GO-derived input.
- [GAEF](https://doi.org/10.1093/bib/bbag336) supplies relevant ontology consistency
  methods, but whole-genome completeness assumptions do not fit CRC99. Actual
  taxon satisfiability needs the matched ontology/reasoner inputs; raw numeric
  taxon inequality is insufficient.

No qualified independent reference presently supports a whole-graph accuracy
percentage or validated automatic scientific-error pruning here. The new GO
view can be audited as ontology-currentness; the native context can be audited
as source preservation. Neither substitutes for experimental truth.

Taxon rules, retracted-reference rules and relation validation remain scoped:
GORULE13 handles NOT and experimental evidence differently; GORULE22 requires
exact references; GORULE61 needs the native relation. They must not be applied
to missing Pharos fields by guessing their values. The adapter explicitly
reports that these full checks were not executed.

## Reproduce and inspect

See [scientific qualification commands](../SCIENTIFIC_QUALIFICATION.md).
The executed local outputs are:

- `runs/crc_go_context_qualification_v2_20261112/`: native rows, all original GO
  compatibility records, original GAF bytes and the sealed context report.
- `runs/crc_go_ontology_qualification_20261112/`: ontology source, complete
  decisions, separate replacement proposals, retained graph and full baseline.
- `runs/scientific_gaps_20261112/release_check/`: official current-release check.
- `runs/scientific_gap_reference_20261112/`: bounded reference-fit review and
  pinned primary paper/code metadata; no new matched CRC negative labels opened.

The first native sidecar is preserved separately. A pre-release correction
retained symlink evidence for the existing Gold input checks; the final sidecar's
native rows, compatibility inventory and source GAF bytes are identical to the
first output. This was an input-contract correction, not a new biological result.

Tests exercise source pins, unknown handling, context preservation, exact
matches, competing candidates, review/source immutability and the real native
parser. No Brev instance, model inference, paid service or default graph change
was needed. Upstream native data and existing redistribution restrictions remain
separate from the MIT software. The [aggregate result](scientific_gaps_20261112_summary.json)
binds the executed reports and independent implementation review.
