# Bounded export validation

October 25, 2026 (America/New_York). **Official KGX checks and the plain JSONL
roundtrip pass for 171 nodes and 236 Reactome pathway edges. Full Biolink
conformance remains unresolved.** This increment tests interchange behavior,
not scientific accuracy or graph improvement.

The actual output is `runs/export_standard_validation_v2_20261025/` (ignored).
The [aggregate receipt](export_standard_validation_20261025_summary.json)
records counts, versions and content hashes. The [usage guide](../STANDARD_EXPORT.md)
documents commands and scope; the [reuse investigation](../literature/EXPORT_STANDARD_REUSE_20261025.md)
records official sources, version checks and reproduced upstream limitations.

## Source and projection

Input: `runs/construction_crc_proteins_v3_20261023/gold_packet`, built from live
Pharos for EGFR, KRAS and BRAF. All 1,009 original nodes, 1,103 evidence edges
and 1,103 qualified assertions are copied in the sealed source packet. Mapping
ledgers account for every node, edge and assertion. The source graph hash remains
`09a614a048a9924b09c300f8706af00a7639f55cad4ded57f2b7d80d5735ff4d`.
The original construction publication still passes its independent offline
verifier after this export.

| Disposition | Evidence edges |
|---|---:|
| Projected mapped Reactome pathway memberships | 236 |
| Preserved local pathway identifiers outside this profile | 593 |
| Preserved GO existence annotations lacking required relation semantics | 237 |
| Preserved drug listings without a mapped interaction claim | 34 |
| Preserved PPI annotation bundles without a concrete standard predicate | 3 |
| Total | 1,103 |

The 867 excluded edges remain in the source packet. Exclusion is a mapping
decision, not pruning or biological rejection. The 236 projected edges connect
171 nodes; their stable IDs and source hashes bind them back to full records.

## Independent validation results

Pinned tools: KGX 2.7.0, BMT 1.4.8, LinkML and LinkML-runtime 1.10.0,
jsonschema 4.26.0, Biolink model 4.4.6. Six official model artifacts and a
manifest are copied into the output and verified against fixed SHA-256 values.
The actual audit ran offline in the optional Python 3.12 environment.

| Check | Result | Interpretation |
|---|---|---|
| Official KGX validator | Passed | Implemented field, prefix, category and predicate checks passed |
| Official JSONL Source → Sink | Passed; zero changed records | All 171 nodes and 236 edges retain exactly the same values and counts |
| Published class-specific JSON Schema | Failed; 171 category-enum errors | Upstream schema declares category as an array but its enum uses a scalar; the documented array fails |
| Declared predicate/domain/range audit | Review required; 236 domain flags | Protein → pathway usage conflicts with the model's declared `participates_in` domain |
| Offline bundle verification | Passed | Source packet, resources, file inventory, validation input hashes and exact mapping replay agree |

KGX alone does not enforce all predicate mixin or domain/range restrictions.
The pathway-domain inconsistency is documented in
[Biolink issue 1606](https://github.com/biolink/biolink-model/issues/1606).
The category-enum failure was reproduced against the published schema and the
supported LinkML regeneration; it was not identified as an acknowledged issue
in the targeted upstream search. Older Biolink 4.1.6 retains both limitations.
No model constraints or validator methods were weakened to obtain a pass.

## Integration corrections and preserved failures

The initial nested-evidence probe exposed an upstream importer behavior: KGX
stringifies custom dictionary fields. The adopted export uses plain core rows
with the full established source packet and mapping ledgers alongside them.
No transformed output replaces the original evidence.

The first complete integration run,
`runs/export_standard_validation_20261025/`, found **our own cardinality error**:
`primary_knowledge_source` was a one-element list, whereas the pinned standard
requires a single string. KGX rejected it, JSON Schema reported 236 edge type
errors, and the roundtrip changed the field. The exporter now uses a scalar
primary source and an array of aggregators. The failed run remains unchanged;
v2 records the corrected result. This error is distinct from the remaining
upstream model/schema findings.

A separate code review found that the initial offline projection reader used
permissive JSON decoding. It now reuses the source-packet strict decoder and
rejects duplicate keys even if someone reseals an outer receipt. The well-formed
v2 artifact verifies unchanged with that stricter reader. Hash records are
unsigned and do not authenticate a publisher.

## Verification boundary

Synthetic projection and artifact tests cover qualifications, identifier/source
scope, local review states, complete ledgers, source-byte preservation, immutable
outputs, offline replay, malformed/resealed inputs and CLI behavior. Their
mocked validator reports explicitly identify themselves as synthetic; they
are not evidence of standard conformance. Separate optional tests exercise
the real pinned validators, unknown predicates, lossy nested imports and empty
supported projections.

Final regression: **599 tests, 23 skipped, no failures** in the core environment.
All **five optional validator tests passed** in the pinned audit environment.
The skipped core tests include four optional standards checks; the real audit
and their separate run provide that validation. Documentation links and
`git diff --check` also pass. No browser UI was changed by this increment.

This work changes no biological comparison, assay outcome or original source
artifact. The [reference/comparator decision](../literature/REFERENCE_COMPARATOR_DECISION_20261025.md)
is complete separately; the next assay adapter and frozen corroboration report
remain to be implemented. No Brev model, GPU or AWS resource was used.
