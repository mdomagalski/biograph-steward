# Sanger/FIREWORKS fresh-reference feasibility

This bounded check did not qualify a clean fresh reference for the current
delivery increment. No association values, PCA, covariance estimates,
regressions or new comparisons were computed. The positive RA result remains
a consumed-reference exploratory result.

## What is available

| Route | Verified finding | Decision |
| --- | --- | --- |
| FIREWORKS | Published CRISPR analysis uses Broad DepMap20Q1/CERES, 739 profiles. The current generator names a 20Q4 input. | A different analysis method, not a distinct Sanger experimental reference. |
| Current Sanger downloads | 2025 fitness archive is explicitly combined Sanger v2 + Broad21Q2. | Cannot treat the whole archive as independent of the prior Broad source. |
| Pure Sanger Release1 | Native CRISPRcleanR-corrected profiles: 17,995 genes×325 profiles, described as 324 cell lines plus HT29v1.1. | Plausible distinct experimental source, but no native pairwise association reference was located in the examined official resources. |
| Targeted published GLS | A 93/98-gene block is mathematically feasible after estimating covariance from the full genome. | Faithful preprocessing cannot run on this panel using the existing author code without an unqualified change. |

The [FIREWORKS paper](https://doi.org/10.26508/lsa.202000882) and
[official code](https://github.com/mendillolab/fireworks) were inspected.
The generator constructs a full correlation matrix from Achilles/CERES input;
the repository does not supply a general pure-Sanger pair matrix, and no
repository LICENSE file was found. No software was copied into the app or run.

The [official Sanger documentation](https://depmap.sanger.ac.uk/documentation/datasets/wg-crispr-knockout/)
distinguishes corrected fold changes from BAGEL fitness calls and binary
depletion flags. Those gene-level calls are not gene-pair cofunction labels or
biological negatives. Its [dataset/API catalogue](https://api.cellmodelpassports.sanger.ac.uk/swagger/)
separates Sanger dataset 8 from merged dataset 12.

## Source coverage without reading outcomes

Only native archive-directory metadata, the Release1 README, a corrected-LFC
header and the first identifier column of the small binary-table member were
decoded. Numeric fields were discarded without conversion or inspection.
The provider describes the matrices as sharing the 17,995-gene/325-profile
axes; full corrected-LFC row order and numerical completeness were not replayed.

There are 93 literal current Approved HGNC-symbol matches among the 98 cohort
genes. PAK5, PRKDC, MAP3K15, TNNI3K and GRK2 do not match literally. No aliases,
protein forms or compound labels were collapsed to increase coverage. This is
an identifier coverage gate, not scientific validation.

The 614.8 MB archive was not downloaded. Its corrected-LFC member is 108.6 MB
uncompressed/49.2 MB compressed. The tiny binary-table member was streamed only
for its identifier axis. A pinned MIT
[RemoteZip reader](https://github.com/gtsystem/python-remotezip) and standard
ZIP decoding avoided a custom archive parser. Partial ranges/ETags and native
member CRCs are retained; no complete archive SHA256 is invented.

## Why the existing GLS pipeline is not ready unchanged

The [Wainberg author code](https://github.com/kundajelab/coessentiality/tree/e094aed398760ec3bbca5c462a0748998ad7b997)
contains a reusable mathematical regression function, but importing the script
also loads Broad-specific files and executes all-pair fitting. Its loader
maps Broad IDs, removes four principal components estimated from 419 olfactory
control identifiers, and drops four profile columns before full-genome
covariance whitening.

The native Sanger panel has **zero** literal matches to those 419 controls,
and no `OR`-followed-by-digit gene labels. Both native CSV parsing and panel
inspection confirm this; it is not a quoting error. No claim is made about
why the provider excluded these genes. Skipping PCA or choosing replacement
controls would change the published preprocessing and needs separate
source-specific justification and validation. We did not improvise that change.

The full 17,995×325 float64 profile matrix would occupy 46.8 MB, covariance 0.85 MB,
and each 93×93 coefficient/SE/P array 0.07 MB, excluding parsing/copy overhead.
Thus 17,995² pair outputs and GPU inference are unnecessary in principle.
Covariance must nevertheless use the full genome: estimating a 325-variable
covariance from only 98 gene observations has centered rank at most 97.
No conditioning, runtime or fit was tested here.

This is a verified integration/method-qualification gap, **not proof that GLS
cannot be applied to Sanger data**. A published Sanger-compatible preprocessing
artifact or independently validated adapter would be needed before generating
a fresh targeted association reference.

## License and boundary

The [Sanger policy](https://depmap.sanger.ac.uk/documentation/data-usage-policy/)
allows internal research/education while restricting resale, commercial
services and direct third-party API embedding. Unrestricted open-data or MIT
redistribution rights are not asserted. This check did not add a Sanger source
to the app or embed its API.

All source metadata, code/version checks, native headers, strict coverage rows
and range receipts are preserved under
`runs/sanger_fireworks_feasibility_20261113/`. The sealed feasibility report is
`feasibility_report.json`, seal `faaa2aa0…`. The dataset is stopped at this gate;
no bias-control substitution, raw-screen reimplementation, additional metric
or fallback fit was attempted.
