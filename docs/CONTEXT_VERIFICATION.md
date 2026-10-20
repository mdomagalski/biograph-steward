# Context verification

The optional `source-context.v3` tool extracts eight dimensions from a supplied
claim and numbered source passages: disease, molecular profile, regimen,
population, treatment line, comparison, outcome and qualification. Each asserted
dimension has exact claim/source spans, a passage index and a model-assessed
relation. Empty or unavailable context is explicit. The model has no retrieval,
graph mutation or human-review authority.

The compact schema caps the explanation at 300 characters and each span at 220.
Evidence indices must be unique, valid, and no more numerous than the available
passages (maximum three). The pinned Brev decoder receives a basic fixed boolean
map with one slot per available passage (`fixed_passage_map.v4`). String lengths
and the three-selection bound are enforced locally, rather than asking that
decoder to enforce unsupported advanced schema keywords. The original bounded
array schema is retained for replay of the interrupted infrastructure attempt.
Local validation remains mandatory with guided decoding.
Invalid fields, duplicates, truncation and altered spans are errors; the tool
never deduplicates, retries or repairs an answer.

The eligibility check withholds SUPPORT when the model reports unknown/mismatched
context, omits recognized claim literals, or cannot ground them in its context
span. A small literal vocabulary also checks the complete supplied source window.
Missing literals mean **unresolved context**, not biological absence or contradiction.
Literal co-occurrence and exact span fidelity do not prove entailment. Unmapped
synonyms, disease hierarchy, complex profiles and findings spread across passages
can cause false flags or escape these checks. No ontology or clinical equivalence
is inferred from spelling. The raw judgment is preserved separately from eligibility.
Withheld claims request review; no automatic quarantine, acceptance or graph writes.

## Use on one provided-document task

Use the verifier environment settings described in [LOCAL_MODEL.md](LOCAL_MODEL.md).
`task.json` contains only `id`, integer `claim_id`/`document_id`, `claim`, and
`document` (`title`, contiguous numbered `sentences` containing `index`/`text`).

```sh
python -m biograph_steward context-assess --task task.json --verifier configured --out runs/context_assessment_001
```

This requests one turn and saves the unchanged task, raw response, exact context
spans and findings. It is an explicit tool, not a silent default-verifier replacement.

For insufficient evidence, use `literature.collect_literature` to save a new bounded
retrieval from the same PubMed ID and its linked PMC record, and then
`literature.source_document(..., 'augmented')` for a new source window. Save the
new view separately before reassessment. Do not overwrite frozen inputs, search
until a different paper supports the claim, or treat inaccessible text as negative.
The body selection does not exhaustively review the paper or its supplements.

## Paired evaluation

```sh
python -m biograph_steward context-prepare --literature runs/new_literature --previous-literature runs/prior_literature --out runs/context_packet_001
python -m biograph_steward context-run --packet runs/context_packet_001 --verifier none --out runs/context_offline_001
python -m biograph_steward context-run --packet runs/context_packet_001 --verifier configured --out runs/context_live_001
python -m biograph_steward context-verify --result runs/context_live_001
```

The default panel has 18 claims from three publications outside supplied previous
CRC literature inventories: nine valid paraphrases and nine context edits. Claims
and reference rationales are AI-authored, inspected against source text before
freeze, and **not independently reviewed scientific gold**. Public sources may be
in model training. Freshness refers only to supplied previous CRC source inventories;
related trial cohorts are not assumed independent.

Preparation freezes sources, identities, references, exclusions, code hashes,
instructions and per-task schemas. Only task fields enter prompts; reference labels,
edit names, rationale sets and expected dimensions are withheld. Labels are parsed
for scoring only after predictions close. One legacy v2 passage-index turn and
one compact context turn run per case, with alternating order and the same model
and budgets. No retries, fallback, retrieval or tools. A changed engine requires
a new packet; a new result directory is always required. The first advanced-schema
attempt timed out in the decoder fallback and was stopped, preserving one completed
legacy response, one context timeout and one interrupted context request. The
fixed-map follow-up uses byte-identical claims, sources and references; it is a
compatibility follow-up on the predeclared panel, not a new independent fresh test.
Reusing inspected
publications is development work, not another fresh test.

Five views show all-source retention, literal checks, legacy SUPPORT, compact raw
SUPPORT, and compact SUPPORT after eligibility checks. The last two reuse identical
responses, isolating the gate. Failures remain in denominators. False flags on
valid controls are shown alongside retained errors; abstaining on everything and
format failures do not count as correct reasoning.

The report records reference-verdict agreement, reference passage-set coverage
and expected context-axis alignment separately. Passage overlap is not entailment;
axis alignment against AI references is not independent scientific judgment.
Expert rationale correctness remains null. Blank worksheets support source,
reference and reasoning review. This does not measure biological graph improvement
or authorize model promotion.

Completed comparisons appear in the app, with authenticated, integrity-checked
reports and exports. Synthetic fresh cases never attach to real graph assertions.
Existing original-annotation passports and historical comparisons remain unchanged.
