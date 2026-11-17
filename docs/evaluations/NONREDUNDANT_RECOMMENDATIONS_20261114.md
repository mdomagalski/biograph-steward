# Nonredundant recommendations from existing predictions

**Completed source-frozen development assessment.** This is a bounded
recommendation-selection task using the existing DeepGO-SE and strict-source
LocalPlus forecasts. It tests whether excluding dated baseline annotations
before applying a three-term review budget reveals useful support farther down
the same rankings. It does not train a new predictor, correct the official
CAFA benchmark or change the application graph/default.

## Established task and verified implementation gap

The [CAFA5 primary preprint, version 2](https://pmc.ncbi.nlm.nih.gov/articles/PMC13142333/)
describes a strong baseline containing annotations present at the initial time
regardless of evidence category, while benchmark known-term exclusion follows
the admitted reference categories. Its discussion identifies conditioning on
existing annotations as an opportunity. This is a preprint, not a peer-reviewed
endorsement of our particular selector. Existing nonexperimental annotation
later receiving experimental support is a valid benchmark event, but it is not
necessarily a new function discovered beyond prior biological knowledge.

The [previous complementarity assessment](METHOD_COMPLEMENTARITY_20261114.md)
used both methods' original positive-score top three, then measured how many
selected terms were absent from the baseline. That accurately described the
existing shortlists, but it did not test a selector designed to spend review
slots on functions absent from that baseline. A baseline-covered high-ranking
term can consume a slot even when other supported terms remain below it.

The remedy uses existing APIs rather than a new prediction or integration
framework: the pinned [CAFA-evaluator-PK implementation](https://github.com/claradepaolis/CAFA-evaluator-PK/tree/e386b085e204ccfbd75a4f52c1a8b25987d8b465),
native canonical/alternative-ID handling, `fill` closure, historical ontology,
IA and terms of interest, existing full-score ordering and three-slot helper,
and the previously qualified None/PK count branches. No learned fusion,
reference-trained reranker, parameter sweep or extra source is introduced.

## Fixed selection and original scoring

Three saved readouts are retained for each method/task/aspect:

1. **Original top three:** unchanged prior selection, exactly reconstructed
   against its source-pinned identities and native protein order.
2. **Filtered after top three:** remove baseline-covered terms from that
   original list; leave unused slots empty. This reconstructs the old
   baseline-absent yield, without replenishing the control.
3. **Baseline-aware before top three:** exclude the native PK known closure
   plus the dated baseline closure before selecting from the same complete
   positive-score ranking. Preserve the original canonical-ID tie-break.

For NK/LK the original scoring branch remains `exclude=None`; an empty known
object is not substituted. The baseline exclusion is a **ranking** mask. It is
never subtracted from scoring truth, and it never changes the original eligible
protein population. Every original case remains, including cases whose entire
future reference is already baseline-covered. Numeric hashes guard the original
reference matrices; native full-frame and separate per-protein six-column
counts must agree.

All twelve original strata remain visible, with two methods in each:

| Frame | Native task | BPO eligible N | MFO eligible N | CCO eligible N | Scoring exclusion |
|---|---|---:|---:|---:|---|
| Original cohort | PK | 833 | 525 | 445 | Original native known-at-t0 closure |
| Additional cohort | PK | 2,826 | 2,192 | 1,450 | Original native known-at-t0 closure |
| No knowledge | NK | 44 | 39 | 118 | Native None branch |
| Limited knowledge | LK | 227 | 60 | 197 | Native None branch |

These are aspect-specific native eligible populations, not disjoint studies or
counts of Pharos Tdark proteins. Original IA eligibility is retained separately.
The benchmark-wide official terms-of-interest vocabulary was already exposed
and remains a ranking qualification. **No per-target future-reference labels
enter selection**, but this is not an unbiased full-application deployment
test or a fresh holdout.

## What constitutes useful evidence

The endpoint is baseline-absent curator-supported selected terms divided by
`3 × original native eligible N`. A residual-positive subset never replaces N.
The complete native future truth and known-term rules remain unchanged.

Every old baseline-absent selection is contained in the new selection. Its own
supported yield therefore cannot decrease by construction. A positive
before-versus-after difference, or an interval computed from that difference,
would not establish a better underlying model. **No own-variant confidence
interval or model-superiority claim is produced.**

Instead, the report shows the cost and utility of replenishment: added slots,
added curator-supported terms, additional reference-unmatched proposals,
marginal support fraction among added slots, returned-list PPV, recall, unused
budget, mean IA and ancestor-related redundancy. PPV can fall even when fixed
budget yield rises. Reference-unmatched proposals remain unresolved rather
than asserted to be biologically false.

The genuine method comparison is baseline-aware DeepGO minus baseline-aware
LocalPlus under identical original populations and review budgets. All twelve
paired comparisons are retained. Four MFO contrasts are the designated focus;
eight BPO/CCO contrasts remain secondary. Conditional paired percentile
intervals reuse the existing 2,000 protein resamples, seed 20261113, without
multiplicity adjustment or a new bootstrap/threshold search. Unlike the
own-variant comparison, this method contrast has no subset guarantee.

Residual future-reference pairs, positive- and zero-opportunity case counts,
and the reference-aware sum of `min(3, residual truth count)` describe label
headroom only. That oracle uses future knowledge and is never a selector,
denominator or attainable performance claim. Baseline membership means the
canonicalized released forecast closure; it does not recover original literal
GOA/GAF provenance, establish assay evidence or prove discovery.

## Source qualification and delivery

### Completed comparison

The [complete aggregate report](nonredundant_recommendations_20261114/report.html)
retains all 24 method/task/aspect rows, 12 opportunity strata and 12 genuine
method contrasts. The question is not devoid of reference opportunity:
1,900 of the additional cohort's 2,192 original MFO proteins have at least one
later curator-supported term absent from the frozen baseline. Together they
have 4,799 such protein/term pairs, including ontology-propagated ancestors.
This is annotation headroom in the exposed reference, not 4,799 directly
curated assertions or new biological discoveries.

MFO replenishment has a substantial unresolved review cost:

| Frame | Method | Supported, after-filter → before-filter | Added supported | Added reference-unmatched | Support among added slots |
|---|---|---:|---:|---:|---:|
| Original PK | DeepGO | 92 → 111 | 19 | 423 | 4.30% |
| Original PK | LocalPlus | 110 → 122 | 12 | 276 | 4.17% |
| Additional PK | DeepGO | 358 → 456 | 98 | 1,814 | 5.13% |
| Additional PK | LocalPlus | 421 → 467 | 46 | 1,181 | 3.75% |
| NK | DeepGO | 9 → 18 | 9 | 65 | 12.16% |
| NK | LocalPlus | 14 → 17 | 3 | 35 | 7.89% |
| LK | DeepGO | 22 → 37 | 15 | 100 | 13.04% |
| LK | LocalPlus | 30 → 34 | 4 | 65 | 5.80% |

These own-variant increases are expected from containment; filling more review
slots is not evidence of better model accuracy. Reference-unmatched proposals
are not established biological errors. In the genuine baseline-aware MFO
method comparison, all four conditional intervals cross zero:

| Original population | DeepGO − LocalPlus supported slots / 3N | Conditional 95% interval |
|---|---:|---|
| Original PK, N=525 | −0.00698 | [−0.02349, 0.00825] |
| Additional PK, N=2,192 | −0.00167 | [−0.00897, 0.00623] |
| NK, N=39 | 0.00855 | [−0.04274, 0.06838] |
| LK, N=60 | 0.01667 | [−0.05556, 0.10000] |

The useful conclusion is a task distinction: benchmark annotation recovery,
nonredundant recommendations and biological discovery are different claims.
The selector exposes more supported suggestions, with low marginal reference
support and no established method winner. It is retained as a research utility;
it is not an automatic acceptance or pruning rule, and no app default changes.

The fixed source packet is `717683e2bfe4f9f09e242b0566004de8f02d5f2b1c0e01e766e4b46936feadc2`;
freeze FILE SHA256 is `f07977f6ee115953315ea21bc9fbeddece7e7b137685950043f8ee6fdbe1cd83`;
complete source report FILE SHA256 is `5d417f7d7b728e6f335e8f54ca514603f98e894a00ea6235ae0011e5153a1c31`.
The actual pinned runtime passed all ten required synthetic checks before the
freeze. The [independent numerical audit](nonredundant_recommendations_20261114/independent_numeric_review.json)
also passed: all 24 full-score rankings, 72 original/post/aware six-column
arrays, original orders/masks/populations, opportunity and review-cost
partitions, and all 12 saved paired-bootstrap distributions were reproduced.
It reuses the official parsers with separate ranking and count arithmetic;
it supplies no new biological labels or independent study replication.
Audit FILE SHA256: `61d35b49c79126dfac5d93d6b3a18d35fdb8a5e36ef7c2e4fd9924d437bca9c6`.
The initial audit's `OSError` receipt is preserved. The identical reviewer
passed with its temporary directory on the larger data volume; no scientific
rule, input, numeric tolerance or result was changed.

The fixed producer is
[baseline_aware.py](../../tools/deepgo_reference/baseline_aware.py).
The final freeze binds its source packet, original overlap report/freeze,
forecasts, masks, ontology/IA/TOI, runtime and successful required native fixture
before the newly declared endpoint values are opened. No earlier reference
exposure is erased: these are consumed CAFA5 development outcomes.

Five invented pure fixtures test future-label-independent selection, exact
ordering/known masking, containment, additional unmatched cost, zero-residual
case retention and shape guards. A separate required fixture exercises the
actual pinned evaluator's None and PK scoring branches. These mechanical
checks validate integration; they do not establish scientific accuracy.

The aggregate-only
[publisher](../../tools/deepgo_reference/publish_baseline_aware.py)
reads only a sealed report and freeze supplied explicitly by the operator. It
does not follow their private paths or load reference rows, forecasts, selected
identities, model weights or per-protein numeric files. It verifies all 24
method rows, 12 opportunity strata, 12 saved method intervals, original native
count/order gates and budget/support/cost partitions. The existing shared
sanitizer removes operator paths while retaining source hashes; public HTML and
JSON preserve all favorable, unfavorable and inconclusive aggregates.

**Remaining limits:** reused development labels, incomplete curator truth,
hierarchical GO dependence, unequal predictor source/training histories and
unreconstructed training/homology overlap still apply. A useful selector would
show that the existing forecasts can allocate a bounded review budget more
productively for this explicit task. It would not establish independent
whole-graph biological accuracy, calibrated acceptance probabilities,
cross-organism transfer, automatic biological pruning or newly verified facts.

No accepted annotation, app/default, historical primary adoption rule or source
graph changes follow automatically. Raw arrays stay on the existing Brev
storage; this comparison uses CPU and memory without new model inference or
fresh source retrieval.
