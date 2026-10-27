# Isolated official IntAct MITAB reader bridge

This developer helper wraps the unmodified **PSI-JAMI `jami-mitab` 3.9.4**
interaction-evidence reader. The published sources match pinned upstream commit
`b66f63654d5878b918aad74af60054b1be0437a8` (171 MITAB and 586 core Java files).
It uses Gson 2.13.2 for explicit-map JSON serialization and Java release 11.
JDK 21 is the local validation runtime. This is not a new biological parser,
ontology mapper, eligibility grader, standards validator or scientific evaluator.

The dependency is published in the official
[EBI PSI release repository](https://www.ebi.ac.uk/Tools/maven/repos/content/repositories/pst-release/psidev/psi/mi/jami/jami-mitab/3.9.4/jami-mitab-3.9.4.pom),
not Maven Central. JAMI and Gson declare Apache-2.0. Reference interaction data
retain their separate CC BY 4.0 attribution requirement.

Build with the task's pinned Maven and isolated local repository, for example:

```sh
runs/intact_reader_validation_20261026/tooling/apache-maven-3.10.0/bin/mvn \
  -f tools/intact_reader/pom.xml \
  -Dmaven.repo.local="$PWD/runs/intact_reader_validation_20261026/m2" \
  compile
```

The controlled runner must construct and record the resolved classpath, runtime,
artifact hashes and source/contract receipts before invocation:

```sh
java -cp "tools/intact_reader/target/classes:RESOLVED_DEPENDENCY_CLASSPATH" \
  org.biograph.IntactReader PATH_TO_AUTHORIZED_LOCAL_SYNTHETIC_OR_DEVELOPMENT_FILE
```

This helper accepts one local regular file and has no network/enrichment API.
It does not authorize opening a reserved reference file. The orchestration layer
must replay the frozen preparation and mandatory semantic amendment, validate
synthetic controls, and enforce the authorized publication split first.

## Output contract

One JSONL record is emitted for every physical input line, including header,
comment, blank, malformed and unparsed lines. Each record contains:

- `line_number`, `raw_line`, `raw_cells`, `row_status`, `parsed_count`.
- `diagnostics`: every official listener callback, its argument class names,
  available public message and source locators. Bridge framing/errors have
  separately named `bridge_*` callbacks. Parser line numbers refer to the
  one-row reader; locators also retain the original physical input line.
- `interactions`: explicit JAMI-only projections; `interaction` duplicates the
  sole projection when exactly one interaction was returned, otherwise null.
- Interaction projections contain `negative`, original `negative_raw` and
  `expansion_raw` cells; detection method/type; host taxonomy; publication/source
  and evidence identifiers; annotations; and participant projections.
- Participant projections contain source-located A/B side, exact unique-ID,
  alternative-ID and type raw cells; JAMI preferred/other identifiers, aliases,
  taxonomy, type, separate biological/experimental roles, identification methods,
  features and ranges, stoichiometry, annotations and xrefs.
- `source_fields` contains full per-cell collections returned by the official
  grammar's `ids`, `cvTerms`, `taxId`, `sourceDbs`, `complexExpansion` and
  `annotations` routines, before the row object's first-value selection. Each
  entry contains `column`, `raw`, `status`, `values`, `diagnostics`. Its parser
  must consume the whole cell followed by exactly one separator and EOF.
  Diagnostic phases distinguish `source_field`, `row_model` and bridge framing.
  These source collections remain separate from the potentially lossy row model.

`CvTerm` projections use `mi_id`, `mod_id`, `par_id`, `name`, `full_name`.
Xrefs use `database`, `id`, `version`, `qualifier`. Nulls remain explicit. The
projection does not recursively serialize model graphs or invent missing fields.
Participant side comes from the official participant's MITAB source locator,
not collection order or matching aliases. If unavailable, side/raw-side fields
remain null for later quarantine rather than guessing.

Application framing requires exactly 42 cells and is separately reported as
`mitab27_framing_valid`. For controlled synthetic compatibility observations the
official row reader is also invoked on other column counts, without padding or
changing the input. Such a row remains `invalid_column_count` even if the official
reader accepts an older MITAB format; `official_reader_status` and `parsed_count`
describe that observation. `source_fields` is only produced for the declared
42-column format. No non-42-column observation is eligible for the frozen panel.
Cell contents are
interpreted exclusively by JAMI. Raw text and cells stay alongside the structured
projection because the author model can infer types and retain only the first of
some multi-valued terms. A warning or a source/model mismatch is not repaired.
An absent expansion annotation never establishes true-binary experimental origin.
JAMI's `negative=false` for a raw `-` retains its source-default provenance through
the raw cell; it is not evidence that every possible interaction is true.

The official reader is recreated per physical data row, with the listener
attached before iterator creation. This avoids misattributing diagnostics caused
by JAMI's eager prefetch. The reader can report and skip bad input; `unparsed`,
diagnostics and raw row accounting expose that behavior rather than dropping it.
Read/encoding failures terminate the process visibly; upstream parsing/projection
failures remain in the affected row record. Stored source hashes preserve exact
input bytes; `raw_line` intentionally excludes its physical newline delimiter.

The pinned author's
[`MitabLineParser.error_skipToNext()`](https://github.com/MICommunity/psi-jami/blob/b66f63654d5878b918aad74af60054b1be0437a8/jami-mitab/src/main/java/psidev/psi/mi/jami/tab/io/parser/MitabLineParser.java#L2180-L2184)
prints parse-error prose directly to `System.out`. During field and row parsing,
this single-threaded command routes the upstream standard-output stream to
stderr and restores the original stream in `finally`; JSONL is emitted through
the saved original stream afterward. No prose is filtered, parsed away or
discarded. The controlled runner must preserve raw stderr alongside JSONL and
listener callbacks. This transport routing is scoped to the standalone helper;
it is not intended as a process-global setting in an embedded concurrent service.

No call to this bridge, schema-valid object, or successful parsing certifies
biological truth, IMEx curation of newly generated data, full PSI-MI conformance
or an independent improvement over Pharos.
