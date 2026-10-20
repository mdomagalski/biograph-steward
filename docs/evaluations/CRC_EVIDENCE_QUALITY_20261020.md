# CRC evidence-quality comparison — October 20, 2026

The source-consistency runner and app passports are implemented and deployed. The local verifier is **not ready for automatic evidence pruning**: its assisted preview retains only three of six source-supported controls, admits six semantic edits as supported, and obtains most additional flags through output-validation failures. No graph lifecycle or source record was changed.

The [machine-readable receipt](crc_evidence_quality_20261020_summary.json) contains both results, exact packet/result hashes, failure accounting, pre-execution receipts, runtime identities and authenticated export checks. See the [workflow and reference limitations](../EVIDENCE_QUALITY.md).

## Panel and comparison

Six saved CRC publications supply 42 cases: six exact-excerpt controls, 18 protein/citation/quotation binding edits, 12 semantic edits and six complete unmodified CIViC annotations. The first 36 have AI-authored source-contract references; the six original annotations are unscored. Sources are reused development material. These are not independent biomedical gold labels, representative valid graph edges, independent studies or an unseen biological test.

The three views share the complete case inventory. “Flag” means a quarantine proposal or a request for review; it does not mean a relationship is biologically false. Invalid model output counts as a request for review and remains in the denominator. Supported-preview retention is separate from human acceptance.

| View, final follow-up | Supported controls retained | Injected errors retained | Flag precision | Flag recall | False flags | False quarantine proposals |
|---|---:|---:|---:|---:|---:|---:|
| Original unverified preview | 6/6 | 30/30 | Undefined | 0% | 0 | 0 |
| Deterministic checks | 6/6 | 12/30 | 100% | 60% | 0 | 0 |
| Checks plus verifier | 3/6 | 6/30 | 88.9% | 80% | 3 | 0 |

**The assisted recall increase is not evidence of better semantic verification.** Among the 12 semantic edits, six were incorrectly retained with valid SUPPORT outputs, one received a valid NOT_ENOUGH_INFORMATION judgment, and five were withheld because their outputs were invalid. Thus five of the six extra flags over deterministic checks came from format failures. Two supported controls also failed output validation; a third received NOT_ENOUGH_INFORMATION. Zero false quarantine proposals must not obscure the three false review flags or the six false-support admissions.

The model admitted the controlled statistical-negation edit for PMID 26812186 as supported. Exact passage retrieval and a valid response envelope did not ensure that the passage entailed the altered claim. All such cases remain inspectable in the report.

## Executions and preserved failure

The first execution used the original full-quotation response contract. It requested 24 model turns, blocked 18 integrity cases without inference, validated four responses and rejected 20: two incorrect task identities and 18 altered/nonmatching quotations. Its assisted preview retained zero supported controls and admitted one injected error. That apparent 29/30 error flag rate was dominated by abstention after failures, not successful reasoning.

An identity-only follow-up packet was prepared but **never executed**. The final executed follow-up explicitly froze both exact task-ID constraints and an index-only citation interface. The model selects supplied passage IDs; the application attaches exact saved text. Raw selections and bound outputs are preserved. No verdict, explanation or context judgment is repaired, and no failed response is retried. The evidence-selection instructions/schema change explicitly; claims, source text, references, decision rules and 24-turn budget are unchanged byte for byte.

| Execution | Requested turns | Structurally blocked cases | Validated responses | Invalid responses |
|---|---:|---:|---:|---:|
| Original quotation contract | 24 | 18 | 4 | 20 |
| Bound task/passage selection | 24 | 18 | 15 | 9 |

The follow-up's nine invalid responses comprise six duplicate-passage selections and three incomplete/malformed responses that reached the 3,000-token limit. Its 15 valid responses contain 12 SUPPORT and three NOT_ENOUGH_INFORMATION verdicts, with no CONTRADICT verdicts. Four of the six unmodified original annotations received valid assessments; none has an independent scientific support label. Validation is not an accuracy label.

Both executions used the existing Brev L40S service: `nvidia/Llama-3.1-Nemotron-Nano-8B-v1`, revision `54641c1611fcff44fa4865626462445e0a153fc7`, the existing pinned vLLM deployment, `nemotron_nano_v1`, 3,000 output tokens, a 120-second request timeout and one request per eligible case. Total requested turns: 48. No model restart, new model/provider, source retrieval, AWS resource, hidden repair, automatic review event or further prompt search followed the final scores.

## App and verification

The app lists completed, verified comparisons under **Evidence-quality comparison**. Each report contains all three previews, exact source passages, proposed dispositions, before/after test edits and unscored original annotations. Hidden preview cases remain in the export.

Real CIViC assertion passports receive only the unmodified-annotation assessments, bound to the exact Pharos snapshot, CIViC snapshot and assertion revision. Synthetic edits never attach to real edges. The general assertion table now includes molecular-profile assertions through their protein crosswalks: the saved source displays all 41 therapy-response assertions, rather than an empty table. Existing human review controls remain separate and create new runs.

- [Final comparison on Brev](http://127.0.0.1:8767/api/evaluation/crc_evidence_quality_v2_20261020/)
- [Preserved initial comparison](http://127.0.0.1:8767/api/evaluation/crc_evidence_quality_20261020/)
- [Source workbench](http://127.0.0.1:8767/?run=crc_evidence_quality_source_20261020)

These links require the existing SSH forward and workspace sign-in. Saved artifacts are at `runs/crc_evidence_quality_20261020/live/` and `live_v2/`. Replay without inference:

```sh
python3 app.py quality-verify --result runs/crc_evidence_quality_20261020/live_v2
```

All 394 tests pass on macOS Python 3.14 and Brev Python 3.12, with one optional integration test skipped on each. Offline verification reproduces both results, decisions, model/source bindings, exact quotations and reports without another model call. Authenticated HTTP reports/metrics match saved bytes; both ZIP exports match all 52 files each; anonymous access is rejected. The live scoped endpoint returns only the two original-annotation passports for the checked edge, with no injected edits. All 12 earlier reports remain byte-identical. Chrome visual checks cover the preview filters, profile assertion table and source-verification passport; receipts accompany the summary.

## Decision and limits

Keep deterministic checks as the reproducible foundation and model assessments advisory. Do not automatically accept, quarantine or delete graph edges based on this model. Before promotion, address repeated passage IDs and incomplete outputs under a separately declared interface, then evaluate non-extractive source-support cases with independent review and additional reserved publications. More retrieved rows do not resolve the observed entailment errors.

Human scientific labels remain zero, scientific accuracy remains null and scientific improvement remains unestablished. This experiment does not reopen the consumed DepMap holdout or change any Pharos feature/source policy. The challenge's same-model measured graph-link comparison and independent biological pruning evaluation remain separate work.

## Identities

- First engine commit: `654fd15ed73d8890b6934416e718b96108869dd6`.
- Final follow-up engine commit: `099d8e153a1fdf18fb3040ba69d7fef7a739fab0`.
- First packet: `6a86fea5a9eed6dfb09740ba1b47eebf98666ebd39426cc24d40d9dd8198334f`.
- Final follow-up packet: `f0cc9db5080342af63a829b280b3e484c35140528d34f1bc25b5584d43e57070`.
- First result: `04935be9f7dba554d93c297936e6a2d5a40efba6dc3031c026bc4486e73e3357`.
- Final follow-up result: `2c3b8b2798a070d68641c4f7f360c8af4bfe3ca478441e5276f1f6c6a75d565a`.
