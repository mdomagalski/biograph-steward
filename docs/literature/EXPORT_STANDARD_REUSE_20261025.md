# Export standards: reuse decision and verified limits

Reviewed October 25, 2026. This is an interoperability audit, not an assessment
of whether any biomedical assertion is true. Existing saved graphs, evidence
qualifications, source responses and historical receipts are unchanged.

## Decision

Use the established KGX JSON Lines serialization and the official KGX validator,
with a pinned Biolink model and explicit per-edge export dispositions. Start with
the mapped pathway-membership subset whose predicate is already present in the
saved graph. Do not rename weak annotation-existence records into stronger
biological relationships just to satisfy a validator.

The complete project-local gold-interface packet remains the reversible source
bundle. It is not itself KGX and must not be advertised as a community gold set.
Qualifiers, source evidence and local review state remain in the source bundle
and source-binding ledger, including every excluded edge. A serialization
projection is not a graph-pruning verdict.

The adopted export keeps the standard core rows in the KGX files, with stable
edge identifiers binding them to an explicit ledger and the full original source
packet. Nested project-specific metadata stays in those preserved sidecars. This
uses the upstream format without relying on its lossy nested-extension importer.

[KGX's specification](https://biolink.github.io/kgx/kgx_format.html) defines node
categories as arrays, supports JSONL node/edge files and allows extension
properties. Its documentation also warns that transformations can insert defaults.
We validate the original projection values without those default insertions.

## Pinned implementations and source material

The optional environment uses KGX 2.7.0, BMT 1.4.8, LinkML and LinkML-runtime
1.10.0, and jsonschema 4.26.0 with Biolink model **v4.4.6**. Direct dependencies are
in `requirements-export-validation.txt`; the observed Python 3.12.4/macOS arm64
resolution is in `docs/third_party/kgx_validation_macos_20261025.lock.txt`.
The core application does not acquire these dependencies.

The official release YAML, its `attributes.yaml` import, predicate map, JSON-LD
context, generated JSON Schema and license are preserved in
`runs/export_standards_resources_20261025`. Their original URLs and SHA-256 values
are recorded by `biograph_steward.standards_validation.resource_manifest()` and
checked before validation. The optional preparation function downloads only
these fixed URLs, and rejects changed upstream bytes.

Sources: [KGX 2.7.0](https://github.com/biolink/kgx/releases/tag/v2.7.0),
[Biolink v4.4.6 YAML](https://github.com/biolink/biolink-model/blob/v4.4.6/biolink-model.yaml),
[Biolink v4.4.6 JSON Schema](https://github.com/biolink/biolink-model/blob/v4.4.6/project/jsonschema/biolink_model.schema.json),
[BMT source](https://github.com/biolink/biolink-model-toolkit).

Licenses inspected: KGX and BMT package metadata identify BSD-3-Clause;
LinkML identifies Apache-2.0; jsonschema identifies MIT. The Biolink repository
LICENSE is Apache-2.0, while its model YAML declares CC0. The installed
`biolink-model` package metadata reports MIT; that package's metadata must not be
substituted for the license of the separately downloaded schema artifacts.
Keep the upstream LICENSE alongside those artifacts. Source database licenses
remain separate from software/schema licenses.

## Actual bounded graph and initial probe

The existing `construction_crc_proteins_v3_20261023` graph contains 1,103 normalized
evidence edges. A conservative initial projection identifies **236 mapped
pathway-membership edges**, connecting **171 nodes**. The remaining 867 edges are
593 locally identified pathway memberships, 237 GO annotation-existence records,
34 drug listings and three PPI annotation records. These are preserved and
explicitly excluded from this narrowly defined projection, not marked false.

The initial probe used node `id`, `category` and `name`; edge `id`, `subject`,
`predicate`, `object`, `knowledge_level=not_provided` and `agent_type=not_provided`,
plus a nested `original_record` extension. Unknown upstream epistemic or agent
labels are not guessed from our deterministic software implementation.

The **official KGX validator passed all 171 nodes and 236 edges**. That result is
limited to the checks the implementation actually performs. Four separate
limitations were reproduced; none was hidden by changing the model.

After selecting the core-row-plus-sidecar representation, the public KGX JSONL
Source/Sink roundtrip preserves **all 171 node and 236 edge objects exactly**.
The KGX checks still pass. The published JSON Schema now reports only the 171
category-array errors; the 236 pathway domain flags remain. This is a usable,
lossless interchange representation with explicit remaining conformance limits,
not a claim that the upstream schema/model issues have been fixed.

The first integrated export additionally exposed an error in our own mapping:
`primary_knowledge_source` was emitted as a list, although the pinned model
requires a single string. KGX rejected that type; JSON Schema reported 236 edge
type errors and the importer changed the values. The failed receipt is preserved
at `runs/export_standard_validation_20261025`. The corrected export uses the
scalar `infores:reactome`, with `aggregator_knowledge_source` remaining the array
`["infores:pharos"]`. The optional test exercises this production shape. This
was an integration bug, separate from the unresolved upstream constraints above.

## Verified limitations and their disposition

1. **Predicate metadata and domain constraints exceed KGX's checks.** An injected
   `biolink:interacts_with` predicate passes KGX even though the pinned model marks
   it as a mixin. An unknown project predicate is correctly rejected. KGX 2.7.0's
   predicate validation checks presence, naming and model lookup, but does not
   enforce predicate mixin or domain/range constraints. The added audit therefore
   reports the pinned BMT element metadata and category ancestors separately.
   This is verification of the validator's scope, not evidence that any concrete
   PPI subtype can be inferred. [Official KGX validator code](https://github.com/biolink/kgx/blob/v2.7.0/kgx/validator.py).

2. **The pathway domain conflict is already known upstream.** Biolink describes
   `participates_in` as involving a continuant in a process, but declares its
   domain as `occurrent`. Protein is not a descendant of that domain. The source
   predicate is retained and the 236 edges receive a model-domain review flag.
   [Biolink issue 1606](https://github.com/biolink/biolink-model/issues/1606) describes
   this same inconsistency. Both v4.1.6 and v4.4.6 contain it; downgrading to the
   older version does not resolve it. No local schema patch or waiver is applied.

3. **The generated JSON Schema and KGX's lenient contract differ.** The pinned
   `Protein.category` property has `type: array` and an enum containing the scalar
   string `biolink:Protein`. Therefore the documented category list fails with
   `['biolink:Protein'] is not one of ['biolink:Protein']`. The same occurs for
   Pathway. The published schema also rejects extension fields through
   `additionalProperties: false`, although KGX permits them. Direct jsonschema
   validation produces 171 category errors and 236 extension-property errors for
   the initial probe. The supported `linkml-validate` regeneration path with
   LinkML 1.10.0 reproduces the category error; Biolink v4.1.6's published schema
   has the same problem. We found no matching confirmed issue for the exact enum
   failure in the targeted upstream search, so this is recorded as a reproduced
   upstream artifact issue, not a claimed upstream acknowledgement. See the
   [official JSON Schema guidance](https://biolink.github.io/kgx/kgx_biolink_validation.html).

4. **JSONL import is not lossless for nested custom objects in this KGX version.**
   A public `JsonlSource` → `JsonlSink` roundtrip preserves the counts but converts
   all 236 nested `original_record` objects to strings. The source's inherited
   `sanitize_import` implementation explains this behavior. The audit records
   changed fields and never replaces the published bundle with transformed
   output. A minimal interchange graph plus complete source sidecars avoids
   relying on custom nested object support. The documented empty
   `default_provenance` setting prevents insertion of fictitious `Graph` sources.
   [KGX import implementation](https://github.com/biolink/kgx/blob/v2.7.0/kgx/utils/kgx_utils.py).

## Offline audit boundary

The optional `validate_projection(nodes, edges, resources_dir)` function returns
separate KGX, published-JSON-Schema, domain/predicate and JSONL-roundtrip results.
It sets `full_conformance=false` and `biological_validation_performed=false`.
An error in one checker is not overwritten by success in another.

BMT 1.4.8 always retrieves a predicate map during construction; KGX also initializes
a default toolkit during module import and defaults its prefix context to an
older model. The adapter replays the exact frozen predicate-map response, supplies
the frozen official toolkit at those resource-loading boundaries, and supplies
the matching context. Validator methods and schema contents are not patched.
This optional audit runs in its own process; it is not an HTTP-thread service.
The audit succeeds without network access after resources have been prepared.

There is no justification here for additional biomedical extraction experiments,
paid compute, a new graph database, or a replacement framework. The verified gap
is bounded interoperability and precise reporting of existing standard/tool
limitations, while scientific usefulness still requires an independent-reference
comparison with protected outcome boundaries.
