# Compare evidence snapshots and preserve compatible reviews

This increment compares two **already saved, ordinary workbench runs**. It performs no source retrieval, model inference, scientific adjudication or automatic pruning. It implements the first maintenance step in the [Pharos value review](PHAROS_CONSTRUCTION_AND_VALUE.md), using existing source-record → evidence-edge → assertion links.

## Use in the app

Open **Compare saved evidence snapshots**, select the earlier reviewed run and the newer retrieved run, then choose **Compare snapshots**. The optional **Carry compatible prior reviews** checkbox creates inherited decisions only where all compatibility checks pass. It is off by default. The resulting graph is saved in a new run, with links to the comparison report and a self-contained source/export packet. The original runs and saved question answers remain unchanged.

Use **Saved comparison history** in the same panel to reopen existing reports. It lists comparison packets directly under the runs directory and inside up to three directory levels, including returned deployment packets. Symlink directories are excluded. Each entry distinguishes saved-file integrity from compatibility with the current implementation. Opening an archive performs no new comparison, retrieval, model call or review action.

Comparison does not refresh the API cache itself. Retrieve a new run through the existing controls first, preserving the same declared scope when you want a comparable pull. A reported source version and response hashes identify observed inputs; they do not establish an atomic upstream snapshot or independently authenticated source release.

## Command line

```bash
python3 app.py refresh-compare \
  --before runs/earlier_reviewed_run --after runs/new_source_run \
  --out runs/snapshot_comparison

# Explicitly preserve eligible decisions, with new carryover provenance.
python3 app.py refresh-compare \
  --before runs/earlier_reviewed_run --after runs/new_source_run \
  --carry-reviews --out runs/snapshot_comparison_with_reviews

# Replay from preserved inputs without either original parent directory.
python3 app.py refresh-verify --run runs/snapshot_comparison_with_reviews
```

Use an empty output directory outside both inputs. This version supports `biograph-steward.pharos.v1` disease-workbench runs; the experimental explicit-ID 512-gene panel is a different format and is not accepted. Source snapshots, saved graph, manifest and any reviews/CIViC sidecar must be available.

## Interpreting differences

Every assertion has two separate fields:

| Field | Meaning |
|---|---|
| `observed_change` | Exact qualified assertion identity/content is unchanged, changed, added or removed from the two saved representations. |
| `status` | That observation, or `not_comparable` when scope, policy or relevant coverage prevents a comparable interpretation. Reasons remain visible. |

“Removed” means absent from a comparable pull. It does not establish a retraction, contradiction or biological invalidity. A changed value or qualifier can change assertion identity: expression changes may appear as an added and removed pair rather than one changed assertion. This version does not infer correspondence from similar labels or unstable local source IDs.

The comparison checks data kind, endpoint, exact disease, query settings, selected protein identities and context scopes. Relevant completeness checks use target count reconciliation and per-protein/per-family status, reported/retrieved/retained counts, limits and issues. Preview pathway lists lack sufficient completeness evidence; missing rows there remain non-comparable. Failed, capped, inconsistent or differently scoped retrieval cannot establish a comparable removal.

Known differences in source releases remain inspectable as observations, but unknown or changed live Pharos versions block review carryover. Identical synthetic fixtures have an explicit software-only exception; they attest no upstream biology.

## Review carryover is an inherited decision

Eligibility requires an existing earlier review history, an unreviewed target assertion, compatible scope/coverage/policy, unchanged assertion/evidence semantics and compatible source version. Comparing only the assertion ID or revision would miss structural-status changes and source-record multiplicity, so the compatibility signature also covers these fields and relevant endpoint context. Retrieval timestamps and source locators remain traceable without alone constituting changed evidence.

Saved transformation metadata must agree, and the saved graph must agree with current replayed semantics. This verifies the recorded output contract; it does not attest the historical source-code version that created the original graph. Ordinary legacy review replay still rejects events bound to another snapshot.

Eligible source lifecycle transitions are reconstructed through the normal review validator as new target-bound events. Each records the tool as actor, original event and event hash, source/target bindings, comparison hash and `fresh_human_adjudication: false`. Original actor, timestamp and reason remain in the original event. Existing target reviews are never overwritten, and changed assertions keep the newer run's state.

For CIViC response assertions, this version requires the exact same complete sidecar and manifest binding. A freshly retrieved unversioned sidecar is not automatically eligible. Adding or changing CIViC does not by itself invalidate compatible Pharos assertions.

This first version supports **one carryover step**. Runs produced by an earlier snapshot comparison, or already containing inherited review events, are rejected as parents until recursive proof preservation is implemented. Do not remove migration metadata to bypass that restriction. Independent-study counts remain unknown.

## Export and verification

The new run contains the normal graph/source exports, plus:

- `refresh_comparison.json`: source bindings, compatibility decisions, per-assertion deltas and eligibility blockers.
- `refresh_report.html`: readable comparison, source pointers, limitations and full inherited-event provenance.
- `refresh_inputs/before/` and `after/`: byte-preserved minimal parent snapshots, graphs, manifests, review files and optional CIViC sidecars.
- `refresh_receipt.json`: file inventory/hashes, implementation identities and deterministic execution metadata.

Verification checks saved bytes, current implementation identity, comparison reconstruction, generated review events, result graph and readable report. It works after the original parent directories move. Current code changes deliberately make an old receipt require its matching implementation for verification. Hashes detect changed artifacts; they are not signatures, reviewer authentication or biological validation.

The app checks comparison integrity and current replay before serving its live graph, replayed report or ZIP. Missing/incomplete receipts are rejected. A current-implementation mismatch returns HTTP 409 with `refresh_runtime_mismatch` and an archive link; changed saved bytes still fail verification. The pinned-version guard is unchanged: an archive cannot be opened as a current graph or used to bypass replay.

The separate read-only archive checks the receipt digest, exact file inventory, every recorded file hash, preserved-parent bindings, execution-policy fields and comparison identity. It does **not** reconstruct the comparison using today's code. The archived report receives a visible response-only notice; its saved file and receipt remain untouched. Linked source records remain accessible inside the archive. Hashes are relative to an unsigned local receipt, so passing them establishes neither source authenticity nor scientific correctness. Changed or incomplete packets are listed as failed and their contents are withheld. The history view does not imply a successful current replay, even when code hashes match.

Protected hosting applies the existing authentication and origin rules. The HTTP interface is `POST /api/refresh-compare` with exact `before_run`, `after_run` and boolean `carry_reviews`, plus `GET /api/refresh/<run_id>/` for the replayed report. `GET /api/refresh-history` lists archives and `GET /api/refresh-archive/<archive_id>/` opens a read-only report; opaque archive IDs bind to safe relative paths below the runs directory. Snapshot source text is escaped in reports, and archive responses disable scripts and forms. Existing comparison outputs are excluded from parent selection because recursive carryover remains unsupported.

## What this demonstrates

Controlled fixtures test selective re-review, eligible unchanged-review preservation, coverage safeguards, history replay, immutable inputs, portable exports and tamper rejection. They measure software maintenance behavior. They do not establish experimental independence, clinical accuracy, prospective source-change reliability or biological prediction improvement.

The [October 20 live Brev comparison](EXPERIMENT_HISTORY.md#reopening-an-archived-file "Archive file: docs/evaluations/PHAROS_LIVE_REFRESH_20261020.md") now checks two fresh, matching 99-protein pulls. All 15,671 assertions remained unchanged candidates, with zero deltas or non-comparable assertions. Independent replay and protected HTTP/export verification passed. No prior live reviews existed, so real human-review carryover remains untested. Back-to-back consistency does not establish successful detection of a later source update. Prospective update validation and usability review remain subsequent checks.

See the [earlier October 20 validation record](EXPERIMENT_HISTORY.md#reopening-an-archived-file "Archive file: docs/evaluations/SNAPSHOT_REFRESH_20261020.md") for test counts and the synthetic walkthrough. Its deployment boundary describes that earlier checkpoint; the live comparison records the subsequent Brev deployment.

The source-chain and revision concepts follow [Biolink RetrievalSource](https://biolink.github.io/biolink-model/RetrievalSource/) and [PROV-O](https://www.w3.org/TR/prov-o/). These standards guide the local contract; full RDF/Biolink conformance is not claimed.
