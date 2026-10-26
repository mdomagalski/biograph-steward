# Qualified assay evidence publication

October 25, 2026 (America/New_York). The bounded observation publication is
complete. It reuses the consumed Lambourne assessment and its frozen Pharos
lookup to expose qualified assay evidence, without changing either source or
repeating a scientific evaluation. The [literature gate](../literature/ASSAY_EVIDENCE_REUSE_20261025.md)
records the established IMEx/PSI-MI approach and why the author tables were used
after checking the reported IM-30553 deposition.

The [usage and contract guide](../ASSAY_EVIDENCE.md) defines the local format.
The delivered directory is `runs/lambourne_assay_evidence_20261025/` (ignored by
Git); open `index.html` to inspect it. The tracked
[aggregate summary](assay_evidence_publication_20261025_summary.json) identifies
its receipt and source bindings. Source bytes and upstream terms stay attached
to the local publication; they are not included in a fresh Git clone.

## Delivered behavior

| Item | Actual count / behavior |
|---|---:|
| Preserved nominated observations | 3,222 |
| Detected in the selected assay | 376 |
| Not detected in the selected assay | 2,300 |
| Excluded / failed observations, retained in the audit | 546 |
| Protein nodes, including isolates from excluded pairs | 3,173 |
| Eligible, qualified observation edges and assertions | 2,676 |
| Comparator-eligible observations | 2,674 |
| Detected + no match with both Pharos endpoints resolved | 42 |
| Original Pharos records modified | 0 |
| Assertions automatically accepted | 0 |

The 546 excluded observations preserve the existing 478 sequence-confirmation
failures, 41 autoactivators and 27 failed tests. They are never converted to
negative edges. The 2,300 nondetections remain assay-specific observations,
not statements of biological absence. The two unresolved Pharos pairs retain
their assay observations and unresolved comparator state.

The inspection view supports accession search, outcome and lookup filters,
pagination, source details and a two-protein observation view. The 42-pair
shortcut changes only the view; it does not remove any other observation or
claim that those pairs are globally novel. Every selected observation exposes
the original raw/published result, AD/DB constructs and confirmations,
Pharos provider/exposure context, full saved lookup record and precise source
locators. The original tables, crosswalk and frozen comparison are linked.

The derivative graph reuses the current protein and assertion implementations.
`assay_observation` is a distinct kind with explicit method, observation identity,
participant species and outcome qualification. All assertions are candidates,
with no biological-validation or independent-evidence-count claim. The existing
ordinary protein-neighborhood template does not generalize these records into
unqualified paths. No main workbench graph is rewritten.

## Validation and limits

The 12 projection tests cover complete accounting, exact joins, role-preserving
identity, changed-source rejection, failed/nondetected distinctions, no
automatic acceptance and prevention of unqualified answer propagation. The 14
publication tests cover copied-source replay after original directories are
removed, byte preservation, immutable output boundaries, source/manifest/code
tampering, resealed derivative changes and safe HTML embedding. These tests use
invented observations; the real publication separately runs the unchanged
frozen scientific-source verifier.

The full regression run completed **675 tests with 26 optional skips**, with
no failures. The actual projection reproduces every count above and preserves
the original frozen assessment. The tracked aggregate summary also records the
actual artifact replay and browser acceptance checks.

**Browser acceptance remains unverified.** The preferred browser connection
failed macOS code-signature validation; the alternative browser bridge was
unavailable and the native Chrome connection blocked before opening the page.
No visual or interactive browser checks completed. The static HTML controls,
embedded payload and escaping passed automated tests. The preview and final
HTML bytes are identical. This limitation does not change the source replay
result, but no claim of tested browser usability is made.

This is a standalone, immutable evidence layer with an offline viewer. It is
not yet a general source attachment in ordinary saved workbench runs, a new
IMEx-curated dataset, or a standards-conformant interaction export. The broader
source attachment/review/maintenance integration must preserve this context
and source contract if implemented later.

The incremental result is traceable information availability. No learner,
confidence rule, pruning threshold, new reference panel or new model run was
introduced. **No predictive or independent biological improvement was measured.**
The imported panel is already consumed and cannot validate its own addition.
This closes the predefined publication increment; it does not trigger another
source/model experiment. Brev was not needed.
