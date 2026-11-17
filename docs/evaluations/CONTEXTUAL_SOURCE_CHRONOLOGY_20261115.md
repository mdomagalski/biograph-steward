# Source chronology and known-annotation audit

This read-only follow-up qualifies the completed context-aware comparison.
It changes no forecast, label, exclusion, threshold, model choice or score.

## Question checked

The complete provenance audit found **111** supporting T1 annotation rows
dated on or before the April 10 starting snapshot. We checked whether these
were previously admitted annotations that should already have been excluded,
rather than assuming an explanation from their dates.

The [official GAF specification](https://geneontology.org/docs/go-annotation-file-gaf-format-2.2/)
separates file-generation date from annotation date in column 14. Neither
dates a publication or experiment. The author reference builder compares
admitted protein/term/aspect associations across snapshots and does not apply
an annotation-date novelty filter. Its source also notes that ontology changes
can introduce new ancestral labels. The downstream native evaluator propagates
the starting known annotations on the evaluation ontology before exclusion.

This is a documented benchmark issue. The
[CAFA3 assessment](https://link.springer.com/article/10.1186/s13059-019-1835-8)
identified older annotations newly imported into GOA from another database;
the organizers verified their prior public availability before removing them.
The [official CAFA5 release](https://zenodo.org/records/22381862) supplies a
separate publication-after-T0 evaluation with its own known exclusions.
These precedents do not establish why any of our 111 rows appeared later.

The [LAFA preprint, June 2026 revision](https://arxiv.org/html/2604.20782v2)
explicitly tests whether starting nonexperimental GOA annotations predict later
curator-supported annotations. The 58 matching T0 associations under
nonreference evidence are therefore legitimate available context for this
declared task. The completed comparison retained that flat nonexperimental
baseline as a control; these associations are not claimed as entirely unknown
biological functions.

## Complete source-to-known check

Every supporting row was followed through literal and native-alias association
matching, T0 evidence admission, the original extracted/propagated tables,
the actual PK-known inputs and the exact evaluator GT/exclusion parsers.
This checks the chain before exclusion as well as the final disjoint masks;
checking only final residual/known disjointness would be tautological.

| Readout | Native view | Fixed-T0 view |
|---|---:|---:|
| Distinct supporting T1 rows examined | 475 | 472 |
| Rows with an already admitted curated-positive T0 association | 0 | 0 |
| Rows with a T0 association only under nonreference positive evidence | 58 | 58 |
| Rows without a T0 literal/native-alias association | 417 | 414 |
| Old-dated supporting rows | 111 | 111 |
| Of those, with only nonreference T0 evidence | 19 | 19 |
| Of those, without a T0 association | 92 | 92 |
| Source-to-known-chain discrepancies | 0 | 0 |
| Residual-positive/parsed-known-mask discrepancies | 0 | 0 |

There were also no exact T0 row matches or matches preserving the assessed
evidence/qualifier/context fields for these supporting rows. Counts describe
T1 rows, not independent pairs, studies or experiments. The nonreference
category is the original benchmark's evidence policy; it is not a biological
falsehood label or proof of a curator's reason for a change.

The model-independent partition of **all positive protein/function pairs**
also preserves their different unit:

| Dates of all supporting annotation rows | Native view | Fixed-T0 view |
|---|---:|---:|
| Only on/before the starting date | 702 | 716 |
| Only after the starting date | 2,537 | 2,508 |
| Both older and later support | 15 | 19 |
| Unknown/invalid support dates | 0 | 0 |
| Complete residual-positive pair population | 3,254 | 3,243 |

These are source-date counts, not performance slices or independent
experiments. Ontology inheritance lets one raw row support many label pairs.

The [maintained read-only adapter](../../tools/contextual_combination/source_coherence.py)
accepts pinned sources, dates and namespace settings. It reuses the official
GAF-parser sidecars and unchanged native reference/GT/exclusion helpers.
Invented/native fixtures cover missing known inputs, NOT/context differences,
strict date handling, empty support and a second GO namespace. Real-data
verification remains primary BP only; it reproduced the original complete
source audit without changing any evaluated reference or forecast.
The [complete aggregate](contextual_source_coherence_20261115/aggregate.json)
and [qualification/parity receipt](contextual_source_coherence_20261115/receipt.json)
retain its source and execution commitments.

## Local archived-reference presence

A safer alternative to the external publication-age lookup reuses the exact
Swiss-Prot **2026_01** archive, whose official release note dates it to
**January 28, 2026**. The installed official Biopython reader streamed all
574,627 reviewed records without extracting the DAT file. The complete
20,431 reviewed-human records yielded 90,324 distinct PubMed identifiers;
that inventory was constructed before matching any evaluation references.

Of the native reference's **272** supporting PubMed identifiers, **107** were
already cited in that pre-T0 reviewed-human archive and **165** were absent.
The fixed view has 107 present and 164 absent out of 271. This establishes a
lower bound on older **reference-identifier presence**, not availability of
the evaluated protein/function assertion. Absence does not establish a new
publication, previously unknown function or lack of public evidence elsewhere.
No publication year, exact publication date or experiment date was inferred.

The [aggregate record](archived_reference_presence_20261115/aggregate_report.json)
and [reader qualification](archived_reference_presence_20261115/qualification_receipt.json)
retain exact archive/member, release-note and official-reader hashes. The
[reusable reader](../../tools/contextual_combination/archived_reference_presence.py)
performed no network requests and exported no selected identifiers. Raw
identifier inventories remain private on the persistent research disk.

## Consequence

No missing-known-input bug was detected in this comparison. The result remains
**later-snapshot annotation recovery under the declared admission rules**.
It does not establish first public knowledge, first annotation, publication
novelty or newly performed experiments. Backfill, evidence changes and source
history are possible explanations, not assigned causes. A different novelty
endpoint would require a separately qualified reference and known mask; it
must not silently replace the completed primary endpoint.

No post-hoc date filtering or model-dependent source selection was applied.
The [completed results](CONTEXTUAL_COMBINATION_RESULTS_20261115.md) and their
unfavorable controls remain unchanged. The optional publication-age lookup
was not executed after automatic approval rejected sending selected reference
PMIDs; no publication dates were inferred in its place. Its limited local
alternative reports only archived reference-identifier presence, as above.
