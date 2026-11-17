# Restoring shared WikiPathways source context

The evidence audit found an integration gap that can be repaired without a
new biological model: multiple Pharos annotations cite the **same exact
versioned pathway URL**, but each currently uses its own local pathway node.
An optional, separate source projection now joins that shared context while
preserving every original evidence record. It does not validate the underlying
membership or change the app's historical graphs.

## Verified gap and established solution

In the original workspace, 3,492 WikiPathways edges point to **3,492 distinct
local nodes**, although their records name only **308 full pathway versions**.
Every local node has just one protein subject. This is explicitly flagged as
unresolved mapping in `graph.pathway_id`; it was a conservative capability
boundary, rather than a silently certified identifier mapping.

After the separate current-source qualification, 1,600 WikiPathways rows remain:
1,558 current encoded-membership keeps and 42 retained unknowns. They still
point to 1,600 local leaves, even though they cite only 275 full versions.
There are 1,319 distinct protein/version connections and 281 additional raw
representations. No source node was removed from the preserved full workspace.

The [WikiPathways primary paper](https://pmc.ncbi.nlm.nih.gov/articles/PMC10767877/)
and [maintainer's version-resource explanation](https://github.com/wikipathways/wikipathways-help/discussions/222)
describe version-specific resources. All examined Pharos rows explicitly
supply a matching locator, for example
`http://www.wikipathways.org/instance/WP179_r105448`.
We use that **verbatim supplied URL**, rather than inventing a URI conversion
or equating a database row with an unversioned biological entity. The URL is a
source-reported version locator; its current HTTP response need not preserve
that historical content.

The existing standard export's plain JSONL plus complete mapping-ledger pattern
fits this task. The [KGX 2.7.0 merge implementation](https://github.com/biolink/kgx/blob/v2.7.0/kgx/graph_operations/graph_merge.py)
also shows why distinct source evidence keys must be retained when endpoints
become shared. We did not expand the Reactome-only standards profile or the
UniProt-only SSSOM identity contract. `dcterms:isVersionOf` remains provenance;
it is not added as a biological graph edge or replaced with Biolink's more
restricted `version_of` slot.

## Completed source projection

| Measure | Retained source representation | Exact-version projection |
|---|---:|---:|
| Protein subjects in this Wiki scope | 76 | 76 |
| Incident pathway object nodes | 1,600 local identifiers | 275 exact version URLs |
| Evidence edges | 1,600 | 1,600 |
| Distinct protein/version connections | 1,319 in source metadata | 1,319 shared endpoint connections |
| Distinct protein pairs co-listed under a version | 1,133 in source metadata | 1,133 shared-object contexts |

The projection contains **351 nodes** in total. Each evidence edge keeps its
original ID and directed `protein → pathway` predicate, with source assertion
ID, local pathway ID, `pwid`, evidence status and assertion review state.
Parallel evidence records are not merged, weighted or counted as independent
experiments. There are no new protein-interaction edges.

For example, RAD21 and TP53 have distinct local annotations citing
`WP179_r105448`, Cell cycle. Their projected edges share that exact source URL.
This is a **common-object join**: `RAD21 → cited model ← TP53`. It is not a
directed protein-to-protein path, a causal mechanism or proof of physical
interaction. The existing app path explorer's direction rules are unchanged.

The saved trace contains 18 RAD21 rows and one TP53 row: **19 evidence records
represent two protein/version connections**, rather than 19 independent
experiments. All remain candidate assertions with source evidence needing
review. Sharing a context node does not change those states.

Every input edge, node and assertion has a ledger entry. All 13,493 edges outside
this Wiki profile remain in the full preserved source package. Unsupported or
unversioned identifiers, inconsistent URLs, conflicting native metadata and
nonempty qualifications remain outside this flat projection with explicit
reasons. Different revisions never collapse. Local review and acceptance are
not transferred between assertions just because their context node is shared.

The source baseline, retained graph, original probability sample, evidence
judgments and earlier comparisons are unchanged. Unknown current-source
eligibility stays unknown. No historical model-content validation, full
KGX/Biolink conformance or downstream biological-utility claim follows from
this representation repair.

## Reuse and verification

The [optional adapter](../../tools/sampled_audit/wiki_version_projection.py)
accepts a verified Gold retained package and an explicit report-file SHA256:

```sh
python3 tools/sampled_audit/wiki_version_projection.py export \
  --retained runs/my_current_wiki_view/retained \
  --retained-report-sha256 VERIFIED_RETAINED_REPORT_FILE_SHA256 \
  --out runs/my_wiki_version_projection
python3 tools/sampled_audit/wiki_version_projection.py verify \
  --projection runs/my_wiki_version_projection
```

The exporter preserves the full verified source package, writes six JSONL
inventories and replays them before and after sealing. Source, copy and
implementation changes fail closed. The verifier rejects invented scientific
or standards-validation claims even if a modified manifest is resealed.
Core controls include distinct revisions, parallel evidence, unsupported local
ID conflicts and exact URL syntax. No new dependency, network retrieval,
model or GPU is required.

The local v1 export is preserved. A subsequent literal-URL parser guard rejects
parameters or whitespace that `urllib.parse` could normalize away. Actual
native URLs contain neither; the v2 export is a technical replay on identical
consumed data, with unchanged scientific decisions and source topology.

Local artifacts live under
`runs/whole_graph_sample_audit_20261112/wiki_version_projection_v2/`.
They retain the same provider restrictions as their full source package and
are not bundled in Git. Aggregate evidence is linked from the
[whole-workspace audit](WHOLE_GRAPH_SAMPLE_AUDIT_20261112.md).

The useful next scientific question is whether this better source representation
helps a specified retrieval or biological task. It has not been answered by
the normalization counts, and it does not explain previous weak prediction
results retroactively.
