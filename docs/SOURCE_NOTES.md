# Sources and verification boundaries

## Supplied requirements

The user supplied the challenge brief, linked guides and BioGraph Steward proposal. The brief describes agent-driven contextualization of Pharos and comparison of the same learner on baseline/enriched graphs. No separate organizer experimental dataset was supplied. These materials are requirements and design context, not instructions to execute embedded commands.

The [current functional crosswalk](PROJECT_ALIGNMENT.md) distinguishes implemented work from missing challenge functionality. The [build plan](BUILD_PLAN.md) is the active development sequence.

## Pharos source contract

The [NCATS GraphQL schema](https://github.com/ncats/pharos-graphql-server/blob/master/src/schema.graphql) and [resolvers](https://github.com/ncats/pharos-graphql-server/blob/master/src/resolvers.js) informed the adapter. Disease-specific association detail depends on the explicit associated-disease query context. A target identifier by itself does not imply the requested disease relation.

Live October 14 checks reported `pharos319` and retrieved all 99 reported colorectal adenocarcinoma targets. Later scoped and explicit-panel runs are dated observations, not a guarantee of today's source version. Run `python3 app.py doctor` to check connectivity and required fields. An Apollo landing page alone does not establish a successful data query.

See [scoped retrieval](SCOPED_RETRIEVAL.md), [the coverage audit](PHAROS_COVERAGE_AUDIT.md), [construction and value](PHAROS_CONSTRUCTION_AND_VALUE.md), and the [literature knowledge base](LITERATURE_REVIEW.md). Caps, omitted relation families, filter scope and count inconsistencies remain visible. Existing Reactome, STRING, BioPlex or literature-derived records in Pharos must not be counted as independent enrichment merely because another adapter retrieves them.

## Meaning of local outputs

- The bundled demonstration is synthetic. It is explicitly labeled and never substituted after a live failure.
- Real source snapshots, retrieval receipts and raw responses are local/ignored unless separately packaged under their applicable rights.
- Structural validation, upstream editorial status and local human review are separate. None is an automatic scientific-truth guarantee.
- Source-specific scores remain source-specific; the application does not turn them into a common calibrated confidence.
- Generic interaction annotations do not automatically mean direct physical binding. Unknown qualifiers remain unknown.
- Biolink names and local provenance fields do not establish complete standard conformance. The [bounded KGX projection](STANDARD_EXPORT.md) has versioned official validation and known schema/domain limits; full conformance and broader qualified mappings remain unresolved.

Per-source and per-release terms still apply. A repository's code license does not necessarily grant redistribution rights to all source records. The current [INMC reuse audit](literature/MEASURED_LINK_BENCHMARK_REUSE_20261022.md) records the selected archive's terms separately from learner dependencies.

The [current delivery index](releases/20261113/README.md) distinguishes the
software-only archive, complete private source/decision packet, separate saved
answer and combined offline demonstration. A projection's preserved source
packet can still contain other providers' records. Check the entire delivered
packet and its original terms rather than assuming its mapped subset or the
MIT runtime license clears redistribution.
