# NVIDIA integration and compute status

Checked November 13, 2026. The supported BioGraph demonstration uses guided
questions and deterministic, source-bound execution. NVIDIA model and workflow
integrations are optional. More deployment infrastructure does not provide
scientific labels or establish that a graph claim is correct.

The [current hosted update](evaluations/hosted_polish_update_20261113_summary.json)
uses code `0529d2b` on the existing AWS instance, with unchanged authentication
and permissions. Real restart, saved native answer/export replay and complete
Neptune parity/read checks passed. The separate aggregate grounding publication
is now API-verified there. This deployment used no Brev model, GPU inference,
new cloud resources or new biological comparison. The newer native GO web/QC
follow-up remains local-only and is not included in that hosted code.

## What the project actually uses

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
