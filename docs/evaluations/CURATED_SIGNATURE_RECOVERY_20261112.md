# Biological target recovery with published curated signatures

The published curated-library comparator improves coverage and all four
preselected study-weighted recovery metrics in this bounded retrospective
comparison. This is a useful positive result for **source choice in kinase
signature inference**. It does not establish general scientific accuracy,
direct catalytic truth, a graph-pruning benefit or clinical utility.

## Why this intervention

The earlier drug comparison found that every model abstention had zero
measured prior signature sites. The [2025 primary benchmark](https://doi.org/10.1038/s41467-025-59779-y)
identifies source-library choice as important and reports benefits from
combining curated libraries. We therefore tested its released curated CSV,
rather than tuning another pruning threshold or inventing a new inference
method. The comparator adapts the authors' existing resource; it is not a new
independently curated library.

The unchanged original SIGNOR prior has 6,114 binary memberships across 373
source-reported regulators. The author CSV has 15,814 rows; existing strict
gene/product, coordinate and present-flank checks retain 11,741 compatible rows,
11,727 unique memberships and 381 genes. A source-declared unavailable flank
remains unreported; it is not interpreted as experimental confirmation.
Duplicate rows add no weight. Both arms use the same source-only union of
**420 candidate genes**, the same measurement background and the same raw
RoKAI z-score, requiring five finite distinct measured target sites.

## Reference and preserved execution boundary

The [Hernandez-Armenta benchmark](https://doi.org/10.1093/bioinformatics/btx082)
is reused from the [authors' frozen release](https://zenodo.org/records/14824013).
Seven whole parent studies with known local exposure were excluded before
measurements were decoded. A source-only citation audit then found one
additional study, PMID 20068231, explicitly supporting SIGNOR records. It was
excluded from both reference arms before outcome access; both priors remained
unchanged. This left **16 selected study groups and 65 conditions**.

The first attempt used the registry loader incorrectly and applied the older
study's three-field identifier reader. It qualified no measurements and failed
before reference scoring. Its plan, code and outputs remain preserved. The
corrected reader follows the authors' four-field
`gene | site | ENSG | ENSP` encoding and checks ENSG against captured HGNC
context. ENSP remains unverified protein-isoform context. Zero qualified sites
now stops execution before inference or reference access.

The completed run is explicitly a **technical replay after exposure**, not a
fresh unseen confirmation. Sources, thresholds, candidate genes, study
selection, readout and metrics were not tuned. Predictions were sealed before
the corrected run decoded expected targets and signs. A separate software-agent
numerical reconstruction agrees within 1.78e−15; this is not expert human curation.

Of 61,180 measurement rows, 52,311 qualify as gene/canonical-coordinate
proxies; this is not experimental proteoform verification. The selected
reference has 118 supplied records. Frozen atomic-gene rules leave **105
target cases, 20 genes, 61 conditions and 14 evaluable study groups**. Thirteen
records remain reference-unresolved, leaving two selected studies and four
conditions without a qualified reference. They are not model errors or
biological negatives. The affected tokens, ATR, PRKACA and RAF1, are approved
primary names blocked by the frozen resolver's secondary-alias conflicts;
they are not unknown gene families. No post hoc label rescue was applied.

## Results

Metrics average targets within a condition, conditions within a study group,
then give each evaluable study group equal weight. Missing target scores
receive worst rank 420. Top-five rank hits and absolute direction agreement
remain separate; no unlabelled kinase is called a true negative.

| Study-weighted metric | Original SIGNOR | Published curated comparator |
| --- | ---: | ---: |
| Mean normalized expected-sign rank, lower is better | 0.680898 | **0.576408** |
| Target-score coverage | 32.14% | **42.77%** |
| Expected-direction agreement, including abstentions | 29.85% | **41.75%** |
| Top-five rank hits, regardless of absolute sign | 27.04% | **32.45%** |

The unweighted case count increases from **31 to 39 scored cases out of 105**.
Twelve cases gain scores, all matching the declared intervention direction;
four previously scored cases lose scores, 27 remain scored and 62 abstain in
both arms. These case counts differ from the study-weighted percentages above.
Mean rank improves in four study groups, worsens in two and ties in eight.

### Coverage helps; superiority on shared targets is mixed

A prespecified sensitivity restricts both arms to their common finite
candidates and common scored target cases. It contains only **27 cases,
15 conditions and six study groups**, with 6–28 common candidates in the
scored conditions. It is a different assessment population, not a replacement
for the all-case primary.

| Common-finite sensitivity | Original SIGNOR | Published curated comparator |
| --- | ---: | ---: |
| Mean normalized rank | 0.235774 | 0.230846 |
| Expected-direction agreement | 88.89% | 94.44% |
| Top-five rank hits | **76.39%** | 70.83% |

Thus, the result supports addressing missing signature coverage. It does not
show that the published library always prioritizes already-scorable targets
better. Under the original 420-candidate population and weights, the net rank
gain comes from newly scorable targets; changes on shared scorable targets
slightly offset that gain. The lost scores also expose complementary source coverage: some
SIGNOR-supported sites are absent from the native author CSV, including a
2024 report published after its older source snapshots. They were not simply
lost by the new adapter. No post hoc union, source replacement or threshold
change was promoted using these outcomes.

## What we retain and what remains unresolved

The reusable source adapter, configured comparison runner and synthetic
integration checks are retained under [optional tools](../../tools/kinase_utility/README.md).
They preserve source rows, reject present identifier/flank conflicts, retain
missingness and abstentions, check the actual registry API, and prevent empty
input from producing a seemingly valid comparison. No study names, target
genes or expected answers are hardcoded in the reusable functions.

The biological interpretation remains bounded:

- Intervention targets and signs are surrogate reference labels. Compound
  selectivity, feedback and experimental context can affect them; this is not
  a direct activity assay for every kinase. Study groups and target cases are
  not counts of independent experimental replicates; no statistical superiority
  or whole-graph error rate is established.
- The compilation and libraries were used in published method development.
  The curated CSV omits per-edge citations and original support provenance,
  so complete source-study disjointness cannot be certified. A zero exact
  SIGNOR citation intersection does not resolve that limitation.
- Author preprocessing projects some historical names, fusions and isoforms
  onto gene labels. Compatible current coordinates do not independently
  validate those origins or every catalytic claim.
- The frozen resolver's alias policy has a verified coverage cost. Resolving
  it requires source-namespace or stable-ID qualification; a blanket override
  after seeing these results would weaken this comparison.
- The **whole Hernandez compilation is now consumed**. Further changes on it
  are development/sensitivity work. The software has not changed the app graph
  or automatically accepted any source assertion.

The practical conclusion is to retain curated signatures as a useful
comparator and candidate enrichment route, while preserving current SIGNOR
evidence and source distinctions. Automatic merging/export is not justified:
record-level origins and upstream redistribution terms remain unresolved.
Native source memberships, measurements and row ledgers stay private and
Git-ignored; the software's MIT license does not relicense those inputs.

See the [aggregate result](curated_signature_recovery_20261112_summary.json).
Complete plans, preserved failure, source reviews and independent recount are
saved under `runs/curated_signature_accuracy_20261112/`. No Brev, GPU or model
inference was needed.
