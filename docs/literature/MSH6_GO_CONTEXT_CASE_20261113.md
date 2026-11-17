# MSH6: why source context must remain visible

For human **MSH6 (UniProtKB:P52701)** and **GO:0043570, maintenance of DNA
repeat elements**, a native experimental negation and the original Pharos
annotation have different source fields. Neither should silently replace the
other.

| Field | Pinned native GOA annotation | Original Pharos projection |
| --- | --- | --- |
| Relation and polarity | `NOT\|involved_in` | Not retrieved; unknown |
| Evidence | `IMP` | `IBA` |
| Assigning source | `BHF-UCL` | `GO_Central` |
| Reference | [PMID:16388310](https://pubmed.ncbi.nlm.nih.gov/16388310/) | Not retrieved |
| Annotation date | `20080917` | Not retrieved |
| Taxon; product form | `taxon:9606`; `UniProtKB:P52701` | Not present in this GO record |

The native row is line 326404 of the pinned
[human GOA release](https://release.geneontology.org/2026-08-05/annotations/gaf/HUMAN-uniprot.gaf.gz),
generated July 28, 2026. Its annotation extension and With/From fields are empty.
The canonical product-form repetition is preserved, without an isoform mapping.
Pharos reports an annotation; the graph predicate is `biograph:has_go_annotation`,
and its missing polarity is not interpreted as a positive function claim.

The [2006 paper](https://doi.org/10.1038/nsmb1042) tested doxycycline-induced
contraction of an engineered `(CAG)95` HPRT reporter in HT1080-derived FLAH25
human cells. [Figure 2](https://www.nature.com/articles/nsmb1042/figures/2)
reports two MSH6 siRNAs without a significant contraction change under the
authors' criterion; MSH2/MSH3 knockdowns provide responsive controls.
[Published methods](https://media.springernature.com/original/springer-static/esm/art%3A10.1038%2Fnsmb1042/MediaObjects/41594_2006_BFnsmb1042_MOESM8_ESM.pdf)
describe repeated transfection, protein blots, viable-cell normalization and at
least five experiments. Supplementary controls check reporter transcription and
partner-protein stability. This is a controlled, endpoint-specific negative
observation, not a demonstrated biochemical function-loss variant or an
equivalence test proving absence of every role for MSH6. The main article is
subscription-only; public figures, supplements and metadata were examined.

The authors' [open 2009 primary follow-up](https://pmc.ncbi.nlm.nih.gov/articles/PMC3671857/)
explicitly limits this reporter to **large contractions exceeding 55 repeat
units**, distinguishes that process from mono/dinucleotide-repeat maintenance,
and cautions about extrapolating to disease-relevant expansions and in-vivo
biology. Its discussion interprets the earlier MSH6 result; it is not independent
replication of that experiment.

The GO record is a genuine **curator-asserted negation**. That does not make its
entire broad biological scope independently verified by our reading of a
knockdown null. [Official GO guidance](https://geneontology.org/docs/go-annotations/#the-not-modifier)
distinguishes NOT from inconclusive results and allows positive/NOT annotations
to coexist when context or evidence differs. This case merits source-context
inspection, without overruling the curator or labelling the Pharos record false.

Existing code already supplies the needed mechanism: native GO inspection
returns the exact NOT row and references; the compatibility sidecar identifies
the same subject/term with differing evidence and assigning source. No new
scorer or biological pruning rule is needed. A readable cue can say: **“A
separate NOT-qualified native annotation exists for this protein and GO term;
its evidence and source differ. Inspect both contexts.”** Historical record
identity, Pharos polarity loss and a contradiction of annotation existence
remain unproved.

Local proofs and the replayed inspector output are preserved under
`runs/msh6_GO_context_review_20261113/`. No source graph, qualifier, decision or
earlier score was changed.
