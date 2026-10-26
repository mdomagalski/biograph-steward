# Uniform Pharos retrieval and source-exposure audit

October 22, 2026 local time; the pull completed October 23 at 01:49 UTC.
**Source preparation is complete for the declared bounded profile. The biological
comparison is not frozen or executed. No assay outcomes or author-positive pairs
were opened; no model or Brev compute was used for this retrieval.**

## What changed

The old CRC graph covered only 43 of the INMC panel's original genes. We now have
a consistent, explicit-accession Pharos pull for the full audited request
inventory, using the existing client and retriever. All chunks use the same
declared interaction-partner population, so chunk boundaries do not remove
cross-chunk links. Expression retrieval explicitly covers all tissue labels,
within the existing per-protein limits.

The retriever preserves raw API responses, unresolved identities, gene–product
mappings, source versions, row counts, caps and original record locators. Resume
checks the inventory, implementation, source and completed-chunk hashes before
continuing. The default disease-workbench retrieval behavior is unchanged.

## Actual coverage

| Item | Result |
|---|---:|
| Original gene identities, all preserved | 1,805 |
| Requested distinct reviewed accessions | 1,797 |
| Exact accessions resolved in Pharos | 1,794 |
| Original genes with resolved Pharos product context | 1,798 |
| Completed chunks | 72 |
| Saved successful chunk response envelopes | 6,195 |
| Retrieved annotation rows, before partner filtering | 1,246,761 |

| Family | Retrieved rows | Retained rows | Coverage within requested scope |
|---|---:|---:|---|
| Pathways | 29,593 | 29,593 | Counts reconcile for all resolved accessions |
| GO | 23,283 | 23,283 | Counts reconcile for all resolved accessions |
| PPI | 203,054 | 23,968 | Confidence threshold 400; retained partners must be in the full request inventory |
| Listed drugs | 238 | 238 | Counts reconcile; these are not verified drug mechanisms |
| Expression | 990,593 | 990,593 | One accession capped; no tissue filter or cross-source numeric normalization |

P62805 (Pharos label HIST1H4A) has 7,386 available expression rows; the declared
limit retained 5,000. Its 2,386 omitted rows remain an explicit cap. Consequently,
`all_requested_families_count_reconciled` is **false**, even though the retrieval
finished. Completion must not be presented as complete Pharos coverage.

P0DTL6, P0DW28 and P0DX52 did not resolve by exact accession. One belongs to a
gene with another resolved product. Seven original genes therefore lack resolved
Pharos context: ENSG00000153684, ENSG00000184258, ENSG00000187954,
ENSG00000213204, ENSG00000255245, ENSG00000264058 and ENSG00000268500.
No synonym substitution or original-node deletion was applied. Fourteen reserved
pairs involve at least one such gene; they are not excluded from evaluation on
that basis.

This profile omits publication discovery, disease annotations, separate GTEx,
non-drug ligand activities, GWAS, LINCS and affiliate datasets. The saved packets
are source-staging artifacts, not disease-workbench snapshots or approved learner
features. In particular, expression row presence is not an assertion of positive
expression or a comparable quantitative scale.

## Source release boundary

Every chunk's before/after metadata reports **Pharos GraphQL `pharos319`**.
This is not an atomic database transaction, and unchanged version metadata alone
cannot prove that no source row changed during retrieval. Counts and raw receipts
provide the bounded audit record.

The [NCATS directory](https://opendata.ncats.nih.gov/public/pharos/) also exposes
400 identity/TDL tables. Those are not a full replacement context graph. The API
catalog returned no GO source-release date. The
[source review](../literature/PHAROS_GO_QUALIFICATION_REUSE_20261022.md) records the
deployment/version uncertainty and why a newer GO release must be distinguished
from a better representation of the same evidence.

## Reserved-pair exposure

The audit reads only the two original identity fields from the pinned INMC
experimental table. It projects all 3,276 reserved unordered pairs to every
mapped product combination, including reciprocal, shared-product and self-pair
equivalents. This produces 3,264 distinct unordered product pairs. Outcomes do
not determine the mask.

**277 reserved off-diagonal gene pairs already appear in the retrieved Pharos
PPI rows**, represented by 276 product pairs and 552 directional source views.
The raw and retained views identify exactly the same exposures. Provider labels
include STRINGDB (550 views), BioPlex (10) and Reactome (4); labels overlap within
rows and are not independent studies.

The audit inventories those exposures; it does **not** yet remove graph edges.
Before training, the graph builder must exclude all reserved and development-pair
equivalents from direct interaction predicates and answer-bearing derived inputs.
The report found no literal occurrence of the validation paper's PMID 36949045
in saved responses. This narrow check does not establish independence from that
study, HuRI, STRING or their derivatives.

All 23,283 retained Pharos GO rows expose GO ID, aspect, term, evidence/ECO and
assigning source. None has a reference, negation or relation field in this API
projection. That absence is an information limitation, not evidence that Pharos
contains incorrect positive annotations. Cross-release matching cannot establish
the identity of the underlying GO annotation.

## Qualified GO source comparison

The pinned GOA release and official Biopython 1.88 GAF parser yielded 131,860
annotations across 1,790 inventory accessions. Matching was restricted to the
1,794 accessions resolved in this exact completed Pharos retrieval. The join
checks the inventory, plan, source version, chunk manifest and pair-mask report
bindings before reading annotations.

| Compatible projection group | Groups | Interpretation |
|---|---:|---|
| One record from each source | 5,817 | Compatible identifiers, evidence code and assigning source; underlying record identity remains unverified |
| Multiple records in a group | 798 | A flat projected tuple can combine distinct qualified records |
| GOA only | 35,865 | May reflect updates or source/filter differences |
| Pharos only | 16,668 | May reflect updates or source/filter differences |

The literal exposure scan flags 955 With/From rows spanning 348 product pairs
and 352 original candidates, and 10 extension rows spanning eight product pairs
and nine candidates. With/From hits occur in IBA, IPI and IGI records; extension
hits also occur in IDA, IMP and EXP. **These fields have different biological
roles. A matching identifier is not automatically a physical-interaction claim
or proof of leakage.** The scan provides review/exclusion candidates and cannot
certify a complete semantic mask.

This rules out treating a blind GOA merge as independent new evidence. A newer
source release, additional record qualifications and additional graph structure
must be evaluated as distinct interventions. No GOA records were promoted into
the workbench or learner graph by this audit.

## Learner integration checked separately

The [PyKEEN context smoke](PYKEEN_CONTEXT_SMOKE_20261022.md) exercised the native
R-GCN with different context adjacency and identical positive supervision,
reserved-pair negative filtering and fixed-pair scoring. It used only invented
data on CPU. This verifies library integration, not biomedical performance,
GPU readiness or a final scientific protocol.

## Reproduction and receipts

Validation: the core suite ran 377 tests: **375 passed, two optional integrations
skipped** (NeMo and the separately installed Biopython parser). The isolated GO
environment passed all **23 GO audit tests**, including the actual inventory-audit
producer/consumer contract. The completed real Pharos audit reconciled source
hashes, manifests, target resolution, coverage and raw/retained interaction rows;
the real GAF join passed its provenance checks. These are engineering checks,
not accuracy or usability measurements.

Local raw receipts are under `runs/inmc_pharos_uniform_20261022/` and
`runs/inmc_go_feasibility_20261022/pharos_join/`, and are ignored by Git. The
[compact tracked summary](inmc_pharos_uniform_20261022_summary.json) links their hashes; it does not redistribute
the source data or grant reuse rights. Source catalog license fields were not
populated, so redistribution terms still need checking before packaging real
examples.

```sh
python3 scripts/retrieve_pharos_inventory.py \
  --inventory runs/inmc_mapping_followup_20261022/input_audit_v2/context_targets.json \
  --output-dir runs/inmc_pharos_uniform_20261022/retrieval
python3 scripts/audit_pharos_inventory.py \
  --retrieval-dir runs/inmc_pharos_uniform_20261022/retrieval \
  --archive runs/link_prediction_reuse_audit_20261022/inmc_release_v1.zip \
  --output-dir runs/inmc_pharos_uniform_20261022/audit
```

Use new output directories for a new pull/audit. A completed retrieval can be
verified with `--resume` without additional HTTP calls if its inputs and retrieval
implementation are unchanged. Earlier packets must not be resealed after code or
source changes.

The completed audits select [GO hierarchy augmentation](../literature/PHAROS_GO_QUALIFICATION_REUSE_20261022.md#selected-next-comparison-ontology-structure-with-unchanged-annotations)
as the next bounded intervention. The same restricted Pharos annotation substrate
is used in both arms; current-GOA protein annotations are not added. The next gate
is to build and audit that graph projection, source-lineage exclusions, three-hop
message-passing behavior and matched controls. Freeze these together with the
learner budget and assay contract before materializing labels. Only the subsequent
paired evaluation can measure predictive benefit. It will remain a retrospective
assay-specific test, not clinical validation or independent temporal prediction.
