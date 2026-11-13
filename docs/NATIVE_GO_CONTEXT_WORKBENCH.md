# Native GO context in the evidence workbench

The optional source inspector now puts already preserved GO annotations and
their saved official quality checks beside an exact selected GO claim. It
addresses an interpretation gap: the available Pharos fields omit the native
relation, NOT qualifier, references, product form and annotation extensions.
Those fields are now inspectable as **separate versioned source context**;
they are not copied into the historical Pharos record.

The implementation reuses the existing native-source loader and recorded
ontobio/GAFeRence outputs. It adds no classifier, model call, threshold,
biological prediction or new correctness label. The underlying methods and
earlier executed results remain in [native GO quality](GO_NATIVE_QUALITY.md)
and the [scientific assessment](evaluations/SCIENTIFIC_LIMIT_RESOLUTION_20261112.md).

## Enable one explicitly bound source frame

The core feature is disabled by default and needs only Python/CPU when enabled.
The complete source sidecar and saved QC output must already be available.
For the local preserved CRC packet:

```sh
BIOGRAPH_GO_CONTEXT_DIR="$PWD/runs/crc_go_context_qualification_v3_20261112" \
BIOGRAPH_GO_QC_DIR="$PWD/runs/go_pipeline_reuse_20261112/native_qc_sparse_v3" \
python3 app.py serve --runs-dir runs --host 127.0.0.1 --port 8765 --no-browser
```

The native source and QC are separate ordinary directories with unchanged
strict inventories. Keep both outside `source_faithful_workspace_20261113` and
outside one another. The browser cannot choose either path. The native source
can be configured alone; the UI then reports that QC is unavailable and does
not imply a pass. A configured invalid source or QC output fails closed.

These packets are not in Git or a fresh checkout. The
[private hosted update](evaluations/hosted_native_go_20261113_summary.json) runs
`ea5752e` with the approved, separately installed 12-file native/QC packet.
Its two configured source paths are outside the saved workspace. API acceptance
checked the two NRAS cases across a real restart; the earlier local Chrome
walkthrough remains separate from these hosted API checks. The original graph,
question, publications and authentication are preserved. Fresh installations
remain unconfigured. Brev, its model, a GPU, a paid literature API and fresh
source retrieval are unnecessary.

## Walk through the source

1. Open the supplied saved workspace in the app.
2. In **Evidence & sources**, find a GO annotation and choose **Guide me through
   this source**.
3. Choose **Inspect preserved native GO annotations**. This is an on-demand
   read-only query for the selected protein and exact GO term.
4. Inspect the original native relation, positive/NOT polarity, references,
   evidence code, taxon, product form and extension alternatives.
5. Read any separately labeled normalization or context warning. Expand the
   row's QC details for rule IDs and original/derivative values, and the source
   provenance for the ontology and retraction-table versions.

All same-protein/same-term native rows remain visible. Rows compatible with the
exact five available Pharos fields are distinguished from related native rows
whose projection fields differ. A unique compatible row still does not prove
that it was the historical source. Multiple reference IDs can name one reference;
rows, database labels and repeated studies are not independent votes. No match
means UNKNOWN within this preserved frame.

## A concrete source-quality example

The retained workspace contains an NRAS annotation for **GO:0005794 (Golgi
apparatus)**. Its available Pharos fields do not supply the original relation.
A separately preserved native GOA row uses `part_of`. The already executed
[GORULE:0000061](https://github.com/geneontology/go-site/blob/master/metadata/rules/gorule-0000061.md)
normalizes the current native derivative to `located_in`. The inspector shows
that exact before/after difference and the recorded warning. It preserves the
original GOA row, original Pharos annotation and local review state.

This makes a concrete semantic correction inspectable. It does not establish
historical row identity, an independent experimental replication, or a finding
that NRAS's Golgi association is false. The same rule is reusable for other
compatible packets; no NRAS-specific scientific rule was introduced.

For **NRAS/GO:0070062**, the source also illustrates the difference between
taxon validity and context validity. The saved reasoner reported at least one
combination of context terms as unsatisfiable under the pinned ontology, with
no taxon problem. The UI exposes that warning separately from the taxon result;
it does not declare the base annotation false or apply a replacement cell ID.
Other OR alternatives can differ. The earlier paper-context review remains its
own AI-assisted source assessment, not an independent expert label.

## Verification and scope

The existing complete native frame has 15,888 source records. Its saved QC
contains nine relation changes, 49 extension alternative-ID normalizations and
13 records with a reported non-taxon unsatisfiable context conjunction. These
are different findings and are not pooled into a biological error count.

The 49 extension normalizations concern current native RAD21/TRRAP annotations
for GO:0005515, which have no selected GO claim in the active 99-target graph.
Their presence in the whole native frame does not authorize adding that claim
or copying its qualifiers into a different historical term. The UI's exact
query scope remains unchanged; the full native CLI can inspect those annotations
under their own identity.

The consumer verifies the source's exact GAF lines and complete native frame,
then binds every QC change to its native record ID, source line and raw source
text. It checks the normalized GAF against the recorded changes and shows
actual selected rule calls. It preserves sparse null satisfiability values and
NOT exemptions. Execution-receipt content seals and their file-byte hashes
remain different digest domains. No report-named arbitrary path is opened.

These web requests replay original source bytes and saved output consistency;
they do not rerun Biopython, ontobio or the reasoner. Passing checks remain
relative to the pinned source, ontology and retraction table. Integrity checks
do not authenticate the publisher or supply independent whole-graph truth.

The [sanitized replay receipt](evaluations/native_go_workbench_20261113_summary.json)
records actual source-frame and selected-claim checks, including ineligible
RAD21 display scope. Source graphs, native packets, earlier failures and
scientific results remain unchanged. The feature improves interpretation of
known source issues; it does not establish a prediction gain or enable automatic
biological pruning.

The [release checks](evaluations/native_go_release_checks_20261113_summary.json)
record the full core/JavaScript checks and actual Chrome inspection of the two
NRAS examples locally. The separate hosted receipt records deployment and API
acceptance; no new hosted browser walkthrough is claimed. Exact GO IDs are
searchable alongside displayed claim labels. The older three-root recovery
check does not cover this later native GO attachment.
