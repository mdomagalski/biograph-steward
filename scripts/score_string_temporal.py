#!/usr/bin/env python3
"""Replay native STRING 12.0 scores against an already-consumed assay panel.

The temporal control queries functional and physical networks independently.
It preserves the original 12.5 result and does not claim unseen validation,
scientific accuracy, direct binding, or a Steward-specific graph improvement.
"""
from __future__ import annotations

import argparse
from collections import Counter
from html import escape
import math
from pathlib import Path
import platform
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / 'scripts'))

from biograph_steward.client import digest, utcnow, write_json
from biograph_steward.file_utils import new_output, sha
from biograph_steward.gold_packet import _decode
import score_string_component as established

ARMS = established.ARMS
UNRANKED = established.UNRANKED
SCORING_PYTHON = '3.12.4'
SKLEARN_VERSION = established.SKLEARN_VERSION
UNRANKED_STATES = frozenset({'unmapped', 'ambiguous', 'collapsed_representative',
                            'no_returned_native_row'})
PREDICTION_FIELDS = frozenset({'products', 'source_row', 'mapping_states',
                             'mapping_proof', 'query_batch', 'views'})


def _validate_view(view):
    if not isinstance(view, dict) or set(view) != {'state', 'native_score', 'ranking_score'}:
        raise ValueError('Native prediction view must contain only source state and raw/ranking scores.')
    state, native, ranking = view['state'], view['native_score'], view['ranking_score']
    if state == 'numeric':
        if (type(native) not in (int, float) or not math.isfinite(native)
                or not 0 <= native <= 1 or type(ranking) not in (int, float)
                or not math.isfinite(ranking) or native != ranking):
            raise ValueError('Native numeric score must be finite 0..1 and unchanged for ranking.')
    elif state in UNRANKED_STATES:
        if native is not None or type(ranking) not in (int, float) or ranking != UNRANKED:
            raise ValueError('Legitimate unranked state requires null native score and ordinal -1.')
    else:
        raise ValueError('Unknown/technical source state cannot be imputed into ranking.')


def _validate_projection(prediction):
    if (set(prediction) != PREDICTION_FIELDS or not isinstance(prediction['views'], dict)
            or set(prediction['views']) != set(ARMS)):
        raise ValueError('Temporal predictions must be label-free fixed native views for the exact candidate.')
    for view in prediction['views'].values():
        _validate_view(view)
    states, proofs, batches = (prediction[field] for field in
                              ('mapping_states', 'mapping_proof', 'query_batch'))
    if (not isinstance(states, list) or len(states) != 2
            or any(state not in established.MAPPING_STATES for state in states)
            or not isinstance(proofs, list) or len(proofs) != 2
            or not isinstance(batches, dict) or set(batches) != set(ARMS)):
        raise ValueError('Exactly two endpoint mapping states/proofs and separate native query batches required.')
    representatives = []
    for accession, state, proof in zip(prediction['products'], states, proofs):
        if (not isinstance(proof, dict) or proof.get('accession') != accession
                or proof.get('status') != state):
            raise ValueError('Mapping proof must retain its exact input accession/status.')
        representative = proof.get('string_id')
        if ((state == 'resolved' and (not isinstance(representative, str)
                                     or not representative.startswith('9606.')
                                     or representative == '9606.'))
                or (state != 'resolved' and representative is not None)):
            raise ValueError('Human representative differs from the endpoint mapping state.')
        representatives.append(representative)
    expected = ('unmapped' if 'unmapped' in states else
                'ambiguous' if any(state in {'ambiguous', 'mapping_limit_reached'} for state in states) else
                'collapsed_representative' if representatives[0] == representatives[1] else None)
    if expected is not None:
        if any(batches[arm] is not None or prediction['views'][arm]['state'] != expected for arm in ARMS):
            raise ValueError('Mapping missingness/collapse cannot be treated as a queried native pair.')
    else:
        for arm in ARMS:
            if (not isinstance(batches[arm], str) or not batches[arm]
                    or prediction['views'][arm]['state'] not in {'numeric', 'no_returned_native_row'}):
                raise ValueError('Distinct resolved endpoints require captured native queries and native row states.')
        # Neither network is an overlay on the other. A physical-only row is valid.


def _validate_join(candidates, label_rows, predictions, reference_predictions):
    # The established strict source/construct/exposure join is replayed on its
    # unchanged, schema-compatible 12.5 packet. No synthetic overlay is fabricated.
    joined = established._validate_join(candidates, label_rows, reference_predictions)
    indexed = established._index(predictions)
    if set(indexed) != {established._pair_key(row['candidate']) for row in joined}:
        raise ValueError('Temporal prediction population differs from the fixed consumed reference.')
    result = []
    for row in joined:
        prediction = indexed[established._pair_key(row['candidate'])]
        _validate_projection(prediction)
        result.append({**row, 'prediction': prediction})
    return result


def score_rows(candidates, label_rows, predictions, reference_predictions):
    """Validate exact joins and score the declared 12.0 native-network control."""
    import sklearn
    from sklearn.metrics import average_precision_score
    if sklearn.__version__ != SKLEARN_VERSION:
        raise ValueError('Scoring requires pinned scikit-learn ' + SKLEARN_VERSION + '.')
    joined = _validate_join(candidates, label_rows, predictions, reference_predictions)
    eligible = [row for row in joined if row['assay']['evaluable']]
    common = [row for row in eligible if all(
        row['prediction']['views'][arm]['state'] == 'numeric' for arm in ARMS)]

    def fingerprints(rows):
        return {arm: digest([{'products': row['prediction']['products'],
            'source_row': row['prediction']['source_row'],
            'ranking_score': row['prediction']['views'][arm]['ranking_score']} for row in rows])
            for arm in ARMS}

    eligible_fingerprints, all_fingerprints = fingerprints(eligible), fingerprints(joined)
    strata = {}
    for huri in (False, True):
        for inmc in (False, True):
            selected = [row for row in joined
                        if row['candidate']['exposure']['huri_overlap'] is huri
                        and row['candidate']['exposure']['inmc_overlap'] is inmc]
            selected_eligible = [row for row in selected if row['assay']['evaluable']]
            strata[f'huri={huri},inmc={inmc}'] = {'all_nominations': len(selected),
                'assay_eligible': len(selected_eligible),
                'coverage_all': {arm: established._coverage(selected, arm) for arm in ARMS},
                'coverage_eligible': {arm: established._coverage(selected_eligible, arm) for arm in ARMS},
                'full_panel': established._comparison(selected_eligible, average_precision_score)}
    return {'format': 'biograph-steward.string-temporal-metrics.v1',
        'source_release': '12.0', 'predictor_design': 'separate_native_networks',
        'dataset_status': 'consumed_development',
        'selection_status': 'temporal_control_selected_after_consumed_12.5_result',
        'metric': 'sklearn.metrics.average_precision_score',
        'runtime': {'python': platform.python_version(), 'scikit_learn': sklearn.__version__},
        'primary_population': {'all_nominations': len(joined), 'assay_eligible': len(eligible),
            'detected': sum(row['assay']['detected'] is True for row in eligible),
            'not_detected': sum(row['assay']['detected'] is False for row in eligible),
            'assay_excluded': len(joined) - len(eligible),
            'exclusions': dict(sorted(Counter(row['assay']['assay_status'] for row in joined
                                               if not row['assay']['evaluable']).items()))},
        'coverage_all': {arm: established._coverage(joined, arm) for arm in ARMS},
        'coverage_eligible': {arm: established._coverage(eligible, arm) for arm in ARMS},
        'full_panel': established._comparison(eligible, average_precision_score),
        'jointly_numeric': {'selection': 'Both 12.0 native scores explicitly numeric; actual conditional population.',
            'comparison': established._comparison(common, average_precision_score)},
        'ranking_vectors': {'eligible_sha256': eligible_fingerprints,
            'identical_eligible_inputs': eligible_fingerprints['functional'] == eligible_fingerprints['physical'],
            'all_nominations_sha256': all_fingerprints,
            'identical_all_nominated_inputs': all_fingerprints['functional'] == all_fingerprints['physical']},
        'exposure_strata': strata,
        'historical_pharos_descriptive_anchor': {
            'role': 'Different source-release presence lookup; not a third matched arm.',
            'all_nominations_states': dict(sorted(Counter(row['candidate']['pharos_status'] for row in joined).items())),
            'eligible_states': dict(sorted(Counter(row['candidate']['pharos_status'] for row in eligible).items())),
            'eligible_with_known_presence': sum(row['candidate']['historical_pharos_comparator_eligible'] for row in eligible)},
        'unranked_policy': {'ordinal_value': UNRANKED, 'all_native_numeric_scores_above_unranked': True,
            'meaning': 'Retrieval ordering only; neither confidence nor a biological negative.'},
        'temporal_control': True, 'study_independence_established': False,
        'steward_improvement_tested': False, 'scientific_accuracy_measured': False,
        'confidence_intervals_computed': False, 'thresholds_tuned': False, 'graph_modified': False}


def _write_html(output, metrics):
    def number(value):
        return 'Unscorable' if value is None else f'{value:.4f}'
    def table(comparison):
        rows = []
        for arm in ARMS:
            item = comparison['arms'][arm]
            rows.append('<tr>' + ''.join('<td>' + escape(str(value)) + '</td>' for value in
                (arm, item['pairs'], item['explicit_numeric'], item['detected'],
                 number(item['average_precision']), item['status'])) + '</tr>')
        return ('<table><tr><th>Native network</th><th>Pairs</th><th>Numeric scores</th>'
                '<th>Detected</th><th>Average precision</th><th>Status</th></tr>' + ''.join(rows) + '</table>')
    population = metrics['primary_population']
    body = ('<h1>STRING 12.0 temporal development control</h1>'
        '<p>Separate native functional and physical networks, scored against previously consumed human Y2H-v1 outcomes. '
        'This older-source control was selected after seeing the 12.5 result. '
        'It is neither unseen independent confirmation nor a Steward-specific improvement test.</p>'
        f'<p>All {population["all_nominations"]:,} nominations retained; {population["assay_eligible"]:,} eligible pairs '
        f'({population["detected"]:,} detected, {population["not_detected"]:,} not detected). '
        f'{population["assay_excluded"]:,} pre-existing exclusions remain accounted for.</p>'
        '<h2>Primary: full eligible population</h2>' + table(metrics['full_panel'])
        + '<p>Physical minus functional AP: '
        + escape(number(metrics['full_panel']['physical_minus_functional_average_precision']))
        + '. A valid missing native row ties below explicit numeric zero; it is not an inferred biological negative.</p>'
        + '<h2>Secondary: actual jointly numeric population</h2>'
        + table(metrics['jointly_numeric']['comparison'])
        + '<p>This release-specific conditional population does not replace the primary denominator.</p>'
        + '<h2>Prior exposure strata</h2>')
    for name, stratum in metrics['exposure_strata'].items():
        body += '<h3>' + escape(name) + '</h3>' + table(stratum['full_panel'])
    body += ('<p>Numeric coverage and complete source states appear in '
        '<a href="metrics.json">metrics.json</a>. '
        'Earlier HuRI evidence and other shared inputs remain possible. Unflagged does not mean independent. '
        'The separate native 12.0 networks differ from the 12.5 typed overlay; '
        'cross-release score changes cannot isolate study ingestion or a graph intervention. '
        'Nondetection is assay-conditional. No threshold tuning or confidence interval was used.</p>'
        '<p><a href="report.json">Verification receipt</a></p>')
    (output / 'report.html').write_text('<!doctype html><html lang="en"><meta charset="utf-8">'
        '<title>STRING 12.0 temporal control</title><style>body{font:16px system-ui;max-width:1100px;'
        'margin:40px auto;padding:0 20px;line-height:1.5}table{width:100%;border-collapse:collapse}'
        'th,td{padding:9px;border-bottom:1px solid #ccc;text-align:left}th{background:#edf2f6}'
        '</style>' + body + '</html>', encoding='utf-8')


def _implementation_hashes():
    return {'scripts/score_string_temporal.py': sha(Path(__file__)),
            'scripts/score_string_component.py': sha(Path(established.__file__))}


def _verified_capture(capture):
    import run_string_temporal as runner
    captured = runner.verify_capture(Path(capture))
    if (platform.python_version() != SCORING_PYTHON
            or captured['protocol']['rules']['scoring_python'] != SCORING_PYTHON):
        raise ValueError('Scoring Python runtime differs from the pinned temporal protocol.')
    return captured


def score_capture(capture, output):
    captured = _verified_capture(capture)
    metrics = score_rows(captured['candidates'], captured['label_rows'],
                         captured['predictions'], captured['reference_predictions'])
    out = new_output(output, capture)
    write_json(out / 'metrics.json', metrics)
    _write_html(out, metrics)
    scorable = all(metrics['full_panel']['arms'][arm]['status'] == 'scored' for arm in ARMS)
    report = established._seal({'format': 'biograph-steward.string-temporal-result.v1',
        'created_at': utcnow(), 'status': 'completed' if scorable else 'unscorable_comparison',
        'capture_report_sha256': captured['report']['content_sha256'],
        'protocol_sha256': captured['protocol']['content_sha256'],
        'source_release': '12.0', 'predictor_design': 'separate_native_networks',
        'dataset_status': 'consumed_development', 'new_outcome_source_accesses': 0,
        'temporal_control': True, 'study_independence_established': False,
        'steward_improvement_tested': False, 'scientific_accuracy_measured': False, 'graph_modified': False,
        'implementation_sha256': _implementation_hashes(),
        'files': {name: sha(out / name) for name in ('metrics.json', 'report.html')}})
    write_json(out / 'report.json', report)
    verify_result(capture, out)
    return report


def verify_result(capture, output):
    captured = _verified_capture(capture)
    folder = Path(output)
    if any(path.is_symlink() for path in (folder, *folder.parents)) or not folder.is_dir():
        raise ValueError('Use an ordinary result directory without symlink traversal.')
    if any(path.is_symlink() for path in folder.rglob('*')):
        raise ValueError('Result contains a symlink.')
    report = _decode((folder / 'report.json').read_bytes())
    if (not isinstance(report, dict) or report.get('content_sha256') !=
            digest({key: value for key, value in report.items() if key != 'content_sha256'})):
        raise ValueError('Result content receipt differs.')
    files = {path.relative_to(folder).as_posix(): sha(path) for path in folder.rglob('*')
             if path.is_file() and path.name != 'report.json'}
    if (report.get('format') != 'biograph-steward.string-temporal-result.v1'
            or report.get('files') != files or set(files) != {'metrics.json', 'report.html'}
            or report.get('capture_report_sha256') != captured['report']['content_sha256']
            or report.get('protocol_sha256') != captured['protocol']['content_sha256']
            or report.get('implementation_sha256') != _implementation_hashes()
            or report.get('source_release') != '12.0'
            or report.get('predictor_design') != 'separate_native_networks'
            or report.get('dataset_status') != 'consumed_development'
            or report.get('new_outcome_source_accesses') != 0 or report.get('temporal_control') is not True
            or any(report.get(flag) is not False for flag in ('study_independence_established',
                'steward_improvement_tested', 'scientific_accuracy_measured', 'graph_modified'))):
        raise ValueError('Result files, capture, protocol or implementation differ.')
    actual = _decode((folder / 'metrics.json').read_bytes())
    expected = score_rows(captured['candidates'], captured['label_rows'],
                          captured['predictions'], captured['reference_predictions'])
    if actual != expected:
        raise ValueError('Metrics do not reproduce from the sealed native predictions.')
    scorable = all(expected['full_panel']['arms'][arm]['status'] == 'scored' for arm in ARMS)
    if report.get('status') != ('completed' if scorable else 'unscorable_comparison'):
        raise ValueError('Unscorable support cannot be reported as a completed comparison.')
    return report


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--capture', type=Path, required=True)
    parser.add_argument('--out', type=Path, required=True)
    parser.add_argument('--verify', action='store_true')
    args = parser.parse_args(argv)
    try:
        report = verify_result(args.capture, args.out) if args.verify else score_capture(args.capture, args.out)
    except (ValueError, OSError, KeyError, TypeError, ImportError) as exc:
        parser.exit(1, f'ERROR: {exc}\n')
    print(f"{report['status']}: {args.out.absolute()}")
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
