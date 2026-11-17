# IntAct correction through the complete workbench flow

The standards-supported identity-comparator correction now passes a complete
development replay on the four studies already opened by the stopped assessment.
Both source-eligible observations survive native Pharos construction, assay
attachment, the readable cited answer and the exported source packet. This
closes the known integration defect on consumed material. It is not a new
reserved score, scientific-accuracy result or biological improvement.

The [tracked result](intact_consumed_flow_20261027_summary.json) binds the
contract, original outcome, implementation archive, source records, result and
independent automated review. The [original stopped assessment](INTACT_FINAL_ASSESSMENT_20261027.md)
and [component diagnostic](INTACT_IDENTITY_PROJECTION_DEVELOPMENT_20261027.md)
remain separate historical checkpoints.

## Verified issue and remedy

The original comparator expected all MITAB interaction identities, but compared
them with an XML helper deliberately restricted to IntAct/IMEx identifiers.
The official XML records already preserve structural database identifiers.
The [pinned IntAct manual](https://github.com/intact-portal/intact-portal-documentation/blob/b5d5bb35365739d4942e9ca250a2cf4fbaa14c62/docs/curation-manual/interaction.md)
and [MITAB 2.7 specification](https://psicquic.github.io/MITAB27Format.html)
support database-qualified interaction identities beyond IntAct/IMEx.

The existing correction includes identity-qualified references (MI:0356), plus
IMEx-primary references (MI:0662), in the alias comparison. It leaves the narrow
IntAct/IMEx record join and all other field checks unchanged. Generic see-also
and method citations do not become identities. All original comparisons remain
beside their corrected counterparts; exactly the three previously diagnosed
alias comparisons change. No reference projection errors remain in this replay.

## Complete replay result

| Study PMID | Physical rows | Evidence rows | Source-eligible rows | Full-flow strict fidelity |
|---|---:|---:|---:|---|
| 39833857 | 4 | 3 | 0 | Not evaluable |
| 40211762 | 3 | 2 | 0 | Not evaluable |
| 39972491 | 4 | 3 | 0 | Not evaluable |
| 40555359 | 7 | 6 | 2 | 2/2 |
| Total | 18 | 14 | 2 | 2/2 |

All physical rows and all exclusions remain preserved. The two eligible rows
represent one protein pair in one publication; they are not two independent
studies. The source's explicit positive/negative state, assay context, roles,
features, stoichiometry, missing values and complete raw columns remain intact.
All eight field groups pass raw, structured and readable checks. No field error
was detected. Empty negative and expansion strata remain unevaluated.

The replay uses the ordinary application publication, attachment, saved-run,
answer and export APIs. The independent oracle reads the preserved official
reader and complete source ledger rather than constructing its expectations
with the application adapter. It checks the complete output inventory before
scoring a pair batch. Downstream failures would remain misses in the same
source-eligible denominator; no failure or zero-eligible study is replaced.

All 14 output/inventory checks and all 70 copied-source-file checks pass. The
exported packet reopens through the ordinary verifier. Seven read-only Pharos
queries supplied a fixed PPI context for the one exact pair. The frozen limits
allow at most 14 queries, seven per pair, with no retries or cache fallback.
No new IntAct download, Java reader, model inference or GPU work ran.

## Preserve history and disclose exposure

Before active application code changed, all 71 original implementation files
were copied and verified against the stopped execution freeze. Their Git
checkpoint is `720beeafdc0be63cca7a2fcce7de7f5cfc203f43`. The archive receipt,
original freeze and new consumed contract travel in the publication and exported
source packet. The current application advances deliberately; it no longer
claims to match the old execution's implementation hashes. Reproduction of that
old execution uses its archived implementation or Git checkpoint.

The successful consumed replay also has an exact 79-file implementation archive.
After that execution, only a test fixture changed to remove its dependency on
ignored local metadata folders. The production application and replay runner
remain unchanged. All 16 new controls then passed in a copied source tree with
no run artifacts present. The replay's original code pins and result are not
resealed to describe this later test cleanup.

The new contract was sealed before reading the captured streams. Publication,
attachment and export explicitly carry `consumed_reserved_replay`; the source
viewer displays the consumed-data notice. Known consumed studies remain in this
engineering replay's denominator. They are not treated as independent test data.
The bounded provenance check found no unresolved explicit dataset-link statement,
but study independence and broader Pharos/STRING reuse remain unverified.

The stopped original assessment, its source bytes, outcome and one-shot access
marker remain unchanged. A successful replay cannot turn that stop into a
successful final result.

## Next assessment boundary

The [fresh selection](FRESH_INTACT_REFERENCE_20261027.md) includes all four
remaining metadata-eligible studies from the original directory, without
biological or outcome filtering. Their interaction bodies, abstracts, protein
identities and outcomes remain unopened. The
[expanded consumed inventory](intact_consumed_inventory_v2_20261027.json) records
all eight opened IntAct studies and the existing historical anchors, with 28
primary participant identities, 22 pair views and 56 qualified evidence aliases.

Before fresh access, freeze the complete execution, source and transport caps,
reader/runtime, source eligibility, qualified-lineage rules, independent oracle,
deterministic questions and all denominators. Keep zero-eligible studies and
failures without replacement. Even a successful new assessment would measure
source preservation on that bounded reference. Biological improvement still
requires a separately justified measured-link comparison. Neither step requires
Brev unless model or graph-learning inference is explicitly scheduled.

The expanded inventory does not itself widen the historical lineage auditor's
narrow IntAct/IMEx identity query. A future assessment must explicitly freeze
the complete qualified-alias overlap check as well as the supplied inventory;
unqueried structural aliases cannot be described as audited disjointness.

## Saved artifacts

- Contract: `runs/intact_consumed_flow_20261027_attempt_01/consumed_flow_freeze.json`
- Result: `runs/intact_consumed_flow_20261027_attempt_01/execution/report.json`
- Cited answer: `runs/intact_consumed_flow_20261027_attempt_01/execution/batch_0001/answer/report.html`
- Source publication: `runs/intact_consumed_flow_20261027_attempt_01/execution/publication/index.html`
- Reopenable graph packet: `runs/intact_consumed_flow_20261027_attempt_01/execution/batch_0001/packet/`

These local run artifacts are ignored by Git; the tracked summary retains their
exact hashes and scope. Historical and fresh references are not silently bundled
into a checkout.
