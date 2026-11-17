# Frozen exploratory resource-allocation extension

This extension is declared **after** the original native GLS outcomes and
binary-context result `a0b55ae3…` were inspected. It is a consumed-reference
development analysis, not fresh confirmation. Original source packets, graph
policies, learner outputs, reference ranks and the completed comparison remain
unchanged. No new source, learner, threshold or biological labels are added.

## Verified gap and existing method

The original binary co-context indicator gives the same value to a shared
model containing two measured genes and one containing most measured genes.
The standard resource-allocation index weights each shared neighbor by inverse
degree. We reuse installed **NetworkX 3.7 `resource_allocation_index`**, with
the native NetworkX CPU backend explicitly selected. No custom RA formula or
new correlation model is implemented.
Use `PYTHONHASHSEED=2026111301` for both preparation and evaluation, since the
native implementation sums an unordered common-neighbor set. This fixes
floating-point summation order without modifying the published algorithm.

For each existing arm, build a simple undirected bipartite incidence graph.
Gene nodes and exact source-version model nodes occupy different namespaces.
Add all 92 measured genes, including isolates. Every source membership appears
once; different revisions remain different context nodes. Pass the explicit
3,968 nonsyntenic gene pairs to the native function, avoiding its default
all-nonedge enumeration.

Each model degree is its fixed degree in the **full 92-gene arm**. It is not
rebuilt for a query or after chromosome/reference filtering. This is observed
cohort-local degree, not the complete biological pathway size. Source
incompleteness, correlated models, gene/product differences and reuse of
evidence remain unresolved by weighting.

## Fixed readout

Keep the exact original unsigned native GLS lexical-orientation ranks,
N=1…10, fractional boundary ties, common valid-measurement mask and all 92
queries. RA does not change which reference partners occupy the top N.

For each query g, observed weighted context is the sum of its RA scores at
those reference positions, including fractional tie weights. Expected weighted
context is `N × sum(RA(g,h) over eligible reference partners) / partner_count`.
Sum observed and expected scores over all 92 queries, and report their ratio,
the two absolute sums and means per selected query-partner slot. Zero source
score is valid; zero expected score makes enrichment undefined. Insufficient
reference partners makes the whole fixed-frame N point UNKNOWN.

RA scores are uncalibrated nonnegative affinities and may exceed one. Zero is
absence of shared observed context, not a biological negative. No accuracy,
edge probability, causal effect, physical binding or new PPI is inferred.

Reuse all 87 source arms, including the previously frozen twenty measured-frame
count controls and twenty measured-frame degree controls per treatment. Keep
all ten points and all legacy-control diagnostics. Report every control draw
and descriptive minimum/median/maximum envelopes; mixing, a uniform null and
confidence intervals are not established.

The project-specific descriptive rule remains fixed: a treatment is above all
declared comparators only if every one of its ten N points has defined
enrichment exceeding normalized and each of its forty own-treatment control
draws by more than 1e-12. This is not a statistical significance criterion.
There is no best-N, best-arm, best-draw, threshold, sign or scope selection.
Only the nonsyntenic unsigned primary domain is evaluated in this extension;
Jaccard and other new metrics are omitted.

Freeze this contract, implementation, native NetworkX source/version and exact
original source/reference inventories before calculating new RA weights.
Existing byte/source/frame verifiers continue to run; original raw-column
decoding and saved selections must reproduce the consumed reference exactly.

## Sources and claim boundary

- [NetworkX resource-allocation API](https://networkx.org/documentation/3.7/reference/algorithms/generated/networkx.algorithms.link_prediction.resource_allocation_index.html)
  and its released implementation define the reused score and graph constraints.
- [Zhou, Lü and Zhang 2009](https://doi.org/10.1140/epjb/e2009-00335-8)
  introduces the local-information resource-allocation index. This does not
  establish biological validity for Wiki memberships.
- [Wainberg et al.](https://doi.org/10.1038/s41588-021-00840-z)
  supplies the already consumed experimental reference and documents GLS,
  synteny and the meaningful interpretation of both signs. Its Jaccard use
  concerns ClusterONE module sets; it is not evidence that our source models
  are equally complete or independent.

This tests whether a known degree-aware interpretation feature gives more
useful contextual ordering under the same experimental readout. A positive
result would still require fresh task-matched validation before a biological
improvement claim or automatic pruning. The production graph is untouched.
