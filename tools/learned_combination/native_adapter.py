# SPDX-License-Identifier: GPL-3.0-only
"""Isolated intake/mixing adapter for the unchanged pinned CAFA evaluator.

No ontology or scoring implementation is copied. This module calls the
preserved author-evaluation-v1 cafaeval APIs (commit e386b085e204ccfbd75a4f52c1a8b25987d8b465).
The host driver supplies the pinned source on PYTHONPATH and controls label
access, source freezes, development fitting and independent evaluation.
"""
import csv
import hashlib
import importlib
from pathlib import Path

from .core import LOCALPLUS_UPPER_ROUNDOFF, ScoreMatrix, convex_mix, need, validate_axes


AUTHOR_COMMIT = 'e386b085e204ccfbd75a4f52c1a8b25987d8b465'
AUTHOR_FILES_SHA256 = {
    'graph.py': '3b0f523f672bab3234e6798b86801514fbd84ea43c38e57e902e7b6e2cc74111',
    'parser.py': '825e81969a30b5075069c9a5510ae711e0159507c7618a51a05e46dfc0f45d17',
    'evaluation.py': '515664459bec8909df138a422a713058ba3f8a8ddc7e4b0475382459a709cda2',
    'tests.py': '15c764c44fcd59dfd7986aed228a01975c6575624ec88887e6c0b4c2465f6826',
}


def _native():
    """Fail closed on another cafaeval implementation, even with matching API."""
    modules = {name: importlib.import_module('cafaeval.' + name)
               for name in ('graph', 'parser', 'evaluation', 'tests')}
    for name, module in modules.items():
        source = Path(module.__file__)
        need(source.name == name + '.py'
             and hashlib.sha256(source.read_bytes()).hexdigest() == AUTHOR_FILES_SHA256[source.name],
             'native evaluator source differs from pinned author-evaluation-v1: ' + name)
    return modules


def native_ontologies(obo_path):
    """Use native is_a/part_of parsing, no IA and the existing no-root policy."""
    return _native()['parser'].obo_parser(str(obo_path), ('is_a', 'part_of'),
                                         ia_file=None, orphans=False)


def _term_axes(ontologies):
    axes = {}
    for namespace, ontology in ontologies.items():
        terms = tuple(term['id'] for term in ontology.terms_list)
        need(len(terms) == ontology.idxs
             and all(ontology.terms_dict[term]['index'] == index
                     for index, term in enumerate(terms)),
             'native ontology term ordering is not its matrix ordering.')
        need(ontology.ia is None, 'this ordinary micro-Fmax comparison requires IA None.')
        axes[namespace] = terms
    need(axes, 'nonempty native ontologies are required.')
    return axes


def load_native_scores(paths, proteins, ontologies, *, localplus=False, chunksize=1_000_000):
    """Read saved TSV/gzip forecasts before this evaluator's propagation.

    The C parser uses round-trip float64 conversion, no score rounding. Every
    source score is checked before filtering. Broader-file proteins and terms
    outside this ontology are counted and ignored as the native reader does;
    the requested protein axis itself is literal, complete and unchanged.
    Native alternative IDs may expand to multiple primary terms. Aliases and
    repeated rows are combined by MAX before any mixing or propagation.

    Return ``({namespace: ScoreMatrix}, diagnostics)``. The missing-value zero
    is arithmetic only, never a biological-negative label. ``localplus=True``
    enables only its already-qualified upper 1e-10 roundoff allowance.
    """
    import numpy as np
    import pandas as pd

    _native()
    need(isinstance(localplus, bool), 'localplus qualification flag must be boolean.')
    need(isinstance(chunksize, int) and not isinstance(chunksize, bool) and chunksize > 0,
         'positive integer C-parser chunk size required.')
    axes = _term_axes(ontologies)
    proteins, _ = validate_axes(proteins, next(iter(axes.values())))
    paths = [paths] if isinstance(paths, (str, Path)) else list(paths)
    need(paths, 'at least one captured forecast file is required.')
    p_index = {protein: index for index, protein in enumerate(proteins)}
    namespaces = tuple(ontologies)
    matrices = {ns: np.zeros((len(proteins), len(axes[ns])), dtype=np.float64) for ns in namespaces}
    seen = {ns: np.zeros(matrices[ns].shape, dtype=bool) for ns in namespaces}
    direct, multiple, term_namespace = {}, {}, {}
    # Assignment order follows the native pred_parser namespace lookup. The
    # native per-namespace alt mapping takes priority over a primary collision.
    for ns_code, ns in enumerate(namespaces):
        ontology = ontologies[ns]
        direct[ns] = {term: data['index'] for term, data in ontology.terms_dict.items()}
        multiple[ns] = {}
        for term in ontology.terms_dict:
            term_namespace[term] = ns_code
        for alias, primary_terms in ontology.terms_dict_alt.items():
            term_namespace[alias] = ns_code
            indexes = tuple(ontology.terms_dict[term]['index'] for term in primary_terms)
            if len(indexes) == 1:
                direct[ns][alias] = indexes[0]
            else:
                direct[ns].pop(alias, None)
                multiple[ns][alias] = indexes
    tolerance = LOCALPLUS_UPPER_ROUNDOFF if localplus else 0.
    totals = {'source_rows': 0, 'rows_outside_requested_protein_axis': 0,
              'rows_outside_native_ontology': 0, 'rows_inside_both_axes': 0,
              'scores_in_upper_roundoff_band': 0, 'explicit_zero_rows': 0,
              'native_alias_source_rows': 0, 'native_cell_assignments': 0,
              'duplicate_native_cell_assignments': 0, 'maximum_source_score': 0.}
    files = []

    def assign(ns, rows, columns, scores):
        if not len(rows):
            return
        flat = rows * len(axes[ns]) + columns
        unique = np.unique(flat)
        totals['native_cell_assignments'] += len(flat)
        totals['duplicate_native_cell_assignments'] += int(len(flat) - len(unique)
            + np.count_nonzero(seen[ns].ravel()[unique]))
        np.maximum.at(matrices[ns].ravel(), flat, scores)
        seen[ns].ravel()[unique] = True

    for source in paths:
        source = Path(source)
        file_rows = 0
        try:
            # The C parser can silently truncate an extra field encountered
            # across a chunk boundary, even with on_bad_lines='error'. Reserve
            # an explicit fourth string field and require it to be empty:
            # any fourth-or-later token makes that guard nonempty. This keeps
            # native three-token input while making the C-parser boundary
            # independent of chunk size (covered by a regression fixture).
            reader = pd.read_csv(source, sep=r'\s+', header=None,
                names=[0, 1, 2, 3], index_col=False,
                dtype={0: str, 1: str, 2: np.float64, 3: str}, engine='c',
                quoting=csv.QUOTE_NONE, na_filter=False, float_precision='round_trip',
                chunksize=chunksize, compression='infer', on_bad_lines='error')
            with reader:
                for chunk in reader:
                    need(chunk.shape[1] == 4 and (chunk[3] == '').all(),
                         source.name + ': exactly three forecast columns required.')
                    scores = chunk[2].to_numpy(dtype=np.float64, copy=False)
                    need(np.isfinite(scores).all() and (scores >= 0).all()
                         and (scores <= 1 + tolerance).all(),
                         source.name + ': all source rows require finite qualified [0,1] scores; no clipping.')
                    rows = chunk[0].map(p_index).fillna(-1).to_numpy(dtype=np.int64)
                    ns_codes = chunk[1].map(term_namespace).fillna(-1).to_numpy(dtype=np.int64)
                    valid = (rows >= 0) & (ns_codes >= 0)
                    count = len(chunk)
                    file_rows += count
                    totals['source_rows'] += count
                    totals['rows_outside_requested_protein_axis'] += int(np.count_nonzero(rows < 0))
                    totals['rows_outside_native_ontology'] += int(np.count_nonzero(ns_codes < 0))
                    totals['rows_inside_both_axes'] += int(np.count_nonzero(valid))
                    totals['scores_in_upper_roundoff_band'] += int(np.count_nonzero(scores > 1))
                    totals['explicit_zero_rows'] += int(np.count_nonzero(scores == 0))
                    if count:
                        totals['maximum_source_score'] = max(totals['maximum_source_score'], float(scores.max()))
                    for ns_code, ns in enumerate(namespaces):
                        mask = valid & (ns_codes == ns_code)
                        if not np.any(mask):
                            continue
                        labels = chunk.loc[mask, 1]
                        indices = labels.map(direct[ns]).fillna(-1).to_numpy(dtype=np.int64)
                        row_subset, score_subset = rows[mask], scores[mask]
                        direct_mask = indices >= 0
                        assign(ns, row_subset[direct_mask], indices[direct_mask], score_subset[direct_mask])
                        alias_set = ontologies[ns].terms_dict_alt
                        totals['native_alias_source_rows'] += int(labels.isin(alias_set).sum())
                        # Native one-to-many alternative IDs are rare. Expand
                        # them exactly rather than selecting an arbitrary term.
                        for position in np.flatnonzero(~direct_mask):
                            alias = labels.iloc[position]
                            columns = np.asarray(multiple[ns][alias], dtype=np.int64)
                            assign(ns, np.full(len(columns), row_subset[position], dtype=np.int64),
                                   columns, np.full(len(columns), score_subset[position]))
        except pd.errors.EmptyDataError:
            pass  # Explicit all-zero, no-source-coverage intake below.
        files.append({'file': str(source), 'source_rows': file_rows})
    result = {ns: ScoreMatrix(proteins, axes[ns], matrices[ns], tolerance) for ns in namespaces}
    by_ns = {}
    for ns in namespaces:
        present = np.any(seen[ns], axis=1)
        observed = int(np.count_nonzero(seen[ns]))
        by_ns[ns] = {'targets_on_requested_axis': len(proteins),
            'targets_with_source_rows': int(np.count_nonzero(present)),
            'targets_without_source_rows': int(np.count_nonzero(~present)),
            'observed_native_cells': observed,
            'omitted_cells_filled_with_arithmetic_zero': int(matrices[ns].size - observed),
            'all_scores_zero': bool(not np.any(matrices[ns]))}
    return result, {**totals, 'files': files, 'by_namespace': by_ns,
        'duplicate_policy': 'native canonical/alternative-ID expansion then MAX before arithmetic',
        'outside_row_counts_are_nonexclusive': True,
        'all_requested_target_axes_retained': True,
        'source_score_transformation': 'none', 'upper_roundoff_tolerance': tolerance,
        'missing_score_meaning': 'zero for arithmetic only, not a biological negative',
        'ontology_propagation_performed': False}


def native_predictions(localplus, deepgo, alphas, ontologies):
    """Mix before this evaluator's closure, then native fill once per aspect.

    This timing concerns the current evaluator call. It makes no claim that
    component training annotations or model internals never used GO structure.
    A globally zero aspect retains its explicit zero/no-coverage matrix; the
    author's empty-matrix propagation path otherwise raises before its guard.
    """
    import numpy as np

    native = _native()['graph']
    axes = _term_axes(ontologies)
    need(set(localplus) == set(deepgo) == set(alphas) and bool(localplus),
         'identical nonempty aspect sets for both components and alphas required.')
    predictions = {}
    for ns in localplus:
        need(ns in axes and localplus[ns].terms == deepgo[ns].terms == axes[ns],
             'component term axes differ from the exact native ontology axis.')
        mixed = convex_mix(localplus[ns], deepgo[ns], alphas[ns])
        # Author propagate indexes the first nonzero column before checking
        # emptiness, so a globally zero namespace raises IndexError upstream.
        # Its fill operation is an identity on zeros: retain that explicit
        # zero forecast without invoking the known empty-matrix code path.
        if np.any(mixed.values):
            native.propagate(mixed.values, ontologies[ns], ontologies[ns].order, mode='fill')
        prediction = native.Prediction(
            {protein: index for index, protein in enumerate(mixed.proteins)}, mixed.values, ns)
        # Native Prediction carries row IDs but no column IDs. Retain the
        # already-verified axis as adapter metadata so a same-sized, different
        # ontology cannot silently pass the later evaluation boundary.
        prediction._learned_combination_terms = mixed.terms
        predictions[ns] = prediction
    return predictions


def _ordered_ids(value, label):
    ids = value.ids
    need(len(ids) == value.matrix.shape[0]
         and set(ids.values()) == set(range(len(ids))),
         label + ': complete unique native row identity mapping required.')
    ordered = [None] * len(ids)
    for protein, index in ids.items():
        ordered[index] = protein
    return tuple(ordered)


def align_predictions(predictions, ground_truth):
    """Reorder/subset forecasts to native GT rows; never infer equal-shaped IDs."""
    import numpy as np

    native = _native()['graph']
    aligned = {}
    for ns, gt in ground_truth.items():
        need(ns in predictions, 'ground-truth namespace has no complete forecast matrix: ' + ns)
        pred = predictions[ns]
        _ordered_ids(pred, 'prediction')
        gt_ids = _ordered_ids(gt, 'ground truth')
        need(set(gt_ids) <= set(pred.ids),
             'ground-truth targets are outside the exact captured forecast axis.')
        need(pred.matrix.shape[1] == gt.matrix.shape[1], 'prediction and native ground-truth term axes differ.')
        rows = np.asarray([pred.ids[protein] for protein in gt_ids], dtype=np.int64)
        aligned[ns] = native.Prediction(dict(gt.ids), pred.matrix[rows, :], ns)
        need(hasattr(pred, '_learned_combination_terms'),
             'explicit captured prediction term-axis metadata is required.')
        aligned[ns]._learned_combination_terms = pred._learned_combination_terms
    return aligned


def evaluate_native(predictions, ground_truth, ontologies, *, gt_exclude=None,
                    tau=None, n_cpu=1):
    """Return unchanged native ordinary curves and namespace micro-Fmax.

    Predictions must already be explicitly aligned via ``align_predictions``.
    Default thresholds are the byte-identical native ``np.arange(.001,1,.001)``.
    A declared coarser development grid is accepted through ``tau``. No IA,
    weighted endpoint, threshold fit, or final-test selection is added here.
    Native unscorable namespaces are represented by None, not invented gains.
    """
    import numpy as np
    import pandas as pd

    native = _native()['evaluation']
    axes = _term_axes(ontologies)
    tau = np.arange(.001, 1, .001) if tau is None else np.asarray(tau, dtype=np.float64)
    need(tau.ndim == 1 and len(tau) > 0 and np.isfinite(tau).all()
         and (tau > 0).all() and (tau < 1).all() and (np.diff(tau) > 0).all(),
         'strictly increasing finite native threshold grid within (0,1) required.')
    need(isinstance(n_cpu, int) and not isinstance(n_cpu, bool) and n_cpu > 0,
         'explicit positive CPU count required.')
    selected = {}
    summary = {}
    for ns, gt in ground_truth.items():
        need(ns in axes and ns in predictions, 'native GT namespace lacks ontology or forecast.')
        pred = predictions[ns]
        need(_ordered_ids(pred, 'prediction') == _ordered_ids(gt, 'ground truth')
             and pred.matrix.shape == gt.matrix.shape,
             'prediction/ground-truth row identities differ; call align_predictions explicitly.')
        need(pred.matrix.shape[1] == len(axes[ns]), 'native prediction/ontology term axes differ.')
        need(getattr(pred, '_learned_combination_terms', None) == axes[ns],
             'exact captured prediction term IDs/order differ from native ontology.')
        if gt_exclude is not None:
            need(ns in gt_exclude and gt_exclude[ns].ids == gt.ids
                 and gt_exclude[ns].matrix.shape == gt.matrix.shape,
                 'native exclusion rows/shape differ from ground truth.')
        summary[ns] = None
        if np.any(gt.matrix[:, ontologies[ns].toi]):
            selected[ns] = pred
    if not selected:
        return pd.DataFrame(), summary
    curve = native.evaluate_prediction(selected, ground_truth, ontologies, tau,
        gt_exclude=gt_exclude, normalization='cafa', n_cpu=n_cpu)
    for ns, group in curve.groupby('ns', sort=False):
        # Native cafa_eval drops zero-coverage thresholds before selecting a
        # best metric. Keep the exact evaluate_prediction curve for inspection
        # but do not manufacture a scored zero endpoint when it has no rows.
        # cov is also nonpositive/NaN if known-term exclusion leaves ne == 0.
        available = group.loc[group['cov'] > 0]
        if not available.empty:
            summary[ns] = float(available['f_micro'].max())
    return curve, summary
