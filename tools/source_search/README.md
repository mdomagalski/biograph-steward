# Bounded biomedical support search

This optional research track adds free **question → PubMed candidate papers**
retrieval. It compares the same Nemotron 8B controller with and without a short,
attributed evidence-search procedure, plus a deterministic native full-question
query. It does not evaluate biological truth, modify Pharos, or claim that every
returned paper has been read. Existing exact-PMID XML fetching/parsing is reused
from `biograph_steward/literature.py`; only search is new.

## Pinned components

- [BioMCP v0.9.3](https://github.com/genomoncology/biomcp/releases/tag/v0.9.3),
  commit `5641de7d7b79b53872f8599dbb4dba22e611dcaf`, MIT. The official Mac arm64
  archive is checked against SHA256
  `e637062c18c6692f3ec49c5847e69b29f6feee7f7909345970bd504d72174994`.
- Original authors' [BioASQ11 release](https://zenodo.org/records/7655130),
  CC-BY-2.5. `training11b.json` is 37,639,648 bytes, publisher MD5
  `fc1fe03831b69157c82a746337c00712`. Its README declares 4,719 questions.
  No third-party 5,399-question mirror is used.
- [Scientific Agent Skills v2.72.0](https://github.com/K-Dense-AI/scientific-agent-skills/tree/526ebce143bc326f44471554e33d66a19c840360),
  selected MIT ontology-resolution, critical-thinking and claim/evidence
  procedures. Exact source paths/bytes are pinned in `policy.py`; this is a
  reviewed adaptation, not installation of the complete skill library.
- Existing NVIDIA `Llama-3.1-Nemotron-Nano-8B-v1`, model/tokenizer revision
  `54641c1611fcff44fa4865626462445e0a153fc7`, vLLM0.8.5 V0 and its existing
  schema backend. No model, serving environment or app dependency is replaced.

Run from a repository checkout. Reference preparation and the post-seal
reference-document assessment need the optional
`ijson==3.4.0.post0` streaming parser, isolated under the ignored task directory;
the controller and native tool wrapper use the standard library and existing
application transport/parser. The core app does not import this package.

## Boundaries before running cases

`prepare.qualify` downloads/hash-checks the official Mac binary, then runs only
version/help. Qualify source behavior first with the excluded manual query
**Pharos TCRD**. A native short-keyword suggestion otherwise contacts EBI OLS4
even with `--source pubmed`; the documented `--disable-sources ols4` suppresses
that auxiliary route. The qualified invocation is explicit PubMed, no source
fallback, no provider API keys and no inherited endpoint/proxy overrides.
Native JSON, stderr, completeness, source plan and query echoes remain captured.
The PubMed echo is not represented as a separately observed encoded ESearch URL.

The original source JSON stays private/ignored. `ijson` may internally decode
all JSON events, but only `id`, `body` and `type` are retained or exposed to
selection, model code and logs. References, snippets and answers are not
model inputs. Twelve factoid and twelve list IDs are chosen in fixed SHA order
after the declared publisher/documentation/manual-topic exclusions. Opened
public examples cannot become fresh cases by renaming a run.

Prepare and review the immutable protocol before any selected-question search
or generation. The preparation CLI lists all explicit source/runtime/manual
qualification pins:

```sh
python -m tools.source_search.prepare qualify --output NEW_BINARY_DIRECTORY
python -m tools.source_search.prepare prepare --help
python -m unittest tools.source_search.test_source_search -v
```

The saved run is `runs/source_search_skill_20261114/`. Raw sources, executable,
licenses, qualification receipts and later model traces remain ignored and
must be supplied separately for exact replay; no download is triggered by app
startup or by importing this package.

## Matched execution after review

```sh
python -m tools.source_search.agent --frozen FROZEN_QUESTIONS \
  --protocol-sha256 PROTOCOL_FILE_SHA256 --mode all \
  --cache NEW_SHARED_CACHE --output NEW_BLOCKED_EXECUTION \
  --endpoint http://127.0.0.1:8011/v1/chat/completions
```

Each agent gets at most two searches, one exact abstract get and four generation
calls, each capped at1,200 output tokens. The final ranked list has at most ten
unique PMIDs from its returned candidates. Only the requested exact returned
PMID can be opened; no PMC/full-text follow-up occurs. Search candidates are a
handoff, not citations claimed to have been read or entailed.

Execution is question-blocked, with12 unskilled-first and12 skill-first cases in
fixed metadata-hash order. All arms share immutable captures keyed by query,
binary and helper pins. The direct control uses one full-question query with
whitespace normalization only and native provider cleanup/ranking. Its lower
cost is reported, not called an equal-call control.

The model receives compact source projections; complete native bodies remain
in cache. Any title/abstract truncation is explicit. Before generation, the
installed CPU `/tokenize` API counts the **exact** Nano system/user message
transform. Input plus1,200 reserved output tokens must fit the conservative
8,192-token cap. Unavailable tokenization or overflow produces an explicit
no-inference case, not a repair or silent content drop. Tokenization requests,
generation calls, native process executions, exact-fetch invocations and cache
hits are distinct. Exact upstream HTTP counts are unreported because native
search can perform multiple exchanges/retries; process count is not substituted.

## Installed-runtime qualification

The first operational attempt is preserved under the ignored run directory.
Its native query-length schema bounds caused the installed Outlines tokenizer
index construction to exceed a bounded 45-second CPU probe. The matching
schema without only the query string bounds completed normally, including
`maxItems: 0`; that empty-array constraint was not the demonstrated cause.
The official [vLLM 0.8.5 fallback implementation](https://github.com/vllm-project/vllm/blob/v0.8.5/vllm/model_executor/guided_decoding/__init__.py)
and [version-specific feature check](https://github.com/vllm-project/vllm/blob/v0.8.5/vllm/model_executor/guided_decoding/utils.py)
explain why these requests use Outlines. This is a measured integration workload
on the pinned runtime, not a claim that every backend or newer release fails.

Current generation guidance omits only query `minLength`/`maxLength`. The full
controller still rejects blank or over-2,000-character queries, wrong shapes,
unknown/duplicate IDs and over-budget actions before any source call. All native
array limits and ID enums remain. Each request records separate native-guidance
and complete acceptance-schema hashes. Malformed provider values become retained
invalid outcomes, without semantic retry or repair. Historical source captures
allow replay of older frozen protocols after the maintained adapter changes.

The original reviewed operational version is `frozen_v3`: the same 24 question bytes,
policies and logical budgets as the earlier preserved attempts. Its source pins
are verified before and after execution. No reference-paper values were used to
choose this runtime correction.

The separately frozen `frozen_v4` follow-up enables one standard recovery
mechanism. An exact literal duplicate of an already executed search is still
blocked before any tool/cache invocation, but its typed error becomes an
`isError: true`, `executed: false` observation. The next ordinary decision uses
the existing four-call budget. No source counters advance, no query advice is
added, and the fourth call remains finish-only. Other invalid IDs, shapes,
case changes, source-budget violations and runtime/model failures stay terminal.
This adapts the selective error-observation pattern described by the
[MCP tools specification](https://modelcontextprotocol.io/specification/2026-07-28/server/tools#error-handling),
[version-pinned LangGraph ToolNode](https://github.com/langchain-ai/langgraph/blob/5eb60aef6f3837a1fb632a8abc6cf8e8da81785b/libs/prebuilt/langgraph/prebuilt/tool_node.py)
and [author ReAct environment](https://github.com/ysymyth/ReAct/blob/6bdb3a1fd38b8188fc7ba4102969fe483df8fdc9/wikienv.py).
Those sources do not mandate this exact duplicate rule or establish a benefit
for this model. No framework dependency is installed.

`BASE_POLICY` and `SKILL` remain unchanged. There is no additional prompt key or
recovery instruction before an error; actual shared request-prefix and parsed
output agreement is recorded rather than assumed. Executed source actions and
rejected controller observations are stored separately and independently
replayed by the sealer. Transport retries and hidden calls remain zero;
explicit feedback-consuming decisions are counted normally. The original
fail-fast result is retained, not relabeled as the follow-up.

The pre-reference operational rule requires more valid final completions than
the original 10/48, with all guards and budgets intact. Reference retrieval
benefit additionally needs the matched final-list Recall@10 intervals; merely
passing a schema is not scientific or retrieval accuracy. The additional
follow-up has the same per-case limits and at most 192 generation requests.
Inherited `operational_revision` function hashes describe the earlier runtime
correction. The follow-up's current `files` pins and `recovery_followup` fields
are authoritative for its selective-feedback implementation.

Exact pre-repair research source is also retained on local archive refs
`codex/archive-source-search-stop-v3-20261114`
(`dac3285cae18df49754fa64680d2f5bcc6273673`) and
`codex/archive-source-search-feedback-v4-20261114`
(`f9c709277f2a551fa01c968f7db2608d43f39504`). These are source-only local
archives, not a claim that a branch or raw run data has been published. The
maintained code contains one current implementation; captured bytes retain
the original gates for historical replay.

## Evaluation scope

Reference papers remain unavailable until every fixed arm output is complete,
sealed and reviewed. The fixed endpoint is paired mean question-level reference
PMID Recall@10, skill minus unskilled, with descriptive2,000-draw question
bootstrap intervals and all direct-control outcomes retained. Identifier shape,
opened-abstract identity, unavailable sources and costs are separate readouts.

BioASQ is a human-authored positive document reference, with incomplete relevant
paper coverage. A nonmatching paper is not thereby biologically false or
irrelevant. This small public historical comparison is not model-unseen, an
official competition submission, independent-study replication, or a measure of
whole-graph biological accuracy. The selected skills themselves do not supply
gold labels or establish factual accuracy.
Excluding known viewed publisher examples also does not establish that the
remaining questions were unseen during native-tool development or tuning;
complete model/tool-development membership is not independently audited.

## Inspect papers for your own question

The supplied-question utility does not load BioASQ or require `ijson`. Start
with native mode: it uses the free qualified PubMed search, no language model
and no Brev instance. The example uses the locally qualified Mac arm64 release
receipt and its **file** hash; qualify your own receipt when reproducing on
another machine. Choose a new output directory each time.

```sh
python -m tools.source_search.query \
  --question 'YOUR PUBLIC RESEARCH QUESTION' \
  --qualification runs/source_search_skill_20261114/binary_v1/qualification.json \
  --qualification-sha256 69a3ca4ca57feb7b9d403df3b2caa5c91d7abdcfc6922862eb75d3db2936c68c \
  --mode native --cache runs/source_search_operator_cache \
  --output runs/source_search_operator_example
```

That example uses this checkout's recorded local qualification. For a fresh
Apple Silicon Mac, follow the [operator setup guide](../../docs/SOURCE_PAPER_INSPECTION.md)
to qualify the binary locally and calculate that new receipt's file hash.
The ignored receipt above is not distributed with a clone, and its absolute
executable path must not be reused on another machine.

Open `runs/source_search_operator_example/report.html`. It distinguishes native
search candidates, any valid final model selection and exact abstract
inspections; source flags and missing metadata remain explicit. Saved source
records, a sealed operator receipt and actual model/tool/cache counts are
linked. A failed or empty agent selection does not hide papers already captured
or establish that evidence is absent.

Optional agent mode uses the existing qualified Nano service and loopback port
forward. Start that service yourself, then use the same command with
`--mode agent --procedure base --endpoint http://127.0.0.1:8011/v1/chat/completions`
and a new output directory. It can use two searches, one exact abstract get and
four model calls, with selective duplicate feedback inside that budget. The CLI
does not start paid compute, replace a model or request an external paid API.
Native/base defaults are deliberate; `--procedure reviewed` is an explicit
alternative and is not assumed superior.

This is an inspectable paper handoff, not a biological answer. PMID membership
or an abstract read does not establish a scientific claim. Pharos/evidence reuse
is **unassessed** unless a separate workspace audit is supplied: a discovered
paper is candidate source context, not a new independent graph assertion.
No graph ingestion, acceptance or pruning occurs.

## Reference assessment commands

The evaluator is separate from the producer. Freeze its policy before the run,
then seal the complete blocked execution and all native source captures:

```sh
python -m tools.source_search.evaluate freeze-policy --help
python -m tools.source_search.evaluate seal-predictions --help
python -m unittest tools.source_search.test_source_search tools.source_search.test_evaluate -v
```

`release-score` interprets selected document URLs only after an explicit durable
release event and complete pinned forecasts; obtain the required review first.
It never uses answer text or snippets as labels. The aggregate report retains
all three arms, costs, failures, early finishes, source-tool order and abstract
inspection counts. `python -m tools.source_search.report --help` renders that
sealed aggregate without including questions, expected PMIDs or source text.

A separately sealed error-localization addendum compares each agent's **first
attempted search** with its final handoff. Failed, empty or partial first
searches are never replaced by later ones; native order is retained through ten
candidates, and a case with no executed search stays empty. It adds no retrieval or generation.
This diagnostic was motivated by observed dialogue failures before reference
release and does not replace the original primary comparison. Ma et al.'s
[Rewrite–Retrieve–Read paper](https://aclanthology.org/2023.emnlp-main.322/) and
[official artifacts](https://github.com/xbmxb/RAG-query-rewriting) motivate
separating query discovery from later processing. We copy none of that
repository's prompts/code and do not reproduce its trained or RL method.

## Attribution

Cite Krithara et al., [BioASQ-QA](https://doi.org/10.1038/s41597-023-02068-4),
the original BioASQ deposit, [BioMCP](https://github.com/genomoncology/biomcp), and
Kassis et al., [Scientific Agent Skills](https://arxiv.org/abs/2609.00065).
Upstream MIT notices and dataset terms are preserved beside the staged source
files. PubMed abstract and article-specific rights are not replaced by a tool's
software license. The K-Dense paper reports no task-level scientific evaluation;
our paired comparison therefore measures the proposed adaptation rather than
assuming a published skill-accuracy gain.
