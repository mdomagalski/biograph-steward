# Kinase coverage, source grounding and assay gaps

The follow-up identified specific limits behind the consumed kinase comparison.
It also found five citation/entity mismatches in a proposed SIGNOR expansion.
That expansion is **on HOLD**. The completed comparison, its null pruning result,
the current CRC workspace and its review states remain unchanged.

The useful implementation is a read-only
[source identity audit](../../tools/kinase_utility/source_identity.py). It
separates a valid current protein identifier from evidence that a cited paper
studied that protein. It does not automatically change sources or activity inputs.

## What caused the 38 missing scores

The exact source-site and measurement trace covers 38 condition–target cases
across 14 genes:

| Finding | Cases |
| --- | ---: |
| No raw measurement row at a qualified prior site's same literal coordinate | 30 |
| A qualified matching row exists, but its supplied value is missing | 8 |
| Finite same-site measurement rejected by identity filtering | 0 |
| Finite observation lost through duplicate aggregation | 0 |

This audit does not establish that every legacy coordinate, isoform or family
projection is resolved. It establishes that the missing scores were not caused
by dropping finite observations at the exact qualified sites. The upstream
author preprocessing changes zero to missing; a supplied missing value cannot
identify whether that specific value was originally zero or unquantified.

Only **122 of 12,101 qualified measured sites are tyrosines (1.0%)**. Twenty
missing cases involve ten kinases with predominantly tyrosine-site priors.
Ten involve PIK3CD/PIK3CG, where protein-phosphosite measurements do not directly
measure lipid-kinase activity. PIK3CG also has reported protein-kinase activity,
so its protein-site evidence must not be categorically discarded. Eight cases
involve BRAF/MAPK12. These are different coverage and interpretation problems;
adding annotations cannot supply an unmeasured phosphosite.

The [2025 primary benchmark](https://doi.org/10.1038/s41467-025-59779-y)
likewise discusses scarce phosphotyrosine measurements and prior-library
choice. The published
[PIK3CG biochemical study](https://doi.org/10.1042/bj3240489) supports keeping
its lipid and protein activities distinct.

## Valid identifiers can still be grounded incorrectly

The source identity audit found that 20 proteins previously excluded by a
gene-only rule have explicit current protein/gene cross-reference support.
Other products of a gene or another gene's historical alias do not invalidate
an explicitly supplied primary protein. Missing secondary GeneID corroboration
is recorded as unavailable; conflicting or nonunique identifiers remain distinct.

This is **identifier-context qualification only**. A source-only projection
contained 392 compatible contexts and 6,800 binary links, but a focused primary
review found the following mismatches before activation:

| Source records | Supplied identity | Entity in the citation | Disposition |
| --- | --- | --- | --- |
| SIGNOR-114289, -171005, -277178, -277179 | P26927: MST1, hepatocyte growth factor-like protein | Mammalian STE20-like kinase context, including Mst1/STK4 and Mst2 | Source-grounding review required |
| SIGNOR-250265 | Q15118: mitochondrial PDK1 | Phosphoinositide-dependent kinase PDPK1/O15530 | Source-grounding review required |

The [MST1/Sirt1 paper](https://doi.org/10.1074/jbc.M110.182543),
[Mst1/Mst2 paper](https://doi.org/10.1038/ni.3268),
[MST phosphorylation paper](https://doi.org/10.1074/jbc.M108138200) and
[PDPK1/PRK paper](https://doi.org/10.1074/jbc.275.15.11064) concern those kinase
contexts. This does not independently validate every substrate-site or direct
catalysis assertion: one quoted H2B statement is background, and the Mst1/Mst2
paper's direct PKC assay uses Mst2. Automatic substitution with STK4 would
therefore overstate what was verified.

Four flagged assertions share a citation/site with kinase-named records already
in the old prior. This is an evidence-reuse warning, not proof of identical
assay contexts or four independent experiments. Neither global MST1 nor global
PDK1 renaming is justified. A separate PDK1/PDHA2 record has a context consistent
with mitochondrial PDK1.

The [version-bound alert list](signor_grounding_alerts_20261112.json) preserves
record IDs, complete-row hashes, citations and review limits without applying
corrections. Exact intersection with the current 290-record CRC SIGNOR
publication is **0/5**; that does not validate the remaining records.

The proposed driver activation was withdrawn before new measurement preparation
or inference. Its patch and candidate remain preserved outside tracked active
code. The new audit helper explicitly returns
`citation_grounding_status="not_assessed"`; its identifier checks cannot serve
as biological approval.

## Assay and reference context need separate qualification

Two excluded MAPK12/Tau records appeared capable of adding measured sites.
The [original experiment](https://doi.org/10.1016/S0014-5793(97)00483-3)
used rat SAPK3 and human Tau441 in a reconstituted assay. Its T231 antibody
signal appeared with added dextran sulphate. The source's blank cofactor field
does not establish absence of that condition. No automatic transfer to a human
cell reaction or canonical isoform/site was made.

The four MAPK12 expected-target labels remain gene-identity-qualified under
the frozen benchmark rules. Pharmacological isoform, dose and cell-context
support remains unverified. The
[Hijazi accepted manuscript](https://qmro.qmul.ac.uk/xmlui/bitstream/123456789/63605/9/Rodriguez%20Reconstructing%20kinase%20network%202020%20Accepted.pdf)
reports a study-wide 1–10 micromolar, one-hour phosphoproteomic treatment range.
The separate 200 nM selectivity profile is a different experiment. The released
PH-797804 profile and MAPK12 label differ, but weak micromolar affinity and
unverified compound-specific cell doses prevent declaring that label false.
TAK-715 also requires primary selectivity and cell-context qualification.
No labels were replaced, excluded or rescored.

## Established resources and what they can add

| Resource | Appropriate role | Verified limit |
| --- | --- | --- |
| OmniPath enzyme–substrate service | Discover source coverage and trace provenance | The inspected client's `strict_evidences` reconstruction applies to interactions, not enzyme–substrate rows. The checked enzyme–substrate header omitted assay context and requested taxonomy fields. |
| PTMsigDB | Typed kinase, perturbation, pathway or disease signatures | These are different evidence types; bulk import would also reuse PSP origins. |
| iKiP-DB | A separate gene-level in-vitro signature source | The private source-table audit found potential measured-site matches. Exact assayed accessions/constructs remain unknown; none was imported. |
| INDRA/Gilda | Existing source normalization and contextual grounding candidates | These can assist triage; a candidate grounding does not establish an experiment or catalytic claim. |

The pinned [INDRA SIGNOR processor](https://github.com/sorgerlab/indra/blob/7ae3337dcae88baed918d7ae6af2ddc21f9946fa/indra/sources/signor/processor.py)
already contains version-specific source fixes. No MST1/STK4 or PDK1/PDPK1
correction was found in the checked path. It preserves the supplied accessions;
that path does not use sentence/PMID context. The
[Gilda context API](https://gilda.readthedocs.io/en/latest/modules/index.html)
supports candidate disambiguation when a model exists. Model availability and
accuracy for these two strings were not tested; no new grounder was built.

The [iKiP primary study](https://doi.org/10.1021/acs.jproteome.2c00198)
reprocesses the [Sugiyama parent experiment](https://doi.org/10.1038/s41598-019-46385-4).
The official source-table metadata specifies **CC BY-NC 4.0**, separately from
the tool's MIT code. Its raw workbook and row-derived audit remain private and
Git-ignored. Author metadata connects the relevant named sets to parent inputs,
supporting a gene-level in-vitro interpretation. The exact official parent S5
download returned a proof-of-work HTML page, so its proposed construct/catalog
metadata was not inspected. No access workaround was used.

Pharos already has a PSP-linked Harmonizome connection. Additional site,
citation and assay detail can enrich its representation while adding no new
independent study. A provider name, a source-library difference or a row count
does not establish Pharos-wide absence or novelty. The same Sugiyama experiment
must not be counted again through iKiP and PTMsigDB.

## What is retained and what comes next

The source identity audit and its invented tests are retained. Independent
review reproduced the source counts and checked the five flags. The original
driver, measurement mapper, statistics, graph and completed
[comparison](SCIENTIFIC_ACCURACY_ROUND2_20261112.md) remain unchanged.
No new activity inference, biological score, graph acceptance or GPU work was
performed.

The next focused work is to resolve source grounding and qualify the assay
eligibility of a separate in-vitro signature layer. A new independent evaluation
boundary is needed before claiming biological improvement. The consumed Hijazi
study can support development diagnostics only.

See the [aggregate audit](kinase_coverage_gaps_20261112_summary.json). Local full
case traces, candidate HOLD notices and primary-source receipts are preserved
under `runs/kinase_coverage_investigation_20261112/` and are not bundled into the
public source tree.
