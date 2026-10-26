# Bounded KGX export and validation

Updated October 25, 2026. The workbench now publishes an audited **KGX JSONL
projection** alongside its complete source packet. It does not claim full
Biolink conformance or biological correctness. The real check and known upstream
limits are recorded in the [validation result](evaluations/EXPORT_STANDARD_VALIDATION_20261025.md)
and [reuse investigation](literature/EXPORT_STANDARD_REUSE_20261025.md).

## What is exported

The initial profile, `biograph-steward.kgx-reactome-pathways.v1`, covers only
mapped UniProt protein → Reactome pathway memberships already represented as
`biolink:participates_in` in the source graph. A record must have an exact mapped
identity, Reactome source, matching assertion identity, no nonempty qualifiers,
and a candidate, provisional or accepted local review state. The projection
does not turn candidates into accepted evidence.

Every source edge, node and assertion has a mapping-ledger entry. Local pathway
identifiers, GO annotation-existence records, drug listings, mixed-source PPI
annotations and qualified claims outside this profile remain in the complete
`source_packet/`. Their exclusion from this projection is neither pruning nor
a claim that they are false. No relation is strengthened or relabeled merely to
pass a validator.

Plain JSONL rows carry standard fields. Edge IDs, source hashes and the ledgers
connect each projected row to its original evidence, qualifications, review
state and source-response locator. Keep the whole bundle when passing evidence
to another tool; the two graph files alone are not the complete evidence record.
KGX's importer stringifies nested custom objects, so evidence objects are kept
in the established source packet instead of nested inside interchange rows.
Unknown knowledge level and agent type use `not_provided`.

## Run the audit

The core app and offline integrity verifier still need only Python 3.10+.
Install upstream validators in a separate **Python 3.12** environment:

```sh
python3.12 -m venv .venv-standards
.venv-standards/bin/python -m pip install -r requirements-export-validation.txt
python3 app.py standards-resources --out runs/standards_resources_01
.venv-standards/bin/python app.py standards-export \
  --packet runs/construction_crc_proteins_v3_20261023/gold_packet \
  --resources runs/standards_resources_01 \
  --out runs/standards_projection_01
python3 app.py standards-verify --run runs/standards_projection_01
```

Use a source packet that exists locally. A fresh checkout can create a synthetic
packet using the [gold-interface demo commands](GOLD_SET_INTERFACE.md#export-and-verify-a-graph).
Real source snapshots are not in Git. Outputs must be new directories outside
the sealed source packet and resources. Export preserves the input packet;
it never rebuilds it using today's transformer.

`standards-resources` downloads six hash-pinned official Biolink 4.4.6 artifacts
and their manifest. Export and verification are offline after installation and
resource preparation. KGX 2.7.0, BMT 1.4.8, LinkML/LinkML-runtime 1.10.0 and
jsonschema 4.26.0 are checked at runtime. The observed macOS transitive package
resolution is saved under `docs/third_party/`; it is not a cross-platform lock.
No model, GPU or AWS account is needed.

## Interpret results separately

`validation.json` records four checks:

| Check | What it establishes |
|---|---|
| Official KGX validator | The field, prefix, category and predicate checks actually implemented by that version |
| Official KGX JSONL Source → Sink roundtrip | Whether the interchange rows survive that import/export without changed values or counts |
| Published Biolink JSON Schema | Class-specific validation against unchanged upstream schema bytes |
| Declared domain/range and predicate audit | Separate inspection of pinned BMT metadata and category ancestors, including constraints KGX does not enforce |

For the real three-protein packet, KGX validation and the plain-row roundtrip
pass. The generated schema rejects documented category arrays, and the model's
declared `participates_in` domain conflicts with its protein/pathway use.
The audit reports these failures; it does not patch the model, change categories
to pass, or turn a KGX pass into a full conformance claim. Empty supported
projections are reported explicitly rather than treated as successful validation.

An export command can successfully save an audit that reports failed checks.
Its exit status indicates artifact creation; inspect the separate statuses and
`full_standard_conformance_claimed: false` before downstream use.
`standards-verify` checks hashes, source bindings, frozen resources and exact
mapping replay using the core app. It **does not rerun upstream validators**.
To rerun those checks, export the preserved `source_packet/` using the preserved
`standards/` into a new directory in the optional audit environment.

The manifest includes implementation hashes, validation input hashes, resource
hashes and a complete file inventory. These are unsigned integrity records,
not publisher authentication. A current mapping change may prevent exact replay;
retain the source revision identified by the implementation hashes.

## Remaining work

Resolve or explicitly negotiate the upstream model/schema constraints before
claiming full conformance. Extend profiles only when the source supplies enough
relation and qualifier semantics. Broader SSSOM, PROV-O, JSON-LD or organizer
format conformance is not implied by this increment. The [reference decision](literature/REFERENCE_COMPARATOR_DECISION_20261025.md)
separately defines the limited biological assessment that can be supported now.
