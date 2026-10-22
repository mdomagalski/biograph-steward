# Current Pharos representation audit — October 20, 2026

This read-only audit distinguishes retrieved source records, preserved raw responses, normalized assertions and predictor features. It adds no retrieval, model calls, scientific labels or implementation changes. It updates the scope accounting in the [October 14 coverage audit](../PHAROS_COVERAGE_AUDIT.md); that earlier 99-protein audit must not be reported as the current 512-gene retrieval.

## Exact saved scope

The inspected packet is `runs/crc_fresh_comparison_20261020/retrieval_serial/`, principally `snapshot.json`, `retrieval_coverage.json`, `gene_coverage.json`, `feature_policy.json`, `feature_candidates.json` and `feature_exclusions.json`. Its snapshot SHA-256 is `dae2e60819473882b09b67256826de24a451f5f3b0a24b28815b7018beb3eec4`.

The fixed panel contains **512 genes and 513 requested protein accessions**. Pharos resolved **512 products**; accession **C0HLS1** was not found. Every gene retained at least one resolved product; 511 genes had all requested products resolved. There was no symbol-based replacement. The pull used **1,441 fresh successful response envelopes**, zero cached envelopes, and reported database version **pharos319** before and after. Count reconciliation is not an atomic upstream snapshot guarantee.

| Family | Scanned rows | Retained rows | Observed status |
|---|---:|---:|---|
| Pathways | 12,421 | 12,421 | Complete for all 512 resolved products |
| GO | 8,403 | 8,403 | Complete for all 512 |
| PPI | 81,787 | 3,950 | Complete bounded neighbor lists; selected-cohort partners retained |
| Expression | 316,438 | 5,284 | Complete scans; colon/rectum label matches retained |
| Drugs | 0 | 0 | Not requested; 116 protein-linked listings inventoried |
| Publications | 0 | 0 | Not requested; 46,897 protein-linked records inventoried |

Counts are source rows, not distinct studies, drugs or publications. PPI retrieval uses confidence filter 400. Expression scope is local, case-insensitive whole-word **colon OR rectum**, not an inferred disease-to-tissue ontology mapping. Successful raw response envelopes retain the 77,837 out-of-cohort PPI rows and 311,154 out-of-scope expression rows.

This is `biograph-steward.explicit-pharos-panel.v1`, produced by the [matched-panel adapter](../EXPERIMENT_HISTORY.md#reopening-an-archived-file "Archive file: biograph_steward/matched_panel.py"). It is separate from the ordinary disease workbench snapshot. The general scoped application can request drugs and publication discovery; their omission here is an experimental-profile choice, not evidence of absence from Pharos. See the [fresh comparison](../EXPERIMENT_HISTORY.md#reopening-an-archived-file "Archive file: docs/evaluations/CRC_FRESH_COMPARISON_20261020.md").

## Preserved information and missing semantics

The [retrieval field contract](../../biograph_steward/retrieval.py) makes the boundary explicit:

- **Identifiers:** requested UniProt accessions are checked against returned IDs. Reactome/WikiPathways stable IDs survive in raw records. Of 12,421 pathway rows, **1,190 lack `sourceID`**, all from PathwayCommons or UniProt; local pathway IDs avoid unsafe name-based merging.
- **GO:** ID, term, aspect, evidence code, ECO code and assigning source survive. The retrieved fields lack relation, negation, annotation extensions and claim-level study references. More annotation rows would not recover these qualifications.
- **PPI:** original source bundles, partner IDs and properties survive. **3,880/3,950** retained rows include STRING; **224** have BioPlex probability fields. Source bundles and reciprocal views are not independent experiments. The fields do not establish physical binding, experimental system, release-specific study identity or independent support.
- **Expression:** 2,167 HPA Protein, 1,022 HPA RNA, 1,022 HPM Protein and 1,073 JensenLab TISSUES rows survive, all with UBERON mappings. **None has a populated PMID or URL**. Units remain unknown; qualitative absence is preserved. Source-specific scales must not be pooled. GTEx appears in metadata, but its separate measurement endpoint was not retrieved.
- **Other families:** drug listings would contain local ligand IDs/name/drug status, not activity, mechanism or response. GWAS, LINCS, full ligand activities and claim-level literature are outside this profile. Affiliate pointers are not imported datasets: **all 512 products have LinkedOmicsKB links**, but those links are not CPTAC sample measurements.

[Normalization](../../biograph_steward/normalization.py) preserves raw records and conservative annotation semantics. Exact duplicates retain every locator; reciprocal PPI views retain their original properties. Within-run lineage already connects context records → evidence edges → assertions through `normalized_evidence_edge_ids`, `context_record_ids` and `assertion_ids` in the [graph builder](../../biograph_steward/graph.py). It should not be described as missing functionality.

Predictor features are a further, intentional projection. The provisional feature files are not the final scoring approval. The [frozen comparison policy](../EXPERIMENT_HISTORY.md#reopening-an-archived-file "Archive file: biograph_steward/comparison_protocol.py") withholds GO, integrated expression and unqualified PPI contributions; it uses selected stable-ID pathways, separable BioPlex components and source-specific expression. Omitted feature fields remain in the source snapshot. Feature exclusion is not source-record deletion or proof that excluded biology is irrelevant.

## Reproduced refresh-review gap

An assertion revision hashes its identity and evidence-edge IDs. Retrieval timestamps and locators do not themselves enter the edge identity. Nevertheless, [review replay](../../biograph_steward/assertions.py) rejects an event whenever the **whole snapshot hash** changes, even if its assertion and evidence revision are unchanged. The [client](../../biograph_steward/client.py) hashes creation time, response envelopes and retrieval metadata into that snapshot. CIViC reviews additionally bind to the complete sidecar hash; source-refresh reconciliation is not implemented.

The following read-only synthetic probe, run from the repository root, reproduced the behavior without changing source evidence or writing files:

```bash
python3 - <<'PY'
from copy import deepcopy
from biograph_steward.demo import demo_snapshot
from biograph_steward.graph import build_graph
from biograph_steward.assertions import new_review_event
from biograph_steward.client import digest
s = demo_snapshot(); g = build_graph(s)
a = next(x for x in g['assertions'] if x['kind'] == 'pathway_membership'
         and x['structurally_usable_evidence_ids'])
event = new_review_event(g, a['id'], 'accepted', 'Synthetic audit', 'Probe')
n = deepcopy(s); n['created_at'] = '2030-01-01T00:00:00+00:00'
n.pop('content_sha256'); n['content_sha256'] = digest(n)
b = next(x for x in build_graph(n)['assertions'] if x['id'] == a['id'])
assert a['revision'] == b['revision']
try:
    build_graph(n, [event])
except ValueError as exc:
    print(exc)
else:
    raise AssertionError('Expected snapshot-bound review rejection')
PY
```

Observed: `Review belongs to another snapshot or assertion revision; review the new evidence.` The existing [assertion tests](../../tests/test_assertions.py) also deliberately require rejection after only changing creation time. This is conservative current behavior, not evidence corruption.

## Checkable product value

A useful next increment is **cross-snapshot comparison and review reconciliation**, building on existing lineage. Compare matching identifiers, source fields, filters, coverage and transformation policy; distinguish unchanged evidence, changed assertions, additions, comparable removals and non-comparable absence. A capped/failed or differently scoped pull must not imply retraction. Preserve original events; any carried decision needs explicit new provenance.

Measure correct change attribution, false-removal rate, unchanged-review preservation and review effort. These are maintenance gains, not biological prediction gains. Existing CIViC profile–therapy qualifications and CPTAC sample measurements add represented detail beyond this baseline; shared source studies must not be counted as independent corroboration. **Independent-study lineage and general biological improvement remain unresolved.**
