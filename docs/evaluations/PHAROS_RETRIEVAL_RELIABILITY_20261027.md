# Pharos retrieval reliability — 27 October 2026

The consumed engineering check completed **8/8 eligible observations across all four original exact pairs**, with no source-field mismatch detected. One real PPI-query timeout recovered through the existing native retry loop. The unchanged original fresh assessment remains **4/8**; these results are separate and are not pooled.

## Diagnosis and existing solutions

Both original failures occurred at the identical global `SourceLicenses` query, before any target or PPI query. The same query subsequently succeeded for the other two batches. The ordinary `PharosClient` already supported two retries, exponential backoff and a timestamped, hash-verified, successful-response cache. The frozen fresh transport intentionally used zero retries and no cache.

Before changing code, we inspected the current client and public upstream documentation/code. Pharos’s [source-count resolver](https://github.com/ncats/pharos-graphql-server/blob/3feb5ac7e450b3c6b767651f0fe1f39994085380/src/resolvers.js#L335-L356) performs global joins/counts/grouping even for license-field selection; we have not verified the deployed server commit. The bounded upstream issue search found no matching timeout issue, which does not rule out an incident. [Python 3.12 urllib documentation](https://docs.python.org/3.12/library/urllib.request.html) describes timeouts on blocking operations and participating environment/system proxy settings. [AWS’s retry guidance](https://aws.amazon.com/builders-library/timeouts-retries-and-backoff-with-jitter/) supports bounded retries at a single layer with backoff. None identifies the cause of our timeouts.

The implementation reuses the existing retry loop and cache. The small client extension records actual native attempt boundaries, timing, failure stage and retry decisions. It does not introduce another HTTP library, a second retry layer, a different biological scope or an alternative evidence projection. Injected transports and cache hits remain outside native retry observation.

## Actual live outcome

| Measure | Result |
| --- | --- |
| Source-eligible observations | 8, with the same all-eligible denominator |
| Exact pair cohorts | 4/4 completed |
| Pipeline coverage | 8/8 |
| Strict source-field fidelity | 8/8 |
| Aggregate field/inventory/source-copy checks | 368/368 passed |
| Logical queries | 27 |
| Native `urlopen` invocations | 25: 24 succeeded, one timed out |
| Retries scheduled | 1; its second attempt succeeded |
| Validated logical responses | 27: 24 live, three cache hits |
| `SourceLicenses` retrieval | One live response, three verified cache reuses |
| Database version | `pharos319` before/after every cohort |
| Terminal batch failures | 0 |
| New IntAct requests / Java reader runs / model calls / GPU runs | 0 / 0 / 0 / 0 |

The recovered timeout was a `Scoped_ppis` query in `batch_0004`, logical query 5 for the P06400/Q01094 pair (RB1/E2F1): a 30.0607-second timeout at the open stage, one-second backoff and successful second attempt. This demonstrates recovery of that particular transient failure. It does not establish why the original license calls failed, a long-term service reliability estimate, or the isolated causal contribution of each change.

| Exact pair | Eligible rows preserved | Logical queries | Native opens |
| --- | --- | --- | --- |
| A0A1B0GWG4 / O14649 | 2/2 | 6 | 6 |
| O14656 / Q8NFQ8 | 2/2 | 7 | 6 |
| O95863 / P0C2W1 | 2/2 | 7 | 6 |
| P06400 / Q01094 | 2/2 | 7 | 7 |

## Scope, guards and interpretation

The run uses the exact saved source publication, official-reader records and original independent field oracle. Its ordinary path is exact Pharos construction → source-qualified assay attachment → readable answer → full graph export → reopen and field checks. The source packet’s historical fresh envelope is preserved as provenance; the current assessment is explicitly `consumed_retrieval_reliability`.

The cache starts empty in this run’s directory, is shared only across its pair clients, has a 24-hour validity window, and accepts only matching endpoint/payload/response-hash entries after successful validation. Version checks bypass caching. There is no stale-cache fallback or import of captured successful Pharos responses. Policy remains 30-second socket timeouts, two retries, at most 28 logical requests / 84 native `urlopen` invocations and the existing 25 MB response limit. Native urllib redirect behavior is unchanged; redirect hops are not individually counted.

All four pairs and all eight observations stayed in scope. Missing outputs would remain failures in the original denominator. Failed attempts are retained in durable started/finished JSONL receipts and successful logical responses retain their original source timestamps. Seven runner controls plus native client and construction controls were independently run before live execution: 39 tests passed. The pre-live receipt and 646-file historical manifest bind the implementation and original artifacts.

The result verifies supplied-source preservation, not independent biological truth, scientific accuracy, source novelty, study independence or improved graph prediction. Negative=true rows and supplied complex-expansion annotations are absent and remain unevaluated. Missing annotations remain missing; absence from Pharos does not establish a biological negative. No automatic acceptance or pruning was introduced.

A separate offline artifact audit passed **214/214 checks**, reproduced the complete existing field-oracle outputs for all four batches, reconciled retry/cache receipts and verified all 646 historical file hashes. The [audit revision note](../../runs/pharos_reliability_consumed_20261027_attempt_01/independent_result_audit_v2.json) preserves an initial reviewer comparison error: Python tuples serialize as JSON arrays, as documented by [Python 3.12](https://docs.python.org/3.12/library/json.html#json.JSONEncoder). Exact canonical JSON comparison retained every field; no source, oracle or assessment result changed.

## Artifacts

- [Readable result](../../runs/pharos_reliability_consumed_20261027_attempt_01/index.html)
- [Machine-readable result](../../runs/pharos_reliability_consumed_20261027_attempt_01/report.json)
- [Execution policy](../../runs/pharos_reliability_consumed_20261027_attempt_01/started.json)
- [Source/upstream review](../../runs/pharos_retrieval_reliability_20261027/source_review.json)
- [Pre-live review and controls](../../runs/pharos_retrieval_reliability_20261027/pre_live_review.json)
- [Independent artifact audit](../../runs/pharos_reliability_consumed_20261027_attempt_01/independent_result_audit_v2.json)
- [Historical preservation manifest](../../runs/pharos_retrieval_reliability_20261027/preservation_before.json)
- [Unchanged original fresh result](../../runs/intact_fresh_assessment_20261027/execution/report.json)

The next biological comparison still requires a verified Steward-specific evidence/input contrast and a separate evaluation boundary. This retrieval check does not supply that scientific result.
