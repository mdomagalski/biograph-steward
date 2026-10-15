# Source verification agent: initial contract

The next agent evaluates whether a supplied source supports a specific assertion. The existing planner's 24/24 agreement measures query scope; this verifier needs a separate evaluation of evidence interpretation. Published expert annotations provide an external answer key without requiring the project owner to supply biomedical labels.

## Inputs and authority

Give the verifier one assertion, its exact identifiers and qualifiers, and bounded source text with numbered sentences or stable passage offsets. Preserve source identity, version/retrieval metadata and text hashes. Keep curated CIViC descriptions, article text and application-generated summaries distinguishable. A source annotation is a claim to check; its ACCEPTED flag, level or rating must not act as an answer key.

Initially provide the paper text directly. Verify the cited paper identity and text availability deterministically. Add bounded PubMed/PMC retrieval after evaluating given-document reasoning, so retrieval failure and reasoning error remain distinguishable. Full-text retrieval failure must be recorded as an access limitation. Never infer that the paper or claim is false because it could not be retrieved.

The agent returns a machine assessment only. It cannot change review events, accept assertions, delete edges, rewrite source records or assign human reviewer identities. Suspicious claims remain inspectable with a proposed flag or request for more evidence. Existing human acceptance and evaluation worksheets remain separate.

## Checks

| Check | Required behavior |
|---|---|
| Citation and provenance | Confirm document identity and returned-text hash. Cite actual source sentence IDs/passages; reject nonexistent indices or altered quotes. |
| Entity and biological scope | Check the complete variant/profile, disease, species/model and population. A broad KRAS result does not automatically establish a G13D subgroup result. |
| Treatment and comparison | Preserve the whole regimen, combination/substitute/sequential semantics, comparator and treatment setting. A one-drug database list does not establish monotherapy. |
| Claim support | Assess the actual relationship and outcome against the source passage, including required qualifiers. A matching topic or title is insufficient. |
| Negation, speculation and statistics | Preserve negated annotations, tentative conclusions, associations, nonsignificant results and subgroup limitations. An absent significant benefit is not automatically proven resistance. |
| Study context | Separate patient evidence from cell/model experiments; retain retrospective/prospective context where the source states it. Mark unreported details unknown. |
| Cross-source comparison | Count shared source identities and overlapping cohorts separately from independent experiments. Differing conditions are not automatically contradictions. |

## Output and abstention

Use `SUPPORT`, `CONTRADICT` or `NOT_ENOUGH_INFORMATION` **relative to the supplied source text**. Add reason codes such as `context_mismatch`, `missing_required_detail`, `needs_full_text`, `source_unavailable`, `negation_or_speculation`, `statistical_qualification`, `shared_source` or `contradictory_passage`.

`SUPPORT` requires the material claim and qualifications to be supported by cited passages. `CONTRADICT` requires opposing evidence about the same assertion/context; it cannot be inferred merely from silence or a different variant, regimen or population. Context mismatch or missing details normally produce `NOT_ENOUGH_INFORMATION` with the appropriate reason. This source-level assessment does not establish clinical truth.

Return task/assertion identity, claim/source hashes, verdict, evidence sentence IDs (initial budget: three), a concise explanation, context matches/mismatches, missing details and recommended follow-up. For the public benchmark, expose only the claim and source text to the model. Hide expert labels, rationale annotations and evaluation summaries. Validate the output against the exact supplied text before scoring or displaying it. No model repair loop or extra retrieval is implicit in a verification turn.

## Evaluation

Start with [SciFact](https://aclanthology.org/2020.emnlp-main.609/) for source-supported claim classification and sentence evidence. The prepared local protocol supplies one claim/abstract pair, so it measures verification after citation selection rather than open-corpus retrieval. Preserve complete alternative rationale sets: matching one complete valid set can justify a decision; a single fragment from a multi-sentence set cannot.

Report macro F1 and per-class precision/recall, the confusion matrix, false-support rate, support precision, complete-rationale coverage, evidence sentence precision/recall, invalid-reference rate and unknown/error rates. Define false-support rate as predicted SUPPORT among pairs whose expert label is not SUPPORT; support precision uses all predicted SUPPORT as denominator. Keep model failures in the denominator. Compare with unverified acceptance of every claim, always-insufficient output and a simple text-overlap rule. These baselines detect empty or indiscriminate behavior; task scores should not be equated with pruning performance.

Freeze prompts, model and budgets before a final run. Use training examples for development; reserve the official development split for a fixed evaluation. If it is used to tune, describe subsequent results as development results. Official SciFact test labels are not included in its release. Shared claims, papers and paraphrases require grouped analysis; published benchmark contamination in model pretraining remains unknown.

The prepared official train/dev tasks share citation candidates, so also report the supplementary document-disjoint subset described in [benchmark preparation](VERIFICATION_BENCHMARKS.md). Exclude whole claims touching training documents rather than retaining another pair from the same claim. Keep custom-subset scores separate from official-split scores.

Then add a targeted CRC source audit and explicit context-corruption tests, followed by [NLI4CT](https://aclanthology.org/2023.emnlp-main.1041/) for clinical-trial context and evidence selection. A synthetic corruption is a known edit, not automatically a false biological relationship. Keep its expected label tied to the supplied source and changed condition.

The promotion gate is a documented comparison of errors, supported claims retained, unsupported claims admitted and evidence spans against external labels. Choose tolerances before examining the reserved evaluation, report uncertainty, and do not enable automatic graph pruning merely because aggregate accuracy is high. The challenge's same-model baseline/enriched graph prediction experiment still requires its own biological task and measured labels.
