# Construction planning: failure diagnosis and reuse decision

Review date: 2026-10-26. The initial source/code investigation needed no model
calls, retrieval or paid compute. The subsequent two-request format observation
and completed twelve-request comparison are recorded below. Preserve the failed
and mixed runs and keep the optional planner experimental.

## What the failures establish

The [recorded comparison](../evaluations/CONSTRUCTION_PLANNER_20261026.md) failed
four **planning requests before graph construction**. Three supported requests
were declined. The fourth requested interactions and pathways but proposed only
interactions. Exact UniProt identities were already supplied; these cases do not
demonstrate an entity-resolution failure or a Pharos retrieval failure.

The schema/runtime correction reduced invalid proposals from seven to one but
left supported-task agreement at 0/4. It fixed contradictory output combinations
and a verified decoder compatibility problem, not semantic task selection.
Generic reasons such as “Abstain” do not reveal why the model declined. Model
size, prompt length, branch ordering and refusal wording remain hypotheses.

The application validates permitted capabilities and identity bounds, but
`validate_construction_plan` does not certify agreement with arbitrary natural
language. A valid plan can omit a requested relation. The preview and explicit
user build action remain necessary; a successful schema check is not task success.

## Existing solutions checked

**Exact model reference.** The [pinned NVIDIA model card](https://huggingface.co/nvidia/Llama-3.1-Nemotron-Nano-8B-v1/blob/54641c1611fcff44fa4865626462445e0a153fc7/README.md)
documents tool-calling training and a BFCL v2 Live evaluation. It provides a
user-message tool wrapper, `<AVAILABLE_TOOLS>{functions}</AVAILABLE_TOOLS>`,
followed by the user request. Our current custom policy/schema interface differs.
The deployed reasoning-off system switch and greedy decoding match the card.
The published score does not predict success on our four cases. Reproducing the
documented interface is a concrete missing baseline; the result does not yet
establish that this model lacks the capability.

The [BFCL Nemotron handler](https://github.com/ShishirPatil/gorilla/blob/main/berkeley-function-call-leaderboard/bfcl_eval/model_handler/api_inference/nemotron.py)
exists, but the inspected registration is for Ultra 253B,
not this Nano 8B revision. Its prompt placement and output parser cannot be
assumed compatible. The Nano model files provide no verified corresponding
parser or scoring harness. Exact output parsing and evaluation configuration
remain a prerequisite to claiming a faithful reproduction. Do not install a
current general harness into the pinned app environment merely because it has
a similarly named handler. NVIDIA's [NeMo-Skills tool-calling documentation](https://nvidia-nemo.github.io/Skills/evaluation/tool-calling/)
also separates tool presentation, parsing and execution; its illustrated parser
is for Super 49B v1.5. BFCL's [package manifest](https://github.com/ShishirPatil/gorilla/blob/main/berkeley-function-call-leaderboard/pyproject.toml)
declares Apache-2.0, Python 3.10 or later and substantial dependencies. Reuse
appropriate components in an isolated diagnostic rather than changing production
dependencies. The Nano weights retain their separate NVIDIA/Llama license terms.

**Failure categories.** [BFCL's author methodology](https://gorilla.cs.berkeley.edu/blogs/8_berkeley_function_calling_leaderboard.html)
separately checks selected functions, arguments and function relevance.
[When2Call (NAACL 2025)](https://aclanthology.org/2025.naacl-long.174/) explicitly
studies the choice between calling a tool, answering directly, requesting missing
information and declining. These support separating over-abstention from wrong
arguments and malformed output, rather than reporting one combined validity rate.
Neither paper diagnoses the cause of our specific declines.

The [When2Call code](https://github.com/NVIDIA/When2Call) is Apache-2.0; its
[dataset card](https://huggingface.co/datasets/nvidia/When2Call/blob/main/README.md)
specifies CC-BY-4.0, synthetic generation and automated labels. Its records trace
to BFCL, and the LLM-judge set is a subset of the multiple-choice set. They are
not independent references. Dataset creation overlaps the model's documented
training period; absence of training exposure is not established. Use it as a
tool-decision diagnostic, not an unseen biological gold set. Only documentation
and examples were inspected here; no test-set run or fine-tuning was performed.

**Existing local safeguards.** The saved-graph query planner already binds target
scope and checks requested relations separately from schema validity. Reuse that
pattern when preserving explicit construction choices. Its lexical scope checker
assumes one protein anchor, so it is not a drop-in validator for multi-protein
cohorts. Prefer structured user choices for exact cohort, focus and relations;
derive the retrieval profile from the selected relations. Do not create a broad
natural-language parser from four observed failures.

## Bounded next increment

1. Check the Nano reference output format/parser. If an exact released harness
   cannot be verified, present one permitted real function using the published
   Nano wrapper, retain the raw response and perform a dry parse without
   execution. Label this an **author-pattern adaptation**, not a reproduced BFCL
   result. Freeze its comparison against v3, including parser behavior, before
   assessing task success; never assume Ultra's output tags are Nano's contract.
2. Reuse the existing constructor and scope checks. Keep approved cohort, focus
   and relation choices bound to execution. Detect dropped requirements without
   silently repairing the model output or scoring a declined request as success.
3. Report decision, tool, arguments, complete requested scope and final task
   success separately. Preserve the 12 consumed cases as development regression
   checks; freeze fresh wording before any later generalization assessment.
4. Run only planning first. If the supported requests pass, perform the already
   specified real-cohort construction and compare its output with the same-input
   deterministic graph. This tests workflow equivalence, not biological accuracy.

Do not add biomedical sources, a new multi-agent framework or a prompt/model
sweep to address this particular failure. Announce the bounded inference run
before asking for Brev; the source investigation and walkthrough need no GPU.

## Assisted evidence walkthrough

The assistant can inspect identifiers, source fidelity, missing qualifiers,
duplicated provenance and export consistency. It can guide a person to those
records, but cannot supply independent human usability observations or establish
scientific truth by acting as another model judge. Use the existing
[walkthrough worksheet](../USER_WALKTHROUGH_20261026.md), with assisted results
recorded separately from unaided attempts.

The saved CCNO/CDKN1A example was checked against its source files: E001 is a
STRINGDB annotation through Pharos with no explicit paper reference supplied;
two reciprocal rows form one annotation. A separate Y2H-v1 detected observation
retains constructs and source locators, with assay host unspecified. It must not
be promoted to a general physical-binding or clinical claim, nor called an
independent confirmation without an overlap audit. The existing
[IMEx/assay literature review](ASSAY_EVIDENCE_REUSE_20261025.md) records why those
qualifications matter. A precomputed candidate answer now supports an immediate
walkthrough; it is not an agent success result.

## Subsequent two-request format observation

After this source review, the isolated research script
`scripts/probe_nemotron_tool_interface.py` froze the published Nano wrapper,
one description of the existing constructor, two consumed development requests,
wire payloads, implementation and model configuration. It deliberately bypasses
JSON generation constraints while reusing the existing endpoint/configuration
checks. There is no production planner change or tool executor in this probe.
Eleven focused tests passed before inference; a separate read-only runtime check
matched the pinned model revision, image, vLLM 0.8.5 and XGrammar 0.1.18.

The two calls returned:

- `ppi_full`: textual `<TOOLCALL>` tags containing a JSON array with one
  `construct_cohort` call. Every argument matched the frozen expected request;
  the existing deterministic constructor's validation passed in a separate
  inspection, without execution.
- `clinical`: a text response declining treatment selection and describing its
  limited retrieval capability. No call was returned.

Neither response used the API's native `tool_calls` field. The response format
is now observed for this exact setting; a general parser is not yet established.
The published prompt wrapper, function presentation and absence of guided JSON
all differ from v3, so this is not a causal test of any single change. The full
12-case comparison was still required at that point; its later result is below.
The earlier 0/4 result remains preserved. No graph, source retrieval or biological
benefit was tested.

Raw final responses, frozen requests and runtime metadata are preserved under
`runs/nemotron_tool_format_probe_20261026/`; the
[tracked observation summary](../evaluations/nemotron_tool_format_probe_20261026_summary.json)
binds them by hash. Usage was 738 input and 109 output tokens, with 3.303 seconds
of summed request latency, excluding startup and idle time. The next increment
was a bounded adapter for the observed representation using existing JSON and
construction validators. That local preparation is now complete, with the
[full comparison completed](../evaluations/CONSTRUCTION_PLANNER_20261026.md).
The adapter is experimental and the application default remains unchanged.
Ordinary no-call text is reported separately from semantic abstention; this
preserves the separation of presentation, parsing and execution described by
the upstream evaluation tools.

## Full comparison diagnosis and existing remedies

The fixed run matched **1/4 supported requests**, versus 0/4 for v3, but admitted
one unsupported assay-filter request as an unfiltered plan. All six attempted
calls had the observed tagged JSON representation. Two used illegal `profile`
values; one retained an unwanted authorized protein; one added an unauthorized
protein and was blocked. Six responses contained no call. Post-hoc reading found
four clear refusals, one appropriate clarification, and one clarification that
did not acknowledge the unsupported external source. None of this is a biological
evaluation, and the no-call inspection is not an independent human score.

Three different issues are now documented:

1. **Generation constraints were absent.** The experimental payload sends the
   function schema as text, without `guided_json`, structured `response_format`
   or API-native tools. Illegal enum values therefore do not show that the
   runtime ignored an enforced constraint. The existing argument validator
   rejected them correctly. This is separate from tagged-output parsing.
2. **The tool contract lost exclusions.** The shorter `function_definition` in
   the probe omits the old policy's explicit assay/organism/disease-filter,
   arbitrary-source/URL and do-not-substitute restrictions. The omission is
   verified and consistent with the assay/source failures; its causal effect
   has not been isolated from the other interface changes.
3. **Permitted scope differs from intended scope.** The validator enforces an
   authorized cohort boundary, not whether the user explicitly requested fewer
   proteins. The subset failure passes those bounds while misunderstanding the
   question. No JSON grammar can establish arbitrary natural-language intent.

The installed version already has a possible syntax mechanism to investigate:
vLLM 0.8.5's [Apache-2.0 structural-tag example](https://docs.vllm.ai/en/v0.8.5/getting_started/examples/openai_chat_completion_structured_outputs_structural_tag.html)
shows constraints on JSON within selected tags while permitting other response
text. It may fit the observed Nano representation. Compatibility with this exact
array schema, model and XGrammar 0.1.18 serving path remains unverified; first
check the actual vLLM preflight and grammar behavior without inference. Do not
repeat the earlier mistake of checking the grammar library alone.

The [same-version tool-calling documentation](https://docs.vllm.ai/en/v0.8.5/features/tool_calling.html)
distinguishes parsability from output quality and explains named/required calls.
Forcing a call on every input would violate the eight withholding cases.
Structured decoding cannot repair a silently omitted assay requirement or an
unwanted but authorized cohort member.

Before another live comparison, restore a complete capability contract and
reuse explicit user-selected cohort/focus/relation constraints at the application
boundary. The existing `planning_scope` checks and guided selections provide
reusable patterns; its single-target resolver is not a drop-in cohort parser.
Do not build a general language recognizer by tuning to these twelve exposed
questions. Keep the deterministic workflow available and test any revised
interface under a separate freeze.

Deriving `profile` from relations requires an explicit design decision. The
planner policy suggests a mapping, but the current constructor permits
`context + interactions`, and context also retrieves GO, drug and publication
data. Silently changing profiles could change retrieval scope and budgets.
It is not a harmless output repair and cannot retrospectively turn this run
into three successes. No additional variant, inference or production integration
was performed during this diagnosis. Brev is no longer needed for local review.

## Pinned engine compatibility gate

Follow-up review: 2026-10-26.

The version-specific source review resolves an important prerequisite left open
above: **the documented structural-tag response format is not implemented by
our current vLLM V0 XGrammar path.** The API
[protocol](https://github.com/vllm-project/vllm/blob/v0.8.5/vllm/entrypoints/openai/protocol.py#L467-L488)
accepts that format and carries it into sampling parameters, but the V0
[grammar configuration](https://github.com/vllm-project/vllm/blob/v0.8.5/vllm/model_executor/guided_decoding/xgrammar_decoding.py#L143-L246)
has no structural-tag branch and reaches its unsupported-mode error. The V1
[backend](https://github.com/vllm-project/vllm/blob/v0.8.5/vllm/v1/structured_output/backend_xgrammar.py#L91-L119)
does compile structural tags, with a separate
[validation path](https://github.com/vllm-project/vllm/blob/v0.8.5/vllm/v1/structured_output/backend_xgrammar.py#L263-L275).
An API request model accepting a field is therefore insufficient evidence that
the selected engine can enforce it. This is a source-level finding; no live
request was made to reproduce the error.

`compose.brev-local-model.yaml` explicitly sets `VLLM_USE_V1: "0"`. Git history
places that choice in initial deployment commit `f991e2e`; the accompanying
deployment notes record working inference but no rationale for V0 and no V1
failure. The configured dtype is **bfloat16**, not float16. Do not describe V0 as
a proven requirement of Nano or our GPU. No deployment settings were changed
during this follow-up.

The small [configuration at the pinned Nano revision](https://huggingface.co/nvidia/Llama-3.1-Nemotron-Nano-8B-v1/blob/54641c1611fcff44fa4865626462445e0a153fc7/config.json)
was retrieved separately from the weights and identifies `LlamaForCausalLM`,
`model_type: llama`, and `torch_dtype: bfloat16`. vLLM 0.8.5
[registers that architecture](https://github.com/vllm-project/vllm/blob/v0.8.5/vllm/model_executor/models/registry.py#L74)
and its [implementation](https://github.com/vllm-project/vllm/blob/v0.8.5/vllm/model_executor/models/llama.py#L420)
does not declare the V0-only marker. The
[registry compatibility check](https://github.com/vllm-project/vllm/blob/v0.8.5/vllm/model_executor/models/registry.py#L517-L522)
uses that marker. This supports an isolated V1 compatibility check; it is not
evidence that this exact model revision has already passed one here.

The V1 [eligibility checks](https://github.com/vllm-project/vllm/blob/v0.8.5/vllm/engine/arg_utils.py#L1260-L1315)
allow BF16 and FP16 and require CUDA compute capability at least 8.0. NVIDIA lists
the [L40S as 8.9](https://developer.nvidia.com/cuda/gpus). The current ordinary
generation configuration does not use the incompatible features identified in
those checks. Forcing `VLLM_USE_V1=1` makes unsupported configuration fail rather
than silently reverting to V0. Actual package compatibility, memory use, startup
and inference remain untested. Retain the existing driver/image/revision and
check these conditions before considering any upgrade.

V1 also changes defaults: its
[argument initialization](https://github.com/vllm-project/vllm/blob/v0.8.5/vllm/engine/arg_utils.py#L1457-L1469)
enables chunked prefill and defaults prefix caching on. The
[V1 guide](https://docs.vllm.ai/en/v0.8.5/getting_started/v1_user_guide.html)
documents request-level structured-output backend limitations. A future freeze
must name the engine and effective caching/prefill settings; copying V0's
request-level `xgrammar:no-fallback` option is not an established V1 recipe.
The V1 XGrammar backend accepts only its documented backend options, not that
V0 no-fallback control.

**Schema boundary, still to verify.** XGrammar 0.1.18's
[structural-tag API](https://github.com/mlc-ai/xgrammar/blob/v0.1.18/python/xgrammar/grammar.py#L188-L245)
permits ordinary text until a trigger, constrains a matching tag body, then
permits ordinary text and later tags again. It does not enforce our
exactly-one-call/no-surrounding-prose rule by itself. The strict adapter must
remain authoritative for that envelope, allowed identities and final argument
checks. Its [author tests](https://github.com/mlc-ai/xgrammar/blob/v0.1.18/tests/python/test_grammar_matcher_structural_tag.py)
are the appropriate starting point for CPU acceptance controls.

Do not copy the prompt's array `minItems`, `maxItems` or `uniqueItems` into a
decoder schema and assume they work. The pinned V1
[feature detector](https://github.com/vllm-project/vllm/blob/v0.8.5/vllm/v1/structured_output/backend_xgrammar.py#L173-L209)
rejects those keywords on its ordinary JSON path; structural-tag validation
instead calls XGrammar directly. The absence of that detector on the latter
path is not proof that every nested constraint is enforced. A conservative
candidate can use required properties, closed objects, enum/constant values
and complete compatible branches already checked in the earlier grammar work,
while retaining application cardinality/uniqueness checks. The new tagged array
combination still requires positive and negative tests, including empty and
multiple calls, wrong profiles, unknown IDs, duplicate IDs and surrounding text.
No exact tagged-array schema has been compiled or measured locally in this
follow-up; vLLM, XGrammar and PyTorch are not installed in this Mac interpreter.

V0 supports an EBNF `guided_grammar` route, but no exact author-provided Nano
adapter for tagged tool calls plus free no-call text was verified for it.
Building a replacement grammar would introduce another custom protocol; it is
not the recommended next step. Prefer a bounded isolated V1 preflight using the
existing pinned container: first protocol conversion and CPU grammar controls,
then cached model configuration/architecture checks. Only after those pass,
announce a separately frozen model startup and at most two planning/format
requests on Brev, each capped at 1,600 output tokens and 120 seconds (3,200
output tokens total), without tool execution or graph access. Do not change the
working V0 deployment or rerun the twelve planning cases merely to discover a
serving incompatibility.
This follow-up changed documentation only and did not use Brev, load weights,
install packages, run inference or establish improved planning accuracy.

Subsequent local preparation is saved separately in
`runs/construction_structural_tag_preflight_20261026/`. It freezes a CPU-only
protocol/grammar harness, synthetic fixtures and local strict-parser observations.
Input hash verification and local parser checks passed; the vLLM/XGrammar runtime
checks have **not** run. The harness uses real installed protocol and validation
helpers, with a synthetic tokenizer only for the V0 rejection control. It neither
starts an engine nor establishes compatibility with Nano's actual tokenizer.
Brev reports the instance stopped, so the installed-runtime check awaits startup;
the model server is not needed for that first check. No production code, deployed
settings or previous comparison results were changed.

Before copying or running that preparation, verify its `manifest.json` against
the externally recorded SHA-256
`272673e5bf12999489f72118177d4b67c84f2403a59e0b765f31e92d872d0845`.
Independent review confirmed the eleven listed files and 23 synthetic fixtures,
but the harness trusts the manifest's inventory; its `--verify-only` result alone
would not detect an inventory removed from the manifest. This external digest
is therefore part of the execution prerequisite, not a runtime-success claim.

## Installed CPU compatibility result

The subsequent Brev check passed unchanged in the cached pinned image:
**seven helper controls and all 23 synthetic grammar controls**. The
[tracked receipt summary](../evaluations/structural_tag_cpu_20261026_summary.json)
binds the original preparation, result, launcher and runtime observation. The
outer launcher checked the externally pinned manifest before extraction and
recorded the image identity, `runc`, no device requests, no networking and a
read-only input mount. The disposable check container exited successfully and
was removed. The existing V0 service auto-started with the VM and was left
unchanged; the helper check itself loaded no model weights or Nano tokenizer.

The installed API conversion preserved the structural-tag request, V1's actual
validator accepted it, and grammar acceptance matched every declared positive
and negative control. V0 reproduced its expected unsupported-mode error using
the explicitly synthetic tokenizer. Seven invalid examples still passed the
grammar and require the existing application checks, including duplicate/empty
cohorts, focus membership and the one-call envelope. Plain text remains allowed
without proving that a refusal or clarification is semantically correct.

That result closed the CPU protocol/grammar prerequisite; actual V1 startup,
Nano tokenization, inference and task interpretation were still unresolved at
that stage. The next bounded diagnostic used the same model, revision and two
earlier probe requests, adding the verified response format in a separately
recorded V1 engine. Its purpose was serving/format compatibility, not improvement
on the twelve development cases; the result follows below.

## Isolated V1 live compatibility result

The subsequent [frozen two-request diagnostic](../evaluations/nemotron_v1_structural_probe_20261026_summary.json)
completed successfully using the same pinned vLLM 0.8.5 image, XGrammar 0.1.18,
Nano model/tokenizer revision and BF16 cached weights. Actual V1 startup,
health/model identity and the effective runtime were recorded before inference.
V1 chunked prefill used a 2,048-token batch limit; prefix caching was explicitly
disabled. These runtime differences from the V0 reference remain part of the
comparison record.

The two original development requests were unchanged except for adding the
exact CPU-verified structural `response_format`. The PPI request returned one
tagged call with the exact original cohort, focus, profile and relation arguments.
The clinical request returned text declining treatment selection and no call.
Both responses identified the pinned Nano model and finished normally; the
existing parser returned `validated` and `no_call_text`, respectively. No
retrieval, construction, repair or retry occurred. The temporary V1 service was
removed and the original V0 service restored healthy.

Both returned final texts are byte-for-byte identical to the earlier
unconstrained two-request probe. The tracked summary binds those prior result
files by hash. Thus no answer improvement was observed on these two examples.

This establishes the tested serving/format compatibility, including the ability
to produce no-call text without forcing a tool invocation. It is not a fresh
semantic benchmark: both cases were already consumed in development, the tool
description remained unchanged, and no independent semantic refusal assessment
was performed. The earlier **1/4 supported-request** result and unsupported
assay-filter failure remain unchanged. No biological gain is established.

The next work is therefore the previously identified contract and intent gap:
restore omitted capability exclusions, preserve explicit caller selections when
provided, and reject selection mismatches rather than rewriting them. Structured
decoding does not establish whether a permitted plan silently discards an assay
condition or unwanted authorized protein. Keep the production default and
historical traces unchanged; any revised interface and user-assisted selection
task require separate inputs, policy and evaluation interpretation.

## Tool V2 implementation and frozen comparison

The separate `nemotron_tool_v2` interface now implements the bounded next step
in [`nemotron_construction_v2.py`](../../biograph_steward/nemotron_construction_v2.py).
It restores the v3 capability exclusions in the tool description: ambiguous or
unknown identities; clinical, therapy or variant interpretation; causality and
prediction; organism, disease, assay and physical-binding-only filters; evidence
truth, calibrated confidence, acceptance and pruning; arbitrary sources, URLs,
code execution and external publication. Unsupported requirements must not be
silently replaced by a supported retrieval request.

This reuses the pinned Nano prompt-wrapper pattern and the same structural
response format verified by the CPU and isolated V1 diagnostics. The strict
existing parser and constructor remain authoritative for the call envelope,
cardinality, uniqueness, identity authorization and focus membership. This is
consistent with the [vLLM 0.8.5 documentation](https://docs.vllm.ai/en/v0.8.5/features/tool_calling.html),
which separates the caller's tool/context responsibilities from schema-valid
generation, and with [XGrammar 0.1.18's structural-tag behavior](https://github.com/mlc-ai/xgrammar/blob/v0.1.18/python/xgrammar/grammar.py#L188-L245),
which permits text outside constrained tags. Neither source establishes that a
longer description will improve this model's decisions; that remains to be
measured.

The experimental Python scope may include a caller-supplied `exact_selection`
containing the complete cohort, focus, profile and relations. Existing constructor
validation checks that selection before inference; a returned call must match
it after canonical ordering or be rejected without repair. `context + interactions`
remains permitted and distinct from `ppi`. This field is not part of the current
UI or production API, and V2 traces cannot execute through the v3 publication
path. See the [callable contract and commands](../CONSTRUCTION_AGENT.md#v1-serving-compatibility-and-experimental-tool-v2).

The frozen comparison at `runs/construction_planner_tool_v2_20261026` preserves
the original twelve development scopes and expected requests. None has an
explicit selection, and expected labels are never converted into model input.
The runner's `--interface nemotron_tool_v2` preparation freezes the new policy,
wire requests and implementation. Its `--runtime-observation` execution requires
a current, separately verified V1 runtime receipt with hashed evidence, recorded
after preparation. The old two-request receipt is historical evidence, not a
substitute for this check. Receipt checking binds the recorded configuration; it
does not independently attest live engine state.

Local checks and independent review passed; the [preparation record](../evaluations/construction_planner_tool_v2_20261026_preparation.json)
binds the frozen requests and unchanged case files. The historical
**1/4 supported-request** result and unsupported assay-filter admission form the
baseline for the subsequent live comparison below. Restoring a
contract does not prove its semantic enforcement: a call can agree with an
explicit selection while ignoring an unsupported free-text assay condition.
Selection-assisted behavior needs separately declared inputs and interpretation.
Continue to report no-call text, rejected outputs, unsupported proposals and
supported exact matches separately; none establishes biological improvement.

## Tool V2 live result and source-based error interpretation

The [completed comparison](../evaluations/construction_planner_tool_v2_20261026_summary.json)
improved exact supported selections from **1/4 to 3/4**, while unsupported
requests admitted as executable-shaped proposals increased from **1/8 to 2/8**.
Pathway-only retrieval and the exact subset/focus now match. The combined request
still omits pathways. The assay-only condition remains silently dropped, and the
ambiguous request now receives a PPI plan instead of a clarification. The unknown
identity request produced a duplicate permitted accession and was rejected.

Five other unsupported requests returned `<TOOLCALL>[]</TOOLCALL>`. The frozen
strict one-call parser rejects them; their recorded `invalid_plan` status remains
unchanged. This is an output-contract observation, not evidence that the model
attempted a harmful action or understood why it should decline.

This representation is already understood in public tool-use evaluation. At
commit `6ea57973c7a6097fd7c5915698c54c17c5b1b6c8`, BFCL's
[irrelevance evaluator](https://github.com/ShishirPatil/gorilla/blob/6ea57973c7a6097fd7c5915698c54c17c5b1b6c8/berkeley-function-call-leaderboard/bfcl_eval/eval_checker/eval_runner.py#L263-L316)
recognizes empty lists as containing no function call. Its
[Nemotron handler](https://github.com/ShishirPatil/gorilla/blob/6ea57973c7a6097fd7c5915698c54c17c5b1b6c8/berkeley-function-call-leaderboard/bfcl_eval/model_handler/api_inference/nemotron.py#L17-L24)
is for Ultra 253B, so it is not an exact released parser contract for this Nano
revision. A future adapter may represent empty lists separately as no-call
outputs, but must not silently rescore this completed run or count them as useful
refusals. No parser change was made after observing these results.

[When2Call](https://aclanthology.org/2025.naacl-long.174/) and its
[released evaluator](https://github.com/NVIDIA/When2Call/blob/ecc8d42388e91ab37e7e737d48e16e8ecea3d1dc/evaluation/llm_as_a_judge/run_openai_judge.py#L25-L34)
distinguish tool calls, requests for information, inability to answer and direct
answers. An unexplained empty list does not establish which useful semantic
behavior occurred. Likewise, the
[vLLM 0.8.5 guarantee](https://docs.vllm.ai/en/v0.8.5/features/tool_calling.html#named-function-calling)
concerns schema conformity rather than answer quality. The combined-relation and
unsupported-condition failures demonstrate that boundary in this implementation.
The observed duplicate identifier cannot be causally attributed to decoding from
this comparison alone.

All twelve live cases had `explicit_selection_supplied=false`. The new guard is
locally tested, but cannot explain the measured gain or claim live effectiveness
here. Contract text, schema presentation, input serialization, decoding and engine
changed together; the comparison is not an ablation or a fresh holdout.

Decision: keep free-text V2 experimental and retain deterministic guided
construction. The next product integration should reuse caller-owned selections
and existing constructor checks, ask for missing choices and expose unsupported
requirements without executing them. This requires a separate assisted-workflow
evaluation; it is not a claim that an exact-selection guard detects arbitrary
unsupported language. Do not launch another prompt sweep on these consumed cases.

Exactly twelve model calls completed (9,288 prompt and 532 completion tokens).
No retrieval, tool execution or graph change occurred. Independent implementation
review verified the traces, hashes, counts and runtime evidence. The original V0
service was restored healthy; the temporary V1 service and tunnel were removed.
No biological gain or independent human scientific review is established.
