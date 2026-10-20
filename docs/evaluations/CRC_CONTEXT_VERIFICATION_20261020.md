# CRC context-verification comparison — 2026-10-20

The optional context tool and paired comparison are implemented and deployed on
Brev. The application preserves the raw model judgment separately from exact
span validation and support eligibility. All decisions remain advisory; graph
and human-review states are unchanged. The default planner/verifier configuration
has not been promoted to the experimental context tool.

The useful result in this small panel is the literal review check: it withholds
7/9 edited claims while retaining all 9 valid paraphrases. The legacy verifier
admits 8/9 edits as supported. The new context verifier validates **0/18** responses,
withholding every valid control as well as every edit. Its apparent 100% error
flagging comes entirely from invalid-output abstention and is not an improvement.
The context gate cannot be evaluated meaningfully because no response reaches it
with a validated assessment. Keep the model tool experimental and disabled by default.

## Fixed panel and execution

The 18 predeclared cases comprise nine valid paraphrases and nine context edits
from PubMed [37870968](https://pubmed.ncbi.nlm.nih.gov/37870968/),
[36546659](https://pubmed.ncbi.nlm.nih.gov/36546659/) and
[20921465](https://pubmed.ncbi.nlm.nih.gov/20921465/). These publication IDs are
outside the 12-paper previous CRC literature inventory. This excludes previous
provided-document sources, not model training, upstream Pharos citations or
shared clinical cohorts; PRIME may be represented in earlier meta-analyses.
Claims and rationale references are AI-authored and inspected before freezing;
independent scientific and rationale labels remain zero. No biological graph
improvement, clinical accuracy or independent replication is established.

The initial advanced-schema attempt was stopped after one legacy response, one
120-second context timeout and one interrupted context request. The pinned
decoder logged fallback from xgrammar to outlines for advanced schema keywords.
This is an incomplete infrastructure attempt, not a scored completed comparison.
Its packet, execution record, two saved traces and interruption receipt remain
under `runs/crc_context_verification_20261020/aborted/`.

One separate invented wire probe returned JSON in 13.1 seconds. It marked absent
dimensions unknown with empty claim spans and failed local validation; it is not
counted as biological evidence or a successful assessment. The compatibility
follow-up uses a native fixed boolean passage map, with exact span and length
constraints enforced locally. Claims, source selections and references are
byte-identical to the original freeze. It is a compatibility follow-up on that
panel, not another independent fresh test.

The completed follow-up issued 36 requests: one legacy v2
passage-selection turn and one context turn per case, alternating arm order.
Model/tokenizer revision `54641c1611fcff44fa4865626462445e0a153fc7`,
NVIDIA Llama-3.1-Nemotron-Nano-8B-v1, vLLM 0.8.5, L40S,
`nemotron_nano_v1`, temperature zero, 3,000 output tokens and 120-second timeout
were unchanged. No retries, repair, extra tools, retrieval, fallback model or
reference labels were supplied. The serving decoder's logged grammar fallback
is distinct from the application's prohibited retry/model-fallback behavior.
The model service was not restarted. Defaults and planner settings were not changed.

## Recorded advisory previews

| View | Valid controls retained | Context errors retained | False flags on valid controls |
|---|---:|---:|---:|
| original | 9 / 9 | 9 / 9 | 0 / 9 |
| literal_checks | 9 / 9 | 2 / 9 | 0 / 9 |
| legacy_v2 | 9 / 9 | 8 / 9 | 0 / 9 |
| context_raw | 0 / 9 | 0 / 9 | 9 / 9 |
| context_checked | 0 / 9 | 0 / 9 | 9 / 9 |

Original and literal-check views retain unverified records. Model views require
a valid SUPPORT response. Context raw and checked reuse identical responses;
their difference isolates the application gate, with no additional inference.
A withheld assertion requests review; it does not declare a biological negative.
Output failures remain failures in all-case denominators and are never credited
as correct reasoning merely because they withhold an erroneous claim.

## Verdict and reasoning diagnostics

| Verifier | Valid responses | Reference verdict matches | Reference passage sets covered | Expected context axis aligned |
|---|---:|---:|---:|---:|
| legacy_v2 | 17 / 18 | 9 / 18 | 10 | None |
| context_v3 | 0 / 18 | 0 / 18 | 0 | 0 |

These are reference-agreement diagnostics, not independent scientific accuracy.
Passage overlap does not establish entailment or rationale correctness. The
legacy NEI contract requires no evidence indices, while the context contract
permits citing context gaps; passage coverage is consequently not a fair standalone
comparison of reasoning quality. Expected-axis alignment applies only to context
outputs, can agree even when a raw verdict disagrees, and uses AI references.
Expert reasoning correctness remains unscored. Review worksheets preserve empty
source-support, reference-agreement and rationale-correctness fields.

The new verifier's first validation errors are 13 citation-budget failures, four
explanations exceeding 300 characters, and one exact-span/index failure. None of
its responses reaches the 3,000-token cap; the legacy verifier's single invalid
response does. These counts identify the first rejected field, not an exhaustive
audit of all defects in a response. All 18 raw, unvalidated context labels are
SUPPORT, as are all 17 validated legacy labels. Neither output contract provides
evidence of improved context reasoning. Relaxing length/citation checks after
seeing these answers would change the experiment; no such rescoring was used.

Exact invalid-output reasons and latency/token diagnostics are recorded in the
[machine-readable summary](crc_context_verification_20261020_summary.json).
Do not turn local formatting success or conservative abstention into a biological
improvement claim. Do not enable automatic graph pruning or acceptance.

## Reproducibility and access

- Implementation: `072b64f433ab359e490237621753f23e498528ed`.
- Follow-up packet: `fc635d934a39b5d0b8daf6f0aa7f64edcb75486833c8248c9e58735c655c4ba6`.
- Follow-up result: `11c29c521832605eb9c2ad4a50689707cb1843377ee7179e62b384c34d005acd`.
- Mac Python 3.14 and Linux container Python 3.12: 403 tests, one optional
  integration skipped, no failures. The first Mac full-suite invocation used
  the host proxy for loopback and failed HTTP tests with 503; the recorded passing
  invocation explicitly excludes loopback from the proxy.
- Both earlier evidence-quality comparisons replay unchanged. Protected report,
  metrics and complete export are byte-identical to the local replay; previous
  quality and fresh-growth reports remain intact. Synthetic cases never attach
  to real assertion passports. No access token or raw paper is committed.

With the existing SSH tunnel and workspace sign-in, open
[the comparison](http://127.0.0.1:8767/api/evaluation/crc_context_verification_map_20261020/).
The app lists it alongside earlier comparisons. For a new provided-document task,
use the explicit `context-assess` tool described in
[CONTEXT_VERIFICATION.md](../CONTEXT_VERIFICATION.md). Broader database integration
remains deferred until a concrete, nonduplicative evidence gap is identified.
