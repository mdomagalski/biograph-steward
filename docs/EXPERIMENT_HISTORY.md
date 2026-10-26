# Closed experiments and recovery

The active branch contains the current evidence workbench and INMC preparation tools. Completed or superseded research implementations, their protocols and dated reports were removed from the active tree after preserving the full pre-consolidation source snapshot.

**Archive branch:** `codex/archive-pre-consolidation-20261022`

**Immutable archive commit:** `602681bc82417720e7a465bd19db7a7500c88f38`

**Status:** local branch only; not pushed to GitHub as part of this consolidation.

This is an archive of tracked and non-ignored source files, including the uncommitted research work present before cleanup. It does **not** back up ignored `runs/`, downloaded datasets, model weights, environments or credentials. Those local artifacts remain in place and require a separate backup policy. No experiment packet was relabeled, resealed or deleted by this consolidation.

## Outcome ledger

Paths in this table are relative to the archive commit, not files on the active branch. Successful component replications remain historical too: archiving does not mean every approach failed.

| Completed track | Recorded result and decision | Archived report |
|---|---|---|
| Planner entity and tool selection | Early all-abstention behavior was repaired. The later v4 regression matched 26/32 exposed scope references, with zero wrong-scope queries and six unnecessary declines. Bounded planning remains in the product; old study runners and reference packets are archived. | `docs/evaluations/SCOPED_TARGETS_V4_20261020.md` |
| CPTAC/DepMap growth ranking | Adding the CPTAC summary gave Spearman 0.2605 versus restricted Pharos 0.3810; the paired interval included zero. No primary incremental gain was demonstrated. This was ridge growth ranking, not KG link prediction. | `docs/evaluations/CRC_GROWTH_COMPARISON_20261020.md` |
| Fresh pathway-only growth comparison | On 256 reserved genes, pathway-only scored 0.2635 versus full restricted Pharos 0.2607; the paired interval included zero. The primary improvement rule failed. | `docs/evaluations/CRC_FRESH_COMPARISON_20261020.md` |
| Source/context verifiers and pruning previews | The context verifier produced 0/18 valid responses. Withholding every case was invalid-output abstention, not successful reasoning. Automatic model acceptance/pruning was not justified. | `docs/evaluations/CRC_CONTEXT_VERIFICATION_20261020.md` |
| Deterministic source-pattern extraction | The fixed compiler emitted no records on ten new abstracts: 0/14 broad reference coverage. Narrow development examples did not establish general extraction coverage. | `docs/evaluations/SOURCE_FACTS_UNSEEN_20261020.md` |
| CT-Corpus guided/nested extraction | Nested output passed schema checks on 6/6 responses, but both recipes recovered 0/22 complete associations; exact quotes could still be attached to the wrong arm. The training gate failed. | `docs/evaluations/CT_NESTED_EXTRACTION_TRAINING_20261020.md` |
| Published cancer-claim verifier comparison | BioMedBERT matched 29/45 strict-majority references versus Nemotron 16/45. False support remained too frequent for automatic graph decisions. Reference amendments and exposure qualifications are preserved. | `docs/evaluations/CANCER_CLAIM_DEVELOPMENT_20261021.md` |
| Published NLI4CT verifier replication | Task-trained FLAN-T5-XL matched 383/500 labels versus transferred BioMedBERT 195/500, but produced 70 false supports. This was public-benchmark replication, not independent validation of Pharos claims. | `docs/evaluations/NLI4CT_VERIFIER_COMPARISON_20261021.md` |
| Trial-context prompt adaptation | Accuracy changed from 106/128 to 103/128 exposed cases; the prespecified improvement gate failed. The published baseline was not replaced. | `docs/evaluations/NLI4CT_CONTEXT_PILOT_20261021.md` |
| Equal-source CIViC context QA | Full context matched 18/24 provisional options versus sources alone 15/24, while explanations and support remained unreliable. This small development agreement gain was not scientific accuracy or graph improvement. | `docs/evaluations/CONTEXT_QA_PROSPECTIVE_RESULT_20261021.md` |
| Topic-field ablation | Removing the topic field left those totals unchanged at 15/24 and 18/24. The prompt-variation sequence was closed; source-traceable product features were retained. | `docs/evaluations/CONTEXT_QA_TOPIC_ABLATION_RESULT_20261021.md` |

The archive also retains source-curation audits, all intermediate failures, diagnostic protocols, exact model/runtime receipts, tests and result summaries. The current [literature knowledge base](LITERATURE_REVIEW.md) and useful Pharos construction reviews remain on the active branch because their source findings inform current work.

## Exposure boundaries survive cleanup

- The original growth development panel and later 256-gene reserve have been consumed. Their 512-gene union cannot be relabeled as an unseen test.
- The planner's 24 pilot and subsequent 32 scope questions are exposed development/regression material.
- The selected 47 cancer-claim pairs have been evaluated; the 45-case strict-majority subset and 47-case plurality amendment are separate recorded analyses, not new tests.
- NLI4CT public test reuse, checkpoint training/development overlap and the 128-case context diagnostic remain disclosed in their reports.
- CIViC context-QA references are provisional AI-authored/reviewed development judgments, with disclosed trial overlap; exact citation binding is not an expert support label.
- The CT-Corpus experiments inspected training material. Their 33 validation and 41 test publications remained reserved at this checkpoint. Moving the implementation does not authorize opening those labels.
- The original INMC audit inspected identities/code vocabulary only. The subsequent [frozen restricted Pharos/GO comparison](evaluations/INMC_COMPARISON_20261023.md) opened the assay and author-positive reference on **October 23, 2026 at 15:10:21 UTC**, after completing all fixed predictions. The panel is now consumed: 1,751 primary pairs were scored, with no consistent hierarchy benefit demonstrated. It cannot become an unseen test again after model, source or qualification tuning. This new reusable evaluation pipeline is on the active branch, not in the older archive commit above.

## Current reference exposure history

The October 23 [external human PPI reference audit](evaluations/LAMBOURNE_REFERENCE_AUDIT_20261023.md)
read Lambourne nomination metadata and identifiers, plus author preprocessing
source. It downloaded opaque outcome-containing files but **did not decode
pair-level assay results**, determine assay eligibility, train or score models.
At that point the 3,222 published nominations were not a frozen test cohort. Their overlaps
with consumed INMC pairs and known training/source pairs are recorded; changing
reference publications does not reset those exposure boundaries.

The subsequent [focused PPI lookup](evaluations/LAMBOURNE_PHAROS_LOOKUP_20261023.md)
queried the complete author accession inventory and found 2,325 represented
pairs. It preserved the prior snapshots and outcome boundary. No new assay
eligibility selection, graph training or scoring occurred.

The October 25 [frozen assay corroboration](evaluations/LAMBOURNE_CORROBORATION_20261025.md)
subsequently opened outcomes at **October 26, 2026 00:28:58 UTC** (October 25
locally). All 3,222 nomination statuses reconciled against the raw author
export. Of 2,676 assay-eligible pairs, 2,674 had a resolved Pharos comparator:
334/1,966 represented pairs were detected versus 42/708 resolved no-match
pairs. Without either prespecified HuRI/INMC flag the fractions were 74/1,619
and 16/650. All 546 assay exclusions and two unresolved pairs remain visible.
This is retrospective assay corroboration, not independent Pharos accuracy
or Steward improvement. **The panel is now consumed**; changes developed
using it require a separate evaluation reference. No prior result or failure
was overwritten. This implementation is on the active branch, not in the
older archive commit.

## Reopening an archived file

Read a report without changing the active checkout:

```sh
git show 602681bc82417720e7a465bd19db7a7500c88f38:docs/evaluations/CRC_FRESH_COMPARISON_20261020.md
git ls-tree -r --name-only 602681bc82417720e7a465bd19db7a7500c88f38
```

For execution, use a separate checkout of the archive commit so its original source paths and bytes remain together:

```sh
git worktree add --detach ../biograph-steward-history \
  602681bc82417720e7a465bd19db7a7500c88f38
```

Then follow the archived protocol and supply the absolute path to its existing packet. For example, from that separate checkout:

```sh
python3 scripts/run_context_qa_topic_ablation.py verify \
  --experiment /Users/42573/biograph-steward-pharos/runs/civic_context_qa_topic_ablation_20261021/experiment
```

The five saved QA packet loaders passed before consolidation and again from an isolated extraction of the archive commit, using the original absolute packet paths. Their source inventories remain satisfied by the archived source bytes and saved source copies. A file-integrity check is not a new scientific result, and exact replay can require the original dependencies or model runtime. Do not weaken a loader or rewrite a historical receipt to make old work pass against current source.

Git's existing [worktree](https://git-scm.com/docs/git-worktree) and [show](https://git-scm.com/docs/git-show) commands provide this separation; no custom archive framework or second copy of historical executable code is maintained on `main`.
