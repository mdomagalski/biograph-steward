# Source qualification and biological utility — November 12, 2026

The completed comparison **does not demonstrate added utility from the existing
pruning rule**. Published propagation has modest descriptive gains over raw
scoring, while the four Pharos PPI views produce nearly unchanged recovery.
The work retained in `f254e43` and `f1d1c0e`,
the original Pharos records and the earlier mixed, failed or unscorable
assessments remain unchanged. This analysis does not establish whole-graph
scientific accuracy or a colorectal-cancer benefit.

## Qualified source prior

The consumed SIGNOR Oct2026 release supplies literal human-experiment,
direct-phosphorylation records between exact canonical protein accessions.
Explicit state/complex qualifiers and ambiguous site strings are excluded;
every raw row and exclusion reason remains available. The 7,505 candidates
were checked against a complete, captured UniProt reviewed-human reference.
There are 7,449 compatible rows: **52 coordinate incompatibilities and four
rows with a missing exact primary enzyme accession** remain excluded. These
are reference-compatibility findings, not labels of false biology. No accession,
isoform or site-coordinate rescue was applied.

An exact release/record/hash/ordinal check found **none of those 56 flagged
records** in the current CRC workspace's 290 SIGNOR records. This finding does
not require a workspace correction and does not validate its other assertions.

Positive numeric citation and exact source-enzyme gene/product correspondence
are required before binary deduplication. The predeclared exclusion of the
reference parent study, PMID `31959955`, matched **zero qualified source rows**.
This does not rule out untagged reuse of the study or related evidence.

The final alternative prior contains **6,708 source rows, 6,114 binary links,
373 source-reported phosphorylation regulators, 1,649 site hosts and 4,363
sites**. Every retained regulator has at least one site; no five-site cutoff
was applied. Valid host sites are retained without requiring host-gene
mappability. Duplicate annotations add no weight, and SIGNOR `EFFECT` never
flips phosphorylation incidence.

SIGNOR separates phosphate addition from its effect on the target's activity.
Its directness annotation does not independently certify purified catalysis,
experimental proteoforms or a canonical kinase catalog. The roster retains
source-reported roles, not a newly validated catalytic classification.
See the [SIGNOR 4.0 primary description](https://doi.org/10.1093/nar/gkaf1237).

Only the historical Pharos PPI subgraph induced on the fixed source-regulator
roster enters this comparison. The existing global masks and connectivity safeguard are
unchanged. Every retained edge keeps its attested native weight in `[0,1]`,
including edges selected by Network Enhancement.

| Frozen Pharos view | Induced weighted regulator pairs |
| --- | ---: |
| Unpruned | 365 |
| Native confidence | 303 |
| Preselected experimental-support primary | 321 |
| Network Enhancement | 287 |

Primary and native differ at 30 nonzero-weight pairs. Equal global pruning
budgets produce **unequal induced densities** here. Any later utility difference
may reflect density or coverage; it cannot identify better individual edges.

## Frozen method and reference

The unchanged author `rokai_core`, `rokai_circuit` and `rokai_inference`
functions provide propagation and mean/z-score readouts under their MIT license.
The same source prior, measurements, missingness, regulator universe and
parameters are shared across arms; only the frozen regulator–regulator PPI input
changes. Raw mean, raw z-score and KS-only propagation are controls. The common
SIGNOR prior and zero site–site matrix are a supported ablation, **not a
replication of the paper's PhosphoSitePlus/PTMcode network**.
See [RoKAI's primary study](https://doi.org/10.1038/s41467-021-21211-6).

The fixed reference uses the processed
[Hijazi et al. phosphoproteomics study](https://doi.org/10.1038/s41587-019-0391-9)
as distributed by the
[2025 kinase-inference benchmark](https://doi.org/10.1038/s41467-025-59779-y)
in [Zenodo record 14824013](https://zenodo.org/records/14824013).
All **122 source conditions** in HL60 and MCF7 are retained. Before expected
target labels are opened, **12,101 of 13,249 input rows** qualify for the frozen
gene/canonical-coordinate correspondence; **465 prior KS sites are observed**,
and **79 regulators have an unpruned PPI neighbor**. These are input coverage
counts, not target-recovery results or independent sample counts.

Expected-target metadata remained closed until all prediction artifacts were sealed.
The endpoint is recovery of author-assigned intervention targets and agreement
with their expected direction. It is not a direct activity assay for every
kinase; other kinases are not verified biological negatives. Source processing,
drug selectivity, feedback and gene/proteoform correspondence limit interpretation.

The primary is fixed against both native and unpruned propagation. Average-tie
signed rank, top-five recovery, direction agreement and coverage use the same
complete two-cell drug population; missing model targets receive the worst
rank. The frozen benefit gate requires better mean rank against both controls,
no worsening of the secondary or per-cell safeguards, and at least 20 target
cases, five target genes, five complete drugs and two cells. Paired drug
resampling uses 10,000 draws with seed `20261112`; its intervals are conditional
descriptions of this panel. Stronger within-panel support additionally requires
both paired rank-difference upper 95% bounds below zero. A stronger NE result
remains visible and cannot replace the preselected primary. Method/literature exposure is recorded; this
is not completely blinded, literature-independent confirmation.

## Completed comparison

The reference contains 118 metadata rows for the 122 measured conditions.
Four conditions have no reference metadata; another 12 have no qualified
atomic target after the frozen identity rules. The primary population contains
**53 complete two-cell drug groups, 170 condition–target cases and 52 target
genes**. All 38 model abstentions remain in the denominator at worst rank.
The full native-condition ledger and all excluded source tokens are preserved.

These are equally weighted drug macros after averaging targets per condition
and the two cells per drug. Lower normalized rank is better; none of these
percentages is whole-graph scientific accuracy.

| Fixed readout | Mean normalized rank | Top-five recovery | Expected-direction agreement | Target-score coverage |
| --- | ---: | ---: | ---: | ---: |
| Unpruned Pharos PPI | 0.382477 | 9.67% | 59.43% | 70.06% |
| Native-confidence pruning | 0.382528 | 9.67% | 59.43% | 70.06% |
| Preselected experimental-support pruning | 0.382510 | 9.67% | 59.43% | 70.06% |
| Network Enhancement pruning | 0.382409 | 9.67% | 59.43% | 70.06% |
| KS-only propagation | 0.382900 | 9.83% | 59.91% | 70.06% |
| Raw z-score | 0.392250 | 7.39% | 56.18% | 70.06% |
| Raw mean | 0.398397 | 4.87% | 56.18% | 70.06% |

The primary's paired rank difference is −0.0000177 versus native confidence
(descriptive 95% interval −0.0001041 to +0.0000675) and +0.0000333 versus
unpruned (+ means worse; interval −0.0002044 to +0.0003178). Both intervals
include zero. The primary fails the predeclared unpruned-rank and HL60
no-worsening checks, so **both benefit gates fail**. Relative to unpruned,
nine target cases have better ranks, nine worse ranks and 152 unchanged ranks.
NE's slightly lower rank does not replace the preselected method or establish
a confirmed benefit.

The raw-control differences support retaining published propagation as a
useful development baseline. They are secondary descriptive results, not a
replacement confirmatory claim for pruning or an independent activity assay.
KS-only propagation also has slightly higher top-five and direction recovery
than the PPI-augmented variants, so the PPI layer has no consistent advantage
across these endpoints.

The predeclared source-degree diagnostic retains the original candidate
universe and primary population. Among 154 target cases with at least five
prior sites, unweighted score coverage is 83.12%; among 16 cases below five it
is 25.00%. These case means are separate from the drug macros above. No
subgroup or method was promoted using this diagnostic.

All 38 missing target scores have **zero measured prior signature sites**.
RoKAI uses unquantified sites as connectivity bridges, then preserves their
missingness at readout; its `KeepMissingSites` setting does not fill these
measurements. This is a verified reason for the abstentions. The original
paper also attributes most improvement to shared kinase–substrate connectivity,
with smaller PPI gains limited by coverage and redundancy; adding predicted
links did not consistently help. The 2025 benchmark likewise identifies prior
library choice as important. The literature supports addressing this
source-coverage problem first.

Other verified gaps are sparse representation of this regulator roster in the
historical PPI scope and unresolved reference or assay identity. Their causal
contribution to the small pruning differences remains unproven.
The next justified development target is better qualified coverage in a
biologically aligned scope, with a fresh evaluation boundary before claiming
added utility. Another pruning or prompting sweep is not supported by this run.

The original Octave 11.3.0 container completed all seven readouts in 754.58
seconds. Source and input hashes were unchanged. Predictions were sealed at
14:16:43 UTC; expected metadata was first parsed at 14:16:58 UTC. The isolated
local runtime fallback was not used. See the
[machine-readable aggregate](kinase_utility_20261112_summary.json),
[frozen method plan](kinase_utility_plan_20261112.json) and
[pre-access review amendment](kinase_utility_preaccess_amendment_20261112.json).
Independent execution review reproduced all seven scores, both paired intervals,
the source/output hashes and the prediction-before-reference chronology.
The entire Hijazi study is now consumed for this project; further changes
evaluated on it are development or sensitivity analyses, not unseen confirmation.

## Saved evidence and optional tool

Independent source and final-prior recounts passed. Local, Git-ignored receipts
bind the [qualified source](../../runs/scientific_accuracy_round2_20261112/product_scope/source_qualification_v2/qualified/receipt.json),
[final prior](../../runs/scientific_accuracy_round2_20261112/product_scope/final_pilot_prior/receipt.json),
[independent recount](../../runs/scientific_accuracy_round2_20261112/independent_utility_review_v1/final_prior_recount.json)
and [execution freeze](../../runs/scientific_accuracy_round2_20261112/execution_v1/freeze.json).
These links require the separately saved run artifacts.

The byte-identical frozen harness is retained under
[`tools/kinase_utility`](../../tools/kinase_utility/README.md), outside default
application dependencies and core test discovery. No new application component
or source graph is introduced. The existing
[biological assessment](BIOLOGICAL_IMPROVEMENT_20261112.md) and
[current-cohort temporal assessment](PHAROS_TEMPORAL_BASELINE_20261112.md)
retain their original results and boundaries.
