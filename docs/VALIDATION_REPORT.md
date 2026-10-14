# Validation report

Tested at 2026-10-12T01:24:49.930716+00:00.

## Automated offline tests

**41 tests passed**, using Python 3.13.5.

Covered identifier handling, explicit synthetic labels, data-integrity hashes,
source-specific evidence preservation, zero scores, missing evidence, disease
scope warnings, duplicate records, output non-overwrite behavior, replay,
HTML-safe embedded data, schema mismatch handling, pagination and caps,
empty results, GraphQL errors including partial errors, source metadata failures,
cache integrity and timestamps, connection failures, HTTP error behavior,
a complete extraction through a local mock GraphQL HTTP service, and local
UI endpoints including ZIP download, origin checks and invalid paths.

The mock responses are invented fixtures, not recordings from Pharos.

## Browser checks

The report HTML was rendered in headless Chromium using Playwright. Protein
selection, Tdark filtering, evidence cards, review/quarantine tables and JSON
download were exercised. There were no JavaScript errors. A 390-pixel mobile
viewport did not overflow horizontally at the page level.

Browser navigation to local HTTP URLs is restricted by this runtime's browser
policy, so browser interaction checks used in-memory HTML rendering. Local
HTTP routes were exercised separately using Python's HTTP client. Direct
file navigation and real Pharos retrieval were not certified by these tests.

## Live integration: not verified

The actual `doctor` request failed with a DNS resolution error from this
runtime. No live Pharos data was obtained and no live extraction result is
claimed. See LIVE_CONNECTIVITY_CHECK.txt. Queries were checked against the
published NCATS schema; the first real `doctor` and disease extraction on the
team's network remain required.

## Scientific validation: not performed

No held-out-link benchmark, predictive model, curation accuracy estimate,
clinical evaluation or LLM was run. Demo graph counts are software-fixture
counts only. Passing structural checks is not evidence of biological truth.

## Ready for the team

The dependency-free local application, labeled demonstration and snapshot
replay are runnable. The live Pharos client is implemented and schema-aware,
but requires the stated integration check. The next shared deliverable is a
real, saved Pharos run, not a prediction-performance claim.
