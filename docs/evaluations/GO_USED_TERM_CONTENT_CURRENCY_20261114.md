# GO content currency across the used vocabulary

The saved source audit now covers **18,002 distinct GO IDs** across the retained
predictor's training vocabulary, saved workspace and separate native GOA
inspector. It preserves the January 2023 interpretation of historical forecasts
and records differences against the pinned July 26, 2026 ontology. Pharos GO
annotation vintage remains **unknown**. This is source qualification, not a
biological error rate or a forecast improvement.

| Declared source scope | Distinct IDs | Active in both snapshots | Active in both with any compared literal difference |
|---|---:|---:|---:|
| Retained LocalPlus historical training-head vocabulary | 17,670 | 16,411 | 3,854 |
| Workspace GO nodes, including preserved context | 1,924 | 1,759 | 329 |
| Workspace primary Pharos GO endpoints | 1,759 | 1,759 | 329 |
| Separate native inspector primary GO IDs | 1,732 | 1,717 | 329 |
| Native inspector literal GO mentions, including extensions | 1,773 | 1,755 | 338 |
| Six saved query candidate lists | 27 | 23 | 4 |

Scopes overlap and must not be summed. Training heads are the complete admitted
vocabulary, not a claim that every term receives a positive score for each
query. Literal mentions are not additional graph assertions. Experimental
DeepGO heads are outside the retained product scope. The native inspector frame
contains 15,888 preserved annotations: its primary IDs and extension mentions
added 58 IDs absent from the initial scope. That initial preparation remains
preserved and unexecuted; the extended scope was frozen before comparison.

Among all 18,002 IDs, 16,623 are active in both snapshots. Of these, 662 have a
different label, 1,125 a different definition, 802 different scoped-synonym
records, and 2,881 different explicit `is_a`/`part_of` records. These overlapping
flags cover 3,888 distinct active IDs. Explicit parent differences can also
reflect the compared source serializations; they do not establish complete OWL
differences, semantic inequivalence, or false annotations.

All IDs are found in the July snapshot; 64 are absent from the January snapshot.
The broader inventory includes 1,363 currently obsolete IDs, including 1,259
historical predictor heads. These are retained with their literal lifecycle
declarations. **No automatic replacement, pruning or score change was applied.**
All 1,759 primary Pharos GO endpoint IDs remain active in July. Among those,
32 labels, 89 definitions, 58 synonym records and 249 explicit parent records
differ between the two dated ontologies. The graph's own recorded labels are
preserved without assigning them an unsupported release date.

The 27 saved candidate IDs reproduce the earlier displayed-term finding:
four are currently obsolete; the other 23 retain their labels and definitions,
with four explicit-parent differences. The separate
[C1QBP worked-example qualification](GO_TERM_CONTENT_CURRENCY_20261114.md)
still applies: an unchanged GO ID does not establish that a historical binding
forecast predicted a later reader/adaptor definition.

## Sources, method and limits

The native annotation header records generation on July 28, 2026 and GO release
July 26; its preserved archive URL is the August 5 GOA release. This source date
does not establish the vintage of a historical Pharos annotation. No annotation
dates were treated as first-discovery dates and no source absence was labelled
biologically negative.

The audit reuses the pinned CAFA author's unchanged OBO reader with a
metadata-only collector, plus the existing native OBOGraphs/lifecycle loader.
Original stanzas and native nodes are retained. The
[GO documentation](https://geneontology.org/docs/ontology-documentation/)
separates term identifiers, names, definitions, synonym scopes and lifecycle.
[ROBOT diff](https://robot.obolibrary.org/diff) and
[OAK diff](https://incatools.github.io/ontology-access-kit/cli.html#diff)
were checked as established ontology-difference tools. This narrower audit
compares recorded fields; it does not install those tools or claim full
ontology equivalence. The
[official GO curator discussion](https://github.com/geneontology/go-ontology/issues/25788)
illustrates why an ID's continuing activity does not guarantee unchanged scope.

The [path-free summary](go_used_term_content_currency_20261114_summary.json)
records all source, code, frame, freeze and publication hashes. The full saved
index is 6,357,650 bytes compressed and 71,889,992 bytes expanded. Production of
the index took 6.1 seconds and 763,176 KiB peak RSS on the existing Brev CPU;
the standard-library consumer validated the complete index in 1.4 seconds at
326,760 KiB peak process RSS. No source retrieval, model inference or GPU call
was made. Four invented-data tests cover literal flags, scope completeness,
exact source pins, lifecycle preservation and tampering rejection.

The [operator instructions](../../tools/go_content_currency/README.md) describe
the optional research producer, exact-ID saved-index consumer and offline
compact-note projection. The existing historical function-term detail now
supports a separate optional `content_notes` sidecar. The local 27-ID example is
90,874 bytes; it binds the unchanged historical publication/query inventory to
the complete source-index hashes and shows the two dated labels, definitions,
lifecycle and explicit parent records. Full ontology bodies stay offline. Each
web request reads only this bounded sidecar, with a separate authenticated
download; the larger index is never opened by the web consumer. Existing
annotation-overlap notes remain separate and unchanged. No new app panel,
automatic mapping, graph rewrite, score change or predictor promotion was added.
This local example has not been deployed to AWS.

Actual local browser inspection passed for an active term (`GO:0048856`) and an
obsolete term (`GO:0005615`): dated source content was readable beside the
separate annotation notes, with historical scores unchanged. The existing
horizontal table scroller is reused at narrower widths. This visual check
assesses presentation, not biological correctness.

- Scope freeze FILE SHA256: `2253eb940cf635f2b6ac5cb4abdb0c36bf1bc70537d799406157c3893fd69681`
- Publication FILE SHA256: `3c07f97df9c7664e00bfdf20a4b83069640d87eb60ab22175d1ca6828a6d0da1`
- Publication content seal: `623e31433435e7bf5d69006939e0d389da9c0ceaa155d8fd05b1da7fe43074e5`
