# Biological comparison scope

October 27, 2026. **The fixed retrospective component comparison is complete.**
The [executed evaluation](evaluations/STRING_COMPONENT_COMPARISON_20261027.md)
reports AP 0.172827 → 0.190056 on 2,676 measured human Y2H pairs, with lower
physical-overlay numeric coverage. This document preserves the scope selected
before whole-panel access. General framework expansion and UI redesign were
outside the increment. The result does not establish independent validation
or a Steward-specific improvement.

## Question and actual comparison

**Does selecting STRING's physical overlay change the ranking of recorded
human Y2H-v1 detection compared with its functional scores, on the same
published candidate pairs?**

Use native STRING 12.5 scores, without fitting a new predictor or inventing a
confidence formula. The supported typed API returns functional-network rows
with physical annotations; this is **functional retrieval versus its physical
overlay**, not yet a demonstrated comparison of two complete native networks.
The [official API](https://string-db.org/help/api/) documents that boundary.
One request for the already consumed TAS1R2–TAS1R3 pair verified the actual
24-column schema, reciprocal rows and both native scores. Their equality on
that one pair is a capability check, not a biological result.

| Representation | Role |
|---|---|
| STRING 12.5 `functional_combined_score` | Native functional ranking comparator |
| `physical_combined_score` in the same typed response | Question-specific physical-overlay comparator |
| Existing Pharos pair-presence lookup | Historical descriptive anchor; different release/projection, not a matched third arm |
| Original measured Lambourne outcomes | Evaluation reference only; never inserted as evidence for these candidate pairs |

The reference measures detection by specified constructs/assay conditions.
STRING physical scores include predicted proximity/co-complex association, not
a guarantee of direct binding. Their usefulness for this assay is precisely
what is being tested. Nondetection is not a universal biological noninteraction.

The [Wright interactome evaluation](https://link.springer.com/article/10.1038/s44320-024-00077-y)
supports task-specific comparison and coverage controls. Its
[author code](https://github.com/sarah-n-wright/Network_Evaluation_Tools) does
not supply independent experimental truth for our panel or prescribe all of
our evaluation boundaries. The present application of those principles is a
local development study.

## Fixed population and source roles

Retrieve predictor inputs for **all 3,222 original nominations / 3,173 exact
UniProt accessions**. Preserve the original source row, AD/DB constructs,
exclusions, source resolution and HuRI/INMC exposure flags.

The existing author-consistent adapter supplies **2,676 assay-eligible pairs**:
376 detections and 2,300 nondetections. The 546 other nominations remain
accounted for: 27 test failures, 41 autoactivators and 478 failed sequence
confirmations. No exclusion or replacement is selected by a new score.

The old Pharos comparison covers 2,674 eligible pairs; its two unresolved
pairs remain eligible for the native STRING component if their STRING
identities resolve. Do not inherit a Pharos-specific exclusion into the new
source assessment. The old lookup contains 2,325 represented pairs, 895 bounded
no-matches and two unresolved pairs across all nominations.

All these outcomes were consumed in the earlier assessment. This study can
measure a retrospective task-specific ranking difference, with reference
overlap limits. It cannot become an unseen validation by writing a new freeze.
Report the full population and the pre-existing HuRI/INMC exposure strata;
an unflagged pair is not certified independent of current STRING.

The four unopened IntAct studies stay separate: their selected task is source
fidelity. No new oncology, causal, proteome-wide or organizer-score claim is
added to this comparison.

## Mapping, coverage and scoring boundaries

The following boundaries were fixed before whole-panel scoring and are now
implemented and tested in the [capture/scoring workflow](STRING_COMPONENT_COMPARISON.md):

1. Preserve exact input accessions and isoforms. Use the official STRING mapping
   output as a **locus-representative correspondence**, not sequence/construct
   identity. Keep missing/ambiguous mappings and two different inputs collapsing
   to one representative explicit. Do not select a convenient mapping by assay
   outcome or gene label.
2. Use `https://version-12-5.string-db.org`, species 9606, `required_score=0`,
   `network_type=functional`, `network_flavor=typed`,
   `typed_physical_edges=1`, `typed_regulatory_edges=0`, `add_nodes=0`
   and deterministic query batches covering every
   nominated pair. Save complete responses/parameters. Verify symmetric duplicate
   rows agree; they are one provider prediction, not two experiments.
3. Keep explicit numeric zero, no row returned by a validated complete query,
   physical `-`, unresolved mapping and ambiguous mapping as distinct states.
   The documented `-` combines absence/below-threshold possibilities; do not
   resolve those possibilities without further source evidence. Retrieval,
   truncation, species or schema failures stop the comparison rather than
   becoming missing evidence.
4. Primary metric: **full-panel retrieval ranking with unranked pairs tied
   last**, on the same 2,676 eligible pairs. Native numeric scores retain their
   order, including zero. Legitimate unranked states use a separate ordinal
   sentinel below every native score. This is a fixed operational retrieval
   policy, not an inferred confidence, biological negative or necessarily
   conservative estimate. Preserve raw state/score beside the metric input.
5. Before joining outcomes, record the native score/state differences across
   both views. Identical ranking inputs are a no-op, not a reason to add another
   model or tune the source. Use the existing scikit-learn average-precision implementation; keep ties
   intact. Report per-view explicit-numeric/mapping coverage and every unranked
   state, plus a secondary comparison restricted to the same jointly numeric
   pairs. That conditional result cannot replace the full-panel denominator.
   An arm with no explicit numeric support is unscorable, not a successful
   all-abstaining baseline. Do not tune thresholds on the outcomes.
6. Report the paired difference descriptively. Shared proteins and a selected
   single-study panel do not justify independent-pair confidence intervals or
   an external-generalization claim. A favorable difference motivates separate
   confirmation; an unfavorable difference closes this candidate without a
   source/threshold sweep.

These policies were subsequently bound to actual mapping, retrieval and scoring
code in `runs/string_component_protocol_20261027_attempt_01/` before whole-panel
predictor access. The original scope packet remains **preparation, not the
executable freeze**. It preserves the existing source/outcome interface rather
than adding a new label protocol.

## Why the previous three-arm proposal is not ready

The intended later software-contribution comparison remains Pharos baseline,
ordinary addition and qualified addition of **identical information**. It needs
a real, verified input difference between the latter two arms. The present
inputs do not supply one:

- The earlier INMC learner graphs deliberately excluded all direct Pharos PPI.
  Displaying source-reuse flags cannot change their predictions.
- All 4,650 reciprocal matching Lambourne Pharos source views lack explicit
  publication/method/curated-record/MIscore fields. Source-bundle labels and
  aggregate scores cannot replace those inputs to
  [MImerge/MIscore](https://academic.oup.com/database/article/doi/10.1093/database/bau131/2433131).
- Native MIscore is already preserved in consumed IntAct raw records; its absence
  from one structured projection is not lost source data. Those small records
  do not form an adequate cohort intervention: their six literal single-UniProt
  pairs have **zero exact pair overlap** with the Lambourne nominations.
- Readding the reference's detected pairs and then evaluating on them would
  leak outcomes. Making an ordinary-addition arm falsely call all assay rows
  positive would be an invalid baseline.

The native-score component therefore precedes a Steward-specific three-arm
claim. If later qualified and ordinary graph inputs have identical features,
report that no-op and do not run a learner expecting a difference.

## Published comparator reuse and preparation

The paper-linked **MPS(T)** topology implementation passed a synthetic native
Java/author-ranker conformance check. It is a useful later comparator, with its
degree-product control, not a newly independent reference. The native exporter
enumerates all pairs and truncates ranked output to 500; a fixed-candidate
adapter and masking/resource checks remain necessary before using it on our
complete panel. Do not replace the current assay scorer with neteval's full
pipeline: it changes coverage and uses other positive-list references.

The [completed scope preparation](evaluations/BIOLOGICAL_COMPARISON_SCOPE_20261027.md)
records exact inputs, method receipts, implementation checks and the runnable
offline command. The [completed native-score assessment](evaluations/STRING_COMPONENT_COMPARISON_20261027.md)
is its executed follow-through. No model or GPU was needed for preparation,
retrieval or scoring. A later GNN comparison will be announced separately.
