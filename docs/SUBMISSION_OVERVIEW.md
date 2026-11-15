# BioGraph Steward submission overview

BioGraph Steward builds and inspects scoped Pharos evidence graphs. A
researcher chooses a supported question, follows the answer's graph paths to
their original records, and exports the complete workspace with its baseline
and review decisions. Guided execution is the dependable route. Optional
NVIDIA model planning and source-audit agents are implemented and evaluated,
with their limitations retained.

This overview describes the working product and evidence available on
**November 14, 2026, Eastern time**. Research identifiers ending `20261115`
use UTC. The [delivery status](DELIVERY_STATUS_20261115.json) separates the
verified hosted checkpoint, local software, research results and remaining
submission actions. The longer [submission record](FINAL_SUBMISSION.md)
provides the evidence appendix.

## Review the application

The [saved TP53 reviewer example](https://bi-3a117d5e2b3942678dc518fce65ab5d2.ecs.us-east-2.on.aws/?run=source_faithful_workspace_20261113&question=question_20261113T075313Z_1a76b00f&view=ask)
requires a workspace token supplied separately. Reviewers need a browser,
without an AWS account, local tunnel or model server. The shared ingress
allows saved-data inspection and exports; new retrieval, model calls and
review edits are disabled there.

1. In **Ask & explore**, find the written answer and select a TP53–AKT1 path.
   Both proteins connect to the same cited WikiPathways model. This describes
   shared source context, without asserting direct physical binding.
2. Open the **evidence passport**, then **Download cited native GPML**. Locate
   the exact historical model, original record and review state. Distinguish a
   compatible gene-level match from exact protein-form identity.
3. In **Compare & assess**, inspect a saved scientific result and one historical
   function hypothesis. Its neighbor/source contribution explains the model
   score; the score does not accept a biological annotation.
4. In **Export**, download the full workspace and the separate answer ZIP.
   The answer diagram is a selection; the workspace contains the full graph,
   original baseline and every keep/prune/abstain disposition.

Use the [five-minute demonstration](DEMO_SCRIPT.md) for a presentation, or the
[team testing guide](TEAM_REVIEW_GUIDE_20261113.md) to record obstacles and unclear
terms. Independent teammate feedback remains pending.

For a checkout-only route, follow [START_HERE](../START_HERE.md):

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
| Biological source context | CIViC clinical profiles and complete therapy combinations; qualified STRING, MAP-IT and SIGNOR extensions; separately qualified assay examples; native GO and pathway source inspection. Availability depends on the selected workspace and its source attachments. |
| Readable questions and sources | Five task tabs, supported question templates, bounded multihop paths, cited summaries, source versions, original records and unresolved context. |
| Review and maintenance | Versioned assertions, explicit lifecycle states, immutable snapshots, review history and guarded snapshot comparison. Uncertain records stay visible. |
| Export and standards | Retained graph, exhaustive decisions and original baseline/source packet. Stable identifiers, explicit Biolink references, a bounded KGX projection and qualified SSSOM mappings retain documented conformance limits. |
| Local and cloud operation | Dependency-light Python app, Docker/deployment configuration, authenticated AWS reviewer app and private Neptune mirror. Ordinary saved answers use workspace files; the database inspector performs read-only Neptune queries. |

The main retained graph contains **16,687 evidence records across 9,865
entities**. Its full baseline preserves 16,985 records. The 298 exclusions
concern obsolete GO identifiers in a pinned ontology; they are not 298
experimentally disproved relationships. A record count is not a count of
independent experiments. The main Pharos319 capture is frozen at October 14,
2026; later publisher context keeps its own source dates.

## What the measurements support

| Question tested | Result and interpretation |
|---|---|
| Does adding context improve the same graph learner over the original baseline? | Matched R-GCN comparisons are complete, with mixed or negative results against their controls. A consistent advantage on the challenge's central enriched-graph link-prediction task remains unestablished. |
| Can published methods recover later protein-function annotations? | Existing controlled CAFA5 comparisons show bounded secondary method/context gains. The [later temporal mixture comparison](evaluations/LEARNED_COMBINATION_RESULTS_20261115.md) finds a cellular-component mixing gain on 447 proteins: micro-Fmax 0.3342 versus LocalPlus 0.3041 and DeepGO-SE 0.2914. The primary molecular-function learned-weight test fails. |
| Can the app preserve and explain source content? | Original records, qualifications and native exports are replayed. The archive study recovered 253/308 exact cited WikiPathways revisions, with the remainder unresolved. A separate expert-grounding assessment measures a false-alarm/recall trade-off. |
| Does the model agent establish biological truth or support automatic pruning? | No. The tested source-claim agent trails the published specialist. The app preserves its results without adopting automatic acceptance or biological pruning. |

Fmax is a benchmark function-recovery score, not a graph-accuracy percentage.
The cellular-component gain is a secondary result, with conditional paired
intervals. It comes from a 50/50 mixture, which the fitter also selects; it does
not prove an extra advantage from learning weights. Public curator labels
are incomplete and can share studies or prior training exposure. Whole-graph
biological accuracy and validated automatic scientific pruning remain open.
The [scientific record](evaluations/SCIENTIFIC_RESULTS_20261114.md) and
[complete mixture results](evaluations/LEARNED_COMBINATION_RESULTS_20261115.md)
retain unfavorable controls, sparse populations and unavailable strata.

## Handoff and remaining release actions

The software uses the [MIT license](../LICENSE). Retrieved data retain their
own terms. The complete graph includes KEGG material, so public redistribution
of the mixed-source packet has not been cleared. The protected reviewer route,
code-only demonstration and CC0 annex provide distinct access paths.

The intended graph handoff preserves these files together:

- `retained_graph.json`: the resulting graph, retaining abstentions.
- `edge_dispositions.jsonl`: one explicit disposition for each source edge.
- `baseline_packet/source/graph.json`: the complete retrieved baseline, with
  surrounding source snapshots and provenance.

Final actions are to designate and test the release checkpoint, provide a
permitted graph/source access route, publish the intended open-source
repository/release, and submit the organizer's required final package.
The supplied deadline is **November 17, 2026**; the exact final file/scoring
contract has not been supplied. These local assessments are supporting
evidence, rather than an official organizer score.

The [editable presentation](../output/presentations/BioGraph_Steward_Challenge_Presentation_20261115_v2.pptx)
has six main slides and two technical appendix slides. The
[organizer/proposal crosswalk](PROJECT_ALIGNMENT.md) distinguishes delivered
functionality from broader proposal ambitions. The older release archives,
PDFs and hosted receipts remain dated checkpoints rather than interchangeable
copies of the latest local code.
