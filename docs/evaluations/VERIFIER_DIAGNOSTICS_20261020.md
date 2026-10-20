# Verifier diagnosis — 2026-10-20

Direct claim classification remains unreliable. Ordinary and guided-choice
outputs, requested reasoning-on, and a balanced example recipe all fail the
six-case development gate. A separate source-only probe covers the requested
arm/endpoint associations in four answers, but adds unsupported material.
This supports testing a narrower extraction interface; it does not establish a
reliable extractor, scientific accuracy or graph improvement. The recorded
biological comparison remains unchanged.

## Reasoning-off classification

Six invented ORCHID claims cover two supported statements, two explicit opposing
findings in the same context, and two unsupported changes of regimen/population.
Each receives one ordinary and one guided-choice request, alternating arm order.
Requests share the exact user prompt and source. Guided requests alone specify
`guided_choice` and `xgrammar:no-fallback`.

| Configuration | Valid responses | Reference matches | Predictions |
|---|---:|---:|---|
| Ordinary, thinking off | 6/6 | 2/6 | All insufficient information |
| Guided choice, thinking off | 6/6 | 2/6 | All insufficient information |

All completions contain five tokens. Inputs contain 283–290 tokens. No response
is truncated. The synthetic gate fails; the original packet's biological stage
is not executed. This does not prove that decoding has no effect on other tasks.

The model service is healthy and configured for the pinned model/tokenizer
revision `54641c1611fcff44fa4865626462445e0a153fc7`, BF16, vLLM 0.8.5,
16,384-token context and the existing L40S. Chat `/tokenize` followed by
`/detokenize` confirms the complete user prompt, source and thinking-off system
message, standard role boundaries and assistant header. Its 284-token count
matches the first completion's prompt usage. No generation is performed by those
tokenization checks. Thinking-on tokenization likewise confirms the system
switch and no prefilled thinking block.

## Copying and elementary reading

A separate eight-request plan begins with two copying checks. Its first attempt
stops after two: the model returns `CHECK_7319.` instead of `CHECK_7319`, and
copies `blue` exactly. The extra period is a formatting failure, not evidence
that the source is unreadable. That result remains failed and unchanged.

A new packet changes only the echo instruction to delimit its target explicitly
with quotation marks. References, classification prompts, parsing and stop rules
remain unchanged. Both copying checks pass, allowing six ordinary classification
requests. Each policy sees the same source: a crate contains three red balls and
no blue balls. Claims concern three red balls, a blue ball, and a steel crate.

| Prompt policy | Valid responses | Reference matches | Error |
|---|---:|---:|---|
| Existing verification instructions | 3/3 | 2/3 | Blue-ball contradiction classified as insufficient information |
| Neutral reading-comprehension instructions | 3/3 | 2/3 | Same error |

The observed wording change does not resolve the elementary contradiction. This
small probe does not establish which aspect of the earlier ORCHID fixture causes
its additional failures. It is insufficient to attribute all errors to model
capacity, the word “untrusted,” or a specific decoder.

## Requested reasoning and final calibration

The next frozen packet changes the requested system mode to thinking on and uses
NVIDIA's recommended temperature 0.6 and top-p 0.95, with a 2,048-token output
budget. The user instructions initially still demand a bare label and no
explanation. All six answers are valid NEI labels, with five completion tokens
and no native thinking envelope or separate reasoning field. The gate fails.
This is a requested configuration change, not evidence that native reasoning was
exercised and failed. NVIDIA's [instructions at the pinned revision](https://huggingface.co/nvidia/Llama-3.1-Nemotron-Nano-8B-v1/blob/54641c1611fcff44fa4865626462445e0a153fc7/README.md)
describe native thinking markers even when no reasoning is needed.

One final calibration plan is frozen before either attempt: run six ordinary
cases with three balanced, unrelated crate examples; if that fails, run the same
recipe with thinking on and instructions that allow native format while
constraining only the final answer. Stop classifier tuning after both fail.
The scored ORCHID claims and their labels are absent from the examples.

| Configuration | Valid responses | Reference matches | Observation |
|---|---:|---:|---|
| Requested thinking on, original final-only prompt | 6/6 | 2/6 | All NEI; no native thinking observed |
| Reading recipe with examples, thinking off | 6/6 | 2/6 | One correct positive and one false SUPPORT; no contradiction recognized |
| Reading recipe with examples, native-compatible thinking-on prompt | 6/6 | 2/6 | All NEI; no native thinking observed |

None passes the gate. No biological claim-classification request is made. The
different mode, sampling, budget, examples and final-format wording form
configuration comparisons; these runs do not identify one isolated cause or
prove that the model lacks all relevant capabilities.

A final, separately frozen **unscored runtime control** sends the official
model-card equation example with thinking on and no verifier or final-label
instructions. It produces a complete native thinking envelope and 709 completion
tokens. Only envelope metadata and hashes are retained; reasoning text and the
final solution are not saved. This establishes native-format operation on the
current deployment. It does not demonstrate reasoning or correctness on the
verification cases, but weakens a general serving-format-failure explanation.

## Separate source-only capability probe

After stopping classifier experiments, a new exploratory plan makes **four
claim-free extraction requests**: two source questions, each with full and focused
abstract windows. This is a separate capability question, not continuation of a
failed classification stage. It supplies neither a candidate claim nor reference
facts, issues no verdict and cannot reopen a classification gate.

All four answers cover the requested core associations on AI-assisted source
review, corroborated by a second AI audit:

- KRYSTAL: adagrasib monotherapy has 19% response among 43 evaluable patients;
  adagrasib plus cetuximab has 46% among 28.
- PRIME: in the WT KRAS stratum, the panitumumab-FOLFOX4 versus FOLFOX4 comparison
  has significant PFS improvement (P=.02) and a nonsignificant OS increase
  (P=.072).

**These are not four clean extractions.** Every answer adds unrequested material.
The full KRYSTAL answer falsely says grade-5 event information is absent despite
the source's explicit report of no grade-5 events. The focused answer presents
44 as an overall patient total, losing the source's separate combination-group
count. PRIME answers add testing and scope-completeness commentary that is not
part of the requested facts; result availability also should not be rewritten
as the exact proportion tested.

The defensible result is requested-field coverage in four answers, with explicit
extra errors or misleading scope in two. Whole-answer accuracy remains
unestablished. The frozen summaries' correctness fields remain null. A separately
hashed `source_facts_review.json` binds the AI review to the result and inputs;
independent human scientific labels remain zero.

The next product increment should test claim-free structured source-fact records
with exact provenance and only requested fields. Claim comparison should use
those connected facts and explicit application checks. Free-form narrative and
the current model's SUPPORT/CONTRADICT/NEI decisions should not approve assertions.
Application checks should detect explicit entity, regimen, endpoint and
qualification mismatches; ambiguous mappings and missing context still require
review. This is not a general deterministic entailment engine.

## Preservation and interpretation

The original 18-case result replays unchanged with result hash
`11c29c521832605eb9c2ad4a50689707cb1843377ee7179e62b384c34d005acd`.
Its literal-check count of seven withheld edits needs an additional qualification:
one flag concerns a synonym difference (“previously untreated” versus “no prior
chemotherapy”), rather than recognizing the actual regimen error. Correct flags
and correct explanations must be evaluated separately.

Artifacts are saved under `runs/verifier_diagnostics_20261020/`. Source documents,
requests and raw model answers are excluded from Git. Frozen v1 runner copies in
`frozen_v1/scripts/`, and later v2/v3 snapshots, preserve replay when the working
diagnostic implementation changes. Matching code hashes are required; an updated
runner cannot silently rescore the old packet.

| Artifact | Packet hash | Result hash |
|---|---|---|
| Initial six-claim paired diagnostic | `26ae75f9f92131328f43c796daf52fc46825a6c69e13d9df577f80fec4b14abc` | `5d4764d6eec0c85c7edfcc57419418ebefd55579590e446338260fd240ad4662` |
| Initial echo/copy attempt | `49869d62bd7cc6e8484ec4e3986a964962446189b97367b582b117c70d5a33c3` | `10ec583f3439db80dd7f79a83a1c92e14793180c9b408909e030c831d468446c` |
| Explicit echo delimiter and reading comparison | `5c89f12259794d5c1e35ee6dfc9676050ebb0bb254460d05f09867f7dfd2e7e4` | `bd0af71f2c626a86f40b22f107a32b55a49886fe3771d9a5ca1efe7471a5c99e` |
| Requested thinking on, original prompt | `a674df2cd3233f9b07e1d8adb952acd390f8154b82c8f4fd807f59b27afbceb3` | `bef4b791cd1a8add8b32eda6d9ae7ac374c864125b28c4884b07fa88ee9147be` |
| Example recipe, thinking off | `33afc60491a03524be0806e220a36a20ba7e45d898198e8048b57dfc75c401d3` | `10fcdfda243cf1a47e4e7444e8ed0c86bbe7c302e57f0869b6c441ebffd3d59c` |
| Example recipe, native-compatible thinking on | `dcaea4229b171a33df25a22921d4cf8bb55dd45e8decaaf76577f0af8c726daf` | `db5781a7208cb4fdbbfec0a5491236daa77f1dff94578ec68c77eb4413d15a72` |
| Source-only extraction | `e1740b5571d40ce92da41ee1f4b57b100eb0703b2189b9139a98419f77622870` | `8e2b3b5496d4ca4e3398f29856bc3da8ef133de65f5b3764556ff62c1e222cdb` |

The [machine-readable summary](verifier_diagnostics_20261020_summary.json) records
request inventories and separate results: 44 development requests plus one
unscored official-example control, with zero biological claim-verification calls.
The four source-only biological requests are separate exploratory extraction
probes. The final full software suite runs
423 tests, with one optional integration skipped and no failures. An initial
sandboxed invocation could not bind HTTP test listeners; the passing invocation
uses loopback access. Software tests validate contracts and reproducibility,
not model judgments.

See [the diagnostic protocol](../VERIFIER_DIAGNOSTICS.md) for preparation,
execution, stage gates and exact replay. Classification references are not sent
to the model. Output errors remain in denominators; no old outputs are repaired
or promoted to supported assertions.
