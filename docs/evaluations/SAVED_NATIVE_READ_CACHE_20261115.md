# Byte-verified reuse of saved native workspace replay

The browser opens a saved graph and then verifies its saved native physical
answer against that graph. These are two sequential full source replays under
the ordinary biological-extension reader. Separate HTTP requests can also overlap.
Metadata catalogues do not trigger those full replays. This is redundant delivery
work, not a newly discovered scientific limitation or evidence of a failed source.
The observed long hosted wait also overlapped other QC; it is not attributed to
this mechanism alone.

## Established mechanism and scope

`biograph_steward.saved_run_cache` adapts the existing qualified-workspace
loader's single-entry, locked full-fingerprint/deep-copy design. Only ordinary
saved `biological_extension` runs with their complete ordinary source attachment
are eligible. Other modes and qualified workspaces pass through the unchanged
original reader. Only `webapp` reader imports opt into the wrapper. Direct CLI/scientific
readers continue to use the original reader.

The existing [Python 3.10 memoization documentation](https://docs.python.org/3.10/library/functools.html#functools.lru_cache)
does not promise once-only execution. The [actual CPython 3.10.12 implementation](https://github.com/python/cpython/blob/v3.10.12/Modules/_functoolsmodule.c#L953-L964)
explicitly handles another cache result arriving while the wrapped function is
running. The outer lock therefore covers a miss, full validation and returned
copy. A bare `lru_cache` decorator would be insufficient.

Every eligible request freshly fingerprints every ordinary workspace file and
directory before and after the read/copy, reusing the existing qualified helper.
It also hashes every core Python helper, including new native source modules,
and records the actual ordinary reader/builder/assay/CIViC function identities.
No path or modification time is treated as proof. Cold misses call the unchanged
full ordinary reader, including source reconstruction and graph/ledger checks.
Changed sources force replay; a validation failure clears the cache and remains
an error. Source rules are not widened or silently repaired.

At most one ordinary parsed workspace is retained, with eviction before loading
a different one. Callers receive private deep copies. The existing separate
qualified-workspace cache retains its own one-entry bound. There is no temporary
source staging, filesystem cache, database mutation or new dependency. Initial
replay and full-byte hashing still cost time; process restart or workspace
alternation can require another cold read. Caller copies still consume memory.

## Preserved immutable bindings

`reviews.py`, `assay_source_reuse.py`, `questions.py`, `qualified_workspace.py`,
`evidence_extension.py`, `gold_packet.py` and the native GO/STRING readers remain
byte-identical. This matters because existing assay-reuse manifests bind the
original `reviews.py` bytes. Saved graph/question hashes depend on their preserved
semantic content; the cache adds no graph field, label, review or source record.
The source-reuse contract is not bypassed or resealed.

## Qualification

On Python 3.12.14, 49 focused tests passed, including 13 new cache tests and two
actual HTTP tests. Checks cover cold/warm equivalence, concurrent single replay,
returned-object mutation, same-size changes with restored modification times,
resealed invalid native projections, added/deleted files, empty directories,
symlinks, helper/reader changes, mutation during replay/copy and one-entry eviction.
Added non-source files trigger the unchanged reader's rules rather than a new
blanket rejection policy.

The HTTP graph → candidate answer → accepted answer → complete source passport
→ workspace/answer export sequence performs one original ordinary replay.
Exact source files and answer contents remain unchanged; retrieval, model and live STRING
factories stay unused. Warm source tampering is rejected by graph, saved-answer
and source-passport routes. Existing saved-review, qualified cache/HTTP and
physical-ranking HTTP regressions remain included. A further 44 GO-source,
assay-reuse and export preservation tests passed, including their actual HTTP
source/download routes. The two focused groups total 93 passing tests.

The existing 99-target native-location workspace was then read by the unchanged
reader, a cold wrapper and a warm wrapper, with no large files copied and network
connections explicitly blocked. All 199 source-file hashes stayed unchanged.
Complete graph/snapshot/reviews and candidate/accepted native-GO question hashes
matched exactly. The graph remains 9,724 nodes, 18,980 evidence records and 16,100
assertions, with canonical hash
`fa366b17c7090e352d6269d31956b0c5201697b1f40eb7417350f81d3a44e4b8`.

| Local read | Wall time | Full wrapper replays so far |
|---|---:|---:|
| Original uncached reader | 18.532 s | Not applicable |
| Wrapper cold | 22.217 s | 1 |
| Wrapper warm | 4.159 s | 1 |

This one local equality check is not a repeated latency benchmark or a hosted
speed guarantee. It uses the available native-location workspace; the combined
native physical workspace requires its separately verified hosted packet. Cold
fingerprinting/copying adds overhead, and source-file downloads can still perform
their own complete publication reprojection. Historical assay-reuse supplements
retain their own original reader. No source validation is skipped to hide that
cost.

Private equality/input-hash receipts are under
`runs/saved_native_cache_20261115/`. The earlier GOA semantic-projection cache
candidate remains separately unpromoted; this adaptation does not use its
temporary-directory bridge. No biological metrics, source/review states,
prediction methods or held-out boundaries changed. Hosted rollout and its
latency check remain separate delivery steps.

The subsequently accepted AWS runtime is `47a2e5a`; its [delivery receipt](native_profiles_hosted_20261115/summary.json)
records the actual restart, unchanged graph/answers/source inventories and private
Neptune parity. Hosted browser timing and usability checks are recorded separately
from the local equality observations above.
