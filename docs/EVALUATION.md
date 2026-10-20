# Frozen-source evaluation and one bounded question planner — v0.6

The v0.8 portability increment adds `--planner nim` and shared/role-specific model configuration. See [Brev/NIM setup](PORTABILITY.md). `--planner live` uses the configured provider; Codex and replay remain available. A frozen suite's engine fingerprint intentionally changes with the new adapter: initialize a new suite before collecting new-model results, and retain earlier suites/reports unchanged.

The [first live Nemotron comparison on Brev](evaluations/NEMOTRON_20261019.md) completed all 24 development questions. Its all-abstention result is retained as a failure of planning usefulness, with scientific metrics pending. See the [local model setup](LOCAL_MODEL.md) to reproduce the configured serving environment.

The current [planning protocol](PLANNER_PROTOCOL.md) is an explicitly selected hybrid of exact lexical binding, application scope checks and constrained model planning. The [v3 comparison](evaluations/TOOL_SHAPES_V3_20261019.md) matched 24/24 draft plans, with eight application-enforced abstentions and 16 query outputs equal to the enriched deterministic arm. The unsuccessful v1 and v2 results are retained. Comparisons reuse the development questions with that reuse disclosed; a new engine fingerprint requires a new frozen suite. Source files, reference cases and display budgets were checked against the first experiment rather than refreshed or relabeled. Held-out scope evaluation and scientific adjudication remain pending.

The runner compares the expanded Pharos baseline with its CIViC-enriched copy and a single question-planning model using the same deterministic tools. It exports source-bound reviewer worksheets and a read-only HTML report. This is a research-workbench evaluation, separate from the challenge's still-pending controlled prediction experiment.

The included 24 questions are **draft development scenarios**, grouped into 15 question families. Paraphrases are not independent biological observations. Reference plans specify scope; they are not biomedical answers, paper-verified labels or a held-out test. A reviewer must approve scope and adjudicate evidence before scientific accuracy is reported. The supplied pilot has no held-out test cases.

The separate [prospective planning workflow](PROSPECTIVE_PLANNING.md) prepares 32 additional draft questions in 16 paired families against the unchanged v3 planner and exact control sources. It detects simple case reuse, provides blank scope-review sheets before inference, and distinguishes offline application-constraint diagnostics from live model performance. The cases are AI-prepared same-source challenges, not an independent biological benchmark.

Its [first live run](evaluations/PLANNING_CHALLENGE_LIVE_20261020.md), after explicitly AI-attributed engineering review, matched 22/32 scope plans and executed seven queries with incorrect scope. Six mismatches were predetermined by application constraints. The earlier development and new prospective scores use different cases; they are not a paired software-version comparison. Human-approved references and scientific judgments remain absent.

The [paired v4 regression](evaluations/SCOPED_TARGETS_V4_20261020.md) reuses those exact cases, sources, scope reviews and serving configuration after refining target handling. It matched 26/32 plans, with zero wrong-scope queries and all 17 executed outputs equal to the deterministic enriched arm. Eight cases improved and four regressed; six supported requests were declined. The new `planning-regression-prepare` command binds a changed planner to the historical control and identical review worksheet. This is regression evidence after tuning, not another prospective or biomedical validation result.

## Run the comparison

```bash
python3 app.py evaluation-init \
  --baseline runs/crc_normalized_verified_20261014 \
  --enriched runs/crc_civic_final_20261015 \
  --out runs/evaluation_suite_01

# Deterministic comparison; the model arm is explicitly marked not run.
python3 app.py evaluation-run --suite runs/evaluation_suite_01 \
  --out runs/evaluation_results_01
```

Use `--cases path/to/cases.json` to supply a different question set; see `biograph_steward/evaluation_cases.json`. Groups must remain wholly within development or test. Use `--reviewed runs/<reviewed-copy>` at suite creation for an optional review-policy comparison. That copy must use the same Pharos/CIViC snapshots and assertion revisions. Source enrichment must preserve baseline Pharos review states, so adding data and changing human decisions are not conflated.

The suite copies raw snapshots and review events, records their exact byte hashes, derived graph/review hashes, question specifications, software hashes and common budgets. It does not refresh source data during evaluation. Changes to sources, cases or Python implementation require a new suite. Planner instructions, schema, catalogue, model request/response hashes and usage are recorded separately in execution traces.

Default display budgets are eight results and three paths per result. Use `--max-results` and `--max-paths` at suite creation to set common limits. A tool call that returns no accepted evidence is recorded as `no_evidence`; it is distinct from a planner abstention, missing source, invalid plan or unavailable model. A baseline without CIViC must abstain from the CIViC question; it cannot infer therapy response from protein context.

## Outputs and reviewer workflow

| File | Purpose |
|---|---|
| `evaluation.json` | Frozen manifest, cases, per-workflow outputs, source citations, execution traces and evidence review pool. |
| `metrics.json` | Coverage, planning agreement, review-dependent quality measures, filter decisions and explicit missing judgments. |
| `report.html` | Read-only outputs and complete evidence records, including excluded source items. |
| `case_reviews.tsv` | Approve or reject the reference scope plan against the question. |
| `answer_reviews.tsv` | Grade each workflow output and record review effort. |
| `evidence_reviews.tsv` | Adjudicate source support/relevance and retained/excluded policy decisions. |

Open TSVs in Excel, another table editor or a text editor. Preserve columns, IDs and hashes. Leave unknown judgments blank or use `uncertain`; do not fill missing values with “no.” The report shows neutral variant IDs, with the mapping available in its manifest; this reduces repeated arm labels but is **not a blinded user study**.

Suggested first review: the G13D/cetuximab question, its local-accepted counterpart and one unsupported-scope question. Compare complete profile, exact disease, therapy set, direction, origin and experimental conditions. Review the underlying publication/abstract and document where an evidence item is a curated summary rather than direct paper text. Do not infer a monotherapy effect from a combination or substitute set. Differing annotations are not automatically contradictions.

### Worksheet values

`case_reviews.tsv`: set `reference_plan_correct` to `yes`, `no` or `uncertain`, with `reviewer` and `notes`. A rejected reference requires a corrected question/reference in a **new suite**; do not silently change an evaluated case.

`answer_reviews.tsv`: `plan_correct`, `answer_correct`, `citation_support`, `conditions_preserved` and `abstention_correct` each accept `yes`, `no`, `uncertain` or blank. Supply reviewer/notes for judgments. Optional `review_seconds` is an integer from 0 to 86400. A workflow that was not executed has no answer to grade. Judge abstention against the requested scope and evidence view, not simply whether a statement is present.

`evidence_reviews.tsv`: `verdict` accepts `relevant_supported`, `relevant_unsupported`, `irrelevant`, `uncertain` or blank. `source_check` accepts `not_checked`, `record_only`, `abstract` or `full_text`. **`relevant_supported` requires an abstract/full-text check and an `evidence_locator` with a citation/location or span**, plus reviewer and notes. CIViC's ACCEPTED source status alone is insufficient. This worksheet does not accept graph assertions or create model-training labels.

For each `retained`/`excluded` source item, `filter_decision` accepts `correct`, `incorrect`, `uncertain` or blank, with reviewer/notes. Evaluate the declared filtering policy separately from scientific relevance: a useful study may be conservatively excluded because a source revision is pending. Conflicting filtering judgments for one frozen source item must be reconciled before scoring.

Score completed sheets into a new directory:

```bash
python3 app.py evaluation-score --result runs/evaluation_results_01 \
  --case-reviews /path/to/completed/case_reviews.tsv \
  --answer-reviews /path/to/completed/answer_reviews.tsv \
  --evidence-reviews /path/to/completed/evidence_reviews.tsv \
  --out runs/evaluation_scored_01
```

Incomplete sheets are allowed; unknowns remain explicit. Imports reject changed identities/hashes, duplicate rows, unknown labels and unsupported source checks. Scoring preserves original outputs, copies submitted sheets and records their file hashes/time.

## What the metrics mean

- **Coverage:** questions answered, source gaps, no-evidence results, abstentions, planner errors and unexecuted cases. A workflow that answers nothing does not receive an artificial perfect precision.
- **Judged precision:** supported relevant returned units divided by returned units adjudicated supported/unsupported/irrelevant. Unknown returned counts and lower/upper precision bounds are shown alongside it.
- **Review-pool recall:** supported returned units divided by all supported units in the reviewer pool. The pool contains returned citations and scoped raw CIViC items, including filtered exclusions. **It is not corpus recall:** Pharos paths remain display-bounded, unreviewed units may be missing, and source coverage has limits. Accepted-only answers can deliberately have low coverage until local review occurs.
- **Planning:** draft semantic-plan agreement is an engineering diagnostic. Agreement with reviewer-approved reference plans is reported separately; rationale wording is excluded. An invalid/unavailable plan is not a successful answer. The deterministic reference workflow receives a supplied scope plan, so its scope agreement is by construction, not an NLP baseline or proof that the plan is correct.
- **Human answer grades:** separate rates and denominators for plan correctness, answer correctness, citation support, condition preservation and appropriate abstention. Source-addition, local-review and planning deltas use only cases with paired yes/no answer reviews.
- **Filtering:** incorrect-decision rates for unique judged retained/excluded CIViC items. Repeated question rows do not create additional independent filtering labels.
- **Effort:** tool/model call counts, elapsed time, returned token usage and recorded human review seconds. There is no assumed price table; dollar cost remains unknown. Source loading/freezing is outside per-observation timing. Provider failures may consume tokens whose usage was not returned.

Units are CIViC evidence items or Pharos qualified assertions. Multiple records/publications are not independent experiments. Stratify by question family and source type; do not treat repeated paraphrases or shared citations as independent samples. The pilot deliberately leaves `scientific_improvement_established=false`: descriptive deltas require review and broader confirmation before a general claim.

The first comparison measures source addition (Pharos → enriched deterministic). Filtering is assessed using the retained/excluded pool. An optional reviewed copy measures review-policy effects. The planner is compared against the **same enriched graph and exact query engines**, isolating planning from source changes.

## One question-planning agent

The model gets only the question, available entity IDs/names, exact source diseases, two query tools and their limits. It emits one structured plan selecting `protein_neighborhood`, `civic_therapy` or abstention. Application code validates IDs, scope, evidence view and fields, and executes **at most one read-only local query** with the frozen budgets. Answers and citations come from the existing deterministic engines. The agent cannot accept assertions, rewrite evidence, call shell commands, refresh sources or launch other agents.

The tool contract currently cannot express extra filters such as monotherapy-only, response-direction-only, clinical-only or patient-specific conditions. The planner is instructed to abstain when these are required. A model can still choose an incorrect supported scope; the runner records that mismatch for review. Schema validation constrains execution, not biomedical understanding.

### Configure a live model locally

The implementation supports the OpenAI Responses API, a Chat Completions-compatible endpoint, and an explicit signed-in Codex CLI option, without adding Python dependencies. The API adapter uses [Structured Outputs](https://developers.openai.com/api/docs/guides/structured-outputs?api-mode=responses), rejects incomplete/refused/malformed responses and makes no automatic model fallback or repair retries.

For OpenAI, set `OPENAI_API_KEY` locally and `BIOGRAPH_PLANNER_MODEL` to a model available to your account that supports structured output. Do not paste keys into chat or commit them. The app does not automatically load `.env`. No default model is guessed.

```bash
# After setting the key and model in your local environment:
python3 app.py evaluation-run --suite runs/evaluation_suite_01 --planner live \
  --out runs/evaluation_with_model_01

python3 app.py plan-question --run runs/crc_civic_final_20261015 \
  --question 'Explore candidate CIViC response evidence for KRAS G13D and records containing cetuximab in Colorectal Cancer (DOID:9256). Preserve complete treatment sets.' \
  --out runs/one_planned_question_01
```

For a local compatible server, set `BIOGRAPH_PLANNER_ENDPOINT` to the full endpoint URL, `BIOGRAPH_PLANNER_API=chat_completions` (or `responses`), and `BIOGRAPH_PLANNER_MODEL`. Use `BIOGRAPH_PLANNER_API_KEY` only if that server requires one. The OpenAI key is used only for `api.openai.com`; it is not sent to a custom endpoint. HTTPS is required outside loopback. Embedded URL credentials and query/fragment secrets are rejected; TLS verification is never disabled.

### Optional signed-in Codex CLI

If Codex CLI is already installed and authenticated, `--planner codex` uses that existing local session. Set `BIOGRAPH_CODEX_MODEL` explicitly to an available model; `BIOGRAPH_CODEX_BIN` optionally selects the executable. No authentication file is read by this application, no key is copied, and no API-to-CLI fallback occurs. Follow the official [non-interactive mode](https://learn.chatgpt.com/docs/non-interactive-mode) and [configuration reference](https://learn.chatgpt.com/docs/config-file/config-reference) for CLI setup and supported flags.

```bash
BIOGRAPH_CODEX_MODEL='<available-model>' python3 app.py evaluation-run \
  --suite runs/evaluation_suite_01 --planner codex --out runs/evaluation_codex_01

# Explicitly enable this provider for the browser or plan-question command:
BIOGRAPH_PLANNER_PROVIDER=codex BIOGRAPH_CODEX_MODEL='<available-model>' \
  python3 app.py serve --port 8766 --no-browser
```

Each question starts an ephemeral, read-only CLI session in an empty temporary directory, with user configuration ignored, shell/apps/hooks/subagents/memories/remote plugins disabled, and web search disabled. Only the question, source entity catalogue, tool contract and JSON schema are supplied. A final plan is accepted only after one completed planning turn and an event stream containing no tool items. Unknown events, tool attempts, incomplete output and 90-second timeouts fail closed without a local query. Managed CLI requirements still apply. Private reasoning and raw CLI stderr are not saved.

Traces record `live_codex_cli`, the requested model (not a claimed independently verified served-model identity), CLI version, prompt/schema hashes, event type labels and returned token usage. `model_calls=1` means **one requested CLI planning turn**; CLI transport retries are not exposed, so HTTP-attempt counts and dollar cost remain unknown. The app makes no repair turn or provider fallback. Injected CLI tests remain `injected_test_model`.

Restart the app in that configured environment to enable **Plan a research question with one model agent**. `/api/planner` reports configuration readiness without disclosing keys; it does not verify model availability/account access. `/api/plan` saves the proposed plan, validation and local-tool trace plus any cited result. A configured provider may still reject a request or model name.

An explicit `--planner replay --replay recorded.json` mode supports offline transport tests/reproduction. Recorded keys bind the exact question/catalogue hash. Its report says `recorded_replay`, counts zero live model calls and is never presented as a live agent evaluation. Mock-model tests similarly say `injected_test_model`. With no configured model, `--planner live` records the model arm as not run while completing the deterministic comparison.

## Validation and next decision

The automated suite covers fixed source bytes/code, question groups, withheld reference data, bounded planning, malformed plans, exact IDs, source gaps, human-review gates, source/worksheet integrity, metrics and local HTTP transport. CLI tests additionally check the isolated prompt/environment, tool-event rejection, timeout behavior and absence of credentials/private reasoning in traces. Mock/replay responses verify behavior; they do not demonstrate real model planning quality.

After the pilot review and a configured live-model run, inspect paired answer quality, unsupported statements, lost relevant evidence and effort. Keep the planner only if it provides useful question interpretation without worsening the evidence contract. Freeze a separate held-out question set before tuning for a test result. The measured candidate population, experimental relationship labels, leakage audit and same-model baseline/enrichment prediction experiment remain separate pending work.

## Saved local pilot — October 15, 2026

The verified suite is `runs/evaluation_suite_verified_20261015/` and its first result is `runs/evaluation_pilot_verified_20261015/`. Open `http://127.0.0.1:8766/api/evaluation/evaluation_pilot_verified_20261015/` while the local server is running. The report provides individual TSV downloads; the existing run download route exports the full result ZIP.

The Pharos arm returned answers for 8/24 questions, had 8 scoped-source gaps and abstained on 8 unsupported scenarios. The enriched deterministic arm returned answers for 14/24, had two no-evidence outputs and abstained on the same eight unsupported scenarios. The reviewer pool contains 259 question/source rows covering 97 unique source units. These are **observed coverage counts**, not adjudicated correctness or independent experiments. The planner arm is `not_run` for all 24 cases because no model was configured. Scientific precision, review-pool recall and approved-plan agreement are null pending review.

### Live CLI follow-up — v0.6.1

The follow-up suite is `runs/evaluation_suite_codex_20261015/` (SHA-256 `5dd3fa7e282546b31854efa0efd94508bb433cb12d043bb9a8d1a76d638230cb`), with results in `runs/evaluation_live_codex_20261015/`. It preserves the initial pilot's exact question specifications and source file bytes while recording the new implementation. The earlier suite/result remains unchanged.

The requested model was `gpt-6-astra`, through existing CLI authentication, with `codex-cli 0.162.0-alpha.17.2`. All 24 single-turn plans validated and matched the **draft** reference plans: 14 answers, two no-evidence outputs and eight abstentions. No tool events were observed in the model sessions. The planner then invoked 16 bounded application queries. It returned the same source units and summary statements as the enriched deterministic workflow for every case. Deterministic outputs also match the preceding pilot. This supports question-to-scope interpretation on these development examples; **it establishes no scientific improvement over the graph or guided workflow**.

CLI-reported usage totals 334,589 input tokens and 1,993 output tokens, including CLI overhead; pricing and internal HTTP-attempt counts are unknown. Per-question CLI time was about 6–10 seconds. These overheads matter when deciding whether natural-language planning is worth using instead of guided controls. The initial connectivity probe and separate browser smoke test are outside the 24-case evaluation.

Open `http://127.0.0.1:8766/api/evaluation/evaluation_live_codex_20261015/` for the full result. The smaller packet is `runs/three_case_review_20261015/`, served at `http://127.0.0.1:8766/api/evaluation/three_case_review_20261015/`. It retains the original full result's IDs/hashes and contains 3 scope rows, 9 workflow-output rows and 20 question/source rows covering 10 unique CIViC items. Partial sheets can be scored against the full result. All judgment/reviewer/time fields remain blank. [AI-prepared source-check notes](PILOT_REVIEW.md) identify treatment-context and study-design issues for adjudication; they are not human scientific labels.

Validation: **181 tests passed**, plus a live browser check confirming monotherapy-only abstention and saved trace export. Next, adjudicate the three cases and decide which source qualifiers must be surfaced before collecting held-out questions or extending agent responsibilities.

The v0.6.2 [source-context display](STUDY_CONTEXT.md) subsequently surfaced per-record levels, study titles, original descriptions and treatment-list limits. Its separate saved-plan replay preserved all 72 observations' statuses, evidence units, claim text and graph/review bases. This replay used no new model calls and supplies no human scientific judgments. The original live result and worksheet packet remain historical and unchanged.
