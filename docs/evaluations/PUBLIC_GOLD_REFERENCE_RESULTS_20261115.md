# Public curator references: executed assessment

Published labels have now been recovered and applied, rather than only screened
for feasibility. The clearest bounded gain is **additional localization-label
recovery from the saved native GO source**. Interaction qualification produces a
precision–coverage trade-off. Two exact cancer claim–evidence projections match
actual human gold. These results do not provide one accuracy percentage for the
entire graph.

Open the [readable report](public_gold_20261115/report.html),
[complete aggregate results](public_gold_20261115/summary.json) or
[source/candidate register](public_gold_20261115/source_qualification.json).
The [independent numerical audit](public_gold_20261115/numeric_audit.json)
checks every copied metric, denominator and study omission against its source.
This is a local research publication. It has not replaced the hosted reviewer
site's graph or saved scientific assessment.

## Localization: measured recovery beyond the captured Pharos annotations

The released [HOU test set](https://zenodo.org/records/18435290), associated with
the [2026 localization benchmark](https://doi.org/10.1038/s41592-026-03142-6),
contains 3,814 proteins with positive location labels at three levels. Exact
accessions match **31 of the original 99 primary proteins**, representing 31
distinct genes. The other 68 proteins remain reference-unavailable. The full
218-protein workspace has 45 identifier matches, reported as coverage only;
neighbors without original complete Pharos GO retrieval are not negative cases.

All five arms and all three levels were fixed before joining the cohort to its
labels. Main arms use the same 107-entry, ontology-qualified crosswalk from
official UniProt subcellular-vocabulary GO cross-references to author labels.
No score threshold, model fitting or outcome-based selection is involved.

| Fixed arm | Detailed positive labels recovered | Middle | Broad | Additional detailed outputs, truth unknown |
|---|---:|---:|---:|---:|
| Captured Pharos GO annotations | 41/51 (80.4%) | 40/46 | 42/48 | 38 |
| Actual retained Pharos annotations | 41/51 (80.4%) | 40/46 | 42/48 | 38 |
| Native positive `located_in`, all eligible codes | **44/51 (86.3%)** | **42/46** | **44/48** | **27** |
| Native positive `located_in`, experimental codes | 42/51 (82.4%) | 40/46 | 42/48 | 16 |
| Unchanged author-map coarse control | 44/51 | 42/46 | 44/48 | 51 |

The all-code native arm improves two proteins, worsens none and leaves 29
unchanged at each level. Its three gained detailed labels come from additional
native GO terms absent from the captured Pharos cellular-component frame under
the identical mapping. Filtering original rows alone cannot add those terms.
Removing obsolete IDs alone produces no difference in this comparison.

The gained labels trace to four eligible native records: three IDA annotations
assigned by HPA and one TAS annotation assigned by PINC. **HOU also uses HPA**,
so there is concrete shared-provider exposure. Annotation dates span 2003–2025;
the historical GOA vintage underlying Pharos is unknown. The result demonstrates
representation coverage and curator/imaging-reference concordance, not new
independent experiments or necessarily newer evidence. Experimental-only
filtering loses two supported labels in two other proteins, illustrating a
coverage cost; TAS annotations are not thereby false.

Source inspection also caught two upstream qualification limits. The author's
coarse dictionary includes non-entailing mappings such as generic membrane to
plasma membrane. A fixed `is_a`/`part_of` containment check excludes 53 such
assignments before the outcome join; the original 160-entry map remains a
separate control. An author notebook function can admit an OpenCell-only label
despite its documented two-source intent. The release lacks per-label source
masks, so this behavior cannot be attributed to the 31 matched cases. The
released labels were not silently repaired. Missing compartments remain unknown:
no biological precision, specificity or F1 is inferred from their omission.

## Cancer: exact human-reviewed claim–evidence gold

The [CIViC-Fact author release and manual reviews](https://github.com/creisle/civicfact/tree/1a767d889b015a836f0f4331afcac5cef165ec7f)
provide two exact matches in the current clinical family. Admission requires
the same Evidence Item ID, PMID, complete five-field molecular-profile / type /
significance / therapy-set / disease projection, and **identical evidence
paragraph**. Both labels are explicit human corrections to `SUPPORTS`; the raw
typed review, processed review and released final label agree. Bracketed model
tags, augmented claims and inconsistent versions are not human gold.

All **46 Evidence Items / 41 qualified assertions** remain in the denominator:
two distinct assertions have a supported benchmark projection and 44 source
records remain unmatched. The captured Pharos-only graph contains none of these
reported-response claims, so the retained workspace adds **two gold-labelled
claim projections**. This is added labelled coverage, not an accuracy gain.

The reference has one human reviewer and shared CIViC/study lineage. Direction,
origin, therapy-interaction details and complete clinical interpretation exceed
the older five-field task. The entire assertion's scientific judgment and its
candidate review state remain unchanged. Earlier CIViC-Fact model/reference
exposure is recorded; no newly blinded model evaluation is claimed.

## Interactions: actual positives and negatives, with states preserved

[SNOOPPI](https://doi.org/10.1093/bioinformatics/btag736) supplies released
sequence-specific interaction labels. Exact full canonical human sequences,
literal accessions and source-state qualification admit **15,326 positive and
16 negative pairs** in the fixed historical 20,412-protein frame. There are
311 positive homomers outside the declared nonself graph-proxy domain. The
smaller current 218- and pruning 3,172-protein frames have 42 and 1,099 positive
canonical pairs, respectively, and no canonical negatives. Their specificity
and binary discrimination remain undefined.

Mutant/PTM sequence records, ambiguous identifiers and inferred binding-region
deletion negatives are not converted into wild-type gold. An independent
source-code audit confirmed that 152 canonical positive control rows carry
metadata describing their PTM-modified counterparts; the controls themselves
have original canonical sequences. Their labels were not changed after review.

The separate [Negatome manual reference](https://pmc.ncbi.nlm.nih.gov/articles/PMC3965096/)
uses original unfiltered literature pairs and a separately identified
IntAct-filtered stratum. It excludes structural-noncontact negatives. Opposing
gene-pair curations remain unknown. The full frame has **14,995 positive /
1,223 negative / 20 conflicting unknown pairs**; current and pruning frames
retain **23/3/0** and **1,005/150/7**. Complete tested sequences and context are
not supplied by these manual tables. This broader panel is an assay-context
proxy check, not a universal canonical-binding truth table.

### Same-release source comparison

STRING 12.5's functional and physical files were compared using identical gold
panels and a reciprocal direct `UniProt_AC` plus full-sequence crosswalk.
Exactly 16,206 of 20,414 canonical reference proteins are admitted; 2,768
sequence mismatches and 1,440 missing direct aliases remain unavailable.
Missing numerical scores are never filled with zero. Nonedge presence is only
a declared classifier prediction, not negative gold.

| Reference / frame | Common returned-score pairs (+ / −) | Functional AUROC | Physical AUROC |
|---|---:|---:|---:|
| Canonical / current 218 | 13 (13 / 0) | Undefined | Undefined |
| Canonical / pruning 3,172 | 632 (632 / 0) | Undefined | Undefined |
| Canonical / historical 20,412 | 4,318 (4,314 / 4) | 0.7035 | 0.7721 |
| Assay-context / current 218 | 14 (13 / 1) | 0.2692 | 0.2692 |
| Assay-context / pruning 3,172 | 696 (626 / 70) | 0.3637 | 0.3632 |
| Assay-context / historical 20,412 | 4,630 (4,300 / 330) | 0.3435 | 0.3888 |

Only four canonical negatives have both scores; omitting one negative study
reverses the apparent advantage. All seven study-omission checks are retained.
The broader panel remains below chance in both networks. Nearly perfect AP in
the canonical subset mostly reflects its 99.9% positive prevalence and is not
headline evidence of scientific accuracy.

On the **same mapped known units** of the broad full-frame panel, physical
network presence reduces negative-reference conflicts **492 → 330**, while
positive hits fall **4,889 → 4,300**. Conditional precision rises
0.9086 → 0.9287 and recall falls 0.4848 → 0.4264. Another 5,197 cases are
identity-unavailable; the 20 conflicting reference rows are not scored.
This is a trade-off, not a general pruning gain. Physical STRING includes
co-complex evidence, rather than only direct binary binding. Shared
IntAct/Negatome study or calibration exposure remains possible.

The earlier Pharos-represented STRING 11.0 functional graph is retained as a
separate historical proxy baseline, with all six panels and their denominators
in the aggregate JSON. Its weights date to December 2018. It does not stand in
for current Pharos or the same-release comparison.

## Other references and reproducibility

MitoCarta supplies two positive inventory labels and one explicit
mito-interacting/outside-resident label among 98 primary gene units. All four
arms agree: two positive hits and one outside-inventory conflict; 95 units
remain unknown. No improvement is claimed. DrugCentral agrees with 168/174
target–drug source records, which is source concordance. ClinGen's 3,733 expert
curations supply no exact gene/disease match to the 100 current association
records. No broader-disease substitution is made.

Actual BioKGBench and EvidenceNet releases were inspected; their labels concern
different stored graph states or extracted assertions. The DisGeNET labels in
the inspected KG-accuracy method are synthetic. Another published expert
triplet collection was found but its public label artifact was not located.
The [register](public_gold_20261115/source_qualification.json) records these
decisions; it does not claim every possible source has been exhausted.

The optional adapters reuse native source readers, the existing Gold/GAF
verification and scikit-learn metrics. The verified integration gaps were
format/version-specific accession, proteoform, evidence-identity and mapping
boundaries. No new biological truth-voting protocol or learned verifier was
invented. Preparation scripts are in
[the reproduction bundle](../../tools/reference_accuracy/reproduction/README.md),
with public source locators, hashes and a PPI preparation configuration example.
Full-source PPI preparation reproduces all 12 previously consumed admission
files byte for byte; GO metadata replay reproduces the identity masks and both
crosswalks. Raw cases, excerpts and sequences remain outside the public source
tree under their respective terms.

Use the separate optional Python 3.12.4 environment and
[public-gold dependency pins](../../tools/reference_accuracy/requirements-public-gold.txt).
The application retains its empty dependency list. Core invented-fixture tests
exercise missing-data, identity, context, state, conflict, mutation and
source-sealing failures without installing scientific packages:

```sh
python3 -m unittest discover -s tests -p 'test_reference_accuracy_*.py' -v
python3 -m unittest discover -s tests -p 'test_civic_fact_gold.py' -v
```

The [separate native-location workspace](NATIVE_LOCATION_WORKSPACE_20261115.md)
now uses the fixed source profile in actual source questions, inspection and
exports without importing reference labels. Its all-target question census
passes. This is application integration, not a new confirmatory biological test.

This assessment changes no original/default graph or review state. The original
200 sampled audit judgments stay separate. Public human labels, curator-source
agreement, independent experiments and prospective prediction gain remain
different claims; results from these tasks are not pooled into a graph-wide
accuracy percentage.
