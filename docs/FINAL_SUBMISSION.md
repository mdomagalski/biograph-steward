# BioGraph Steward final submission

Working submission and presentation draft, November 12, 2026. The release scope is a usable Pharos evidence workbench with reproducible source records, qualified graph exploration and measured supporting comparisons. The private AWS workbench/Neptune mirror is tested; PaperQA3 is optional.

## Project summary

BioGraph Steward turns a bounded Pharos research question into an inspectable graph, cited answer and source-preserving export. It integrates scoped CIViC and experimental interaction records while retaining identifiers, assay conditions, original references and separate review decisions. Users can explore paths, inspect evidence reuse, compare saved snapshots and export the resulting graph with a complete decision ledger.

Our evaluations distinguish useful task-specific ranking from graph-learning improvement. Native STRING physical scores improved retrospective prioritization with reduced numeric coverage; adding GO or Reactome context did not demonstrate a consistent prediction benefit. Those findings guided the app toward transparent evidence inspection and optional prioritization, with automatic scientific pruning left unvalidated.

The [latest biological assessment](evaluations/BIOLOGICAL_IMPROVEMENT_20261112.md)
compares preselected graph views against OpenCell coassociation calls. At the
same pruning budget, the fixed experimental-support view retains 272/284
strictly mapped positives, versus 269/284 for native confidence; Network
Enhancement also retains 272/284. This is a small positive-retention benefit
on one study, not whole-graph accuracy or a CRC-specific prediction result.
The current processed-data check and original frozen assessment remain
separate. The app exposes both, alongside complete graph/decision exports.

The current CRC source workspace adds 290 SIGNOR regulatory records with
direction, sites, experimental organism and cell/tissue context. Twenty-four
source-bound literature notes show what the cited studies establish and what
remains uncertain. These complement STRING and MAP-IT without automatically
validating assertions or counting repeated records as independent experiments.

## Judge walkthrough

Start with [START_HERE](../START_HERE.md). The core app needs Python 3.10+ and no model account. A fresh checkout includes the synthetic software demonstration. The existing real examples require their saved source packets; local run directories are not included in Git.

For a recorded or source-packet demonstration, use this five-minute sequence:

1. **Ask & explore:** open the saved BRAF question on the 99-protein colorectal-cancer Pharos cohort. Show a bounded question, answer paths and the source/review scope.
2. Inspect the optional physical ordering: all 21 matching proteins remain available, with 14 scored and seven unranked. Explain what the missing values mean.
3. **Evidence & sources:** open `crc_evidence_enriched_20261111` and select **Show EGFR tissue evidence**. Show the 120 source-qualified proximity observations, search for ENG, and inspect its statistics, method, exact identity and archived-Pharos context. Explain why additional source records are not independent experiments. The separate TAS1R2/TAS1R3 example remains available for exact curated-record reuse.
4. **Compare & assess:** show the experimental reference table and its explicit study/mapping limits. Distinguish the historical 3,172-protein assessment from the selected CRC workspace. Open the current processed result and original frozen protocol. Literature searching is optional.
5. **Export:** identify the retained graph, exhaustive decision ledger and complete original source baseline. Explain whole-workspace versus current-answer scope.

Current local examples:

- BRAF question: `crc_civic_final_20261015` / `question_20261027T180832Z_781f7543`.
- Replay-compatible qualified-source workspace: `source_reuse_workbench_20261029`.
- Current graph-and-decision package: `runs/submission_release_20261111/submission_handoff.zip`.

These are source-specific demonstrations. The taste-receptor example is separate from the cancer question. Retain source licenses and attribution when delivering real packets; software MIT licensing does not relicense upstream data. Provide a bounded retrieval recipe when a packet cannot be redistributed.

## Completed biological source enrichment

The [versioned source increment](BIOLOGICAL_SOURCE_UPDATE.md) adds 858 STRING 12.5
functional-association records to the existing CRC workspace, including 238
previously unrepresented pairs and newer records for 620 existing pairs. It also
adds 120 qualified MAP-IT EGFR tissue observations and 119 participant proteins.
All original source records, assertions and the 99 primary Pharos targets remain
unchanged. New records remain candidates with separate provenance.

This produces an inspectable graph with 9,865 entities and 16,695 evidence
records. The source-first EGFR question, statistics, source-group lineage,
historical overlap states and portable source packages demonstrate the result.
This is verified biological evidence enrichment, not independent proof of
scientific accuracy or automatic pruning. The completed MAP-IT pruning endpoint
is unscorable (zero eligible positives); the previous Lambourne superiority gate
remains failed. Both limitations remain part of the delivered assessment.

## Results to present

| Assessment | Result | Interpretation |
|---|---|---|
| OpenCell positive retention, equal graph budget | Fixed primary 272/284; native 269/284; Network Enhancement 272/284 | Small scoped retention benefit over native; NE ties. Same-study processed QC is not another fresh confirmation; no precision/accuracy or CRC-specific claim |
| Native STRING 12.5 ranking, 2,676 eligible measured pairs | AP 0.172827 functional versus 0.190056 physical; numeric coverage 88.3% versus 72.4% | Retrospective source-component prioritization benefit, with a coverage trade-off |
| Native STRING 12.0 control, same consumed panel | AP 0.149732 functional versus 0.161223 physical; coverage 93.4% versus 75.2% | Direction agreed with the selected older-source control; independent validation remains unresolved |
| Matched R-GCN GO-hierarchy comparison | AP 0.719833 versus 0.720135 on 1,751 measured pairs, with mixed seed effects | No consistent hierarchy benefit demonstrated |
| Matched R-GCN Reactome-context comparison | AP 0.717794 versus 0.719605 on the consumed panel, with mixed seed effects | No consistent context benefit demonstrated |
| Source delivery | Fresh IntAct assessment 4/8; separate consumed reliability replay 8/8 | Retrieval/source-preservation results; the replay does not replace the original assessment |

The native ranking result supports the app's optional ordering feature. It does not establish a Steward-versus-Pharos graph-learning gain. Existing measured panels are consumed and will not be reused as unseen tests.

Evidence: [STRING comparison](evaluations/STRING_COMPONENT_COMPARISON_20261027.md), [older-source control](evaluations/STRING_TEMPORAL_CONTROL_20261027.md), [INMC comparison](evaluations/INMC_COMPARISON_20261023.md), [Reactome comparison](evaluations/REACTOME_CONTEXT_COMPARISON_20261026.md), [fresh source assessment](evaluations/INTACT_FRESH_ASSESSMENT_20261027.md), [reliability replay](evaluations/PHAROS_RETRIEVAL_RELIABILITY_20261027.md).

The [November 11 release check](evaluations/release_candidate_20261111_summary.json) passed isolated package installation, service startup, cited questions and current real graph/decision export without a paid service or new source retrieval.

## Six-slide presentation draft

| Slide | Main point | Visual or demonstration |
|---|---|---|
| 1. Make Pharos evidence usable | Researchers need bounded questions, interpretable context and access to original support | One actual workbench screenshot |
| 2. From question to evidence | Scoped retrieval and deterministic tools build the graph; qualified assertions retain source and review history | Question → graph → source → decision → export flow |
| 3. Explore and inspect | Task navigation, bounded multihop paths and guided source inspection expose what an annotation supports | Short BRAF and qualified-assay walkthrough |
| 4. What the measurements show | Native physical prioritization helps this task with lower coverage; matched context enrichment showed no consistent gain | AP and coverage table above |
| 5. Preserve meaning across resources | Identifiers, source lineage, full assay conditions and reuse checks prevent unsupported strengthening or double counting | A source passport and shared-record example |
| 6. Deliverables and limits | MIT software, reproducible graph/source packet, decisions and evaluation artifacts; experimental planning and biological pruning remain bounded gaps | Export contents and concise next scientific step |

A six-slide editable presentation draft now uses current app captures and separate native charts for average precision and numeric coverage. The interpretation examples display labeled IntAct fields, distinct retrieval/source labels and the existing CIViC study level with its full treatment scope. The [interpretation delivery record](evaluations/interpretation_delivery_20261111_summary.json) documents these display changes and their source checks.

The optional NVIDIA Nemotron/NAT integration belongs on slide 2 or in the technical appendix. The current planner is experimental; the primary demonstration uses supported guided tools. Show implemented methods and useful behavior before architecture details.

## Delivery inventory

| Item | Current state | Finish action |
|---|---|---|
| MIT repository and build instructions | Implemented; current source passed the isolated installation/start/export gate | Make the delivered release checkpoint available through GitHub |
| App and demonstration | Working local five-tab workflow; source packets and historical desktop/mobile checks exist | Select the final example, record the walkthrough and provide a portable route for judges |
| Graph and decisions | Current real package exported and verified, including ZIP extraction/replay; original 62 source files unchanged | Include the designated packet; the demonstrated real ledger is all abstentions |
| Standards | Explicit vocabulary references, bounded KGX profile and SSSOM audit | Link the implemented profile and documented conformance limits |
| Scientific assessment | Actual matched learner comparisons and native-score supporting results exist | Present results and denominators together; preserve negative/mixed outcomes |
| Final submission format | Supplied brief and Slack updates guide the handoff; exact final file schema remains unspecified | Follow any later organizer instructions; keep this inventory ready |

The supplied rubric weights usability 40%, accuracy/pruning 30%, explainability 20% and standards 10%. Semi-autonomous construction is allowed. AWS, Neptune and PaperQA3 are not stated prerequisites. See the [current organizer/proposal crosswalk](PROJECT_ALIGNMENT.md).

## Optional no-spend literature illustration

The prepared [support-search assessment](evaluations/support_search_comparator_20261029_summary.json) has five consumed assertions and three distinct author queries. Three standard web-interface searches would cover those distinct prompts; allow at most five submissions including failures. Edison’s published notice describes 10 monthly free credits, regular agents at 1–2 credits and paid API access. The account's displayed allowance and task cost determine whether those searches fit. No paid API execution is required for release.

The existing PubMed/PMC source path and preserved citations remain usable without an Edison account. The available Brev model can optionally summarize retrieved text using existing credits; that would be a separately identified method. Installing another literature framework is outside the finish scope.

Sources: [Edison allowance notice](https://edisonscientific.com/news/we-raised-70m-to-accelerate-science), [PMC developer services](https://pmc.ncbi.nlm.nih.gov/tools/developers/).
