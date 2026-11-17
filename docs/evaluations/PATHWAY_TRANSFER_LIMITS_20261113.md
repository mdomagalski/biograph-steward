# Pathway transfer: verified limits and next decision

The fixed new-gene check did **not** establish transferable biological benefit
from historical-source qualification plus resource-allocation (RA) weighting.
Keep the source qualification and its uncertainty visible; do not promote the
score to a default biological ranking or pruning rule. This focused primary-source/official-code review (13 November 2026) adds no
outcome experiment, replacement cohort or tuned method; it is not an exhaustive
systematic review.

## What our comparison establishes

One metadata-only sample contained 128 previously unevaluated genes, with 7,648
nonsyntenic pairs. Complete Pharos responses produced 410 distinct gene/version
links; native historical encoding supported 103 links. The other 307 links
remain UNKNOWN, not false. Historical context connected only 31 primary pairs
across 26 queries; all 102 zero-context queries were retained.

All 42 arms and N=1–10 were frozen before new reference capture. Neither RA nor
the binary shared-context diagnostic exceeded normalized context and every
fixed control at any N. Absolute historical observed affinity was lower at all
ten N. Independent reconstruction from the raw float64 ranges reproduced all
8,128 native P/sign rows, 321,216 RA pair weights and 840 curve points exactly.
This verifies the implementation and the negative result; it does not identify
a single biological cause of the failure.

The result is preserved in
`runs/coessentiality_transfer_20261113/scored_v1` (`ce3791a4…`), with independent
review under `runs/coessentiality_prospective_review_20261113/` (arithmetic seal
`9ae6a15d…`; availability/claims seal `8f7588d5…`).

## Source coverage beyond the Wiki feature view

A [post hoc source-only diagnostic](source_coverage_20261113_summary.json)
replays the six frozen Pharos chunks and exact gene/accession joins, without
opening matrix or ranking outcomes or changing the experiment. Sparsity is not
confined to Tdark:

| Captured Pharos319 class | Sampled genes | Complete-zero Wiki responses | No eligible historical shared-context partner |
|---|---:|---:|---:|
| Tclin | 3 | 1 | 1 |
| Tchem | 11 | 0 | 3 |
| Tbio | 85 | 55 | 70 |
| Tdark | 29 | 28 | 28 |

Of the 102 queries without an eligible historical partner, 74 are non-Tdark.
The 84 complete-zero raw Wiki responses are a different denominator: having
an annotation need not supply a partner on another chromosome in this cohort.
TDL classes describe target development and knowledge availability, not
biological relevance or guaranteed pathway coverage.
[Pharos 2023](https://doi.org/10.1093/nar/gkac1033),
[official current TDL definitions and release boundaries](https://opendata.ncats.nih.gov/public/pharos/pharos400_readme.html).
The diagnostic retains its captured Pharos319 labels.

Other pathway records already exist in this exact Pharos capture: **Reactome
614 rows across 73 genes**, **KEGG 151 across 57**, and WikiPathways 585 across
44. At least one queried pathway provider covers 97/128 genes; 53 of the 84
zero-Wiki genes have another provider's pathway rows. These are overlapping
raw annotation counts, not independent experiments, verified reaction roles
or outcome gains. Other evidence families were not retrieved. This identifies
an availability limit in the chosen Wiki feature view, without establishing a
causal explanation of the negative result or authorizing a new fit on consumed
outcomes. Existing Reactome record inspection is therefore a concrete resource
already available for source-context work.

## What the literature explains—and what remains a hypothesis

**Coverage differs across biological questions.** A systematic assessment of
pathway annotation systems found substantial variation in gene coverage,
annotation depth and study-related biases. This supports reporting the coverage
of each question rather than assuming performance transfers from a selected
cancer cohort to a metadata-random gene sample. Our complete zero-Wiki responses
are observed source sparsity; they do not show biological irrelevance. We have
not causally attributed our result to study bias. [Gable et al., 2022](https://pmc.ncbi.nlm.nih.gov/articles/PMC9487593/)

**RA uses the supplied graph's degree.** Native NetworkX defines
`RA(a,b) = sum(1 / degree(p))` over common neighbors. In our bipartite graph,
`degree(p)` counts sampled genes connected to a versioned model, not every
biological participant in that pathway. Changing the gene cohort can therefore
change a pair's weight even with the same source model. This is a mathematical
property of the reviewed implementation, not a runtime defect. Full native
pathway size would require a separately qualified entity/universe mapping; it
cannot be silently substituted after this result. [NetworkX 3.7 definition and source](https://networkx.org/documentation/stable/reference/algorithms/generated/networkx.algorithms.link_prediction.resource_allocation_index.html)

**Keeping zeros does not make a ratio coverage-adjusted.** Our pooled O/E adds
zero to both observed and expected sums for a query with no shared context.
Those queries lower absolute affinity per fixed query-partner slot, but do not
otherwise alter the O/E ratio. A small informative subset can dominate the
ratio. The verified formula therefore requires coverage and absolute means
beside enrichment. At N=10, historical O/E was 0.775 versus 0.604 normalized,
while historical absolute observed affinity was lower and a fixed control
reached 2.493. No favorable N replaces the failed full-curve rule.

**Matched controls are necessary, not a universal correction.** Published work
shows that annotation multifunctionality and node degree can generate strong
functional-prediction performance without the desired specific associations.
Our count and degree controls address two structural alternatives. They do not
establish uniform null mixing, independent replications, removal of every
curation bias, or a degree shortcut in our graph. The negative transfer prevents
turning the earlier exploratory enrichment into a general accuracy claim.
[Gillis and Pavlidis, 2011](https://pmc.ncbi.nlm.nih.gov/articles/PMC3041792/)

**The endpoint is functional concordance.** Wainberg's released matrices measure
co-essential fitness patterns; co-pathway context does not establish physical
binding, a causal mechanism or clinical efficacy. Old development outcomes and
paper examples informed the selected method. The new-new block was held until
the prospective freeze, but it comes from the same published study, not an
independent experimental replication. [Wainberg et al., 2021](https://doi.org/10.1038/s41588-021-00840-z), [author data/code](https://github.com/kundajelab/coessentiality)

## One actionable interpretation gap

The useful next unit is an **exact native reaction or complex record and its
role/context**, when available, rather than another score on flattened pathway
membership. Reactome explicitly distinguishes reactions, complexes, entity
sets, protein modifications, compartments and inferred human events. A shared
pathway alone supplies none of those distinctions. This is interpretation of
source evidence, not independent corroboration: Reactome is already represented
in Pharos. Preserve the provider/release and record lineage, and keep missing
historical correspondence UNKNOWN. [Reactome data model](https://reactome.org/documentation/data-model)

Existing public tools address this representation problem. Paxtools provides
BioPAX querying and formal conversion patterns; Pathway Commons separates
`in-complex-with`, `controls-state-change-of` and `interacts-with`. A co-complex
projection must retain that meaning and cannot become direct binding merely
because it is binary. The MIT-licensed Paxtools source currently requires
JDK 17+; the inspected master POM declares `6.0.1-SNAPSHOT`, so a future execution
must pin an actual release and its dependencies. No installation or runtime
compatibility test was performed here. [Paxtools paper](https://doi.org/10.1371/journal.pcbi.1003194), [official code](https://github.com/BioPAX/Paxtools), [native relation rules](https://www.pathwaycommons.org/pc2/formats)

**GO:** use the existing guided source inspection and official
[Reactome Content Service](https://reactome.org/dev/content-service) to expose
native event/participant roles for a bounded, version-qualified question.
Paxtools is a reusable route if BioPAX extraction is later needed; no new
classifier, paid API or model training is required. This is a feasible source
interpretation task, not a demonstrated biological-performance improvement.
The delivered source guide already opens the exact current Reactome record
and its event browser. It preserves the original imported reference and warns
about species inference and historical correspondence. Automatic structured
role extraction remains separate future work.

**NO-GO:** add Paxtools as a new scoring dependency now, reinterpret its native
relations as assay truth, or compare a different method on the now-consumed
128-gene outcomes and call it prospective. The exact compatible unweighted
shared-context baseline was already evaluated and remains negative under its
fixed rule.

A newer public alternative, the 2024 PET/Benchmark release, provides experimental
perturbation gene sets and pathway-discovery evaluation with author code. It is
useful if the product later accepts perturbation expression/ranked-gene inputs.
It is **not** a drop-in reference for our pairwise co-essentiality, original
Pharos assertion correctness or PPI pruning. Its published repository is
GPL-3.0 and requires a separate task/data-lineage qualification before reuse;
no data or package was imported here. [Primary study](https://pmc.ncbi.nlm.nih.gov/articles/PMC11343859/), [author benchmark](https://github.com/loooooooopi/Benchmark)

The delivery decision is to retain the source-faithful graph, historical proof
and UNKNOWNs, report the failed transfer alongside the development result, and
make source-context interpretation clearer. No published method reviewed here
justifies automatically deleting the unresolved memberships or claiming
whole-graph scientific accuracy.
