# Source verifier development results — October 15, 2026

Version 0.7.0 adds a supplied-document source verifier and external-label scorer. This run measures abstract interpretation after citation selection. It does not establish improved graph prediction, clinical truth or automatic evidence-pruning safety.

## Fixed evaluation

- Dataset: SciFact custom document-disjoint development subset, 104 claims / 119 claim–abstract pairs (50 SUPPORT, 22 CONTRADICT, 47 NOT_ENOUGH_INFORMATION). Whole development claims touching any training document were excluded during preparation.
- Integration smoke test: 20 training pairs, selected by ascending task-ID hash. Labels matched 16/20; correct label plus complete rationale matched 15/20. No prompt changes followed this pilot.
- Requested model: `gpt-6-astra`, using the existing signed-in Codex CLI. The CLI does not independently return served model identity. Each pair used one tool-disabled, ephemeral, read-only turn in a temporary directory; maximum three exact source sentences and 90 seconds per turn.
- Full subset evaluated once, without a pair limit, with four concurrent independent turns. Training-pilot and development contract hashes match. Gold labels were parsed after predictions closed. All 119 turns passed output/citation validation; no repairs or alternate-model fallbacks.
- No prespecified scientific promotion threshold. These are exploratory development estimates; this subset is now observed and cannot serve as an untouched final test for later tuning.

## Results

| Workflow | Label accuracy | Macro F1 | Support precision | False-support rate | Label + complete rationale |
|---|---:|---:|---:|---:|---:|
| accept_all | 42.0% | 19.7% | 42.0% | 100.0% | 3.4% |
| always_insufficient | 39.5% | 18.9% | — | 0.0% | 39.5% |
| lexical_overlap | 52.1% | 36.7% | 66.7% | 13.0% | 47.1% |
| verifier | 79.0% | 78.0% | 94.7% | 2.9% | 74.8% |

The live verifier matched **94/119 labels** and **89/119 labels with complete rationales**. It predicted SUPPORT for 38 pairs: 36 matched expert SUPPORT and two were expert insufficient-information pairs. Support recall was 36/50 (72.0%); contradiction recall was 15/22 (68.2%). Of 25 label errors, 19 were insufficient-information predictions for expert-decisive claims. The remaining six were wrong decisive verdicts. All errors remain in the report; expert labels were not overridden.

| Expert label | Predicted SUPPORT | Predicted CONTRADICT | Predicted insufficient | Error |
|---|---:|---:|---:|---:|
| SUPPORT | 36 | 2 | 12 | 0 |
| CONTRADICT | 0 | 15 | 7 | 0 |
| NOT_ENOUGH_INFORMATION | 2 | 2 | 43 | 0 |

Complete rationale coverage was 47/72 decisive pairs (65.3%), irrespective of the predicted label. Label-aware sentence precision was 54/95 (56.8%) and recall was 54/132 (40.9%). These require whole rationale sets, not just one matching fragment. Alternative rationale sets are preserved. Sentence recall counts the union of gold rationale sentences, so selecting one sufficient alternative need not recover every annotated sentence. Invalid-reference and model-error rates were both zero.

False support is predicted SUPPORT among expert non-SUPPORT pairs (2/69 for the live verifier). Always-accept uses an arbitrary first-sentence citation. The fixed lexical rule supports when the best sentence covers at least half of non-stopword claim tokens and never predicts contradiction. These are sanity comparisons, not state-of-the-art baselines or comparisons with the original Pharos graph.

Pairs share claims and documents and are not independent experiments. Reported percentages are point estimates, without confidence intervals. The custom subset is small, general scientific rather than CRC-specific, and foundation-model exposure to this public benchmark cannot be excluded.

## Reproducibility

- Result: `runs/verifier_document_holdout_20261015/` (`report.html`, `metrics.json`, `contract.json`, `run_manifest.json`, frozen inputs/gold, predictions and 119 sanitized traces). Source licensing/attribution is preserved in `benchmark_manifest.json`. Real data and generated results remain outside Git.
- Run manifest SHA-256: `fb88b084970853547b6933a1a307138401faed40e5386ca08dd647536723c16f`.
- Prompt/schema contract SHA-256: `d42545a5cd71777fc6e2416465f801e0486ec5aefc3d73b01fad6e36f0d58ab0`.
- Selected input bytes SHA-256: `a6750c719ab3f70d46da63674311b45928b3ee1e207f07ea5271d5bfc35c7551`.
- Selected gold bytes SHA-256: `47ccb4f2c84657325463431d612d4a724befff65ab3e3fe80d9a10a8b7ecbc8c`.
- Closed predictions SHA-256: `81ace83986e3d812a66bb2c9e335494bf8f92ea31b6e7a9551713c7619d09b0d`.
- CLI version: `codex-cli 0.162.0-alpha.17.2`. Requested turns: 119. Usage returned for all 119 pairs: 1,385,407 input tokens, including 890,624 cached-input tokens; 22,007 output tokens. Internal transport attempts and monetary cost are not inferred.
- Offline `verification-score` reproduced the saved metrics exactly in `runs/verifier_document_holdout_rescore_20261015/`, without model calls. All 205 regression tests passed, including HTTP tests; the focused verifier tests also passed after the final runner metadata changes.
- A responsive report with context matches, mismatches, missing details and follow-up is in `runs/verifier_document_holdout_review_20261015/`. It was rendered from the same frozen predictions with identical metrics and no new model calls. Open <http://127.0.0.1:8766/api/evaluation/verifier_document_holdout_review_20261015/> while the app is running.

See [run commands](RUNNING_VERIFIER.md), [protocol and metric definitions](VERIFIER_PROTOCOL.md), and [source preparation/licensing](VERIFICATION_BENCHMARKS.md). SciFact source: [Wadden et al. (2020)](https://aclanthology.org/2020.emnlp-main.609/).

## Next integration

Keep assessments advisory. Add them beside a small frozen CRC/CIViC evidence set, with explicit variant, regimen, population and study-context checks and controlled context edits. Missing source text stays an access limitation. Automatic graph acceptance, rejection and pruning remain disabled. A later challenge comparison still needs the same prediction method and held-out split on baseline and enriched graph variants.
