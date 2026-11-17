# Current-refit source qualifications — November 15

A source-only check reproduced the **124 canonical BP NOT pairs** and **22
positive-target overlap flags** in the original 4,040-protein fitting frame.
It used the existing pinned ontology normalization, published grouping and
Biopython 1.88 GAF reader. It read no future reference, forecast, model or
performance result and changed no labels or predictions.

| Source finding | What it establishes |
|---|---|
| 21 of the 22 positive-target flags already occur in the original full fitting repertoire; one is added by the current positive union | Most flags precede this refit. Retaining a positive is not a new biological adjudication. |
| 16 flagged canonical pairs also have at least one current, direct positive row admitted by the existing Experimental/IC/TAS rule | Some opposite-polarity support is present within the same current snapshot. It is not solely an old-versus-new annotation issue. |
| Those 16 pairs have 21 native positive rows: 18 admitted Experimental/IC/TAS rows and three additional IBA rows | The three IBA rows are context outside this benchmark's curated admission, not three additional curated labels. They concern three pairs, each of which also has admitted positive support. |
| The other six pairs lack a current admitted direct positive row | Their historical or ancestor-derived positive provenance was not adjudicated here. Missing a direct match remains unknown. |
| The 22 native NOT rows and 21 current positive rows have no explicit product-form or annotation-extension field; all have the `involved_in` relation | These recorded fields do not resolve the flags. Blank fields establish neither identical biological context nor a form-specific explanation. |

The 22 NOT rows comprise 17 rows within the benchmark's Experimental/IC/TAS
admission codes and five outside it. Admission groups are not a general quality
ranking or a count of independent studies. Native rows, references and
qualifiers remain available in the separate private replay.

GO documents that positive and NOT annotations can coexist when findings
conflict, and that NOT can describe a particular protein form. Missing
annotations are not biological negatives. These flags therefore require
source-context review; they do not justify automatic target removal or label
flipping. [GO annotation principles and NOT guidance](https://www.geneontology.org/docs/go-annotations/)

GAF 2.2 keeps the primary entity in column 2, the specific product form in
column 17, and additional context in column 16. Canonical protein/term targets
cannot establish equivalence of these scopes. The audit retains exact native
rows rather than inventing missing context. [Official GAF 2.2 specification](https://geneontology.org/docs/go-annotation-file-gaf-format-2.2/)

## RCA evidence check

The GO external-resource guidance recommends omitting RCA, which is being
retired because of false positives. The current fitting source contains four
RCA rows across all aspects: **BP 0, MF 1 and CC 3**. None survives the unchanged
fixed-BP normalization or enters eligible positive BP context. No RCA filtering
change or model retry was needed for this BP refit. This check does not certify
the older MF/CC models or all other source profiles. [GO external-resource guidance](https://geneontology.org/docs/guidelines-external/)

## Reproduction and boundary

[Aggregate source counts](current_refit_negative_context_20261115/aggregate.json),
[admission clarification](current_refit_negative_context_20261115/admission_clarification_v1.json),
[RCA qualification](current_refit_negative_context_20261115/RCA_source_check_v1.json)
and the [preservation receipt](current_refit_negative_context_20261115/qualification.json)
record exact source and code hashes. All 14 members of the 25,420-byte private
source replay were verified by size and SHA-256 after transfer. It retains the
unchanged diagnostic, native source records and receipts; it is not a public
case release.

This is a data-context qualification, not a new accuracy endpoint or a remedy
shown to improve prediction. It preserves a concrete unresolved limitation:
flat fitting targets do not represent the full context of opposite-polarity
source assertions. The frozen comparison and application remain unchanged.
