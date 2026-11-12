# Whole-graph assessment scope and automatic task qualification

The first automatic source/task-qualified graph is materialized and independently
replayed. It closes a decision-application gap. It does **not** establish
whole-graph scientific accuracy or the precision of deleting biologically false
relationships.

## Executed result

The unchanged source graph has 9,865 entities, 16,985 evidence records and
16,980 assertions, including 290 SIGNOR observations. Under the fixed
[direct human phosphoregulation profile](../AUTOMATIC_TASK_QUALIFICATION.md):

| Source-profile outcome | Records |
| --- | ---: |
| Explicitly eligible for the named task | 175 |
| Explicitly incompatible with the named task | 76 |
| Unknown applicability; abstain and retain | 39 |
| Other evidence families; unassessed and retained | 16,695 |

The derived graph retains **16,909 evidence records, 16,904 assertions and all
9,865 entities**. Its exhaustive ledger contains 175 keep, 76 prune and 16,734
abstain decisions. No numeric confidence is invented. The original source
packet, review history and every unchanged assertion remain preserved.

A pre-release review tightened the organism rule: broad or unknown TaxIds
must abstain, rather than being treated as nonhuman merely because they differ
from `9606`. The final materialization uses four recognized nonhuman species
from the captured NCBI metadata. Its record selection is identical to the
initial materialization; that earlier output and implementation remain
preserved. This correction concerns general applicability, not a new biological
comparison or a changed outcome.

The exclusions have 49 non-phosphoregulation mechanism flags, 20 nonhuman
experimental-organism flags and 15 explicit indirectness flags. These reasons
overlap; they are not 84 distinct removals. BRAF Ser614 remains eligible and an
in-vitro observation remains unknown. Neither result proves purified catalysis
or a colorectal-cancer effect. In particular, excluding a binding record from
this task does not refute that binding interaction.

Independent replay verified all 88 baseline files against the earlier complete
CRC delivery, all 16,985 original edge dispositions and all retained graph
arrays. A separate literal-based recount reproduced 175/76/39 without calling
the new classifier. Synthetic tests additionally check stale bindings,
unknown handling, alternative support and preservation of rejected review
states. These checks establish faithful policy application, not independent
biological truth.

The existing one-hop path explorer also reads the derived graph. An illustrative
HRAS → PIK3CA query changes from two binding-context paths to zero under the
phosphoregulation task, while EGFR → CTNNB1 retains its two phosphorylation
paths. This demonstrates the task-view effect; it is not an independent
accuracy comparison, and the excluded binding paths are not thereby false.

The executed local view is
`runs/crc_task_qualification_v2_20261112/retained/retained_graph.json`.
Its full ledger is alongside it as `edge_dispositions.jsonl`; the parent
`task_qualification.json` binds the fixed policy, source and implementation.
Only 175 records are explicitly eligible. The retained graph also contains the
39 unknown SIGNOR observations and 16,695 outside-profile records as background.

## What whole-graph accuracy still needs

The graph mixes nine claim families. Its record counts cannot be treated as
independent experiments or a common set of binary biological truth labels.
Every family remains accounted for:

| Evidence family | Records | Remaining scientific requirement |
| --- | ---: | --- |
| Pathway membership | 9,540 | Match pathway/complex/reaction membership and release; direct binding is a different claim |
| GO annotation | 4,078 | Recover relation, polarity, extensions and references before evaluating functional assertions |
| Interaction annotation | 1,576 | Separate functional association, co-complex proximity and assay-specific direct interaction |
| Expression observation | 1,061 | Match tissue, assay, measurement and detection scope |
| Regulatory observation | 290 | Independently test direction, mechanism, identity and experimental context; current gate checks source metadata |
| Drug listing | 174 | Distinguish a listing from a binding, activity or clinical-efficacy assertion |
| Tissue-proximity observation | 120 | Preserve proximity/assay context; it is not direct-binding truth |
| Disease association | 100 | Match exact disease and association semantics; association is not automatically causation |
| Variant/therapy response | 46 | Match the full molecular profile, disease, treatment set and clinical evidence context |

The 13,618 GO/pathway records form about 80% of this graph. A PPI-only reference
cannot establish their accuracy. Our GO capture explicitly represents annotation
existence: relation, negation and extensions are unknown. The
[GO Consortium](https://geneontology.org/docs/go-annotations/) distinguishes
missing annotations from explicit NOT, permits contextual/conflicting positive
and NOT evidence, and requires provenance. Unknown qualifiers must not be
filled with positive or negative biological claims. Recovering those native
qualifiers is the priority for broader assessment, rather than another global
ranking sweep.

## Independent negative-reference feasibility

Official IntAct metadata/count queries found 836 human–human negative evidence
candidates. Both-endpoint restriction to all 218 exact UniProt proteins in the
current CRC graph returned **zero candidates**. A query against the existing
3,172-protein historical pruning population failed with a generic service error;
its coverage is unknown, not zero. No interaction rows or new quantitative
outcomes were opened.

The [official IntAct curation manual](https://raw.githubusercontent.com/intact-portal/intact-portal-documentation/master/assets/intact-curation-manual.pdf)
links negative observations to supporting positive experiments and preserves experimental
conditions and isoforms. Such observations could support a separately scoped
physical-interaction test after qualification. They cannot label regulation,
GO or functional coassociation as false. Negatome's structural noncontact pairs
likewise do not refute co-complex or functional association; see its
[primary paper](https://doi.org/10.1093/nar/gkt1079).

This closes the immediate CRC negative-reference route as insufficient coverage.
It does not justify randomly generated negatives, deleting reference-absent
edges, reusing consumed panels as unseen, or reporting a whole-graph accuracy
percentage. The next scientific gate is a predicate/context-matched independent
reference with adequate coverage, separate from the data used to make decisions.

The [aggregate summary](automatic_qualification_20261112_summary.json) binds
the implementation and executed artifacts. Detailed native decisions and
source/reference receipts remain local; no upstream source rights are changed.
