# Removed PPI pairs: source audit and biological interpretation

November 11, 2026. **Completed audit; no independent biological superiority established.**

We accounted for all **26,167 distinct pairs removed by either policy** and traced 20 already-consumed assay cases in depth: all eight detections lost by native-score selection, and all twelve usable nondetections removed by Network Enhancement (NE). The original graph, selections, thresholds and reference outcomes were not changed. No model, Brev instance or new outcome set was used.

## What was removed

| State of removed pair | Native score | Network Enhancement |
| --- | ---: | ---: |
| Recorded detection | 8 | 0 |
| Conditional nondetection | 62 | 12 |
| Assay excluded from scoring | 18 | 6 |
| No assay observation in this panel | 16,264 | 16,334 |
| **Total** | **16,352** | **16,352** |

Both policies remove 6,537 common pairs and 9,815 different pairs each. Every removed pair is exact STRINGDB-only; mixed-provider and non-STRING evidence remains protected. **99.89% of NE removals are unassessed** in this panel. Only 12/16,352 removals have usable assay outcomes. The six excluded records do not become negatives.

NE retains 334/334 source-present recorded detections, compared with 326/334 for native selection. However, it also retains 50 more nondetections, and its retained measured detection fraction is 17.09% versus 17.19%. The original conjunction rule for a clear NE advantage remains false. This audit adds traceability and biological interpretation, not a replacement success criterion.

## Exact source and assay trace

The audit checked 24 hash-bound Pharos retrieval chunks, reconciled all 40 reciprocal source views for these 20 pairs, and reproduced every canonical evidence edge ID. Each result was joined to its original published author row, raw assay result, construct IDs and appropriate sequence-confirmation value. Reciprocal views are two representations of the same association, not independent experiments.

The captured Pharos PPI rows contain aggregate STRINGDB scores and target metadata. They do **not** supply the underlying PMID, original experiment identifier or upstream STRING release. Thus the source-row trace is complete at the captured aggregation layer; publication-level STRING lineage and independence from the reference remain unresolved. A numeric Pharos `nid` is not treated as a study identifier.

The published panel and ORF mapping use author data commit `fb05ab3ca2cc0fcaf402bb0df568e95a5158178b`. The saved preprocessing script comes from the separately documented historical commit `ec477f7043195c46ce1787cbd7e09fd407d21b97`; its bytes were freshly verified against the original capture. Its later removal from the repository was documented by the authors. No guessed current-commit code URL is used.

Ten of these 20 cases have a one-to-many author ORF crosswalk, including six of the eight native-lost detections. The audit preserves those alternatives. Matching the published protein pair does not establish construct/sequence equivalence for every accession; role orientation is never inferred from sorted protein endpoints.

### Eight recorded detections removed by native selection

All eight native scores are below the fixed 0.48 cutoff, so these losses do not depend on tie-breaking. NE retains all eight. Five have a known HuRI pair-overlap flag; the other three are not certified independent.

| Pair | Native score | NE score | HuRI pair flag | Original author row |
| --- | ---: | ---: | --- | --- |
| PPP1CB–PPP1R27 | 0.419 | 0.402530 | Yes | [829](https://github.com/CCSB-DFCI/ai-interactome-experimental-assessment/blob/fb05ab3ca2cc0fcaf402bb0df568e95a5158178b/supplementary_tables/Y2H_v1_pairwise_test_AlphaFoldRoseTTAFold_human.tsv#L829) |
| UBE2K–RNF5 | 0.469 | 0.256653 | Yes | [1390](https://github.com/CCSB-DFCI/ai-interactome-experimental-assessment/blob/fb05ab3ca2cc0fcaf402bb0df568e95a5158178b/supplementary_tables/Y2H_v1_pairwise_test_AlphaFoldRoseTTAFold_human.tsv#L1390) |
| NEFL–GFAP | 0.409 | 0.045822 | Yes | [2239](https://github.com/CCSB-DFCI/ai-interactome-experimental-assessment/blob/fb05ab3ca2cc0fcaf402bb0df568e95a5158178b/supplementary_tables/Y2H_v1_pairwise_test_AlphaFoldRoseTTAFold_human.tsv#L2239) |
| UBE2E3–RNF185 | 0.403 | 0.322669 | Yes | [2838](https://github.com/CCSB-DFCI/ai-interactome-experimental-assessment/blob/fb05ab3ca2cc0fcaf402bb0df568e95a5158178b/supplementary_tables/Y2H_v1_pairwise_test_AlphaFoldRoseTTAFold_human.tsv#L2838) |
| GCA–SRI | 0.442 | 0.084036 | No recorded flag | [3130](https://github.com/CCSB-DFCI/ai-interactome-experimental-assessment/blob/fb05ab3ca2cc0fcaf402bb0df568e95a5158178b/supplementary_tables/Y2H_v1_pairwise_test_AlphaFoldRoseTTAFold_human.tsv#L3130) |
| GNAI3–RGS17 | 0.452 | 0.377143 | No recorded flag | [3307](https://github.com/CCSB-DFCI/ai-interactome-experimental-assessment/blob/fb05ab3ca2cc0fcaf402bb0df568e95a5158178b/supplementary_tables/Y2H_v1_pairwise_test_AlphaFoldRoseTTAFold_human.tsv#L3307) |
| CCNO–CDKN1A | 0.458 | 0.258733 | No recorded flag | [3527](https://github.com/CCSB-DFCI/ai-interactome-experimental-assessment/blob/fb05ab3ca2cc0fcaf402bb0df568e95a5158178b/supplementary_tables/Y2H_v1_pairwise_test_AlphaFoldRoseTTAFold_human.tsv#L3527) |
| SH3GLB2–SH3GLB1 | 0.400 | 0.151959 | Yes | [4029](https://github.com/CCSB-DFCI/ai-interactome-experimental-assessment/blob/fb05ab3ca2cc0fcaf402bb0df568e95a5158178b/supplementary_tables/Y2H_v1_pairwise_test_AlphaFoldRoseTTAFold_human.tsv#L4029) |

**CCNO–CDKN1A example.** Source edge `edge:9e007ef6cd1c9d74924a` records native score 0.458. Native selection removes it; NE retains it. Published row 3527 reports a detected assay result. Here the author crosswalk is uniquely mapped: AD/prey construct `100063977 → P22674` (CCNO) and DB/bait construct `3192 → P38936` (CDKN1A). These are explicit mappings, not an inference from endpoint order. This observation does not establish binding in every biological context.

### Twelve usable nondetections removed by NE

Five are also removed by native selection. All twelve retain their original assay conditions and sequence-confirmation trace. None is relabeled a universally false association.

| Pair | Native score | Native decision | Original author row |
| --- | ---: | --- | --- |
| RAD23A–RPL22L1 | 0.418 | Remove | [1047](https://github.com/CCSB-DFCI/ai-interactome-experimental-assessment/blob/fb05ab3ca2cc0fcaf402bb0df568e95a5158178b/supplementary_tables/Y2H_v1_pairwise_test_AlphaFoldRoseTTAFold_human.tsv#L1047) |
| UBE2D2–DTX3L | 0.935 | Retain | [1273](https://github.com/CCSB-DFCI/ai-interactome-experimental-assessment/blob/fb05ab3ca2cc0fcaf402bb0df568e95a5158178b/supplementary_tables/Y2H_v1_pairwise_test_AlphaFoldRoseTTAFold_human.tsv#L1273) |
| TIMP2–BGN | 0.501 | Retain | [1407](https://github.com/CCSB-DFCI/ai-interactome-experimental-assessment/blob/fb05ab3ca2cc0fcaf402bb0df568e95a5158178b/supplementary_tables/Y2H_v1_pairwise_test_AlphaFoldRoseTTAFold_human.tsv#L1407) |
| BCL6–ZBTB16 | 0.515 | Retain | [1591](https://github.com/CCSB-DFCI/ai-interactome-experimental-assessment/blob/fb05ab3ca2cc0fcaf402bb0df568e95a5158178b/supplementary_tables/Y2H_v1_pairwise_test_AlphaFoldRoseTTAFold_human.tsv#L1591) |
| KRT8–VIM | 0.438 | Remove | [1792](https://github.com/CCSB-DFCI/ai-interactome-experimental-assessment/blob/fb05ab3ca2cc0fcaf402bb0df568e95a5158178b/supplementary_tables/Y2H_v1_pairwise_test_AlphaFoldRoseTTAFold_human.tsv#L1792) |
| TPR–CTR9 | 0.500 | Retain | [2132](https://github.com/CCSB-DFCI/ai-interactome-experimental-assessment/blob/fb05ab3ca2cc0fcaf402bb0df568e95a5158178b/supplementary_tables/Y2H_v1_pairwise_test_AlphaFoldRoseTTAFold_human.tsv#L2132) |
| KLRK1–FCGR2B | 0.409 | Remove | [2339](https://github.com/CCSB-DFCI/ai-interactome-experimental-assessment/blob/fb05ab3ca2cc0fcaf402bb0df568e95a5158178b/supplementary_tables/Y2H_v1_pairwise_test_AlphaFoldRoseTTAFold_human.tsv#L2339) |
| PRKACA–DNAJC5 | 0.420 | Remove | [2872](https://github.com/CCSB-DFCI/ai-interactome-experimental-assessment/blob/fb05ab3ca2cc0fcaf402bb0df568e95a5158178b/supplementary_tables/Y2H_v1_pairwise_test_AlphaFoldRoseTTAFold_human.tsv#L2872) |
| UBE2D2–HECW2 | 0.937 | Retain | [3166](https://github.com/CCSB-DFCI/ai-interactome-experimental-assessment/blob/fb05ab3ca2cc0fcaf402bb0df568e95a5158178b/supplementary_tables/Y2H_v1_pairwise_test_AlphaFoldRoseTTAFold_human.tsv#L3166) |
| NDUFB10–MRPL57 | 0.686 | Retain | [3702](https://github.com/CCSB-DFCI/ai-interactome-experimental-assessment/blob/fb05ab3ca2cc0fcaf402bb0df568e95a5158178b/supplementary_tables/Y2H_v1_pairwise_test_AlphaFoldRoseTTAFold_human.tsv#L3702) |
| DCN–FST | 0.431 | Remove | [4202](https://github.com/CCSB-DFCI/ai-interactome-experimental-assessment/blob/fb05ab3ca2cc0fcaf402bb0df568e95a5158178b/supplementary_tables/Y2H_v1_pairwise_test_AlphaFoldRoseTTAFold_human.tsv#L4202) |
| RPS8–NUDC | 0.515 | Retain | [4469](https://github.com/CCSB-DFCI/ai-interactome-experimental-assessment/blob/fb05ab3ca2cc0fcaf402bb0df568e95a5158178b/supplementary_tables/Y2H_v1_pairwise_test_AlphaFoldRoseTTAFold_human.tsv#L4469) |

## A literature-supported caution against false-edge labels

**UBE2D2–DTX3L** has native score 0.935, is retained by native selection and removed by NE; the recorded Y2H-v1 row 1273 is a nondetection. Dearlove et al. experimentally use purified UBE2D2 with DTX3L in ubiquitination reactions and measure E2–ubiquitin discharge. This supports productive biochemical partnership under those conditions. It neither establishes universal cellular binding nor explains the particular Y2H result. The functional association and conditional nondetection can coexist. Therefore this removal cannot be described as removal of a demonstrated biological error. [Primary paper, Fig. 1, supplementary experiments and methods](https://elifesciences.org/articles/98070).

For **UBE2D2–HECW2**, a source trail points to activity-based E3 profiling, but the exact protein/probe record was not verified from the official detail. The reviewed E2–ubiquitin probe method uses engineered covalent trapping; that must not be silently converted into native binding. This case remains unresolved rather than accepted or rejected. [Primary activity-probe study](https://www.nature.com/articles/s41586-018-0026-1).

This is consistent with STRING’s documented distinction between functional association, physical/co-complex proximity and direct contact. Its physical view is not a universal correctness filter. The present Y2H panel cannot label the full functional graph true or false. [Official STRING interpretation](https://en.string-db.org/help/scores/).

## What would demonstrate biological improvement

1. **Fix the claim before a new test.** A defensible first endpoint is better preservation of independently measured physical associations at the same graph size. This is narrower than universal graph accuracy. Keep the existing result and failed superiority gate intact.
2. **Qualify an external study before reading its pair outcomes.** Require exact construct/isoform identities, a known tested population and QC, and a documented source cutoff before that study’s data became available. Audit reuse through databases and calibration. A different database name or an unflagged pair does not establish independence.
3. **Run the unchanged policies and matched comparators once.** Report source absence, exclusions and study/protein dependence along with retained experimental positives. A positive-only reference can assess positive retention at fixed graph size; it cannot assess pruning precision or false-edge removal. A stronger error-removal claim requires context-compatible negative/error evidence, not sampled missing edges or universalized assay nondetections.
4. **Quantify uncertainty for the actual sampling design.** Predefine paired metrics, study/protein grouping and the decision rule. More intervals on this consumed, nominated panel do not make it independent. Repeatedly selecting a successful evaluation also introduces selection bias. [Cawley–Talbot](https://www.jmlr.org/papers/v11/cawley10a.html).

**Public-reference decision.** No immediately qualified independent full-pruning reference was established in this focused review. Lambourne’s human data use Y2H-v1; the orthogonal GPCA/MAPPIT/Y2H-v4 comparisons concern yeast. A newer human peroxisomal iBRET study is a plausible future positive-retention reference, but its complete screen/QC/nondetection matrix was not verified. Its public archive lists final-edge and reference files; its aggregate interactome reuses existing databases. Construct/isoform mapping, chronology and graph coverage must be established first. No pair outcomes from that candidate were opened. [Lambourne methods](https://www.nature.com/articles/s41467-026-70942-x), [peroxisomal study](https://pmc.ncbi.nlm.nih.gov/articles/PMC13324248/), [CC BY 4.0 archive metadata](https://zenodo.org/records/20443272).

**Current decision:** preserve functional source evidence and keep pruning views optional. Do not promote either automatic policy as biologically superior. The completed contribution is an auditable comparison that exposes both detection preservation and potentially misleading removals. The next scientific step is reference qualification, rather than another policy variant tuned to this panel.

**Follow-up completed:** the [external-reference qualification](EXTERNAL_PPI_REFERENCE_QUALIFICATION_20261111.md)
found only one possible peroxisome policy contrast in the current graph. It
identified MAP-IT as a better biological match for the original 99-target CRC
cohort, with public licensed data/code, while documenting the need for a
historical input binding before an independent comparison. No new biological
score was computed.

## Review artifacts

- [All 26,167 removed-pair choices and available assay context, CSV](../../runs/removed_pair_audit_20261111/agent_statistics/removed_union.csv).
- [Same records, JSONL](../../runs/removed_pair_audit_20261111/agent_statistics/removed_union.jsonl).
- [Descriptive recount and source bindings](../../runs/removed_pair_audit_20261111/agent_statistics/statistics.json).
- [Twenty detailed source/assay/construct traces](../../runs/removed_pair_audit_20261111/agent_trace/trace_audit.json).
- [Original fixed comparison](PPI_PRUNING_COMPARISON_20261111.md).

The source-data artifacts remain in ignored local run directories and must be supplied separately from a fresh code clone. This audit did not mutate the hosted workspace or Neptune, change any selection, or create new assay outcomes.
