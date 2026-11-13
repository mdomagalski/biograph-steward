# Frozen experimental functional-concordance comparison

Neither Wiki source-qualification contrast shows a consistent advantage over
the fixed count and degree controls. This supplies an experimental functional
readout that is closer to shared-pathway context than physical-binding labels,
but it does **not** establish biological improvement or whole-graph accuracy.
The production graph and prior learner results were not changed.

## What was compared

The author-released Wainberg coessentiality arrays contain pan-cancer fitness
associations from DepMap18Q3. The published pipeline handles covariance between
cell lines using GLS; the paper also documents residual synteny/copy-number
effects and meaningful negative correlations. We reused the native arrays and
their two-sided P ranks instead of implementing another correlation pipeline or
reconstructing a significance/FDR threshold. P values are association-test
outputs, not calibrated edge-truth probabilities or credible negative labels.

Sources: [Wainberg et al.](https://doi.org/10.1038/s41588-021-00840-z),
[author code](https://github.com/kundajelab/coessentiality/tree/e094aed398760ec3bbca5c462a0748998ad7b997),
[native DepMap release](https://doi.org/10.6084/m9.figshare.6931364.v1),
[documented FDR reconstruction issue](https://github.com/kundajelab/coessentiality/issues/5).

Explicit reviewed gene-product relationships map the original 99 proteins to
98 genes; the complete native gene order and DepMap Entrez header cover 92.
Six absent genes remain outside experimental coverage, not biological negatives.
All 92 query genes remain in the evaluation, including zero-context queries.
The primary domain contains 3,968 different-chromosome pairs. The 218
same-chromosome pairs and sign-restricted curves are separately reported
sensitivities.

After deduplicating gene/context links and restricting to the measured frame:

| Source arm | Exact gene/version memberships | Genes with memberships | Different-chromosome pairs sharing context |
| --- | ---: | ---: | ---: |
| Normalized source | 1,922 | 70 | 1,333 |
| Current-release eligibility contrast | 1,275 | 70 | 983 |
| Historical native-xref contrast | 1,020 | 69 | 892 |

The historical arm includes explicit protein xrefs and compatible gene-level
source encodings; these do not equate a gene with a protein form. The current
arm is a development contrast, not an accepted rule that historical absence
proves false biology.

Each treatment has twenty fixed count-matched subsets and twenty native
degree-preserving XSwap draws generated **after** measurement restriction.
Both endpoint degree vectors, all seeds and swap diagnostics were verified.
Four older global controls remain visible as diagnostics because their original
matching did not survive this projection. This gives 87 complete source arms.
The [author XSwap implementation](https://github.com/hetio/xswap/tree/ffbb933d1731c2ce4e4e24f00a9a909b53ddf75c)
was reused; twenty algorithm draws do not prove uniformity or adequate mixing
and are not a statistical null probability.

## Primary results

For every query and N=1…10, the readout selects the lowest native two-sided
P values. Boundary ties receive fractional inclusion summing to exactly N.
Expected hits use each query's own eligible-partner background. A primary
point requires all 92 queries; none is dropped for lack of source context.

Observed/expected shared-context enrichment:

| N | Normalized | Current-release contrast | Historical-xref contrast |
| ---: | ---: | ---: | ---: |
| 1 | 0.939946 | 1.187124 | 1.308711 |
| 2 | 0.939946 | 1.033237 | 1.114828 |
| 3 | 0.896730 | 0.952630 | 1.017886 |
| 4 | 0.939946 | 0.978278 | 1.030004 |
| 5 | 0.939946 | 0.967286 | 1.017886 |
| 6 | 0.945348 | 0.981942 | 1.017886 |
| 7 | 0.963097 | 0.986129 | 1.031735 |
| 8 | 0.972358 | 0.961790 | 1.005768 |
| 9 | 1.001169 | 1.001483 | 1.044814 |
| 10 | 0.988564 | 0.980476 | 1.022733 |

Historical enrichment exceeds normalized enrichment at every N, but both
treatment curves are covered by the combined count/degree-control ranges.
Neither treatment exceeds normalized plus all forty own-treatment null draws
at any N, so neither meets our predeclared descriptive full-curve claim rule.
That rule is a project reporting constraint, not a published significance test.
There are no P values computed from the ten correlated N points.

Absolute context-hit coverage also falls after qualification. At N=10, the
fractions are 0.331522 normalized, 0.242391 current and 0.229348 historical.
The complete fractions, query records, control envelopes and all declared
sensitivities are retained; this example is not a newly selected endpoint.
Higher enrichment with a smaller background must not be described as improved
recall or calibrated precision.

## Integrity and limitations

- Initial scientific freeze: `6195ca09e0a0a6f71268d845cbaaf5631390ee0954d60b0d272f9da37a5a7dfe`.
  The independent source/control replay passed before numerical decoding.
- All 184 requested native columns have exact HTTP206 range, length, ETag and
  per-range SHA256 receipts. The capture is 25,957,248 bytes, not complete
  matrix files. No full-file cryptographic checksum is inferred from ETags or
  partial ranges.
- A Path-only receipt-writer integration repair preserved the original packet,
  contract and controls byte for byte. Eight raw range bodies from the failed
  attempt were preserved without decoding or outcome inspection. The technical
  continuation admits that byte exposure and links the original freeze.
- All 4,186 captured pairs have usable native P and sign values. Directional
  P differences occur on 4,033 pairs, with maximum absolute difference
  2.01×10⁻¹⁴ and maximum relative difference 8.62×10⁻¹⁴. The author independently
  computes regressions in both directions. All 4,600 declared scope/N/query
  fractional top-N selections are identical under reversal. The originally
  locked native-symbol lexical orientation was not changed.
- This is an exploratory endpoint frozen after earlier INMC outcomes and
  published paper examples were seen. It is not untouched confirmation.
- The reference is historical and pan-cancer, not specific to colorectal
  cancer, clinical usefulness, physical binding or causal biological truth.
  GO-assisted original preprocessing and possible indirect source reuse remain
  disclosed. No missing annotation is labelled biologically false.
- The original release is CC BY4.0 and the author code MIT. The separately
  hosted derived matrices do not state a distinct redistribution license;
  captures remain outside the repository.

## Artifacts and reproducibility

All paths below are under `runs/coessentiality_comparison_20261113/`:

- `frozen_v2/`: original pre-value scientific contract, source arms and controls.
- `independent_frozen_v2_review.json`: independent measured-frame replay.
- `frozen_transport_repair_v1/`: unchanged scientific packet plus transparent
  receipt-writer continuation and original-code preservation.
- `captured_v2/`: native column payloads and receipts; seal `5873e38f…`.
- `scored_v1/`: all 87×5×10 curve points, native pair values, shared rank
  selections and compressed per-query scores; seal `a0b55ae3…`.
- `diagnostics_v1/asymmetry_replay.json`: native-direction and rank diagnostic;
  seal `53e65fbc…`.
- `readable_v3/report.html`: complete tables and control envelopes; seal
  `3c460b1a…` in its rendering receipt.

Code: `tools/coessentiality_feasibility/`. Eighteen focused controls pass in
the existing native NumPy runtime, including nonsymmetric rectangular Fortran
decoding, fractional ties, source-drift/resealed-arm rejection and raw/receipt
persistence. The combined reference/coessentiality suite passes 55 controls
in total; two native NumPy reader controls skip on a runtime without NumPy.
No model, learner fit, GPU or Brev instance was required.
