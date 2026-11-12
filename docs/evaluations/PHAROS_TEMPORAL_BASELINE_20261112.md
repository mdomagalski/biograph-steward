# Current Pharos PPI input and temporal validation — November 12, 2026

**No historical graph was substituted.** The complete computational PPI input of
our existing 99-target colorectal-cancer workspace matches the official archive
completed on April 17, 2024. That archive supplies a verifiable time anchor for a
separate assessment against later MAP-IT tissue proximity measurements.

This is a retrospective fixed-cohort test. The disease cohort was selected in
2026, before inspecting MAP-IT, and was not a prospective forecast made in 2024.
The completed MAP-IT comparison is **unscorable for the pruning endpoint**:
none of the evaluable eligible pairs meets the fixed enrichment rule. It cannot
establish whole-graph biological accuracy or identify every false edge.

## Source finding

The official `pharos319.sql.gz` download is 2,257,847,063 bytes. Its full gzip
integrity and SHA256 were verified; the internal SQL completion is
`2024-04-17 17:46:32`. We extracted the actual PPI tables with the established
MIT-licensed sql-splitter v1.21.0, inspected the version-specific Pharos resolver
and reproduced its provider and score semantics. All 11,753,235 selected-table
rows imported without conversion warnings.

The current and archived components agree on all **99 target proteins, 1,436
reciprocal source views and 718 canonical PPI associations**, including provider
bundles, native weights and raw record identifiers. Independent recounting
confirmed the match. This attests the full selection input; it does not attest
all Pharos records or current non-PPI metadata.

The age of this component is a source limitation, not something the comparison
removes. Archive metadata identify its STRING input as v11.0 loaded in 2019.
A separately captured STRING 12.5 network does **not** reproduce these Pharos
weights or edge population. A current-release method comparison could be useful
later, but it would answer a different source/update question. We did not choose
between versions using biological performance.

[Official archive](https://opendata.ncats.nih.gov/public/pharos/archive/),
[Pharos resolver pinned to the inspected revision](https://github.com/ncats/pharos-graphql-server/blob/3feb5ac7e450b3c6b767651f0fe1f39994085380/src/resolvers.js).

## Fixed comparison

| View | Eligible pairs retained | Protected pairs retained | Total PPI retained | EGFR neighbours |
| --- | ---: | ---: | ---: | ---: |
| Unpruned | 624 | 94 | 718 | 46 |
| Native STRING score | 499 | 94 | 593 | 33 |
| Published Network Enhancement | 499 | 94 | 593 | 35 |

Both scored views remove 125 eligible pairs. Mixed-provider and non-STRING
records remain protected. Network Enhancement uses the unchanged author code and
defaults; no biological result has selected a parameter, cutoff or source
version. The native boundary splits a five-way score tie using the already fixed
pair identifier. The full source graph and app deployment remain unchanged.

Equal global budgets do not equalize EGFR degree. Biological accounting must
show this difference, the measured coverage, the number of retained enriched
partners and the corresponding descriptive fractions. More retained positives
alone would not establish better discrimination.

[Published Network Enhancement method](https://www.nature.com/articles/s41467-018-05469-x).

## Reference qualification

MAP-IT provides antibody-directed proximity measurements in primary colorectal
tumour and adjacent tissue. The deposited raw data were publicly announced on
October 5, 2026, after the archive. This assay measures proximity enrichment,
not universal direct binding. The additive EGFR analysis pools the antibody
effect across tissue contexts; it does not estimate tumour-specific rewiring.

Two source issues were detected before interpreting quantitative results:

- The figure workbook contains 79 plot-selected statistics beside 5,378
  annotation rows. Those columns are not aligned as a full reference table.
  We rejected that join and reused the authors' full released analysis instead.
- The released EGFR script reverses patient 7's tissue labels relative to both
  the sample key and raw filenames. A separate primary reanalysis corrects only
  those tissue tokens; the original script is preserved as a fixed sensitivity
  replay. Neither version is selected by its graph result.

The full author model uses seven patients, 14 physical tissue blocks and 168
measurements, with limma's repeated-measurement model. Its filters and full-family
Benjamini–Hochberg correction are retained. The operational enriched reference is
finite **Beta_Ab < 0 and Q_Ab < 0.05**: the antibody coefficient is
Isotype−Primary. Uncalled or missing observations are not validated negative
interactions. Exact protein-group lineage uses the actual DEP dependency, without
choosing a first accession or collapsing isoforms.

This is a documented reanalysis, not an author-supplied binary gold standard.
The authors supply no environment lock, so the compatible runtime is explicitly
pinned: R 4.4.3, limma 3.62.1, DEP 1.28.0, MSnbase 2.32.0 and 294 verified binary
packages. Both variants, inputs, identity rules and comparison choices were
frozen before the full numerical analysis. Previously seen article examples and
qualitative findings remain recorded as exposure.

[MAP-IT primary study](https://doi.org/10.1038/s41467-026-79134-z),
[author analysis](https://zenodo.org/records/23181000),
[deposited dataset](https://proteomecentral.proteomexchange.org/cgi/GetDataset?ID=PXD075907&outputMode=XML).

## Completed biological accounting

Both published-code replays completed, preserving their full model families and
passing the exact source-identity and full-family BH fidelity checks. The primary
metadata-aligned analysis models **5,378 protein groups**, with **122 enriched
observations** under the frozen rule. Of these, 121 have an unambiguous exact
accession and one remains an unresolved group. Forty-six of the 99 CRC targets
survive the author filters with exact identities, including the EGFR bait.
The bait's self-observation is excluded from every partner metric.

| EGFR partner category in CRC99 | Possible pairs | Evaluable after author filters | Enriched under fixed rule |
| --- | ---: | ---: | ---: |
| Eligible source pairs | 38 | 18 | **0** |
| Protected source pairs | 8 | 4 | **1** |
| Absent from this source component | 52 | 23 | **0** |

The one qualified partner is **ERBB2 / P04626**, on a protected Reactome+STRING
association with EGFR. Its corrected-analysis antibody coefficient is −0.472149
and full-family Q is 4.81225×10⁻¹¹. All three views retain that pair. This is
consistent with preserving this protected example; it is not evidence of an NE
advantage or direct binding established by this assay.

Native and NE each retain 14 of the 18 evaluable eligible neighbours, removing
four conditional noncalls. The removed sets differ. Those noncalls are not
validated false edges. Because the eligible-positive denominator is zero, the
primary NE−native retention difference is **undefined**, not zero and not a
failed or successful superiority test.

The untouched released-metadata replay has 118 full-family enriched groups,
four fewer than the corrected variant, but **the same CRC99 coverage and zero
eligible positives**. The biological conclusion therefore does not depend on
which metadata variant is used. No thresholds, identifiers, cohort or source
version were changed in response.

## Conclusion and next decision

The outdated-baseline concern was resolved through complete input attestation,
without a baseline downgrade. The reference coverage is now the limiting factor.
This completed assessment does **not** demonstrate biological improvement and
must not be presented as evidence that either pruned graph is more accurate.

Keep pruning optional and preserve the source graph. Do not tune it on this
now-consumed reference or enlarge the cohort and call the result independent.
Any later expansion is development work and needs a separately declared
reference and adequate coverage for a confirmatory comparison. The earlier
[Lambourne comparison](PPI_PRUNING_COMPARISON_20261111.md) remains a failed
predeclared superiority gate and is not replaced by this endpoint.

The completed deliverable is a reproducible source-lineage check, fixed graph
choices and a qualified biological-accounting report. No scientific performance
benefit is claimed where the reference cannot measure it.

Independent verification reproduced full-family BH values (maximum numerical
difference below 4×10⁻¹⁵), exact identities, file hashes and all denominator
counts. The 98 partner possibilities reconcile as one enriched observation,
44 conditional noncalls, five rows excluded by author filters and 48 without an
exact raw identity. This does not imply an absence of evidence outside the
selected cohort or assay.

Local evidence, supplied separately from a fresh clone:

- [Archive receipt](../../runs/historical_pharos_mapit_20261112/source/archive_receipt.json).
- [Complete input match](../../runs/historical_pharos_mapit_20261112/source_research/derived/current_cohort_attestation.json).
- [Independent source and selection review](../../runs/historical_pharos_mapit_20261112/reviews/temporal_source_review.json).
- [Fixed choices](../../runs/historical_pharos_mapit_20261112/fixed_choices/source_selection.json).
- [Reference metadata audit](../../runs/historical_pharos_mapit_20261112/reference_rules/author_runtime/sample_metadata_audit.json).
- [Runtime acceptance](../../runs/historical_pharos_mapit_20261112/reference_runtime/runtime_acceptance.json).
- [Final pre-outcome freeze](../../runs/historical_pharos_mapit_20261112/final_analysis_protocol.json).
- [Author execution receipt](../../runs/historical_pharos_mapit_20261112/author_verified/study_results/execution_receipt.json).
- [Readable assessment report](../../runs/historical_pharos_mapit_20261112/report.html).
- [Independent arithmetic review](../../runs/historical_pharos_mapit_20261112/reviews/independent_mapit_arithmetic_review.json).
- [Complete assessment](../../runs/historical_pharos_mapit_20261112/assessment_results/report.json).
- [Partner-level biological ledger](../../runs/historical_pharos_mapit_20261112/assessment_results/primary_CRC99_partner_ledger.tsv).

No Brev/GPU, language-model call, new instance or production graph modification
is needed. Author computations run in an offline container on the existing AWS
CPU host; runtime and inputs are read-only and results are saved separately.
