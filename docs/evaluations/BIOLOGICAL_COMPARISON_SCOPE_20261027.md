# Biological comparison scope preparation

October 27, 2026. **Completed scope repair and offline population preparation;
no new biological performance result.** The [study scope](../BIOLOGICAL_COMPARISON_SCOPE.md)
selects native STRING 12.5 functional retrieval versus its physical overlay
on the existing measured Lambourne panel. The previous Pharos lookup is a
historical descriptive anchor. This component study precedes a defensible
Steward-specific ordinary-addition versus qualified-addition comparison.

**Subsequent execution:** the [native STRING component evaluation](STRING_COMPONENT_COMPARISON_20261027.md)
completed capture and scoring under its own implementation-bound protocol.
This report remains the preparation receipt; it did not itself generate scores.

## Verified population and method fit

| Check | Result |
|---|---|
| Original nominations retained | 3,222 exact unordered pairs / 3,173 accessions |
| Author-consistent assay eligibility | 2,676 eligible; 546 excluded with original reasons |
| Existing Pharos comparator eligibility | 2,674; two unresolved Pharos pairs remain in the new source scope |
| Assay exclusions | 27 failed tests, 41 autoactivators, 478 failed sequence confirmations |
| Existing matching Pharos views | 4,650 reciprocal source views |
| Explicit publication/method/type/curated-record/MIscore fields in those views | Zero literal prerequisite fields recovered |
| Consumed IntAct literal single-UniProt pairs | Six; zero exact pair overlap with the nominated panel |
| STRING typed runtime probe | One known consumed pair; HTTP200, 24 columns, reciprocal scores agree |
| Published MPS(T) implementation | Unchanged official Java and author ranking passed synthetic conformance |

The prepared candidate file preserves original source rows, constructs,
eligibility and exposure flags but omits individual detection labels. This
does not make the assessment hidden: its outcomes were already consumed.
Native IntAct MIscore is present in the checked raw evidence records; it does
not need a new formula. Those records cannot supply a cohort-scale intervention
for this panel. Pharos provider names do not substitute for missing method or
publication attribution.

## Artifacts and verification

Final preparation: `runs/biological_comparison_scope_20261027_attempt_03/`.

- `candidates.json`: every original nomination, with separate assay and old
  Pharos eligibility. SHA-256 `ba91676dc21312362b72bb930639855c0523a5d5569d176953be0fcf85b8ff73`.
- `accession_inventory.json`: the fixed query population.
- `report.json`: source bindings, counts, field availability and remaining gates.
  SHA-256 `a801584b5830340f0c2b2a6b718d81ed80f6bf41874dfa615158bb30e436ecef`.
- [Tracked summary](biological_comparison_scope_20261027_summary.json): method
  receipts and execution paths without redistributing the biological inputs.

The [new offline preparer](../../scripts/prepare_biological_comparison_scope.py)
reuses the original assessment verifier, outcome adapter and exact identity
joins. Seven invented-data tests plus the existing corroboration tests passed
(33 total). Checks cover changed/duplicate/missing joins, construct mismatch,
eligibility handling, no detection-label dependence in the candidate projection,
isoform/namespace preservation and unsupported confidence-field inference.
No current app or frozen assessment file was edited.

The original verifier correctly rejects the active tree because
`gold_packet.py` has advanced since the historical assessment. Its expected
hash is `7d67abb15a5d15558781e9f8b55da419ae3aaefbb41df58998fef4f138d6bd81`;
the active file is `b14062d...`. Preparation therefore ran in a full Git archive
of **`3f7c462d517ce5793c9af99fce65922a97f9159c`**, after all ten original
implementation fingerprints matched. Only the new preparation script was
copied byte-identically into that archive. This follows the existing
[historical execution workflow](../EXPERIMENT_HISTORY.md#reopening-an-archived-file).

The complete execution receipt is
`runs/biological_scope_verifier_20261027_attempt_03/execution_receipt.json`,
SHA-256 `311ceeb8b6a88fa070b6c7733ebf8d5267cb1d291464405d01a7dee513927f53`.
Earlier attempts remain preserved: the first used an isolated mixed-version
copy; the second used the full archive before the final overlay wording.
Attempt 03 supersedes them for this preparation. None generated scores.

## Reproduce without changing the active checkout

From the repository root, choose new directories. The original real-data
assessment must be available separately; it is not bundled with the code.
This historical verifier pins **Python 3.14.0** as well as its source files;
use that exact interpreter. This does not change the core app's Python minimum.

```sh
comparison_project="$PWD"
comparison_python="/opt/homebrew/opt/python@3.14/bin/python3.14"
"$comparison_python" -c 'import platform; assert platform.python_version() == "3.14.0"'
comparison_verifier="$(mktemp -d /private/tmp/biological-verifier.XXXXXX)"
git archive 3f7c462d517ce5793c9af99fce65922a97f9159c | tar -x -C "$comparison_verifier"
cp scripts/prepare_biological_comparison_scope.py "$comparison_verifier/scripts/"
"$comparison_python" "$comparison_verifier/scripts/prepare_biological_comparison_scope.py" \
  --assessment "$comparison_project/runs/lambourne_corroboration_20261025" \
  --intact-inventory "$comparison_project/docs/evaluations/intact_consumed_inventory_v2_20261027.json" \
  --out "$comparison_project/runs/biological_scope_new"
```

## Public methods inspected, not reinvented

- MImerge/MIscore: primary methods and official `miscore`/`micluster` code were
  checked. Current version/build/license details need resolution before a new
  packaged integration; supplied native scores remain usable annotations.
  Receipt: `runs/qualification_method_scope_20261027/report.json`, SHA-256
  `92325ab2926718a2a50acbc21c7a65db361fd2de182c65055f0830b3245f74be`.
- Native STRING: the probe's body hash is
  `6edc1567c28596ed7fb23667d06fa52d4b0e86be572a77760abd72bb80366755`.
  It verifies schema on one consumed pair, not whole-cohort coverage. Physical
  `-` combines absence/below-cutoff possibilities. Complex Portal is a physical
  score calibration reference, not automatically independent validation.
- Wright/neteval and MPS(T): paper-pinned neteval v0.2.2 and current relevant
  code agree; the full evaluator would change our population and reference.
  MIT-licensed author MPS(T) source passed exact synthetic formula/ranking
  conformance. Its missing candidate-only interface and selection dependence
  remain explicit. Receipt: `runs/neteval_method_scope_20261027/report.json`,
  SHA-256 `fd7935b2d65d48f36abf5e2b8f17f73a0755584de46fdd9c0988fcb4e09d7dd2`.

## Next execution boundary

Implement and test the declared source-mapping, complete query coverage,
physical-overlay missingness and ranking adapters, then bind their actual code
and source request plan before whole-panel predictor retrieval/scoring. Report
coverage and full-panel ranking together; preserve API errors as errors.
The documented bottom tie is an operational ranking boundary, not a source
confidence or a biological-negative label.

The preparation report leaves the corresponding **implemented-and-bound**
gates false; the linked scope defines their intended policies. No new reference
outcomes, model, GPU or whole-cohort predictor inputs were accessed here.
The one STRING capability request is recorded separately from the offline
preparer's zero source calls. The fresh IntAct studies remain unopened.
