# Inspect a historical function prediction

In **Compare & assess**, **Trace a historical function prediction** opens a
saved, source-qualified model context. Choose an exact archived protein and
select **Open saved context**. This requires no model server or scientific
Python dependencies.

Each displayed GO hypothesis includes its historical LocalPlus score, exact
weighted neighbor contributions, source pair identifiers and dated training
terms. The small diagram shows the largest contributions; expand the table or
download the query JSON to inspect every contributor. A functional STRING
association does not automatically establish direct physical binding.

The six saved examples include EGFR, NRAS, KRAS, TP53 and two distinct CUX1
source accessions. The CUX1 examples abstain when their historical identity
support cannot qualify a neighborhood. A shared gene or symbol does not justify
copying another source product's interactions.

The optional annotation notes distinguish:

- A concept already present in the broader pre-t0 annotation source.
- A current curator row that supplies the literal predicted term.
- A narrower current annotation that supplies ancestor context through an
  explicit admitted ontology path.
- An obsolete historical term or an unresolved current-source match.

Native relations, references, forms and extensions remain inspectable. A GAF
form field repeating the query's canonical accession is not itself evidence
of a distinct isoform. Later curation is displayed separately and never fed
back into the historical model.

These are uncalibrated ranking scores. A later curation match is not a new
discovery, and no hypothesis is automatically accepted, pruned or added to the
current evidence workspace. The model context is also separate from the
benchmark's population-level evaluation.

## Operator registration

Real model/source packets are separate from the code-only installation. A
verified publication can be registered in `runs/function_context_index.json`:

```json
{
  "format": "biograph-steward.function-context-index.v1",
  "publications": [{
    "id": "historical_function_context_20261113",
    "manifest_sha256": "EXACT_PUBLICATION_FILE_SHA256",
    "display_notes": {
      "id": "historical_function_context_notes_v2_20261113",
      "file_sha256": "EXACT_NOTES_FILE_SHA256"
    }
  }]
}
```

Use ordinary named children of the configured runs directory and actual
64-character FILE hashes. The publication binds its query/source files; the
separate notes bind the exact publication and hypothesis identities. Invalid
files, changed bytes and symlink traversal fail closed. If nothing is
registered, the model-context card stays hidden.

The historical source profile uses Pharos319's archived STRINGv11 weights,
2019 identity support, GO2023 and the CAFA5 author's historical annotation
snapshot. Upstream data retain their licenses and attribution; the app's MIT
license does not relicense source data. See the optional
[prediction reproduction tools](../tools/cafa_prediction/README.md) and
[official reference adapter](../tools/cafa_reference/README.md).
