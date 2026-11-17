# Used-term GO content currency

This optional, offline audit compares literal GO content in the pinned January
2023 OBO and July 2026 OBOGraphs snapshots. It extends the earlier displayed-term
audit to an explicit source-frozen vocabulary. It does not evaluate biological
truth, remap identifiers, reason over OWL, modify annotations, or update a model.

The producer reuses the pinned CAFA author's OBO reader and this project's
existing OBOGraphs/lifecycle loader. The unchanged reader is extracted as an AST
function with a metadata-only Graph collector; its unused dense graph is never
constructed. The optional literal-audit producer (`audit.py`) is GPL-3.0-only. The standard-library saved
index consumer in `biograph_steward/go_content_currency.py` remains part of the
MIT application and imports no optional scientific runtime.

First freeze the exact used-term scope, then compare it:

```sh
python3 -m tools.go_content_currency.audit prepare \
  --graph /absolute/source/graph.json \
  --training /absolute/retained/downloads/training_snapshot.json.gz \
  --publication /absolute/retained \
  --native-publication /absolute/native-go-publication \
  --historical /absolute/2023/go-basic.obo \
  --comparison /absolute/2026/source.json.gz \
  --author-parser /absolute/pinned/cafaeval/parser.py \
  --output /absolute/new-scope

python3 -m tools.go_content_currency.audit audit \
  --frame /absolute/new-scope/term_frame.json \
  --freeze /absolute/new-scope/scope_freeze.json \
  --expected EXACT_SCOPE_FREEZE_FILE_SHA256 \
  --historical /absolute/2023/go-basic.obo \
  --comparison /absolute/2026/source.json.gz \
  --author-parser /absolute/pinned/cafaeval/parser.py \
  --output /absolute/new-index
```

All paths must identify existing, ordinary nonsymlink source files; outputs must
be new directories. The two ontology byte pins are fixed in the producer. Do
not edit the audit or consumer after freezing a scope and silently reuse that
freeze. Preserve failed or superseded preparations.

The index retains original OBO stanzas and native OBOGraphs nodes alongside
explicit names, definitions, synonym scopes, lifecycle declarations and
`is_a`/`part_of` records. The consumer verifies the manifest FILE hash, content
seal, compressed index hash, size limits, complete ID inventory and recomputed
literal flags before an exact-ID lookup:

```python
from biograph_steward.go_content_currency import load_index, get_term
manifest, rows = load_index('/absolute/new-index', 'EXACT_MANIFEST_FILE_SHA256')
context = get_term(manifest, rows, 'GO:0062153')
```

The January 2023 predictor interpretation, unknown-vintage Pharos labels and
separately dated native annotations remain distinct. A change is an inspection
flag, never a prune verdict; missing historical terms remain unassessed. Even
unchanged fields do not establish semantic equivalence. July 2026 is the pinned
comparison date, not a claim of the latest GO release.

The actual 18,002-term run and its resource costs are documented in
[the used-term audit](../../docs/evaluations/GO_USED_TERM_CONTENT_CURRENCY_20261114.md).
The complete index consumes about 319 MiB peak process RSS in the recorded
consumer check; it should not be reparsed for every ordinary app request.

## Compact notes for existing saved term details

The offline projection reads the full index once, selects the exact candidate
IDs already present in a registered historical publication, and preserves the
publication, candidate order, labels and scores. It uses only the MIT consumer;
it does not execute the optional scientific reader or recompute predictions.

```sh
python3 -m tools.go_content_currency.project \
  --index /absolute/new-index \
  --index-expected EXACT_INDEX_MANIFEST_FILE_SHA256 \
  --publication /absolute/retained \
  --publication-expected EXACT_HISTORICAL_PUBLICATION_FILE_SHA256 \
  --output /absolute/new-content-notes
```

The resulting `notes.json` binds the historical publication and original query
inventory to the full source-index manifest/content, term frame, compressed
index and ontology hashes. It excludes full ontology bodies. A generic
`project_terms()` helper can select another explicit ID frame without ranking,
alias resolution or reference labels.

Place the new notes in their own ordinary directory beside the saved historical
publication in the configured runs folder. Add an optional `content_notes`
registration to that publication's existing `function_context_index.json` row:

```json
{
  "id": "historical_publication_id",
  "manifest_sha256": "EXACT_HISTORICAL_PUBLICATION_FILE_SHA256",
  "content_notes": {
    "id": "separate_content_notes_directory",
    "file_sha256": "EXACT_NOTES_FILE_SHA256"
  }
}
```

Keep any existing `display_notes` registration: it supplies a different
annotation-overlap comparison. Previous registrations without `content_notes`
continue to work. Authenticated saved-query GETs expose the small content-note
projection, with a separate `download/term_content` download; they never open
the full used-term index. The term's existing detail gains a collapsed dated
comparison, without a new panel or navigation item. The actual 27-ID projection
is 90,874 bytes. Nothing is installed in AWS by this local operation.

## Focused verification

The maintained app checks cover the optional registration, authenticated
GET/download, exact candidate/source binding, escaping and legacy behavior.
The HTTP check forbids full-index loading and verifies that saved answers and
source files remain unchanged. The focused run passed 25 Python checks and
nine existing DOM checks. No optional science package is needed for the app
consumer; the audit test uses its already-qualified native reader when present.

```sh
NO_PROXY=127.0.0.1,localhost,::1 no_proxy=127.0.0.1,localhost,::1 \
  PYTHONPATH=.:tests python3 -m unittest \
  test_function_content_notes test_function_context test_function_context_http \
  tools.go_content_currency.test_audit -v
node --test tests/function_context_ui.test.cjs
```

The local active/obsolete examples also passed actual browser inspection.
These are implementation and presentation checks, not biological validation or
an AWS deployment check.
