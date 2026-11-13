# Optional source-grounding evaluation

This is an expert-curator-relative component evaluation of human-gene
grounding-conflict proposals. It measures agreement with qualified published
curations. It does not estimate whole-Pharos accuracy, establish biological
truth, identify a corrected protein form, or automatically prune a graph.

The application core does not require this runtime. No GPU, Brev instance,
AWS account, API key, or paid service is needed for these commands.

## Install the separate runtime

Use Python 3.12 and a new virtual environment. From the repository root:

```sh
python3.12 -m venv .venv-grounding
.venv-grounding/bin/python -m pip install -e .
.venv-grounding/bin/python -m pip install -r tools/grounding_claims/requirements.txt
```

The requirements pin INDRA 1.24.0, Gilda 1.6.1, Adeft 0.13.0, the classifier
runtime, and the streaming/decimal JSON libraries. Commands record their actual
versions and native parser source hashes. Ordinary `--help` and the acquisition
command use only the standard library. New output directories are required;
existing captures and partial downloads are preserved.

## Capture and join the reference

The reference is the author-released JSON data for
[the INDRA assembly paper](https://doi.org/10.15252/msb.202211325),
[Zenodo 7559353](https://doi.org/10.5281/zenodo.7559353). Its data license is
**CC BY-NC-SA 4.0**, separate from this repository's software license. Keep
downloads and derived source packets in private storage. Do not bundle the
raw data in a public MIT software release. The author analysis repository is
not required and its code is not copied or executed.

```sh
.venv-grounding/bin/python -m tools.grounding_claims.reproduce acquire \
  --out /absolute/private/path/grounding-source

.venv-grounding/bin/python -m tools.grounding_claims.reproduce join \
  --data /absolute/private/path/grounding-source \
  --out /absolute/private/path/grounding-join
```

Acquisition verifies current official metadata against exactly two released
files: the 1,687,078-byte curation JSON and the 460,045,058-byte compressed
statement JSON. Both publisher MD5 and independently captured SHA-256 pins
must match. The much larger pickle file is never downloaded or loaded.
Receipts preserve URLs, byte counts, checksums, and failed partial captures.
Allow at least 2 GB of free space for source files and the optional runtime.

The curation inventory reads only original signed `(pa_hash, source_hash)`
identity fields and schema keys. It does not inspect tag, comment, curator,
or correctness values. IDs remain exact decimal strings; no floating-point
conversion is allowed. The join streams the compressed corpus with published
`ijson`, preserves decimal JSON with `simplejson`, and loads one selected
Statement at a time using native `indra.statements.stmts_from_json`.

The join emits the existing `prepare` inputs: `selected_statements.jsonl`,
`pair_join_inventory.json`, `exposure_groups.json`, and sealed `join_report.json`.
Complete native source objects are retained, together with original compressed
file hashes, array ordinals, and separately named canonical parsed-value
hashes. Native reader/hash drift stops the join. Multiple payloads sharing a
reference hash are preserved; no representative payload is selected.

Evidence-specific `annotations.agents.raw_text` and `raw_grounding` arrays
remain paired. The pipeline does not substitute an assembled Agent's text.
Publication/source/family components are conservative exposure groups, not
gold biological equivalence classes.

## Prepare the frame and source context

Use the release's outcome-free **expanded reviewed-source exposure inventory**
as `--exposure`: [published exposure tokens](../../docs/evaluations/grounding_replay_20261113/prior_reviewed_source_tokens.json)
and [replay metadata](../../docs/evaluations/grounding_replay_20261113/metadata.json).
It records known earlier paper/source exposure and authoritative
identifier aliases. A new team's reading history may differ: record it before
splitting, without using reference categories or model results. Do not replace
this with an empty inventory to recreate a larger test set. The original
reviewed-source history, official alias receipts, frame, context manifests,
resource receipt, and final evaluation freeze are audit metadata that must
accompany any claimed exact replay; they are not contained in the Zenodo data.

```sh
.venv-grounding/bin/python -m tools.grounding_claims.prepare \
  --join /absolute/private/path/grounding-join \
  --exposure /absolute/path/to/expanded_prior_reviewed_source_tokens.json \
  --out /absolute/private/path/grounding-frame
```

`prepare` applies the documented native citation policy while preserving the
original fields: malformed secondary reader IDs are qualifiers; different
valid numeric PMIDs remain unresolved. Prior reviewed identifiers force the
whole connected component into development. This controls known project
exposure, not unknown Gilda/Adeft training-publication overlap.

The public `tools.grounding_claims.context` module provides `capture_context`
and `load_context`; the repository's frozen evaluation uses its exact PubMed
title-and-abstract capture and raw XML replay. Capture newly eligible PMID
identities before predictions. A current refetch is a new source capture;
compare raw hashes before calling it an exact reproduction. Unavailable
publication context remains unresolved, with no source-sentence fallback in
the publication arm.

```sh
.venv-grounding/bin/python - <<'PY'
import json
from pathlib import Path
from tools.grounding_claims.context import capture_context
frame = Path('/absolute/private/path/grounding-frame')
pmids = json.loads((frame / 'requested_pmids.json').read_text())
capture_context(pmids, Path('/absolute/private/path/grounding-contexts'))
PY
```

## Capture native model resources

Run resource setup in a fresh Python process after preparing the blind frame:

```sh
.venv-grounding/bin/python -m tools.grounding_claims.reproduce resources \
  --frame /absolute/private/path/grounding-frame \
  --out /absolute/private/path/grounding-runtime
```

This uses Gilda's native `get_grounding_terms`/`get_gilda_models` and Adeft's
native availability/download helpers. Anonymous access to the projects'
public S3 buckets does not use AWS account credits. Gilda lexicon/model
SHA-256 pins must match the evaluated 1.6.1 resources. Adeft directories are
selected by exact stripped input mentions across the blind frame, not by
labels or observed success. Both contextual arms use the same native assets.
Metadata HEAD requests establish a 150 MB total bound before downloads.

The generated `resource_receipt.json` records every asset hash and local path,
the frame source pin, and the selected Adeft shortforms/directories. Versioned
bucket paths alone do not guarantee immutable content: compare **every** asset
hash to the released evaluation receipt for exact replay. Any drift requires
a separately recorded qualification and evaluation freeze, not overwriting
the original result. These commands never run a grounder prediction.

## Freeze, predict, then score

Create a local plan with the existing runner contract after completing the
source-only prerequisites. `freeze` verifies source and context seals, the
original curation-file SHA-256 without decoding its values, local code pins,
and every native asset hash. Its paths refer to your current checkout, so the
published plan's original absolute paths do not have to exist on your machine.
The optional parent reference links this local freeze to the released one and
records code/version comparisons.

```sh
.venv-grounding/bin/python -m tools.grounding_claims.reproduce freeze \
  --frame /absolute/private/path/grounding-frame \
  --contexts /absolute/private/path/grounding-contexts \
  --resources /absolute/private/path/grounding-runtime/resource_receipt.json \
  --curations /absolute/private/path/grounding-source/indra_assembly_curations.json \
  --parent-freeze /absolute/path/to/released_evaluation_freeze.json \
  --acknowledge-source-only \
  --out /absolute/private/path/local_evaluation_freeze.json
```

`--acknowledge-source-only` records the operator's declaration that this local
setup used source/identity metadata, without category- or prediction-driven
changes to the fixed inputs or method. It is **not automatic proof of
blinding**. If using the pipeline for a separate prospective evaluation, omit
`--parent-freeze` and record its actual exposure history before outcomes.
Replaying published results is semantic reproduction of a consumed reference;
it does not create a new independent holdout. File locations, capture dates,
gzip headers, manifest timestamps, and their seals can differ. Compare the
released source, scientific code, case/split, context, and model-asset pins
before claiming a matching scientific replay.

Run both fixed partitions before opening scoring outputs. These commands use
only the prepared source frame, contexts, model assets, and local plan:

```sh
.venv-grounding/bin/python -m tools.grounding_claims.run \
  --frame /absolute/private/path/grounding-frame \
  --contexts /absolute/private/path/grounding-contexts \
  --resources /absolute/private/path/grounding-runtime/resource_receipt.json \
  --plan /absolute/private/path/local_evaluation_freeze.json \
  --split development --out /absolute/private/path/predictions-development

.venv-grounding/bin/python -m tools.grounding_claims.run \
  --frame /absolute/private/path/grounding-frame \
  --contexts /absolute/private/path/grounding-contexts \
  --resources /absolute/private/path/grounding-runtime/resource_receipt.json \
  --plan /absolute/private/path/local_evaluation_freeze.json \
  --split test --out /absolute/private/path/predictions-test
```

Only scoring opens the selected native curation categories. Keep its
case-level outputs private under the reference-data license:

```sh
.venv-grounding/bin/python -m tools.grounding_claims.evaluate \
  --frame /absolute/private/path/grounding-frame \
  --predictions /absolute/private/path/predictions-development \
  --curations /absolute/private/path/grounding-source/indra_assembly_curations.json \
  --plan /absolute/private/path/local_evaluation_freeze.json \
  --out /absolute/private/path/evaluation-development

.venv-grounding/bin/python -m tools.grounding_claims.evaluate \
  --frame /absolute/private/path/grounding-frame \
  --predictions /absolute/private/path/predictions-test \
  --curations /absolute/private/path/grounding-source/indra_assembly_curations.json \
  --plan /absolute/private/path/local_evaluation_freeze.json \
  --out /absolute/private/path/evaluation-test
```

The existing `run` and `evaluate` modules reject changed source/code/resource
pins. Do not tune on the reserved partition or pass curator data to a
predictor. A technical change needs a separately linked freeze and preserved
failure history; it cannot restore a consumed holdout. The supported order is
source qualification, known-exposure grouping, frame/context/resource capture,
final freeze, saved predictions, then reference-category admission and scoring.

All three preset arms retain the same eligible cases: lexical Gilda, source
Evidence text, and exact PubMed title plus abstract. Only unanimous native
`correct` and `grounding` labels enter the defined endpoint. Other or mixed
curations remain outside it. Unresolved/model-error cases stay visible in
coverage and error-recall denominators. Undefined ratios remain undefined.
Newly generated prerequisites do not reproduce an already consumed holdout
or authorize another independent-validation claim.
