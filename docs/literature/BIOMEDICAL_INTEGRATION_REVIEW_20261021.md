# Biomedical integration: literature and reusable-method review

Reviewed October 21, 2026. Scope: the integration and maintenance layer of BioGraph Steward. This is a focused evidence map with 14 source families, not an exhaustive systematic review, a new graph import, or a scientific-accuracy result. The companion [source registry](integration_sources_20261021.json) records checked claims, artifacts, limits and reuse status. Source IDs below match that registry.

## What this task is called

Our integration task spans **biomedical knowledge integration**, **semantic interoperability**, **entity normalization/grounding**, **ontology mapping**, **provenance-aware knowledge graph construction**, and **knowledge maintenance**. These are separable from scientific claim verification, evidence synthesis, causal inference and target prioritization. A well-formed, traceable graph can still contain unsupported, conflicting or context-inappropriate claims.

The strongest practical conclusion is to make existing evidence more interpretable before multiplying sources. Standards already address many representation problems; they do not determine scientific truth, study independence, or whether an enrichment improves the intended biological task. Statements labeled “project implication” below are our inference from the sources, not reported experimental results.

## Search and screening record

Search date: 2026-10-21. Discovery used web searches against indexed primary publications and official project documentation; direct pages were then opened and relevant sections inspected. Venues inspected include Nucleic Acids Research, Database, Bioinformatics/Bioinformatics Advances, Clinical and Translational Science, Scientific Data, eLife, W3C recommendations, and official GitHub/documentation sites. No exhaustive PubMed, Embase, Scopus or Web of Science export was conducted. There was no independent duplicate screening, formal risk-of-bias assessment, saturation test or preregistered protocol. The 14 IDs are source families, not a count of all papers returned or fully read.

Exact discovery queries included:

- `Biolink Model biomedical knowledge graph standards 2022 paper`
- `SSSOM simple standard sharing ontological mappings 2022 paper`
- `Biomappings semiautomated creation maintenance biological identifier mappings 2023`
- `PheKnowLator biomedical knowledge graph 2024 paper construction`
- `Pharos 2023 target central resource database 79 data sources`
- `PrimeKG building a knowledge graph enable precision medicine 2023 Scientific Data`
- `Hetionet systematic integration biomedical knowledge prioritizes drugs repurposing 2017`
- `Biomedical Data Translator Node Normalization service gene protein conflation official`
- `site.geneontology.org documentation annotations NOT qualifier open world`
- `site.platform-docs.opentargets.org evidence score data source harmonic sum association`
- `Gilda biomedical entity text normalization machine learned disambiguation Bioinformatics 2022`
- `Bioregistry integrative meta registry community driven curation model 2022 Scientific Data`
- `site.nodenormalization-sri.renci.org conflate gene protein`
- `site.github.com/NCATSTranslator/NodeNormalization conflate description`
- `site.biopragmatics.github.io/gilda organism text grounding context`

Selection favored direct relevance to our observed integration gaps, primary descriptions with inspectable artifacts, and methods that can be reused without replacing the project. Generic tutorials, promotional claims, unrelated PHAROS acronyms and secondary mirrors were not used as evidence. Some PMC direct opens returned a challenge page; publisher pages, indexed primary text and official documentation supplied the checked passages. GitHub raw fetches for NodeNormalization failed, but its rendered `server.py` was available. No inaccessible source is treated as fully inspected. Repositories were read on their current branch without installing them; unpinned branch content and API deployments can change.

## Evidence map

### INT01 — Pharos 2023 / TCRD construction

[Kelleher et al., NAR 2023](https://doi.org/10.1093/nar/gkac1033) describes a target-centered resource integrating 79 sources in that publication and harmonizing target, disease and ligand identifiers. It documents disease-ontology aggregation and exploration features. This establishes heterogeneous integration, not uniform experimental validation or a current source-count guarantee.

Project implication: use Pharos as an existing integration baseline; compare exact records and qualified context before counting another database as new evidence. Historical paper behavior must be checked against the actual release and endpoint. The old public TCRD builder is not proof of the deployed pipeline's version. Our saved construction audit already makes this distinction.

### INT02 — Pharos400 release and identity changes

[Official NCATS release notes](https://opendata.ncats.nih.gov/public/pharos/pharos400_readme.html) distinguish 20,654 canonical proteins from 166,833 total protein rows, including isoforms and alternate products. The canonical comparison reports 2,137 TDL upgrades. UniProt is the public protein identifier; internal IFX IDs serve traceability. Tdark criteria permit limited evidence and Tchem assignment uses qualifying activity rules.

Project implication: compare our 512-gene panel to the canonical release before a full import. Record obsolete, one-to-one and one-to-many accession changes separately. Do not multiply gene-level CPTAC observations into isoform observations. We did not download these tables or establish that the existing GraphQL endpoint serves this release; table/API compatibility remains untested.

### INT03 — Biolink Model and retrieval-source chains

[Unni et al., 2022](https://doi.org/10.1111/cts.13302) supplies shared categories, predicates and association attributes for interoperability. The official [RetrievalSource specification](https://biolink.github.io/biolink-model/RetrievalSource/) records resource identity, role, upstream resources and source-record URLs.

Project implication: map our local predicates and provenance to a pinned compatible model rather than asserting full Biolink compliance. Keep aggregator chains distinct from the underlying experiment. The standard does not infer independence, prove a source's statement, or make all predicates interchangeable. Our present local qualifiers remain intentionally narrower than a complete Biolink mapping.

### INT04 — SSSOM mappings as inspectable artifacts

[Matentzoglu et al., 2022](https://doi.org/10.1093/database/baac035) and the [versioned 1.0 introduction](https://mapping-commons.github.io/sssom/1.0/introduction/) distinguish exact, broad, narrow, close and related mappings, with mapping-level provenance. A bare cross-reference does not necessarily mean equivalence. Mapping incompleteness can arise from deliberate scope, obsolete terms or missed matches.

Project implication: record mapping predicate, method, source versions and review status beside our crosswalks. Do not merge disease subtypes, pathways or products solely by label or broad mapping. SSSOM represents the mapping decision; it does not adjudicate correctness. The current repository declares BSD-3-Clause with an explicit image exception.

### INT05 — Biomappings: curated versus predicted equivalence

[Hoyt et al., 2023](https://doi.org/10.1093/bioinformatics/btad130) provides a community process for missing mappings. The [official repository](https://github.com/biopragmatics/biomappings) separates positive, negative, unsure and predicted mappings in SSSOM files; code is MIT and its primary/derived mapping data CC0.

Project implication: inspect coverage for our unresolved entities and use documented negative/unsure mappings as challenging cases before writing label-merging heuristics. Predictions must stay candidates. Neither coverage nor correctness for our pathway, disease and ligand examples has been measured. The package and mapping revision were not installed or frozen.

### INT06 — Translator NodeNormalization

The [official service repository](https://github.com/NCATSTranslator/NodeNormalization) provides CURIE normalization. Its inspected [server implementation](https://github.com/NCATSTranslator/NodeNormalization/blob/main/node_normalizer/server.py) exposes gene/protein and drug/chemical conflations; both GET normalization flags default to true.

Project implication: a proposed adapter must explicitly choose conflation settings and retain original IDs, semantic types and taxa. Protein-specific and formulation-specific assertions should not inherit generic normalization equivalence silently. Source code is MIT; deployed version, compendium release, coverage and runtime were not verified. This is an existing capability to test, not an installed component or a guarantee of exact biological identity.

### INT07 — PROV-O for derivation and revision

[W3C PROV-O, 2013 recommendation](https://www.w3.org/TR/prov-o/) models entities, activities, agents and derivations, including revisions. It offers an interoperable vocabulary for recording transformations and responsibility.

Project implication: relate raw snapshots, mapping versions, transformations, assertions and review events explicitly. Our immutable snapshots and conservative refresh comparisons already implement part of this need. PROV-O provides a provenance representation; it cannot reconstruct missing study lineage or establish independent replication. A formal PROV export or conformance check has not been implemented here.

### INT08 — Hetionet: task-specific integration and evaluation

[Himmelstein et al., eLife 2017](https://doi.org/10.7554/eLife.26726) integrated 29 resources and evaluated drug-repurposing predictions, including external treatment sets. This is evidence for a particular integrated prediction workflow, not validation of every graph relationship.

The [official graph repository](https://github.com/hetio/hetionet) assigns original content CC0 while retaining source-specific license considerations and per-node/edge license attributes. Project implication: preserve resource rights and evaluate a declared downstream task. A Hetionet import would require overlap checks against Pharos and would not itself create independent corroboration. Its historical v1.0 baseline is not a current cancer-claim truth set.

### INT09 — PrimeKG: construction precedent, with a successor

[Chandak et al., Scientific Data 2023](https://doi.org/10.1038/s41597-023-01960-3) documents harmonization of 20 resources, deduplication, reverse edges and a connected graph. Its [official repository](https://github.com/mims-harvard/PrimeKG) now states that OptimusKG supersedes it. MIT applies to software; dataset licenses remain separate.

Project implication: reuse build recipes and source manifests as design references, rather than assuming a broad graph is a fresh truth source. Reverse edges are derived views, not new studies. Removing disconnected nodes may be unsuitable for a workbench intended to expose dark-target gaps. Successor capabilities and compatibility require their own review; no graph was imported.

### INT10 — PheKnowLator: representation choices matter

[Callahan et al., Scientific Data 2024](https://doi.org/10.1038/s41597-024-03171-w) publishes customizable class/instance, relation and semantic-abstraction choices with 12 benchmark graphs. Authors disclose that their tool comparison was qualitative, involved their developers, and was not a same-input execution comparison; computational timings came from one build.

The [Apache-2.0 implementation](https://github.com/callahantiff/PheKnowLator) and paper-linked v2.1.0 artifacts are inspectable. Project implication: make representation choices explicit and compare alternatives on the same inputs. It is not evidence that this framework improves our claims. Installation was not tested; inspected setup metadata includes older dependency constraints and does not establish current runtime compatibility.

### INT11 — GO annotation semantics and missingness

The [official GO annotation guide](https://www.geneontology.org/docs/go-annotations/) states the open-world assumption, distinguishes relations and explicit NOT annotations, and permits conflicting positive/NOT annotations. NOT is not a generic flag for an inconclusive or negative experiment. Annotation propagation depends on relation and polarity.

Project implication: our conservative `has_go_annotation` representation is appropriate while the API omits relation, negation and extensions. Recover these upstream fields before interpreting annotations as positive molecular functions. Absence stays unknown. This is a documented limitation in our current retrieval, not evidence of a faulty GO resource. The exact ontology/annotation release and redistribution terms must be selected before importing.

### INT12 — Open Targets: evidence aggregation is not calibrated certainty

The official [association-scoring documentation](https://github.com/opentargets/platform-docs/blob/main/associations.md) distinguishes direct/ontology-propagated associations and describes source-weighted harmonic aggregation. It explicitly characterizes scores as ranking heuristics based on available data, not confidence probabilities.

Project implication: retain source semantics and avoid converting publication counts, provider counts or borrowed association scores into scientific certainty. Open Targets is a useful comparison for source-aware presentation; adding it would require record/study overlap checks. The official [pipeline documentation](https://platform-docs.opentargets.org/data-access/data-pipeline) links reusable components, but no specific release, execution or license was audited for adoption.

### INT13 — Gilda: contextual grounding, with identity-policy choices

[Gyori et al., 2022](https://doi.org/10.1093/bioadv/vbac034) evaluates biomedical name grounding and contextual disambiguation. The paper explicitly merges gene/protein synonyms by default, while allowing custom grounders to separate them. The [official repository](https://github.com/gyorilab/gilda) supplies local/API use and custom-grounder examples; inspected packaging requires Python >=3.8 and uses BSD-2-Clause.

Project implication: compare a restricted, context-aware grounder against our exact catalog resolver before inventing fuzzy rules. Freeze resources and assess ambiguity, species, families and gene/protein separation. Published name-grounding results do not establish relation extraction or claim verification. No model/resource download or local test occurred in this review.

### INT14 — Bioregistry: identifier syntax and namespaces

[Hoyt et al., Scientific Data 2022](https://doi.org/10.1038/s41597-022-01807-3) and the [official implementation](https://github.com/biopragmatics/bioregistry) describe harmonizing identifier-resource metadata, prefixes and resolver conventions. Repository code is MIT; curated registry data are CC0, while aggregated data retain original licenses.

Project implication: validate namespace/prefix formatting before semantic mapping and preserve resource-version information. A syntactically valid CURIE or working URL does not prove the record is the intended entity. Registry curation solves a different layer from Gilda grounding, SSSOM mappings and evidence-origin resolution. Package compatibility and current resource coverage were not tested.

## Mapping this evidence to the current project

The following assessments come from inspected repository documents, not from claims of the external papers. Relevant local references: [data contract](../DATA_CONTRACT.md), [construction/value review](../PHAROS_CONSTRUCTION_AND_VALUE.md), [context normalization](../CONTEXT_NORMALIZATION.md), [cohort mapping](../EXPERIMENT_HISTORY.md#reopening-an-archived-file "Archive file: docs/COHORT_MAPPING.md"), [CIViC adapter](../CIVIC_EVIDENCE.md), and [snapshot refresh](../SNAPSHOT_REFRESH.md).

| Capability | Current basis | Verified gap or unresolved question | Existing approach to assess first |
|---|---|---|---|
| Versioned identity | Frozen HGNC/UniProt crosswalks; ambiguity retained; gene measurements remain gene-level | Pharos400 canonical/isoform change not reconciled with our saved319 panel | Official400 transition fields; SSSOM mapping provenance |
| Entity normalization | Stable UniProt IDs; local unresolved disease/pathway/ligand IDs; no silent label equivalence | Coverage of established resolvers for actual unresolved examples is unmeasured | Bioregistry, curated Biomappings, explicit NodeNorm settings; Gilda for text names |
| Assertion semantics | Qualified candidate assertions; local predicates clearly disclosed | Complete GO polarity/extensions and some source-specific qualifiers unavailable in current extract | GO formats, pinned Biolink mappings; retrieve missing fields before stronger inference |
| Provenance | Raw response locators, hashes, source fields and review history | Aggregator labels do not identify all studies, experiments or reused samples | Biolink RetrievalSource and PROV-O for representation; source-level study resolution still required |
| Evidence independence | `independent_evidence_count` deliberately null | No complete experiment/sample overlap map; different PMIDs may share samples | Preserve unknown status; use explicit study/assay/sample IDs where sources provide them |
| Refresh | Scope/completeness checks and conservative review carryover | Migration behavior under changed identifiers or source rules needs evaluation | Versioned mapping decisions and derivation records; distinguish disappearance from withdrawal |
| Confidence presentation | Original source scores preserved; structural status separated from biology | A calibrated common confidence scale is not established | Open Targets as cautionary source-aware ranking precedent, not probability calibration |
| Rights and reuse | CIViC licensing recorded; legacy catalog licenses often null | Third-party source/data rights remain heterogeneous | Hetionet/PrimeKG per-source rights separation; do not inherit software licenses for all data |

## Recommended decision sequence and remaining research gaps

These are recommendations, not completed integrations:

1. Freeze a task-specific vocabulary of acceptable claim types and identity granularity. Decide whether each question concerns a gene, canonical protein, isoform, molecular profile, drug ingredient, formulation or therapy combination. This prevents a resolver's convenience defaults from becoming biological assumptions.
2. Audit Pharos319-to400 identity and evidence-field coverage on our existing panel while preserving the old baseline. Separate an accession correction, additional context, changed source rules and new underlying experimental evidence.
3. Build a small manually inspectable resolver test set from the unresolved cases we already have. Compare established tools without changing production assertions. Include exact matches, broader disease terms, ambiguous synonyms, family/complex mentions, one-to-many products and deliberately incorrect pairs. Measure mapping correctness and abstention, not just resolution rate.
4. Recover missing qualifiers and lineage for the specific claims selected for evaluation. In our current graph this has a more direct justification than another broad KG import. Record “independence unknown” when study/sample IDs cannot be established.
5. Keep structural integrity, source faithfulness, evidence quality, maintenance utility and downstream biological performance as separate outcomes. None of the reviewed integration tools supplies a universal scientific-accuracy ground truth.

Unresolved research gaps include reliable cross-database study/sample deduplication, disease-specific rather than generic protein function, formulation/variant equivalence, temporal validity of curated conclusions, source-specific measurement comparability, and the effect of missingness on our chosen endpoint. No literature search can guarantee anticipation of every limitation. The useful output is a traceable list of known limits, reusable methods, and bounded questions to resolve before another implementation choice.
