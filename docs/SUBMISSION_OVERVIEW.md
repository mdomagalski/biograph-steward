# BioGraph Steward submission overview

BioGraph Steward builds and inspects scoped Pharos evidence graphs. A
researcher chooses a supported question, follows the answer's graph paths to
their original records, and exports the complete workspace with its baseline
and review decisions. Guided execution is the dependable route. Optional
NVIDIA model planning and source-audit agents are implemented and evaluated,
with their limitations retained.

This overview describes the working product and evidence available on
**November 15, 2026, Eastern time**. Research identifiers ending `20261115`
use UTC. The [delivery status](DELIVERY_STATUS_20261115.json) separates the
verified hosted checkpoint, local software, research results and remaining
submission actions. The longer [submission record](FINAL_SUBMISSION.md)
provides the evidence appendix.

## Review the application

[Open the saved native KRAS example](https://bi-3a117d5e2b3942678dc518fce65ab5d2.ecs.us-east-2.on.aws/?run=native_evidence_workspace_20261115&question=native_physical_KRAS_question_v3_20261115&view=ask), using the workspace token supplied
privately. The [ten-minute guide](REVIEW_NATIVE_EVIDENCE_20261115.md) provides
five short review tasks: find the 14 candidate result proteins, inspect one
STRING source record, compare the empty accepted-only view, interpret one
public-reference result and distinguish answer from workspace downloads.
No AWS account, local tunnel or model server is needed.

The shared reviewer route runs code **`47a2e5a`** with an explicit saved-data-only
server policy. It supports saved questions, source inspection and downloads.
Construction, fresh retrieval, model calls and review edits are blocked. The
shared token admits the valid saved workspaces; it does not create individual
reviewer roles. Reviewers need a browser and the token supplied privately, with
no AWS account, Brev instance or model server. The
[hosted acceptance receipt](evaluations/native_profiles_hosted_20261115/summary.json) records a real service
restart, authenticated saved-answer/source checks and preservation of the
older graph, review states, environment and private Neptune connection.

The [earlier qualified TP53 example](https://bi-3a117d5e2b3942678dc518fce65ab5d2.ecs.us-east-2.on.aws/?run=source_faithful_workspace_20261113&question=question_20261113T075313Z_1a76b00f&view=ask) remains available with its
historical WikiPathways passport and identifier-currency decisions. Use the
[five-minute demonstration](DEMO_SCRIPT.md) for that workflow and the
[team testing guide](TEAM_REVIEW_GUIDE_20261113.md) to record obstacles and unclear
terms. Independent teammate feedback remains pending.

For a checkout-only route, use `codex/contextual-gain-delivery` and follow
[START_HERE](../START_HERE.md); default `main` still has the older checkpoint:

```sh
python3 app.py
```

Python 3.10+ runs the core app without pip, GPU or cloud setup. Choose
**Data & saved work > Offline demonstration > Build synthetic demonstration**.
Those records are invented and test the software. The separate
[CC0 Reactome annex](../examples/reactome_context_20261113/README.md) supplies a
small real-source inspection example directly from the repository. Repository
access alone does not include the complete mixed-source demonstration packet.

## What the product delivers

| Capability | Implemented scope |
|---|---|
| Scoped graph construction | Bounded Pharos retrieval and exact-accession construction, with saved requests, coverage and source snapshots. The main demonstration has 99 primary protein targets. |
| Biological source context | CIViC clinical profiles and complete therapy combinations; qualified STRING, MAP-IT and SIGNOR extensions; separately qualified assay examples; native GO locations, sequence-qualified STRING physical associations and pathway source inspection. Availability depends on the selected workspace and its source attachments. |
| Readable questions and sources | Five task tabs, supported question templates, bounded multihop paths, cited summaries, source versions, original records and unresolved context. |
| Review and maintenance | Versioned assertions, explicit lifecycle states, immutable snapshots, review history and guarded snapshot comparison. Uncertain records stay visible. |
| Export and standards | Retained graph, exhaustive decisions and original baseline/source packet. Stable identifiers, explicit Biolink references, a bounded KGX projection and qualified SSSOM mappings retain documented conformance limits. |
| Local and cloud operation | Dependency-light Python app, Docker/deployment configuration, authenticated AWS reviewer app and private Neptune mirror. Ordinary saved answers use workspace files; the database inspector performs read-only Neptune queries. |

Two separate saved workspaces remain available:

| Workspace | Scope and use |
|---|---|
| New native-evidence profile | **99 primary targets, 9,724 entities and 19,310 evidence records**: 15,671 original Pharos records, 3,309 native GOA rows and 330 STRING physical associations. Additions remain candidates. Use the KRAS answer and public-reference comparison. |
| Earlier qualified retained graph | **99 primary targets, 9,865 entities and 16,687 retained records**, with the 16,985-record input and every keep/prune/abstain decision preserved. Its 298 obsolete-GO-ID exclusions concern identifier currency, not experimentally disproved biology. Use the TP53 pathway example. |

The new source profile does not replace the earlier retained graph or its
reviews. The private Neptune mirror continues to hold that earlier qualified
graph. Ordinary saved answers, including the new native profile, use their
saved workspace files.

The native physical source records 330 pairs, of which **243 already have a
pair represented in the captured Pharos graph and 87 do not**. These are
versioned source records and new workspace pairs, not independent experiments
or discoveries. Exact reciprocal alias and full-sequence checks admit 77 of
99 targets; 21 sequence mismatches and one missing direct alias stay unresolved.
A physical association can describe shared-complex membership without direct
binding. STRING already supplies Pharos, so adding its separately qualified
physical view does not create an independent evidence vote.

The main Pharos319 capture is frozen at October 14, 2026. Later source context
keeps its own dates. A November 15 UTC metadata-only API check returned
`pharos319`; it did not replace the frozen graph or establish equivalence with
Pharos400 artifacts.

## What the measurements support

| Question tested | Result and interpretation |
|---|---|
| Does adding context improve the same graph learner over the original baseline? | Matched R-GCN comparisons are complete, with mixed or negative results against their controls. A consistent advantage on the challenge's central enriched-graph link-prediction task remains unestablished. |
| Can published methods recover later protein-function annotations? | The [completed contextual comparison](evaluations/CONTEXTUAL_COMBINATION_RESULTS_20261115.md) improves over retained LocalPlus in both fixed primary views: Fmax 0.05473 → 0.07343 and 0.17155 → 0.21009, with paired intervals above zero. Updating annotations also helps primary BP. Extra learning benefit beyond that updated control is uncertain. Secondary MF/CC gains over LocalPlus do not beat the stronger direct nonexperimental-GOA control; CC favors that control. |
| Can the app preserve and explain source content? | Original records, qualifications and native exports are replayed. The archive study recovered 253/308 exact cited WikiPathways revisions, with the remainder unresolved. A separate expert-grounding assessment measures a false-alarm/recall trade-off. |
| Have public curator references actually been applied? | [Yes](evaluations/PUBLIC_GOLD_REFERENCE_RESULTS_20261115.md). Native GO context recovers 44/51 published positive location labels versus captured Pharos's 41/51 across 31 matched proteins (two improve, 29 unchanged). A second OpenCell comparison recovers 31/40 positive categories versus 30/40 among 23 matching proteins, including after HPA/explicit OpenCell-study exclusion. OpenCell is previously used and has cell-context/source-overlap limits. Two exact clinical claim–evidence projections have human-reviewed support. The same-release physical/functional interaction comparison shows a coverage trade-off, with all unmatched cases and source reuse disclosed. |
| Does the model agent establish biological truth or support automatic pruning? | No. The tested source-claim agent trails the published specialist. The app preserves its results without adopting automatic acceptance or biological pruning. |

Fmax is a benchmark function-recovery score, not a graph-accuracy percentage.
The measured outcome can be stated directly: **the retained Pharos-derived
baseline performed worse than the selected contextual predictor on this
declared task**, with positive paired intervals in both primary views. The
baseline is LocalPlus on historical Pharos-represented STRING weights with
dated GO annotations as supervision; it is not an accuracy score for raw
Pharos or proof that the entire corrected graph is biologically more accurate.
The latest comparison seals all 3,300 target forecasts before reference opening
and retains all 18 settings/aspects/views. It reuses ProtBoost and the authors'
CAFA6 context features with qualified adaptations. Its primary residual-positive
populations contain 322 and 319 proteins; the unchanged native bootstrap frames
contain 1,954 and 319. Absolute Fmax across views describes different populations.
The earlier [global-mixture primary test](evaluations/LEARNED_COMBINATION_RESULTS_20261115.md)
remains failed. Public curator labels
are incomplete and can share studies or prior training exposure. Whole-graph
biological accuracy and validated automatic scientific pruning remain open.
A separate [annotation-preservation development check](evaluations/ANNOTATION_PRIOR_DEVELOPMENT_RESULTS_20261115.md)
improves the selected cellular-component model but still trails direct GOA,
and worsens biological process. It is retained without promotion or an
independent-confirmation claim.

A subsequent [fixed current-data refit](evaluations/CURRENT_REFIT_DEVELOPMENT_RESULTS_20261115.md)
did not improve on the original selected model. All six BP cells and stronger
source-union controls are retained as development on consumed labels. Adding
historical memberships back also lowered the direct prior's score in both
views. This informs source maintenance without declaring those historical
records biologically false or changing the application.

The next [cross-fitted graph/frequency fit](evaluations/CROSSFIT_DEVELOPMENT_RESULTS_20261115.md)
completed one fixed training run and all 3,300 forecasts. In the fixed-T0
ontology view, BP Fmax improves from current-curated LocalPlus's 0.18277 to
0.21336 (paired 95% interval for the difference: +0.00409 to +0.05665).
The native-view interval includes zero, and no clear improvement over the
original selected model appears in either view. This is a consumed-reference
development result; the candidate is retained without changing app defaults.

The [sequence-similarity audit](evaluations/CONTEXTUAL_SEQUENCE_SIMILARITY_20261115.md)
also limits any claim of transfer to distant protein families; exact duplicate
removal does not establish that separation.

The [completed whole-workspace assessment](evaluations/WHOLE_GRAPH_ACCURACY_COMPLETION_20261115.md)
also compares all captured Pharos-only, enriched and retained assertion IDs.
It qualifies references for the 180 frozen main cases and 20 separate removed
cases, but admits no independent correctness labels matching the complete
stored claims. The result provides no biological-accuracy percentage or
whole-graph superiority claim. It verifies GO-ID currentness and preserves
all previously matched curator-supported assertions; its logical uncertainty
ranges remain separate from prediction Fmax and confidence intervals.
The subsequent [public-reference assessment](evaluations/public_gold_20261115/report.html)
adds bounded, explicitly matched curator-label tasks; it does not turn those
200 earlier cases into independently adjudicated whole-claim truth labels.
The [native-location source profile](evaluations/NATIVE_LOCATION_WORKSPACE_20261115.md)
puts the source context into the existing answer, source-inspection and export
flow. All 99 target questions were checked, covering 3,309 records and 429
candidate concepts across 94 targets, with explicit empty answers for the other
five. The combined native-evidence profile adds the separately qualified physical
source and is available as its own hosted workspace. The older/default retained
graph and its review decisions are preserved.

The [original fixed full report](evaluations/contextual_combination_20261115/report.html),
[latest development report](evaluations/crossfit_development_20261115/report.html),
[scientific record](evaluations/SCIENTIFIC_RESULTS_20261114.md) and
[earlier mixture results](evaluations/LEARNED_COMBINATION_RESULTS_20261115.md)
retain unfavorable controls, sparse populations and unavailable strata.

## Handoff and remaining release actions

The core application uses the [MIT license](../LICENSE). Optional research
adapters retain their stated licenses, including the
[GPL-3.0-only evaluator adapters](../tools/cafa_reference/NOTICE.md).
Retrieved data retain their own terms. The complete graph includes KEGG material, so public redistribution
of the mixed-source packet has not been cleared. The protected reviewer route,
code-only demonstration and CC0 annex provide distinct access paths.

The intended graph handoff preserves these files together:

- `retained_graph.json`: the resulting graph, retaining abstentions.
- `edge_dispositions.jsonl`: one explicit disposition for each source edge.
- `baseline_packet/source/graph.json`: the complete input workspace before these
  decisions, with surrounding source snapshots and provenance. It may already
  contain source extensions, so this packet baseline is not always Pharos-only.

Final actions are to designate and test the release checkpoint, provide a
permitted graph/source access route, publish the intended open-source
repository/release, and submit the organizer's required final package.
The supplied deadline is **November 17, 2026**; the exact final file/scoring
contract has not been supplied. These local assessments are supporting
evidence, rather than an official organizer score.

The [47a2e5a core software ZIP](evaluations/software_release_cached_review_20261115_summary.json) passed clean Python
construction, answer, actual export and fresh-reopen checks. It is a dated tested
checkpoint; hosting and final publication remain separate actions.

The review branch is now backed up in the existing private repository, with
[draft PR #1](https://github.com/mdomagalski/biograph-steward/pull/1) and a
[private draft release](https://github.com/mdomagalski/biograph-steward/releases/tag/untagged-28e4edec341d2cb39dab).
The latest named review files are the tested core ZIP, public-reference aggregate
ZIP, editable slides and checksums; the earlier prediction-study packet remains
separately available. Draft-release access requires repository write permission;
tracked reports/slides remain available through the branch checkout. Neither
main nor public visibility changed.

The [editable presentation](../output/presentations/BioGraph_Steward_Challenge_Presentation_20261115_v8.pptx)
has six main slides and four technical appendix slides, including the separately
labeled current-data development result and public-reference qualifications. The
[organizer/proposal crosswalk](PROJECT_ALIGNMENT.md) distinguishes delivered
functionality from broader proposal ambitions. The older release archives,
PDFs and hosted receipts remain dated checkpoints rather than interchangeable
copies of the latest local code.

The [closing delivery audit](evaluations/DELIVERY_COMPLETENESS_20261115.md)
maps each expected artifact to its review route. The remaining actions are
teammate feedback, the permitted source-graph handoff and final repository/release
publication and submission.
