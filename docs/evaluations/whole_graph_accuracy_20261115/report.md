# Whole-workspace comparison and scientific-reference assessment

The Pharos-derived predictor baseline performed worse on the predefined function-recovery task. The separate whole-workspace assessment is now executed, but it supplies no independent biological-accuracy estimate: none of the 200 frozen cases acquired a qualifying exact-claim independent correctness label.

## Measured prediction outcome — a separate task

The fixed original contextual comparison uses a historical 20,412-protein Pharos-derived STRING network and dated GO supervision. It forecasts 3,300 proteins; its primary native/fixed-T0 residual-positive populations are 322/319. These Fmax scores measure later curator-annotation recovery, not accuracy of the 99-target app workspace.

| Predictor/source profile | Native Fmax | Fixed-T0 Fmax |
| --- | --- | --- |
| Retained Pharos-derived graph + LocalPlus | 0.054732 | 0.171550 |
| Same graph + complete current-T0 curated annotations | 0.058838 | 0.182771 |
| Original selected contextual predictor | 0.073431 | 0.210093 |
| New cross-fitted development candidate | 0.071129 | 0.213361 |

The original selected predictor and the newer development candidate both have positive paired intervals over retained LocalPlus in both views. The additional primary benefit over fully refreshed LocalPlus remains uncertain across the two required views. The new fit does not establish improvement over the original selected predictor, and its reference had already been consumed.

## Complete stored workspace — same primary cohort

| Graph | Stored assertions | Independent true / false labels | Unknown assertions |
| --- | --- | --- | --- |
| Pharos only | 15671 | 0 / 0 | 15671 |
| Before GO-ID qualification | 16980 | 0 / 0 | 16980 |
| Current retained graph | 16682 | 0 / 0 | 16682 |

The common unit is a stored qualified assertion, not a deduplicated biological fact or independent experiment. The captured primary cohort has 99 targets. The retained graph has 9,865 entities and 16,687 evidence records; assertions and evidence records have different denominators.

| Comparison | Shared | Removed | Added |
| --- | --- | --- | --- |
| pharos_only → retained | 15373 | 298 | 1309 |
| enriched_baseline → retained | 16682 | 298 | 0 |

The 1,309 additions comprise 858 versioned STRING assertions, 120 MAP-IT observations, 290 SIGNOR observations and 41 CIViC response assertions. Added records are not automatically independent or newly discovered biology. The 298 exclusions concern obsolete GO identifiers in the pinned July 26, 2026 ontology, not 298 experimentally refuted relationships.

## Public reference qualification — actual execution

| Examined resource | Observed coverage | Scientific admission |
| --- | --- | --- |
| Main sample plus separate removed-GO sample | 180 + 20 exact frozen cases | 200 unknown; 0 admitted true/false |
| Current native GO curation | 22 sampled cases; 49 rows; 11 cases with experimental curation | Shared/unresolved lineage and missing original qualifiers |
| Reactome expert review | 16 externally reviewed records; 15 current memberships | Same upstream provider; not independent validation |
| Archived WikiPathways | 14 exact revisions; 8 gene-context matches | Gene-level context is not exact protein-form judgment |
| Archived Pathway Commons | 13 same-lineage memberships | Source corroboration, not independent truth |
| Complete IntAct negative download | 985 rows / 910 human-human negatives; 0 sampled-PPI pair matches | No labels inferred from absence |
| Published expert extraction curations | 6,022 curations / 1,800 statements; 6 partial candidates in 4 cases | Exact full claim/context or independent lineage not established |

All 201 distinct referenced local artifact hashes were checked. Curator agreement and public database presence remain separate from independent correctness. Neither missing records, failed assays in another context, missing source-model xrefs nor GO term obsoletion were relabelled as biological negatives. The original evidence-support reviews and earlier comparisons are preserved.

## What the available labels mathematically identify

Each graph has logical accuracy bounds of 0 to 100%, because no scientific true/false labels were admitted. These express missing knowledge, not an estimate that the graph is inaccurate. The shared-assertion calculation limits the possible difference between graph versions without validating their common claims.

| Comparison | Logical difference range, percentage points | Confidence interval |
| --- | --- | --- |
| pharos_only → retained | [-7.8468, +7.8468] | Not computed |
| enriched_baseline → retained | [-1.7550, +1.7550] | Not computed |

These finite-population completion ranges are not confidence intervals, equivalence tests, achieved improvements or claims of high absolute accuracy. They share one unknown truth per identical assertion ID; unreviewed and unsampled assertions stay unknown. The main and removed-domain design-weighted availability summaries remain separate. No missing-at-random assumption or LLM truth vote is used.

## Confirmed graph-quality outcome and remaining requirement

The pinned-GO active-ID proportion improves from 3,780/4,078 (92.69%) to 3,780/3,780 (100%) among retained GO assertions. The previously measured 373 compatible experimental-GO matches and 32 coding-cohort-supported disease assertions are all preserved. This establishes ontology currentness and bounded support preservation, not whole-graph biological precision.

A broader biological-accuracy claim needs independently qualified judgments on the exact stored claims, with original context and study/source lineage. The new evaluator can consume such labels without changing the frozen graph/sample. More model fitting or turning existing source-support judgments into true/false labels would not supply the missing reference.

Reproduction fixed a display-version mismatch without changing a dossier: a compatible historical inspector reproduces all 180 guides exactly. The native Gold retained profile was also handled according to its existing metadata contract. Both rejected integration attempts are retained, before scientific output. No graph, model default or hosted AWS workspace changed.

Methods: [Gao et al.](https://www.vldb.org/pvldb/vol12/p1679-gao.pdf); [Horowitz–Manski](https://doi.org/10.1080/01621459.2000.10473902).
