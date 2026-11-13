# Coessentiality task and source gate

This optional gate reads identifiers and methods before opening numerical
coessentiality values. It does not fit a learner, recompute correlations, assign
biological negatives or change any source graph or earlier experiment.

The question is whether source-qualified shared pathway context concentrates
published experimental **co-functionality** signal. This fits the source
relation more closely than physical-binding recovery. It still cannot establish
whole-graph biological accuracy, clinical usefulness or CRC-specific causality.

## Established sources and method

[Wainberg et al. 2021](https://doi.org/10.1038/s41588-021-00840-z) release native
17,634 × 17,634 GLS P values and correlation signs through their
[MIT-licensed author code](https://github.com/kundajelab/coessentiality).
The study uses DepMap Public 18Q3 CERES gene effects, accounting for guide/copy
number effects. GLS addresses relatedness between cell lines. The supplied
pipeline additionally removes four olfactory-gene PCA components and four
arbitrary cell lines, leaving 481 processed profiles from 485 original screens
across 27 lineages. Recomputing raw Pearson correlations would discard those
published corrections and is outside this track.

The authors compare ranked partners at fixed N = 1…10 with functional pathway
or complex relationships, normalizing overlap by the comparator's background
pair frequency. This is a useful existing evaluation pattern. Restricting a
future readout to the preexisting project cohort would be an explicit bounded
adaptation, not reproduction of the full-proteome result. Shared-pathway
contexts remain common-object relationships, never newly asserted PPIs.

The independent experimental measurement is a processed fitness association.
It is not a binary universal truth label. Negative correlation can describe
antagonistic regulators or different cell-type contexts. A high P value or an
unmeasured gene is not proof of biological nonfunction. There is no new
significance threshold or conversion of absent significant pairs into negatives.

[Author issue #5](https://github.com/kundajelab/coessentiality/issues/5) reports
discrepancies reconstructing significant-pair counts. The paper's per-gene FDR
and the repository's global-FDR module-clustering code have different roles.
Neither is silently substituted for the other. A continuous native-value/rank
readout would avoid rebuilding an uncertain significant-edge list.

[Wright et al. 2024/2025](https://doi.org/10.1038/s44320-024-00077-y) and their
[official evaluation code](https://github.com/sarah-n-wright/Network_Evaluation_Tools)
also support matching the network relation and intended evaluation task rather
than assuming performance transfers from one biological endpoint to another.

## Outcome-free identifier proof

The official release
[DepMap Achilles 18Q3 public](https://doi.org/10.6084/m9.figshare.6931364.v1)
is CC BY 4.0 according to native Figshare metadata. Only the first CSV header
row of the exact author-linked `gene_effect.csv` file is captured here. No
essentiality observation is read or saved. The full CSV checksum is not
represented as independently verified by a header-only capture.

The author loader strips text following the first space in the header's gene
labels. `identifiers.py` verifies the **entire** stripped header order against
the author-provided `genes.txt`, then preserves the original parenthesized
Entrez IDs. Current reviewed human UniProt/HGNC/Entrez relationships are reused
from core. A renamed symbol can therefore match through its explicit native
Entrez ID, without alias guessing or protein/gene identity inference. Repeated
or missing native IDs remain unknown.

```sh
python -m tools.coessentiality_feasibility.identifiers --help
```

The saved November 13 gate has 99 source proteins, 98 distinct current genes
and 92 uniquely covered native matrix genes: 4,186 nonself gene pairs. Six
missing genes remain unknown. At the native historical Wiki feature boundary,
the source-qualified view covers 69 of these genes. Every future arm must use
the same 92-gene evaluation universe; zero context is a lack of source context,
not a biological negative. The outcome-free projected gene-level degree vectors
remain exactly matched between the fixed treatment and degree control.

## Version, independence and licensing limits

The exact author commit, native header, original gene order and public metadata
are pinned in ignored run receipts. Source NPY headers were inspected with no
array values read or saved. Both artifacts are little-endian float64, Fortran
order, 17,634², with an 80-byte header and total size 2,487,663,728 bytes each.
The server advertises byte ranges and stable per-file ETags. This is the
published historical reference, not a claim of the latest DepMap biology.

MIT applies to the author repository. The separately hosted matrix files do
not carry an explicit data-license statement in their directory. No blanket
redistribution license is inferred and these files must not be vendored into
the product or public repository. The original DepMap release's CC BY license
is recorded separately from the author's derived results.

No direct Wainberg PMID/DOI, coessentiality, DepMap or Achilles citation was found
in the captured 253 exact historical Wiki native models. This is a literal
known-reference check, not proof that all biological knowledge is independent.
Other resources, indirect curation and unavailable models can still reuse
evidence. The original pipeline also uses olfactory GO annotations for noise
correction and compares methods with CORUM/hu.MAP/STRING. These priors and
method-selection dependencies must remain explicit.

The primary article contains illustrative gene-pair results. These literature
examples were encountered during method review; no claim of complete human
blinding is made. Numerical matrix outcomes remain unopened at this gate.
The whole target cohort and source arms predate their retrieval. A fixed
source/control/readout contract is required before any matrix values are opened.

The primary also documents residual copy-number artifacts among **syntenic**
pairs, despite CERES correction. Its functional predictions exclude syntenic
modules and Extended Data Fig. 6 evaluates same- versus different-chromosome
pairs separately. A primary nonsyntenic readout and secondary all-pair/syntenic
sensitivity would reuse that distinction. Canonical chromosomes can be bound
to the existing frozen HGNC registry without a new genomic-distance cutoff.
Those labels describe the reference genome, not a cancer cell line's somatic
karyotype or proof that remaining pairs are artifact-free.
# Controlled functional-concordance readout

`prepare.py`, `matrix.py` and `compare.py` stage the frozen comparison described
in [contract.md](contract.md). This reads the author's published two-sided GLS
P-value/sign arrays; it does not implement a new correlation estimator, run a
learner or create biological truth labels. Primary ranks include both signs.
Nonsyntenic pairs are primary; sign and same-chromosome views are diagnostics.
All N=1…10 points are retained with fractional boundary ties, query-matched
backgrounds and the complete fixed query frame. Reference missingness remains
UNKNOWN.

The preparation reuses the existing native source verifiers and official human
gene-product registry. Nulls are generated after gene deduplication and measured
gene restriction: twenty fixed count subsets and twenty author-XSwap draws for
each treatment, with both bipartite degree vectors checked. Original controls
are preserved as diagnostics because original protein/global degree matching
does not necessarily survive measurement restriction. These draws give
descriptive control envelopes; mixing, a uniform null and statistical
significance are not established.

Run preparation **before** capture in an optional runtime containing NumPy and
the pinned author XSwap build already recorded by `tools/wiki_utility`:

```sh
python -m tools.coessentiality_feasibility.prepare \
  --current CURRENT_WIKI_PACKET --historical HISTORICAL_WIKI_PACKET \
  --registry REVIEWED_HUMAN_REGISTRY --readiness READINESS_INPUTS \
  --xswap PINNED_XSWAP_LIBRARY --out NEW_FROZEN_DIRECTORY
python -m tools.coessentiality_feasibility.matrix \
  --frozen NEW_FROZEN_DIRECTORY --out NEW_CAPTURE_DIRECTORY
python -m tools.coessentiality_feasibility.compare \
  --frozen NEW_FROZEN_DIRECTORY --captured NEW_CAPTURE_DIRECTORY \
  --out NEW_RESULTS_DIRECTORY
python -m tools.coessentiality_feasibility.report \
  --scored NEW_RESULTS_DIRECTORY --out NEW_READABLE_DIRECTORY
```

Outputs must be new directories outside every input. Capture requires every
requested native column, HTTP206, exact byte range/length and the predeclared
ETag. A failed transfer aborts without a success manifest; it is never treated
as biological missingness. Each saved range has its own SHA256. No complete
matrix checksum is inferred. ETags are server validators, not cryptographic
hashes. The NumPy reader validates the native Fortran header and byte offsets;
an offline nonsymmetric rectangular save/load control guards transposition.

Result files retain every arm/scope/N curve, a common native-pair availability
ledger, all reference selections, compressed per-query scores and full control
envelopes. Source pins and all frozen arm/control/gene metadata are replayed
before/after comparison. This is pan-cancer experimental functional-concordance
evidence, not PPI binding, colorectal-cancer-specific mechanism, causal effect,
calibrated accuracy or a new prediction-benefit demonstration.

The [author code](https://github.com/kundajelab/coessentiality) is MIT; the
original [DepMap18Q3 release](https://doi.org/10.6084/m9.figshare.6931364.v1)
is CC BY4.0. The separately hosted derived matrices do not state a distinct
data redistribution license; captures remain outside the repository. XSwap's
[author implementation](https://github.com/hetio/xswap) is BSD-2-Clause and
documents its bundled Roaring license. No model, GPU or Brev instance is needed.

