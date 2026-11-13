# Closing delivery fixes — November 13

Two reproducible integration issues are fixed in the current checkout. The
hosted AWS app remains at its separately recorded `902699e` revision; these
changes have not been deployed there. The
[measured receipt](evaluations/delivery_polish_20261113_summary.json) preserves
the checks, implementation hashes and scope.

## Large saved answers

The saved native models contain Unicode that was expanded into JSON escape
sequences in HTTP replies. Python's existing
[JSON encoder](https://docs.python.org/3.10/library/json.html) supports native
UTF-8, as specified for network JSON by
[RFC 8259](https://www.rfc-editor.org/rfc/rfc8259). The normal JSON route now
uses that representation and its existing gzip support. Legacy lone surrogate
values retain the previous escaped representation rather than emitting invalid
UTF-8. Non-finite numbers are still rejected.

An actual saved-question GET, including the normal complete source/export
verification, returned HTTP 200 with the same decoded values and canonical
answer hash. For this one question:

| Representation | Previous bytes | Current bytes | Reduction |
|---|---:|---:|---:|
| Decoded HTTP JSON | 62,181,391 | 27,108,229 | 56.4% |
| Gzip response body | 3,130,544 | 1,624,303 | 48.1% |

The 64,235,516-byte saved file and its ten exports remain byte-identical. This
is a serialization comparison, not a controlled latency result. Repeated
parsed model content still makes the saved format large; deduplicating that
content requires an explicit versioned format migration and is deferred.

## Read-only source verification

Native path verification previously created a temporary TSV merely to compare
its bytes with an existing export. The established
[csv writer interface](https://docs.python.org/3.12/library/csv.html#csv.writer)
accepts file-like text streams. The same existing TSV writer now serves both
normal file exports and an in-memory verification stream. It preserves quoting,
column order, line endings, nested JSON and spreadsheet formula escaping.

The saved real TP53 answer and pathway exports verified with all temporary-file
creation, write opens and directory creation forced to fail: 26 read opens,
zero attempted writes or temporary creations. All 13 input files and directory
entries remained unchanged. This check covers `verify_answer` and
`verify_pathway_files`, not a full VM restore or every application operation.
The earlier AWS recovery failure and its documented bounded `/tmp` remedy are
preserved under their original code version.

## Verification and remaining boundaries

The clean Python core suite passed (1,954 tests, 36 optional skips); all 46
JavaScript tests passed. Regression checks include legacy TSV byte equality,
Unicode, surrogate fallback, gzip, non-finite values, tamper rejection and saved
question/export compatibility after a real server restart. These are engineering
checks, not biological accuracy measurements.

The first GitHub run exposed a test-oracle assumption on Python 3.10: its native
CSV writer leaves a lone carriage return unquoted when the line terminator is
LF. Later Python releases include the upstream
[gh-67044 fix](https://github.com/python/cpython/issues/67044), with selected
maintenance backports. The regression test now probes that one native CSV
capability while pinning the remaining bytes exactly. Production serialization
is unchanged. Legacy byte preservation is relative to the same CSV runtime;
cross-version byte identity for this edge case is not claimed. Use the recorded
Python 3.12 environment for exact replay of the supplied real packet. The initial
failed CI jobs remain available in GitHub Actions.

The [current scientific assessment](evaluations/SCIENTIFIC_DELIVERY_20261113.md)
and [expert-grounding result](evaluations/EXPERT_GROUNDING_20261113.md) remain in
their declared scope. Independent whole-graph precision and transferable
prediction gains remain unproven. The next delivery priorities are independent
weekend task feedback, a single designated reviewer build, permitted source-data
access and the final repository/submission handoff.

Local CPU is sufficient for these fixes and document preparation. Brev and its
model may stay off. Keep the existing AWS app and Neptune available while their
private demonstration is needed. The
[NVIDIA status review](NVIDIA_INTEGRATION_STATUS_20261113.md) records why adding
NemoClaw is deferred and identifies the optional NeMo Agent Toolkit wrapper's
upstream deprecation; neither requires changing the supported core workflow.
