# Reference-source traceability audit

Every residual PK biological-process positive in both reference views was checked against all eligible native GAF source rows. This checks source traceability and admission consistency. It does not independently establish biological truth or an accuracy percentage.

| Source readout | Native view | Fixed-T0 view |
|---|---:|---:|
| Residual protein/function pairs | 3254 | 3243 |
| Pairs with eligible raw-source support | 3254 | 3243 |
| Distinct supporting native rows | 475 | 472 |
| Label-to-source-row links | 3800 | 3804 |
| Distinct literal PMID identifiers | 272 | 271 |
| Distinct reference bundles | 289 | 288 |
| Supporting rows with extensions | 52 | 52 |
| Supporting rows with With/From | 19 | 18 |
| Supporting rows with product-form IDs | 0 | 0 |

A native row can support several inherited labels. The native view has 472 direct links and 3,328 ancestor links; the fixed-T0 view has 472 direct links and 3,332 ancestor links. Ancestor links follow the original is_a/part_of closure and do not represent additional assays.

| Eligible support-link family | Native view | Fixed-T0 view |
|---|---:|---:|
| Experimental | 3290 | 3288 |
| IC | 176 | 176 |
| TAS | 334 | 340 |

Experimental evidence codes, curator inference (IC) and traceable author statements (TAS) are distinct admission families. These are link counts, not independent studies. A reference bundle can contain several identifiers for one cited source.

The raw target-scope inventory preserves 234,156 T0 annotation rows on 3,298 target proteins, and 240,334 T1 rows covering all 3,300 targets. NOT annotations and non-admitted evidence remain in the private raw source inventory; they do not become positive support. Source assigners, curation dates and literal qualifiers remain available in the complete private trace.

Publication dates have not been independently inventoried. Annotation dates must not be interpreted as publication dates or new experimental discoveries. No model, label, threshold, performance endpoint, graph or app default was changed.

The JSON contains only aggregate counts and lineage hashes. Protein/function cases, PMID mappings, score ledgers and local case paths remain private.
