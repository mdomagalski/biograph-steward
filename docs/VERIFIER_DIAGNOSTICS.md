# Verifier diagnostic ladder

`scripts/diagnose_verifier.py` separates serving and output problems from source
selection and claim comparison. It is a small development diagnostic, not a new
biological benchmark. It makes explicit requests to an existing loopback model
endpoint, writes new local artifacts, and changes no graph, review decision,
production verifier default, or model service.

The current runner freezes `verifier-diagnostics.v4` packets with an explicit
profile and instruction recipe. Omitting `--profile` selects `reasoning-off`;
reasoning on is opt-in. Omitting `--recipe` selects `baseline`.

| Profile / recipe | Synthetic gate | Context stage | Classification ladder ceiling |
|---|---|---|---|
| `reasoning-off` / `baseline` | Six cases in each of ordinary and guided arms; both must pass 6/6. | Eight guided labels and four ordinary fact answers. | 24 primary, plus at most four qualifying enum-order probes. |
| `reasoning-on` / either recipe | Six ordinary cases; all must pass. | Eight ordinary labels and four ordinary fact answers. | 18; no guided or enum-order calls. |
| `reasoning-off` / `few-shot` | Six ordinary cases; all must pass. | Eight ordinary labels and four ordinary fact answers. | 18; no guided or enum-order calls. |

Stop at the stage gates below. Do not repeat stages in new directories to obtain
a better answer. A deliberately changed protocol requires a new packet and a
separately identified development experiment. The separate eight-call reading
probe and four-call source-fact probe below have their own explicitly bounded
purposes; neither replaces a prediction or reopens a failed classification gate.

## Prepare without inference

Run commands from the repository root. The example requires the saved context
packet from the preceding CRC development comparison; its sources are not
downloaded again.

```sh
python3 -m scripts.diagnose_verifier prepare \
  --context-packet runs/crc_context_verification_20261020/packet_map \
  --profile reasoning-off \
  --recipe baseline \
  --out runs/verifier_diagnostics_001/packet
```

Preparation verifies the parent input/reference hashes and freezes invented
claims, reused CRC claims, source windows, separate references, model settings,
instructions, and the runner's code hash. It makes no model request. Output
directories must be new. Changing the runner after preparation invalidates that
packet for subsequent use; preserve the matching code revision for replay.

Both profiles use `nvidia/Llama-3.1-Nemotron-Nano-8B-v1`, seed zero, one response,
and no streaming. Their complete settings are frozen in `protocol.json`:

| Setting | `reasoning-off` | `reasoning-on` |
|---|---|---|
| System message | `detailed thinking off` | `detailed thinking on` |
| Temperature / top-p | 0 / 1 | 0.6 / 0.95 |
| Label / fact output-token budgets | 128 / 384 | 2,048 / 2,048 |
| Timeout per request | 60 seconds | 120 seconds |
| Reasoning envelope | Rejected | `native-thinking-final.v1` |

The endpoint must be explicit loopback HTTP at `/v1/chat/completions`; redirects
and proxies are disabled. The script does not start a model, open a tunnel, or
provision compute. Changing profiles changes a configuration package, including
sampling, budgets, parsing, and decoding mode; it does not isolate the causal
effect of reasoning alone.

## Baseline reasoning off: ordinary versus guided classification

```sh
python3 -m scripts.diagnose_verifier run \
  --packet runs/verifier_diagnostics_001/packet \
  --stage synthetic \
  --endpoint http://127.0.0.1:8000/v1/chat/completions \
  --out runs/verifier_diagnostics_001/synthetic

python3 -m scripts.diagnose_verifier verify \
  --result runs/verifier_diagnostics_001/synthetic \
  --packet runs/verifier_diagnostics_001/packet
```

Six invented claims each receive one ordinary and one guided-choice request,
alternating arm order: **12 calls**. The prompt and source bytes are identical
between arms. Guided requests additionally specify the three allowed labels and
`xgrammar:no-fallback`. This requests that backend; the model response alone
does not independently attest which decoder served the request.

All six use a fictional study in which adults with condition A and marker V1
receive drug P plus drug Q or drug Q alone. The combination increases endpoint E;
the between-arm difference in endpoint F is not statistically significant. The
claims comprise two supported statements, two explicitly opposing findings in
the same context, and two unsupported changes of regimen or condition.

The label definitions remain distinct:

- `SUPPORT`: the source establishes every material claim and qualifier.
- `CONTRADICT`: an explicitly opposing finding in the same context.
- `NOT_ENOUGH_INFORMATION`: a missing, ambiguous, or different material context.

Thus changing an observed increase to a decrease is contradiction; substituting
an unstudied monotherapy or condition is insufficient information. Nonsignificance
does not establish no effect, equivalence, benefit, or harm.

**Both arms must produce six valid labels and six reference matches to advance.**
The runner enforces this gate before any CRC diagnostic calls. Inspect the
three-way confusion counts and paired responses rather than treating an
all-SUPPORT or all-insufficient answer as useful performance.

If both arms fail these basic distinctions, stop and examine prompt serialization,
serving configuration, or model capability. If ordinary succeeds while guided
fails, investigate decoding before adding biological tasks. A failure of ordinary
formatting alone does not establish a reasoning failure; it still blocks this
preregistered ladder.

## Baseline reasoning off: conditional enum-order diagnostic

Use this instead of advancing when an ordinary response is correct and the paired
guided response is a **valid but wrong label**:

```sh
python3 -m scripts.diagnose_verifier run \
  --packet runs/verifier_diagnostics_001/packet \
  --stage order \
  --previous runs/verifier_diagnostics_001/synthetic \
  --endpoint http://127.0.0.1:8000/v1/chat/completions \
  --out runs/verifier_diagnostics_001/order

python3 -m scripts.diagnose_verifier verify \
  --result runs/verifier_diagnostics_001/order \
  --packet runs/verifier_diagnostics_001/packet
```

The runner reverses the guided label order for at most the first four qualifying
synthetic cases in frozen input order. Invalid output or transport failure does
not qualify as a valid wrong label. With no qualifying pair, the command refuses
to run. This is a conditional decoder diagnostic, not a retry that replaces an
earlier prediction. Preserve both results and stop afterward; enum-order recovery
does not satisfy the original synthetic gate or authorize the context stage.

## Baseline reasoning off: facts, matched claims, and source windows

Run only after the synthetic result passes both arms:

```sh
python3 -m scripts.diagnose_verifier run \
  --packet runs/verifier_diagnostics_001/packet \
  --stage context \
  --previous runs/verifier_diagnostics_001/synthetic \
  --endpoint http://127.0.0.1:8000/v1/chat/completions \
  --out runs/verifier_diagnostics_001/context

python3 -m scripts.diagnose_verifier verify \
  --result runs/verifier_diagnostics_001/context \
  --packet runs/verifier_diagnostics_001/packet
```

This stage makes **12 calls**:

- Four existing claims each receive a guided-choice assessment with the full
  abstract and a focused source window: eight classification calls. They are
  `krystal-response`, `krystal-regimen`, `prime-os`, and `prime-significance`.
- Two claim-free questions each receive an ordinary answer with both windows:
  four source-fact calls. One asks for each KRYSTAL treatment arm's response
  percentage and evaluable patient count. The other asks for the PRIME wild-type
  KRAS treatment comparison and the PFS/OS significance and P values.

The paired claims separate the 46% response in the adagrasib-plus-cetuximab arm
from an unsupported cetuximab-monotherapy claim, and a nonsignificant wild-type
KRAS OS increase from an opposing significant-OS claim. The latter is
contradiction; the unstudied regimen is insufficient information.

Focused windows are a diagnostic aid, not newly retrieved evidence. They retain
the study methods and relevant results. PRIME's results selection preserves the
wild-type scope and both endpoints, with exact parent offsets and a source hash;
it does not supply only the answer sentence. Full windows retain abstract
background and other results that can distract from the relevant arm or endpoint.
Claim-free extraction requests contain the source and question, without a claim
to confirm or a reference answer to copy.

The development target is **8/8 valid, correct claim labels and 4/4 complete,
correctly associated source-fact answers**. Report full and focused windows
separately. Classifications are scored against the frozen references. Fact
answers require source review: the summary deliberately leaves
`complete_and_correctly_associated` as `null`. A completed fact response means
only that a bounded, nonempty answer arrived. Do not equate completion with
correct extraction or fill these judgments automatically from word overlap.
Record any review separately with the result hash, case ID, reviewer, source
locators, and reasons; do not edit the frozen summary or receipt.

Review requested-field coverage separately from the fidelity of the whole answer.
A response can preserve every requested association while adding an incorrect
number, unsupported absence claim, or unrelated assertion. Such a response is
not a clean extraction merely because its core fields match. An AI source review
also does not create independent human expert labels.

Use the failure pattern to choose the next experiment:

| Observed pattern | Next investigation |
|---|---|
| Correct with focused text, wrong with the full abstract | Selection and binding of facts amid background and other endpoints. |
| Correct source facts, wrong matched verdict | Claim comparison, context composition, and decision consistency. |
| Wrong facts even with focused text | Instructions or model capability before adding more sources. |
| Invalid or truncated responses | Interface reliability; semantic correctness remains unestablished. |
| All development targets met | Freeze the next interface and evaluate separately on independently labeled or reviewed cases. |

Selecting source IDs can guarantee that displayed quotations are exact. It cannot
prove that a selected result belongs to the claimed treatment arm, population, or
endpoint. These probes diagnose that distinction before another large evaluation.

## Opt-in reasoning-on ladder

Prepare a new packet; do not change the profile inside an existing freeze or
reuse another profile's synthetic result as its gate:

```sh
python3 -m scripts.diagnose_verifier prepare \
  --context-packet runs/crc_context_verification_20261020/packet_map \
  --profile reasoning-on \
  --recipe baseline \
  --out runs/verifier_reasoning_on_001/packet

python3 -m scripts.diagnose_verifier run \
  --packet runs/verifier_reasoning_on_001/packet \
  --stage synthetic \
  --endpoint http://127.0.0.1:8000/v1/chat/completions \
  --out runs/verifier_reasoning_on_001/synthetic

python3 -m scripts.diagnose_verifier verify \
  --packet runs/verifier_reasoning_on_001/packet \
  --result runs/verifier_reasoning_on_001/synthetic
```

This profile uses the same six invented claims and label definitions, with
**six ordinary requests only**. It advances only on six valid labels and six
reference matches. Guided decoding and the `order` stage are unavailable. If
the gate fails, stop; do not interpret conservative or invalid outputs as a pass.

After a passing synthetic result, the context stage uses the same eight paired
claims and four source-only questions described above, **all ordinary output**:

```sh
python3 -m scripts.diagnose_verifier run \
  --packet runs/verifier_reasoning_on_001/packet \
  --stage context \
  --previous runs/verifier_reasoning_on_001/synthetic \
  --endpoint http://127.0.0.1:8000/v1/chat/completions \
  --out runs/verifier_reasoning_on_001/context

python3 -m scripts.diagnose_verifier verify \
  --packet runs/verifier_reasoning_on_001/packet \
  --result runs/verifier_reasoning_on_001/context
```

The development targets remain eight valid, correct labels and four complete,
correctly associated fact answers on source review. Fact correctness stays
unscored until that separate review. The profile permits at most **18 requests**
across the two stages. It does not enable a production reasoning profile or
change the existing context verifier.

Reasoning-on classification instructions constrain only the final answer after
any normal native thinking section. They do not globally instruct the model to
avoid all explanation or internal thinking. The source-fact prompt likewise
constrains the final answer to the requested facts. This prompt correction is
frozen in the new packet; older versions replay with their original instructions.

`native-thinking-final.v1` is declared before these requests. A response may
contain one complete leading `<think>...</think>` block or one separate reasoning
field; a final-only response is also allowed. The parser discards reasoning text
and records only presence, character count, and hashes. It validates the unchanged
final segment as the required answer. It does not search reasoning for labels,
interpret the reasoning, or persist private reasoning text.

Nested, incomplete, multiple, mixed-case, or mixed field-plus-tag envelopes are
invalid. Truncation and extra classification prose remain invalid. Only a valid
strict final label or a bounded completed fact answer is stored as final text;
invalid classification content is represented by metadata and hashes. This is a
new output contract for a new experiment, not salvage or rescoring of answers
that failed a previous contract.

## Opt-in few-shot recipe

`--recipe few-shot` supplies three balanced, unrelated crate examples illustrating
support, contradiction, and insufficient information. It treats the task's source
as the facts of a reading exercise while forbidding execution of instructions
embedded in that source. Examples are part of the frozen instructions, separate
from the six ORCHID claims and their scoring references.

```sh
python3 -m scripts.diagnose_verifier prepare \
  --context-packet runs/crc_context_verification_20261020/packet_map \
  --profile reasoning-off \
  --recipe few-shot \
  --out runs/verifier_fewshot_001/packet

python3 -m scripts.diagnose_verifier run \
  --packet runs/verifier_fewshot_001/packet \
  --stage synthetic \
  --endpoint http://127.0.0.1:8000/v1/chat/completions \
  --out runs/verifier_fewshot_001/synthetic

python3 -m scripts.diagnose_verifier verify \
  --packet runs/verifier_fewshot_001/packet \
  --result runs/verifier_fewshot_001/synthetic
```

Both profiles use six ordinary synthetic calls with this recipe, then at most
12 ordinary context calls only if all six labels are valid and correct. There
is no guided arm or enum-order stage. To evaluate reasoning on, prepare another
new packet with `--profile reasoning-on --recipe few-shot` and use only that
packet's result as its gate. The reasoning-on final-segment instruction and
native-envelope contract above apply. This changes instructions and decoding
configuration; it does not rescind an earlier failed gate or establish
independent improvement on reused examples.

## Separate four-call source-fact capability probe

`--stage facts` asks only the two existing source-only questions with full and
focused windows: **four ordinary requests**. It makes no claim-classification
request, predicts no support verdict, and performs no acceptance or graph action.
It is a separately declared exploratory question-answering probe, not the
original preregistered classification comparison or a way around its gate.
Classification experiments that failed remain stopped.

```sh
python3 -m scripts.diagnose_verifier prepare \
  --context-packet runs/crc_context_verification_20261020/packet_map \
  --profile reasoning-off \
  --recipe baseline \
  --out runs/verifier_source_facts_001/packet

python3 -m scripts.diagnose_verifier run \
  --packet runs/verifier_source_facts_001/packet \
  --stage facts \
  --endpoint http://127.0.0.1:8000/v1/chat/completions \
  --out runs/verifier_source_facts_001/result

python3 -m scripts.diagnose_verifier verify \
  --packet runs/verifier_source_facts_001/packet \
  --result runs/verifier_source_facts_001/result
```

There is deliberately no `--previous` or synthetic gate for this isolated probe,
because it does not assess claims. The reasoning-off baseline extraction prompt
is unchanged; only fact questions and their supplied passages enter requests.
Record the extra four requests as a separate exploratory allocation rather than
silently adding them to an earlier experiment's ceiling. Successful completion
or requested-field coverage cannot satisfy a classification gate, unlock the
`context` stage, validate the full generated answer, or justify model promotion.
Correctness remains pending separate source review; the original summary's fact
correctness fields stay `null` and human expert-label counts remain zero.

## Separate reading and prompt probe

`scripts/probe_verifier_prompt.py` freezes a separate invented-text diagnostic.
It uses reasoning off and ordinary output, with no guided JSON, guided choice,
or response-format parameter. It makes **two requests before a wire gate**, and
at most **eight total**:

```sh
python3 -m scripts.probe_verifier_prompt prepare \
  --out runs/verifier_prompt_probe_001/packet

python3 -m scripts.probe_verifier_prompt run \
  --packet runs/verifier_prompt_probe_001/packet \
  --endpoint http://127.0.0.1:8000/v1/chat/completions \
  --out runs/verifier_prompt_probe_001/result

python3 -m scripts.probe_verifier_prompt verify \
  --packet runs/verifier_prompt_probe_001/packet \
  --result runs/verifier_prompt_probe_001/result
```

The default sentinel request unambiguously asks for the text inside quotation
marks, without quotes or punctuation: `CHECK_7319`. The second request asks for
the exact value of a source field: `blue`. Both must match their frozen targets
with valid model, finish, and role metadata and no tools, refusals, reasoning, or
extra prose. Otherwise the run closes after two requests and executes no
classification calls. The full eight-request plan remains in the artifact even
when only two requests execute.

After that gate, three claims about a crate containing three red balls and no
blue balls receive the current classification policy and a neutral reading
policy, with alternating order. The claims cover support, explicit contradiction,
and insufficient information. Only the policy text changes between paired
requests; source and claim bytes remain identical. The summary reports each
policy's three-way results and the wire gate separately. References are opened
for scoring after executed predictions close. A sentinel/copy pass is software
evidence, not biological verification, and this probe does not unlock either
ladder's context stage.

## Artifacts, validation, and limits

Each stage saves `requests.json`, `traces.json`, `execution.json`, `summary.json`,
and `receipt.json`. Requests are frozen before calls; reference-based scoring
occurs after stage predictions close. Traces record status, final answer when
permitted, hashes, latency, available token usage, and returned model identity.
Summaries show valid labels, reference matches, confusion counts, label counts,
full/focused results where applicable, and unscored fact answers.

Classification accepts only a single final allowed label, apart from outer
whitespace. Extra prose, refusals, tool calls, a different returned model,
truncation, or transport errors remain failures. Reasoning off rejects reasoning
wrappers and fields; reasoning on accepts only its predeclared native envelope
and strict final segment. Neither profile persists or mines reasoning text.
There is no substring label recovery, source-span repair, retry, or replacement
prediction. Invalid responses remain in all-case denominators.

Always supply `verify --packet` for the stronger replay: it checks packet and
result hashes, exact request bindings, the frozen runner, and the reproduced
summary. Verification without `--packet` checks result inventory and request/trace
bindings but does not reproduce reference scoring. Verification makes no model
requests.

## Replay preserved earlier results

The current version deliberately refuses packets bound to earlier implementations.
The preserved `frozen_v1` scripts allow the original off-mode ladder and prompt
probe to replay with their own code and output contract. Do not edit their
packets, receipts, or parser to make them acceptable to the new runner.

From the repository root, use the frozen scripts and put their parent ahead of
the live repository on the import path. Replace the packet/result placeholders
with the corresponding saved v1 artifacts:

```sh
PYTHONPATH="$PWD/runs/verifier_diagnostics_20261020/frozen_v1:$PWD" \
  python3 "$PWD/runs/verifier_diagnostics_20261020/frozen_v1/scripts/diagnose_verifier.py" \
  verify --packet /absolute/path/to/v1/packet --result /absolute/path/to/v1/result

PYTHONPATH="$PWD/runs/verifier_diagnostics_20261020/frozen_v1:$PWD" \
  python3 "$PWD/runs/verifier_diagnostics_20261020/frozen_v1/scripts/probe_verifier_prompt.py" \
  verify --packet /absolute/path/to/v1/probe-packet --result /absolute/path/to/v1/probe-result
```

The import-path order matters because the frozen prompt probe imports
`scripts.diagnose_verifier`. These are verification commands only, with no model
calls. Keep the source snapshot and `code_manifest.json` beside saved artifacts;
the snapshot is an evaluation record, not a production implementation fork.

The `frozen_v2` and `frozen_v3` directories preserve the intermediate reasoning-on
and few-shot runners. Replay their own packets with the matching snapshot,
never the latest parser or an edited protocol. For example:

```sh
PYTHONPATH="$PWD/runs/verifier_diagnostics_20261020/frozen_v2:$PWD" \
  python3 "$PWD/runs/verifier_diagnostics_20261020/frozen_v2/scripts/diagnose_verifier.py" \
  verify --packet /absolute/path/to/v2/packet --result /absolute/path/to/v2/result

PYTHONPATH="$PWD/runs/verifier_diagnostics_20261020/frozen_v3:$PWD" \
  python3 "$PWD/runs/verifier_diagnostics_20261020/frozen_v3/scripts/diagnose_verifier.py" \
  verify --packet /absolute/path/to/v3/packet --result /absolute/path/to/v3/result
```

## Interpretation limits

The source panel is reused development material from two public publications;
the earlier 18-case panel has already been observed. Invented examples and
AI-authored CRC references are not independent biomedical gold. The facts require
explicit source review, and cases sharing papers or trials are not independent
studies. No result establishes clinical accuracy, biological graph improvement,
generalization to new papers, or safety of automatic acceptance or pruning.
Existing comparison artifacts remain unchanged.
