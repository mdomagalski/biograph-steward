# BioGraph Steward

BioGraph Steward is a source-traceable biomedical evidence workbench built around **Pharos** and bounded **CIViC** evidence. Its current product flow is:

```text
Choose an exact disease or protein cohort → retrieve a scoped graph → ask a guided question
→ inspect the cited answer and source context → review and export
```

See the [November 13 delivery and scientific results](docs/evaluations/SCIENTIFIC_DELIVERY_20261113.md), [submission and presentation draft](docs/FINAL_SUBMISSION.md) and [completion scope](docs/BUILD_PLAN.md). The core demonstration requires no paid literature service or GPU.

The [portable delivery guide](docs/DELIVERY.md) separates the software-only
runtime from the complete local CRC source/graph/decision package. Follow the
[five-minute demonstration](docs/DEMO_SCRIPT.md). Real source redistribution
remains subject to upstream terms; a verified ZIP does not clear those rights.

The [source-faithful workspace](docs/evaluations/SOURCE_FAITHFUL_WORKSPACE_20261113.md)
is deployed in the private AWS workbench and Neptune: **16,687 retained evidence
records across 99 primary protein targets**, with the original graph, reviews
and complete decision ledger preserved. Native archives recovered **253/308
cited WikiPathways revisions**, including 15 of the 20 most frequent source
versions. Guided protein → cited model ← protein questions expose those native
records and retain unresolved context. The 298 excluded records have obsolete
GO identifiers in the pinned July 2026 ontology; they are not experimentally
disproved relationships. Current CIViC profile and Reactome event lookups help
users inspect curator context without adding independent evidence or changing
local review.

The **Compare & assess** tab separates native-source verification, experimental
GO curation, published CRC cohort support, CIViC expert conclusions and fixed
prediction comparisons. Compatible records cover 373/4,078 original GO
assertions and 32/100 disease assertions, all retained. These are positive-support
coverage measurements, not whole-graph precision. Current-release and historical
pathway-context filters showed **no reliable R-GCN improvement over count and
degree controls**. Original graphs, UNKNOWNs and negative results are preserved.

An earlier [inverse-degree context assessment](docs/evaluations/RESOURCE_ALLOCATION_CONTEXT_20261113.md)
showed exploratory relative concentration on consumed pan-cancer data, usually
with lower absolute affinity. The subsequent **fixed transfer to 128 new genes
and 7,648 nonsyntenic pairs was negative**: neither RA nor binary shared context
beat baseline and all 40 controls at any N=1–10. See the
[complete transfer result](docs/evaluations/PROSPECTIVE_GENE_TRANSFER_20261113.md).
No RA ranking or automatic biological pruning was promoted to the app; a
transferable predictive gain and independent whole-graph accuracy remain unproved.

Earlier bounded results remain in the [biological assessment](docs/evaluations/BIOLOGICAL_IMPROVEMENT_20261112.md),
[source-qualification comparison](docs/evaluations/SCIENTIFIC_ACCURACY_ROUND2_20261112.md)
and [curated-signature assessment](docs/evaluations/CURATED_SIGNATURE_RECOVERY_20261112.md).
Those source-choice and coverage findings are separate from the current
workspace and from whole-graph biological accuracy.

## Run the workbench

Python 3.10 or newer; the core app requires no third-party packages, model, API key or cloud account.

```sh
python3 app.py
```

Open `http://127.0.0.1:8765/`. A fresh checkout includes an explicitly synthetic demonstration; real source snapshots are retrieved separately and are not bundled. Start with [the walkthrough](START_HERE.md).

For verification, [core and scientific test instructions](docs/TESTING.md)
separate ordinary app portability from the pinned optional evaluation runtime.
The application itself keeps its empty dependency list.

The workbench now separates **Data & saved work**, **Ask & explore**, **Evidence & sources**, **Compare & assess**, and **Export**. Switching tasks keeps the current graph and form selections. Existing saved question links still open their answer.

In **Ask & explore**, bounded path exploration follows up to three saved relationships, respecting direction and explicit symmetry. Each step retains its conditions, source evidence and review state; candidate paths are not promoted to accepted evidence. **Evidence & sources** provides guided source inspection for Pharos, CIViC and assay records, with original references when supplied and explicit missing-context/reuse limits. Both features read the saved workspace without retrieving sources or calling a model.

The **Compare & assess** tab opens saved scientific assessments with explicit
reference units, unknowns, controls and source receipts. It can also open
saved OptimusKG support-search preparations. The five-case development assessment shows three distinct endpoint queries: different qualified claims can produce the same upstream search. This evaluates method fit, not scientific accuracy. Actual PaperQA3 execution requires separate Edison access and a current cost check; Brev is not required for preparation or inspection.


The [clean-install real-data check](docs/evaluations/CLEAN_INSTALL_REAL_DEMO_20261026.md) now verifies a fresh local clone and installed wheel using an existing two-protein source packet. The installed app generates a cited answer, displays the separate assay context, downloads the complete graph/decision package and reopens its recovered source with identical citations. Reproduction requires the authorized real-data input separately; this is automated delivery verification, not independent user or biological validation.

## Current capabilities

- [Whole-workspace evidence audit](docs/evaluations/WHOLE_GRAPH_SAMPLE_AUDIT_20261112.md):
  a frozen 180-assertion probability sample spans all nine source families.
  Exact source fidelity, examined evidence and independent correctness remain
  separate. The [source-faithful default](docs/evaluations/SOURCE_FAITHFUL_WORKSPACE_20261113.md)
  now retains all unresolved Wiki claims, checks native historical content and
  uses the exact-version projection in actual guided answers. The earlier
  current-GMT exclusion is preserved as an ablation, not biological pruning.
  Fuller Pharos activity context retains assay and value-scale limits.
- [Native GO context and ontology qualification](docs/SCIENTIFIC_QUALIFICATION.md):
  inspect complete native GOA qualifiers alongside historical Pharos records,
  and export a separate active-GO-ID view. The executed CRC view excludes 298
  obsolete-ID records with an exhaustive ledger; 167 explicit replacement
  proposals remain unapplied. These checks establish source/ontology semantics,
  not independent biological accuracy.
- [Current native GO inspection and published QC](docs/GO_NATIVE_QUALITY.md):
  query exact preserved source annotations and execute the official GO
  relation, reference and qualified taxon checks in an optional runtime.
  The [completed assessment](docs/evaluations/SCIENTIFIC_LIMIT_RESOLUTION_20261112.md)
  normalizes nine relations and 49 alternative-ID extensions, finds no taxon
  violations, and traces extension-context issues to primary evidence. It
  preserves the source graph and does not estimate whole-graph accuracy.
- [Automatic task qualification](docs/AUTOMATIC_TASK_QUALIFICATION.md): create a
  separate source-reported direct human phosphoregulation graph with complete
  keep/prune/abstain decisions. The first full CRC view excludes 76 explicitly
  task-incompatible SIGNOR records and retains unknowns. This is not a global
  biological-false-edge classifier; original workspaces remain preserved.
- [Reported sites and experimental context](docs/SITE_CONTEXT_INSPECTION.md):
  inspect phosphate addition/removal separately from the source's net protein
  effect, with exact source-context filters and citations; no graph mutation,
  inference or model call.
- [Source-scoped stable-ID qualification](docs/evaluations/SCOPED_IDENTITY_QUALIFICATION_20261112.md):
  qualify identifiers physically supplied in bound source rows without choosing
  a protein from a gene-only label. The optional helper leaves all 13 original
  unsupported historical target rows unresolved and does not rescore results.

- [Bounded cohort construction](docs/CONSTRUCTION.md): 1–25 exact protein accessions, a fixed source profile, published graph, cited candidate answer and offline-verifiable export. This deterministic flow needs no model.
- [Retrieval reliability](docs/PHAROS_RETRIEVAL_RELIABILITY.md): reuse native bounded retries and validated caching, with optional durable records of each native HTTP attempt. A separate consumed-data diagnostic preserves all eight eligible observations and the original fresh result.
- [Experimental construction planner](docs/CONSTRUCTION_AGENT.md): propose a bounded request for inspection against explicit cohort/form choices. Planning provenance survives publication and export. The [guided live check](docs/evaluations/GUIDED_CONSTRUCTION_ASSESSMENT_20261027.md) still failed all four supported tasks; use deterministic construction.
- Scoped Pharos retrieval with pagination, explicit limits and per-protein coverage reporting for pathways, GO, interactions, drugs, selected expression and publication discovery.
- [Record-level evidence overlap](docs/EVIDENCE_OVERLAP.md): inspect exact protein-pair overlap, shared record/publication identifiers, added assay context and unresolved lineage; export explicit identity mappings targeting SSSOM 1.0. Three saved development workspaces were audited, and all 14 exported mapping rows passed three official validators and preservation checks. The audit does not merge or prune records, pool confidence or establish independent corroboration.
- [Shared-record workbench flags](docs/ASSAY_SOURCE_REUSE.md): display verified current-STRING reuse beside preserved assay context and carry the proof in the workspace ZIP. The consumed example distinguishes one user-assisted exact record match from one unresolved record; historical Pharos inclusion remains unknown.
- [Scoped Pharos400 source supplement](docs/PHAROS_SOURCE_UPDATE.md): capture richer pair details and versioned identity/TDL rows, export conservative SSSOM correspondences and replay the resulting report offline. The demonstrated two-protein update leaves the original graph intact; experimental lineage remains unresolved.
- Qualified assertions, raw-source provenance, immutable snapshots and separate local human-review states.
- [Qualified assay attachment](docs/ASSAY_WORKBENCH.md): selected cohort observations, original assay context, source-preserving reviews and complete run exports.
- [Qualified IntAct source evidence](docs/INTACT_EVIDENCE_WORKBENCH.md): official-reader-backed records, readable experimental context and a dedicated traceable source question using the existing attachment/export framework. The real Pharos-attached flow preserves all four eligible development records through answer and gold export; this measures source fidelity, not biological accuracy.
- Guided protein-neighborhood and CIViC molecular-profile/therapy questions, with compact evidence graphs, deterministic cited summaries and complete evidence-context exports.
- [Optional physical association priority](docs/PHYSICAL_ASSOCIATION_PRIORITY.md): order an existing protein-neighborhood answer by native STRING 12.5 scores, with explicit missing scores and a saved, replayable source packet. Alphabetical order remains the default; graph relationships, functional context and review states are preserved.
- Saved graphs and answers, source passports, and comparison of saved snapshots with guarded review carryover.
- [Versioned biological source enrichment](docs/BIOLOGICAL_SOURCE_UPDATE.md): preserve Pharos while adding a newer STRING layer, qualified EGFR tissue-proximity observations and directed SIGNOR regulation, with source inspection, overlap accounting and portable replay.
- [Optional PPI pruning comparison](docs/PPI_PRUNING.md): separate source-graph views selected by native STRING scores or the unchanged external Network Enhancement implementation, with protected mixed-provider evidence, complete ledgers and a fixed measured-assay comparison. **Compare & assess** provides a read-only saved preview with policy metrics, searchable pairs, assay observations and source traces. The original workspace graph remains intact.
- Source-bound graph handoff, materialized retained graph and exhaustive keep/prune/abstain ledger, including qualified assay sources. Exact external-reference alignment preserves raw labels; official gold scoring awaits its contract. See the [real export verification](docs/evaluations/SUBMISSION_DEMO_20261026.md).
- [Bounded KGX export audit](docs/STANDARD_EXPORT.md), with a complete preserved source packet, mapping ledgers and separate upstream validation results. Full standard conformance remains unresolved.
- An optional bounded model planner that selects an existing read-only query. Deterministic guided questions work without it.
- Local/Docker/Brev operation, protected shared access and persistent data directories. Model inference is optional.

These capabilities preserve and expose source evidence. They do not establish clinical correctness, independent study replication, or general biological prediction gains. Bounded task comparisons report their own coverage and limitations. Language models do not approve or prune assertions automatically.

The [current release check](docs/evaluations/PHAROS_RELEASE_CHECK_20261027.md) confirms that our configured public API still reports `pharos319`; the client reads that label from the service. Official Pharos400 identity/TDL tables are available, but an equivalent complete 400 graph endpoint or dump was not verified in the checked official materials. Preserve source releases explicitly rather than relabelling old relationships.

The [fixed native STRING comparison](docs/evaluations/STRING_COMPONENT_COMPARISON_20261027.md) is complete on the consumed measured Lambourne panel. Across all **2,676 eligible pairs**, average precision was **0.172827 for functional scores versus 0.190056 for the physical overlay**, while explicit numeric coverage decreased from **88.3% to 72.4%**. On the same 1,938 jointly numeric pairs, AP was **0.176919 versus 0.199278**. This is a retrospective source-component ranking result, not independent biological validation or a Steward-versus-Pharos gain. The frozen comparison used native scores without a learner, GPU or model.

The October 27 [source-independence review](docs/evaluations/STRING_REFERENCE_INDEPENDENCE_20261027.md) records known HuRI/calibration reuse and the actual richer 12.5 lineage schema. No newly checked public reference qualified as independent confirmation. Its selected [STRING 12.0 temporal control](docs/evaluations/STRING_TEMPORAL_CONTROL_20261027.md) is now complete on the same **2,676 eligible pairs**: native functional AP **0.149732** versus native physical AP **0.161223**, with numeric coverage **93.4% versus 75.2%**. On the actual 2,013 jointly numeric pairs, AP was **0.150794 versus 0.165078**. Offline replay and a separate arithmetic review verified the result. The modest ranking benefit persists with the older fixed source, but this consumed-panel control does not establish independent validation or Steward graph improvement. Separate native 12.0 networks and the 12.5 typed overlay are different source profiles; between-release changes cannot isolate study ingestion. The original 12.5 result remains unchanged. This closes the selected temporal control without a version or threshold sweep. Its bounded product follow-up, optional question-specific physical association priority, is now implemented; it preserves functional coverage and source context and does not establish a new biological validation result.

The [reserved IntAct assessment](docs/evaluations/INTACT_FINAL_ASSESSMENT_20261027.md) executed once and stopped without a final score. It exposed a comparator defect for structural identifiers; captured XML preserves those identifiers. The standards-supported correction now passes a [complete consumed-data replay](docs/evaluations/INTACT_CONSUMED_FLOW_20261027.md): both eligible records survive Pharos attachment, the readable answer and the exported source packet. The original stopped result remains unscored. The [fresh four-study assessment](docs/evaluations/INTACT_FRESH_ASSESSMENT_20261027.md) subsequently completed with **4/8 end-to-end coverage and strict fidelity**: two source-license-query timeouts caused four misses; all four completed observations preserved assessed source fields. Those studies are now consumed. Source preservation does not establish biological accuracy or graph improvement.

A separate [retrieval-reliability check](docs/evaluations/PHAROS_RETRIEVAL_RELIABILITY_20261027.md) completed **8/8 observations** using the existing native retry/cache path. Its trace records one actual PPI timeout followed by a successful retry, plus three validated license-cache hits. The original fresh result remains **4/8**; this is consumed-data engineering verification, not new biological validation.

The [fixed PPI pruning comparison](docs/evaluations/PPI_PRUNING_COMPARISON_20261111.md) now measures actual retained graphs from 89,665 source edges. Native-score and Network Enhancement views each retain 73,313 edges while protecting mixed-provider evidence. On the consumed assay panel, NE retains all 334 source-present detections versus 326 for native selection, but retains more nondetections; its slightly lower retained detection fraction fails the predeclared rule for clear superiority. Its secondary raw-score AP increases from 0.152397 to 0.175440 at identical numeric coverage. The earlier STRING physical overlay remains higher at 0.190056 on this panel. These are retrospective tradeoffs, with original source records and complete ledgers preserved; the app's default graph remains unchanged.

[CRC temporal baseline verification](docs/evaluations/PHAROS_TEMPORAL_BASELINE_20261112.md) confirms that all 718 PPI pairs in the existing 99-target CRC input match the archive completed in April 2024. This anchors the unchanged component for the completed MAP-IT tissue-evidence assessment. That pruning endpoint is unscorable: none of 18 evaluable eligible EGFR pairs meets the frozen enrichment rule; one protected enriched pair is retained by all views. The source age and coverage limitations remain explicit; biological improvement is unproven.

## Current investigation

The challenge calls for the **same graph learner on baseline and enriched graphs**, evaluated against held-out measured relationships. A bounded supporting comparison is now complete; the official organizer reference is still unavailable.

Organizer Slack excerpts supplied October 23 also mention a **Pharos gold set**.
Its scoring contract remains unavailable to us; final test labels can reasonably remain hidden. [Public references](docs/literature/PUBLIC_REFERENCE_OPTIONS_20261026.md) can support bounded local assessments. The [local handoff interface](docs/GOLD_SET_INTERFACE.md) now exports verified graph packets and aligns explicitly mapped references without guessing label meanings. The study below is
a provisional supporting evaluation, not a substitute for the official reference;
see the [updated alignment](docs/PROJECT_ALIGNMENT.md#organizer-clarifications-and-submission-boundary).

The published **INMC experimentally tested human protein-pair panel** was evaluated using native PyKEEN R-GCN and a ComplEx control. The [paired evaluation graphs](docs/evaluations/INMC_PAIRED_GRAPH_20261023.md) share 10,350 nodes and 2,570 qualified-scope Pharos GO annotation pairs; only 315 official GO hierarchy edges differ. All Pharos interactions are excluded from learner inputs, including the 277 reserved-pair exposures. After the graph/runtime/scorer freeze, all 12 model runs completed locally and the author reference reconciled. On 1,751 eligible measured pairs, mean AP changed from **0.719833 to 0.720135**, with mixed seed effects. [The result](docs/evaluations/INMC_COMPARISON_20261023.md) does **not** demonstrate a consistent hierarchy benefit. This is an assay-specific retrospective PPI component evaluation, not a CRC treatment-response task or an official challenge score. The panel is now a consumed holdout.

Read the [reuse decision](docs/literature/MEASURED_LINK_BENCHMARK_REUSE_20261022.md), [assay/identity decision](docs/evaluations/INMC_READINESS_FOLLOWUP_20261022.md), [completed source audit](docs/evaluations/INMC_PHAROS_UNIFORM_20261022.md), [measured result](docs/evaluations/INMC_COMPARISON_20261023.md), and [next steps](docs/BUILD_PLAN.md). No general biological improvement is claimed.

A subsequent [fixed Reactome-context development comparison](docs/evaluations/REACTOME_CONTEXT_COMPARISON_20261026.md) adds 11,138 exact memberships already retrieved from Pharos. All six matched R-GCN fits completed after resource checks and an execution freeze. On the same 1,751 assay pairs, mean AP was **0.717794 versus 0.719605**, with two positive seed differences and one negative: **no consistent benefit is demonstrated**. Coverage and gene-influence diagnostics are reported. This consumed-panel comparison is closed without further tuning; it is not independent validation or a new binding-evidence source.

The subsequent [Lambourne assay corroboration](docs/evaluations/LAMBOURNE_CORROBORATION_20261025.md)
is complete after freezing the author-consistent adapter, eligibility and Pharos
comparator. All **3,222 nominated pairs** remain accounted for: 2,676 are assay
eligible and 2,674 also have complete Pharos identity coverage. Detection is
**334/1,966 (17.0%)** among represented pairs and **42/708 (5.9%)** among resolved
no-matches. In the prespecified stratum without observed HuRI/INMC pair overlap,
the rates are **74/1,619 (4.6%)** and **16/650 (2.5%)**. These are conditional
assay-concordance results; study independence remains unresolved and Steward
improvement was not tested. This panel is now consumed and cannot support new
prediction, enrichment or protocol tuning as an unseen test.

The [qualified assay evidence publication](docs/ASSAY_EVIDENCE.md) now preserves
all 3,222 observations in a standalone immutable layer and offline inspection
view: 2,676 qualified observation edges, 3,173 protein nodes and 546 excluded
assays retained in the audit. The 42 detections without a bounded Pharos match
are an inspection filter, not independently validated new interactions.
Study/construct context, nondetections and original Pharos records remain
explicit. See the [publication record](docs/evaluations/ASSAY_EVIDENCE_PUBLICATION_20261025.md).
The [workbench attachment](docs/ASSAY_WORKBENCH.md) now selects both-endpoint observations for an exact live protein cohort, preserves the entire original publication and supports inspection/review/replay and graph-plus-decisions export. KGX export and cohort refresh for attached runs remain unsupported and fail explicitly. This integration does not establish prediction gain or replace independent evaluation.

## Repository scope

`main` contains the current workbench, reusable source/identity adapters and the current INMC preparation tools. Retired growth-ranking, extraction, verifier and context-QA experiments are preserved on a separate **local archive branch**, rather than mixed into the active application. The [experiment ledger](docs/EXPERIMENT_HISTORY.md) records outcomes, consumed holdouts, exact archive commit and recovery instructions. The archive has not been pushed; ignored run data are not included in Git.

| Area | Guide |
|---|---|
| Team walkthrough | [START_HERE](START_HERE.md) |
| Current plan and challenge gaps | [Build plan](docs/BUILD_PLAN.md), [alignment](docs/PROJECT_ALIGNMENT.md) |
| Evidence and source contracts | [Data contract](docs/DATA_CONTRACT.md), [Pharos retrieval](docs/SCOPED_RETRIEVAL.md), [CIViC](docs/CIVIC_EVIDENCE.md) |
| Identity and evidence overlap | [SSSOM profile, record-level audit and release boundaries](docs/EVIDENCE_OVERLAP.md) |
| Explicit cohort construction | [Request, publish, inspect and replay](docs/CONSTRUCTION.md) |
| Questions, review and updates | [Guided questions](docs/GUIDED_QUESTIONS.md), [study context](docs/STUDY_CONTEXT.md), [snapshot comparison](docs/SNAPSHOT_REFRESH.md) |
| Gold-reference handoff | [Packet export, edge decisions and exact alignment](docs/GOLD_SET_INTERFACE.md) |
| Standards audit | [Bounded KGX projection and separate validator results](docs/STANDARD_EXPORT.md) |
| Optional model and deployment | [Planner](docs/PLANNER_PROTOCOL.md), [portability](docs/PORTABILITY.md), [local Nemotron](docs/LOCAL_MODEL.md) |
| Research and current scripts | [Literature knowledge base](docs/LITERATURE_REVIEW.md), [scripts](scripts/README.md) |

## Useful commands

```sh
python3 app.py --help
python3 app.py demo --out runs/demo_01
python3 app.py doctor
python3 app.py search colorectal
python3 app.py runtime-check
python3 -m unittest discover -s tests -q
```

Live retrieval never silently substitutes synthetic data. Keep credentials in local deployment configuration and source snapshots in the ignored data directories. A source's reuse terms still apply to its records and exports.
