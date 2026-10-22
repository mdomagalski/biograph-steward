# Current build plan

Updated October 22, 2026. The active product is the source-traceable evidence workbench. The active scientific investigation is preparation of a bounded measured PPI comparison. Retired experiments and old next-step proposals are preserved in the [experiment archive](EXPERIMENT_HISTORY.md).

## Current product

Maintain the guided question → evidence graph → cited answer → source-passport flow, complete molecular-profile/therapy context, explicit source and display coverage, local reviews and saved-version comparison. The optional planner may select a bounded read-only query; it does not accept or prune graph assertions.

Source fidelity, usability, claim verification and biological prediction have different evaluation targets. The workbench's structural checks and source preservation do not establish scientific accuracy. Keep that distinction in the app, exports and progress report.

## Next scientific increment: finish input readiness

The [reuse review](literature/MEASURED_LINK_BENCHMARK_REUSE_20261022.md) selects the INMC experimentally tested protein-pair panel for preparation with PyKEEN R-GCN and simpler controls. The [input audit](evaluations/INMC_INPUT_READINESS_20261022.md) established:

- 3,276 candidate pairs, including 495 self-pairs that need separate treatment; all 1,805 genes occur in the released training network and no candidate pair is a training edge.
- 1,801 exact HGNC gene mappings, with unresolved IDs and multiple/missing protein products retained explicitly.
- Insufficient baseline coverage: the old CRC pull directly covers only 43 panel genes and contains two candidate-pair overlaps in raw context.
- An author-provided positive reference, but unresolved handling of partially unsuccessful assays. No binary labels or predictions were generated.

Proceed in this order:

1. **Resolve or bound assay interpretation.** Check the primary paper, supplement and released artifacts for each unresolved code. Do not treat unscored, untested or interfering assays as negatives. If exact author adjudication remains unavailable, document a restricted, unambiguous task and its coverage before deriving outcomes.
2. **Resolve mapping exceptions without replacing source identities silently.** Preserve assay gene IDs separately from current protein-context mappings and disclose construct/isoform limits.
3. **Retrieve uniform Pharos context for the fixed population.** Reuse the existing client, identity and normalization capabilities. Record source releases, caps and omissions; do not inherit the CRC tissue filters or the consumed DepMap cohort policy.
4. **Freeze the source and pair exclusions.** Check held-out pairs, inverses/equivalents, raw responses, derived features, study/source reuse and answer-bearing text. Current Pharos postdates the experiment, so a retrospective masking test cannot be called independent temporal validation.
5. **Freeze and run one matched comparison.** Use identical targets, candidates, splits, model implementation, seeds and tuning budgets for baseline and enriched graphs. Select settings on validation only. Include simple topology/embedding controls; keep observed assay negatives distinct from unlabeled training corruptions. Report an honest negative result if enrichment does not help.

A PyKEEN runtime smoke on Nations passed; this is not a biomedical evaluation. Before R-GCN training on the panel, complete the input and protocol gates above; a successful smoke does not resolve them. The present preparation needs no GPU.

## Remaining challenge functionality

| Gap | Reviewable completion criterion |
|---|---|
| Measured graph-link comparison | Frozen, source-audited paired experiment with metrics, uncertainty, controls and reproducible artifacts |
| Bounded agent construction | Declared source tools and budgets, deterministic normalization/publication, recorded calls and graph changes |
| Validated interoperability | Version-pinned Biolink/LinkML/KGX or other selected standard checks, qualification-preserving exports and explicit mappings |
| Evidence filtering/pruning | Task-compatible references, false-removal and abstention reporting; no promotion of invalid model outputs as successful detection |
| Maintenance | Controlled source-change cases distinguish changed evidence, scope/cap absence and withdrawal; review continuity remains traceable |
| Usability | Actual biomedical-user task completion, errors, time and interpretation checks |
| Packaging | Fresh-clone instructions, source/license manifests, dependency pins, fetchable or redistributable examples and separate archived history |

Use established implementations before filling these gaps with custom infrastructure. Recheck official versions, task assumptions, licenses and training/evaluation overlap. When a new scientific or integration issue appears, record what literature documents, what our implementation demonstrates and what remains unresolved.

## Delivery context

The supplied challenge brief lists an intermediate progress report on **October 27, 2026** and challenge end on **November 17, 2026**. These are supplied dates, not a newly verified schedule. No organizer dataset beyond those materials has been provided. Report the workbench and bounded preparation separately from missing graph-learning results; seek mentor feedback on the assay-specific PPI task's challenge fit.

See the [functional crosswalk](PROJECT_ALIGNMENT.md) for organizer/proposal coverage. AWS/Neptune, a UI framework migration and additional agents are conditional implementation choices, not substitutes for the missing evaluation.
