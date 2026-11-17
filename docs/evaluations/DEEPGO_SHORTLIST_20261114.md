# Fixed-budget function shortlist comparison

**Completed; no default change.** This development comparison measures how
many later curator annotations each method supports within
the same three-slot review budget per protein/aspect. It reuses the previously
exposed 6,100-protein CAFA5 PK forecasts and references. It is neither a fresh
validation nor a replacement for the failed original BPO adoption rule. The
retained app profile and accepted graph remain unchanged. The
[DeepGO method record](DEEPGO_SE_20261114.md) retains checkpoint, supervision,
sequence-date and runtime differences; this review-budget comparison does not
isolate sequence, topology or ontology-axiom contributions.

The existing app orders positive candidate scores by descending value, breaks
ties by canonical GO ID and displays up to three per aspect, excluding known
terms and roots. Its code does not provide a cohort-wide matched-budget test.
The earlier Fmax and fixed-0.5 comparisons allow different prediction counts,
so they do not answer this review-budget question.

The pinned CAFA-evaluator-PK commit
[`e386b085e204ccfbd75a4f52c1a8b25987d8b465`](https://github.com/claradepaolis/CAFA-evaluator-PK/tree/e386b085e204ccfbd75a4f52c1a8b25987d8b465)
identifies package 1.2.1. Its `max_terms` documentation explicitly describes an
input-order cap before propagation, without score sorting. The parser also
checks the existing count with `<=`; it is not a strict post-closure top-k
selector. That option is therefore not substituted for the app's ranking rule.
The unchanged native alias, ontology, known-mask and confusion APIs remain
reusable.

Ranked top-n precision/recall has precedent in
[Wang, Cao and Cheng (2013)](https://doi.org/10.1186/1471-2105-14-S3-S3), while
[information-theoretic evaluation](https://academic.oup.com/bioinformatics/article/29/13/i53/195366)
addresses weaknesses of unweighted ontology scores. The older top-n study lets
tied confidence groups exceed n; this comparison instead adapts strict
cardinality to the existing three-slot interface. It is not a replication of
that paper or a new CAFA official metric. A
[user-centered protein-function study](https://academic.oup.com/bioinformaticsadvances/article/2/1/vbac057/6670646)
also cautions that displayed-list utility and aggregate benchmark rankings are
different assessments.

Both unchanged full joined forecast files pass through the same official 2023
canonical/alternative-ID parser and `fill` propagation. Candidate selection
then removes native roots/orphans, known-at-t0 closure and terms outside the
same terms-of-interest file for both methods. It ranks the remaining positive
scores with the existing deterministic tie-break and retains at most three.
No propagation occurs after selection: that would exceed the review budget.
This is a **benchmark-qualified shortlist**, not a claim to reproduce every
literal raw term in today's app display. No score threshold, k sweep,
case-specific prompt, new model or future-label-based ranking is introduced.

The designated focus is molecular function in both existing cohorts; BPO and
CCO remain visible. The primary endpoint is **curator-supported slots per
fixed three-slot budget**, TP divided by three times the native ordinary
eligible population. Abstentions leave slots unused; missing annotations and
unused slots are not asserted to be false biology. Precision among returned
candidates, recall, F1, coverage and IA-weighted readouts remain distinct.
Molecular function was designated after the earlier six-aspect point results
were known, so this is explicitly exposed-label development work.

Three related ancestor/descendant terms are not three independent discoveries.
The report therefore retains descriptive counts of ancestor-related pairs
within each shortlist, mean IA per returned term and supported IA per fixed
budget. Directed reachability uses the same native child-to-parent graph and
[SciPy 1.13.1 breadth-first search](https://docs.scipy.org/doc/scipy-1.13.1/reference/generated/scipy.sparse.csgraph.breadth_first_order.html).
These diagnostics do not filter, reorder or optimize the shortlist.

Native one-threshold confusion counts are reused without changing their
implementation. All six ordinary eligible frames and their IA eligibility
must equal the earlier reference contract. Six paired difference intervals
use the official
[SciPy 1.13.1 bootstrap API](https://docs.scipy.org/doc/scipy-1.13.1/reference/generated/scipy.stats.bootstrap.html),
with paired sampling, 2,000 draws, seed 20261113, a 95% percentile interval and
bounded batches. These conditional protein intervals are not multiplicity
adjusted and do not remove source, graph or study dependence. No automatic
consumer/default change follows from them.

## Completed fixed-budget results

The [complete static report](deepgo_shortlist_20261114/report.html) and
[sanitized aggregate](deepgo_shortlist_20261114/report.json) retain all 12
profile/cohort/aspect rows, six paired differences, native checks and specificity
diagnostics. No partial endpoint values were opened or used to change the
frozen selection rule. All whole-frame native ordinary/IA six-column checks
passed the predeclared scale-aware raw-count tolerances. Raw weighted sums can
differ at floating-point reduction precision; these checks do not replace or
relax the earlier Fmax-curve agreement gates.

| Cohort / aspect | DeepGO supported slots / 3-budget | LocalPlus supported slots / 3-budget | Difference | Paired 95% interval |
| --- | ---: | ---: | ---: | --- |
| Original / BPO | 0.172469 | 0.205682 | -0.033213 | [-0.052021, -0.014806] |
| Original / MFO | 0.132698 | 0.124444 | +0.008254 | [-0.011429, 0.027937] |
| Original / CCO | 0.227715 | 0.268914 | -0.041199 | [-0.068914, -0.011985] |
| Additional / BPO | 0.183770 | 0.206063 | -0.022293 | [-0.031965, -0.012385] |
| Additional / MFO | 0.138686 | 0.118461 | +0.020225 | [0.010489, 0.030417] |
| Additional / CCO | 0.293103 | 0.315172 | -0.022069 | [-0.040230, -0.004368] |

The designated MFO comparison is **positive only in the additional cohort's
interval**. The original cohort's interval crosses zero. All four BPO/CCO
intervals favor LocalPlus. The earlier positive MFO Fmax signal therefore does
not establish a consistent top-three benefit across both existing cohorts.
These are different, source-declared questions; the fixed-budget result does
not replace the Fmax result or its failed original BPO adoption rule.

Both methods fill approximately 99–100% of the three-slot budget, so the
observed differences are not explained simply by one method leaving many
slots empty. Precision among returned candidates remains separately visible in
the static report; it is not equated with the fixed-budget yield or whole-graph
scientific accuracy.

MFO shortlists often contain related concepts: DeepGO has an ancestor-related
pair in 388/525 original lists and 1,652/2,192 additional lists; LocalPlus has
351/525 and 1,490/2,192. Mean IA per returned MFO term is 2.0591 versus 2.0861
(original DeepGO versus LocalPlus) and 1.9252 versus 1.9911 (additional).
These diagnostics describe redundancy and specificity under the frozen
benchmark ontology. They neither prove a causal explanation nor make related
terms independent discoveries. No redundancy filter or reranking was fitted to
these outcomes.

The completed source report FILE SHA-256 is
`1c796671a97e13f75ef71e9a83f1d88329925195ad61965046dfdec2b279f074`.
The source freeze FILE SHA-256 is
`b224094b52bd7c810d29a10c8c67037093835e9b1f5d9786665cee08fb558830`.
The original unexecuted preparation is preserved separately; the executed v2
added full-frame native count equivalence without changing ranking or metric
recipes. Raw forecasts, reference rows and numeric per-protein arrays remain
on Brev. No new DeepGO consumer, accepted graph fact or default is introduced.
