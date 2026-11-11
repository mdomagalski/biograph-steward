# Optional physical association priority

The existing guided protein-neighborhood question can order its matching
interaction partners by **native STRING 12.5 physical association scores**.
Alphabetical order remains the default and makes no additional STRING calls.
This is a question-specific ordering supplement, not a graph modification or
a new confidence formula.

## Use it

Open a saved real Pharos run, select a protein and choose reported interactions,
or interactions and shared pathways. In **Result order**, select **Physical
association priority · STRING**, then find evidence paths. The existing accepted
or candidate evidence view still determines which paths are eligible.

The option requires exact UniProt identifiers. It is unavailable for synthetic
demo data and shared-pathway-only queries. A question with no eligible interaction
paths cannot use it; explore candidate paths or choose alphabetical order.
Changing any question control invalidates the displayed answer until it is run
again. Saved physical answers restore their order; older answers remain
alphabetical.

Scoring considers all matching interaction partners **before** the result limit.
Numeric physical scores sort from highest to lowest, with alphabetical ties.
Unscored and pathway-only matches follow alphabetically. The result limit does
not silently restrict the scored population. Summary counts cover every matching
protein, including matches omitted from the displayed results.

## Interpret the result

The source score predicts physical proximity or co-complex association; it does
not establish direct binding, a disease mechanism or clinical relevance.
STRING is already a Pharos provider, so the supplement is not additional
independent evidence. It remains separate from the saved Pharos release and
does not add, remove or accept assertions, change paths, or change review states.

| Displayed state | Meaning |
| --- | --- |
| Native numeric physical score | A score supplied by STRING; numeric zero stays zero. |
| No returned functional row | No row returned for the mapped pair under this query profile. |
| Physical score unavailable | No physical overlay supplied, or below the requested source profile. |
| Unmapped or ambiguous endpoint | Mapping was unavailable or unresolved; no score is imputed. |
| Both endpoints map to one representative | The source cannot distinguish this pair at its locus-representative level. |
| Pathway-only match | Retained as pathway context and not queried or ranked physically. |

Missing scores are coverage states, not evidence of no interaction. Mapping is
STRING's best-match locus correspondence, not proof of exact isoform, sequence
or assay-construct identity. The [STRING 2023 primary paper](https://academic.oup.com/nar/article/51/D1/D638/6825349)
describes this locus-level representation and the distinction between functional
and physical associations. The [official API](https://string-db.org/help/api/)
documents best-match mapping and typed functional networks with physical
overlays. This implementation uses that overlay, not a complete standalone
physical-network retrieval.

## Bounded source retrieval

The source address is pinned to `version-12-5.string-db.org`; a version response
must confirm 12.5. Queries use human species 9606, `required_score=0`,
`add_nodes=0`, and the typed functional network with its physical overlay and
regulatory overlay disabled. Incidental returned interactions do not become
new candidates.

At most **100 matching interaction partners** may be scored per question.
Larger questions fail before retrieval and must be narrowed. At most seven
logical requests are allowed: one version check, up to two mapping batches and
four network batches. Calls are sequential, at least 1.05 seconds apart.
Transient network failures and HTTP 500/502/503/504 may receive up to three
attempts per request. HTTP 429, malformed responses, source/version mismatch,
inconsistent scores or exceeded transport limits stop the question. No failed
retrieval is converted into missing evidence or an alphabetical answer.
Limits are 60 seconds per request, 4 MiB per body and 32 MiB total body bytes.
No Brev instance, model or GPU is required.

## Saved trace and offline replay

The question ZIP retains its normal summary, paths and evidence, plus:

- `physical_ranking_source.json`: the complete candidate binding, source
  profile, mappings, raw TSV response text, request/attempt receipts, checksums
  and replayable score annotations. The same packet is embedded in
  `question.json`.
- `physical_priority.tsv`: the full ordered matching population with physical
  and functional native scores and explicit source states, including matches
  omitted by the displayed result limit.

The answer shows release, retrieval time, numeric/unranked counts and the packet
hash. Reopening and downloading in the app verify the saved packet, readable
exports and the original run's graph/review basis without querying STRING again.
Keep the original source run alongside the saved question for that full check.
An offline check from the repository root is:

```python
import json
from pathlib import Path
from biograph_steward.questions import verify_answer, verify_ranking_files
from biograph_steward.webapp import verify_qualified_question_source

folder = Path("runs/QUESTION_ID")
answer = json.loads((folder / "question.json").read_text(encoding="utf-8"))
verify_answer(answer)
verify_ranking_files(answer, folder)
verify_qualified_question_source(answer, folder.parent)
```

The [native component comparison](STRING_COMPONENT_COMPARISON.md),
[archived temporal control](STRING_TEMPORAL_CONTROL.md), and
[source-independence review](evaluations/STRING_REFERENCE_INDEPENDENCE_20261027.md)
record the evaluation rationale and its limits. They support this bounded
optional ordering; they do not establish independent biological validation or
Steward-specific graph improvement.
