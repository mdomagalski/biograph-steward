# Run the source verifier

The browser app and benchmark runner are separate commands in the same application. Start the app in one terminal:

```bash
cd /Users/42573/biograph-steward-pharos
python3 app.py serve --port 8766 --no-browser
```

Open <http://127.0.0.1:8766/>. If it is already running, keep that terminal open. In a second terminal, run the commands below. No Python packages need installing.

## Offline comparison

The prepared data already exists in this checkout's ignored `runs/` directory. This command runs three fixed baselines without model calls:

```bash
cd /Users/42573/biograph-steward-pharos
python3 app.py verification-run \
  --benchmark runs/scifact_verification_document_holdout_20261015 \
  --out runs/verifier_baselines_02
```

Use a new output directory for each run. Results cannot overwrite earlier runs. On a fresh checkout, [download and prepare the source data](VERIFICATION_BENCHMARKS.md#prepared-scifact-data) first; real abstracts and generated reports are intentionally excluded from Git.

## Live verifier

The verifier uses the same signed-in Codex CLI as the existing question planner. Select an available model explicitly; the project's initial evaluation uses `gpt-6-astra`. This requires the CLI's existing login, not a new API key. It consumes model usage. The adapter runs one isolated turn per pair, with tools and browsing disabled, and validates the verdict and copied sentence text. See the [official CLI options](https://learn.chatgpt.com/docs/cli/reference).

For this desktop installation:

```bash
export BIOGRAPH_CODEX_BIN="/Applications/ChatGPT.app/Contents/Resources/codex-cli/CodexCLI.app/Contents/MacOS/codex"
export BIOGRAPH_CODEX_MODEL="gpt-6-astra"

# First check the integration on 20 training pairs.
python3 app.py verification-run \
  --benchmark runs/scifact_verification_train_20261015 \
  --verifier codex --limit 20 --workers 2 \
  --out runs/verifier_train_pilot_02

# Freeze the prompt/model, then evaluate the whole custom development subset.
python3 app.py verification-run \
  --benchmark runs/scifact_verification_document_holdout_20261015 \
  --verifier codex --workers 4 \
  --out runs/verifier_document_holdout_02
```

`--limit` selects pairs in a fixed hash order without using labels. Omit it to evaluate all inputs. `--workers` controls simultaneous independent turns (1–4; default 1). The model sees only one claim and its supplied abstract. Labels are read by the scorer after all predictions close. Errors remain scored cases; there are no repair calls or silent fallback models.

The custom subset excludes whole development claims touching any training document. It is development data, not a final test or an official SciFact leaderboard evaluation. Once viewed, it must not be reused as an untouched test after prompt changes. Keep any subsequent tuned result separate.

## Read and reproduce the results

The terminal prints the absolute `report.html` path. Open that file directly, or use the running app's report route, replacing the folder name with your output directory:

<http://127.0.0.1:8766/api/evaluation/verifier_document_holdout_02/>

The report compares the live verifier with always accepting, always insufficient, and a fixed lexical-overlap rule. It includes each model assessment, exact cited sentences, expert labels/rationale alternatives, confusion matrices and error counts. The full result directory contains frozen inputs, post-prediction gold, the prompt/schema contract, per-turn traces, source attribution and byte hashes. Traces omit private reasoning and credentials. The CLI reports the requested model; it does not independently attest the served model identity.

Rescore saved predictions without model calls or the original source directory:

```bash
python3 app.py verification-score \
  --result runs/verifier_document_holdout_02 \
  --out runs/verifier_document_holdout_rescore_02
```

Rescoring checks saved input, gold, prediction, contract and trace hashes. Interrupted runs retain completed traces but are incomplete and cannot be scored as completed runs. Start a new run rather than silently dropping unfinished cases.

These scores test supplied-source interpretation. They do not measure literature retrieval, clinical truth, graph pruning, or improvement in held-out link prediction. No assertion state or human review worksheet changes. After inspecting this evaluation, the next integration is a read-only verifier assessment beside a small CRC evidence set, followed by a matched graph experiment with the same model and split.
