# Core and optional evaluation tests

The application has no third-party runtime dependencies. Its portability tests
and the scientific evaluation tests use separate standard `unittest` discovery
patterns; installing the scientific stack is not required to run the app.

## Core and portability

From the repository root:

```sh
NO_PROXY=127.0.0.1,localhost,::1 no_proxy=127.0.0.1,localhost,::1 \
  python3 -m unittest discover -s tests -v
```

Default discovery selects `test*.py`. The core CI matrix uses Python 3.10,
3.12 and 3.13. Existing guarded checks for optional integrations may skip when
their dependencies are unavailable; this does not establish that an optional
integration works. The loopback proxy bypass follows the existing portability
workflow and keeps temporary local test servers out of system proxy routing.
Workflow YAML uses only `no_proxy`: GitHub treats environment-map names as
case-insensitive and rejects both spellings in the same map. Local shell
commands may export both spellings as shown above.

## Pinned scientific evaluation

Seven modules use `evaluation_*.py` names and run in a separate CI job:

- `evaluation_reactome_handoff.py`
- `evaluation_reactome_runner.py`
- `evaluation_string_component_scoring.py`
- `evaluation_string_temporal_scoring.py`
- `evaluation_go_native_parser.py`
- `evaluation_go_context_inspection.py`
- `evaluation_wiki_author_reader.py`

They retain their required dependency/version assertions. Missing scientific
packages are failures in this group, not new skips. The existing dependency
file pins PyKEEN, Torch, NumPy, SciPy, scikit-learn and workbook support. In an
isolated **Python 3.12.4** environment:

```sh
EVALUATION_PY=/absolute/path/to/python3.12.4
"$EVALUATION_PY" -m pip install -r requirements-inmc-evaluation.txt
NO_PROXY=127.0.0.1,localhost,::1 no_proxy=127.0.0.1,localhost,::1 \
  PYTHONPATH=.:tests "$EVALUATION_PY" -m unittest discover \
  -s tests -p 'evaluation_*.py' -v
```

The exact Python patch version matters: the temporal scorer pins 3.12.4, and
the metric tests require scikit-learn 1.9.1. Native tests also require PyKEEN
1.11.1 and Torch 2.6.0. These tests use invented graphs, workbooks and labels;
they do not rerun the real biological comparisons or require Brev/GPU access.

The evaluation CI job uses Ubuntu 22.04 and `actions/setup-python` with
3.12.4. It passed on GitHub after the workflow syntax correction. The core
workflow tests app portability separately; consult the current branch's
Actions results for each version rather than inferring Linux success from
local macOS verification.

Clean-checkout tests use temporary invented metadata, not files in an ignored
research `runs/` directory. A separate HTTP regression covers CPython 3.10's
strict parser behavior for an empty query ([upstream source](https://github.com/python/cpython/blob/v3.10.22/Lib/urllib/parse.py)): default pair requests bypass the
parser, while nonempty queries retain strict validation. No scientific
implementation or old reference outcome changes through these fixes.

## Scope preservation

The original split renamed four files and updated one fixture cross-import.
The native GO and WikiPathways integrations extend the optional group without
changing existing assertions or skip policies. All other test modules remain
in default discovery; the union of both groups preserves every previously
collected case. The separate
[kinase utility tests](../tools/kinase_utility/README.md) retain their existing
optional command.

No scientific implementation, source data, frozen execution pins or benchmark
results change through this test-routing increment. Historical receipts retain
their original filenames and commands.

## Sampled audit and native pathway reader

The [sampled-audit tools](../tools/sampled_audit/README.md) have standard-library
controls in default discovery. They test source binding, probability weights,
UNKNOWN preservation, reversible decisions and failure handling with invented
fixtures. The optional `evaluation_wiki_author_reader.py` executes two
unmodified MIT-licensed author functions whose exact bytes and license are
retained in `tests/fixtures/pywikipathways_reader`.

For a smaller isolated Python 3.12 reader environment, install
`tools/sampled_audit/requirements-pathway-quality.txt` and run:

```sh
PYTHONPATH=.:tests /path/to/reader-venv/bin/python -m unittest \
  evaluation_wiki_author_reader -v
```

The dependency remains optional; default app startup and standard-library
tests do not import pandas. These controls verify implementation behavior,
not the truth of biomedical source records or reviewer judgments.

References: [standard unittest discovery](https://docs.python.org/3.12/library/unittest.html#test-discovery)
and [GitHub Python version/dependency setup](https://docs.github.com/en/actions/tutorials/build-and-test-code/python).
