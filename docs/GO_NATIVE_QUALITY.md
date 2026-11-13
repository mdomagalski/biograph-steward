# Inspecting and checking native GO annotations

The historical Pharos projection lacks fields needed to identify its original
GOA rows. The current native GOA records can still be used as their own
versioned source. Keep these roles separate: inspect the historical record,
inspect a current annotation, or inspect an explicitly normalized derivative.
None establishes independent experimental truth by itself.

## Optional source inspection in the app

The [native GO workbench guide](NATIVE_GO_CONTEXT_WORKBENCH.md) explains the
on-demand source inspector, its operator configuration and worked NRAS cases.
It reuses the existing dependency-free source loader and separately bound
saved official QC output. Original rows, NOT qualifiers, references, forms and
context alternatives remain intact; normalization and context warnings do not
repair the historical Pharos record or establish biological truth.

The feature is disabled by default. Configure `BIOGRAPH_GO_CONTEXT_DIR` and,
optionally, `BIOGRAPH_GO_QC_DIR` as separate complete ordinary directories
outside the strict saved workspace. The web request checks original source
lines and saved output consistency; it does not rerun Biopython, GO rules or
the reasoner. The [private hosted `ea5752e` workspace](evaluations/hosted_native_go_20261113_summary.json)
has both packets configured and passed restart/API acceptance. Fresh software
installations remain unconfigured. The native CLI and methods below retain
their original scope.

The [portable source-packet download](NATIVE_GO_PORTABLE_EXPORT.md) keeps these
12 unchanged source/QC files separate from the ordinary workspace ZIP. Its
local export/extraction replay reopened both NRAS examples identically without
rerunning the pipeline or changing any original input. Both source and QC
must be configured for the download; a software checkout alone is insufficient.

## Explain historical mismatches

`qualify-go-context` retains its exact five-field compatibility rule. It now
also lists every native record with the same exact protein and GO ID, together
with differing evidence, assigning-source or aspect fields. These are
diagnostics, not broadened matches. No source alias is applied and no preferred
native row is chosen.

In the executed CRC inventory, 1,351 of the 2,930 unmatched records have a
current exact protein–GO pair but differ in the other fields. The remaining
1,579 have no exact protein–GO pair in that source: 298 use obsolete terms and
1,281 use active terms. Absence from the current GAF does not make the historical
annotation false. Exact restoration requires the missing historical source
release/record keys; an approximate string join cannot supply them.

## Inspect a current native source

Use the existing optional Biopython 1.88 environment:

```sh
.venv-go-audit/bin/python app.py go-context-inspect \
  --context runs/my_go_context --protein UniProtKB:P15056 \
  --go GO:0004674 --out runs/my_braf_current_go
```

Omit `--go` to inspect all preserved annotations for that protein. The reader
checks the sidecar's complete byte inventory, original GAF line bindings and
exact-subject completeness. It then uses the actual native parser to replay
the queried protein. References, NOT, protein forms and AND/OR context stay
attached to their own records. Unknown/out-of-scope results do not imply
biological absence. The original Gold graph is not revalidated by this reader.

The query does not expand the preserved protein cohort, infer ancestors,
collapse isoforms or add independent evidence votes. It leaves the Pharos
qualifiers unchanged and reports all matching source records.

## Execute the published GO quality rules

The optional [official-QC adapter](../tools/go_qualification/run_official_qc.py)
runs the installed `ontobio==2.9.12` implementation. It supplies pinned ontology,
ECO mapping and retraction inputs and preserves the original and normalized
GAF rows. It does not implement substitute rule bodies.

```sh
python3.12 -m venv .venv-go-quality
.venv-go-quality/bin/python -m pip install -r tools/go_qualification/requirements.txt
.venv-go-quality/bin/python tools/go_qualification/run_official_qc.py \
  --qualification runs/my_go_context \
  --ontology /path/to/go-basic.json.gz --ontology-sha256 VERIFIED_SHA256 \
  --retracted-refs /path/to/retracted-publications.txt --retracted-sha256 VERIFIED_SHA256 \
  --eco-mapping /path/to/gaf-eco-mapping.txt --eco-sha256 VERIFIED_SHA256 \
  --eco-derived-mapping /path/to/gaf-eco-mapping-derived.txt --eco-derived-sha256 VERIFIED_SHA256 \
  --out runs/my_native_go_quality
```

The selected checks cover:

- The official parser's obsolete/alternative-ID handling, including GO IDs in
  annotation extensions and With/From. Explicit replacements can be applied to
  this normalized native derivative, with every original row preserved.
- [GORULE:0000022](https://github.com/geneontology/go-site/blob/master/metadata/rules/gorule-0000022.md):
  exact references against the supplied retraction list. The list has its own
  release/capture boundary; passing does not certify every paper's validity.
- [GORULE:0000061](https://github.com/geneontology/go-site/blob/master/metadata/rules/gorule-0000061.md):
  permitted gene-product-to-term relations under the supplied GO ontology.

The adapter records actual rule method calls. A generic PASS entry for a rule
that was not selected must not be reported as successful validation. Source
versions, runtime dependencies and any serialization or semantic changes remain
explicit. Native-source normalization does not repair unknown historical
Pharos record identities or transfer their reviews to another claim.

## Taxon constraints need actual inference data

[GORULE:0000013](https://github.com/geneontology/go-site/blob/master/metadata/rules/gorule-0000013.md)
requires applicable inference results. A missing or unrelated inference table
must not count as a pass. Generate results using the published GAFeRence tool,
the matching `go-gaf.owl` and the exact prepared `base_validated_native.gaf`.
Pin the input/output bytes and execution receipt before supplying them to QC.

GAFeRence v0.5 emits a sparse delta: ordinary satisfiable keys with no additional
inference are omitted. Absence from an arbitrary table cannot therefore be
treated as a successful check. The published-sparse mode requires the exact
source GAF SHA256, native ontology version, successful reasoner execution
receipt and a separate receipt/output from the released parser. That audit
calls the unmodified parser and must reproduce every non-NOT prepared
annotation's semantic keys, including its extension groups. No passing entries
are fabricated to fill the sparse table. A valid empty delta is usable only
with this complete provenance and coverage proof.

NOT exemptions and experimental-evidence warnings remain distinct from
nonexperimental exclusions under the official rule. A complete taxon run is
reported only after the checks succeed. See the optional runner's `--help`
for the inference, execution and parser-coverage arguments.

These are selected GO checks, not full GO pipeline conformance, a clinical
recommendation, a calibrated confidence score or a whole-graph accuracy test.

The [executed CRC assessment](evaluations/SCIENTIFIC_LIMIT_RESOLUTION_20261112.md)
covers 15,888 native annotations. It reports nine relation repairs and 49
alternative-ID extension normalizations, with no taxon violations detected.
GAFeRence also identifies ten extension-unsatisfiable semantic keys affecting
13 annotations. Those are a separate diagnostic scope: GORULE13 handles taxon
problems and does not filter these non-taxon cases. The source trace includes
four records whose cell-context identifier disagrees with the cited study's
methods. The dossier proposes withholding that context from inference pending
curation; it does not replace the identifier or reject the base association.

The actual runtime also exposed typed CURIE versus full-IRI extension lookup
keys. The optional adapter uses the installed official relation/prefix APIs at
the lookup boundary and checks the result against every released-parser key.
Unknown conversions fail; no annotations, inference entries or rule bodies are
rewritten to make coverage pass. See the runner's [method and constraints](../tools/go_qualification/README.md).

## What an accuracy estimate still requires

A complete gold label for every graph assertion is not necessary.
[Published KG accuracy evaluation](https://www.vldb.org/pvldb/vol12/p1679-gao.pdf)
uses probability samples and independent correctness judgments; more recent
[interval-estimation work](https://doi.org/10.1145/3725279) addresses inference
from those judgments. Sampling reduces review effort, but does not create
the correctness labels. Unvalidated LLM agreement would measure agreement
with that model, not independent biological accuracy.

The smallest remaining external input is qualified review of a fixed sample
in a declared claim scope. Use complete qualified assertion identities,
preserved evidence dossiers, explicit indeterminate outcomes and appropriate
sampling weights/dependence handling. A source-annotation-existence predicate
must not be reviewed as if it asserted an unqualified positive biological
function. Repeated supporting records are not independent biological facts.

The existing Gold/reference interface can preserve sampled identities and
returned judgments. No accuracy estimate or new sampling protocol is implemented
by these native-source tools. Suitable pre-existing expert labels could replace
review only where they match the actual claim and have a qualified source
relationship; a different database name is not proof of independence.
