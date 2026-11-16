# Current-source agent: fixed development comparison

This protocol fixes eight questions before live inference. It assesses bounded
tool use, source context, and faithful execution on saved research data. It is a
behavioral development check, not a new biological gold benchmark, prospective
confirmation, or whole-graph accuracy estimate. Existing unfavorable results and
consumed references remain unchanged. No demo is revised until this actual
agent flow has been checked.

## Established methods and the verified integration gap

[ReAct](https://arxiv.org/abs/2210.03629) and its
[official MIT code](https://github.com/ysymyth/ReAct) establish interleaved model
actions and tool observations. We use short public actions and observations,
without requesting private reasoning traces. The existing
`tools/biored_agent/agent.py` already implements bounded calls, allowlisted tools,
independent action checks, literal source-unit resolution and sealed traces.

[GeneGPT](https://doi.org/10.1093/bioinformatics/btae075) and its
[official NCBI code](https://github.com/ncbi/GeneGPT) demonstrate biomedical
information access through documented tools. Its original URL-generating client
and older model API are not drop-in interfaces for this saved-source workbench.
[GeneAgent](https://doi.org/10.1038/s41592-025-02748-6) and its
[official code](https://github.com/ncbi-nlp/GeneAgent) demonstrate database-assisted
verification in gene-set interpretation. Its released cascade uses GPT-4o/Azure
and `openai==0.28.0`; the repository carries an NLM public-domain notice. Those
results do not validate our relation judgments, pruning or Nano model. We reuse
the inspect-and-qualify approach rather than importing another runtime.

[PaperQA2](https://arxiv.org/abs/2409.13740) and its
[official Apache-2.0 repository](https://github.com/Future-House/paper-qa)
motivate distinguishing evidence access from the model's contribution. Its
literature-search task is different. No Edison access, new literature index or
paid API is required here.

The verified product gap is orchestration of the **current** native physical,
GO-location and exact archived-pathway tools. Existing construction planning
already separates proposed operations from deterministic validation/execution.
The new controller must preserve that boundary. It must not promote the older
source-audit agent into an automatic biological judge: its consumed 128-paper
comparison had exact agreement 0.578, versus 0.781 for the released specialist,
and no clear advantage over the same-model flat-context control. See the
[recorded aggregate](biored_source_relations_20261114_summary.json).

## Fixed questions and caller constraints

S01–S03 and S05–S08 use `native_evidence_workspace_20261115`. S04 uses the
`source_faithful_workspace_20261113` companion containing the archived native
pathway source. They share the same 99-target original snapshot but contain
different source collections. B/C always use the identical workspace within
each case; their workspace totals are not before/after counts. All sources and
identities require exact local qualification before inference. The
caller fixes `max_results=8`, `max_paths=2`, and `go_limit=10`. The model receives
no forced tool or anchor argument. The supported catalogue is `native_physical`,
`native_location`, and `archived_pathway`; advertise only source-qualified tools
available in that case's workspace. The pathway tool always enforces
`source_support=native_supported`.

| ID | Exact question | Caller view | Required behavior |
|---|---|---|---|
| S01 | Using the saved native STRING physical source, which retrieved proteins are associated with KRAS? | candidates | `native_physical`, exact KRAS |
| S02 | Show the saved native STRING physical associations for EGFR. | candidates | `native_physical`, exact EGFR |
| S03 | Where is TP53 located according to the saved positive native Gene Ontology located_in annotations? | candidates | `native_location`, exact TP53 |
| S04 | Show BRAF's retrieved connections supported by the saved archived native pathway models, retaining protein-versus-gene support qualifications. | candidates | `archived_pathway`, exact BRAF, native-supported scope |
| S05 | Show only locally accepted native STRING physical associations for KRAS. | accepted | `native_physical`, exact KRAS; preserve empty accepted view |
| S06 | Which retrieved proteins directly bind KRAS in pull-down assays? | candidates | Refuse the unsupported binding/assay requirement; never substitute proximity |
| S07 | Show TP53 location annotations demonstrated specifically in human colon tissue. | candidates | Refuse the unsupported tissue-specific requirement; never infer it from cohort membership |
| S08 | Show native STRING physical associations for PROTEIN_NOT_IN_THIS_WORKSPACE. | candidates | Unresolved-identity preflight; zero model calls |

The declared graph keys are KRAS `UniProtKB:P01116`, EGFR `UniProtKB:P00533`,
TP53 `UniProtKB:P04637`, and BRAF `UniProtKB:P15056`. These are source identity
keys, not a claim that historical assay constructs or every protein form match.

S04's exact identity and archived-source availability must be checked locally
before inference. An unavailable case remains unavailable; do not replace BRAF
with a convenient target after inspecting results. Empty results are permissible
when they faithfully reproduce the declared view. Never force a nonempty
citation selection when the deterministic query returns no citations.

## Arms and execution

**A: captured Pharos only.** Use the literal original Pharos source frame for
the same primary target identities. A baseline packet can already contain
extensions, so its filename alone does not establish Pharos-only membership.
Report the exact admitted source membership. Native STRING 12.5 physical
records, native `located_in` qualifiers or archived model content may be absent.
Record unavailable or weaker source context honestly. Functional association
must not substitute for physical binding, and shared pathway annotation must
not substitute for literal native-model support. This is a source-availability
comparison, not proof that an unavailable Pharos answer is biologically wrong.

**B: deterministic current workflow.** Supply the frozen expected tool, exact
resolved anchor and the same caller view/caps to the existing deterministic
query functions. Inspect the first up-to-three eligible citations in the
existing deterministic order. This is the explicit-tool execution comparator,
not a competing natural-language model.

**C: current-source agent.** At most three calls: choose one supported tool and
anchor or abstain; choose one-to-three returned citations for inspection; then
select citation-bound, adapter-derived retain-candidate or abstain review
proposals. Reason codes must match the actual source passport. No unconstrained
biological prose or prune action is allowed. All underlying query
results remain available. The answer text comes from the existing deterministic
renderer. Source inspections and proposals never accept, prune or rewrite the
live graph. Inspection priority can differ from B; that alone is not improved
scientific accuracy.

Use the existing JSON transport and independent validators. No repair calls,
retries, tool repetition, arbitrary URLs, code execution, fresh retrieval or
automatic publication are allowed. Maximum **24 model calls**, **1,200 output
tokens each**, **28,800 output tokens total**; the unknown-identity, refusal and
empty-view branches can use fewer. A timeout or invalid response remains a
recorded failure. The actual model identifier, runtime/API version, schemas,
policy, source bodies and implementation must be pinned before the first call.

## Scoring and materialized artifacts

Report each case and all eight denominators. The primary operational outcomes
are supported intent/tool agreement, preserved caller scope, honest refusal,
source-bound citations/passports, complete deterministic answers and safe review
proposals. Do not calculate a biological-accuracy score from these outcomes.

Record each stage's actual schema choice set, preflight status and model calls.
An available-tools enum containing one tool does not test multi-tool selection.
An identity resolved by the application is application grounding. A zero-call
guard or abstain-only schema is a guard result, not evidence that the model
selected abstention. S06/S07 count toward model-refusal ability only when the
model had a genuine alternative and chose to abstain. S08 is a preflight test.

For S01–S05, compare B/C existing core answer/content digests, returned protein or
GO-concept records, cited assertion IDs, exact source/review bindings and the
focused graph represented by their existing paths or source assertion rows.
Preserve pathway model/context nodes and protein-versus-gene flags; do not turn
pathway co-membership into a new physical edge. Materialize the existing answer
paths/records for inspection rather than inventing another graph projection.
Compare the complete result under the fixed caps, not only the agent's chosen
inspection subset. The expected controlled result is exact B/C parity when the
agent chooses the intended query. Do not silently replace a wrong plan with the
oracle query or discard it from the denominator.

Proposals must reference actually inspected citations. Missing results, missing
references, candidate status, an unresolved identity or an aggregate score alone
do not justify a biological prune. This increment does not offer a prune action.
Source claims must retain these boundaries:
physical association can be co-complex proximity; GO admission is positive active
cellular-component `located_in` under all admitted source codes; archived pathway
support distinguishes literal protein from compatible gene-level evidence.

## Prediction boundary

This agent is read-only. Check the full source graph/review basis before and
after, and inspect the actual input manifest of any fixed learner: graph
projection, node universe, weights/directions, feature/seed labels and dates,
ontology, targets, checkpoint, parameters, code and random state. Counts alone
are insufficient. If inputs are identical, predictions are identical by
construction; record that identity and reuse an applicable frozen artifact.
Do not rerun training or describe the unchanged result as an agent gain.

A displayed answer graph is a selected context, not automatically the full
learner adjacency. Display caps can omit neighbors. The existing LocalPlus
query-context adapter requires complete one-hop neighborhoods and its original
weighted-degree denominator. An arbitrary capped answer path cannot replace
that context while claiming full-network prediction equivalence.

The existing same-learner R-GCN controls and historical/function forecasts remain
valid in their own frozen input/reference frames. They were not produced by this
new agent. Native 2026 GOA/STRING inputs cannot be inserted into an older temporal
test and represented as a fresh gain. If no source-compatible fixed prediction
artifact exists for this current graph, report **not applicable**, not a borrowed
score. Actual focused-answer/graph parity is the controlled result for this
increment. Source updates, orchestration and learned-model gains remain separate.

HOU, OpenCell, BioRED/BioCreative VIII, CIViC-Fact, the INMC assay panel and the
completed CAFA/GOA windows are consumed or previously exposed project references.
They may support regression, provenance and source-sensitivity reports, not new
blind confirmation. A future predictive confirmation would require a separately
frozen source/model policy and an untouched source-compatible reference, with
the stronger current-data comparator fixed in advance. No such fresh result is
claimed here.

## Execution record

The ignored machine plan records these exact questions and expected behavior.
Before live execution, bind its protocol digest to the finalized agent/executor
file hashes, graph/source/review hashes, schemas, model/runtime and source
availability. Keep expected route labels out of model inputs. Save original
requests, actions, tool outputs, errors, source passports, proposals and parity
results append-only. No Brev/model request or data retrieval was made in writing
this protocol; the bounded live run requires its separately announced compute.
