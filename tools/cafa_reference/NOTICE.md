The BioGraph Steward application and the ordinary source-intake/process-driver
code retain the repository's MIT license.

`author_point_runner.py`, `author_contributions_runner.py` and
`stratified_aggregates.py`, together with the native evaluator adapters
`../cafa_nonpk/evaluate.py` and `../cafa_nonpk/counts.py`, are optional GPL-3.0-only
adapters for the separately downloaded GPL author CAFA evaluator.
They are not application dependencies. The full license text is included as
`LICENCE.GPL-3.0.txt`. Preserve that license and the original CAFA-evaluator
attribution when distributing these adapters together with the author source.

The files carrying the same explicit GPL-3.0-only SPDX notice in
`../learned_combination/` and `../contextual_combination/` retain that license
as well. They wrap the separately pinned native evaluator and remain optional
research code, outside the standalone MIT core application ZIP. Other files
retain their own stated license. The external ProtBoost implementation is
separately source-pinned Apache-2.0 code and is not vendored into the application.

The NK/LK adapter uses that same evaluator with native `exclude=None` and
preserves exact author curves and denominators. Its source/prediction release
gates and optional numerical prediction wrappers do not add the evaluator to
the application runtime.

Author evaluator: https://github.com/claradepaolis/CAFA-evaluator-PK
Reference data: https://zenodo.org/records/22381862 (CC BY 4.0).
No license for a source dataset is replaced by the software's license.
