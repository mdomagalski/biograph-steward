# Current-source agent: completed development comparison

**The actual Nemotron workflow passed all eight fixed checks.** Five supported
questions reproduced the deterministic workflow's complete query result, cited
answer and focused graph under identical limits. Three unsupported or unresolved
requests were blocked by application guards before inference. These are
operational results, not eight independently verified biological conclusions.

The [aggregate](source_agent_20261116/summary.json),
[source/runtime pins](source_agent_20261116/publication.json) and
[pre-inference protocol](SOURCE_AGENT_PROTOCOL_20261116.md) preserve the
denominators and interpretation. The implementation was committed as
`12d70a261ba75920e136d7bba1d42c2391b9228a` before inference.

| Fixed request | Actual outcome | Model calls | Complete deterministic parity |
|---|---|---:|---|
| KRAS native physical associations | Completed, inspected sources, proposed retain-candidate actions | 3 | Query, answer and graph |
| EGFR native physical associations | Completed, inspected sources, proposed review actions | 3 | Query, answer and graph |
| TP53 native GO location | Completed, inspected sources, proposed review actions | 3 | Query, answer and graph |
| BRAF native-supported archived pathway context | Completed, inspected sources, preserved protein/gene qualifications | 3 | Query, answer and graph |
| KRAS, accepted locally only | Correctly returned an empty accepted view | 1 | Query, answer and graph |
| KRAS direct binding in pull-down assays | Unsupported assay/binding scope rejected | 0 | Guard, not model refusal |
| TP53 location specifically in colon tissue | Unsupported tissue filter rejected | 0 | Guard, not model refusal |
| Protein outside the saved workspace | Unresolved identity rejected | 0 | Guard, not model refusal |

## What the agent contributes

The model produced validated query actions, prioritized returned citations for
source inspection and selected adapter-grounded review proposals. Existing
source engines produced the scientific statements and focused graph. All
returned evidence remained available, including records the model did not
prioritize. Complete source passports were retained; selected grouped citations
cannot substitute a first assertion for an uninspected group.

The live run used **13 model calls and 972 reported completion tokens**, with no
retries or repair calls. The predeclared ceiling was 24 calls, each requesting
at most 1,200 output tokens. Both full workspace/source/review bindings remained
unchanged, no fresh source retrieval occurred and no proposal was applied.

The tool-choice claim is deliberately narrow. TP53 offered two executable
source tools, and the model chose location. The other supported requests
offered one source tool plus abstention. Protein identity was grounded by the
application; this was not an entity-discovery benchmark. All three refusals
were application preflight decisions, not evidence of model refusal ability.
Inspection order can differ from an explicit workflow without being more
scientifically accurate.

The featured recorded KRAS run shows **8 of 14 eligible proteins**, with six
outside its declared display cap. The earlier manual KRAS question displays
all 14 under its different cap. Those are different display limits on the same
source, not a loss of evidence. A candidate is not automatically accepted.

## Comparison with Pharos and prediction

The captured Pharos-only graph was reconstructed from the identical original
99-target snapshot with the existing constructor, without the native evidence
or qualification overlays. It lacks these exact native-source tool contracts.
That demonstrates additional inspectable source context; it does not make its
other annotations biologically false, or establish another independent study.

This increment orchestrates saved sources and extracts a focused answer graph.
It does not alter the full learner graph or add training features. There is no
source-compatible prediction artifact for this current workspace comparison,
so a prediction gain is **not applicable here**. The separate historical
function forecasts, stronger controls and public location-reference comparisons
retain their own measured results. Their gains are not attributed to the LLM.

This is a fixed development comparison of a bounded interface. It does not
estimate whole-graph biological precision, clinical validity, arbitrary-language
coverage or reliable automatic biological pruning. In particular, retain-candidate
and needs-review proposals cannot silently become accept or prune decisions.

## Reuse and delivery

The [operator guide](../SOURCE_AGENT.md) documents catalogue, run and model-free
verification commands. Shared reviewers replay the recorded real model run;
they do not trigger inference. Full original requests, responses, tool results,
errors, source passports and before/after bindings are preserved in the private
evaluation packet. The aggregate omits raw model/source passages. Earlier
unfavorable planner and literature-audit experiments remain preserved.

The controller adapts the project's existing bounded tool execution and JSON
transport. Its source-assisted workflow is informed by the primary ReAct,
GeneGPT and GeneAgent methods linked in the protocol; this comparison does not
claim to reproduce their benchmarks.
