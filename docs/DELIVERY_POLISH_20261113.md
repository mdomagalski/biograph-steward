# Closing delivery fixes — November 13

Two reproducible integration issues are fixed in tested code `0529d2b` and
remain included in the current private AWS runtime `ea5752e`. The
[measured receipt](evaluations/delivery_polish_20261113_summary.json) preserves
the original local checks, implementation hashes and scope; the subsequent
[initial hosted update receipt](evaluations/hosted_polish_update_20261113_summary.json)
records their deployment and acceptance. The later
[native GO hosted receipt](evaluations/hosted_native_go_20261113_summary.json)
records the current runtime and separately approved source attachment.

The update preserved the existing graph, TP53 question and all 13 native
question/export files. They reopened after a real service restart, and complete
Neptune parity plus read-only inspection passed. The approved 16-file aggregate
publication `scientific_assessment_delivery_20261113` (`09e50f8e…`) is installed
and verified through the API and catalogue. The previous runtime/image remains
available for rollback; authentication, permissions and compute resources are
unchanged. The update is not a new backup-recovery test.

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

At the original polish checkpoint, the clean Python core suite passed (1,954
tests, 36 optional skips); all 46 JavaScript tests passed. Regression checks include legacy TSV byte equality,
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

The hosted v3 publication contains the grounding component and earlier
92-query/3,968-pair exploratory assessment. The separately reported negative
[128-gene/7,648-pair transfer](evaluations/PROSPECTIVE_GENE_TRANSFER_20261113.md)
remains part of the scientific assessment. The native GO web/QC inspector is
now enabled in hosted `ea5752e` through the separate approved 12-file packet.
Both NRAS contexts passed API checks before and after restart, with graph,
question and publication bytes unchanged. This exposes saved source/QC findings;
it adds no biological correctness labels or automatic pruning. Fresh software
installations remain unconfigured. The existing 153,681-byte
three-page review PDF predates this hosted update and is preserved unchanged;
the linked hosted receipt gives the current runtime status.

Local CPU is sufficient for these fixes and document preparation. Brev and its
model may stay off. Keep the existing AWS app and Neptune available while their
private demonstration is needed. The
[NVIDIA status review](NVIDIA_INTEGRATION_STATUS_20261113.md) records why adding
NemoClaw is deferred and identifies the optional NeMo Agent Toolkit wrapper's
upstream deprecation; neither requires changing the supported core workflow.
