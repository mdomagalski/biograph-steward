# Native GO quality control and remaining scientific limits

The native GO workflow is now executable with the published implementations,
including actual taxon reasoning. On **15,888 preserved native annotations**,
the official checks produce **nine relation repairs and 49 alternative-ID
extension normalizations**, with **zero detected taxon violations**. A separate
extension investigation finds a concrete citation/context discrepancy in four
records. These are source-quality advances, not a whole-graph accuracy score
or a validated automatic biological pruning gain.

This follows the [earlier GO assessment](SCIENTIFIC_GAPS_20261112.md), whose
separate ontology-currentness graph and historical results remain unchanged.
The [aggregate receipt](scientific_limit_resolution_20261112_summary.json)
binds the executed outputs, source versions and implementation reviews.

## Completed work

| Gap | Executed resolution | Boundary |
|---|---|---|
| Unexplained historical/native GO mismatches | Of 2,930 unmatched historical records, 1,351 have the same exact protein–GO pair with other projection fields differing; 1,579 have no such native pair. | The strict five-field compatibility rule is unchanged. Neither diagnosis supplies missing historical source identity. |
| Current native context unavailable for direct inspection | A read-only command verifies the sidecar/GAF bindings and returns every native record for an exact preserved protein and optional GO ID. | Current references, NOT, forms and context belong to those native records; none is copied into an old Pharos row. |
| Native relation/reference checks unexecuted | Actual ontobio 2.9.12 parser lifecycle, GORULE22 and GORULE61 run with pinned inputs. | Selected published checks, not full GO-pipeline conformance or independent experimental validation. |
| Taxon constraints lack inference/processing proof | Actual GAFeRence v0.5 runs on Brev CPU with a matched ontology, followed by released-parser coverage verification and actual GORULE13 execution. | NOT exemptions, sparse inference output and non-taxon extension problems remain explicit. |
| Extension problems uninterpreted | All ten keys are mapped to native records and checked with official rule58 and ontology labels; one key is traced to its cited paper. | Rule58's external-import context is not silently turned into a general filtering policy. No automatic cell-ID replacement or graph pruning is applied. |

## Source/runtime and observed results

The original CRC packet contains 99 target subjects, 9,865 nodes and 16,985
evidence edges. The native sidecar preserves all 15,888 GAF records for those
99 exact subjects, including 23 NOT records and 1,236 extension-bearing records.
Its GAF and GO ontology share the native **2026-07-26** version; the official
release was advertised as **2026-08-05** when checked. These dates are preserved
rather than relabelled as November data. Product-form fields are populated on
all records; that does not mean every record describes a distinct isoform.

The optional QC runtime pins **ontobio 2.9.12** and **prefixcommons 0.1.12**.
The application remains dependency-free. The actual parser's lifecycle handling
covers main GO, With/From and extension IDs; the selected rule methods run
without rewritten biological logic. Every original row and changed-column
inventory is retained beside the normalized derivative.

- GORULE61 repairs nine `part_of` relations to `located_in`.
- The parser normalizes 49 extension alternative IDs: 46 occurrences of
  GO:0043222 → GO:0008278 and three of GO:0030914 → GO:0000124. These are
  alternative-ID normalizations, not 49 obsolete-term removals.
- GORULE22 finds no matches against the supplied retraction table. That table
  is dated June 10, 2026; a pass is relative to its coverage and date.
- GORULE13 processes 15,865 non-NOT records; 23 NOT records are explicit
  exemptions. It reports no taxon warnings or exclusions. All 15,888 records
  remain in the normalized output.

The actual GAFeRence delta contains 324 semantic keys: 314 satisfiable keys with
additional inferences and ten extension-unsatisfiable keys. **None has a taxon
problem.** The ten keys apply to 13 source annotations; they are not ten taxon
violations or ten independently disproved biological relationships. Additional
inferred terms are not added to the app graph.

GAFeRence deliberately omits ordinary satisfiable/no-inference keys. A separate
bridge calls its unmodified released parser and reproduces every non-NOT
prepared annotation's semantic keys before omitted output can be interpreted.
Three declared semantic controls verify valid human binding, valid plant
photosynthesis and invalid human photosynthesis. No fabricated passing rows
are inserted into the sparse table.

Version-specific integration checks also found that ontobio stores extension
query keys as typed CURIEs while the inference loader uses full IRIs. The
read-only adapter uses existing official relation/prefix conversions during
actual rule lookup, with exact released-parser equality and unknown-conversion
rejection. It preserves the annotations, inference entries and rule bodies.
The released command accepts repeated `--contexts` arguments; its misleading
comma metavar does not require a custom command parser. Failed pre-release
attempts and their diagnostics remain preserved separately.

## Primary-source qualification of extension findings

The actual [GORULE58](https://github.com/geneontology/go-site/blob/master/metadata/rules/gorule-0000058.md)
is scoped to external import into Noctua. As a diagnostic on copies, it warns
and removes a conjunction for eight of the ten unsatisfiable keys, affecting
eight annotations. The remaining two keys affect five annotations and pass
that whitelist check despite being unsatisfiable in the pinned reasoner.
Whitelist validity and ontology satisfiability are different checks.

One remaining key includes `GO:0070062` with `part_of(CL:0000639)`. Four native
annotations—NRAS/P01111, PRKCB/P05771, TYK2/P29597 and BAX/Q07812—cite
PMID:20458337. The pinned ontology labels CL:0000639 as a basophil cell of the
pituitary pars distalis. In contrast, the cited paper's Methods, page 854,
describes exosomes isolated from an EBV-transformed human RN **B-cell** line.
The author-uploaded published article was read directly and checked against
the citation metadata. [Primary article, Methods](https://www.researchgate.net/publication/44588150_MHC_class_II-associated_proteins_in_B-cell_exosomes_and_potential_functional_implications_for_exosome_biogenesis).

This supports a bounded **cell-context discrepancy**. The proposal is to
withhold that exact extension from downstream inference pending curator review,
while retaining its original row and base protein–exosome association. The
proposal is not applied or accepted. No replacement cell ID is guessed;
changing the cell alone would not establish the correct formal relation.
The protein identifications themselves were not re-adjudicated against all
supplemental peptide tables. This is AI-assisted primary-source assessment,
not an independent expert label or population accuracy estimate. The four
records share one study and are not four independent experimental failures.

## What remains unresolved, and the smallest valid next step

**Historical identity:** the old Pharos projection omits release-specific native
row identifiers and qualifiers. Current exact-pair diagnostics cannot restore
those missing facts. The new current-source inspector avoids needing that
restoration for current GO questions; historical claims remain historical.

**Scientific accuracy:** a complete whole-graph gold file is not required.
Published [probability-sample KG evaluation](https://www.vldb.org/pvldb/vol12/p1679-gao.pdf)
and [interval-estimation methods](https://doi.org/10.1145/3725279) can reduce
review effort, but require qualified correctness judgments. Freeze the claim
unit and probability sample, preserve inclusion weights and indeterminate
outcomes, and obtain independent review in the sampled biological domains.
The existing source-bound Gold/reference interface can preserve those returned
judgments. No such accuracy estimator or new sampling protocol is claimed here.

A `has_go_annotation` record asserts that an annotation exists, including its
NOT/context; it must not be scored as an unqualified positive function claim.
ClinGen monogenic validity labels likewise cannot directly refute the current
generic CRC disease-association edges. A second database name does not prove
source independence, and unvalidated LLM agreement cannot replace independent
judgments. More compute does not close that evidence gap.

## Reproduction and retained artifacts

See [native GO inspection and QC commands](../GO_NATIVE_QUALITY.md) and the
[optional runner](../../tools/go_qualification/README.md). Executed local outputs:

- `runs/crc_go_context_qualification_v3_20261112/`: immutable native sidecar
  plus mismatch diagnostics; native source rows are unchanged from v2.
- `runs/braf_current_go_inspection_20261112/`: three source annotations for
  BRAF/GO:0004674, returned separately with their own references/context.
- `runs/go_pipeline_reuse_20261112/native_qc_sparse_v3/`: final official QC,
  normalized GAF, original rows, actual rule calls and coverage report.
- `runs/go_taxon_reasoning_20261112/brev/outputs/`: reasoner/control outputs
  and separate actual released-parser coverage, with completed execution receipts.
- `runs/go_extension_triage_20261112/`: ten-key diagnostic dossiers, pinned
  ontology labels and primary-source context assessment.
- `runs/go_remaining_limits_20261112/`: historical mismatch analysis and
  separate implementation/output verification.

Core, actual Biopython and optional real-package QC controls are tested.
The Brev run used CPU only; no hosted language-model inference was invoked.
The original/default graph, historical results and human review states are
unchanged. Source normalization is a separate artifact. Native data retain
provider terms; the MIT software license does not clear full-graph redistribution.
