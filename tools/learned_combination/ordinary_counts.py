# SPDX-License-Identifier: GPL-3.0-only
"""Efficient ordinary CAFA contributions, gated against the pinned evaluator.

This is a numeric adapter for the existing author metric, not another biological
scoring protocol. NumPy1.26 documents ``searchsorted(..., side='left')`` as the
first insertion boundary before equal values, so ``size - boundary`` counts
exactly scores >= tau, including ties. Documentation and corresponding source:
https://numpy.org/doc/1.26/reference/generated/numpy.searchsorted.html
https://github.com/numpy/numpy/blob/v1.26.0/numpy/core/fromnumeric.py

Native compute_metrics first includes rows with GT in ordinary TOI, then removes
known terms. A row whose GT is entirely known can still contribute FP. Rows
without pre-exclusion GT in TOI contribute six zeros, even with predictions.
"""
from .core import LOCALPLUS_UPPER_ROUNDOFF, need
from .native_adapter import _native, _ordered_ids

COLUMNS = ('n', 'tp', 'fp', 'fn', 'pr', 'rc')
CURVE_COLUMNS = COLUMNS + ('cov', 'mi', 'ru', 'f', 's', 'pr_micro', 'rc_micro', 'f_micro')


def _tau(values):
    import numpy as np
    values = np.asarray(values, dtype=np.float64)
    need(values.ndim == 1 and len(values) > 0 and np.isfinite(values).all()
         and (values > 0).all() and (values < 1).all()
         and (np.diff(values) > 0).all(),
         'ordinary counts require a strictly increasing finite threshold grid inside (0,1).')
    return values


def contributions(prediction, gt, ontology, tau, exclude=None):
    """Return ``(Nprotein,Ntau,6)`` counts and native pre-exclusion row mask.

    Inputs are already propagated, explicitly aligned native forecast/GT objects.
    The returned mask follows compute_metrics *before* known-term exclusion;
    it must not be replaced with a positive residual-GT mask. No input is changed.
    """
    import numpy as np

    _native()  # Source pins, not merely a compatible-looking implementation.
    tau = _tau(tau)
    need(ontology.ia is None, 'ordinary contributions require native IA None.')
    ids = _ordered_ids(gt, 'ground truth')
    need(_ordered_ids(prediction, 'prediction') == ids,
         'native prediction and ground-truth identity axes differ.')
    scores, truth = np.asarray(prediction.matrix), np.asarray(gt.matrix)
    need(scores.ndim == 2 and scores.shape == truth.shape
         and scores.dtype.kind in 'fiu' and np.isfinite(scores).all()
         and (scores >= 0).all() and (scores <= 1 + LOCALPLUS_UPPER_ROUNDOFF).all(),
         'finite qualified score matrix matching ground truth required.')
    need(truth.dtype.kind in 'biu' and ((truth == 0) | (truth == 1)).all(),
         'native binary ground truth required.')
    toi = np.asarray(ontology.toi)
    need(toi.ndim == 1 and toi.dtype.kind in 'iu' and len(set(toi.tolist())) == len(toi)
         and (toi >= 0).all() and (toi < truth.shape[1]).all(),
         'unique native ordinary term-of-interest indexes required.')
    if exclude is not None:
        need(_ordered_ids(exclude, 'known exclusion') == ids
             and exclude.matrix.shape == truth.shape,
             'known-exclusion identities or matrix shape differ.')
    eligible = np.asarray(truth[:, toi].sum(axis=1) > 0, dtype=bool)
    counts = np.zeros((len(ids), len(tau), 6), dtype=np.float64)
    for row in np.flatnonzero(eligible):
        available = toi if exclude is None else np.setdiff1d(
            toi, exclude.matrix[row, :].nonzero()[0], assume_unique=True)
        values = scores[row, available]
        positive = truth[row, available].astype(bool, copy=False)
        n_gt = int(np.count_nonzero(positive))
        ordered = np.sort(values)
        true_ordered = np.sort(values[positive])
        n_pred = len(ordered) - np.searchsorted(ordered, tau, side='left')
        tp = len(true_ordered) - np.searchsorted(true_ordered, tau, side='left')
        counts[row, :, 0] = n_pred > 0
        counts[row, :, 1] = tp
        counts[row, :, 2] = n_pred - tp
        counts[row, :, 3] = n_gt - tp
        counts[row, :, 4] = np.divide(tp, n_pred,
            out=np.zeros(len(tau), dtype=np.float64), where=n_pred > 0)
        if n_gt:
            counts[row, :, 5] = tp / n_gt
    return counts, eligible


def verify_curve(counts, native_curve, *, namespace, tolerance=1e-12):
    """Require the complete summed contribution curve to match native output.

    Native normalization is called unchanged. This includes its post-exclusion
    number of annotated proteins, while the counts preserve pre-exclusion row
    admission. Every ordinary numeric curve column must agree before resampling.
    """
    import numpy as np
    import pandas as pd

    native = _native()['evaluation']
    counts = np.asarray(counts)
    need(counts.ndim == 3 and counts.shape[2] == 6 and counts.shape[0] > 0
         and np.isfinite(counts).all() and (counts >= 0).all(),
         'finite nonnegative per-protein six-column counts required.')
    need(isinstance(tolerance, (int, float)) and not isinstance(tolerance, bool)
         and 0 <= tolerance <= 1e-12, 'curve tolerance must be at most 1e-12.')
    need('ns' in native_curve and 'tau' in native_curve,
         'native namespace/threshold curve required.')
    curve = native_curve.loc[native_curve['ns'] == namespace].reset_index(drop=True)
    need(len(curve) == counts.shape[1], 'native threshold and contribution axes differ.')
    tau = _tau(curve['tau'].to_numpy())
    totals = counts.sum(axis=0)
    n_gt = counts[:, :, 1] + counts[:, :, 3]
    need(np.array_equal(n_gt, np.broadcast_to(n_gt[:, :1], n_gt.shape)),
         'per-protein residual ground truth differs across thresholds.')
    ne = int(np.count_nonzero(n_gt[:, 0] > 0))
    need(ne > 0, 'no residual-GT proteins: ordinary Fmax comparison is unscorable.')
    reconstructed = native.normalize(pd.DataFrame(totals, columns=COLUMNS), namespace,
                                     tau, np.full(len(tau), ne), 'cafa')
    differences = {}
    for column in CURVE_COLUMNS:
        need(column in curve, 'native curve lacks ordinary column: ' + column)
        expected = curve[column].to_numpy(dtype=np.float64)
        actual = reconstructed[column].to_numpy(dtype=np.float64)
        need(np.isfinite(expected).all() and np.isfinite(actual).all(),
             'nonfinite native/contribution curve: ' + column)
        difference = float(np.max(np.abs(expected - actual)))
        differences[column] = difference
        need(difference <= tolerance,
             'ordinary contribution/native full-curve mismatch: ' + column)
    return {'author_point_agreement_passed': True, 'namespace': namespace,
            'raw_protein_rows': int(counts.shape[0]),
            'post_exclusion_GT_proteins': ne, 'thresholds': len(tau),
            'ordinary_only': True, 'IA_supplied': False,
            'max_absolute_curve_difference': max(differences.values()),
            'absolute_tolerance': tolerance, 'columns': differences,
            'pre_exclusion_native_row_admission_preserved': True}


def paired_bootstrap(arrays, *, draws=2000, seed=20261113):
    """Ordinary-only paired resampling; callers must first gate verify_curve.

    Uses the existing micro_fmax implementation and the exact established RNG,
    draw count and whole-protein multinomial multiplicities. No fake IA channel
    is constructed. Returned per-draw arrays are JSON lists for saved artifacts.
    """
    import numpy as np
    from tools.cafa_reference.paired_bootstrap import DRAWS, SEED, micro_fmax

    need(type(draws) is int and draws == DRAWS and type(seed) is int and seed == SEED,
         'predeclared 2000 draws and seed20261113 required.')
    need(arrays and 'learned_mix' in arrays and len(arrays) >= 2,
         'learned_mix and at least one fixed comparator required.')
    first = next(iter(arrays.values()))
    ids, tau = np.asarray(first['ids']), _tau(first['tau'])
    need(ids.ndim == 1 and len(ids) > 1 and len(set(ids.tolist())) == len(ids),
         'at least two uniquely identified reference protein rows required.')
    for row in arrays.values():
        values = np.asarray(row['ordinary'])
        need(np.array_equal(np.asarray(row['ids']), ids)
             and np.array_equal(np.asarray(row['tau']), tau),
             'paired method protein or threshold axes differ.')
        need(values.shape == (len(ids), len(tau), 6)
             and np.isfinite(values).all() and (values >= 0).all(),
             'finite nonnegative ordinary author contributions required.')
    rng = np.random.default_rng(seed)
    weights = rng.multinomial(len(ids), np.repeat(1 / len(ids), len(ids)),
                             size=draws).astype(np.float64)
    scores = {name: micro_fmax(np.asarray(row['ordinary']), weights)
              for name, row in arrays.items()}
    result = {'draws': draws, 'seed': seed, 'raw_proteins': len(ids),
              'ordinary_only': True, 'IA_supplied': False,
              'shared_protein_samples_across_all_arms': True,
              'required_prior_gate': 'verify_curve passed for every arm/namespace',
              'scores': {}, 'comparisons': []}
    for name, values in scores.items():
        result['scores'][name] = {'bootstrap_Fmax': values.tolist(),
            'bootstrap_mean': float(values.mean()),
            'bootstrap_95_percentile_interval': np.quantile(values, [.025, .975]).tolist()}
    for name in scores:
        if name == 'learned_mix':
            continue
        difference = scores['learned_mix'] - scores[name]
        result['comparisons'].append({'candidate': 'learned_mix', 'comparator': name,
            'difference_draws': difference.tolist(), 'difference_mean': float(difference.mean()),
            'paired_95_percentile_interval': np.quantile(difference, [.025, .975]).tolist(),
            'fraction_draws_above_zero': float((difference > 0).mean()),
            'interpretation': 'Conditional paired protein bootstrap; incomplete reference is not negative biology.'})
    return result
