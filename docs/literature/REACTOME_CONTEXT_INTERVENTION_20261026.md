# Selected biological development comparison: Reactome context

**Current status — November 13:** this is the preserved intervention-selection
record. The [fixed Reactome comparison](../evaluations/REACTOME_CONTEXT_COMPARISON_20261026.md)
subsequently completed on the consumed INMC panel, with mixed seed effects and
no consistent incremental benefit. The selected/not-executed status and gates
below describe selection time; they are not a new freeze or fresh holdout.

October 26, 2026 (America/New_York). **Selected, not executed or frozen.**

Add the exact Reactome protein-to-pathway memberships already retrieved from
Pharos to the existing restricted Pharos/GO R-GCN graph. Compare that addition
against the same learner and baseline on the consumed INMC assay panel. This is
one fixed retrospective development comparison. It is not a new data source,
an independent validation, a graph-pruning rule or a claim of improvement.

The [selection record](../evaluations/reactome_context_intervention_20261026_selection.json)
binds the checked source inventory, previous graph and exposure receipts,
historical comparison, intended controls and remaining preflight gates. No old
protocol or result is changed by this decision.

## Why this intervention fits

Reactome describes biological processes through reactions and the entities
participating in them. Its [2026 primary paper](https://academic.oup.com/nar/article/54/D1/D673/8326464)
supports its use as functional context. The [official data model](https://reactome.org/documentation/data-model)
distinguishes physical entities, complexes, molecular forms and compartments.
Consequently, two proteins sharing a pathway need not bind each other directly.
The [official downloads](https://reactome.org/download-data/) also distinguish
pathway memberships from separately derived protein interaction exports. We
select the former only; we do not turn co-membership into interaction labels.

Co-pathway information is an established candidate feature for PPI prediction.
The [ppiPre primary paper](https://pmc.ncbi.nlm.nih.gov/articles/PMC3851814/)
tests it separately for binary and co-complex interaction endpoints. We inspected
the corresponding `KEGGSim` function and package metadata at the
[pinned CRAN mirror commit](https://github.com/cran/ppiPre/tree/7d866f8362cbec234ca6a69768fef234ceb9f81c).
That method uses KEGG, not Reactome, and its published results do not establish a
benefit on this human Y2H panel. The inspected package is GPL-2, version 1.9; it
was not installed and its code is not copied into this MIT repository. It supplies
methodological motivation rather than a claimed reproduced baseline.

The verified implementation gap is in our learner projection. The workbench and
bounded standard exporter already represent exact Reactome pathway membership,
but `scripts/prepare_inmc_graphs.py` excludes all non-GO context. The saved uniform
Pharos retrieval contains 11,138 distinct Reactome product/pathway memberships
covering 982 products and 1,490 human pathway IDs. Every counted row has an exact
`R-HSA-...` source ID, and the checked source has no stable-ID/label conflict.
These are available source counts, **not yet approved learner-edge counts**.
The actual projection and endpoint coverage remain unknown until preflight.

The hypothesis is specific: adding these functional-context connections may
improve ranking of recorded Y2H detection over the unchanged restricted graph.
It is plausible, not a prediction guarantee. The four eligible IntAct development
observations cover only two pairs and are unsuitable for testing predictive gain
against themselves. GO qualification exclusions are already present in both
existing arms. Provider confidence quantities have different meanings and are
not a common probability of Y2H detection. Those alternatives are not added to
this comparison.

## Fixed comparison selected

| Property | Selected rule |
| --- | --- |
| Baseline | Existing HuRI scaffold, original gene-to-reviewed-product context and restricted qualified Pharos GO annotations; no GO hierarchy addition |
| Intervention | Baseline plus only exact Reactome protein-to-pathway memberships from the saved Pharos snapshot |
| Arms | Two; this is the simple-addition test itself, with no invented qualification/filter arm |
| Population | The original 1,751 complete-scored, off-diagonal INMC pairs, with unchanged assay eligibility and exclusions |
| Learner | Existing native PyKEEN 1.11.1 R-GCN integration; no new model or hyperparameter search |
| Budget | Seeds 17, 43 and 101; 20 epochs and 500 optimizer updates per arm/seed; six full runs, contingent on resource preflight |
| Primary comparison | Paired change in average precision (AP), intervention minus baseline; report its arithmetic mean and every seed's change |
| Secondary reporting | ROC-AUC, original context-coverage strata and descriptive leave-one-original-gene-out influence |
| Scoring | The same original eligible pairs and bidirectional score aggregation; missing/nonfinite predictions block headline metrics |

Both arms must use the same union entity and relation ledgers, positive
supervision, original identities, development split and equivalence masks. New
pathway nodes and the membership relation must be in both vocabularies even
though their membership edges occur only in the intervention arm. The baseline
must be rerun within that paired vocabulary; historical predictions cannot
substitute for it. Reproduce matched initialization, positive minibatch schedules
and update counts using the existing runner's supported library settings.

Retain the original three-layer, 32-dimensional, four-basis R-GCN, SoftplusLoss,
Adam learning rate 0.001, batch size 4,096 and 16 typed negative proposals per
positive. Keep the previously tested disabled-dropout and native ordinary
batching paths. No early stopping, source threshold search or post-result seed
selection is allowed. All direct Pharos PPI records remain excluded from both
arms. Add no IntAct observations, current GOA annotations, inferred protein-pair
edges, assay labels, published-positive flags or derivatives of those outcomes
to the predictor inputs.

Predeclare a **descriptive coverage-only diagnostic**, not a third trained arm:
score each candidate by the number of its original gene endpoints with at least
one eligible Reactome membership through any frozen reviewed-product mapping
(0, 1 or 2). Use the same 1,751-pair denominator and report AP/ROC-AUC with the
ties intact. Zero means missing membership context, not evidence of biological
absence. This diagnostic is computed without fitting to outcomes; it checks
whether annotation availability alone ranks the selected assay endpoint. Neither
it nor a positive mean R-GCN AP change identifies a causal biological mechanism.

## Previous negative results remain relevant

The [archived growth comparison](../EXPERIMENT_HISTORY.md) at immutable commit
`602681bc82417720e7a465bd19db7a7500c88f38` tested pathway-only ridge ranking of
continuous DepMap growth against pathways plus expression and BioPlex. On 256
reserved genes it reported Spearman 0.2635 versus 0.2607, failed its improvement
rule, and had a higher coverage-only result of 0.2961. That failure is not
overturned here. The selected task differs in endpoint (recorded Y2H detection),
representation (typed graph context), learner (R-GCN) and comparator (adding one
family to the same restricted graph). The earlier GO hierarchy comparison also
remains unchanged: it showed no consistent gain across the three seeds.

## Gates, interpretation and stopping

Before training, verify the saved source manifests, exact membership mapping,
duplicate handling, unchanged candidates/eligibility and absence of direct
protein-pair inputs or outcome derivatives. Record unresolved qualifications
rather than silently inferring molecular form, direct binding or study
independence. Verify message passing and paired invariants on synthetic data,
perform an intended-runtime resource check, then seal a new execution packet
with code, source, graph, scoring and runtime hashes. A synthetic or resource
check may not become an undeclared assay-scoring run. This selection document
does not satisfy that execution freeze.

The INMC outcomes were first accessed on October 23 at 15:10:21 UTC. They are
consumed development material; freezing another protocol does not make them
unseen. The current Pharos snapshot postdates the assays, and its Reactome import
release and underlying study lineage remain unverified. Removing direct PPI
edges does not certify absence of reference-derived context. The
[recent biomedical KG leakage study](https://academic.oup.com/bioinformatics/article/42/8/btag608/8767164)
supports distinguishing internal comparisons from independent generalization.

Execute this one fixed comparison after preflight, report all paired changes,
and stop. Invalid graph/control bindings or missing scores block results. Fix
integration faults with synthetic controls and preserve failed attempts; do not
alter the cohort or learner in response to the assay scores. Mixed, negligible
or negative changes close this candidate without a sweep. Consistent favorable
changes would support only an internal development effect and the case for
separate independent confirmation. They would not establish scientific truth,
new biological knowledge beyond Pharos or permission to prune source edges.

No learner implementation, fitting, new scoring, new IntAct adoption or reserved
IntAct interaction access occurred in selecting this intervention. Local source
review needs neither Brev nor AWS; any paid-compute run must first be announced
to the user.
