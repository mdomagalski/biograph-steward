# INMC assay and identity follow-up

October 22, 2026. **Assay eligibility is now declared; the context-retrieval inventory is corrected.** The full graph comparison is not frozen or executed. Raw assay codes were decoded only as an unassociated vocabulary. No pair-level outcome labels or author positive-pair records were inspected, no binary labels were derived, and no model was called.

This follows the [input audit](INMC_INPUT_READINESS_20261022.md). The [machine-readable receipt](inmc_readiness_followup_20261022_summary.json) binds the new audit outputs and [assay contract](inmc_assay_contract_20261022.json). Earlier snapshots and registry files remain unchanged.

## Assay ambiguity: bound the task instead of guessing

The INMC paper accepts detection in any assay, but its prose and figure differ in how they qualify negative calls when testing is unsuccessful. The supplement excludes unsuccessful tests from precision calculations. Rechecking the methods, supplement and 110 source/README files in the archived release did not recover definitions of `Not scored` or `freq`, or a full-panel adjudicator. This is a bounded reuse gap, not a conclusion that the study is wrong. [Primary paper](https://doi.org/10.1038/s41467-023-37079-7), [author release](https://zenodo.org/records/7681817).

We have declared a narrower **complete-scored, off-diagonal task** before inspecting pair-level outcomes:

| Source pattern | Treatment |
|---|---|
| Three explicit `Positive`/`Negative` codes, at least one positive | `assay_detected` |
| Three explicit negative codes | `assay_not_detected` under these assays |
| Any autoactivation, not-tested or not-scored code | Excluded from the primary endpoint, including otherwise positive rows |
| Unexpected or empty code | Stop materialization for source review |
| Self-pair | Separate stratum |

`freq` is retained only as opaque source provenance; it cannot drive eligibility, labels, features or weights. Missing current context does not exclude a candidate pair. The original 3,276 nominations, including 2,781 off-diagonal pairs, remain the reporting and masking population. The positive-reference complement never defines negatives.

This is our explicitly limited adaptation, not an exact INMC reproduction. Complete-scored selection may be biased; it does not establish random assay failure. After the full comparison freeze, reconcile eligible detections with the author's positive reference and report all exclusions. Disagreements block performance reporting; do not modify the rule to improve results.

This interpretation follows known assay limitations. HuRI demonstrates complementary detection across assay versions, so mixed positive/negative patterns need not be contradictory. Neither three negative scores nor a reviewed database record proves universal biological noninteraction. Choi et al. use benchmarked assay controls and explicit reference assignments; their experiment-specific thresholds cannot supply missing INMC metadata. [HuRI](https://doi.org/10.1038/s41586-020-2188-x), [Choi et al.](https://doi.org/10.1038/s41467-019-11809-2).

A recent experimental assessment further distinguishes binary contacts from co-complex associations and uses orthogonal assays and source-history checks when evaluating predicted interactions. It supports these limitations, rather than requiring another dataset switch. [Lambourne et al., 2026](https://doi.org/10.1038/s41467-026-70942-x).

## Mapping correction: shared does not mean absent

Our earlier audit counted products usable under a **single, unshared accession** restriction. Its `none` category conflated missing and shared products. The frozen registry was not wrong; our summary was too coarse. UniProt explicitly permits several genes in one entry. [Official gene-name documentation](https://www.uniprot.org/help/gene_name).

| Registry-supported context scope | Original genes | Distinct accessions |
|---|---:|---:|
| Single unshared product | 1,777 | 1,777 |
| All unshared products | 1,781 | 1,785 |
| All confirmed reviewed products, including shared | **1,800** | **1,797** |

Of the 20 exact-HGNC genes previously lacking an unshared product, **19 have reviewed shared products**; only the FXYD6-FXYD2 readthrough has no declared/reviewed product. Four additional Ensembl identifiers lack exact matches in the frozen HGNC index.

The audit now distinguishes `shared_only`, `unconfirmed` and `none`, and writes `context_targets.json`. It deduplicates requests to each accession while retaining all 1,805 original genes and every gene–product link. It does not merge gene nodes, choose an arbitrary isoform, or copy assay labels onto product combinations. Cross-reference conflicts remain excluded from the retrieval inventory. This prepares fuller context retrieval; it does not itself add biological evidence or improve prediction accuracy.

## What the identifier exceptions mean

Official current/GRCh37 Ensembl, HGNC and UniProt responses were saved with hashes under `runs/inmc_mapping_followup_20261022/`. None of the three current unresolved records is a haplotype/patch record. No automatic override was applied.

| Original identifier | Confirmed finding and treatment |
|---|---|
| `ENSG00000268500` | Current protein-coding SIGLEC5 has direct HGNC:10874 and reviewed O15389 links; HGNC's ENSG field still names `ENSG00000105501`, currently annotated as lncRNA. Record the disagreement and contextual link; do not collapse the two original genes. [O15389](https://rest.uniprot.org/uniprotkb/O15389.json) |
| `ENSG00000213204` | Current C6orf165-SLC35A1 readthrough shares a reviewed Q8IYR0 cross-reference with CFAP206's gene. This supports a contextual relation, not replacement by CFAP206. [Q8IYR0](https://rest.uniprot.org/uniprotkb/Q8IYR0.json) |
| `ENSG00000184258` | Historical GRCh37 CDR1 matches HGNC:1798; the identifier is non-current and has no suggested replacement. Current-locus and assay-construct equivalence remain unresolved. [Historical lookup](https://grch37.rest.ensembl.org/lookup/id/ENSG00000184258?content-type=application/json) |
| `ENSG00000264058` | Current novel-transcript record has NMD transcripts, no direct HGNC link and an unreviewed KRT222-related product. It stays outside the reviewed-product contract. [Lookup](https://rest.ensembl.org/lookup/id/ENSG00000264058?content-type=application/json;expand=1) |

These observations are separate from the unchanged frozen-registry inventory. Two current external links are plausible future context additions, but must remain explicit overlays rather than silent canonical replacements. The five genes without frozen-registry context remain benchmark nodes through the common training scaffold.

The four multi-product genes also require preservation of distinct products: CALCA, SEM1, DDIT3 and RBM10 reflect alternative splicing/promoters/initiation or overlapping reading frames. For example, MINAS-60 is not interchangeable with RBM10. Reviewed status alone does not imply experimental protein-existence evidence. [MINAS-60 primary study](https://pmc.ncbi.nlm.nih.gov/articles/PMC9423127/), [SEM1-associated Q6ZVN7 record](https://rest.uniprot.org/uniprotkb/Q6ZVN7.json).

## Next execution boundary

Retrieve consistent Pharos context for the 1,797 frozen-registry accessions, retaining the five context gaps and the documented external-link candidates. Keep raw provider records and coverage caps; do not reuse CRC tissue filters. All original candidate-pair equivalents, including many-to-many product projections and reverse/self-equivalent edges, must be masked in both arms. The validation publication and identifiable derivatives remain blocked. Current-source ancestry is still incomplete, so this remains retrospective assay-outcome recovery.

Before materializing labels or running a biological model, freeze the actual permitted baseline/enrichment, common scaffold, independent development data, paired learner budgets/seeds, scoring and missing-score policy, and uncertainty accounting for shared proteins. The [assay contract](inmc_assay_contract_20261022.json) fixes the current input decision; it is not the full model protocol.

Validation: nine input-audit tests and nine existing registry tests passed. Tests exercise shared entries without collapsing genes, conflicting cross-references, retained unmapped identities and outcome-blind parsing. The real archive rerun confirms 1,800 genes with context and 1,797 accessions. **Brev and AWS were not used; neither is needed for the next retrieval step.**
