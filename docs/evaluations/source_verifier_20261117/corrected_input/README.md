# Corrected Evidence-input diagnostic

Predeclared consumed-reference diagnostic, not a new independent test or a causal model-capacity experiment.

[Complete aggregate](aggregate.json) · [Source and protocol pins](protocol_metadata.json)

The original secondary runtime omitted full Evidence payloads already present in captured curation responses. The separate full view preserves those objects; three unresolved historical inputs remain explicit abstentions.

Agreement with released curator labels for selected sentence/native-claim pairs; annotator expertise is unknown. Not whole-graph biological accuracy or a Pharos edge-error reference.

All fresh arms use the qualified author BASE method and current technical guards. Cached Nemotron rows retain their earlier guards and outcomes unchanged. The primary analysis compares these complete workflows; a separate pre-generation common technical mask provides the comparable-input sensitivity analysis. Native deterministic decisions, technical abstentions and sampling variability remain included. Identical prompts at temperature0.1 can still yield different outputs.

## Primary: complete 145-pair workflow comparison

145 pairs in 87 connected source groups: 72 labelled supported and 73 labelled unsupported.

| Fixed arm | Balanced accuracy | Coverage | Supported claims rejected | Unsupported claims supported |
|---|---:|---:|---:|---:|
| Nemotron original input (cached) | 57.9% | 142/145 | 29/72 | 29/73 |
| Nemotron original curated Evidence | 56.5% | 134/145 | 31/72 | 21/73 |
| Qwen original input | 74.4% | 142/145 | 31/72 | 3/73 |
| Qwen original curated Evidence | 68.1% | 137/145 | 36/72 | 2/73 |

| Paired contrast | Difference in percentage points | Pointwise 95% interval |
|---|---:|---:|
| Nemotron original curated Evidence minus Nemotron original input (cached) | -1.4 | [-9.1, +5.5] |
| Qwen original curated Evidence minus Qwen original input | -6.2 | [-13.5, -0.6] |
| Qwen original input minus Nemotron original input (cached) | +16.4 | [+6.1, +25.7] |
| Qwen original curated Evidence minus Nemotron original curated Evidence | +11.6 | [+2.3, +20.7] |

## Secondary: fixed common technical mask

137 pairs in 83 connected source groups: 70 labelled supported and 67 labelled unsupported.

| Fixed arm | Balanced accuracy | Coverage | Supported claims rejected | Unsupported claims supported |
|---|---:|---:|---:|---:|
| Nemotron original input (cached) | 59.1% | 135/137 | 28/70 | 26/67 |
| Nemotron original curated Evidence | 60.0% | 134/137 | 31/70 | 21/67 |
| Qwen original input | 75.6% | 137/137 | 31/70 | 3/67 |
| Qwen original curated Evidence | 72.8% | 137/137 | 36/70 | 2/67 |

| Paired contrast | Difference in percentage points | Pointwise 95% interval |
|---|---:|---:|
| Nemotron original curated Evidence minus Nemotron original input (cached) | +0.9 | [-6.7, +7.7] |
| Qwen original curated Evidence minus Qwen original input | -2.8 | [-8.4, +1.1] |
| Qwen original input minus Nemotron original input (cached) | +16.5 | [+6.0, +25.9] |
| Qwen original curated Evidence minus Nemotron original curated Evidence | +12.8 | [+3.0, +22.2] |

## Prespecified focal decision

Only the primary all-pair Qwen curated-Evidence minus Nemotron curated-Evidence comparison determines this gate. The secondary common-mask analysis cannot rescue a failed primary gate.

| Required component | Result |
|---|---|
| Positive balanced-accuracy difference with its 95% interval entirely above zero | Passed |
| No increase in supported-claim rejections | Not passed |
| No reduction in coverage | Passed |

Overall primary gate: **not passed**.

Intervals use 10,000 paired connected-source-group resamples with seed 20261117. They are pointwise, not multiplicity-adjusted, and describe this consumed reference rather than independent biological replication. Abstentions receive no balanced-accuracy credit and remain in every declared denominator.

The full-Evidence preflight recorded 12 author-native deterministic decisions per fresh full-input arm. Those decisions do not require LLM inference. Pre-generation prompt comparisons found 115 identical, 10 changed and 20 noncallable pairs for each model. Even identical requests can differ through sampling.

No production promotion or automatic Pharos pruning follows this diagnostic. Original reference results and cached outcomes are unchanged. No current-app assertion has been qualified as eligible for this research verifier.

## Descriptive component audit

A post-outcome [aggregate component audit](component_audit.json) accounts for every pair without introducing a new mask, prediction, fit or promotion rule. The full-Evidence path has 125 LLM-eligible pairs, 12 author-native deterministic decisions and eight technical abstentions. Both full-input arms reject all 12 deterministic cases before an LLM call, including six curator-supported claims. These prechecks account for six of Qwen's 36 supported-claim rejections. Its other 30 supported-claim rejections occur in the LLM-eligible component.

The observed Qwen full-minus-original change decomposes across these disjoint source-input partitions. Contributions use the original 72/73 class denominators, rather than averaging selected subset scores.

| Full-input component | Pairs | Contribution to whole-frame Qwen balanced-accuracy change |
|---|---:|---:|
| Author-native deterministic decisions | 12 | −1.398 percentage points |
| Technical abstentions | 8 | −3.434 percentage points |
| LLM prompts changed between views | 10 | −0.694 percentage points |
| LLM prompts identical between views | 115 | −0.694 percentage points |

The change under identical prompts cannot be attributed to restored metadata. This is descriptive accounting after outcomes were opened, not an additional independent comparison. Three length-capped Nemotron responses remain abstentions with no retries.

The published [Gilda context-disambiguation method](https://doi.org/10.1093/bioadv/vbac034) and [official API](https://gilda.readthedocs.io/en/latest/modules/index.html#gilda.api.ground) provide an existing solution family. A read-only [installed-model coverage check](context_model_coverage.json) finds no applicable registered Gilda or Adeft model for the three triggering strings across the six supported automatic rejections. The installed Gilda bank has 1,008 models above its official cutoff, from 1,287 resource entries. Passing context alone would therefore not activate an existing model for these triggers. No context predictions, new ablation or retraining were run. The original focal gate remains failed and no production pruning rule changed.
