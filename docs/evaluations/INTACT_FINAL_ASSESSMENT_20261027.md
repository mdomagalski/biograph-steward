# Reserved IntAct assessment: preserved stop, no final score

The one fixed reserved execution stopped at its cross-format reference gate.
All four selected studies are now consumed. No study was replaced, no result was
repaired or rescored, and no final source-fidelity or scientific-accuracy result
was produced. The [machine-readable outcome](intact_final_assessment_20261027_summary.json)
binds the execution, unchanged inputs/runtime, source receipts and diagnostics.

This is an integration issue that the guard contained, not evidence of incorrect
biology. The frozen comparator compared every supplied MITAB interaction identifier
with a helper that projects only IntAct/IMEx identities. Three source rows also
supply EMDB and wwPDB identifiers. Their primary IntAct/IMEx identities match.
Independent inspection of the already-captured XML reader stream confirms that
the structural identifiers are retained there; the restricted helper omitted them
from this comparison. The original source/parser records were preserved.

The [official MITAB2.7 column14 definition](https://psicquic.github.io/MITAB27Format.html)
permits database-qualified interaction identifiers; its IntAct/IMEx example does
not limit the allowed databases. The
[official distribution guidance](https://psicquic.github.io/DataDistributionBestPractices.html)
also distinguishes identifiers from other cross-references. Any correction must
respect the source qualifiers and identity semantics, rather than treating every
cross-reference as an equivalent record identifier. The independent diagnosis receipt, bound in the tracked outcome, records the
[pinned IntAct interaction manual](https://github.com/intact-portal/intact-portal-documentation/blob/b5d5bb35365739d4942e9ca250a2cf4fbaa14c62/docs/curation-manual/interaction.md)
and official JAMI interpretation. Its local artifact is
`runs/intact_final_diagnosis_20261027/report.json`.

## Frozen execution and verified preparation

The execution freeze was written before access and remains unchanged:
`7c1f59b4696bd5b6f4b7760d22405f04f358fc46dfd7ea5f0464a98de3492788`.
The exact selected release, four original source hashes, original eligibility,
semantic amendment, reader runtimes, controls, question/batching and failure
policies were bound. The old development loaders and historical results remain
unchanged. A fixed exclusive access marker prevents another reserved execution
under a renamed output directory.

The separate final path passed invented controls and a complete replay on the
already-consumed development material. That replay retained all eighteen physical
rows and fourteen evidence rows, with four eligible records preserved through the
ordinary Pharos attachment, qualified answer and complete source export. Its
coverage and strict fidelity were 4/4. This verifies the engineering rehearsal;
it is neither a reserved result nor independent biological validation.

The reserved run retained each MITAB source, fetched each exact XML URL once with
bounded transport and HTTP receipts, and used the same controlled official
readers. The original MITAB files and execution copies still match their frozen
hashes. XML reader input hashes and byte counts match the saved HTTP bodies.
The failure receipt and all parser streams/alignment diagnostics remain intact.

## Descriptive accounting after the stop

The following counts were recovered from the captured official MITAB streams
using the unchanged original eligibility function. They are explicitly
post-stop source accounting, not a repaired run or a final scoring denominator.

| PMID | Physical rows | Evidence rows | Explicit human-protein source-eligible rows | XML evidence objects |
|---|---:|---:|---:|---:|
| 39833857 | 4 | 3 | 0 | 2 |
| 40211762 | 3 | 2 | 0 | 2 |
| 39972491 | 4 | 3 | 0 | 2 |
| 40555359 | 7 | 6 | 2 | 4 |
| Total | 18 | 14 | 2 | 10 |

Zero eligible records in a study means that its supplied participant identities,
explicit type or taxonomy fall outside the predeclared human-protein task; it
does not mean its biology is false. Source exclusions can overlap. N-ary XML
objects and their expanded MITAB views remain distinct accounting units.

The comparator recorded 235 equal and three different selected-field comparisons.
Those are diagnostics, not an accuracy estimate. The three differences concern
`evidence_identity_aliases` at PMID 40555359 source lines 2, 3 and 4. Line 2 is eligible
under the original source policy; the other eligible record is line 5. None was
passed into a completed final integration assessment.

## What remains unresolved

The stop occurred inside source inspection, before the reserved provenance and
connected-study-component audit. It did not reach Pharos cohort retrieval,
source publication/import, qualified answers, full export or source-fidelity
scoring. These stages are unexecuted, not zero accuracy. The bounded consumed
inventory and its incomplete broader Pharos/STRING, CIViC, dataset and model
pretraining exposure remain disclosed. Exact experiment overlap was not assessed;
the inventory does not enumerate consumed experiment accessions. Previously
retrieved PubMed ESummary metadata is not article-level correction or retraction
clearance. No study-independence claim follows.

The next repair may use the documented identifier semantics, invented cases and
these now-consumed records. It must preserve this failure. Repeating the repaired
flow on this same panel is development work; a new final assessment requires a
separately predeclared reference. Source-fidelity testing remains separate from
scientific accuracy, biological prediction gain, and decisions to accept or prune
graph assertions. This run made no model or GPU calls.
