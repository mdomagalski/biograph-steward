# Next biological comparison: intervention decision

October 27, 2026. **No-go for another predictive run now.** The reviewed inputs
do not yet supply a verified, scientifically defensible graph or feature change
that isolates Steward's contribution under the existing learner. This is a
specific missing intervention, not a requirement to obtain hidden organizer
labels before any development evaluation can proceed.

This decision closes the requested comparison-design review. No new biomedical
outcomes or reserved IntAct study bodies were accessed; no learner was fitted,
source panel expanded, threshold selected or paid compute used.

## What has actually changed

The implemented [physical priority](../PHYSICAL_ASSOCIATION_PRIORITY.md) changes
the order of the same eligible Pharos question results. It sorts native STRING
12.5 physical scores before unranked matches, retaining functional context,
paths, assertions and review states. It changes neither the saved graph nor the
R-GCN inputs. The [BRAF product check](PHYSICAL_PRIORITY_PRODUCT_CHECK_20261027.md)
accounts for all 21 original matches: 14 numeric scores and seven unranked.

The [12.5 comparison](STRING_COMPONENT_COMPARISON_20261027.md) and
[12.0 temporal control](STRING_TEMPORAL_CONTROL_20261027.md) support this bounded
source-selection choice. On the same 2,676 eligible measured pairs, physical
versus functional AP was 0.190056 versus 0.172827 for 12.5, and 0.161223 versus
0.149732 for 12.0; numeric coverage was lower in both physical views. These are
completed retrospective component comparisons. They do not isolate a novel
Steward graph representation, establish direct binding, or prove independent
scientific or researcher-task improvement.

## Exact intervention readiness

| Proposed change | Actual learner-visible change | Decision |
| --- | --- | --- |
| Physical priority or source-reuse annotations | None in the frozen R-GCN projection. `prepare_inmc_graphs.py` excludes all direct Pharos PPI; question ordering and provenance labels are not model inputs. | Keep the completed product feature. Do not rerun this learner expecting an effect. |
| Exact duplicate/source-view collapse | The app already groups reciprocal/source views. The native PyKEEN triples factory also removes identical triples, so changing their multiplicity does not change the current adjacency. | No-go as a new predictive intervention; preservation and source accounting remain useful. |
| Add GO hierarchy or Reactome membership | Genuine adjacency additions were already tested. GO was mixed/negligible; Reactome added exactly 11,138 memberships and gave mixed seed differences, mean AP 0.717794 to 0.719605. | Preserve and close these candidates. No new term, source, seed or threshold sweep is selected. |
| Recompute MIscore or independence-adjusted evidence strength from Pharos PPI rows | The existing scope audit found no explicit publication/method/curated-record/MIscore fields across 4,650 matching reciprocal source views. Provider labels cannot supply these missing inputs. | No-go for a new score formula or an assumed independent-study count. |
| Add the consumed IntAct records, then qualify them | Qualified observations are available, but no matched ordinary/qualified projection into permitted learner inputs has been demonstrated. The six literal single-UniProt pairs have zero exact overlap with Lambourne nominations. That does not rule out indirect context value. | No-go for fitting now; neither sufficient cohort coverage nor an actual useful input contrast is established. |
| Sequence/proteoform-aware qualification using SNOOPPI | Exact tested sequence/features and an adopted, verified projection are absent from the current gene/locus-oriented model. The existing artifact/license review remains conditional. | No adoption or new run under this decision. |

The duplicate finding is dependency behavior, not a new scientific experiment.
The pinned [PyKEEN 1.11.1 triples factory](https://raw.githubusercontent.com/pykeen/pykeen/v1.11.1/src/pykeen/triples/triples_factory.py)
applies `np.unique` to mapped triples. A local synthetic probe confirmed that
two identical input rows and one input row both become `[[0, 0, 1]]`, with the
same entity/relation maps. The receipt is
`runs/next_biological_decision_20261027/pykeen_duplicate_probe.json`.
The [pinned R-GCN implementation](https://raw.githubusercontent.com/pykeen/pykeen/v1.11.1/src/pykeen/models/unimodal/rgcn.py)
takes its message-passing graph from the triples factory; source metadata does
not automatically become a relation, numeric feature or evidence weight.
This is a limitation of our present projection, not proof that PyKEEN cannot
support other representations.

## Comparator and reference decision

There is **no newly selected three-arm predictive comparison**. A valid later
comparison must name a particular source-supported representation change before
scoring. Its baseline must already interpret the source correctly; an arm that
turns every assay row into a positive interaction, discards known negative or
expanded-complex semantics, or intentionally ignores a required native score
would be a contrived comparator.

For an added record set, the intended decomposition remains:

1. A precisely named, frozen Pharos-derived projection and common permitted
   training scaffold.
2. The same projection plus the identical additional source records through a
   documented ordinary adapter, respecting their actual assay semantics.
3. The same information, identities and exclusions with one specified Steward
   representation or qualification. The concrete changed adjacency, relation
   types or numeric features must be supplied and consumed by the learner.

The ordinary adapter may already perform the proposed qualification. If its
permitted inputs equal Steward's inputs, record a no-op and stop; do not weaken
the adapter to manufacture a difference. For a change to existing source
representation with no added information, a matched two-arm comparison can be
sufficient. Three arms are not a universal literature requirement.

The existing INMC reference has 1,751 eligible complete-scored off-diagonal
pairs; Lambourne has 2,676 eligible Y2H-v1 pairs. They measure different
assay contracts and must not be merged into a convenient new reference.
Both are consumed development data. A later justified internal comparison may
reuse one, retaining its exact candidates, constructs/mappings, measured
nondetections, failure exclusions and exposure flags. Unknown import lineage
limits its interpretation; it does not categorically prohibit that internal
paired comparison. Any independent-generalization claim needs a separately
justified reference and source separation. The unopened IntAct selection is
for source fidelity and supplies neither of these predictive references.

## Literature supporting this decision

- [Wright et al., State of the interactomes](https://link.springer.com/content/pdf/10.1038/s44320-024-00077-y.pdf)
  evaluates networks for distinct biological tasks and shows that network
  choice and coverage matter. Its [author implementation](https://github.com/sarah-n-wright/Network_Evaluation_Tools)
  provides evaluation tools; it does not make our assay panel independent or
  establish a Steward-specific intervention.
- [Wang et al., INMC assessment](https://www.nature.com/articles/s41467-023-37079-7)
  motivates measured PPI ranking and strong topology comparators. A systematic
  screen's binary-interaction endpoint is not interchangeable with every
  literature-curated functional or co-complex association.
- [MImerge/MIscore](https://academic.oup.com/database/article/doi/10.1093/database/bau131/2433131)
  provides established merging and heuristic evidence scoring based on
  supporting annotation, including publication, detection method and
  interaction type. Missing annotations cannot be replaced by source-bundle
  counts or an invented confidence formula.
- [IMEx](https://www.nature.com/articles/s41467-020-19942-z)
  supports preserving experimental method, molecular form and context because
  different methods detect different relationships. It does not justify
  reclassifying every unqualified association as biologically false.
- [Official STRING score semantics](https://string-db.org/help/scores/)
  distinguish physical/co-complex proximity from functional association and
  direct binding. They support optional task-specific priority, while opposing
  physical-only filtering as a universal correctness rule.

Primary methods and official artifacts above were rechecked October 27.
These sources support the stated boundaries, not a promised positive effect.
No new dependency was installed or implementation copied in this review.

## Finite next actions and stopping point

1. **Deliver the stronger midpoint report and the completed product example.**
   Include the native-score result, its lower coverage and the BRAF source
   trace. Keep source fidelity, predictive ranking and user usefulness as
   separate claims. The original GO/Reactome results remain closed.
2. **Close the already prepared fresh IntAct fidelity execution as a separate
   deliverable**, only after its full code/runtime/source bounds, expanded
   consumed inventory, complete qualified-alias overlap check and denominators
   are frozen. The consumed full-flow correction has passed, but that does not
   itself constitute a freeze for the new four-study selection. Preserve stops,
   zero-eligible studies and failures without replacement. A successful result
   measures curation preservation through graph, answer and export.
3. **Reopen a predictive comparison only on concrete new readiness evidence:**
   one documented source field/qualification, a standards-respecting ordinary
   comparator, and a saved nonempty difference in the actual permitted graph
   or features under fixed identities/masks. Confirm that the existing learner
   consumes that difference before fitting. If no such difference is available,
   retain this no-go and report the scientific gap explicitly. Do not substitute
   another source/model search for it.

No Brev model, GPU or AWS deployment is needed for this decision or fidelity
preparation. Paid compute would be requested only after a specific executable
comparison passes these input requirements.
