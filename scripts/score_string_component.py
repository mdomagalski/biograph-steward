#!/usr/bin/env python3
"""Score the fixed STRING component on previously consumed assay outcomes.

This module never retrieves predictors or decodes new assay source files.
Average precision is the existing scikit-learn implementation; missingness is
kept as a source state and the declared ordinal unranked value is not confidence.
"""
from __future__ import annotations

import argparse
from collections import Counter
from html import escape
from pathlib import Path
import math
import platform
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / 'scripts'))

from biograph_steward.client import digest, utcnow, write_json
from biograph_steward.file_utils import new_output, sha
from biograph_steward.gold_packet import _decode

ARMS = ('functional', 'physical')
UNRANKED = -1
SKLEARN_VERSION = '1.9.1'
EXPOSURE_FLAGS = ('huri_registry_projected_match', 'huri_author_crosswalk_match',
                  'inmc_registry_projected_match', 'inmc_author_crosswalk_match')
ASSAY_STATES = ('detected', 'not_detected', 'test_failed', 'autoactivator',
                'failed_sequence_confirmation', 'ambiguous_sequence_confirmation',
                'inconsistent', 'unexpected_state')
# These are legitimate source outcomes, never technical retrieval failures.
UNRANKED_STATES = frozenset({'unmapped', 'ambiguous', 'collapsed_representative',
                            'no_returned_functional_row',
                            'physical_not_returned_under_profile'})
MAPPING_STATES = frozenset({'resolved', 'unmapped', 'ambiguous', 'mapping_limit_reached'})


def _pair_key(row):
    if not isinstance(row, dict):
        raise ValueError('Pair row must be an object.')
    products, source_row = row.get('products'), row.get('source_row')
    if (not isinstance(products, list) or len(products) != 2
            or any(not isinstance(p, str) or not p for p in products)
            or products != sorted(set(products)) or type(source_row) is not int
            or source_row < 1):
        raise ValueError('Exact unordered accession pair and positive source row required.')
    return tuple(products), source_row


def _index(rows):
    if not isinstance(rows, list):
        raise ValueError('A complete list of pair rows is required.')
    indexed, seen_pairs, seen_sources = {}, set(), set()
    for row in rows:
        key = _pair_key(row)
        if key in indexed or key[0] in seen_pairs or key[1] in seen_sources:
            raise ValueError('Duplicate pair or source-row identity.')
        indexed[key] = row
        seen_pairs.add(key[0]); seen_sources.add(key[1])
    return indexed


def _validate_view(view, arm):
    if not isinstance(view, dict) or set(view) != {'state', 'native_score', 'ranking_score'}:
        raise ValueError('Prediction view must contain only raw state/native/ranking scores.')
    state, native, ranking = view['state'], view['native_score'], view['ranking_score']
    if state == 'numeric':
        if (type(native) not in (int, float) or not math.isfinite(native)
                or not 0 <= native <= 1 or type(ranking) not in (int, float)
                or not math.isfinite(ranking) or ranking != native):
            raise ValueError('Native numeric score must be finite 0..1 and unchanged for ranking.')
    elif state in UNRANKED_STATES:
        if state == 'physical_not_returned_under_profile' and arm != 'physical':
            raise ValueError('Only the physical overlay can have a physical unavailable state.')
        if native is not None or type(ranking) not in (int, float) or ranking != UNRANKED:
            raise ValueError('Legitimate unranked state requires null native score and ordinal -1.')
    else:
        raise ValueError('Unknown/technical source state cannot be imputed into ranking.')


def _validate_projection(prediction):
    states, proofs, batch = (prediction[field] for field in ('mapping_states', 'mapping_proof', 'query_batch'))
    if (not isinstance(states, list) or len(states) != 2 or any(s not in MAPPING_STATES for s in states)
            or not isinstance(proofs, list) or len(proofs) != 2):
        raise ValueError('Exactly two explicit endpoint mapping states/proofs are required.')
    representatives = []
    for accession, state, proof in zip(prediction['products'], states, proofs):
        if (not isinstance(proof, dict) or proof.get('accession') != accession
                or proof.get('status') != state):
            raise ValueError('Mapping proof must retain its exact input accession/status.')
        representative = proof.get('string_id')
        if ((state == 'resolved' and (not isinstance(representative, str)
                                     or not representative.startswith('9606.') or representative == '9606.'))
                or (state != 'resolved' and representative is not None)):
            raise ValueError('Resolved human STRING representative differs from mapping state.')
        representatives.append(representative)
    expected = ('unmapped' if 'unmapped' in states else
                'ambiguous' if any(s in {'ambiguous', 'mapping_limit_reached'} for s in states) else
                'collapsed_representative' if representatives[0] == representatives[1] else None)
    views = prediction['views']
    if expected is not None:
        if batch is not None or any(views[arm]['state'] != expected for arm in ARMS):
            raise ValueError('Mapping missingness/collapse must not be treated as a queried pair.')
    else:
        if not isinstance(batch, str) or not batch:
            raise ValueError('Resolved distinct endpoints require a captured query batch.')
        left, right = (views[arm]['state'] for arm in ARMS)
        if ((left == 'no_returned_functional_row' and right != left)
                or (left != 'no_returned_functional_row' and
                    (left != 'numeric' or right not in {'numeric', 'physical_not_returned_under_profile'}))):
            raise ValueError('Functional row/physical overlay source states disagree.')


def _validate_join(candidates, label_rows, predictions):
    candidate_index, prediction_index = _index(candidates), _index(predictions)
    if not candidate_index:
        raise ValueError('The fixed nominated population cannot be empty.')
    labels = []
    for row in label_rows:
        if (not isinstance(row, dict)
                or set(row) != {'comparator', 'assay', 'comparator_evaluable'}):
            raise ValueError('Use the unchanged consumed assessment result rows.')
        labels.append(row['comparator'])
    label_index = _index(labels)
    if set(candidate_index) != set(prediction_index) or set(candidate_index) != set(label_index):
        raise ValueError('Candidate/prediction/consumed outcome populations differ.')
    by_key = {_pair_key(row['comparator']): row for row in label_rows}
    joined = []
    for key in sorted(candidate_index):
        candidate, prediction = candidate_index[key], prediction_index[key]
        label = by_key[key]; comp, assay = label['comparator'], label['assay']
        if (set(prediction) != {'products', 'source_row', 'mapping_states',
                               'mapping_proof', 'query_batch', 'views'}
                or not isinstance(prediction['views'], dict)
                or set(prediction['views']) != set(ARMS)):
            raise ValueError('Predictions must be label-free fixed views for the exact candidate.')
        for arm in ARMS:
            _validate_view(prediction['views'][arm], arm)
        _validate_projection(prediction)
        if not isinstance(assay, dict) or _pair_key(assay) != key:
            raise ValueError('Consumed assay pair/source row differs.')
        identity = comp.get('identity', {})
        constructs = candidate.get('constructs', {})
        if (set(constructs) != {'ad_orf_id', 'db_orf_id', 'protein_to_construct_orientation_inferred'}
                or constructs['protein_to_construct_orientation_inferred'] is not False
                or identity.get('source_row') != key[1]
                or sorted((identity.get('uniprot_a', ''), identity.get('uniprot_b', ''))) != list(key[0])):
            raise ValueError('Exact author construct/accession identity is missing or changed.')
        for field in ('ad_orf_id', 'db_orf_id'):
            if (not isinstance(constructs[field], str) or not constructs[field]
                    or constructs[field] != assay.get(field)
                    or constructs[field] != identity.get(field)):
                raise ValueError('AD/DB constructs must match the consumed author identity.')
        status, eligible, detected = assay.get('assay_status'), assay.get('evaluable'), assay.get('detected')
        if (status not in ASSAY_STATES or type(eligible) is not bool
                or eligible != (status in {'detected', 'not_detected'})
                or candidate.get('assay_eligible') is not eligible
                or candidate.get('assay_exclusion_reason') != (None if eligible else status)
                or (eligible and (type(detected) is not bool or detected != (status == 'detected')))
                or (not eligible and detected is not None)):
            raise ValueError('Assay eligibility/outcome does not retain the consumed source rules.')
        if (type(label['comparator_evaluable']) is not bool
                or label['comparator_evaluable'] != (eligible and comp.get('comparator') is not None)
                or candidate.get('historical_pharos_comparator_eligible') is not label['comparator_evaluable']):
            raise ValueError('Historical Pharos eligibility is not an assay exclusion.')
        for field, comp_field in (('pharos_status', 'pharos_status'), ('pharos_present', 'comparator'),
                                  ('resolved_endpoint_count', 'resolved_endpoint_count'),
                                  ('provider_bundles', 'provider_bundles'),
                                  ('previous_pharos_status', 'previous_pharos_status'),
                                  ('lookup_record_sha256', 'lookup_record_sha256')):
            if candidate.get(field) != comp.get(comp_field):
                raise ValueError('Scope descriptive reference differs from the consumed comparator.')
        exposure = candidate.get('exposure', {})
        if (not isinstance(exposure, dict)
                or any(type(exposure.get(f)) is not bool for f in (*EXPOSURE_FLAGS, 'huri_overlap', 'inmc_overlap', 'consumed_intact_exact_pair'))
                or any(exposure[f] is not comp.get(f) for f in (*EXPOSURE_FLAGS, 'huri_overlap', 'inmc_overlap'))
                or exposure['huri_overlap'] != any(exposure[f] for f in EXPOSURE_FLAGS[:2])
                or exposure['inmc_overlap'] != any(exposure[f] for f in EXPOSURE_FLAGS[2:])):
            raise ValueError('Pre-existing HuRI/INMC exposure flags differ.')
        joined.append({'candidate': candidate, 'assay': assay, 'prediction': prediction})
    return joined


def _metric(rows, arm, average_precision_score):
    positives = sum(row['assay']['detected'] is True for row in rows)
    native_count = sum(row['prediction']['views'][arm]['state'] == 'numeric' for row in rows)
    result = {'pairs': len(rows), 'detected': positives, 'not_detected': len(rows) - positives,
              'explicit_numeric': native_count, 'average_precision': None}
    if not rows:
        result['status'] = 'unscorable_empty_population'
    elif not native_count:
        result['status'] = 'unscorable_no_explicit_numeric_support'
    elif not positives:
        result['status'] = 'unscorable_no_recorded_detections'
    else:
        result['status'] = 'scored'
        result['average_precision'] = float(average_precision_score(
            [int(row['assay']['detected']) for row in rows],
            [row['prediction']['views'][arm]['ranking_score'] for row in rows]))
    return result


def _coverage(rows, arm):
    counts = Counter(row['prediction']['views'][arm]['state'] for row in rows)
    return {'pairs': len(rows), 'explicit_numeric': counts['numeric'],
            'explicit_numeric_fraction': counts['numeric'] / len(rows) if rows else None,
            'unranked': len(rows) - counts['numeric'], 'states': dict(sorted(counts.items()))}


def _comparison(rows, average_precision_score):
    metrics = {arm: _metric(rows, arm, average_precision_score) for arm in ARMS}
    left, right = (metrics[arm]['average_precision'] for arm in ARMS)
    return {'arms': metrics, 'physical_minus_functional_average_precision':
            None if left is None or right is None else right - left}


def score_rows(candidates, label_rows, predictions):
    """Strictly join the consumed population and return the declared AP summaries."""
    # Import the existing metric, not a locally reimplemented approximation.
    import sklearn
    from sklearn.metrics import average_precision_score
    if sklearn.__version__ != SKLEARN_VERSION:
        raise ValueError('Scoring requires the pinned scikit-learn ' + SKLEARN_VERSION + ' runtime.')
    joined = _validate_join(candidates, label_rows, predictions)
    eligible = [row for row in joined if row['assay']['evaluable']]
    common = [row for row in eligible if all(row['prediction']['views'][arm]['state'] == 'numeric' for arm in ARMS)]
    fingerprints = {arm: digest([{'products': row['prediction']['products'],
        'source_row': row['prediction']['source_row'],
        'ranking_score': row['prediction']['views'][arm]['ranking_score']} for row in eligible]) for arm in ARMS}
    all_fingerprints = {arm: digest([{'products': row['prediction']['products'],
        'source_row': row['prediction']['source_row'],
        'ranking_score': row['prediction']['views'][arm]['ranking_score']} for row in joined]) for arm in ARMS}
    strata = {}
    for huri in (False, True):
        for inmc in (False, True):
            selected = [row for row in joined if row['candidate']['exposure']['huri_overlap'] is huri
                        and row['candidate']['exposure']['inmc_overlap'] is inmc]
            selected_eligible = [row for row in selected if row['assay']['evaluable']]
            strata[f'huri={huri},inmc={inmc}'] = {'all_nominations': len(selected),
                'assay_eligible': len(selected_eligible),
                'coverage_all': {arm: _coverage(selected, arm) for arm in ARMS},
                'coverage_eligible': {arm: _coverage(selected_eligible, arm) for arm in ARMS},
                'full_panel': _comparison(selected_eligible, average_precision_score)}
    return {'format': 'biograph-steward.string-component-metrics.v1',
        'dataset_status': 'consumed_development', 'metric': 'sklearn.metrics.average_precision_score',
        'runtime': {'python': platform.python_version(), 'scikit_learn': sklearn.__version__},
        'primary_population': {'all_nominations': len(joined), 'assay_eligible': len(eligible),
            'detected': sum(row['assay']['detected'] is True for row in eligible),
            'not_detected': sum(row['assay']['detected'] is False for row in eligible),
            'assay_excluded': len(joined) - len(eligible),
            'exclusions': dict(sorted(Counter(row['assay']['assay_status'] for row in joined if not row['assay']['evaluable']).items()))},
        'coverage_all': {arm: _coverage(joined, arm) for arm in ARMS},
        'coverage_eligible': {arm: _coverage(eligible, arm) for arm in ARMS},
        'full_panel': _comparison(eligible, average_precision_score),
        'jointly_numeric': {'selection': 'Both native scores explicitly numeric; conditional secondary population.',
            'comparison': _comparison(common, average_precision_score)},
        'ranking_vectors': {'eligible_sha256': fingerprints,
            'identical_eligible_inputs': fingerprints['functional'] == fingerprints['physical'],
            'all_nominations_sha256': all_fingerprints,
            'identical_all_nominated_inputs': all_fingerprints['functional'] == all_fingerprints['physical']},
        'exposure_strata': strata,
        'historical_pharos_descriptive_anchor': {'role': 'Different source-release presence lookup; not a third matched arm.',
            'all_nominations_states': dict(sorted(Counter(row['candidate']['pharos_status'] for row in joined).items())),
            'eligible_states': dict(sorted(Counter(row['candidate']['pharos_status'] for row in eligible).items())),
            'eligible_with_known_presence': sum(row['candidate']['historical_pharos_comparator_eligible'] for row in eligible)},
        'unranked_policy': {'ordinal_value': UNRANKED, 'all_native_numeric_scores_above_unranked': True,
            'meaning': 'Retrieval ordering only; neither confidence nor a biological negative.'},
        'study_independence_established': False, 'steward_improvement_tested': False,
        'scientific_accuracy_measured': False, 'confidence_intervals_computed': False,
        'thresholds_tuned': False, 'graph_modified': False}


def _seal(value):
    return {**value, 'content_sha256': digest(value)}


def _write_html(output, metrics):
    def percentage(value):
        return 'Unscorable' if value is None else f'{value:.4f}'
    def metric_table(comparison):
        rows = []
        for arm in ARMS:
            item = comparison['arms'][arm]
            rows.append('<tr>' + ''.join('<td>' + escape(str(value)) + '</td>' for value in
                (arm, item['pairs'], item['explicit_numeric'], item['detected'],
                 percentage(item['average_precision']), item['status'])) + '</tr>')
        return ('<table><tr><th>View</th><th>Eligible pairs</th><th>Native numeric</th>'
                '<th>Detected</th><th>Average precision</th><th>Status</th></tr>'
                + ''.join(rows) + '</table>')
    population = metrics['primary_population']
    body = ('<h1>STRING functional scores and physical overlay</h1>'
        '<p>Fixed retrospective component comparison against recorded human Y2H-v1 detection. '
        'Nondetection is assay-conditional; this is neither independent scientific truth nor a Steward improvement test.</p>'
        f'<p>All {population["all_nominations"]:,} nominations retained; '
        f'{population["assay_eligible"]:,} assay-eligible pairs '
        f'({population["detected"]:,} detected, {population["not_detected"]:,} not detected). '
        f'{population["assay_excluded"]:,} pre-existing assay exclusions remain accounted for.</p>'
        '<h2>Primary: full eligible population</h2>' + metric_table(metrics['full_panel'])
        + '<p>Physical minus functional average precision: '
        + escape(percentage(metrics['full_panel']['physical_minus_functional_average_precision']))
        + '. Unranked pairs tie below native numeric zero. This is an operational retrieval policy, not an inferred negative.</p>'
        + '<h2>Secondary: jointly numeric pairs</h2>'
        + metric_table(metrics['jointly_numeric']['comparison'])
        + '<p>The conditional population does not replace the primary denominator.</p>'
        + '<h2>Prior exposure strata</h2>')
    for name, stratum in metrics['exposure_strata'].items():
        body += '<h3>' + escape(name) + '</h3>' + metric_table(stratum['full_panel'])
    identical = metrics['ranking_vectors']['identical_eligible_inputs']
    body += ('<p>Identical eligible ranking inputs: ' + str(identical).lower()
        + '. No-op inputs do not establish a useful intervention.</p>'
        '<p>No confidence interval, outcome-tuned threshold or source sweep was used. '
        'Unflagged exposure is not certified independence from STRING. '
        'The historical Pharos presence lookup is a descriptive anchor, not a third matched arm.</p>'
        '<p><a href="metrics.json">Metrics, state coverage and fingerprints</a> · '
        '<a href="report.json">Verification receipt</a></p>')
    (output / 'report.html').write_text('<!doctype html><html lang="en"><meta charset="utf-8">'
        '<title>STRING component comparison</title><style>body{font:16px system-ui;max-width:1100px;'
        'margin:40px auto;padding:0 20px;line-height:1.5}table{width:100%;border-collapse:collapse}'
        'th,td{padding:9px;border-bottom:1px solid #ccc;text-align:left}th{background:#edf2f6}'
        '</style>' + body + '</html>', encoding='utf-8')


def score_capture(capture, output):
    """Verify a sealed captured prediction packet before joining consumed labels."""
    import run_string_component as runner
    captured = runner.verify_capture(Path(capture))
    if platform.python_version() != captured['protocol']['rules']['scoring_python']:
        raise ValueError('Scoring Python runtime differs from the frozen protocol.')
    metrics = score_rows(captured['candidates'], captured['label_rows'], captured['predictions'])
    out = new_output(output, capture)
    write_json(out / 'metrics.json', metrics)
    _write_html(out, metrics)
    scorable = all(metrics['full_panel']['arms'][arm]['status'] == 'scored' for arm in ARMS)
    report = _seal({'format': 'biograph-steward.string-component-result.v1',
        'created_at': utcnow(), 'status': 'completed' if scorable else 'unscorable_comparison',
        'capture_report_sha256': captured['report']['content_sha256'],
        'protocol_sha256': captured['protocol']['content_sha256'],
        'dataset_status': 'consumed_development', 'new_outcome_source_accesses': 0,
        'study_independence_established': False, 'steward_improvement_tested': False,
        'scientific_accuracy_measured': False, 'graph_modified': False,
        'implementation_sha256': {'scripts/score_string_component.py': sha(Path(__file__))},
        'files': {name: sha(out / name) for name in ('metrics.json', 'report.html')}})
    write_json(out / 'report.json', report)
    # Recheck after writing; no live network or fresh outcome decoding.
    verify_result(capture, out)
    return report


def verify_result(capture, output):
    import run_string_component as runner
    captured = runner.verify_capture(Path(capture))
    if platform.python_version() != captured['protocol']['rules']['scoring_python']:
        raise ValueError('Scoring Python runtime differs from the frozen protocol.')
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
    if (report.get('format') != 'biograph-steward.string-component-result.v1'
            or report.get('files') != files or set(files) != {'metrics.json', 'report.html'}
            or report.get('capture_report_sha256') != captured['report']['content_sha256']
            or report.get('protocol_sha256') != captured['protocol']['content_sha256']
            or report.get('implementation_sha256') != {'scripts/score_string_component.py': sha(Path(__file__))}
            or report.get('dataset_status') != 'consumed_development'
            or report.get('new_outcome_source_accesses') != 0
            or any(report.get(flag) is not False for flag in ('study_independence_established',
                'steward_improvement_tested', 'scientific_accuracy_measured', 'graph_modified'))):
        raise ValueError('Result files, capture, protocol or scoring implementation differ.')
    actual = _decode((folder / 'metrics.json').read_bytes())
    expected = score_rows(captured['candidates'], captured['label_rows'], captured['predictions'])
    if actual != expected:
        raise ValueError('Metrics do not reproduce from the sealed captured predictions.')
    scorable = all(expected['full_panel']['arms'][arm]['status'] == 'scored' for arm in ARMS)
    if report.get('status') != ('completed' if scorable else 'unscorable_comparison'):
        raise ValueError('Unscorable support cannot be reported as a completed comparison.')
    return report


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--capture', type=Path, required=True)
    parser.add_argument('--out', type=Path, required=True)
    parser.add_argument('--verify', action='store_true', help='Replay an existing result without changing it.')
    args = parser.parse_args(argv)
    try:
        report = verify_result(args.capture, args.out) if args.verify else score_capture(args.capture, args.out)
    except (ValueError, OSError, KeyError, TypeError, ImportError) as exc:
        parser.exit(1, f'ERROR: {exc}\n')
    print(f"{report['status']}: {args.out.absolute()}")
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
