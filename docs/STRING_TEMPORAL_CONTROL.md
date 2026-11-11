# Archived STRING temporal control

October 27, 2026. This is the single older-source control selected by the
[independence review](evaluations/STRING_REFERENCE_INDEPENDENCE_20261027.md).
It tests native STRING 12.0 functional versus physical ranking on the unchanged
consumed Lambourne human Y2H-v1 nominations. It does not train a new model,
change the graph, or search for a favorable source version or threshold.

**Completed:** the [executed control](evaluations/STRING_TEMPORAL_CONTROL_20261027.md)
reports AP 0.149732 versus 0.161223 on all 2,676 eligible pairs, with numeric
coverage 93.4% versus 75.2%. The direction agrees with the prior 12.5 component;
the control is closed without further tuning. The sections below preserve its
pre-execution rules and reproduction commands.

## Why this control

The [STRING 12.0 primary paper](https://pmc.ncbi.nlm.nih.gov/articles/PMC9825434/)
describes distinct functional and physical association scores, canonical locus
representatives and imported experimental knowledge. The
[official version history](https://string-db.org/cgi/access) dates 12.0 to 2023;
[release documentation](https://string-db.org/help/scores/) states that its
network is fixed within a release. The
[assay methods](https://www.nature.com/articles/s41467-026-70942-x) describe
panel selection from 2024 predictions. This supports a temporally earlier
predictor control. It does not certify novel pairs, remove older HuRI exposure
or create a new unseen reference. This control was selected after the 12.5
result; it is a development sensitivity assessment.

The verified integration difference is the
[documented 12.0 native API](https://version-12-0.string-db.org/help/api/):
13 columns and separate `network_type` requests. The current 12.5 typed API
has 24 columns with a physical overlay. We adapt the native interface rather
than coercing it into the newer schema. Help pages are reviewed documentation;
the captured version endpoint and actual responses bind runtime assertions.

## Fixed execution rules

- Keep all 3,222 nominations, 3,173 accessions, original constructs, 546 assay
  exclusions and prior exposure flags. The same 2,676 eligible pairs enter
  each primary arm. Nothing is selected by archived scores or outcomes.
- Reuse the existing exact source/construct/outcome join on the copied original
  capture, then join new predictions by exact pair/source row. No new outcome
  file or reserved study body is decoded.
- Use `https://version-12-0.string-db.org`, species 9606, best-match mappings
  with query echoes, separate functional/physical queries, `required_score=0`
  and `add_nodes=0`. Mappings are locus correspondences, not construct identity.
- Use the same deterministic 25-candidate query groups, at most 50 mapped
  representatives per group. Incidental edges never create candidates. One
  version call, 32 mapping calls and at most 258 network calls give a cap of
  291 logical requests. Calls are sequential and spaced at least 1.05 seconds.
- Accept one undirected source row or agreeing reciprocal rows. Reject repeated
  orientations, conflicting channels/labels, wrong species, extra endpoints,
  schema errors and cross-batch disagreement. Each native view must have its
  own validated response; physical-only and functional-only rows remain valid.
- Keep numeric zero, absent native row, unmapped/ambiguous endpoint and collapsed
  representative distinct. A technical failure stops capture. No missing view
  is inferred from the other. Preserve raw TSVs and every transport receipt.
- Adapt the existing bounded transport: at most three attempts for transient
  network/selected 5xx failures, stop on 429 or schema errors, 4 MiB per body
  and 64 MiB total. Verify response framing, pinned URLs, API version header,
  byte inventories and attempt accounting offline.
- Before cohort access, freeze actual implementation hashes, rules and copied
  source inputs. Each protocol has once-only access; failures are preserved
  and cannot be restarted under the same protocol. Seal captured native inputs
  and their contrast before metric computation.
- Reuse scikit-learn 1.9.1 AP in Python 3.12.4, full eligible population with
  legitimately unranked pairs tied last at ordinal −1. The sentinel is not
  native confidence or a biological-negative label. Report numeric coverage,
  every state, all exposure strata and an actual jointly numeric secondary
  denominator within 12.0. That denominator may differ from 12.5's 1,938.
  No confidence interval, threshold tuning or follow-up version sweep is used.

This changes both the release and the retrieval representation relative to the
12.5 typed-overlay assessment. A result cannot isolate the effect of study
ingestion, source refresh, method revision or a Steward graph intervention.
Nondetection remains assay-conditional and cannot justify deleting a functional
association. A native physical score does not establish direct binding.

## Run and replay

The original real-data capture is supplied separately; it is not bundled in a
fresh repository clone. Use new output directories. Freezing verifies and
copies its complete source packet, allowing subsequent offline replay.

```sh
runs/reactome_context_runtime_20261026/venv/bin/python \
  scripts/run_string_temporal.py freeze \
  --reference-capture runs/string_component_capture_20261027_attempt_01 \
  --out runs/string_temporal_protocol_new
python3 scripts/run_string_temporal.py capture \
  --protocol runs/string_temporal_protocol_new \
  --out runs/string_temporal_capture_new
runs/reactome_context_runtime_20261026/venv/bin/python \
  scripts/score_string_temporal.py \
  --capture runs/string_temporal_capture_new \
  --out runs/string_temporal_result_new
```

The frozen scorer requires the recorded Python/scikit-learn versions. Native
retrieval and ordinary verification use the core standard-library runtime;
neither Brev nor AWS is required. Offline replay makes no new source calls:

```sh
python3 scripts/run_string_temporal.py verify \
  --capture runs/string_temporal_capture_new
runs/reactome_context_runtime_20261026/venv/bin/python \
  scripts/score_string_temporal.py --verify \
  --capture runs/string_temporal_capture_new \
  --out runs/string_temporal_result_new
```
