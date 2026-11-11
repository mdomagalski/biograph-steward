# Frozen Nemotron planner integration check — November 11, 2026

The single live planner request **abstained**, so it did not reproduce the
deterministic evidence answer. The graph and local review state were unchanged.
This is an exposed development integration check, not biological validation.

| Arm | Observed result |
|---|---|
| Deterministic query | Five assertions, eight relevant evidence records and two preserved annotation-disagreement groups; no omitted paths. |
| Nemotron planner | One model request, zero tool calls, no answer; question coverage **0/1**. |

The question explicitly requested candidate/unreviewed CIViC annotations for
the complete KRAS G13D molecular profile, treatment sets containing cetuximab,
and colorectal cancer (`DOID:9256`). Both arms used `max_results=30` and
`max_paths=5`. The original preparation and its 8 relevant / 38 off-scope
reference sets were preserved; the candidate wording and display limits were
frozen before inference.

Read-only inspection confirmed the existing L40S deployment: Nemotron Nano 8B
v1 model/tokenizer revision `54641c1611fcff44fa4865626462445e0a153fc7`, vLLM
0.8.5 with `VLLM_USE_V1=0`, and the pinned serving image. The request used the
existing `scoped_targets_v4` protocol and Nano prompt profile. It consumed
1,961 input tokens and 62 output tokens, with about 7.8 seconds recorded request
latency. There was one transport request and no retry, repair or fallback call.

The application resolved the exact profile, disease, therapy and candidate
view, and recorded `unsupported_requirements: []`. The model nevertheless
returned an abstention with reason `request_scope.unsupported_requirements`.
This is an unnecessary decline on the supported reference question. It is not
evidence of failed entity mapping, absent database records or a biological
contradiction. The response satisfies the output schema; that does not establish
correct execution or a factually justified reason.

A serving-observability gap remains: the pinned vLLM V0 implementation can
[switch grammar backends for this schema's item-limit constraint](https://github.com/vllm-project/vllm/blob/v0.8.5/vllm/model_executor/guided_decoding/__init__.py#L21-L85).
The effective per-request backend was not captured. Upstream support does not
show that either schema branch was unavailable, and this fallback does not
establish why the model declined. The underlying cause remains unresolved.

The v4 schema already binds the exact query arguments from deterministic
resolution. The model mainly chooses whether to query or abstain. Even success
here would establish governed execution, rather than independent classification
of the 46 evidence records or improvement over the deterministic selector.
Abstention cannot be counted as correctly pruning all excluded records.

The deterministic workflow remains the delivery path. The optional model is
not a prerequisite for graph qualification or the next pruning comparison.
No prompt or model was changed after seeing this result, and no second inference
was requested. The [AWS deployment assessment](AWS_NEPTUNE_20261111.md) records
the separate successful database/source and recovery checks.

Private, ignored artifacts:

- `runs/neptune_production_20261111/planner_scope_v2/` — frozen inputs and reference.
- `runs/neptune_production_20261111/brev_runtime_attestation.json` — live runtime observation.
- `runs/neptune_planner_scope_result_20261111/` — complete trace, comparison and artifact hashes.
