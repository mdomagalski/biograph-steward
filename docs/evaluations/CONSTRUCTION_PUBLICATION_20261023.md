# Bounded construction and graph publication

The exact protein-cohort workflow now reaches retrieval, normalization, a saved
workbench graph, a cited candidate answer and a source-bound export. It reuses
the existing Pharos adapter and normalization. The request and fixed retrieval
profile are selected by the user; this is deterministic construction, not an
autonomous construction agent or a biological-performance comparison.

## Public-source check

A fresh request retrieved EGFR (`P00533`), KRAS (`P01116`) and BRAF (`P15056`)
from `pharos319`, with KRAS as the focus and interaction/shared-pathway questions.
All three identifiers resolved exactly. Twelve recorded source envelopes support
the graph. No disease filter, assay outcomes, model or paid compute was used.

| Output | Count |
|---|---:|
| Nodes | 1,009 |
| Candidate assertions / evidence groups | 1,103 |
| Pathway memberships | 829 |
| GO annotations | 237 |
| Drug listings | 34 |
| Cohort protein-interaction assertions | 3 |
| Returned neighboring proteins | 2 |
| Bounded summary statements / citations | 4 / 6 |

All 1,103 evidence groups link to exact original source-response rows, hashes
and retrieval times. The six retained directional PPI source views normalize
to three undirected interaction assertions; they are not six independent
experiments. No assertion was automatically accepted.

| Family | Retrieved | Retained | Observed coverage |
|---|---:|---:|---|
| Pathways | 829 | 829 | Count-reconciled for all three proteins |
| GO | 237 | 237 | Count-reconciled for all three proteins |
| PPI neighbors | 2,303 | 6 | Count-reconciled; 2,297 outside-cohort views preserved in raw responses |
| Drug listings | 34 | 34 | Count-reconciled for all three proteins |
| Publication discovery | 60 | 60 | Capped at 20 per protein; 11,772 reported overall |
| Expression | 0 | 0 | Not requested |

Count reconciliation describes this API profile. It does not establish complete
biology, study independence or factual accuracy. Publication discovery records
are not used as claim-specific supporting citations. Interactions retain the
broad source meaning; direct physical binding is not inferred.

The final artifact is `runs/construction_crc_proteins_v3_20261023/`. Earlier local
publication checks are preserved. The final publication uses the exact original
snapshot bytes; it was reconstructed offline after completing direct pathway
source links. Both its construction receipt and nested `gold_packet/` verify.
The source-bound [machine-readable summary](construction_publication_20261023_summary.json)
records artifact hashes and counts. Source snapshots remain ignored local data.

## Validation

The core regression suite completed **575 tests, with 19 optional-dependency
skips and no failures**. The suite covers the new request, identity, coverage,
source-pointer and version-drift contracts, all-unresolved cohorts, candidate
review boundaries, authenticated routes, immutable output, changed/missing
receipts, implementation fingerprints and offline CLI republication. Existing
disease-graph and answer behavior remains unchanged.

The real saved graph and answer also reopened through the local HTTP API with
matching graph/answer bases. Its 54-file ZIP includes the answer report, raw
source trace and nested graph packet. The static graph report links directly to
the saved cited answer.

Combined workbench JavaScript parsed successfully. Visual browser interaction
could not be completed: the browser runtime failed macOS native-module signature
validation, and the alternate desktop browser connection was unavailable.
No visual rendering, citation click or form-submission success is claimed.

## Remaining boundaries

- Agent-selected construction still needs a constrained tool interface and a
  comparison against this deterministic workflow. The existing model/NeMo
  question planner remains a saved disease-graph workflow and rejects cohorts
  before a model call.
- Full exchange-standard validation and cohort maintenance are separate work;
  the local packet is not a claim of complete KGX/Biolink conformance.
- The independent-reference/source-lineage decision and matched scientific
  comparison remain open. These engineering checks do not demonstrate improved
  predictions or biomedical accuracy.

See [construction commands and reused source contracts](../CONSTRUCTION.md)
and the [delivery sequence](../BUILD_PLAN.md#delivery-sequence-and-completion-criteria).
