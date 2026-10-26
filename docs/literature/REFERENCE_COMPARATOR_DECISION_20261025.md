# Reference and comparator decision

October 25, 2026 (America/New_York). **Use the Lambourne human panel for a
bounded, retrospective assay-corroboration assessment of the frozen Pharos
lookup. Do not certify it as an independent prediction test, and do not start
another enrichment/model comparison yet.** This closes the current source-lineage
investigation with an explicit unresolved result. It does not turn missing
provenance into evidence of either independence or contamination.

No new assay outcome values were decoded, no experimental outcome table was
opened, no learner was run, and no frozen source artifact was changed in this
increment. Primary methods, official loader code and provider documentation
were inspected. No Brev instance is needed for this decision or the next local
protocol/adapter work.

## What is established

The [identity audit](../evaluations/LAMBOURNE_REFERENCE_AUDIT_20261023.md) fixes
3,222 published nominated unordered protein pairs and 3,173 exact author
accessions. The [completed Pharos lookup](../evaluations/LAMBOURNE_PHAROS_LOOKUP_20261023.md)
queries every accession under one declared profile: `pharos319`, confidence
parameter 400, maximum 5,000 PPI neighbors per protein. It resolves 3,172
accessions exactly, reconciles all returned counts and retains all nominations.

| Saved pair state | Pairs | Meaning |
|---|---:|---|
| Represented in queried Pharos PPI responses | 2,325 | Existing Pharos representation, irrespective of its unknown originating study |
| No match under that profile; both endpoints resolved | 895 | Bounded lookup absence, not measured noninteraction |
| No match; one endpoint unresolved | 2 | Incomplete identity coverage; do not convert to a negative lookup prediction |

The earlier 442 possible HuRI overlaps and seven consumed INMC overlaps remain
attached. These flags overlap other categories and are not independent counts.
The 825 fully resolved pairs without an observed match through the audited
routes are a diagnostic stratum, not an independently validated test set.

The selected endpoint is detection in the authors' human Y2H-v1 assessment.
The [paper's methods](https://www.nature.com/articles/s41467-026-70942-x)
restrict the tested proteins to matching experimental constructs and describe
selection from an earlier nomination set followed by intersection with the
published Zhang set. Thus the panel is selected, not a random proteome sample.
Its generic data-availability statement names IMEx accession `IM-30553`; the
scope of individual deposited human records was not established here. The
existing audit retains the figure-caption/methods assay-version discrepancy.

## Finite source-lineage audit

The missing link is **which exact provider files and evidence records produced
the deployed Pharos rows**. Finding a current upstream record or an old loader
does not establish that link.

| Route checked | Supported observation | Remaining limit |
|---|---|---|
| Saved Pharos responses and supported API metadata | The prior full audit found no reference property in 552,451 raw PPI views. Five outcome-blind pair-detail probes returned null evidence and interaction type. Unkeyed `dataVersions` returned five source categories, none for PPI. | Five probes do not characterize every possible detail row. The database label and retrieval time do not identify provider releases or experiments. |
| Official Pharos GraphQL code | The inspected public tree remains commit `3feb5ac7e450b3c6b767651f0fe1f39994085380`. The supported PPI projections and version-info implementation explain the available response fields. | A public commit is not an attestation of the deployed server or database build. |
| Official historical TCRD import code | Pinned commit `90d072154fa7afa1eca3dc3449dae709c72cf1b6` contains provider loaders and dataset/provenance insertion code. The STRING loader names a v11.0 combined-score file. The BioPlex loader names its v4a interaction list and historical updates. | These are historical import recipes, not a manifest binding `pharos319` to those files. The inspected TCRDpy3 tree does not supply replacement PPI loaders. |
| Study-detail preservation in those loaders | STRING loading retains the combined score rather than evidence-channel/publication records. The Reactome loader documents an input publication-reference column, but its `ins_ppi` call does not carry that column into the row. | This demonstrates a historical provenance-loss path; it does not prove that this exact loader generated current Pharos data or that every current row lacks references. |
| Upstream release/evidence documentation | STRING exposes versioned archives and evidence-set/publication relationships. BioPlex distinguishes named releases and cell lines. Reactome provides release archives and interaction exports. | Those resources could support a release-specific join once the actual Pharos inputs are known. Substituting today's upstream data would create a different baseline. |

The code references are the [Pharos PPI implementation](https://github.com/ncats/pharos-graphql-server/blob/3feb5ac7e450b3c6b767651f0fe1f39994085380/src/TCRD.js),
[version metadata implementation](https://github.com/ncats/pharos-graphql-server/blob/3feb5ac7e450b3c6b767651f0fe1f39994085380/src/models/versionInfo/versionInfo.ts),
[STRING loader](https://github.com/unmtransinfo/TCRD/blob/90d072154fa7afa1eca3dc3449dae709c72cf1b6/loaders/load-STRINGDB.py),
[BioPlex loader](https://github.com/unmtransinfo/TCRD/blob/90d072154fa7afa1eca3dc3449dae709c72cf1b6/loaders/load-BioPlexPPIs.py),
and [Reactome loader](https://github.com/unmtransinfo/TCRD/blob/90d072154fa7afa1eca3dc3449dae709c72cf1b6/loaders/load-ReactomePPIs.py).
The [TCRD README](https://github.com/unmtransinfo/TCRD/blob/90d072154fa7afa1eca3dc3449dae709c72cf1b6/README.md)
describes these as rebuild instructions and links database dumps. The linked
UNM download route was inaccessible in this review; no deployment-specific
dump manifest was obtained. This is a bounded access/search result, not a claim
that maintainers cannot provide one.

[STRING's version history](https://string-db.org/cgi/access) lists version
12.5 as current since September 29, 2026 and preserves older releases. Its
[evidence schema](https://string-db.org/help/database/) includes collections,
evidence sets and `sets_pubmedrefs`. Consequently, knowing that an old STRING
release predates the study would help only if Pharos's imported release and
subsequent updates were attested. Neither a currently missing study match nor
the historical loader's filename establishes that condition.

Provider semantics also prevent treating the bundles as repeated measurements
of one endpoint. [STRING](https://string-db.org/help/getting_started/) represents
functional associations. [BioPlex's release page](https://bioplex.hms.harvard.edu/interactions.php)
distinguishes AP-MS networks and cell lines. [Reactome's export documentation](https://reactome.org/download-data)
says its pathway-derived PPI export infers interactions among components of
complexes with four or fewer proteins. A bundle containing these sources does
not establish multiple independent binary-binding experiments.

**Closure:** study independence remains unresolved. No additional generic
provider download, API repetition or source search is required before making
this decision. Reopen the independence question only when an actual imported
release/build manifest or equivalent maintainers' evidence becomes available.
No message to maintainers or organizers was sent.

## Chosen task and comparator

The question is: **Within this fixed nominated human panel, how often is
existing Pharos representation accompanied by detection in the published
Y2H assessment?** This evaluates concordance with one external assay endpoint.
It does not grade all Pharos relations as true or false.

Use the existing saved pair lookup as the primary comparator, without a new
pull or modified confidence cutoff. Preserve the three lookup states above.
On assay-evaluable pairs whose two endpoints resolved, the presence comparator
is fixed at 1 for represented pairs and 0 for bounded no-match pairs. Here 0 is
a lookup output, never a biological negative label. The two unresolved pairs
remain in the coverage denominator and receive no comparator score.

The primary report should show the full cross-tabulation of assay status and
lookup state, with detection proportions and denominators. Show the exact
provider bundles and existing HuRI/INMC exposure flags as predeclared descriptive
strata. Do not call the represented/absent difference an effect of Steward;
these groups were not randomized or matched for nomination mechanisms.
Do not restrict the primary assessment to Pharos-absent pairs: that would make
the presence comparator constant by construction.

Keep recorded STRING scores and BioPlex quantities separate as source metadata.
There is no selected combined score, new learned ranker or provider-specific
threshold sweep. Missing properties stay missing, including possible zeros
omitted by the documented API resolver. No assay-informed score selection is
permitted on this panel. The prior INMC test remains consumed and unchanged.

## Enrichment decision

**No-go for a new predictive graph enrichment at present.** The completed
retrieval establishes much more existing representation than the early small
graph suggested. It does not identify an omitted source that is both relevant
to this endpoint and demonstrably additional. The previous narrow GO-hierarchy
comparison already failed to demonstrate a consistent benefit; this panel must
not become another opportunity to tune that change until a favorable score
appears.

**Go for the bounded baseline corroboration report, then a qualified evidence
overlay if useful.** After the report is frozen and run, assay observations may
be published with their study, construct and assay context as a separately
identified evidence layer. Once used for that layer, they cannot also be held
out to prove its accuracy. A nondetection must not automatically delete a
Pharos functional association, co-complex relation or interaction measured in
another context. Whether the overlay adds useful information can be measured
as new qualified observations and clearer source trace; it is not a demonstrated
prediction improvement.

A future incremental-prediction claim needs a specific, independently justified
change and a newly declared comparison. If extra information is added, compare
Pharos, simple addition of that same information, and Steward's qualification
of it under the same task, learner, candidates and budget. An additional model
or dataset is not the missing framework component today.

## What must be frozen before opening outcomes

**Subsequent execution on October 25:** the
[completed corroboration report](../evaluations/LAMBOURNE_CORROBORATION_20261025.md)
records the tested author adapter, sealed comparator, first-access receipt and
all outcomes. The panel is now consumed. The requirements and unopened status
below describe the original pre-execution decision, which remains preserved.

This decision is the design specification, **not yet an executed evaluation
freeze or an assay-label adapter**. The next local increment should produce one
machine-readable, hash-bound protocol and reuse the authors' preprocessing:

1. Bind the audited 3,222-pair inventory, original identities/construct mapping,
   author commit, source-table bytes, Pharos lookup receipts, and every exposure
   flag. Keep controls outside the nominated population.
2. Bind the author's human preprocessing and resolve its nullable confirmation
   behavior mechanically. Explicit `Positive` and `Negative` are candidates for
   evaluable observations; failed tests, autoactivators, failed confirmation,
   ambiguous confirmation and unexpected states remain separate. Verify the
   processed representation against the raw author export without inventing
   an assay threshold. If consistency fails, stop scoring and report the issue.
3. Fix one row per unordered nominated pair, the identity/assay eligibility
   matrix, lookup-state rules and counts of every exclusion. Retain excluded
   rows in the audit output. No post-outcome mapping repair or favorable-subset
   selection is allowed.
4. Freeze the cross-tabulation/detection-rate report, provider/exposure strata,
   any optional ranking metric, and zero-denominator behavior. Use descriptive
   finite-panel summaries as the primary result. Do not attach an independence-
   assuming pair bootstrap or claim between-study uncertainty from one study;
   a later inferential analysis needs an explicit shared-protein/dependence model.
5. Test the adapter with invented cases including all failure states, duplicate
   headers, nullable confirmation, swapped endpoints and unresolved proteins.
   Seal the comparator outputs before the first real outcome decode. There is
   no training, hyperparameter selection or GPU step in this assessment.
6. Record any already viewed public aggregate results, open the outcomes once,
   write the unchanged result even if concordance is poor, and mark the panel
   consumed. Do not describe this retrospective public panel as prospectively
   hidden or as official challenge gold.

The earlier [author-code audit](../evaluations/LAMBOURNE_REFERENCE_AUDIT_20261023.md#reusing-the-authors-definitions)
already recovered the upstream transformation. The remaining implementation
gap is a tested local adapter and freeze receipt, not a new biological labeling
protocol. Failure-state counts and eligibility are deliberately still unknown.

## Allowed conclusions and framework implication

Allowed after execution: coverage under the declared Pharos profile; assay
concordance on the fixed eligible population; source/context gaps; and the
engineering ability to preserve and export qualified observations. Not allowed:
certified study independence, proteome-wide accuracy, automatic invalidation of
Pharos edges, oncology treatment validity, official challenge performance, or
an enrichment benefit that has not been tested.

The backbone already supports bounded retrieval, graph publication, provenance,
review, replay and comparison artifacts. This decision requires no new graph
store, cloud service or agent framework. Remaining design is concentrated at
evaluation contracts, qualified exchange, bounded agent selection and the
filter/update/user-task acceptance criteria described in the
[build plan](../BUILD_PLAN.md). The organizer's actual gold artifact and label
contract remain an external dependency, not something this assay can replace.

Supporting public-code snapshots and SHA-256 receipts are saved locally under
`runs/reference_comparator_decision_20261025/` (ignored). The preserved
experimental source tables and earlier comparison artifacts were not edited.
