# Final source fidelity rules and biological testing boundary

The final assessment rules are now explicit in the
[machine-readable contract](intact_final_evaluation_20261026_rules.json).
They preserve the original selection, eligibility, semantic amendment and metrics.
**This is a rules/preparation checkpoint, not an executable final freeze or a
reserved score.** No reserved interaction body was read, hashed or queried.

The [development provenance audit](INTACT_DEVELOPMENT_PROVENANCE_AUDIT_20261026.md)
is complete within its declared scope. Four eligible observations represent two
pairs, three curated experiment records and two publications, not four independent
confirmations. One pair is already represented by STRINGDB in the saved Pharos
cohort; its source study is not supplied. Exact cross-development primary-ID pair
and participant overlap is absent, but synonym/sequence equivalence and shared
study data remain unverified. The reserved pair/participant overlap is unknown.
An unknown result is retained rather than relabeled as independence.

## Fixed final rules

- Use the original four reserved studies only. No replacement, favorable subset,
  post-result identity repair, revised eligibility or threshold tuning.
- Leave the development-only loaders, catalog guards and historical results
  unchanged. A separate final path must accept the actual source-eligible count,
  including zero, without hardcoding the four-row development result.
- Preserve every physical row, exact source identity, missing state, assay role,
  host, negative literal/default and original interaction grouping. One n-ary
  interaction may have several MITAB views; these are not replications.
- Before scoring, audit exact study/evidence identifiers and explicit qualified
  primary/subsidiary dataset statements against a declared consumed inventory.
  Exclude known consumed-linked study components without replacement. Generic
  citations, shared proteins/pairs or an IMEx registration alone prove neither
  reuse nor independence. Ambiguous potential dataset reuse requires adjudication.
- Report source eligibility, study-level exclusions and final assessment counts
  separately. Participant/pair overlap is an exposure flag, not an automatic
  scientific exclusion. Missing lineage stays unverified; known missing article
  status checks do not become correction/retraction clearance.
- Freeze the question, focus/order, profile, caps, batching and any Pharos retrieval
  policy before final identities become visible. A source-eligible row that fails
  resolution, attachment, answer or export remains a miss in the appropriate
  denominator; it cannot disappear into a successful subset.
- Report coverage and strict fidelity over every final-assessment eligible row,
  conditional fidelity alongside coverage, critical semantic errors, per-field
  and per-publication results, and empty strata as unevaluated. A source-fidelity
  score is not scientific accuracy, and it authorizes no graph deletion.
- Freeze actual runtime/code/input hashes, passing controls and the complete final
  orchestration before access. Execute once, preserve failures and consumed
  status, and stop on unresolved parser semantics or ambiguous reference
  projection. Do not repair final cases and call the rerun unseen.

These are applications of the already-selected protocol and
[official IntAct curation model](https://github.com/intact-portal/intact-portal-documentation/blob/b5d5bb35365739d4942e9ca250a2cf4fbaa14c62/docs/curation-manual/special-cases.md),
not a new biological annotation scheme. The corrected
[expansion semantics](intact_fidelity_20261026_semantic_amendment.json) remain
mandatory. The [IMEx primary paper](https://www.nature.com/articles/s41467-020-19942-z)
supports preserving context and distinct evidence units.

## What the preflight verifies

The prepare-only checker verifies exact original protocol/amendment pins, the
four reserved IDs, explicit safe metadata bindings, denominator and uncertainty
rules, and declared execution-readiness components. It validates every bound
path before reading any bound file and never follows source paths embedded
inside metadata. It does not invoke readers, retrieve sources or authorize
reserved access, even if future readiness declarations are supplied.

```sh
python3 scripts/check_intact_final_readiness.py
```

Its current `blocked` result is intentional: the rules are specified, but the
complete final orchestration has not yet been implemented and tested. The
remaining work is a thin final orchestration of existing helpers, its invented
cases and consumed-development replay, a bounded consumed-reference inventory,
and one immutable execution receipt. Merely widening the existing four-study
allowlists is not a valid substitute. Opening reserved files for an audit before
that work would expose them while implementation can still change.

## When to test biological improvement

Biological testing should proceed in parallel with this preparation and the
[user walkthrough](../USER_WALKTHROUGH_FINAL_20261026.md); it does not have to
wait for every architecture feature or a finished usability study. We already
executed one biological intervention: GO hierarchy did not give a consistent
prediction gain on the fixed INMC comparison. Those outcomes and the Lambourne
panel are consumed and cannot become fresh validation for a new intervention.

The next confirmatory run needs a concrete graph change justified before seeing
its outcomes, a compatible measured endpoint and a suitable fresh reference with
declared leakage/exposure limits. Compare the same Pharos baseline, addition of the same
information, and Steward's qualification under matched candidates, learner,
seeds and budget; do not invent an intentionally weak baseline. Distinguish
functional association, physical association and direct binding. Assay
nondetections are conditional observations, and missing pairs are unlabeled.
The [recent primary leakage study](https://academic.oup.com/bioinformatics/article/42/8/btag608/8767164)
and [author code](https://github.com/galadrielbriere/data_leakage_kge_benchmark)
support auditing redundant/reverse relations and external-reference validity.

A retrospective development comparison can start sooner, on the already-consumed
assay outcomes, once one literature-supported task-compatible intervention is justified.
Preserve the original results and mark the new comparison exploratory. Keep scored
labels and their derivatives outside predictor inputs; using outcomes for fitting
makes that portion training performance. Its valid claim is a paired performance
change on this consumed panel under fixed conditions, not fresh validation,
independent generalization or new biological knowledge beyond Pharos. Unknown
provider lineage remains a disclosed possible leakage source, but does not by
itself forbid this narrower experiment. There is no reason to wait for every UI,
cloud or final-fidelity feature before such development work.

The present reserved IntAct assessment cannot fill that role: its supplied
curation is intentionally the importer input, and independent study lineage from
Pharos is not established. Fidelity and usability results do not prove biological
prediction gain. The [focused method reuse review](../literature/BIOLOGICAL_IMPROVEMENT_REUSE_DECISION_20261026.md)
identified SNOOPPI's sequence/proteoform qualification as an existing approach,
but not a drop-in independent reference. Its derived/generated labels, sequence
identity and artifact scope require care. No second biological prediction run is
currently ready because no verified, task-compatible intervention has been
selected. That is a scientific design gap, distinct from incomplete source
lineage. The existing learner can support the development comparison once the
intervention is fixed; no additional model or GPU run follows from these checks.
