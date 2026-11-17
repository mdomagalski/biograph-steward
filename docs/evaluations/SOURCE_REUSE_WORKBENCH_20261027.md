# Source-reuse workbench delivery

October 27, 2026. The consumed two-protein workspace now displays the existing
provider trace beside its original assay evidence. This is a product/source
integration check, not a new biological evaluation.

## Result

| Attached record | Current STRING 12.5 | Original Pharos319 import |
|---|---|---|
| IM-30398-1 / EBI-67107463 | Shared curated record, based on the user's copied source link and preserved typed source identities | Unknown |
| IM-30398-5 / EBI-67107533 | Unresolved in the inspected view | Unknown |

The shared record retains its experimental context. No confidence is pooled,
record merged, association pruned or review state promoted. Repeated source
representation is not counted as independent corroboration.

Open the [published guided answer](http://127.0.0.1:8793/?run=source_reuse_workbench_20261027&question=assay_question_20261027T143229Z_2f33bd92)
while the local server is running. The source-reuse field appears in the assay
table, selected observation and answer. The report and complete workspace ZIP
are linked there. Browser layout was not visually verified in this increment.

## Existing implementation used

The adapter consumes the [existing provider trace](PROVIDER_PAIR_LINEAGE_20261027.md),
overlap ledger and captured official PSI-MI JAMI output. Identity qualifiers,
primary publication references and experiment identities follow the existing
PSI-MI/IntAct model. The [implementation guide](../ASSAY_SOURCE_REUSE.md)
links the primary methods and standards checked before implementation.
MImerge/MIscore already address evidence redundancy/scoring; no replacement
algorithm or biological scoring rule was introduced.

The new code supplies the missing workbench display, exact source binding and
portable supplement. It copies the source workspace into
`runs/source_reuse_workbench_20261027` without changing any original file. The
supplement replays from its copied proof and existing assay source, without
opening original absolute paths or executing a provider publication script.

## Verification

The [machine receipt](source_reuse_workbench_20261027_summary.json) records the
actual delivered run, question and source-reuse report hash. Checks passed for
the live source metadata, all four graph/source bindings, three artifact routes,
two-record guided answer, downloaded ZIP and extracted offline replay. Every
original workspace file remained byte-identical. The saved answer and gold
graph/decision exports retain their existing formats; the audit travels in the
normal workspace ZIP.

Targeted checks passed: 15 source-reuse tests, 14 HTTP tests, 83 related
non-HTTP Python tests and 27 assay/construction JavaScript tests. Cases include
portability without original directories, exact identity and method/publication
checks, authenticated downloads, symlinks, partial/tampered supplements,
recomputed-but-false classifications and stale asynchronous UI responses.
The loopback HTTP tests required execution outside the network sandbox. The
delivery script used a resolved temporary path, preserving the existing
symlink guard rather than weakening it.

The earlier IntAct overlap report, Pharos400 source supplement and consolidated
provider report all passed their existing offline verification unchanged.
No new source retrieval, model calls, GPU use or fresh reference-body access
occurred.

## Remaining assessment

The user's copied STRING link is not a machine-captured browser observation.
Historical provider/build inputs, reuse of the second record and exact Reactome
IDs supporting STRING remain unresolved. Current source reuse does not settle
those questions. The next scientific step remains a defined qualification
intervention compared with simple addition of the same information, under a
separately reviewed evaluation freeze. The four fresh studies remain unopened.
