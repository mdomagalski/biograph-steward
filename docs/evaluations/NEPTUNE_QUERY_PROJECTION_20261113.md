# Bound database pages before projecting source records

A complete corrected-graph reconstruction and prior-dataset verification took
11 minutes 31 seconds on the existing private workbench and Neptune engine
1.4.8.0. The result was correct, but cold inspection was too slow for a useful
interactive handoff. Ordinary guided source questions remain file-backed.

The existing queries already use a persistent SDK client and parameterized
values, as [AWS recommends](https://docs.aws.amazon.com/neptune/latest/userguide/best-practices-content-2.html).
AWS explains that a `WITH` boundary is appropriate when an intermediate result
needs ordering or a limit in its
[openCypher guidance](https://docs.aws.amazon.com/neptune/latest/userguide/best-practices-content-7.html).
We tested that established query shape on the actual deployed engine before
changing the reader.

| Fixed 500-record page | Original, two reads | Limit before property projection, two reads |
| --- | --- | --- |
| Vertices | 5.101 s; 5.078 s | 1.949 s; 1.903 s |
| Relationships | 2.141 s; 2.119 s | 1.078 s; 1.012 s |

All returned identifiers, labels, endpoints and complete property dictionaries
were identical in both shapes. These are bounded page observations, not a
general latency guarantee or a full-audit speedup estimate. Internal execution
plans were not used to assert a more specific causal explanation.

The change adds an ordered, fixed-size `WITH` boundary before `properties(...)`.
It preserves the namespace and cursor predicates, final output order, 500-row
bound and complete verification of all original IDs and record properties.
No graph, permission, source qualification, cache lifetime or scientific result
changes. Existing lossless mirror/export and actual HTTP regressions pass.

Full verification still runs for each immutable graph in a fresh server
process; selected database records are checked again on every inspection.
Cold verification can take minutes. A deployment must recheck its complete
source/database parity before acceptance; the bounded timing test alone does
not establish a successful release.

Private execution receipts are under `runs/qualified_app_20261113/`, including
`remote_query_profile_result_private.json`. They contain aggregate timing and
record hashes, not a new biological evaluation.
