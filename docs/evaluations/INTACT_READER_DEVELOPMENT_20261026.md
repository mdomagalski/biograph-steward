# Official IntAct reader and development suitability

October 26, 2026. The official PSI-JAMI reader is installed and validated. The
four frozen development studies have been inspected; four reserved studies
remain unopened. This is an engineering and source-suitability result, **not an
import/answer/export fidelity score or biological accuracy measurement**.

The [tracked summary](intact_reader_development_20261026_summary.json) binds the
runtime, source comparison, unchanged synthetic inventory, both control runs,
development report and all-row ledger by SHA-256. The original
[protocol](intact_fidelity_20261026_protocol.json), panel and
[mandatory expansion amendment](intact_fidelity_20261026_semantic_amendment.json)
remain unchanged.

Later follow-through on the same consumed development records completed the
[real workbench/answer/export comparison](../INTACT_EVIDENCE_WORKBENCH.md):
4/4 eligible records pass source fidelity. That separate result does not change
this reader report's original scope or establish biological accuracy.

## Reused implementation and actual controls

The bridge uses the official published `jami-mitab` and `jami-core` **3.9.4**
binaries from the EBI PSI release repository. Every Java source in their source
JARs matches the pinned upstream Git tree: 171 MITAB and 586 core files. Maven
3.10.0 and Temurin JDK 21.0.1 built and ran the bridge locally. Its six resolved
runtime dependencies and hashes are recorded; the resolved JAMI binaries match
the separately downloaded official artifacts. No GPU or model was involved.

All **30 original synthetic controls and two supplemental controls pass**
(3,193 assertions). They check exact source-side identity/isoforms and roles,
participant versus host taxonomy, negative/default semantics, missing context,
multi-valued fields, malformed records, physical row accounting and diagnostics.
The supplementary controls check lexical-error recovery between valid rows and
complete field consumption. These controls establish bounded implementation
behavior; they do not certify all PSI-MI input or factual correctness.

The first run failed on five malformed-input cases because upstream parser
prose interrupted stdout JSON. It is preserved. The pinned
[official `MitabLineParser` source](https://github.com/MICommunity/psi-jami/blob/b66f63654d5878b918aad74af60054b1be0437a8/jami-mitab/src/main/java/psidev/psi/mi/jami/tab/io/parser/MitabLineParser.java#L2183)
calls `System.out.println` during error recovery. The standalone bridge now
routes that upstream stream to retained stderr during parsing, restores stdout
in `finally`, and emits JSON through its original output stream. No parser
messages are filtered and no expected fixture values were changed.

The [bridge](../../tools/intact_reader/README.md) captures every listener event
before iterator creation and recreates the reader per physical row, avoiding
prefetch misattribution. Full field collections come from the **official public
grammar routines**, before evidence-object initializers choose one value. Raw
cells, diagnostics and the evidence-object projection remain separate. Missing
`-` cells follow the official DASH branch, and field parsing must consume its
separator and EOF. This adapts existing capabilities; it is not an alternative
biological parser.

Source review and actual controls confirm that evidence objects can truncate
multi-valued context and infer missing interactor types. JAMI also silently
maps invalid negative text such as `maybe` to false. The independent raw
true/false/`-` conformance check quarantines that input. Parser recovery values
cannot become asserted evidence. See the
[control source review](../literature/INTACT_READER_CONTROLS_20261026.md).

## Development observations

Each study's pinned bytes were verified and an exclusive exposure-start receipt
was written **before decoding**. The current passing control report, runner,
fixture inventory, Java source/classes, dependency JARs, runtime and inspection
code were bound and rechecked. The inspector accepts only the four development
PMIDs; it has no reserved-study execution option. Independent code review
preceded exposure.

A separate code-agent audit subsequently verified the four authorized source
hashes/sizes, raw rows and side orientation, all eligibility decisions, runtime
and control bindings, exposure receipts and unchanged original preparation.
It opened no reserved body and found no blocking discrepancy. This replay is
engineering verification, not an independent scientific expert assessment.

| Publication | Evidence rows | Eligible human-protein rows | Out-of-scope rows |
| --- | ---: | ---: | --- |
| 40075158 | 2 | 0 | 2 RNA |
| 40404733 | 5 | 2 | 3 involving RNA |
| 40071126 | 4 | 2 | 2 RNA |
| 40739265 | 3 | 0 | 1 RNA; 2 mouse protein |
| Total | 14 | 4 | 10 |

All 18 physical lines, including four headers, reconcile with the reader JSONL
and raw cells. All 14 evidence rows parse; no listener warnings were observed.
This is not a percentage of scientifically correct statements. Excluded rows
are retained and locatable; RNA and mouse interactions are outside the declared
human-protein task, not biological errors.

The four eligible rows have four distinct source evidence IDs, covering **two
protein pairs in two publications**. Reciprocal bait/prey observations and A/B
orientation remain distinct source rows; they are not counted as four independent
biological confirmations. Their source database is **MINT (`MI:0471`)**, as
distributed by IntAct/IMEx; the download portal must not overwrite that provenance.
Both studies report anti-bait co-immunoprecipitation
(`MI:0006`) and physical association (`MI:0915`). That does not establish direct
binding. All four negative cells explicitly say false; all expansion cells are
`-`, meaning no expansion annotation supplied and no affirmative binary-origin
claim. Real negative, default-negative and supplied-expansion strata are absent
from this eligible development subset. Their synthetic controls passed, but
real-data performance in those strata remains unmeasured.

The host fields also contain explicit cell-line labels (Hep3B, KTC-1 and CAL-62).
The raw cells and full official field collections preserve those source labels.
The bridge's abbreviated interaction-object view contains only the host taxid;
it is not the complete reference projection. A downstream answer must use the
full source context, rather than rendering all four experiments merely as
“human.” An empty warning list is not a losslessness score.

The local inspection is in `runs/intact_development_inspection_20261026/`:
`index.html`, `report.json`, `row_ledger.jsonl`, four original-reader JSONLs,
stderr files and four exposure-start receipts. Data attribution remains
IntAct/IMEx and the original publications, under CC BY 4.0.

## Remaining comparison

Build the deterministic qualified-evidence import, readable answer and export
using these development rows and the existing synthetic controls. Compare all
applicable frozen field groups and locators against direct source access, with
coverage and strict fidelity denominators including incomplete/abstained eligible
rows. No such end-to-end score was available at this reader-stage checkpoint;
the later linked workbench result records its completion.

Then commit/freeze the adapter and evaluator before reserved access. Audit
explicit shared-study provenance and participant/pair overlap before any final
score; related studies are excluded without replacement under the existing
protocol. Two development studies with no eligible rows stay in the report and
are not replaced with favorable examples. This small size-selected panel cannot
establish general scientific accuracy, novel interactions or improvement over
Pharos.

Reproduce local checks with an existing resolved classpath:

```sh
python3 scripts/validate_intact_reader_controls.py \
  --classpath-file runs/intact_reader_validation_20261026/classpath.txt \
  --classes tools/intact_reader/target/classes \
  --output runs/NEW_SYNTHETIC_CONTROL_RUN

python3 scripts/inspect_intact_development.py \
  --controls-report runs/NEW_SYNTHETIC_CONTROL_RUN/report.json \
  --classpath-file runs/intact_reader_validation_20261026/classpath.txt \
  --output runs/NEW_DEVELOPMENT_INSPECTION
```

Outputs must be new directories. Re-running development inspection records
another exposure; it does not restore an unseen holdout. Brev can remain off.
