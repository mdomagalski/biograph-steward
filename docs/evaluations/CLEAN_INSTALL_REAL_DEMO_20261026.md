# Clean installation with the saved real cohort — October 26, 2026

The installed CLI and public APIs passed 23 engineering checks across 18 recorded
commands. An actual **local** clone checked out
`e874c4b49965b96bdc84d7147e95959b886aa383`; setuptools **80.9.0** built the wheel,
which was installed into a fresh Python **3.12.14** environment. Runtime commands
ran from an unrelated directory under `/private/tmp`. Module origins were all
the new environment's `site-packages`, and installed code and nine UI assets
matched the clean checkout. No application changes were needed.

The input was the existing `runs/assay_workbench_v2_20261026` cohort:
P22674/CCNO and P38936/CDKN1A, with one Pharos/STRINGDB interaction annotation and
one qualified detected Lambourne assay observation. The new candidate answer
returns CDKN1A with citation E001 to the saved database annotation. The assay
remains a separate observation with its qualifications; this answer does not
merge it into a physical-binding claim. The `assay-question` template supports
IntAct, so it was not used for this Lambourne attachment.

Both nodes, both evidence edges and both assertions survive export. There are
no human review events; both dispositions are `abstain` with null confidence.
All 62 original files stayed unchanged, and the 36 authoritative source files
travel in the 57-file handoff. Its ZIP was extracted outside the source checkout
and reopened using the installed `gold_packet.load_decisions` API. CLI replay,
answer reopening, source bindings, installed origins, prior receipts and all
280 owned artifact hashes were checked. The isolated Chrome workflow also passed:
guided question, cited passport, separate qualified assay display, actual ZIP
download and reopening its recovered source in a second installed-app workspace.
The regenerated answer results, citations and graph/snapshot basis match exactly.

## Local receipts and evidence boundaries

- Preparation, runtime paths and commands: `runs/clean_install_real_demo_20261026/attempt_01/{preparation,installed_ready,command_log}.json`.
- Result and artifact hashes: `runs/clean_install_real_demo_20261026/attempt_01/result.json`.
- Separate CLI and browser artifact reviews: `runs/clean_install_real_demo_20261026/{cli_independent_review,browser_independent_review}.json`.
- New answer: `runs/clean_install_real_demo_20261026/attempt_01/data/runs/real_question/`.
- Complete handoff: `runs/clean_install_real_demo_20261026/attempt_01/data/runs/real_submission/`.
- ZIP: `runs/clean_install_real_demo_20261026/attempt_01/submission_handoff.zip`.
- Separate browser receipt and five inspected screenshots: `runs/clean_install_real_demo_20261026/browser_01/report.json`.
- Independent CLI artifact review: `runs/clean_install_real_demo_20261026/cli_independent_review.json`.

The in-app browser connection and computer-use fallback were unavailable. The
browser check used the existing Chrome installation in an isolated headless
profile through bundled Playwright, without the user's browser profile. All page
requests were restricted to the local test server. This is automated browser
verification, not a participant usability result. The missing STRINGDB paper
reference remains explicitly displayed as **Reference: not supplied**.

Result file SHA-256: `495e25207ba7f82b5753da479067ee73bf1542e4dcf90c851f800082d80e543c`.
ZIP SHA-256: `fb3e033a8e00d631ca5c8f75a8939df3896b0f37f7ad032b2c411c5e89341084`.

These are local artifacts, not bundled source snapshots in a fresh checkout.
Reproduction needs an authorized copy of the existing input and its complete
assay publication. Core and setuptools MIT license files are preserved alongside
all 84 source-license metadata records. The Pharos inventory's missing license
grants and the assay repository's data-scope caveat remain explicit; code MIT
licensing does not establish blanket permission to redistribute source data.

This is engineering acceptance on an already-consumed panel. It does not establish
scientific improvement, independent biomedical-user task success, an official
submission format, remote GitHub availability or cloud deployment. No new source
retrieval, model, GPU/Brev, AWS, real review or reserved interaction-body access
was required.

## Reproduce with new directories

Set the following paths to absolute locations. `DEMO_LOCAL` and `DEMO_OUTPUT`
must be new; keep them outside the author checkout. Supply the already verified
setuptools wheel (SHA-256
`062d34222ad13e0cc312a4c02d73f059e86a4acbfbdea8f8f76b28c99f306922`).
The measured run reused its existing pinned build environment; these commands
recreate that backend in a separate environment using the same wheel.

```sh
DEMO_REPO=/absolute/path/to/local/repository
DEMO_LOCAL=/absolute/path/to/new-isolated-install
DEMO_OUTPUT=/absolute/path/to/new-demo-output
DEMO_INPUT=/absolute/path/to/assay_workbench_v2_20261026
DEMO_BACKEND_WHEEL=/absolute/path/to/setuptools-80.9.0-py3-none-any.whl
DEMO_BASE_PYTHON=/absolute/path/to/python3
mkdir -p "$DEMO_LOCAL/work" "$DEMO_OUTPUT/wheels"
git clone --local --no-hardlinks --no-checkout "$DEMO_REPO" "$DEMO_LOCAL/checkout"
git -C "$DEMO_LOCAL/checkout" checkout --detach e874c4b49965b96bdc84d7147e95959b886aa383
cd "$DEMO_LOCAL/work"
unset PYTHONPATH PYTHONHOME
"$DEMO_BASE_PYTHON" -I -m venv "$DEMO_LOCAL/build_env"
"$DEMO_LOCAL/build_env/bin/python" -I -m pip install --no-index --no-deps "$DEMO_BACKEND_WHEEL"
"$DEMO_LOCAL/build_env/bin/python" -I -c 'import importlib.metadata; assert importlib.metadata.version("setuptools")=="80.9.0"'
"$DEMO_LOCAL/build_env/bin/python" -I -m pip wheel --no-index --no-deps --no-build-isolation --wheel-dir "$DEMO_OUTPUT/wheels" "$DEMO_LOCAL/checkout"
"$DEMO_BASE_PYTHON" -I -m venv "$DEMO_LOCAL/venv"
DEMO_PYTHON="$DEMO_LOCAL/venv/bin/python"
DEMO_CLI="$DEMO_LOCAL/venv/bin/biograph-steward"
"$DEMO_PYTHON" -I -m pip install --no-index --no-deps "$DEMO_OUTPUT/wheels/biograph_steward-0.8.0-py3-none-any.whl"
"$DEMO_PYTHON" -I -c 'import biograph_steward,sys; p=biograph_steward.__file__; assert p.startswith(sys.prefix+"/") and "site-packages" in p; print(p)'
export BIOGRAPH_DATA_DIR="$DEMO_OUTPUT/data"
mkdir -p "$BIOGRAPH_DATA_DIR/runs"
cp -R "$DEMO_INPUT" "$BIOGRAPH_DATA_DIR/runs/real_cohort"
DEMO_RUN="$BIOGRAPH_DATA_DIR/runs/real_cohort"
"$DEMO_CLI" replay --snapshot "$DEMO_RUN/snapshot.json" --reviews "$DEMO_RUN/review_events.json" --assay-run "$DEMO_RUN" --out "$BIOGRAPH_DATA_DIR/runs/replayed_cohort"
"$DEMO_CLI" question --run "$DEMO_RUN" --protein P22674 --relations interactions --view candidates --out "$BIOGRAPH_DATA_DIR/runs/real_question"
"$DEMO_CLI" gold-export --run "$DEMO_RUN" --out "$DEMO_OUTPUT/source_packet"
"$DEMO_CLI" gold-verify --packet "$DEMO_OUTPUT/source_packet"
"$DEMO_CLI" gold-decisions --packet "$DEMO_OUTPUT/source_packet" --decisions "$DEMO_OUTPUT/source_packet/decisions.template.json" --out "$BIOGRAPH_DATA_DIR/runs/real_submission"
"$DEMO_CLI" gold-decisions-verify --run "$BIOGRAPH_DATA_DIR/runs/real_submission"
"$DEMO_CLI" serve --runs-dir "$BIOGRAPH_DATA_DIR/runs" --host 127.0.0.1 --port 8791 --no-browser
```

The saved answer reopens at `/api/question/real_question`, its graph at
`/api/run/real_cohort`, and the handoff downloads at
`/api/download/real_submission`. The browser download ZIP wraps its files in a
`real_submission/` directory: after extraction, run `gold-decisions-verify --run
/absolute/path/to/extracted/real_submission`. The CLI verification harness's
separate ZIP places the handoff files at the archive root, so point that same
verifier directly at its extraction directory. Both use the existing verifier;
do not point it at the browser ZIP's parent directory.

The local orchestration scripts and before/after input inventories are preserved
under `attempt_01/`. The existing `verify_submission_demo.py` deliberately adds
its source root to `sys.path`, so it alone cannot prove installed origins.
The clean-install harness instead invokes the installed console script and
public APIs with Python isolation, denying application network connects and DNS
during the offline workflow. Standard [venv](https://docs.python.org/3.12/library/venv.html)
and [pip wheel](https://pip.pypa.io/en/stable/cli/pip_wheel/) usage supplies the
installation machinery; the harness adds receipts and integrity checks.
