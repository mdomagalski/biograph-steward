# Complete submission example — October 26, 2026

## Result and boundary

**The local graph-plus-ledger handoff passed engineering verification.** An
existing two-protein Pharos cohort, with its qualified assay attachment, was
exported without source changes. The resulting graph, complete edge-decision
ledger and full source packet reopen from the downloaded ZIP in a separate
temporary directory.

All two decisions remain **abstain**, with null confidence. This demonstrates a
complete submission interface, not scientific pruning, a new prediction result,
independent biological improvement or organizer approval of the file format.
No model, GPU, paid compute, new source retrieval or fresh assay outcomes were
used. Controlled pruning remains confined to the invented integrity fixtures.

The source is `runs/assay_workbench_v2_20261026`, containing UniProtKB:P22674
(Cyclin-O) and UniProtKB:P38936 (Cyclin-dependent kinase inhibitor 1). This is the
previously selected integration example, not a new case selected for a scientific
outcome. The already-consumed assay panel cannot be presented as unseen validation.

## Measured engineering result

| Item | Result |
|---|---:|
| Original and retained nodes | 2 / 2 |
| Original and retained evidence edges | 2 / 2 |
| Original and retained assertions | 2 / 2 |
| Pharos interaction annotations | 1 |
| Qualified assay observations in this cohort | 1 detected |
| Keep / prune / abstain decisions | 0 / 0 / 2 |
| Original run files checked unchanged | 62 |
| Authoritative packet input files preserved byte-for-byte | 36 |
| Files in portable handoff | 57 |
| ZIP size | 9,059,056 bytes |

The 36 packet input files include the original snapshots, graph, manifest,
licenses, reviews, assay sidecar/ledger and full 29-file assay publication.
Pharos raw requests/responses remain embedded in the original snapshot; the
source run's additional derived displays/tables are not required for this
source-bound packet. All 62 original run files were hashed before and after.

The example itself has no failed assay; separate invented tests cover preservation
of failed/non-evaluable observations, zero selected assays, controlled pruning,
all-pruned graphs with surviving nodes, mixed assertion support and stale reviews.
Nondetection is never used to prune a Pharos association automatically.

## Artifacts and reproduction

- Human-readable result: `runs/submission_demo_v2_20261026/index.html`
- Download: `runs/submission_demo_v2_20261026/submission_handoff.zip`
- Machine receipt: `runs/submission_demo_v2_20261026/verification.json`
- Resulting graph: `runs/submission_demo_v2_20261026/handoff/retained_graph.json`
- Complete decisions: `runs/submission_demo_v2_20261026/handoff/edge_dispositions.jsonl`
- Original source packet: `runs/submission_demo_v2_20261026/handoff/baseline_packet/`

Use a new output directory:

```sh
python3 scripts/verify_submission_demo.py \
  --run runs/assay_workbench_v2_20261026 \
  --out runs/submission_demo_reproduction
python3 app.py gold-decisions-verify \
  --run runs/submission_demo_reproduction/handoff
```

The reusable runner invokes the existing packet exporter, decision materializer
and verifier; it introduces no second classifier or scientific labeling rule.
It checks complete dispositions, exact source bytes, qualified evidence and
review support, preservation of context/quarantine/assay exclusions, the extracted
ZIP and unchanged original inputs/implementation files. Its JSON receipt hashes
all outputs, the original input inventory and the implementation checkpoint.
Hashes identify saved bytes; they do not authenticate biological truth.

The first attempt, `runs/submission_demo_20261026`, is preserved with a failure
receipt. On macOS the temporary-directory name used a symlinked `/var` ancestor;
the existing assay source loader correctly rejected that path. The runner now
resolves the newly created temporary directory, matching the project's existing
path handling, before loading the extracted ZIP. No source or scientific meaning
changed. The second attempt passed all 12 recorded checks.

## Checks and remaining work

The two dedicated runner tests use invented source records and verify portable
all-abstain output, local report links, preservation of excluded assay records,
immutable output behavior, rejection of unsupported source data and refusal to
seal a successful report when an input changes. The focused graph/assay tests
exercise explicit pruning and tampering without inventing real labels.

This closes the missing materialized retained-graph export and qualified assay
packet support for the demonstrated source profile. It does not complete full
KGX/Biolink mapping, an official organizer scoring adapter, intended-user
usability assessment or independent biological validation. The next assessment
must distinguish those objectives instead of treating export success as a
scientific advance.

Verification receipt SHA-256 (canonical content): `4de54272b9b6fa59fe31a155f445796c242db5835d9fcdfa32d5ac6b42bf54c0`.
Download SHA-256: `ba154a481786a2b14731af35d3cf6bffc4eeb333acc3e36cd9cae73540fc0db3`.

See [the handoff contract](../GOLD_SET_INTERFACE.md),
[assay attachment](../ASSAY_WORKBENCH.md) and
[organizer interpretation](../ORGANIZER_UPDATE_20261026.md).
