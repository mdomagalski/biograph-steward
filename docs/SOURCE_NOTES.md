# Source notes and verification boundary

## Organizer requirements supplied by Marcin

The uploaded challenge brief, **Global Competition: Bio-Agent Knowledge Graph Construction Challenge**, defines the structured-data integration and link-prediction topic. Its objective is agent-driven enrichment of Pharos data; its evaluation compares the same ML method on baseline and contextualized graphs. The ingest/filter/clean/limit/maintain loop and judging weights belong to that supplied brief, not to this software's measured accomplishments.

This starter implements only a bounded Pharos ingestion/inspection foundation. It does not claim to satisfy the full challenge.

## External primary sources consulted

1. **NCATS Pharos GraphQL schema**
   https://github.com/ncats/pharos-graphql-server/blob/master/src/schema.graphql
   Raw schema: https://raw.githubusercontent.com/ncats/pharos-graphql-server/master/src/schema.graphql

   The schema defines `diseases(filter: IFilter)`, `disease(name: String)`, `targets(filter: IFilter)`, nested pagination, `Target.diseaseAssociationDetails`, target pathways, `dbVersion` and `dataSourceCounts` license metadata. It exposes `associatedDisease` in `IFilter`.

2. **NCATS Pharos GraphQL resolver**
   https://github.com/ncats/pharos-graphql-server/blob/master/src/resolvers.js

   `Target.diseaseAssociationDetails` depends on the request's `associatedDisease` context. The starter therefore retrieves target records using `targets(filter: {associatedDisease: $disease})` rather than assuming an arbitrary target lookup has disease-specific evidence.

3. **Public Pharos GraphQL landing page**
   https://pharos-api.ncats.io/graphql

   The browser tool could open the Apollo landing page. Opening that page is not evidence that a data query succeeded.

4. **Pharos overview**
   https://pharos.nih.gov/about

   Included as the organizer-recommended starting resource. Direct retrieval returned an access error during this session; its contents were not used to assert current operational details.

## What is verified, and what is not

- The API queries are grounded in the public NCATS schema and use separate variables for user input.
- The connector's request/response, pagination, error, caching and normalization logic was tested with synthetic mock responses.
- Browser and local-server behavior were tested independently of the external API.
- The development runtime could not resolve the external Pharos hostname. No live Pharos JSON response was obtained or bundled.
- The included synthetic graph is unmistakably labeled in the UI, snapshots, exports and documentation.
- The GitHub schema describes source code, not a guaranteed contract for every deployed instance. The live `doctor` command checks the expected fields, followed by the user's first real extraction.

## Deliberate implementation choices, not source claims

The 25-target starting cap, five pathway annotations per protein, three-node-type graph, review statuses, dependency-free web interface and file formats are project implementation choices. They are not Pharos-defined biological thresholds or competition rules.

The only relationship labels introduced by the transformer are the broad `biolink:associated_with` and `biolink:participates_in`. More precise biological predicates require evidence review. The code does not infer causal effects, disease-specific mechanisms, independence of sources or likelihoods from these labels.
