# Fitted convex combination comparison

This isolated research comparison combines captured, qualified LocalPlus and
DeepGO-SE score matrices. The arithmetic core performs no model inference,
retrieval, ontology traversal, or label extraction. A phased runner fits weights
on previously exposed CAFA development outcomes, seals forecasts, then acquires
one new temporal reference and calls the preserved native evaluator. NumPy and
Pandas remain research-runtime dependencies; app dependencies are unchanged.

The established form is the DeepGOPlus convex combination:

`combined = alpha * LocalPlus + (1 - alpha) * DeepGO`

This is an **adaptation**, not a reproduction of DeepGOPlus. Its original
components are DiamondScore and DeepGOCNN. Our component substitution and the
following development objective/grid are explicit project choices. The paper's
published fitted weights cannot be transferred to these different components.

For each GO aspect independently, the caller supplies native **development**
micro-Fmax for all weights `0.0, 0.1, ..., 1.0`. The selector chooses the largest
objective, breaking an exact tie with the smallest alpha. Thus alpha 0 is pure
DeepGO and alpha 1 is pure LocalPlus. The selector accepts no reference labels
or final-test metrics; it rejects a declared non-development split. This API
cannot verify the provenance of scalar values supplied by a caller. The driver
must retain the existing source freezes and label-access boundaries. Previously
opened CAFA outcomes are development evidence, not an independent final test.

## Reused sources and verified differences

- [DeepGOPlus primary paper](https://doi.org/10.1093/bioinformatics/btz595),
  especially its combination and parameter-selection sections. The later
  [erratum](https://doi.org/10.1093/bioinformatics/btaa763) concerns figure
  placement, not the combination formula.
- [Official author repository at commit
  `8e8dcb1be7f1bfd5beed11893dacc4132213ea19`](https://github.com/bio-ontology-research-group/deepgoplus/tree/8e8dcb1be7f1bfd5beed11893dacc4132213ea19),
  BSD-3-Clause, Copyright 2019 Bio-Ontology Research Group.
- [`evaluate_deepgoplus.py`](https://github.com/bio-ontology-research-group/deepgoplus/blob/8e8dcb1be7f1bfd5beed11893dacc4132213ea19/evaluate_deepgoplus.py)
  SHA256 `749bffbe56d5eeaa2f1561b63cce4687e320fb9a886a257e2b79cb944cea660e`:
  score mixing precedes ancestor MAX propagation. Missing component terms
  contribute arithmetic zero. MAX closure and convex mixing do not commute.
- [`find_alphas.py`](https://github.com/bio-ontology-research-group/deepgoplus/blob/8e8dcb1be7f1bfd5beed11893dacc4132213ea19/find_alphas.py)
  SHA256 `af4809e7dd3ebb48406325e0b87cf35a4c73f445bf0e75d8b5dd01870c9471ab`:
  its current grid is `.45 ... .74` and its objective combines scaled Smin,
  protein-centric Fmax and AUPR. We do **not** claim to execute that optimizer.
- [`alphas.py`](https://github.com/bio-ontology-research-group/deepgoplus/blob/8e8dcb1be7f1bfd5beed11893dacc4132213ea19/alphas.py)
  SHA256 `8316d0723f97b38a627f6a346ab19298304e5e5510cdff0df0a5001d0bb802fa`:
  a separate author development-split alpha search uses `.40 ... .69` and
  protein-centric Fmax. This provides precedent for fitting on development
  data, not permission to tune on the final temporal reference.

The arithmetic core implements the stated formula and checks independently;
it does not vendor the DeepGOPlus scripts or their TensorFlow/DIAMOND runtime.
`native_adapter.py` calls the separately preserved GPL-3.0
[CAFA-evaluator-PK source at
`e386b085e204ccfbd75a4f52c1a8b25987d8b465`](https://github.com/claradepaolis/CAFA-evaluator-PK/tree/e386b085e204ccfbd75a4f52c1a8b25987d8b465).
The adapter verifies the exact graph/parser/evaluation/test source bytes before
use. Ordinary contribution arrays reproduce the native full curves within
`1e-12` before the established paired-protein bootstrap is called. This is a
numerical adapter around the existing metric, not a new biological score.

## Arithmetic and identity contract

- `ScoreMatrix` retains ordered, literal protein and GO axes. Different order,
  identifiers, aliases, isoforms, or dimensions fail rather than being repaired.
  Native canonical/alternative-ID resolution must precede this core when
  needed; this code does not guess equivalence.
- Input values must be real, finite, nonnegative and at most 1. The explicit
  `LOCALPLUS_UPPER_ROUNDOFF = 1e-10` option retains the previously qualified
  LocalPlus upper floating-point roundoff; it never clips or rescales values.
  The option is off by default. Negative roundoff is not accepted by score I/O,
  consistent with the existing qualified fusion intake.
- TSV or gzip rows contain exactly accession, GO ID, and raw score. Literal
  repeated cells retain MAX, consistent with the native CAFA reader. The core
  reader rejects unknown axis members. The native adapter expands the official
  alternative IDs and MAX-reduces resolved duplicates; broader-file proteins
  and terms outside the requested frame are ignored with explicit audit counts,
  matching the native reader's frame restriction. All source scores are checked
  before filtering. Omitted cells contribute zero for arithmetic only; they are
  not biological negatives or proof of prediction coverage. Intake diagnostics
  distinguish explicit rows from omitted cells and targets.
- Alpha endpoints retain the exact validated source numerical values. Float32
  values have an exact float64 representation. TSV uses 17 significant digits;
  deterministic gzip omits a source filename and fixes its timestamp to zero.
- Mix saved scores before **this evaluation call's** ontology closure. This
  does not assert that component training annotations or model internals never
  used GO structure. DeepGOPlus's native demonstration uses MAX closure; our
  declared CAFA comparison retains its existing native `fill` policy after
  mixing, once per nonzero namespace. The synthetic fixture distinguishes both
  the operation order and native `fill` from MAX. A globally zero namespace
  retains an explicit zero/no-coverage matrix, bypassing the upstream
  `propagate` function's empty-matrix indexing error. Native evaluation returns
  no scored endpoint when its positive-coverage filter leaves no rows.
- Native predictions retain complete row and term identity metadata. Call
  `align_predictions` to reorder/subset forecasts to the native ground-truth
  frame before `evaluate_native`; equal matrix dimensions alone do not establish
  identity alignment. The scorer uses native roots, TOI and known-term masks.
  This comparison has no IA artifact, so it reports ordinary metrics only.

## Fixed development and new temporal reference

The frozen [protocol](protocol.py) specifies one comparison and no second grid:

- Fit one alpha per GO aspect using pooled, previously exposed CAFA primary and
  reserved PK outcomes, with native known-term exclusion and historical ontology.
  Exclude every declared LAFA final target accession and every exact sequence
  duplicate from combiner development. Fitting thresholds are `.01 ... .99`.
- Evaluate the sealed forecasts against the author-released
  [LAFA September 2025–March 2026 frame](https://github.com/FriedbergLab/CAFA_forever/tree/c3fd5b9a5226348d88b9efadddb3214c803b80c4/data/releases/Sep_2025_Mar_2026).
  The release is pinned to commit
  `c3fd5b9a5226348d88b9efadddb3214c803b80c4`; each acquired file must match its
  recorded Git blob. Future GO rows and final TOI are decoded only after every
  final forecast is sealed. Final thresholds are `.001 ... .999`.
- Retain the exact-sequence-compatible intersection with already captured human
  forecasts. Original PK forecasts take precedence for all PK-frame accessions;
  NK/LK forecast files supply only other accessions. Independent batch reruns
  are never MAX-pooled to construct a more favorable parent.
- Compare learned mixing against pure DeepGO-SE, pure LocalPlus, fixed equal
  mixing, and the contemporary native T0 nonexperimental GOA baseline. The
  primary endpoint is PK molecular-function ordinary micro-Fmax. Report all
  nine PK/NK/LK by MF/BP/CC strata, including unavailable outcomes. PK uses the
  native known-term exclusion; NK/LK retain native no-exclusion semantics.
- Use 2,000 paired whole-protein bootstrap draws, seed `20261113`, with common
  multiplicities across all arms. The primary success rule requires a positive
  point gain and a paired 95% interval above zero against **every** fixed
  comparator. Secondary strata do not select a replacement winner. There is
  no automatic graph, app-default, hosted-workspace or model adoption.

The contemporary baseline runs the unchanged
[`democafa` author GOA nonexperimental CLI](https://github.com/FriedbergLab/democafa_package/tree/0ab84edbaddf5fef11125dc8adbd19167c3cc038/democafa/baselines/goa_nonexp_container)
at commit `0ab84edbaddf5fef11125dc8adbd19167c3cc038`, using a qualified
September 4, 2025 GAF and the fixed native computational, phylogenetic,
electronic, ND and NAS evidence selection. Its binary score-1 output is a
strong contemporary source-content comparator, not an independent biological
reference or a third ranked component in the learned mixture. Source checks
record taxa, gene-product forms and extensions; the unchanged baseline does
not filter those fields. The helper had no explicit source license in the
qualified checkout, so it is executed separately for research and is not
vendored here. Preserve upstream GO/UniProt data attribution separately from
repository code licenses.

Interpretation remains bounded. Combiner-fit exclusions do not establish
homology independence or base-checkpoint training independence. Newer GOA
source QC was previously performed, so this is not wholly developer-blind.
Temporal curator annotation growth is incomplete reference evidence; unknown
annotations are not experimental negatives. Fmax optimizes a reference
threshold and is not a calibrated deployment threshold. A positive result
would support this transport comparison, not whole-graph biological accuracy
or independent experimental replication. A zero, negative or unavailable
result must remain in the report.

## Running the four phases

Use the separately pinned native research runtime and place its author source
and dependencies on `PYTHONPATH`; do not install them into the app environment.
The qualified execution runtime uses Python 3.10.12, NumPy 1.26.4, Pandas 2.2.3
and SciPy 1.13.1. `--config` must be the finalized configuration with the exact
protocol and input/code pins, not an unfinished template. Output directories
must be new. Keep source, failed-run and earlier-result artifacts intact.

```sh
python -m tools.learned_combination.runner prepare \
  --config frozen_config.json --output comparison/prepared
python -m tools.learned_combination.runner fit \
  --config frozen_config.json --prepared comparison/prepared \
  --output comparison/fitted
python -m tools.learned_combination.runner seal \
  --config frozen_config.json --prepared comparison/prepared \
  --fitted comparison/fitted --output comparison/sealed
python -m tools.learned_combination.runner evaluate \
  --config frozen_config.json --sealed comparison/sealed \
  --output comparison/evaluated
```

`prepare` loads captured forecasts on both epoch ontologies, preserving the
full requested target axes without final outcome labels. `fit` reads only
development outcomes and records the 11 native curves per aspect and selected
weights. `seal` records all five arms on the final ontology, including exact
protein/term axes and file hashes. `evaluate` verifies that seal before acquiring
the new reference, applies native frame/mask rules, checks count/curve parity,
and writes all strata and paired intervals. These phases require CPU/memory,
not a model server, new base-model inference or GPU execution.

## Small API

```python
from tools.learned_combination import (
    ALPHA_GRID, LOCALPLUS_UPPER_ROUNDOFF, convex_mix, load_scores,
    select_development_alpha, write_scores,
)

# Supply the same explicitly qualified axes to both intakes.
localplus, local_intake = load_scores(
    localplus_path, proteins, terms,
    upper_roundoff_tolerance=LOCALPLUS_UPPER_ROUNDOFF,
)
deepgo, deepgo_intake = load_scores(deepgo_path, proteins, terms)

# The driver obtains one native development micro-Fmax per mixed prediction.
# It freezes the chosen alpha before a new temporal reference is opened.
chosen = select_development_alpha(
    'mf', development_micro_fmax_by_alpha,
    development_id=recorded_development_provenance_id,
)
mixed = convex_mix(localplus, deepgo, chosen.alpha)
write_scores(new_prediction_path, mixed)
```

Synthetic checks (no reference cases, model calls or remote resources):

```sh
python -m unittest tools.learned_combination.test_core -v
python -m unittest discover -s tools/learned_combination -t . -v
```

Array/I/O tests skip when NumPy is unavailable; scalar selection tests still
run. Native integration tests need the pinned author source and research
dependencies; set `BIOGRAPH_CAFA_AUTHOR_SOURCE` to its `src` directory when it
is outside the default local preserved-source location. Set
`BIOGRAPH_NATIVE_TESTS_REQUIRED=1` to reject missing native count dependencies,
and verify that the qualified suite reports zero skips. Passing these checks
establishes the adapter's
arithmetic, native parity and phase boundaries, not biological accuracy,
independence, calibration or prediction gains.
