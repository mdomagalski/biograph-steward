"""Publish aggregate source-claim assessment results without individual records.

This helper performs no inference, label join or scientific parameter selection.
Only a fixed allowlist of counts, metrics, method metadata and seals is emitted.
"""
from collections import Counter
from datetime import datetime, timezone
from html import escape
import argparse
import hashlib
import json
import math
from pathlib import Path
import re

from biograph_steward.client import digest


FORMAT = 'biograph-steward.mechanistic-review-public-aggregate.v1'
METHODS = ('retain_all', 'native_counts', 'native_simple', 'nemotron', 'consensus')
NAMES = {'retain_all': 'Retain every claim', 'native_counts': 'INDRA source-count model',
         'native_simple': 'INDRA fixed source priors', 'nemotron': 'Nemotron source review',
         'consensus': 'Counts model + Nemotron agreement'}
COUNT_KEYS = ('claims', 'gold_supported', 'gold_unsupported', 'removed_supported',
              'removed_unsupported', 'abstained', 'removed', 'remaining',
              'remaining_supported', 'remaining_unsupported',
              'effective_retention_policy_correct', 'effective_retention_policy_incorrect')
METRIC_KEYS = ('pruning_precision', 'incorrect_claim_removal_recall',
               'gold_supported_retention_fraction', 'retained_graph_supported_precision',
               'effective_retention_policy_reference_accuracy',
               'effective_retention_policy_balanced_accuracy', 'coverage')
PAPER = 'https://doi.org/10.15252/msb.202211325'
DATA = 'https://doi.org/10.5281/zenodo.7559353'
BOOTSTRAP = 'https://doi.org/10.1111/j.1467-9868.2007.00593.x'


def need(condition, message):
    if not condition:
        raise ValueError('Mechanistic publication: ' + message)


def file_sha(path):
    result = hashlib.sha256()
    with Path(path).open('rb') as stream:
        while chunk := stream.read(1024 * 1024):
            result.update(chunk)
    return result.hexdigest()


def verify_seal(value, name):
    need(isinstance(value, dict), name + ' must be an object.')
    seal = value.get('content_sha256')
    need(isinstance(seal, str) and re.fullmatch('[0-9a-f]{64}', seal)
         and seal == digest({k: v for k, v in value.items() if k != 'content_sha256'}),
         name + ' content seal differs.')


def _fraction(value):
    return value is None or (type(value) in (int, float) and math.isfinite(value) and 0 <= value <= 1)


def _close(left, right):
    return left is right if left is None or right is None else abs(left - right) <= 1e-12


def _ratio(a, b):
    return a / b if b else None


def _metrics(row, total, supported, unsupported):
    need(isinstance(row, dict), 'method metrics missing.')
    need(all(type(row.get(k)) is int and row[k] >= 0 for k in COUNT_KEYS),
         'method count missing, negative or not an integer.')
    need(row['claims'] == total and row['gold_supported'] == supported
         and row['gold_unsupported'] == unsupported, 'method denominator differs.')
    need(row['removed_supported'] <= supported and row['removed_unsupported'] <= unsupported
         and row['removed'] == row['removed_supported'] + row['removed_unsupported']
         and row['remaining'] == total - row['removed']
         and row['remaining_supported'] == supported - row['removed_supported']
         and row['remaining_unsupported'] == unsupported - row['removed_unsupported']
         and row['abstained'] <= row['remaining'], 'retained/removed counts disagree.')
    need(row['abstentions_retained'] is True, 'abstentions must remain retained.')
    expected = {
        'pruning_precision': _ratio(row['removed_unsupported'], row['removed']),
        'incorrect_claim_removal_recall': _ratio(row['removed_unsupported'], unsupported),
        'gold_supported_retention_fraction': _ratio(row['remaining_supported'], supported),
        'retained_graph_supported_precision': _ratio(row['remaining_supported'], row['remaining']),
        'coverage': _ratio(total - row['abstained'], total),
        'effective_retention_policy_reference_accuracy': _ratio(row['remaining_supported'] + row['removed_unsupported'], total),
    }
    a, b = expected['gold_supported_retention_fraction'], expected['incorrect_claim_removal_recall']
    expected['effective_retention_policy_balanced_accuracy'] = (a + b) / 2 if a is not None and b is not None else None
    need(row['effective_retention_policy_correct'] == row['remaining_supported'] + row['removed_unsupported']
         and row['effective_retention_policy_incorrect'] == row['remaining_unsupported'] + row['removed_supported'],
         'effective retention-policy decisions disagree.')
    need(all(_fraction(row.get(k)) and _close(row.get(k), value) for k, value in expected.items()),
         'method metric differs from complete-frame counts.')
    return {**{key: row[key] for key in COUNT_KEYS + METRIC_KEYS},
            'abstentions_retained': True}


def _uncertainty(bootstrap, methods, groups):
    need(isinstance(bootstrap, dict) and bootstrap.get('draws') == 10000
         and bootstrap.get('seed') == 20261117 and bootstrap.get('groups') == groups
         and bootstrap.get('same_group_multiplicities_across_all_methods') is True,
         'frozen paired-group bootstrap settings differ.')
    need(bootstrap.get('status') in ('completed', 'unavailable_fewer_than_two_groups'),
         'bootstrap status invalid.')
    keys = {(a, b) for a in METHODS for b in ('retain_all', 'native_counts') if a != b}
    rows, seen = [], set()
    for row in bootstrap.get('comparisons', []):
        key = row.get('candidate'), row.get('comparator')
        need(key in keys and key not in seen, 'bootstrap comparison missing/duplicated/unknown.')
        seen.add(key)
        a = methods[key[0]]['retained_graph_supported_precision']
        b = methods[key[1]]['retained_graph_supported_precision']
        expected = a - b if a is not None and b is not None else None
        need(_close(row.get('observed_difference'), expected), 'bootstrap point estimate differs from reported methods.')
        defined, undefined = row.get('defined_paired_draws'), row.get('undefined_paired_draws')
        need(type(defined) is int and type(undefined) is int and defined >= 0 and undefined >= 0
             and defined + undefined == 10000, 'bootstrap draw accounting differs.')
        interval = row.get('percentile_95_interval')
        need((interval is None and defined == 0) or
             (isinstance(interval, list) and len(interval) == 2 and defined > 0
              and all(type(v) in (int, float) and math.isfinite(v) and -1 <= v <= 1 for v in interval)
              and interval[0] <= interval[1]), 'bootstrap interval invalid.')
        rows.append({key: row[key] for key in (
            'candidate', 'comparator', 'observed_difference', 'percentile_95_interval',
            'defined_paired_draws', 'undefined_paired_draws', 'interval_scope')})
    need(seen == keys if bootstrap['status'] == 'completed' else not seen,
         'not all prespecified paired comparisons are reported.')
    return {'status': bootstrap['status'], 'draws': 10000, 'seed': 20261117,
            'groups': groups, 'comparisons': rows,
            'method': 'Paired whole connected-source-group percentile bootstrap.',
            'scope': 'Pointwise conditional reference-corpus intervals, not simultaneous intervals, biological replication or population-wide accuracy.'}


def _counter(rows, field):
    counts = Counter()
    for row in rows:
        value = row.get(field)
        if isinstance(value, str) and len(value) <= 200:
            counts[value] += 1
    return dict(sorted(counts.items()))


def make_aggregate(report, native, model, protocol, *, protocol_sha256,
                   report_sha256, native_sha256, model_sha256):
    for name, value in (('assessment', report), ('native envelope', native), ('model envelope', model)):
        verify_seal(value, name)
        need(value.get('protocol_sha256') == protocol_sha256, name + ' protocol differs.')
    need(report.get('format') == 'biograph-steward.mechanistic-claim-assessment.v1'
         and report.get('status') == 'completed', 'completed frozen assessment required.')
    pins = report.get('input_files_sha256', {})
    need(pins.get('protocol') == protocol_sha256 and pins.get('native_predictions') == native_sha256
         and pins.get('model_predictions') == model_sha256, 'assessment input-file pins differ.')
    expected_inputs = protocol.get('input_files_sha256', {})
    need(all(pins.get(k) == expected_inputs.get(k) and isinstance(pins.get(k), str)
             for k in ('source_cases', 'labels')), 'frozen source/reference pins differ.')
    need(report.get('scorer_sha256') == protocol.get('scoring', {}).get('code', {}).get('sha256'),
         'frozen scorer implementation differs.')
    need(native.get('content_sha256') == report.get('native_prediction_seal')
         and model.get('content_sha256') == report.get('model_prediction_seal')
         and native.get('source_cases_sha256') == pins['source_cases']
         and model.get('source_cases_sha256') == pins['source_cases'], 'prediction/source content binding differs.')
    policy = report.get('policy', {})
    need(policy.get('whole_graph_biological_accuracy_claim') is False
         and policy.get('current_app_or_Pharos_graph_changed') is False
         and policy.get('abstentions_retained') is True,
         'assessment scope or retained-abstention policy differs.')
    frame = report.get('frame', {})
    total, supported, unsupported, groups = (frame.get(k) for k in (
        'reserve_claims', 'gold_supported', 'gold_unsupported', 'connected_source_groups'))
    need(all(type(v) is int and v >= 0 for v in (total, supported, unsupported, groups))
         and total > 0 and total == supported + unsupported and 0 < groups <= total,
         'complete reserve denominator invalid.')
    need(set(report.get('methods', {})) == set(METHODS), 'all five methods must be published.')
    methods = {name: _metrics(report['methods'][name], total, supported, unsupported) for name in METHODS}
    bootstrap = _uncertainty(report.get('bootstrap'), methods, groups)
    native_result = native.get('native_result')
    verify_seal(native_result, 'native result')
    native_rows, model_rows = native_result.get('reserve'), model.get('rows')
    need(isinstance(native_rows, list) and isinstance(model_rows, list)
         and len(native_rows) == len(model_rows) == total, 'prediction frame count differs.')
    evidence_counts = [row.get('original_evidence_count') for row in native_rows]
    need(all(type(v) is int and v > 0 for v in evidence_counts), 'original-evidence totals missing.')
    traces = [row['trace'] for row in model_rows if isinstance(row.get('trace'), dict)]
    calls = [trace.get('model_calls', 0) for trace in traces]
    need(all(type(v) is int and v >= 0 for v in calls), 'invalid model-call accounting.')
    primary = methods['nemotron']
    headline = (f"Source review retained {primary['remaining_supported']}/{supported} curator-supported claims "
                f"and excluded {primary['removed_unsupported']}/{unsupported} unsupported claims.")
    comparison = next((r for r in bootstrap['comparisons']
                       if r['candidate'] == 'nemotron' and r['comparator'] == 'retain_all'), None)
    interval = comparison['percentile_95_interval'] if comparison else None
    observed = comparison['observed_difference'] if comparison else None
    if observed is None:
        conclusion = 'Retained-reference precision is undefined for the primary comparison; no precision gain is established.'
    elif observed <= 0:
        conclusion = 'The primary review did not increase retained-reference precision over retaining every claim.'
    elif interval is not None and interval[0] > 0 and comparison['undefined_paired_draws'] == 0:
        conclusion = 'The paired interval supports a retained-reference precision gain over retaining every claim in this bounded assessment.'
    else:
        conclusion = 'Retained-reference precision increased in the observed set; the paired uncertainty does not establish an unconditional precision gain.'
    safe_versions = {key: value for key, value in native_result.get('versions', {}).items()
                     if key in ('indra', 'scikit-learn', 'numpy', 'pandas', 'scipy')
                     and isinstance(value, str) and len(value) <= 80}
    result = {'format': FORMAT, 'created_at': datetime.now(timezone.utc).isoformat(),
        'title': 'Expert-curated source-claim assessment', 'headline': headline,
        'primary_interpretation': conclusion,
        'frame': {'claims': total, 'curator_supported': supported, 'curator_unsupported': unsupported,
                  'connected_source_groups': groups, 'original_evidence_records': sum(evidence_counts)},
        'methods': methods, 'bootstrap': bootstrap,
        'execution': {'model_requests_recorded': sum(calls),
                      'model_status_counts': _counter(model_rows, 'status'),
                      'provider_counts': _counter(traces, 'provider_requested'),
                      'requested_model_counts': _counter(traces, 'model_requested'),
                      'returned_model_counts': _counter(traces, 'model_returned'),
                      'native_package_versions': safe_versions,
                      'model_or_source_calls_by_publisher': 0},
        'definitions': {
            'supported': 'At least one original source was accepted under the published coarse curation policy.',
            'unsupported': 'Every original source was admitted and curator-reviewed, and none was accepted; this does not establish a universally false biological relationship.',
            'pruning_precision': 'Curator-unsupported excluded / all excluded claims.',
            'retained_precision': 'Curator-supported remaining / all remaining claims.',
            'supported_retention': 'Curator-supported remaining / all curator-supported claims.',
            'coverage': 'Non-abstaining proposals / all assessed claims; abstentions remain in the retained graph.',
            'policy_accuracy': 'Correct effective retain/prune decisions / all assessed claims; abstentions are retained, not treated as resolved model predictions.',
            'consensus': 'Exclude only when both the native source-count model and Nemotron propose exclusion. Other claims remain retained.',
        },
        'limitations': [
            'This evaluates extraction/source-claim faithfulness, not independent experimental truth, clinical validity or whole-Pharos biological accuracy.',
            'The corpus and earlier grounding endpoint were previously used in this project. This is a new retrospective endpoint, not a newly unseen independent gold set.',
            'The assigned human-gene source frame does not independently confirm species, isoform, construct or biological context.',
            'The published coarse positive policy includes hypothesis and activity-versus-amount tags. A curator-negative extraction does not make a relationship false in every context.',
            'Some curations used publication context beyond the supplied evidence; insufficient context must remain an abstention.',
            'Native source priors may share curation lineage; model pretraining independence is not established. Native counts were fitted on development data only.',
            'This reference is not a probability sample of the application graph. Results do not establish cross-cohort generalization.',
            'All five prespecified methods and adverse exclusions of supported claims are reported. Intervals are pointwise and conditional on the frozen reference.',
            'Retained native graphs are separate assessment views. The original Pharos graph, application workspace and review decisions remain unchanged.',
        ],
        'attribution': {'reference': 'Bachman, Gyori and Sorger (2023), Automated assembly of molecular mechanisms at scale from text mining and curated databases.',
                        'paper_url': PAPER, 'dataset_url': DATA,
                        'reference_data_license': 'CC BY-NC-SA 4.0',
                        'software_adapter_license': 'MIT', 'native_indra_license': 'BSD-2-Clause',
                        'license_boundary': 'The software license does not relicense INDRA data or source articles. Individual records and source passages are not included in this aggregate publication.',
                        'cluster_bootstrap_method_url': BOOTSTRAP},
        'provenance': {'protocol_sha256': protocol_sha256, 'assessment_file_sha256': report_sha256,
                       'assessment_content_sha256': report['content_sha256'],
                       'native_predictions_file_sha256': native_sha256,
                       'model_predictions_file_sha256': model_sha256,
                       'scorer_sha256': report['scorer_sha256']},
        'privacy': {'aggregate_only': True, 'individual_cases_or_identifiers_included': False,
                    'source_passages_included': False, 'individual_predictions_included': False,
                    'private_paths_endpoints_or_credentials_included': False}}
    result['content_sha256'] = digest(result)
    return result


def _pct(value):
    return '—' if value is None else f'{100 * value:.1f}%'


def _pp(value):
    return '—' if value is None else f'{100 * value:+.1f} pp'


def _table(headers, rows):
    head = ''.join('<th scope="col">' + escape(str(x)) + '</th>' for x in headers)
    body = ''.join('<tr>' + ''.join('<td>' + escape(str(x)) + '</td>' for x in row) + '</tr>' for row in rows)
    return '<div class="scroll" tabindex="0"><table><thead><tr>' + head + '</tr></thead><tbody>' + body + '</tbody></table></div>'


def render_html(aggregate):
    counts, measures = [], []
    for name in METHODS:
        row = aggregate['methods'][name]
        counts.append((NAMES[name], row['remaining'], row['removed_unsupported'], row['removed_supported'],
                       row['abstained'], _pct(row['pruning_precision'])))
        measures.append((NAMES[name], _pct(row['retained_graph_supported_precision']),
                         _pct(row['gold_supported_retention_fraction']), _pct(row['incorrect_claim_removal_recall']),
                         _pct(row['effective_retention_policy_reference_accuracy']),
                         _pct(row['effective_retention_policy_balanced_accuracy']), _pct(row['coverage'])))
    comparisons = []
    for row in aggregate['bootstrap']['comparisons']:
        interval = row['percentile_95_interval']
        comparisons.append((NAMES[row['candidate']] + ' vs ' + NAMES[row['comparator']],
            _pp(row['observed_difference']), '—' if interval is None else _pp(interval[0]) + ' to ' + _pp(interval[1]),
            row['defined_paired_draws'], row['undefined_paired_draws']))
    frame = aggregate['frame']
    summary = (f"{frame['claims']} complete-source claims · {frame['curator_supported']} curator-supported / "
               f"{frame['curator_unsupported']} unsupported · {frame['original_evidence_records']} original evidence records · "
               f"{frame['connected_source_groups']} connected source groups")
    limitations = ''.join('<li>' + escape(text) + '</li>' for text in aggregate['limitations'])
    definitions = ''.join('<dt>' + escape(key.replace('_', ' ').capitalize()) + '</dt><dd>' + escape(value) + '</dd>'
                          for key, value in aggregate['definitions'].items())
    return ('<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">'
        '<title>' + escape(aggregate['title']) + '</title><style>'
        'body{font:16px/1.5 system-ui,sans-serif;color:#172b3a;background:#fff;max-width:1120px;margin:auto;padding:24px}'
        'h1{line-height:1.15;font-size:2rem}h2{margin-top:32px}.lead{font-size:1.12rem}.note{background:#eef5f8;border-left:4px solid #21627b;padding:16px}'
        '.scroll{overflow-x:auto;max-width:100%;margin:14px 0}table{border-collapse:collapse;width:100%;font-size:.88rem}'
        'th,td{border-bottom:1px solid #ccd8df;padding:10px;text-align:right}th:first-child,td:first-child{text-align:left;min-width:170px}'
        'th{background:#edf3f6;color:#152f40}dt{font-weight:650;margin-top:8px}dd{margin-left:0}a{color:#075c85}small{color:#405967}'
        '@media(max-width:600px){body{padding:16px}h1{font-size:1.6rem}}</style></head><body><main>'
        '<p><small>BioGraph Steward · aggregate reference assessment</small></p><h1>' + escape(aggregate['title']) + '</h1>'
        '<p class="lead">' + escape(aggregate['headline']) + '</p><p>' + escape(summary) + '</p>'
        '<div class="note"><strong>' + escape(aggregate['primary_interpretation']) + '</strong><br>'
        'This measures whether supplied evidence supports extracted mechanistic claims. It does not measure whole-Pharos biological accuracy. The application graph is unchanged.</div>'
        '<h2>What was retained or excluded</h2><p>Excluding a curator-supported claim is an error. Abstentions stay retained, including all unavailable native-prior decisions.</p>'
        + _table(('Method', 'Claims retained', 'Unsupported excluded', 'Supported excluded', 'Abstained, retained', 'Pruning precision'), counts)
        + '<h2>All-claim measures</h2><p>Every method uses the same complete denominator. Effective policy accuracy counts abstentions as retained; coverage reports which proposals were resolved.</p>'
        + _table(('Method', 'Retained precision', 'Supported retention', 'Unsupported removal recall', 'Policy accuracy', 'Balanced accuracy', 'Coverage'), measures)
        + '<p>— means the ratio is undefined, not zero.</p><h2>Paired uncertainty in retained precision</h2>'
        '<p>10,000 paired connected-source-group bootstrap draws, seed 20261117. Differences are percentage points. These are pointwise, conditional intervals; all prespecified comparisons are shown.</p>'
        + _table(('Comparison', 'Observed gain', '95% percentile interval', 'Defined draws', 'Undefined draws'), comparisons)
        + '<p>If either retained graph is empty in a draw, its precision is undefined. Such draws are counted explicitly; any remaining interval is conditional on nonempty retained graphs.</p>'
        '<h2>Terms and interpretation</h2><dl>' + definitions + '</dl><h2>Limitations</h2><ul>' + limitations + '</ul>'
        '<h2>Reference and reproducibility</h2><p><a href="' + PAPER + '">Bachman, Gyori and Sorger, 2023</a> · '
        '<a href="' + DATA + '">Official reference data</a> · <a href="' + BOOTSTRAP + '">Cluster-bootstrap methods</a></p>'
        '<p>INDRA reference data: CC BY-NC-SA 4.0. Native INDRA: BSD-2-Clause. This publishing adapter: MIT. Source article rights remain applicable.</p>'
        '<p><a href="aggregate.json">Download aggregate results and provenance</a> · <a href="README.md">Read scope and licensing notes</a></p>'
        '</main></body></html>')


def run(report, native_predictions, model_predictions, protocol, protocol_sha256, output):
    paths = {name: Path(path) for name, path in (
        ('report', report), ('native_predictions', native_predictions),
        ('model_predictions', model_predictions), ('protocol', protocol))}
    need(all(p.is_file() and not p.is_symlink() for p in paths.values()), 'ordinary sealed input files required.')
    pins = {name: file_sha(path) for name, path in paths.items()}
    need(pins['protocol'] == protocol_sha256, 'raw frozen protocol pin differs.')
    values = {name: json.loads(path.read_text()) for name, path in paths.items()}
    aggregate = make_aggregate(values['report'], values['native_predictions'], values['model_predictions'],
        values['protocol'], protocol_sha256=protocol_sha256, report_sha256=pins['report'],
        native_sha256=pins['native_predictions'], model_sha256=pins['model_predictions'])
    output = Path(output)
    need(not output.exists(), 'publication output must be new.')
    output.mkdir(parents=True)
    (output / 'aggregate.json').write_text(json.dumps(aggregate, indent=2, sort_keys=True, allow_nan=False) + '\n')
    (output / 'report.html').write_text(render_html(aggregate))
    (output / 'README.md').write_text(
        '# Expert-curated source-claim assessment\n\n' + aggregate['headline'] + '\n\n'
        + aggregate['primary_interpretation'] + '\n\n'
        'This publication contains aggregate statistics only. All five prespecified methods, adverse supported-claim exclusions, abstentions and paired pointwise intervals remain visible. Individual cases, identifiers, passages, predictions, private paths and endpoints are omitted.\n\n'
        'Supported means at least one original source was accepted under the published coarse curation policy; unsupported means every original source was admitted and reviewed and none accepted. Hypothesis and activity-versus-amount tags count as positive under that historical policy. These are extraction-faithfulness labels, not universally true or false biological relationships.\n\n'
        'The corpus and prior grounding endpoint were already used in this project. This new retrospective endpoint is not an unseen independent holdout. Development-only native model fitting and fixed reserve prediction do not establish independent pretraining or new biological replication.\n\n'
        'Reference-native retained graphs and full ledgers remain private assessment artifacts. No original Pharos graph, app workspace, source record or review decision is modified.\n\n'
        'Reference: [Bachman, Gyori and Sorger (2023)](' + PAPER + '). [Official dataset](' + DATA + '), CC BY-NC-SA 4.0. Native INDRA is BSD-2-Clause; this publishing adapter is MIT. The project software license does not relicense source data or article passages.\n\n'
        'Uncertainty uses paired whole connected-source-group resampling: 10,000 draws, seed 20261117. Intervals are pointwise, not multiplicity-adjusted simultaneous intervals. Empty retained graphs yield undefined draws, explicitly reported. [Clustered-bootstrap methodology](' + BOOTSTRAP + ').\n\n'
        'The aggregate JSON records frozen protocol, assessment, prediction-file and scoring-code hashes without distributing individual reference data.\n')
    need(all(file_sha(path) == pins[name] for name, path in paths.items()), 'a sealed input changed during publication.')
    return {'format': FORMAT, 'status': 'published_aggregate_only',
            'aggregate_content_sha256': aggregate['content_sha256'],
            'input_files_sha256': pins, 'publisher_sha256': file_sha(__file__),
            'all_inputs_unchanged': True,
            'files': {path.name: {'sha256': file_sha(path), 'bytes': path.stat().st_size}
                      for path in sorted(output.iterdir()) if path.is_file()}}


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ('report', 'native-predictions', 'model-predictions', 'protocol', 'protocol-sha256', 'output'):
        parser.add_argument('--' + name, required=True)
    args = parser.parse_args()
    result = run(args.report, args.native_predictions, args.model_predictions,
                 args.protocol, args.protocol_sha256, args.output)
    print(json.dumps(result, sort_keys=True))
