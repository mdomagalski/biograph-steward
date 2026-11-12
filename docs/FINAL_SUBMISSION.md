# BioGraph Steward final submission

Working submission and presentation draft, November 12, 2026. The release scope is a usable Pharos evidence workbench with reproducible source records, qualified graph exploration and measured supporting comparisons. The private AWS workbench/Neptune mirror is tested; PaperQA3 is optional.

## Project summary

BioGraph Steward turns a bounded Pharos research question into an inspectable graph, cited answer and source-preserving export. It integrates scoped CIViC and experimental interaction records while retaining identifiers, assay conditions, original references and separate review decisions. Users can explore paths, inspect evidence reuse, compare saved snapshots and export the resulting graph with a complete decision ledger.

Our evaluations distinguish useful task-specific ranking from graph-learning improvement. Native STRING physical scores improved retrospective prioritization with reduced numeric coverage; adding GO or Reactome context did not demonstrate a consistent prediction benefit. Those findings guided the app toward transparent evidence inspection and optional prioritization, with automatic scientific pruning left unvalidated.

The [graph-retention assessment](evaluations/BIOLOGICAL_IMPROVEMENT_20261112.md)
compares preselected graph views against OpenCell coassociation calls. At the
same pruning budget, the fixed experimental-support view retains 272/284
strictly mapped positives, versus 269/284 for native confidence; Network
Enhancement also retains 272/284. This is a small positive-retention benefit
on one study, not whole-graph accuracy or a CRC-specific prediction result.
The current processed-data check and original frozen assessment remain
separate. The app exposes both, alongside complete graph/decision exports.

A conditional HCT116 BioPlex comparison retains 247/263 qualified pairs for
the primary, 246/263 for native confidence and 251/263 for Network Enhancement.
The one-pair gain is small; prior-assisted source calls prevent treating it
as independent biological truth. No eligible CRC99 pair exists in this
historical ranking comparison. A separate structure-backed reference is too
small after source/exposure qualification to distinguish the graph views.

The small captured-Tdark subgroup does not share that primary-view gain:
primary and native each retain 12/16 strictly mapped positives, while Network
Enhancement retains 16/16. This post hoc descriptor is not a subgroup winner
selection or proof of general benefit for understudied targets.

A subsequent [published curated-signature comparison](evaluations/CURATED_SIGNATURE_RECOVERY_20261112.md)
increases scored perturbation-target cases from 31 to 39 out of 105 and improves
study-weighted normalized rank from 0.680898 to 0.576408 across 14 evaluable
study groups. The gain is mainly coverage-driven; shared-target ranking is
mixed. This optional offline comparison is a supporting biological result,
not a new default app inference feature, a baseline-versus-enriched GNN gain
or whole-graph scientific accuracy. It preserves a failed initial execution
and labels the corrected reader run as a technical replay after exposure.

The current CRC source workspace adds 290 SIGNOR regulatory records with
direction, sites, experimental organism and cell/tissue context. Twenty-four
source-bound literature notes show what the cited studies establish and what
remains uncertain. These complement STRING and MAP-IT without automatically
validating assertions or counting repeated records as independent experiments.
Four private HCT116 context records additionally distinguish tagged-expression
coassociation from endogenous repair function. They add no graph relationships
and are excluded from public source packets while native-data redistribution
terms remain unverified.

## Judge walkthrough

Start with [START_HERE](../START_HERE.md). The core app needs Python 3.10+ and no model account. A fresh checkout includes the synthetic software demonstration. The existing real examples require their saved source packets; local run directories are not included in Git.

For a recorded or source-packet demonstration, use this five-minute sequence:

1. **Ask & explore:** open the packaged BRAF question on the 99-protein colorectal-cancer Pharos cohort. Show the bounded question, answer paths and source/review scope.
2. Follow one path and its assertion references. Eight of 21 matching proteins are shown under the explicit result limit; the saved answer has 16 assertion references. Remaining matches are not biologically absent. Candidate paths require review.
3. **Evidence & sources:** open **Regulation and experimental context → Inhibitory BRAF phosphorylation**. Inspect phosphate addition at Ser614 separately from reduced protein activity, the reported cell context and original PMID. Other saved regulatory and EGFR tissue passports remain available. Explain why added records are not independent experiments; the presentation's TAS1R2/TAS1R3 reuse example is separate from this cancer workspace.
4. Present the separate experimental results and their explicit study/mapping limits using the slides and repository evaluation reports. Distinguish historical whole-source comparisons from the selected CRC workspace. Optional assessment packets are separate; the portable runtime does not bundle a complete research-run history. Literature searching is optional.
5. **Export:** identify the retained graph, exhaustive decision ledger and complete original source baseline. Explain whole-workspace versus current-answer scope.

Current local examples:

- Packaged BRAF question: `crc_judge_demo` / `question_judge_focus` inside the v3 delivery.
- Earlier physical-priority example: `crc_civic_final_20261015` / `question_20261027T180832Z_781f7543`.
- Replay-compatible qualified-source workspace: `source_reuse_workbench_20261029`.
- Current STRING/MAP-IT/SIGNOR workspace: `crc_biological_workspace_20261112`.
- Optional local/private cell-model context: `crc_context_qualified_20261112`.
- Complete local CRC package: `runs/final_delivery_v3_20261112/biograph_steward_crc_local.zip`.

These are source-specific demonstrations. The taste-receptor example is separate from the cancer question. Retain source licenses and attribution when delivering real packets; software MIT licensing does not relicense upstream data. Provide a bounded retrieval recipe when a packet cannot be redistributed.

The designated full example is now `crc_biological_workspace_20261112`, with
99 primary targets, 9,865 entities, 16,985 evidence records and 16,980 assertions.
The [delivery builder](DELIVERY.md) produces the committed core runtime and a
separate locally verified complete CRC packet, with all-abstain decisions and
the preserved original baseline. The [five-minute script](DEMO_SCRIPT.md) uses
the saved BRAF question and new site/context inspector. The earlier two-protein
ZIP remains an engineering check, not the full final example.

The native graph contains 1,588 KEGG pathway records; blanket redistribution
permission is not established. The full packet remains local, including for
judge access until applicable permissions are resolved. The software-only
archive and bounded retrieval route are independently usable. Final repository
publication is intended for submission; local run IDs and commits alone do not
provide external access.

## Completed biological source enrichment

The [versioned source increment](BIOLOGICAL_SOURCE_UPDATE.md) adds 858 STRING 12.5
functional-association records to the existing CRC workspace, including 238
previously unrepresented pairs and newer records for 620 existing pairs. It also
adds 120 qualified MAP-IT EGFR tissue observations and 119 participant proteins.
All original source records, assertions and the 99 primary Pharos targets remain
unchanged. New records remain candidates with separate provenance.

The STRING/MAP-IT increment produced 9,865 entities and 16,695 evidence
records. The current SIGNOR-enriched workspace has the same 9,865 entities and
16,985 evidence records, with all original Pharos records unchanged. The
source-first EGFR question, regulatory passports, statistics, source-group lineage,
historical overlap states and portable source packages demonstrate the result.
This is verified biological evidence enrichment, not independent proof of
scientific accuracy or automatic pruning. The completed MAP-IT pruning endpoint
is unscorable (zero eligible positives); the previous Lambourne superiority gate
remains failed. Both limitations remain part of the delivered assessment.

## Results to present

| Assessment | Result | Interpretation |
|---|---|---|
| OpenCell positive retention, equal graph budget | Fixed primary 272/284; native 269/284; Network Enhancement 272/284 | Small scoped retention benefit over native; NE ties. Same-study processed QC is not another fresh confirmation; no precision/accuracy or CRC-specific claim |
| HCT116 BioPlex positive retention, equal safeguarded budget | Fixed primary 247/263; native 246/263; Network Enhancement 251/263 | Tiny conditional gain over native; NE retains more. Prior-assisted source calls and uncertain historical training versions limit independence |
| Structure-backed reference qualification | 13 eligible pairs; four outside the original exposure boundary, from one paper; all graph views tie | Below the fixed reporting floor; unscorable for improvement |
| Native STRING 12.5 ranking, 2,676 eligible measured pairs | AP 0.172827 functional versus 0.190056 physical; numeric coverage 88.3% versus 72.4% | Retrospective source-component prioritization benefit, with a coverage trade-off |
| Native STRING 12.0 control, same consumed panel | AP 0.149732 functional versus 0.161223 physical; coverage 93.4% versus 75.2% | Direction agreed with the selected older-source control; independent validation remains unresolved |
| Matched R-GCN GO-hierarchy comparison | AP 0.719833 versus 0.720135 on 1,751 measured pairs, with mixed seed effects | No consistent hierarchy benefit demonstrated |
| Matched R-GCN Reactome-context comparison | AP 0.717794 versus 0.719605 on the consumed panel, with mixed seed effects | No consistent context benefit demonstrated |
| Published curated-signature source choice | 31/105 → 39/105 scored target cases; study-weighted rank 0.680898 → 0.576408 | Positive coverage-driven perturbation recovery, mixed shared-target ranking; source reuse/label limitations and technical-replay boundary remain explicit |
| Source delivery | Fresh IntAct assessment 4/8; separate consumed reliability replay 8/8 | Retrieval/source-preservation results; the replay does not replace the original assessment |

The OpenCell table describes the original fixed views. The later connectivity
safeguard preserves all 18 original components at the same graph budget;
primary retention is unchanged, while the native control becomes 268/284.
That consumed diagnostic is separate from the original result. The native
ranking result supports the app's optional ordering feature. These results do
not establish a Steward-versus-Pharos graph-learning gain. Existing measured
panels are consumed and will not be reused as unseen tests.

Evidence: [STRING comparison](evaluations/STRING_COMPONENT_COMPARISON_20261027.md), [older-source control](evaluations/STRING_TEMPORAL_CONTROL_20261027.md), [INMC comparison](evaluations/INMC_COMPARISON_20261023.md), [Reactome comparison](evaluations/REACTOME_CONTEXT_COMPARISON_20261026.md), [fresh source assessment](evaluations/INTACT_FRESH_ASSESSMENT_20261027.md), [reliability replay](evaluations/PHAROS_RETRIEVAL_RELIABILITY_20261027.md).

The [November 11 release check](evaluations/release_candidate_20261111_summary.json) passed isolated package installation, service startup, cited questions and current real graph/decision export without a paid service or new source retrieval.
The [full November 12 delivery](evaluations/DELIVERY_READINESS_20261112.md) now
also replays the complete CRC graph, saved cited answer and new site/context
endpoint from the actual extracted archive, with the full original baseline
and exhaustive abstention ledger. Separate software-only startup succeeds
without repository imports or optional dependencies.

## Six-slide presentation draft

| Slide | Main point | Visual or demonstration |
|---|---|---|
| 1. BioGraph Steward | Pharos evidence for a scoped research question | Title and challenge scope |
| 2. A bounded question and an inspectable answer | Guided choices lead to cited saved paths; scored and unranked matches remain visible | Actual BRAF answer screenshot |
| 3. Site and study context | Phosphate addition and reduced protein activity can coexist in one source record | Current BRAF S614 site/context capture |
| 4. Shared records | Exact source reuse remains visible; another database is not another experiment | IntAct/STRING record and unresolved counterpart |
| 5. Bounded target recovery | Author-curated signatures improve coverage and study-weighted rank; common-target ranking remains mixed | Editable charts, evaluated denominator and limits |
| 6. Delivery and scientific boundaries | Complete CRC workspace, decisions and original baseline; separate software/data permissions | Export screenshot, counts and remaining limits |

A six-slide editable presentation now includes the current site/context capture,
exact source-reuse example, native charts for scored target cases and normalized
rank, complete CRC delivery counts and the source-permission boundary. Speaker
notes preserve the evaluated denominator, mixed shared-target outcome,
technical-replay status and negative same-learner findings. Earlier presentation
and [interpretation checks](evaluations/interpretation_delivery_20261111_summary.json)
remain preserved.

The optional NVIDIA Nemotron/NAT integration belongs on slide 2 or in the technical appendix. The current planner is experimental; the primary demonstration uses supported guided tools. Show implemented methods and useful behavior before architecture details.

## Delivery inventory

| Item | Current state | Finish action |
|---|---|---|
| MIT repository and build instructions | Implemented; current source passed the isolated installation/start/export gate | Make the delivered release checkpoint available through GitHub |
| App and demonstration | Working five-tab flow, full CRC example, site/context desktop/mobile checks, portable builder and five-minute script | Resolve real-source sharing permissions and deliver the chosen route; independent intended-user assessment remains open |
| Graph and decisions | Current CRC packet preserves its original sources and has an all-abstention ledger. Separate historical primary/native pruned packages have complete source baselines and exhaustive keep/prune/abstain ledgers; safeguarded exports preserve all original components | Deliver clearly named source-workspace and experimental-pruning packages with their different scopes |
| Standards | Explicit vocabulary references, bounded KGX profile and SSSOM audit | Link the implemented profile and documented conformance limits |
| Scientific assessment | Retention comparisons, matched learner controls, source-qualified context and a positive curated-signature recovery comparison exist; whole-graph biological accuracy and CRC-specific pruning benefit remain unproven | Present source-choice utility separately from graph-learning/pruning benefit, with comparators, denominators and negative/mixed outcomes |
| Final submission format | Supplied brief and Slack updates guide the handoff; exact final file schema remains unspecified | Follow any later organizer instructions; keep this inventory ready |

The supplied rubric weights usability 40%, accuracy/pruning 30%, explainability 20% and standards 10%. Semi-autonomous construction is allowed. AWS, Neptune and PaperQA3 are not stated prerequisites. See the [current organizer/proposal crosswalk](PROJECT_ALIGNMENT.md).

## Optional no-spend literature illustration

The prepared [support-search assessment](evaluations/support_search_comparator_20261029_summary.json) has five consumed assertions and three distinct author queries. Three standard web-interface searches would cover those distinct prompts; allow at most five submissions including failures. Edison’s published notice describes 10 monthly free credits, regular agents at 1–2 credits and paid API access. The account's displayed allowance and task cost determine whether those searches fit. No paid API execution is required for release.

The existing PubMed/PMC source path and preserved citations remain usable without an Edison account. The available Brev model can optionally summarize retrieved text using existing credits; that would be a separately identified method. Installing another literature framework is outside the finish scope.

Sources: [Edison allowance notice](https://edisonscientific.com/news/we-raised-70m-to-accelerate-science), [PMC developer services](https://pmc.ncbi.nlm.nih.gov/tools/developers/).
