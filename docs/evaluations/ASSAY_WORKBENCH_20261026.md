# Qualified assay workbench integration — October 26, 2026

The [bounded attachment](../ASSAY_WORKBENCH.md) is implemented and checked on
invented regression fixtures and a real source publication. This is product
integration and source-fidelity verification, not a scientific improvement test.
The [machine-readable check](assay_workbench_20261026_summary.json) records the
artifact identities and accounting.

## Real-source check

The first observation in the existing publication's saved order supplied the
two exact accessions, **P22674 and P38936**, before inspecting its outcome for
this interface check. The panel was already consumed by the previous study;
this selection is neither a fresh holdout nor a representative biological sample.

A bounded two-protein Pharos retrieval produced one source-reported interaction
annotation. The workbench retained that annotation and its assertion unchanged,
and attached one qualified Y2H-v1 detection as a separate candidate observation.
This demonstrates preservation of different evidence types for the same pair,
not discovery of a new interaction. The combined run retains all **29 files**
of the original publication byte for byte under `assay_source/`.

Artifacts, ignored by Git:

- Source cohort: `runs/assay_cohort_source_20261026/`.
- Final integrated example: `runs/assay_workbench_v2_20261026/`.
- Original publication: `runs/lambourne_assay_evidence_20261025/`.

The initial integrated rendering is retained at `runs/assay_workbench_20261026/`.
Use v2 for inspection: review identified and fixed a closed review panel, a
second-endpoint filter omission and an absent numeric-value display. These were
interface defects; source records and scientific outcomes were not changed.

## Verification

- Full suite: **700 tests, 26 optional skips, no failures**.
- After the final display corrections, all **25 assay-focused tests** passed.
- Regression coverage includes both-endpoint selection, unresolved identifiers,
  all assay outcomes, unchanged Pharos assertions, review/publication bindings,
  complete source preservation after originals become unavailable, tampering,
  authentication, traversal/symlink rejection, safe source downloads and explicit
  CLI replay without source loss.
- Current-code construction verification and ordinary attached-run replay
  passed on the real artifacts. The saved v2 report equals the current renderer.
- Combined workbench JavaScript syntax and a second-endpoint filtering probe
  passed in Node's JavaScript VM. These are not browser-layout tests.
- The desktop browser bridge was unavailable; browser visual acceptance and
  intended-user task evaluation were not performed.
- `git diff --check` and changed-document local-link checks passed.

The original scientific publication also replayed from isolated checkpoint
`3f7c462` under Python 3.14.0 before integration. The [checkpoint record](CHECKPOINT_REPLAY_20261026.md)
preserves exact historical verification; the new intake explicitly reports
saved-file integrity and observation reprojection instead of claiming to rerun
the original assessment with changed code.

## Remaining boundaries

Assay-qualified observations remain outside the ordinary interaction-path answer.
Their ledger and assertion passports expose context and local review separately.
Gold/KGX packet export and cohort refresh reject attached runs until their
source-preserving mappings exist; the full ordinary run ZIP is available now.

No model/GPU/AWS resource was used. No additional public-reference outcome set
was opened. Independent prediction benefit, automated pruning, intended-user
usefulness and agent-selected construction remain unestablished. The
[public-reference audit](../literature/PUBLIC_REFERENCE_OPTIONS_20261026.md)
selects IntAct/IMEx for a bounded curation-reference preparation step, without
claiming independence from Pharos or an official challenge score.
