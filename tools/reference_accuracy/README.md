# Reference-backed assessment

This optional track is separate from the AI-assisted 180-case audit and its
20-case removed-GO supplement. It must not overwrite their judgments or combine
their samples. The core app, source graph and local review states are unchanged.

## Method selected before reference scoring

The first public reference is **CIViC expert-reviewed Assertions**, rather than
the Evidence Items already imported into the workspace. Assertions summarize
clinical evidence for a complete molecular profile, disease and, when relevant,
therapy context under published interpretation guidelines. They are not another
independent experiment and may reuse the original Evidence Items and studies.

The source qualification uses the
[CIViC knowledge model and SOP](https://pmc.ncbi.nlm.nih.gov/articles/PMC6883603/),
[2022 resource paper](https://doi.org/10.1093/nar/gkac979),
[current Assertion documentation](https://docs.civicdb.org/en/latest/curating/assertions.html)
and [expert editorial policy](https://docs.civicdb.org/en/latest/about/ai-editorial-policies.html).
Public CIViC data are [CC0](https://docs.civicdb.org/en/latest/about/faq.html).
The existing read-only `CivicClient` uses the official GraphQL API; no new
grounder, model, vote rule or clinical inference method is introduced.

Three concepts remain separate:

- **Label independence:** an accepted CIViC expert conclusion was not assigned
  by this project's AI or scoring code.
- **Study independence:** matching conclusions may cite the same primary study
  or incorporate the same Evidence Item. This is recorded, not counted as a new
  replication or an unseen prediction reference.
- **Claim compatibility:** an accepted source-reported observation is not a
  universal clinical interpretation. A different expert conclusion does not
  make the original study report false.

The initial context check retains whole molecular profiles and therapy sets.
It requires literal stable-ID agreement for the molecular profile, disease,
therapy members, therapy interaction, origin and interpretation type. Names,
aliases, disease ancestors, variant subsets and drug substitutions do not
establish a match. Unaccepted, flagged, revised, missing or ambiguous references
remain unknown. Expert Assertion text and guideline context are preserved;
structured-field concordance is not full free-text clinical-context validation.

The original `has_reported_therapy_response` scope therefore supports a bounded
**structured expert-curation concordance** assessment, with clinical-accuracy
claims held unknown when the interpretation scope is not asserted. A separate
clinical-claim task requires its own explicit semantics. Linked Evidence Items
alone are not a positive label: CIViC includes relevant disagreeing evidence in
Assertions as well.

## Probability-sample estimand

Evaluation units are the baseline's qualified assertions with their existing
IDs, not retrospectively deduplicated biological facts. A frozen design groups
them by assertion family and the fixed intervention's retained/pruned
disposition. An assertion is retained if any original evidence edge survives.
Every nonempty stratum has an explicit fixed sample size, selected by simple
random sampling without replacement before labels are inspected. Census
sampling is permitted for a small bounded reference domain.

The estimator is the established stratified design-weighted mean of reference
agreement, disagreement and unknown indicators. It reuses the project's
published-survey variance implementation; no new Bayesian aggregation or
uncertainty model is introduced. Unknown stays in the original denominator.
An incomplete reference does not turn missing records into negatives, and an
agreement rate on the matched subset does not replace the full-denominator
result. The declared reference's scope, rather than the filename or caller's
description, determines what the estimate can mean.

Sources: [Gao et al., PVLDB 2019](https://www.vldb.org/pvldb/vol12/p1679-gao.pdf)
and [standard stratified-SRS/FPC guidance](https://ccsg.isr.umich.edu/chapters/sample-design/appendix-c/).
Design standard errors are conditional on the supplied reference labels and
the fixed sampling frame. They do not quantify reference errors, publication
bias or clinical applicability. No confidence interval for independent
biological truth is supplied. Heterogeneous axes are never pooled into one
whole-graph scientific-accuracy percentage.

## Initial retrieval boundary

The source-only reference plan is saved before retrieving Assertion conclusions.
It selects all accepted predictive Assertions for literal CIViC disease 11
(DOID:9256), with bounded explicit pagination. API-schema inspection precedes
the plan and contains no Assertion outcomes. Source-context coverage may be
inspected before conclusion fields. This is a new reference-backed development
assessment of a preexisting frozen workspace, not a newly blinded prediction
test or an official challenge gold score.

Historical WikiPathways source-model labels, if supplied, belong to a separate
source-attribution axis. Exact native protein xrefs and compatible gene-level
annotations are distinct. Absence from an encoded model is not false biology.

Implementation and command documentation follow the reviewed source contract;
real source captures remain Git-ignored under their own terms.

## Implemented GO reference axis

`go_reference.py` reuses the existing native GOA sidecar verifier and
Biopython 1.88 `Bio.UniProt.GOA.gafiterator`. Preparation executes the author
reader against the complete pinned GAF, compares every selected native row,
then copies the full proof source. Later scoring replays physical GAF lines,
all exact projection candidates and deterministic eligibility without requiring
an optional runtime. It accepts no arbitrary JSONL of AI truth labels.

The claim is **compatibility with a pinned external experimental GO curator
annotation**. It is not the identity of the historical Pharos row or an
independent biological experiment. The exact key is original UniProt accession,
GO ID, evidence code, assigning database and aspect. Positive experimental rows
must have one human taxon, no extension, no With/From context and no distinct
product form. An empty column 17 or literal equality with the complete canonical
subject CURIE is allowed. Different forms, including `-1`, remain distinct.
Strict opposing NOT rows remain unknown. The original polarity, relation and
extensions are never reconstructed. These gates follow the
[GAF 2.2 specification](https://geneontology.org/docs/go-annotation-file-gaf-format-2.2/)
and [GO evidence-code definitions](https://geneontology.org/docs/go-evidence-codes/).
GO data are [CC BY 4.0](https://geneontology.org/docs/go-citation-policy/).

Before preparation, supply a sealed source plan with the module's exact
`POLICY`, the context report's byte/content pins, `native_GAF_sha256` and
`source_url`. The policy is fixed before evaluating its coverage. The supplied
native sidecar must belong to the exact Gold packet. An optional separately
pinned publisher receipt can bind an ordinary HTTPS response to the GAF bytes;
it is not experimental validation or a cryptographic source attestation.

```sh
python -m tools.reference_accuracy.go_reference --help
python -m tools.reference_accuracy.design --help
python -m tools.reference_accuracy.score --help
python -m tools.reference_accuracy.civic_assertions --help
```

Use the pinned optional Biopython runtime only for reference preparation.
`score.py --packet PACKET --reference REFERENCE --reference-sha256 SHA --out OUT`
performs an exact full-frame census. Add `--design FROZEN_DESIGN` to assess a
previously frozen probability sample. A `--dispositions` package also requires
its exact `--disposition-report-sha256`. Structural retention means at least one
original supporting evidence edge survives; it does not mean biological truth.

## November 13 development assessment

The original method note and outcome-free source plans are preserved beside
the ignored source captures. No prior 180/20-case audit is changed or pooled.

The publisher-byte-verified GAF is generated July 28 against the July 26 GO
release. It is **not represented as the latest November release**. The exact
whole-frame census identifies 373 compatible experimental assertions among
4,078 original GO assertions. The other 3,705 GO assertions remain unknown.
All other eight families are outside this reference's scope, leaving 16,607 of
16,980 original assertions unresolved on this axis. The combined GO/Wiki
qualification retains all 373 identified-compatible assertions; all 2,190
removed assertions remain unresolved for this reference. This is preservation
of identified support, not a false-removal or scientific-accuracy estimate.

The native source has 11 eligible experimental NOT rows across nine subjects,
with zero exact original projection matches. No negative labels are invented.
The resolved-only ratio is 100% by the positive reference eligibility rule and
**is not evidence of accuracy**. Present coverage and unknown mass instead.

A separate 220-case, 11-stratum family × disposition SRSWOR demonstration
(20 cases per nonempty stratum; seed 2026111301) estimates compatible-reference
coverage at 2.226% with design SE 1.528 percentage points. The exact census
coverage is 2.197%. This is a check of the reusable estimation pipeline on an
already examined reference, not fresh scientific confirmation. It supplies no
biological confidence interval; homogeneous small strata retain their warning.

The separate CIViC layer preserves two accepted expert clinical Assertions,
including all molecular profile, therapy-set and free-text guideline context.
None exactly matches the 41 original reported-response assertions. In
particular, single-agent panitumumab is not substituted for the graph's
sotorasib-plus-panitumumab combination. Clinical accuracy of the original
reported-observation predicate remains unknown. A source-side matching item
excluded for open revisions is not silently admitted to the graph.

## Reserved CRC cohort support reference

`cornish.py` separately qualifies the published core coding-driver table from
[Cornish et al., Nature 2024](https://doi.org/10.1038/s41586-024-07747-9).
Its 2,023 colorectal adenocarcinoma specimens come from 2,017 UK 100,000 Genomes
Project participants. Six participants have both a primary and metastasis
sample. The reference preserves this distinction and the exact MSS-primary,
MSI-primary, POL-primary and MSS-metastasis calls. TCGA/PCAWG/earlier IntOGen
annotations in the table describe prior knowledge and comparison studies.

This is **published cohort genomic-association support**, not expert gold.
The authors used an IntOGen ensemble weighted using Cancer Gene Census priors,
with rescued known drivers. ST4 supplies 193 putative coding-driver genes but
does not supply native tier labels. Neither a reported Q value nor known-driver
status is used to invent a Tier 1 label. All native cells, Q/Q_CGC values, cohort
labels, prior-driver annotations and formulas are preserved with their source
sheet and row. No inferred functional role, prognosis, drug response or protein
form is attached. Additional location-only, noncoding, structural-variation and
cluster-specific discoveries remain outside this table's scope.

The source context gate inspects every original evidence record, as well as its
assertion. A selected broad MONDO:0005008 node is insufficient when the native
source actually says colon or rectum adenocarcinoma. Whole-CRC discovery does
not establish either narrower anatomic context. Such cases remain unknown,
even when a broader-cohort diagnostic match exists. Exact approved HGNC symbols
and the existing reviewed human UniProt/HGNC/GeneID relation are required.
Aliases, isoforms and gene-to-protein identity are not inferred.

The source archive and article are provided as byte-pinned public EuropePMC
artifacts and copied with the complete frozen registry into an immutable
reference package. Native workbook replay requires optional openpyxl 3.1.5;
ordinary core imports and tests do not. The publication/data are CC BY 4.0.
Patient-level restricted data are not imported. Use:

```sh
python -m tools.reference_accuracy.cornish --help
python -m tools.reference_accuracy.score --reference-kind crc_genomic_cohort --help
```

This axis is scored separately from GO compatibility. Its positive support and
unknown mass must not be pooled into a whole-graph accuracy percentage. The
reference stays outside app graph and learner features. Its inspected outcomes
are not an unseen confirmatory holdout. IntOGen's public compendium was also
inspected as a feasibility comparator; its strong CGI/source overlap prevents
treating a new provider name as independent primary evidence.

The strict context assessment finds published cohort support for 32 of the 100
original disease-association assertions and leaves 68 unknown. A broader
gene-list match would have counted 33, but the extra NRAS record specifically
says rectum adenocarcinoma. That broader match is retained as a diagnostic and
does not become an exact-context support label. The source-faithful GO/Wiki
workspace retains all 32 eligible supported assertions and all 373 separately
identified GO-compatible assertions. Its 298 removed GO assertions remain
unresolved by both references. This is a bounded support-preservation result;
neither reference estimates biological false-removal rate or prediction gain.
