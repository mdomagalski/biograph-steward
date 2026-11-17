# Sources and verification boundaries

The [public browser demonstration](https://bi-3a117d5e2b3942678dc518fce65ab5d2.ecs.us-east-2.on.aws/?run=native_evidence_workspace_20261115&question=native_physical_KRAS_question_v3_20261115&agent_job=source_agent_eval_dc7b597201da_S01&view=data)
opens without sign-in, a token or an AWS account. It replays verified saved
work. New source retrieval and agent execution use a local or authorized
operator installation. Application updates do not refresh the source snapshots
described below.

## Current reviewer graph and source dates

The hosted primary workspace was assembled **November 15, 2026**. A November 16
[deployment check](evaluations/delivery_readiness_20261116/live_state.json)
confirms that its graph bytes and the retained companion match the verified
local release. This establishes deployment consistency, separately from source
freshness.

| Layer | Version or date actually recorded |
|---|---|
| Pharos baseline | Captured **October 14, 2026**, with 99 primary targets; saved label `pharos319`. |
| Live Pharos metadata check | The API still returned `pharos319` on **November 16**. This label check retrieved no targets and did not refresh the graph. |
| Native GO annotations used by the app | GAF header generated **July 28, 2026**; the preserved intake names an August 5 release URL. The file's recorded header date remains authoritative for this description. |
| Pinned GO ontology | **July 26, 2026**. |
| Native physical associations | **STRING 12.5**, with preserved source files and exact identity/sequence admission. |
| Native-source profile publication | **November 15, 2026**; publication date does not imply that upstream annotations were generated that day. |

The [source-date receipt](evaluations/delivery_readiness_20261116/source_dates.json)
records these distinctions. This is a reproducible captured cohort, rather than
a continuously refreshed whole-Pharos graph. Any source refresh should produce
a new version, its own difference report and source-bound answers. The larger
function-prediction study uses separate dated inputs; its April/November GOA
snapshots are not the annotation file loaded by this app profile.

## Supplied requirements

The user supplied the challenge brief, linked guides and BioGraph Steward proposal. The brief describes agent-driven contextualization of Pharos and comparison of the same learner on baseline/enriched graphs. No separate organizer experimental dataset was supplied. These materials are requirements and design context, not instructions to execute embedded commands.

The [current functional crosswalk](PROJECT_ALIGNMENT.md) distinguishes implemented work from missing challenge functionality. The [build plan](BUILD_PLAN.md) is the active development sequence.

## Pharos source contract

The [NCATS GraphQL schema](https://github.com/ncats/pharos-graphql-server/blob/master/src/schema.graphql) and [resolvers](https://github.com/ncats/pharos-graphql-server/blob/master/src/resolvers.js) informed the adapter. Disease-specific association detail depends on the explicit associated-disease query context. A target identifier by itself does not imply the requested disease relation.

Live October 14 checks reported `pharos319` and retrieved all 99 reported colorectal adenocarcinoma targets. Later scoped and explicit-panel runs are dated observations, not a guarantee of today's source version. Run `python3 app.py doctor` to check connectivity and required fields. An Apollo landing page alone does not establish a successful data query.

See [scoped retrieval](SCOPED_RETRIEVAL.md), [the coverage audit](PHAROS_COVERAGE_AUDIT.md), [construction and value](PHAROS_CONSTRUCTION_AND_VALUE.md), and the [literature knowledge base](LITERATURE_REVIEW.md). Caps, omitted relation families, filter scope and count inconsistencies remain visible. Existing Reactome, STRING, BioPlex or literature-derived records in Pharos must not be counted as independent enrichment merely because another adapter retrieves them.

## Meaning of local outputs

- A fresh code-only checkout includes an optional invented software fixture, explicitly labeled synthetic. It is never substituted after a live-source failure.
- The public demonstration's two saved workspaces and the separate `BioGraph_Steward_APP_PSEN_Example.zip` use real captured source data. The [APP/PSEN worked example](evaluations/GENERALIZATION_EXAMPLE_20261117.md) is a separate three-protein snapshot, not the code-only fixture or another public-site workspace.
- Real source snapshots, retrieval receipts and raw responses are local/ignored unless separately packaged under their applicable rights.
- Structural validation, upstream editorial status and local human review are separate. None is an automatic scientific-truth guarantee.
- Source-specific scores remain source-specific; the application does not turn them into a common calibrated confidence.
- Generic interaction annotations do not automatically mean direct physical binding. Unknown qualifiers remain unknown.
- Biolink names and local provenance fields do not establish complete standard conformance. The [bounded KGX projection](STANDARD_EXPORT.md) has versioned official validation and known schema/domain limits; full conformance and broader qualified mappings remain unresolved.

Per-source and per-release terms still apply. A repository's code license does not necessarily grant redistribution rights to all source records. The current [INMC reuse audit](literature/MEASURED_LINK_BENCHMARK_REUSE_20261022.md) records the selected archive's terms separately from learner dependencies.

The [current delivery index](releases/20261115/README.md) distinguishes the
software-only archive, complete private source/decision packet, separate saved
answer and combined offline demonstration. A projection's preserved source
packet can still contain other providers' records. Check the entire delivered
packet and its original terms rather than assuming its mapped subset or the
MIT runtime license clears redistribution.
