# Entity/tool protocol v2 development comparison — October 19, 2026 (EDT)

The first revision fixed the synthetic preflight and produced answers for all eight protein-neighborhood questions. It did **not** pass the full planning comparison: only 6/24 draft scope plans matched, compared with 8/24 in the original all-abstention run. This result is retained unchanged rather than presented as a successful planner.

| Outcome | v2 |
|---|---:|
| Questions / live evaluation requests | 24 / 24 |
| Answered | 8 |
| Invalid plans blocked | 15 |
| No-evidence result | 1 |
| Draft scope matches | 6 / 24 (25%) |
| Query calls | 9 |

The model often selected the correct CIViC profile and tool but also filled `protein_id`, which must be null for that tool. The validator blocked those plans. Some proposed evidence views also differed from the explicit question. A causal-proof request incorrectly reached a read-only query and returned no evidence. Producing more answers did not establish correct planning or biomedical accuracy.

This comparison changed exact lexical binding, focused input, tool instructions, identifier/therapy enums and binding validation together. It retained the original model/revision, serving settings, source bytes, review states, 24 development questions and display budgets. All 24 legacy request payload hashes were checked offline and matched the original experiment. The core suite ran 250 tests with one optional skip; nine new identity/contract tests passed on Brev Python 3.10.

The [machine-readable record](entity_tools_v2_20261019_summary.json) includes every proposed plan and case outcome. Complete results and worksheets remain in `/data/runs/evaluation_entity_tools_20261020/` on Brev and `runs/brev_entity_tools_20261020/v2_live/` locally. The exact v2 source is retained in a local source archive and the commit containing this report. These are reused development cases with draft references, not held-out or independently approved biological answers.

The next revision should enforce separate tool argument shapes in the output schema and check explicitly unsupported requests before allowing a query. It needs a new frozen engine/suite and a separate result; this v2 report must remain unchanged.
