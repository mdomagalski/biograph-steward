# Whole-workspace scientific assessment: executed result

The source-bound comparison now runs for the complete captured 99-target
workspace, with the original Pharos-only graph identified separately from its
enriched and retained versions. Public curator/reference qualification covered
all **180 frozen main cases and 20 separate removed-GO cases**. It found no
independent correctness labels that match the complete stored claims. The
assessment therefore returns **no biological-accuracy point estimate or
confidence interval**, and establishes no whole-graph biological superiority.

This does not reverse the measured prediction outcome: **the retained
Pharos-derived LocalPlus baseline performed worse on the predefined function
task**. The original selected predictor improves Fmax from 0.05473 to 0.07343
in the native view and from 0.17155 to 0.21009 with the starting ontology held
fixed, with positive paired intervals in both. The newer development candidate
scores 0.07113/0.21336 and also beats that retained baseline in both views.
Its further advantage over fully refreshed LocalPlus is uncertain across the
two required views; it does not establish improvement over the original
selected predictor. See the [prediction results](CROSSFIT_DEVELOPMENT_RESULTS_20261115.md).
That is a separate 20,412-protein historical-network task, not an accuracy
percentage for this application workspace.

## Exact graph comparison

The unit is a stored qualified assertion, not a deduplicated biological fact.
The source snapshot, source payloads, primary cohort and shared
subject/predicate/object/qualifier identities were checked.

| Graph | Assertions | Evidence records |
|---|---:|---:|
| Captured Pharos only | 15,671 | 15,671 |
| Enriched source baseline | 16,980 | 16,985 |
| Current retained workspace | 16,682 | 16,687 |

Compared with Pharos only, the retained graph has **15,373 shared assertions,
298 exclusions and 1,309 additions**. The additions are 858 versioned STRING,
120 MAP-IT, 290 SIGNOR and 41 CIViC assertions. Source records can reuse
earlier pairs and studies; they are not 1,309 independent discoveries.
Compared with the enriched baseline, the sole assertion-set change is the
298 obsolete-GO-ID exclusions.

## Credible public-label qualification

The AI-assisted work checked whether existing public expert curation or
experimental records can supply independent judgments. It did not manufacture
expert truth labels from source agreement.

| Examined reference | Concrete outcome | Admission boundary |
|---|---|---|
| Native GO curation | 22 sampled cases / 49 matching current rows; 11 cases with experimental curation | Historical annotation identity, polarity/context and source independence remain unresolved |
| Reactome | 16 externally reviewed records; 15 current memberships | Same upstream provider lineage |
| Exact WikiPathways history | 14 exact revisions; 8 gene-context matches | Gene context does not identify an exact protein-form judgment |
| Archived Pathway Commons | 13 same-lineage memberships | Source corroboration, not independent correctness |
| Complete published IntAct negatives | 985 rows, including 910 human-human explicit negatives; no sampled PPI pair match | No negatives inferred from absence or a different assay context |
| Expert extraction curations | 6,022 curations / 1,800 statements; six partial candidates across four cases | Exact complete claim or qualified independent lineage not established |

All **201 distinct referenced local artifact hashes** and all 200 frozen
case/dossier/assertion bindings were verified. The main sample and removed
supplement retain their original domains and weights. All 200 scientific
outcomes remain **UNKNOWN**; existing source-support judgments are preserved
as a separate axis. A source annotation, an accepted editorial record,
phosphorylation, functional association and direct binding are not
interchangeable claims.

## What is identified

No admitted scientific labels means each graph's absolute logical accuracy
range remains **0–100%**. This expresses missing knowledge, not measured
inaccuracy. Shared assertions permit narrower ranges for the possible change:

| Difference | Logical range, percentage points |
|---|---:|
| Retained minus captured Pharos only | −7.8468 to +7.8468 |
| Retained minus enriched baseline | −1.7550 to +1.7550 |

These are finite-population missing-outcome completion ranges, **not confidence
intervals, equivalence tests or achieved gains**. They use the same unknown
truth for a shared assertion ID, including when graph denominators differ.
Unsampled assertions stay unknown. Cross-ID biological equivalence is not
assumed. Sampling uncertainty and annotation error are not quantified by
these logical bounds.

The underlying method follows established
[missing-outcome identification](https://doi.org/10.1080/01621459.2000.10473902).
The existing probability samples follow
[published KG evaluation methods](https://www.vldb.org/pvldb/vol12/p1679-gao.pdf).
The inspected reusable SIGMOD implementation requires complete binary labels
and replacement sampling; it cannot supply the missing judgments or directly
replace this fixed without-replacement design. The adapter is documented in
the [tool guide](../../tools/sampled_audit/README.md#separate-scientific-label-comparison).

## Confirmed graph-quality outcome

Among GO assertions, active-ID eligibility in the pinned July 26 ontology
increases from **3,780/4,078 (92.69%) to 3,780/3,780 (100%)**. All previously
identified **373 compatible experimental-GO matches and 32 coding-cohort-supported
disease assertions remain present**. This is verified vocabulary maintenance
and bounded support preservation. It does not establish that excluded
historical annotations were biologically false.

The missing requirement for a broader biological claim is independent
judgment of exact stored claims, with adequate original context and qualified
study/source lineage. The new evaluator can admit and compare such judgments
without changing the original sample or treating unmatched records as false.
It cannot replace those judgments with another model fit or an AI source audit.

## Delivery and reproduction

The [standalone aggregate report](whole_graph_accuracy_20261115/report.html),
[saved numerical result](whole_graph_accuracy_20261115/summary.json),
[reference qualification](whole_graph_accuracy_20261115/reference_qualification.json)
and [replay receipt](whole_graph_accuracy_20261115/execution_receipt.json)
contain no raw cases, sequences, reference rows or credentials.
The [separate numerical audit](whole_graph_accuracy_20261115/numeric_audit.json)
independently reproduces graph membership and exact paired bounds, checks all
100 retained-package file pins and 201 reference pins, and verifies the 200
frozen dossier bindings. This is software/source verification within the
development session, not independent biological expert adjudication.

A version mismatch initially rejected replay: the current source inspector
adds lookup links to 62 old displays. A checksum-pinned historical inspector
reproduces all 180 original guides exactly, while full source/dossier equality
checks remain active. It is verified compatible code, not an original
inspector pin absent from the old manifest. The native Gold retained schema
was also handled according to its existing contract. Both rejected attempts
are retained before scientific output; no frozen files were changed.

Detailed inputs, source/reference qualification, judgments, reader compatibility
proof and numerical replay stay in
`runs/whole_graph_accuracy_completion_20261115/` under their source terms.
The graph, app defaults and AWS runtime were not changed. Brev/model compute
was not required.
