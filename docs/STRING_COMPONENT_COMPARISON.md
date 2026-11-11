# Native STRING component comparison

This executes the [fixed biological scope](BIOLOGICAL_COMPARISON_SCOPE.md):
STRING 12.5 functional scores versus the physical overlay of the same typed
retrieval, evaluated against the already consumed human Y2H-v1 panel. The
source supplies both scores. No confidence formula, model training or graph
pruning is introduced.

**Executed October 27:** on the same 2,676 eligible pairs, AP increased from
0.172827 to 0.190056, while numeric coverage decreased from 88.3% to 72.4%.
The [completed evaluation](evaluations/STRING_COMPONENT_COMPARISON_20261027.md)
records full/common-population metrics, exposure strata, immutable artifacts
and independent arithmetic verification. This is a retrospective source-view
result; scientific independence and Steward-specific improvement remain open.

The code uses the [official STRING API](https://string-db.org/help/api/) for
mapping and network retrieval, the original author-consistent assay adapter
for reference eligibility, and scikit-learn's existing average-precision
implementation. Version-specific response checks were tested before cohort
access. Primary metric and missingness rules were fixed before retrieval.

## Reproduce with the original local inputs

The original real-data artifacts and historical verifier checkout must be
available separately; a fresh code clone does not include them. The archived
verifier requires its recorded Python 3.14.0. The metric environment is the
existing Python 3.12.4 / scikit-learn 1.9.1 environment. Choose new output paths.

```sh
python3 scripts/run_string_component.py freeze \
  --scope runs/biological_comparison_scope_20261027_attempt_03 \
  --assessment runs/lambourne_corroboration_20261025 \
  --reference-root runs/biological_scope_verifier_20261027_attempt_03 \
  --out runs/string_component_protocol_new

python3 scripts/run_string_component.py capture \
  --protocol runs/string_component_protocol_new \
  --out runs/string_component_capture_new

runs/reactome_context_runtime_20261026/venv/bin/python \
  scripts/score_string_component.py \
  --capture runs/string_component_capture_new \
  --out runs/string_component_result_new
```

The first command must use Python 3.14.0, not an arbitrary default interpreter.
The [scope preparation](evaluations/BIOLOGICAL_COMPARISON_SCOPE_20261027.md)
documents the exact archive/runtime recipe. The scorer enforces the declared
Python/scikit-learn versions. Neither a Brev instance nor a language model is
needed.

## What is fixed and preserved

- All 3,222 original nominated pairs and 3,173 accessions are retained. The
  primary population is the unchanged 2,676 assay-eligible pairs; excluded tests
  and the two Pharos-unresolved but assay-eligible pairs stay explicit.
- Mapping uses documented `get_string_ids` parameters and exact query echoes.
  A returned representative is the provider's best match, not an exhaustive
  ambiguity search or proof of sequence/construct identity. Missing, conflicting
  or collapsed mappings remain distinct source states.
- Mapping requests contain at most 100 accessions. Network queries group 25
  fixed nominated pairs, with at most 50 mapped representatives, no added
  neighbors and `required_score=0`. Every queryable pair must have both endpoints
  in its assigned query. Incidental returned edges do not create new candidates.
- The versioned typed response is checked against the observed schema. Both
  orientations must agree; repeated pairs in overlapping queries must agree
  in their scores and returned/absent state.
- Calls are sequential and spaced at least 1.05 seconds apart. There are at
  most 161 logical requests, at most three transport attempts per request and
  a 64 MiB total body cap. Transient network/5xx retries retain every attempt.
  HTTP 429 stops the capture. No technical error becomes missing evidence.
- Response framing, source API version, URL/parameters, file fingerprints and
  complete byte inventories are verified. Empty/error bodies do not count as
  validated empty networks. A partial or failed capture cannot be scored.
- Native numeric zero remains numeric zero. Legitimately unranked pairs tie at
  an ordinal value below all native scores; this is a retrieval-ranking rule,
  not an inferred confidence or biological-negative label. Native physical
  `-` remains absent/below-threshold under the requested profile.

The protocol records actual implementation/source hashes before cohort access.
A once-only access marker prevents restarting that protocol into another
output. Failed attempts remain available; repairs require a new declared
attempt. Captured predictions and their native contrast are sealed before
metric computation. Existing reference outcomes do not drive query selection.

## Inspect and replay

The protocol contains copied candidate/reference bytes and their bindings.
The capture contains raw response bodies, every request receipt, the mapping,
query plan, complete prediction ledger and file manifest. The result contains
`report.html`, `metrics.json` and a verification receipt. Paths to original
reference inputs are provenance labels; replay uses the copied capture packet.

```sh
python3 scripts/run_string_component.py verify \
  --capture runs/string_component_capture_new
runs/reactome_context_runtime_20261026/venv/bin/python \
  scripts/score_string_component.py --verify \
  --capture runs/string_component_capture_new \
  --out runs/string_component_result_new
```

Report full-panel AP together with explicit numeric coverage and each unranked
state. The jointly numeric comparison is secondary, with its own denominator.
An all-unranked arm is unscorable. Existing HuRI/INMC exposure strata are
reported without selecting the favorable one. No confidence intervals,
outcome-tuned thresholds or alternative source sweep are used.

This is a retrospective component assessment on selected, consumed nominations.
It does not establish direct binding, calibrated scientific accuracy, independent
validation, a complete native-physical-network comparison or a Steward-specific
three-arm gain. Current provider/reference study reuse remains uncertain.
