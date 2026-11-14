# CUX1: a verified gene/product scope limit

The full Pharos319 identifier audit found **83 STRING locus identifiers linked
to 244 Pharos protein accessions**. These are mapping ambiguities for a
protein-level model, not 244 demonstrated biological errors. The original
Pharos records remain unchanged; the fixed model view withholds edges whose
STRING-to-protein correspondence is not one-to-one.

One case is already present in the real CRC workspace:

| Pharos protein | Source name | NCBI Gene | Archived STRING representative |
|---|---|---|---|
| P39880 | Homeobox protein cut-like 1 | 1523 (CUX1) | ENSP00000353401 |
| Q13948 | Protein CASP | 1523 (CUX1) | ENSP00000353401 |

This is a known biological distinction. The [primary CASP study](https://pubmed.ncbi.nlm.nih.gov/12429822/)
reports different products of the same locus: a nuclear transcription factor
and a Golgi membrane protein. [NCBI Gene 1523](https://www.ncbi.nlm.nih.gov/gene/1523)
lists both accessions, while [UniProt Q13948](https://www.uniprot.org/uniprotkb/Q13948/entry)
preserves the CASP product and its isoforms. The same gene symbol or STRING
representative therefore does not justify merging these proteins, copying every
functional annotation between them, or counting their provider records as
independent biological confirmations.

The existing STRING update adapter already reports
`ambiguous_locus_correspondence` and `collapsed_pair` within a queried cohort.
The explicit gene-relationship and Pharos400 identity helpers also preserve
product/isoform distinctions. Those mechanisms should be reused. The
same-accession SSSOM exporter must not be repurposed to assert UniProt–STRING
sequence equivalence.

The new global audit extends the model's ambiguity check beyond its original
cohort: **236 previously admitted model pairs** become unresolved under the
full source mapping. They are quarantined only from the model adjacency, with
original source weights and Pharos records retained. This is a documented
source-identity qualification; it does not establish that the underlying
functional associations are false.

Exact source rows, native January 2019 alias provenance and existing code hooks
are recorded in
`runs/prediction_next_20261113/full_scope/P39880_Q13948_product_scope_case.json`.
The identifier lookup is from the April 2024 Pharos319 archive. It is historical
context, not a claim about the current API's complete mapping state. The
original frozen model and globally qualified controls remain separate in the
comparison.

The local app now adds accessions to same-symbol protein labels and provides a
conditional passport notice with a direct switch to the other product. Switching
retargets the assertion filter before reading its records. This is a general
display/selection safeguard, not a hard-coded CUX1 correction or new biological
assertion. The [actual local passport](../images/cux1_product_scope_20261113.png)
shows the preserved CASP name and distinct accession.
