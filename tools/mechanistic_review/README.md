# Optional mechanistic-claim review assessment

The [recorded assessment](../../docs/evaluations/MECHANISTIC_CLAIM_REVIEW_20261117.md)
includes the public expert reference, complete admission rule, all five arms,
removal errors and uncertainty. The
[aggregate report](../../docs/evaluations/mechanistic_claim_review_20261117/report.html)
contains no individual source texts or reference cases. This research package
does not change the core application's dependencies or any Pharos decisions.

`prepare.py` derives the symmetric complete-source frame from the separately
retained reference capture and prior fixed publication/source-group split.
`model_review.py` reuses `JSONModelClient`, tokenizes the complete final inputs,
and performs one bounded review per claim. Durable request intents prevent an
interrupted request from being repeated. No source evidence is shortened or
omitted to fit context. Invalid or inconsistent verdicts abstain.

`score.py` validates frozen code/input/protocol hashes and sealed predictions
before joining labels. It writes a full decision ledger and a typed native
retained reference graph for each arm. Unknown evidence is not a negative.
`publish.py` emits only allowlisted aggregates and a readable static report.
All public numbers retain their denominators and adverse results.

The preserved private run used protocol SHA256
`fd362356cdde3f594ab221acf7c258dd22250b60b2a90edd3ea5171069120a7a`.
Its public copy is [protocol.json](../../docs/evaluations/mechanistic_claim_review_20261117/protocol.json).
The raw reference remains under its original CC BY-NC-SA 4.0 terms and is not
included in the software ZIP. The official source and data links are in the
assessment note. Original source capture and fixed split artifacts are required
to reproduce this particular retrospective frame. Supplying a different capture
requires its own explicit input pins and evaluation protocol.

## Native baseline and method credit

`native_baseline.py` adapts INDRA **1.24.0**'s existing
[`CountsScorer`](https://indra.readthedocs.io/en/latest/modules/belief/skl_belief.html)
and optional `SimpleScorer`; their implementations are imported from the
separately qualified research environment, not copied or reimplemented. The
native source code and actual package versions are fingerprinted in every
returned result. INDRA uses the BSD-2-Clause license; this adapter is MIT.
Source Statements and curator data retain their separate CC-BY-NC-SA terms.

The caller supplies ordered native Statements, case IDs and **DEV-only** integer
labels keyed by those IDs. Reserve labels are not accepted. Source vocabulary
is fitted on DEV only and frozen in sorted column order. `CountsScorer` supplies
its unmodified raw evidence-count features. Its optional type, PMID, member,
promoter, evidence-length, residue/position and support-ancestry features stay
off. The adapter retains every original evidence object and neither reads nor
uses released Statement belief scores. In particular, original evidence is not
filtered down to only the sources with favorable curation.

The single predeclared classifier is scikit-learn `LogisticRegression` with
`C=1.0`, `solver='lbfgs'`, `max_iter=1000` and `random_state=20261117`; all other
effective defaults are recorded. There is no parameter search, calibration,
threshold selection or fitting on reserve cases. Probabilities below 0.5 create
**unapplied review proposals** to exclude a candidate from this assessment view;
they do not establish biological falsity or modify a workspace.

One verified integration boundary needs an explicit guard: native CountsScorer
logs unseen source APIs but otherwise omits their columns. This adapter abstains
on such reserve rows rather than silently dropping evidence. Missing or invalid
source identities and overlapping DEV/reserve claims stop the call. Model
failures or nonconvergence yield abstentions rather than negative labels.

The separately reported `SimpleScorer` comparator uses native bundled default
source-error priors, including its native handling of negated evidence. Unknown
priors abstain. Its source-independence assumptions and possible prior curation
exposure remain limitations; this is not a calibrated independent truth oracle.
Neither comparator substitutes one prediction for the other's abstention.

Use the existing optional interpreter (no core dependency or new installation):

```sh
runs/indra_grounding_runtime_20261113/venv/bin/python -m unittest discover -s tests -p 'test_mechanistic_native_baseline.py' -v
```

The invented fixtures cover native feature/order preservation, label joins and
DEV-only fitting, source and claim overlap, unseen sources, model failure and a
Statement object that raises if its released belief is accessed. Importing the
adapter alone requires only Python's standard library. The frozen runner owns
source admission, human-curation label policy, group separation, evaluation and
output files. No real-data model assessment is implied by passing these tests.

The small CLI accepts only a hash-pinned frozen protocol, its exact source-case
file and a separate **DEV-only** JSONL label file:

```sh
runs/indra_grounding_runtime_20261113/venv/bin/python -m tools.mechanistic_review.native_baseline \
  --protocol /absolute/path/protocol.json --protocol-sha256 EXACT_PROTOCOL_SHA256 \
  --source-cases /absolute/path/source_cases.jsonl \
  --dev-labels /absolute/path/development_labels.jsonl --out /absolute/path/new_output
```

Its `native_baseline` protocol section pins `source_cases`,
`development_labels` and `code` as `{file, sha256}` records and declares
`development_count`, `reserve_count`, `parameters` and `include_simple`.
Case split names are `development` and `test`; each case keeps its frozen
`input_sha256` and `group_id`. The CLI checks source-group separation, exact
DEV label IDs, code/input hashes and source counts without rewriting the source
JSON. It never opens a reserve-label file. `native_results.json` is a sealed
envelope containing the protocol/source-file hashes, all reserve input bindings
and the unchanged, separately sealed native result. The enclosing scorer must
still distinguish completed predictions from model-error abstentions.
