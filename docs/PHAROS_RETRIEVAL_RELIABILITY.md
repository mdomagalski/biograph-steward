# Pharos retrieval reliability

The ordinary `PharosClient` already provides bounded retry and validated caching.
Use that native path when retrieval should recover from temporary network or
service failures. An injected `transport` is responsible for its own transport
policy: setting `retries=2` does not wrap it in the native HTTP retry loop.

## What failed and what changed

The October 27 four-study assessment missed four of eight eligible observations
after two read timeouts. Both failures occurred on the identical global
`SourceLicenses` query, before either pair's identity or PPI retrieval. The same
license query succeeded for the later two pairs. The original assessment
deliberately used a single-attempt transport, disabled caching and kept every
miss in its denominator. Its result remains unchanged.

The verified gap in ordinary retrieval was observability: successful responses
were saved, but the failed attempts preceding a recovered response were absent
from the trace. `PharosClient` now accepts an optional `attempt_observer` callback.
It receives `started` and `finished` events for each native `urlopen` invocation,
including operation, request digest, attempt, stage, elapsed time, status, byte
count, failure and retry wait. A successful transport event explicitly leaves
GraphQL validation pending. Cache hits and injected transports emit no native
HTTP events. Observer failures propagate without triggering another request.

Defaults and successful logical response records are unchanged. There is no
second retry layer, new HTTP dependency, reduced evidence scope or license-data
fallback. The retry driver remains in the existing client.

## Verify the recovery workflow

Run from the repository root:

```bash
python3 scripts/run_pharos_reliability.py \
  --output runs/pharos_reliability_consumed_20261027_attempt_01
```

Choose a **new** output path if that directory already exists. Do not rerun the
frozen fresh-assessment command or write inside its historical directory.

This diagnostic uses the same four now-consumed pairs and eight eligible
observations, with the saved IntAct publication. It does not retrieve IntAct
again or use a model, Java reader, GPU or Brev instance. Ordinary construction,
attachment, question answering, packet export and the existing independent
source-field oracle remain in use.

The client uses its existing two retries, 30-second blocking-operation timeout
and a new empty shared cache with a 24-hour TTL. Successful license metadata can
be reused across pairs; original retrieval timestamps and response hashes remain
in the trace. Before/after database-version checks explicitly bypass the cache.
Failed and partial GraphQL responses never become usable cache entries.

The diagnostic permits at most 28 logical calls and 84 observed native `urlopen`
invocations across the four pairs. These counts do not separately enumerate
urllib's internal redirect hops. Native retry waits remain bounded by the
existing policy. The socket timeout is not a whole-run wall-clock deadline.

Inspect each batch's `http_attempts.jsonl` and `logical_requests.jsonl`, then
`report.json`. Attempt boundaries are flushed to disk. A cache hit retains its
original source response and timestamp; it is not a new HTTP response. Every
eligible observation remains in the final denominator even if a batch fails.

## Existing solutions checked

- The [NCATS resolver at the reviewed commit](https://github.com/ncats/pharos-graphql-server/blob/3feb5ac7e450b3c6b767651f0fe1f39994085380/src/resolvers.js#L335-L356)
  performs global joins, counts and grouping for `dataSourceCounts`, including
  when only license fields are requested. This is a plausible source of latency;
  we have not verified the deployed server commit or established the timeout's
  root cause. A bounded repository issue search found no matching timeout issue.
- [Python 3.12 urllib documentation](https://docs.python.org/3.12/library/urllib.request.html)
  describes blocking-operation timeouts and automatic proxy configuration.
  The exception alone cannot distinguish server latency from network, VPN or
  proxy conditions.
- [urllib3 retry documentation](https://urllib3.readthedocs.io/en/stable/reference/urllib3.util.html)
  and [Amazon's retry guidance](https://aws.amazon.com/builders-library/timeouts-retries-and-backoff-with-jitter/)
  support bounded retries, backoff and attempt history at one layer. The existing
  project implementation supplies the needed recovery behavior; it does not
  need another retry framework.
- [pypath's Pharos adapter](https://pypath.omnipathdb.org/_modules/pypath/inputs/pharos.html)
  documents target-chunk timeout concerns. Those concerns do not explain a
  failure before target retrieval, so this increment does not reduce the PPI
  limit or remove evidence fields. No pypath code was copied.

The source-review receipts and preserved upstream code are under
`runs/pharos_retrieval_reliability_20261027/`. The
[dated assessment](evaluations/PHAROS_RETRIEVAL_RELIABILITY_20261027.md) records
the actual live outcome and its independent audit.

That live check completed all eight observations with assessed fields preserved.
It recorded one real PPI timeout followed by a successful retry after the
existing one-second backoff, and three validated license-cache hits. There were
27 logical requests and 25 observed native `urlopen` invocations. The original
fresh result remains 4/8.

## Interpretation

A later successful run shows that the workflow can complete under its recorded
conditions. If no live retry was needed, it does not demonstrate that retries
caused the difference from the earlier run. Controlled timeout tests separately
check retry behavior; actual cache-hit traces demonstrate metadata reuse.

This is consumed-data engineering verification and source preservation. It is
not replacement fresh validation, a scientific-accuracy score or evidence of
Steward-specific biological prediction improvement. Empty negative and
complex-expansion strata remain unevaluated.
