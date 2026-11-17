# Official native GO quality-control runner

## Full replacement-proposal census

`audit_replacements.py` is a separate dependency-free audit of the existing
explicit main-term replacement proposals. It reuses the Gold package and GOA
source verifiers, exact five-field projection matcher and the existing
experimental-reference context gates. It applies no repair and changes no
graph or review. Missing/nonexperimental/context-specific records stay outside
the qualified recovery scope; they are not false labels.

Supply the original GO qualification directory, the actual retained decision
package and original native GO context, each with its independently checked
report file SHA256:

```sh
python -m unittest tools.go_qualification.test_replacements -v
python -m tools.go_qualification.audit_replacements \
  --qualification ORIGINAL_GO_QUALIFICATION \
  --retained-package ACTUAL_RETAINED_PACKAGE \
  --context ORIGINAL_NATIVE_GO_CONTEXT --output NEW_AUDIT_DIRECTORY \
  --qualification-sha256 GO_REPORT_SHA256 \
  --retained-sha256 RETAINED_REPORT_SHA256 --context-sha256 NATIVE_REPORT_SHA256
```

Outputs separately enumerate proposal origins, unique protein/replacement
concepts, exact native rows, concept versus projected-record overlap, and
qualified nonduplicate current-native candidates. `qualified_recoveries.gaf`
is an explicitly labelled standard subset of unchanged native annotation bodies,
not a modified Pharos annotation file. Source licensing and provenance remain
attached. A canonical protein/new-term overlap is not identity of complete
native relations, publications, contexts or evidence.

See the [completed167-proposal census](../../docs/evaluations/GO_REPLACEMENT_CENSUS_20261113.md).
The audit is a source-backed coverage assessment, not independent experimental
truth or a full GORULE20 repair/conformance claim. The separately sourced GOA
adapter and the publication workflow below now support applying its qualified
candidates without rewriting historical Pharos rows.

## Publish native GO recoveries

`publish_recoveries.py` reuses the native GOA adapter, ordinary saved-run replay
and the Gold decision interface. It preserves old evidence, source publications,
assertion identities/revisions and exact decision rows, then appends new native
GO rows with explicit abstentions. Existing extension-bound reviews cause a
failure when the combined source hash changes; they are never migrated silently.

```sh
PYTHONPATH=.:tests python -m unittest tools.go_qualification.test_publish_recoveries -v
python -m tools.go_qualification.publish_recoveries prepare \
  --census CENSUS_DIRECTORY --qualification ORIGINAL_GO_QUALIFICATION \
  --retained-package ACTUAL_RETAINED_PACKAGE --context ORIGINAL_NATIVE_GO_CONTEXT \
  --census-sha256 CENSUS_REPORT_FILE_SHA256 --output NEW_PREPARATION \
  --publication EXISTING_VERIFIED_GOA_PUBLICATION
```

`--publication` is optional. When supplied, its complete proof and source-byte
bindings are replayed before copying it; otherwise the adapter creates it from
the supplied local artifacts. The new directory contains `goa_publication/`,
`raw_run/`, `packet/`, `decisions.json`, `retained/` and a sealed
`recovery_preparation.json`. Preparation does not publish an app workspace.

First recompute the existing WikiPathways history proof against
`NEW_PREPARATION/packet/source/graph.json`, using the original archived captures.
Then finalize with its explicit content pin:

```sh
python -m tools.go_qualification.publish_recoveries finalize \
  --prepared NEW_PREPARATION --history NEW_GRAPH_BOUND_HISTORY \
  --history-sha256 HISTORY_CONTENT_SHA256 --output NEW_WORKSPACE
```

The finalizer refuses an old graph-bound proof, changed prepared files or an
output inside the sealed preparation. All source data stay separate from the
code checkout. No new retrieval, LLM or GPU is required. See the
[actual recovery result](../../docs/evaluations/NATIVE_GO_RECOVERY_20261113.md)
for counts, source versions, interpretation and deployment scope.

## Published quality-control runtime

This optional runner executes the published **ontobio 2.9.12** implementation
with the directly pinned **prefixcommons 0.1.12** identifier registry
on complete, preserved native GAF records. It does not reconstruct historical
Pharos qualifiers, modify the app graph, or estimate independent biological
accuracy. The dependency-free application remains separate.

```sh
python3.12 -m venv .venv-go-qc
.venv-go-qc/bin/python -m pip install -r tools/go_qualification/requirements.txt
PYTHONPATH=.:tests:tools/go_qualification .venv-go-qc/bin/python \
  -m unittest discover -s tools/go_qualification -p test_official_qc.py -v
```

The API is `run_official_qc.run(qualification, ontology, retracted_refs,
eco_mapping, eco_derived_mapping, output, *, ontology_sha256,
retracted_sha256, eco_sha256, eco_derived_sha256, ...)`.
The CLI exposes the same inputs; see `run_official_qc.py --help`.
Use a new output directory and independently checked source pins.

## Actual rules and source contracts

- Official `GafParser` performs primary-term, With/From and extension
  obsolete/alternative-ID validation with repair enabled.
- Official **GORULE22** checks exact reference identifiers against the supplied
  retraction table. Its source capture date is preserved in the report. A pass
  is relative to that table and is not certification that a study is currently
  unretracted or scientifically correct.
- Official **GORULE61** repairs relations according to the GO hierarchy,
  preserving NOT. The exact requested selectors are zero-padded strings
  `0000022` and `0000061`. The inspected runtime's integer-selector examples do
  not execute these rules; a control verifies the actual API behavior.
- **GORULE13** is explicitly not run without proven inference data. The released
  GAFeRence v0.5 output is a **sparse delta**: it emits unsatisfiable cases or
  additional inferences, and omits normal cases. In `published_sparse_delta`
  mode, a valid empty list can therefore be accepted only with matching sealed
  successful producer and released-parser coverage receipts. Arbitrary empty
  files and absent/unproven processing do not establish a pass. All non-NOT
  prepared keys must agree exactly between ontobio and the actual released
  GAFeRence parser; no artificial passing entries are inserted. The official
  rule exempts NOT, retains experimental violations with warnings, and filters
  nonexperimental violations. `complete_keys` mode is retained for explicitly
  enumerated tables and synthetic controls; it is not the released sparse format.

The native GAF `!go-version` date must match the ontology's native version.
An unknown or different release fails before output. The native sidecar and
preserved GAF bytes are verified by the existing core `load_go_context` reader,
including full GAF line/completeness binding. That reader does not revalidate
the original Gold graph/packet. Source/reference hashes pin bytes; they do not
authenticate an arbitrary declared publisher or execution receipt.

Ontobio downloads ECO maps during import. A standard Requests transport replay
supplies exact pinned ECO source bytes and blocks unrecorded requests. Cached
primary/derived mappings are checked using the official parsing API, including
all three mapping instances used by parsing, QC and serialization. Fresh
official rule61 instances avoid carrying a previous ontology's closure cache
across calls. Instrumentation records calls to the unmodified official rule
methods; it does not reimplement their scientific logic.

In this exact ontobio version, `to_gaf_2_2_tsv` changes the working taxon
namespace while writing. The adapter serializes a copy so audit logging cannot
change later GAFeRence lookup keys. A real-package regression test covers this
integration issue. Earlier control failures are preserved in local receipts;
they were not biological performance comparisons.

The same installed version leaves typed `Curie` objects in extension lookup
keys, while its JSON inference loader uses full IRI strings. The released
GAFeRence parser also constructs full IRI keys. An exact source-level diagnosis
and upstream issue/code check found no existing fix for this representation
gap. A read-only mapping adapter converts only the query key, using the
official `relations.curie_to_obo_uri` API for registered extension relations and
strict `prefixcommons` expansion for fillers. Unknown relations or prefixes
fail. No identifier aliases, modified annotations, new inference entries or
rule-body changes are used. Tests exercise an actual rule13 lookup with both
RO and GOREL extension relations. The sparse proof compares these exact IRI
keys against every released-parser key before any absence is interpreted.

## Outputs and interpretation

- `base_validated_native.gaf`: official lifecycle/relation/reference QC output;
  use these exact bytes as GAFeRence input.
- `validated_native.gaf`: final output, optionally including qualified rule13.
- `native_row_changes.jsonl`: original native row/line IDs, original text and
  every resulting base-rule row, with explicit changed-column inventory.
- `official_rule_calls.jsonl`, `official_lifecycle_calls.jsonl`: actual invoked
  methods and outcomes. The upstream report can also contain auto-pass entries
  for inactive rules; those are not execution evidence.
- `official_report.json`, `taxon_rule.json`, `report.json`: original reports,
  source/version/runtime/code pins, coverage and explicit scientific limits.

Literal output changes are not automatically scientific errors. Alternate-ID
normalization, relation repair, filtering and mere serialization differences
must be interpreted separately. Filtered rows remain in the before/after
ledger; original sources and review states are never accepted or deleted here.
An unsuccessful run has only a `failure.json` and is not a sealed QC result.

The full upstream GO pipeline includes other rules and metadata. Running these
specific methods does not claim whole-pipeline conformance, calibrated truth
confidence, historical record identity or whole-graph biological accuracy.

For the published sparse format, supply `--inference-mode published_sparse_delta`,
`--inference-execution execution.json`, `--parser-coverage parser_coverage.jsonl`
and `--parser-execution coverage_execution.json`, as well as the inference file,
its SHA256 and exact prepared-GAF/ontology-version bindings. Producer and parser
receipts bind the same reviewed binary, runtime, prefix contexts, ontology and
prepared GAF. Contexts must have the same verified order in both actual
commands, as well as identical hashes; unordered file-set equality is
insufficient. Their hashes prove local byte consistency, not independent
authentication of an arbitrary supplied execution claim.

`ReleasedParserCoverage.java` calls the unmodified released `processLine` API
and emits its constructed keys for every input row. It contains no alternate
GAF parser or reasoner. Compile against the released tool's `lib/*` and run with
the same standalone ontology, input GAF and JSON-LD prefix files. This detects
skipped qualifiers or dropped extension atoms before interpreting sparse absence.

Rule13 specifically handles taxon problems. A GAFeRence extension-unsatisfiable
delta with `taxonProblem: false` does not become a taxon violation through this
runner. Its raw delta and actual lookup trace remain available for separate
extension-context diagnosis. Additional inferred terms are not added to the
application graph or counted as independent experiments.

## Existing upstream implementations

- [ontobio](https://github.com/biolink/ontobio), BSD-3-Clause; exact installed
  wheel, dependency versions and rule-file hashes are recorded in the run.
- [GO rules](https://github.com/geneontology/go-site/tree/master/metadata/rules).
- [GAFeRence](https://github.com/geneontology/gaferencer), MIT; its released
  command accepts a matched `go-gaf.owl`, GAF and JSON-LD prefix contexts.
  In the verified v0.5 binary, repeat `--contexts first.jsonld --contexts second.jsonld`.
  The help metavar shows a comma, but the actual CaseApp `List[String]` parser
  treats a comma-joined value as one filename. No custom parser is needed.

Provider inputs and derived native annotation data retain their upstream terms.
The software license does not change the full Pharos package's redistribution
boundary. No model, GPU or paid API is needed for this native QC step.
