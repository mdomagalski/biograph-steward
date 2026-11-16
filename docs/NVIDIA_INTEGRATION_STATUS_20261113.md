# NVIDIA integration and compute status

## November 16: current-source agent integration

The product now implements a model-directed [current-source workflow](SOURCE_AGENT.md)
for the actual native STRING physical, native GO location and native-supported
archived-pathway tools. The controller plans a query, executes an existing
source engine, materializes a focused contextual graph and cited answer,
inspects model-prioritized citation groups, and records adapter-bound review
proposals. Complete query results, source passports and model/tool traces stay
available. It neither changes the full graph nor applies biological acceptance
or pruning.

The implementation reuses the existing `JSONModelClient`, pinned model connection
settings and bounded read-tool controller pattern. It is a first-class app/CLI
route, rather than the older optional one-call planner. The shared saved-data
site can replay verified recorded jobs; new model execution belongs to the
explicit live operator route. Live evaluation and deployment receipts must be
recorded separately: code availability is not evidence that inference occurred.

The [fixed current-tool protocol](evaluations/SOURCE_AGENT_PROTOCOL_20261116.md)
compared explicit deterministic execution and this agent on the same saved
source frames and caps. The [completed assessment](evaluations/SOURCE_AGENT_RESULTS_20261116.md)
passed five supported full-query/answer/focused-graph parity checks: four
nonempty source questions and one valid empty accepted-only query. Three other
requests were blocked by preflight guards with zero model calls. Those guard
outcomes are controller behavior, not model reasoning.

The supported executions used **13 Nemotron calls and 972 completion tokens**.
Application code grounded all exact identities. Only the TP53 location case had
two available query choices; other supported planning schemas offered one tool
plus abstention. These eight behavioral checks do not establish unrestricted
routing or scientific accuracy. Original source, graph and review hashes were
unchanged, so no prediction improvement is attributed to this agent run.
The [aggregate receipt](evaluations/source_agent_20261116/summary.json) preserves
its separate endpoints and model/source commitments.

The featured recorded job is `source_agent_eval_dc7b597201da_S01`. It is
prepared for hosted replay; deployment remains pending a separately accepted
restart/source-check receipt. A saved replay does not make new model calls.

The older planning and BioRED audit results below retain their original model,
corpus and dates. They are not replaced or converted into results for this new
controller. The NeMo Agent Toolkit wrapper still registers the older bounded
workflow; no new NAT, NemoClaw or other agent platform is required by the current
Python controller.

## November 14 update: completed source-audit comparison

The November 14 source-audit evaluation used the exact served model
`nvidia/Llama-3.1-Nemotron-Nano-8B-v1`, revision
`54641c1611fcff44fa4865626462445e0a153fc7`, in bfloat16 on the existing
vLLM **0.8.5 V0** service. XGrammar **0.1.18** is installed and configured as the
server default; the native selector routes these `minItems`/`maxItems` schemas
to **Outlines 0.1.11** (`outlines_core` **0.1.26**), as verified by the sealed
capability probe. Requests supply `guided_json` without a backend override;
responses do not independently report backend selection. The bounded
source-audit controller is the project's Python implementation. Sealed runtime
observations before and after execution confirm the same model, container and
configuration.

| Fixed arm | Cases | Model calls | Tool-result reads |
|---|---:|---:|---:|
| Bounded source-audit agent | 128 | 512 | 384 |
| Same model, flat context | 128 | 128 | 384 |

Both arms received the same permitted abstracts, entity contexts and frozen
specialist outputs. Every agent case read the three tools in the same order;
adaptive retrieval benefit was not demonstrated. The native BioREDirect
specialist performed better: exact positive-relation F1 **0.588235**, versus
**0.486957** for the agent and **0.470588** for flat context. The frozen
agent-adoption criterion is **false**. These are curator-reference agreement
results, with the training-exposure and biological-scope limits recorded in the
[complete BioRED assessment](evaluations/BIORED_SOURCE_RELATIONS_20261113.md)
and [current scientific results](evaluations/SCIENTIFIC_RESULTS_20261114.md).

The BioRED live-model job is finished. Reviewing saved results in the workbench
requires no Brev model server or GPU. The earlier planning, deployment and
platform checks below retain their original November 13 scope and dates.

## November 13 review, retained

Checked November 13, 2026. The supported BioGraph demonstration uses guided
questions and deterministic, source-bound execution. NVIDIA model and workflow
integrations are optional. More deployment infrastructure does not provide
scientific labels or establish that a graph claim is correct.

The [current hosted update](evaluations/hosted_native_go_20261113_summary.json)
uses code `ea5752e` on the existing AWS instance, with unchanged authentication
and permissions. Real restart, saved native answer/export replay and complete
Neptune parity/read checks passed. The separate aggregate grounding publication
remains API-verified there. The approved separate native GO/QC packet enables
on-demand source inspection, with both NRAS examples checked through the API
across restart. This deployment used no Brev model, GPU inference, new cloud
resources, new rule/reasoner execution or new biological comparison. Fresh
software installations remain unconfigured; another agent platform is unnecessary.

## Recorded roles at the November 13 checkpoint

| Component | Current role and boundary |
|---|---|
| Core workbench | Ordinary Python and CPU for saved questions, source inspection, review and exports. No model server is required. |
| Nemotron Nano 8B v1 through vLLM | The [pinned Brev configuration](LOCAL_MODEL.md) remains the recorded model setup. The latest [live supported-question check](evaluations/NEMOTRON_NEPTUNE_PLANNER_20261111.md) unnecessarily abstained. It is experimental and not the primary demonstration. |
| NeMo Agent Toolkit wrapper | The optional extra pins `nvidia-nat-core==1.8.0`. It registers the existing bounded read-only question workflow; it does not authorize arbitrary tools, change graphs or improve biological accuracy. |
| NemoClaw | Documentation and method fit reviewed; not installed, integrated or evaluated in this project. |

## Upstream lifecycle and NemoClaw decision

The [official NeMo Agent Toolkit documentation](https://docs.nvidia.com/nemo/agent-toolkit/latest/index.html)
announces deprecation in October 2026 and EOL by the end of 2026. It points to
NeMo Relay for observability/governance, Helix for evaluation/optimization,
and Fabric for agent execution. Keep the tested optional pin identifiable as
a legacy integration; do not describe it as a current long-term platform
commitment. The application core does not depend on it, so this notice does
not require a core rewrite or a migration before submission. Any replacement
needs its own compatibility check.

[NemoClaw](https://github.com/NVIDIA/NemoClaw) is an Apache-2.0 reference stack
for running supported agents inside OpenShell sandboxes. Its documented
capabilities include inference routing, policies and lifecycle operations.
The project still describes itself as alpha. The latest documented release at
this check is [v0.0.143, November 10, 2026](https://docs.nvidia.com/nemoclaw/latest/user-guide/openclaw/release-notes).
It is distinct from the Nemotron model and from the existing Python NAT wrapper.

The [NVIDIA ecosystem guidance](https://docs.nvidia.com/nemoclaw/latest/user-guide/openclaw/about/ecosystem)
positions NemoClaw as a reference-agent deployment path, with a separate
OpenShell/custom-integration route for workloads outside its blueprint. Our
current bounded workflow has no unattended external tool execution requiring
that new harness. Installing it would add deployment and policy qualification;
it would not fix the observed planner decline, supply missing provenance or
turn source agreement into independent biological truth.

**Decision:** defer NemoClaw installation from the closing release path. A
later, separately scoped read-only source-audit assistant could justify a pilot.
Reuse the existing source tools and preserve model/tool traces in that pilot;
evaluate its task before changing any default workflow. The upstream
[Relay](https://github.com/NVIDIA/NeMo-Relay) and
[Fabric](https://github.com/NVIDIA/NeMo-Fabric) projects are alternatives to
qualify for observability or execution, not automatic quality improvements.

NemoClaw's [prerequisites](https://docs.nvidia.com/nemoclaw/latest/user-guide/openclaw/get-started/prerequisites)
include 4 vCPU, 8 GB RAM and 20 GB free disk, plus current Node/npm and a supported
container runtime. Inference requires additional capacity. Its
[existing-vLLM route](https://docs.nvidia.com/nemoclaw/latest/user-guide/openclaw/inference/local-inference/set-up-vllm.md)
can reuse a server, but generic-host setup is marked experimental. Compatibility
with our particular pinned model/runtime is not established by those docs.

## Resources for the remaining release work

| Work | Resource to use |
|---|---|
| Documentation, UI fixes, ordinary source retrieval, identifier audits and saved-data checks | Local CPU with sufficient free disk. No Brev model or GPU is needed. |
| A large archive/source replay that exceeds local capacity | Plan a CPU job on an available host, keeping source/evidence preservation explicit. The model can remain off. |
| A specific fixed Nemotron compatibility comparison | Start the existing Brev instance and model only after stating requests, token budget and allowed actions. Report when it is no longer needed. |
| Hosted real-data walkthrough and database inspection | Use the existing AWS app and Neptune when those paths are needed. A local saved-data walkthrough requires neither. |

No paid instance is started, stopped or resized by this guidance. Account bills
and remaining credits were not queried for this review. Available credits can
support a justified bounded job; they do not require another platform or model
experiment. The [recovery receipt](evaluations/aws_isolated_recovery_20261113_summary.json)
and [delivery index](releases/20261113/README.md) record the existing deployment
and checkpoint scope separately from current software and scientific results.
