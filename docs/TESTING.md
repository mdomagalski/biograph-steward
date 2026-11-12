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

## Pinned scientific evaluation

Four modules use `evaluation_*.py` names and run in a separate CI job:

- `evaluation_reactome_handoff.py`
- `evaluation_reactome_runner.py`
- `evaluation_string_component_scoring.py`
- `evaluation_string_temporal_scoring.py`

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

The new evaluation CI job uses Ubuntu 22.04 and `actions/setup-python` with
3.12.4. Its Linux execution remains pending the actual GitHub Actions run;
local macOS verification does not establish Linux success. The core workflow
continues to test app portability separately.

## Scope preservation

The split renames only those four files and updates their one fixture
cross-import. Test assertions and skip policies are unchanged. All other test
modules remain in default discovery; the union of both groups preserves every
previously collected case. The separate
[kinase utility tests](../tools/kinase_utility/README.md) retain their existing
optional command.

No scientific implementation, source data, frozen execution pins or benchmark
results change through this test-routing increment. Historical receipts retain
their original filenames and commands.

References: [standard unittest discovery](https://docs.python.org/3.12/library/unittest.html#test-discovery)
and [GitHub Python version/dependency setup](https://docs.github.com/en/actions/tutorials/build-and-test-code/python).
