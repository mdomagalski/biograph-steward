# BioGraph Steward final submission

Working submission and presentation draft, updated November 14, 2026. The accepted AWS runtime is `a6a05ff`, with the source-faithful workspace, native GO inspector and a separate historical function inspector containing six saved queries and 36 traceable hypotheses. The [current scientific results](evaluations/SCIENTIFIC_RESULTS_20261114.md) report bounded function-recovery gains and all negative controls. The new aggregate publication is `scientific_assessment_reference_20261114`; it is installed and its protected API, catalogue, source downloads and report passed acceptance. Earlier PDFs, slide decks and hosting receipts remain dated checkpoints until replaced.

## Project summary

BioGraph Steward turns a bounded Pharos research question into an inspectable
graph, cited answer and source-preserving export. Users can explore shared
pathway context, inspect experimental and curator records, see evidence reuse,
and export the graph with its complete decision ledger. Exact identifiers,
whole molecular profiles and therapy sets, source conditions and local review
remain distinct throughout.

The [source delivery summary](evaluations/SCIENTIFIC_DELIVERY_20261113.md)
describes the existing AWS workbench and verified Neptune mirror:
**16,687 retained evidence records across 99 primary protein targets**. The
original 16,985 records, reviews and keep/prune/abstain ledger remain preserved.
Native archives recovered **253/308 cited WikiPathways revisions**, including
15 of the 20 most frequent source versions. The app joins proteins through
those cited models and exposes their native source passports. Unresolved
memberships stay visible. The 298 exclusions concern obsolete GO identifiers
in the pinned July 2026 ontology, not experimentally disproved relationships.
Current CIViC profile and Reactome event links guide users to curator and
mechanistic context without treating live lookup results as historical proof
or independent evidence.

The [November 14 controlled comparison](evaluations/SCIENTIFIC_RESULTS_20261114.md)
measures recovery of later CAFA5 curator annotations using historical inputs.
On 833 eligible biological-process proteins, original-graph LocalPlus micro-Fmax
is **0.1218**, published GeneMANIA+ reaches **0.1299**, and the fuller historical
strict-context LocalPlus profile reaches **0.1353**. The two positive contrasts
are secondary, with paired intervals; the original primary FSS candidate was
negative. A separate partially known (PK) protein cohort supports bounded transfer;
no-knowledge (NK) and limited-knowledge (LK) tasks do not reliably beat their
strongest fixed controls. Fixed pruning
has no reliable recovery benefit. Fmax is not an accuracy percentage, and these
results do not establish whole-graph truth or superiority over complete Pharos.
The tested claim-checking agent remains inferior to the published specialist;
its judgments are not an automatic acceptance or pruning policy.

The hosted [native GO inspector](NATIVE_GO_CONTEXT_WORKBENCH.md) also exposes
preserved relations, NOT qualifiers, references, forms and context alternatives,
with separately labeled saved official QC. It makes known source-quality issues
inspectable without changing the Pharos graph or assuming historical row identity.
The approved 12-file source/QC attachment remains separate from the code-only
software and is absent from fresh installations.

Credible public references provide bounded **support coverage**, not a precision
estimate: compatible experimental GO curations cover 373/4,078 original GO
assertions, and a published CRC genomic cohort supports 32/100 disease
assertions under the declared scopes. All identified support survives. Two
accepted CIViC expert Assertions are preserved separately, with no exact match
to the 41 original reported-response contexts. Missing matches remain UNKNOWN;
independent whole-graph scientific accuracy is not estimable from these labels.
See the [source-faithful assessment](evaluations/SOURCE_FAITHFUL_WORKSPACE_20261113.md).

A separate [expert-labeled source-grounding evaluation](evaluations/EXPERT_GROUNDING_20261113.md)
uses published INDRA curations and native Gilda/Adeft. On 678 eligible reserved
cases, publication context reduces false alarms from 25 to 18 while detecting
26 rather than 31 grounding errors. The tracked reproduction commands recovered
all 4,294 prepared source cases and their split exactly. This measures
source-identity error triage, not correction of the Pharos graph, exact protein-form validation or a new
automatic pruning policy. Full denominators, outside-endpoint cases and
abstentions remain explicit.

The earlier aggregate publication remains available in the private AWS app as
`scientific_assessment_delivery_20261113` (`09e50f8e…`), with its API and catalogue
verified after a real service restart. Its other component is the earlier
92-query/3,968-pair exploratory comparison. The negative 128-gene/7,648-pair
transfer below remains separately reported and is not replaced by that display.

Biological comparisons remain explicit. Matched R-GCN source-context tests did
not beat count and degree controls reliably. An exploratory inverse-degree
context result on consumed coessentiality data was followed by a
[fixed transfer to 128 new genes and 7,648 nonsyntenic pairs](evaluations/PROSPECTIVE_GENE_TRANSFER_20261113.md).
**The transfer was negative:** neither RA nor binary shared context beat
baseline and all 40 controls at any N=1–10. Absolute historical affinity was
lower throughout. No RA ranking, automatic biological pruning or new method
was promoted after this result. That earlier transfer remains negative. The
newer CAFA5 comparisons above measure a separate function-recovery task with
bounded positive findings.

Earlier [retention comparisons](evaluations/BIOLOGICAL_IMPROVEMENT_20261112.md),
[conditional HCT116 assessment](evaluations/HCT116_EXTERNAL_COMPARISON_20261112.md),
[curated-signature recovery](evaluations/CURATED_SIGNATURE_RECOVERY_20261112.md),
[whole-workspace audit](evaluations/WHOLE_GRAPH_SAMPLE_AUDIT_20261112.md) and
[original version-projection assessment](evaluations/WIKIPATHWAYS_VERSION_NORMALIZATION_20261112.md)
remain separate bounded results. Their metrics and limits are retained below
and in the linked experiment ledger; they do not replace the earlier negative
coessentiality transfer or the new CAFA5 function-recovery assessment, and do
not establish whole-graph accuracy.

## Judge walkthrough

Start with [START_HERE](../START_HERE.md). The core app needs Python 3.10+ and no model account. A fresh checkout includes the synthetic software demonstration. The existing real examples require their saved source packets; local run directories are not included in Git.

For a checkout-only real-source illustration, open the
[CC0 Reactome annex](../examples/reactome_context_20261113/README.md).
It supplies exact native records and an offline inspection page. It is
current publisher context, separate from the frozen Pharos baseline and
independent scientific validation.

The current hosted example is `source_faithful_workspace_20261113`, running
accepted `a6a05ff` with saved question `question_20261113T075313Z_1a76b00f`.
Acceptance preserved its graph/question/source bytes and authentication, replayed
the native GO cases, and verified the separate six function queries/36 notes.
Earlier Neptune parity and scoped recovery remain separately recorded checks.
Use the [updated five-minute script](DEMO_SCRIPT.md):

1. **Ask & explore:** open the native-supported TP53 question, with eight
   results and two paths per protein. State the exact frozen Pharos319 scope.
2. **Graph and answer:** follow TP53 → cited WikiPathways model ← AKT1.
   Shared source context is not direct protein binding or a new disease mechanism.
3. **Sources:** open the exact archived GPML, distinguish gene-level compatibility
   from exact protein-form identity, and inspect the preserved review state.
   The clinical source guide separately preserves complete therapy/profile context.
   The optional GO inspector separates original native qualifiers from recorded
   normalization/context warnings; none becomes a historical correction or truth label.
4. **Compare & assess:** open the latest scientific publication and explain
   the CAFA5 gain, comparator, paired uncertainty and secondary status. Retain
   the negative primary FSS result, NK/LK control limits, pruning result and
   inferior agent arm. Inspect one saved historical function hypothesis through
   its neighbor/source pair; it remains an uncalibrated prediction, not acceptance.
5. **Export:** identify the retained graph, exhaustive decision ledger and full
   original baseline. Explain whole-workspace versus current-answer scope.

The earlier portable BRAF-site and taste-receptor reuse examples remain
supplementary. They must retain their original graph, assay and study scope;
they are not the current TP53 answer or independent biological validation.

Current and preserved local examples:

- Current source-faithful AWS/Neptune workspace: `source_faithful_workspace_20261113`.
- Packaged BRAF question: `crc_judge_demo` / `question_judge_focus` inside the v3 delivery.
- Earlier physical-priority example: `crc_civic_final_20261015` / `question_20261027T180832Z_781f7543`.
- Replay-compatible qualified-source workspace: `source_reuse_workbench_20261029`.
- Preserved original STRING/MAP-IT/SIGNOR workspace: `crc_biological_workspace_20261112`.
- Optional local/private cell-model context: `crc_context_qualified_20261112`.
- Complete local CRC package: `runs/final_delivery_v3_20261112/biograph_steward_crc_local.zip`.

These are source-specific demonstrations. The taste-receptor example is separate from the cancer question. Retain source licenses and attribution when delivering real packets; software MIT licensing does not relicense upstream data. Provide a bounded retrieval recipe when a packet cannot be redistributed.

The current full example is `source_faithful_workspace_20261113`, with 99
primary targets and 16,687 retained evidence records. Its complete source package
preserves the original graph and exhaustive decisions. The earlier
`crc_biological_workspace_20261112` baseline has 9,865 entities, 16,985 evidence
records and 16,980 assertions. Its [portable v3 delivery](DELIVERY.md), original
all-abstain ledger and BRAF demonstration remain available
under their original scope. The two-protein ZIP remains an engineering check.

The source graph includes 1,588 KEGG pathway records; blanket redistribution
permission is not established. Complete data remain in authorized private
storage, including the hosted workspace; judge access or packet redistribution
requires a permitted delivery route. The software-only archive and bounded
retrieval route remain independently usable. Final repository publication is
intended for submission; local run IDs and commits alone do not provide
external access.

The [successful isolated recovery](evaluations/aws_isolated_recovery_20261113_summary.json)
replayed the existing backup's graph, bound assessment and saved question,
including exact answer/export hashes. Live files, configuration and container
identity stayed unchanged; the post-check service returned HTTP 200. This is
checkpoint recovery, not full VM/runtime restoration or recovery of the later
grounding publication and current software ZIP. The
[delivery index](releases/20261113/README.md) keeps these versions and artifacts
separate. The other research-archive S3 transfer remains unapproved.
The November 13 updates were outside that earlier recovery scope. A fresh
November 14 native backup and isolated read-only replay now cover the accepted
`a6a05ff` app checkpoint: original source workspace and eight-answer question,
final scientific assessment (including grounding), all six historical function
queries/36 notes, and the 12-file native GO attachment. Live data, configuration
and container identity stayed unchanged. This is selected data/checkpoint replay,
not full VM, credential or Neptune restoration. See the
[current delivery receipt](evaluations/scientific_hosted_delivery_20261114_summary.json).
The source packet remains separate from the code-only archive.

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
| Expert-labeled source-grounding component, 678 eligible reserved cases | Lexical: 31 correct error flags / 25 false alarms; publication context: 26 / 18; both leave 103 unresolved | Source-identity review trade-off; published curator-relative labels, not whole-graph accuracy or automatic corrections |
| Current Wiki-context R-GCN comparison, 1,751 measured pairs | Historical AP 0.71027 versus normalized 0.70978; count control 0.72097 and degree control 0.71133 | Consumed-reference comparison; no reliable predictive gain over controls |
| Fixed new-gene transfer, 128 queries / 7,648 nonsyntenic pairs | Neither RA nor binary shared context beats baseline and all 40 controls at any N=1–10; historical context reaches 26 queries, with 102 zero-context queries retained | Negative transfer within the same published reference; no accuracy estimate or automatic biological pruning |
| OpenCell positive retention, equal graph budget | Fixed primary 272/284; native 269/284; Network Enhancement 272/284 | Small scoped retention benefit over native; NE ties. Same-study processed QC is not another fresh confirmation; no precision/accuracy or CRC-specific claim |
| HCT116 BioPlex positive retention, equal safeguarded budget | Fixed primary 247/263; native 246/263; Network Enhancement 251/263 | Tiny conditional gain over native; NE retains more. Prior-assisted source calls and uncertain historical training versions limit independence |
| Structure-backed reference qualification | 13 eligible pairs; four outside the original exposure boundary, from one paper; all graph views tie | Below the fixed reporting floor; unscorable for improvement |
| Native STRING 12.5 ranking, 2,676 eligible measured pairs | AP 0.172827 functional versus 0.190056 physical; numeric coverage 88.3% versus 72.4% | Retrospective source-component prioritization benefit, with a coverage trade-off |
| Native STRING 12.0 control, same consumed panel | AP 0.149732 functional versus 0.161223 physical; coverage 93.4% versus 75.2% | Direction agreed with the selected older-source control; independent validation remains unresolved |
| Matched R-GCN GO-hierarchy comparison | AP 0.719833 versus 0.720135 on 1,751 measured pairs, with mixed seed effects | No consistent hierarchy benefit demonstrated |
| Matched R-GCN Reactome-context comparison | AP 0.717794 versus 0.719605 on the consumed panel, with mixed seed effects | No consistent context benefit demonstrated |
| Published curated-signature source choice | 31/105 → 39/105 scored target cases; study-weighted rank 0.680898 → 0.576408 | Positive coverage-driven perturbation recovery, mixed shared-target ranking; source reuse/label limitations and technical-replay boundary remain explicit |
| Published native GO quality checks | 15,888 records; nine relation repairs and 49 alternative-ID normalizations; zero detected taxon violations | Separate normalized source derivative; 13 extension-context review cases, including four citation/context discrepancies. [Executed assessment](evaluations/SCIENTIFIC_LIMIT_RESOLUTION_20261112.md); no whole-graph accuracy or automatic biological pruning claim |
| Source delivery | Fresh IntAct assessment 4/8; separate consumed reliability replay 8/8 | Retrieval/source-preservation results; the replay does not replace the original assessment |

The historical HCT116 comparison has no eligible CRC99 pair; it does not
validate this scoped workspace. The curated-signature result spans 14
evaluable study groups and remains mainly coverage-driven, with mixed
common-target ranking and its technical replay after exposure disclosed.

The original captured-Tdark descriptor remains unchanged: primary and native
each retain 12/16 mapped positives, versus 16/16 for Network Enhancement. This
post hoc subgroup is not a selection rule or general benefit for understudied
targets.

The OpenCell table describes the original fixed views. The later connectivity
safeguard preserves all 18 original components at the same graph budget;
primary retention is unchanged, while the native control becomes 268/284.
That consumed diagnostic is separate from the original result. The native
ranking result supports the app's optional ordering feature. These results do
not establish a Steward-versus-Pharos graph-learning gain. Existing measured
panels are consumed and will not be reused as unseen tests.

Evidence: [current delivery](evaluations/SCIENTIFIC_DELIVERY_20261113.md), [fixed new-gene transfer](evaluations/PROSPECTIVE_GENE_TRANSFER_20261113.md), [STRING comparison](evaluations/STRING_COMPONENT_COMPARISON_20261027.md), [older-source control](evaluations/STRING_TEMPORAL_CONTROL_20261027.md), [INMC comparison](evaluations/INMC_COMPARISON_20261023.md), [Reactome comparison](evaluations/REACTOME_CONTEXT_COMPARISON_20261026.md), [fresh source assessment](evaluations/INTACT_FRESH_ASSESSMENT_20261027.md), [reliability replay](evaluations/PHAROS_RETRIEVAL_RELIABILITY_20261027.md).

The [November 11 release check](evaluations/release_candidate_20261111_summary.json) passed isolated package installation, service startup, cited questions and current real graph/decision export without a paid service or new source retrieval.
The [full November 12 delivery](evaluations/DELIVERY_READINESS_20261112.md) now
also replays the complete CRC graph, saved cited answer and new site/context
endpoint from the actual extracted archive, with the full original baseline
and exhaustive abstention ledger. Separate software-only startup succeeds
without repository imports or optional dependencies.

## Six-slide presentation draft

| Slide | Main point | Visual or demonstration |
|---|---|---|
| 1. BioGraph Steward | A source-traceable Pharos research workspace | Title, scoped question and software workflow |
| 2. The corrected graph in actual use | 99 proteins; 16,687 retained records with complete baseline/decisions | [Hosted TP53 graph](images/hosted_source_graph_20261113.png) |
| 3. Verify what the source actually encodes | 253/308 exact historical revisions; gene-level and protein-level support differ | [Archived source passport](images/hosted_source_passport_20261113.png) |
| 4. Inspect curator and biological context | Preserve whole therapy combinations and native pathway roles; do not double-count sources | [Clinical source guide](images/hosted_clinical_source_guide_20261113.png) and [Reactome guide](images/hosted_reactome_source_guide_20261113.png) |
| 5. Measure function recovery | Secondary CAFA5 method/context gains, with negative primary, pruning and transfer controls retained | [Current controlled results and figure](evaluations/SCIENTIFIC_RESULTS_20261114.md) |
| 6. Delivery and scientific boundaries | Working local/private-cloud app, portable software, complete decisions; whole-graph accuracy remains open | Actual export, [assessment](images/hosted_scientific_assessment_20261113.png) and source-permission boundary |

This is the current **slide revision plan**, with actual new captures and a
complete scientific figure ready for use. The existing editable six-slide deck
is the earlier November 12 presentation; it has not yet been regenerated with
the November 14 results. Its previous site/context, source-reuse and target
recovery material remains preserved. Update that artifact before recording or
submitting it; the current source-faithful report and complete November 14
comparison take precedence over the earlier deck's delivery counts and results emphasis.

The [dated review PDF](../output/pdf/BioGraph_Steward_Final_Review_20261113.pdf)
is a separate exportable presentation packet. Its 153,681-byte version predates
the hosted update and still names the earlier hosted runtime. Preserve it as
that checkpoint and use the hosted receipt for current status. It has not been
regenerated, and its existence does not update the older editable six-slide deck.

The optional NVIDIA Nemotron/pinned NAT integration belongs in the technical
appendix. The planner is experimental; the primary demonstration uses supported
guided tools. The [NVIDIA status](NVIDIA_INTEGRATION_STATUS_20261113.md) records
the upstream lifecycle change and the qualified decision to defer NemoClaw.
Show implemented methods and useful behavior before architecture details.

## Delivery inventory

| Item | Current state | Finish action |
|---|---|---|
| MIT repository and build instructions | Implemented; current code is on the private review branch and the current software ZIP passes clean extracted startup/question/export/restart checks | Freeze the final reviewed checkpoint and carry out the public repository/release handoff |
| App and demonstration | Accepted hosted `a6a05ff` preserves TP53/native exports and adds the separate six-query/36-hypothesis function inspector; native GO, five-tab flow, synthetic checkout and CC0 annex remain available | Gather weekend team feedback for Monday, fix observed interpretation/access issues, and verify the permitted judge access route; independent intended-user assessment remains open |
| Graph and decisions | Current AWS/Neptune workspace retains 16,687 records across 99 primary targets, with its original baseline and complete decisions preserved; 298 obsolete-GO-ID exclusions are source qualifications. Earlier all-abstain and experimental-pruning packages remain separate | Deliver clearly named current workspace and historical comparison packages under their source terms |
| Standards | Explicit vocabulary references, bounded KGX profile and SSSOM audit | Link the implemented profile and documented conformance limits |
| Scientific assessment | Public CAFA5 reference shows secondary method/context PK gains and bounded additional-protein transfer; NK/LK strongest controls are not reliably beaten, pruning has no reliable benefit, and the tested agent trails the published specialist. Earlier negative results remain | Present complete denominators, uncertainty, source/time boundaries and macro/fixed-cutoff trade-offs; whole-graph truth and automatic biological pruning remain open |
| Preservation | Existing private checkpoint passed isolated graph/assessment/question recovery; live service and data remained unchanged | Keep scope/version receipts with the handoff; full VM recovery and the separate unapproved research-archive transfer are not completed by that check |
| Final submission format | Supplied brief and Slack updates guide the handoff; exact final file schema remains unspecified | Follow any later organizer instructions; keep this inventory ready |

The supplied rubric weights usability 40%, accuracy/pruning 30%, explainability 20% and standards 10%. Semi-autonomous construction is allowed. AWS, Neptune and PaperQA3 are not stated prerequisites. See the [current organizer/proposal crosswalk](PROJECT_ALIGNMENT.md).

Brev work for this delivery is finished; its instance and model server are not
needed for review. Keep the existing AWS reviewer app and private Neptune
available for the team. No new cloud service or NemoClaw installation is a submission dependency. This
guidance does not report current account billing or credit consumption.

## Optional no-spend literature illustration

The prepared [support-search assessment](evaluations/support_search_comparator_20261029_summary.json) has five consumed assertions and three distinct author queries. Three standard web-interface searches would cover those distinct prompts; allow at most five submissions including failures. Edison’s published notice describes 10 monthly free credits, regular agents at 1–2 credits and paid API access. The account's displayed allowance and task cost determine whether those searches fit. No paid API execution is required for release.

The existing PubMed/PMC source path and preserved citations remain usable without an Edison account. The available Brev model can optionally summarize retrieved text using existing credits; that would be a separately identified method. Installing another literature framework is outside the finish scope.

Sources: [Edison allowance notice](https://edisonscientific.com/news/we-raised-70m-to-accelerate-science), [PMC developer services](https://pmc.ncbi.nlm.nih.gov/tools/developers/).
