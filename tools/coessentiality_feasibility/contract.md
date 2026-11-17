# Frozen co-functionality comparison contract

This is one source-context concordance comparison against the author-published
Wainberg 2021 coessentiality matrices. It fits no learner and changes no graph,
earlier model experiment, pruning decision or reference label. The matrix
values are not training features or binary biological truth.

## Source frame and controls

The original 99 proteins map through explicit reviewed human relationships to
98 genes. Exact native DepMap Entrez headers and the complete author gene order
cover 92 genes. All 92 remain query identities, including zero-context genes.
The evaluation unit is a unique gene pair, not a protein isoform identity.
Gene-to-protein relationships and source evidence remain preserved separately.

Source arms are the unchanged normalized, current-qualified and historical
native-xref-qualified Wiki contexts from their prior frozen packets. Projection
uses exact full source-version URLs, unioning gene contexts through explicit
product relationships. It never merges different pathway revisions. Restriction
to the 92 measured genes gives 1,922, 1,275 and 1,020 gene/context links.

Generate primary nulls **after** gene deduplication and the fixed 92-gene
measurement restriction. Each treatment gets twenty count-matched subsets of
the normalized links (seeds 2026111201+i, i=0…19) and twenty author-XSwap
bipartite degree nulls (seeds 2026111202+i, i=0…19, multiplier 10, disjoint
integer endpoint ranges). Verify exact
unique link counts, gene and pathway degree vectors, and changed adjacency.
Keep swap-attempt/rejection counts and adjacency overlap for every draw. Report
all curves and descriptive minimum/median/maximum envelopes; these twenty
frozen algorithm draws do not establish uniform sampling or adequate mixing
and are not a significance test. The i=0 controls preserve the original seeds.
All four prior/global null arms remain reported as secondary diagnostics. Their
original protein/global counts do not establish measured-gene matching.

## Native reference semantics

Primary ranking is **unsigned native two-sided GLS P**, ascending, consistent
with `gene_pairs.py` and `modules.py`. Negative correlations can describe
functional antagonism and are not false biology. Native positive and negative
sign-restricted rankings are separately labelled sensitivity analyses. Sign zero
is preserved; invalid signs do not invalidate an otherwise usable unsigned P.

Use the author's lexical native-symbol upper triangle for an unordered pair.
Preserve the reverse values and asymmetry diagnostics without averaging or
choosing whichever direction is favorable. Zero and one are valid P values.
Nonfinite or out-of-range values remain UNKNOWN in a single common reference
availability ledger for every source arm. No FDR, significance threshold or
absent-pair negative label is reconstructed.

The primary scope is the fixed 3,968 different-chromosome pairs. The 218
same-chromosome pairs and all 4,186 pairs are separate sensitivities. Canonical
HGNC chromosomes are reference metadata, not cancer-cell somatic karyotypes.
This follows the paper's documented synteny/copy-number caveat.

## Complete curves and denominator

For every gene and N = 1…10, rank available partners by native P. At a boundary
tie, include fractional weight `(N - number strictly ahead)/boundary tie size`;
weights sum exactly to N. This avoids arbitrary partner-ID tie breaking.

For an arm, let `A(g,h)=1` only when the genes share at least one exact full
source-version context. Multiple contexts are not independent votes. This is
coannotation, not a new PPI or a biological truth label.

Observed hits are the sum of `weight(g,h)*A(g,h)` over selected partners.
Expected hits under uniform eligible partner selection are
`sum_g N * context_partner_count(g)/available_partner_count(g)`.
Report observed/expected enrichment, both hit fractions, all denominators and
all query records. This query-matched background handles unequal
interchromosomal candidate counts without reweighting genes implicitly.

For a primary N point, **every one of the 92 queries must have at least N usable
partners**. Otherwise that whole-frame point is unscorable, with query IDs and
UNKNOWN reasons preserved. Sensitivities may additionally report explicitly
conditional summaries over the common reference-available queries; they retain
all 92 rows and report eligible/unknown counts. They cannot establish primary
success. Zero source context never removes a query. Zero expected hits gives an
undefined enrichment, never a fabricated zero or one.

Report every point of every declared curve. The paper does not prescribe a
full-curve mean, so no new primary aggregate or best-N winner is introduced.
Our project-specific, predeclared descriptive claim rule allows a treatment
to be described as pointwise above the frozen comparators only
when all ten primary points are scorable and exceed normalized plus every one
of its forty valid null draws by more than numerical tolerance 1e-12 at every N. This is descriptive,
not statistical significance or generalized biological improvement. Mixed,
negative and unscorable outcomes remain visible. No P value is derived from
the ten correlated N points.

## Capture and scope

Before values, bind this contract, complete source-arm inventories, identifiers,
chromosomes, native 80-byte NumPy headers, expected HTTP ETags/byte counts and
implementation hashes. Source arrays are float64 Fortran 17,634². Partial
retrieval stores full native columns, exact HTTP Content-Range/ETag and payload
SHA-256. No complete-file checksum is invented. Native NumPy readers decode
those byte slices. The whole source artifact is not recomputed or redistributed.

The source is historical DepMap18Q3: 485 initial screens/27 lineages, with
published PCA/GLS preprocessing leaving 481 profiles. It is pan-cancer and
cannot establish CRC-specific mechanisms or clinical usefulness. GO-based noise
correction, method benchmarking, possible indirect study reuse and missing
native models remain explicit. Paper examples were seen during method review;
numerical matrix values were not. Earlier INMC results were already inspected.
This is a newly frozen exploratory endpoint, not an unseen confirmatory trial.

The earlier header-only HTTP request advertised bytes 0–127, but its reader
retained only the 80-byte header. No numerical values were decoded or persisted;
HTTP transport buffering is not asserted to have excluded payload bytes. ETags
are server representation validators, not cryptographic full-file hashes.

Primary sources: [paper](https://doi.org/10.1038/s41588-021-00840-z),
[author code](https://github.com/kundajelab/coessentiality),
[known FDR issue](https://github.com/kundajelab/coessentiality/issues/5),
[native DepMap release](https://doi.org/10.6084/m9.figshare.6931364.v1).
