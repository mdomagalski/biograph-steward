"""Publish complete saved ProtNote aggregates without opening private inputs."""
import argparse
from html import escape
import math
from pathlib import Path
import json

from biograph_steward.client import digest, utcnow, write_json
from biograph_steward.file_utils import new_output, sha
from biograph_steward.scientific_assessment import _task_tree
from .archive import need, sealed
from .publish import read, public_paths_absent, table, METRICS
from .publish_overlap import reject_raw, RUNTIME
from .nonpk_publish import SETTINGS, ASPECTS

FORMAT = 'biograph-steward.protnote-native-evaluation.v1'
METHOD = 'protnote_seed42'
COMPARATORS = ('deepgose', 'strict_alias_localplus', 'official_nonexperimental')
READOUTS = ('ordinary', 'IA_weighted')


def finite(value, low=0., high=None):
    return type(value) in (int, float) and math.isfinite(value) and value >= low \
        and (high is None or value <= high)


def interval(value, low, high):
    return isinstance(value, list) and len(value) == 2 and all(finite(x, low, high) for x in value) \
        and value[0] <= value[1]


def admission_gate(value, policy, protocol):
    need(set(value) == {'all547_original_identities_accounted_for', 'scorable_targets',
        'explicit_unscorable_targets', 'fixed_ontology_classes', 'finite_unit_interval_cartesian_rows',
        'pre_forward_input_qualification_sha256', 'pre_target_label_cache_manifest_sha256',
        'private_inventory_sha256', 'producer_config_file_sha256', 'producer_complete_DONE_file_sha256',
        'all_raw_scores_finite_in_unit_interval', 'exact_full_cartesian_forecast_verified',
        'no_reference_or_TOI_values_used_for_admission'}, 'unexpected raw-forecast admission aggregate.')
    for key in ('scorable_targets', 'explicit_unscorable_targets', 'fixed_ontology_classes',
                'finite_unit_interval_cartesian_rows'):
        need(type(value[key]) is int and value[key] >= 0, 'integer forecast coverage required.')
    need(value['scorable_targets'] + value['explicit_unscorable_targets'] == 547
         and value['fixed_ontology_classes'] > 0
         and value['finite_unit_interval_cartesian_rows'] == value['scorable_targets'] * value['fixed_ontology_classes']
         and value['pre_forward_input_qualification_sha256'] == protocol['producer_input_qualification']['sha256']
         and value['pre_target_label_cache_manifest_sha256'] == protocol['producer_label_cache']['sha256']
         and value['producer_config_file_sha256'] == policy['producer_config']['sha256']
         and value['producer_complete_DONE_file_sha256'] == policy['producer_done']['sha256']
         and all(value[key] is True for key in ('all547_original_identities_accounted_for',
            'all_raw_scores_finite_in_unit_interval', 'exact_full_cartesian_forecast_verified',
            'no_reference_or_TOI_values_used_for_admission')),
         'full547 partition, finite Cartesian coverage or source qualification differs.')


def point_gate(row, denominator):
    need(row['method'] == METHOD and row['known_exclusion'] is None
         and all(row.get(key) == value for key, value in denominator.items()),
         'original None-branch population/reference extent differs.')
    need(row['status'] in ('scored', 'no_native_curve', 'nonfinite_native_curve'),
         'preserve an explicit native outcome status.')
    if row['status'] != 'scored':
        need(isinstance(row['reason'], str) and row['reason'], 'unscored native reason required.')
        return
    need(all(finite(row[key], 0., 1.) and finite(row[key + '_tau'], 0., 1.) for key in METRICS)
         and all(finite(row[key]) and finite(row[key + '_tau'], 0., 1.)
                 for key in ('unweighted_Smin', 'IA_weighted_Smin'))
         and isinstance(row['fixed_0_5'], dict), 'finite saved native point/fixed operating statuses required.')


def prepare(source, expected, freeze, freeze_expected, previous, previous_expected,
            protocol, protocol_expected, output):
    source, freeze, previous, protocol = map(Path, (source, freeze, previous, protocol))
    for path, expected_sha in ((source, expected), (freeze, freeze_expected),
                               (previous, previous_expected), (protocol, protocol_expected)):
        need(sha(path) == expected_sha, 'saved aggregate/freeze/previous/protocol FILE differs.')
    result, policy, old, plan = map(read, (source, freeze, previous, protocol))
    need(result['format'] == FORMAT + '.results' and policy['format'] == FORMAT + '.freeze'
         and plan['format'] == 'biograph-steward.protnote-development.v1.protocol'
         and plan['status'] == 'FROZEN_before_any_target_forecast'
         and result['evaluation_freeze_sha256'] == freeze_expected
         and result['protocol_sha256'] == policy['protocol']['sha256'] == protocol_expected
         and result['previous_report_sha256'] == policy['previous_report']['sha256'] == previous_expected
         and result['prediction_manifest_sha256'] == policy['predictions']['sha256'],
         'complete source/freeze/scientific-protocol binding differs.')
    need(result['runtime'] == RUNTIME and plan['development_only'] is True
         and plan['previous_reference_and_metric_exposure'] is True
         and plan['model']['seed'] == 42 and plan['model']['trained_or_fit_here'] is False
         and plan['model']['ensembles_or_seed_selection'] is False
         and plan['target_scope']['target_count'] == 547
         and plan['target_scope']['population_counts'] == {'no_knowledge': 133, 'limited': 414}
         and plan['prediction_axis']['headers_or_future_labels_or_TOI_used'] is False
         and plan['evaluation']['settings'] == list(SETTINGS)
         and plan['evaluation']['all_aspects'] == list(ASPECTS)
         and plan['evaluation']['focus_namespace'] == 'molecular_function'
         and plan['evaluation']['paired_comparisons'] == [[METHOD, method] for method in COMPARATORS]
         and plan['evaluation']['paired_contrasts'] == 12
         and plan['evaluation']['original_ground_truth_masks_and_denominators_retained'] is True,
         'one-seed/profile, fixed prediction axis or original task contract differs.')
    need(all(plan['adoption'][key] is False for key in
         ('new_accepted_graph_facts', 'automatic_adoption', 'AWS_or_app_default_changes')),
         'no-adoption/accepted-graph boundary differs.')
    for key in ('all_original_populations_and_reference_masks_retained', 'development_only'):
        need(result[key] is True, 'original native scoring population must remain intact.')
    for key in ('new_reference_release', 'app_default_or_graph_changed', 'automatic_adoption'):
        need(result[key] is False, 'new-source/app/default/automatic-adoption boundary differs.')
    need(old['format'] == 'biograph-steward.deepgo-nonpk-evaluation.v1.results'
         and len(old['earlier_36_outcome_rows']) == 36 and len(old['new_outcome_rows']) == 6
         and result['earlier42_outcome_rows'] == old['earlier_36_outcome_rows'] + old['new_outcome_rows'],
         'all42 previous point outcomes must remain exact, including unfavorable/missing states.')
    need(result['limitations'] == plan['limitations']
         and all(result['source_files_sha256'].get(path) == pin for path, pin in policy['input_files_sha256'].items())
         and result['actual_imported_helper_sources']
         and all(policy['input_files_sha256'].get(path) == pin
                 for path, pin in result['actual_imported_helper_sources'].items()),
         'source/helper pins or interpretation limits differ.')
    reject_raw(result)
    admission_gate(result['raw_forecast_admission'], policy, plan)
    denominators = {(row['setting'], row['namespace']): row for row in old['denominators']}
    strata = {(setting, aspect) for setting in SETTINGS for aspect in ASPECTS}
    need(len(old['denominators']) == len(denominators) == 6 and set(denominators) == strata,
         'six original denominator strata required.')
    new = result['new_outcome_rows']
    need(len(new) == 6 and {(row['setting'], row['namespace'], row['method']) for row in new}
         == {(setting, aspect, METHOD) for setting, aspect in strata}, 'all six new point cells required.')
    for row in new:
        d = denominators[row['setting'], row['namespace']]
        need(d['eligible_proteins'] == plan['evaluation']['eligible_N'][row['setting']][row['namespace']],
             'original protocol eligible N differs.')
        point_gate(row, d)
    pairs = result['paired_comparisons']
    required = {(setting, method, readout) for setting in SETTINGS for method in COMPARATORS for readout in READOUTS}
    need(len(pairs) == 12 and {(row['setting'], row['comparator'], row['readout']) for row in pairs} == required
         and all(row['namespace'] == 'molecular_function' and row['candidate'] == METHOD for row in pairs),
         'all twelve ordinary/IA MFO contrasts versus all three controls required.')
    for row in pairs:
        need(finite(row['difference_mean'], -1., 1.)
             and interval(row['paired_95_percentile_interval'], -1., 1.)
             and finite(row['fraction_draws_above_zero'], 0., 1.), 'finite complete conditional method intervals required.')
    agreements = result['native_MFO_point_count_agreements']
    need(set(agreements) == {setting + '/' + METHOD for setting in SETTINGS},
         'both new actual-native MFO count agreements required.')
    for key, agreement in agreements.items():
        setting = key.split('/')[0]; d = denominators[setting, 'molecular_function']
        need(agreement['author_point_agreement_passed'] is True and agreement['known_exclusion'] is None
             and agreement['namespace'] == 'molecular_function'
             and agreement['raw_reference_proteins'] == d['author_recognized_target_IDs']
             and agreement['ordinary_eligible'] == d['eligible_proteins']
             and agreement['IA_weighted_eligible'] == d['IA_eligible_proteins']
             and agreement['checks'] and all(finite(value['max_absolute_curve_difference'], 0., 1e-12)
                                            for value in agreement['checks'].values()),
             'native None-branch point/count agreement or population differs.')
    reports = result['uncertainty_reports']
    need(set(reports) == set(SETTINGS), 'both shared-protein native bootstrap reports required.')
    for setting, value in reports.items():
        need(value['content_sha256'] == digest({k: v for k, v in value.items() if k != 'content_sha256'})
             and value['draws'] == 2000 and value['seed'] == 20261113 and value['numpy'] == '1.26.4'
             and value['shared_protein_samples_across_all_arms'] is True
             and value['raw_proteins'] == denominators[setting, 'molecular_function']['author_recognized_target_IDs']
             and set(value['scores']) == {METHOD, *COMPARATORS}, 'shared native protein-resampling scope differs.')
        need([{'setting': setting, 'namespace': 'molecular_function', **row} for row in value['comparisons']]
             == [row for row in pairs if row['setting'] == setting], 'flat and nested method contrasts differ.')
        for method, scores in value['scores'].items():
            need(set(scores) == set(READOUTS) and all(interval(score['bootstrap_95_percentile_interval'], 0., 1.)
                 and finite(score['bootstrap_mean'], 0., 1.) for score in scores.values()),
                 'complete ordinary and IA method uncertainty required.')
        for row in value['comparisons']:
            expected_difference = value['scores'][METHOD][row['readout']]['bootstrap_mean'] - \
                                  value['scores'][row['comparator']][row['readout']]['bootstrap_mean']
            need(math.isclose(row['difference_mean'], expected_difference, rel_tol=1e-12, abs_tol=1e-12),
                 'bootstrap difference mean differs from the saved paired method means.')
    public = _task_tree(result, sanitize=True)
    _task_tree(public); public_paths_absent(public)
    need(all(public[key] == result[key] for key in
         ('new_outcome_rows', 'earlier42_outcome_rows', 'paired_comparisons', 'raw_forecast_admission')),
         'sanitization changed an outcome, interval or aggregate admission gate.')
    profile = _task_tree({key: plan[key] for key in ('model', 'prediction_axis', 'inference')}, sanitize=True)
    _task_tree(profile); public_paths_absent(profile)
    report = sealed({'format': FORMAT + '.public-results', 'created_at': utcnow(),
        'source_report_file_sha256': expected, 'source_report_content_sha256': result['content_sha256'],
        'evaluation_freeze_file_sha256': freeze_expected, 'scientific_protocol_file_sha256': protocol_expected,
        'previous42_report_file_sha256': previous_expected, 'results': public, 'producer_profile': profile,
        'outcome_slots': 48, 'new_outcomes': 6, 'MFO_paired_intervals': 12,
        'development_exposed_reference': True, 'operator_paths_or_raw_cases_included': False,
        'automatic_adoption': False, 'publisher_implementation_sha256': sha(__file__)})
    out = new_output(output, source, freeze, previous, protocol)
    write_json(out / 'report.json', report); render(report, out / 'report.html')
    write_json(out / 'publication_manifest.json', sealed({'format': FORMAT + '.publication-manifest',
        'source_report_file_sha256': expected, 'files': {name: sha(out / name) for name in ('report.json', 'report.html')},
        'outcome_slots': 48, 'new_outcomes': 6, 'MFO_paired_intervals': 12,
        'operator_paths_or_raw_cases_included': False, 'automatic_adoption': False}))
    return report


def render(report, path):
    value = report['results']; esc = lambda item: escape(str(item), quote=True)
    names = {'no_knowledge': 'No knowledge (NK)', 'limited': 'Limited knowledge (LK)'}
    new, old = value['new_outcome_rows'], value['earlier42_outcome_rows']
    def row(item):
        return [names[item['setting']], item['namespace'], item['method'], item['status'], item['eligible_proteins'],
            item['IA_eligible_proteins'], *(item.get(key) for key in METRICS),
            item.get('unweighted_Smin'), item.get('IA_weighted_Smin')]
    headers = ['Setting', 'Aspect', 'Profile', 'Native status', 'Original N', 'IA N', 'Micro Fmax',
               'IA micro', 'Macro', 'IA macro', 'Smin', 'IA Smin']
    focus = [item for item in new + old if item['namespace'] == 'molecular_function'
             and item['method'] in (METHOD, *COMPARATORS)]
    parts = ['<!doctype html><html lang="en"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>ProtNote native development comparison</title><style>body{font:16px system-ui;line-height:1.5;max-width:1450px;margin:2rem auto;padding:0 1rem;color:#203343}table{border-collapse:collapse;width:100%;font-size:13px}th,td{padding:.6rem;border-bottom:1px solid #ccd5df;text-align:left}.table{overflow:auto}.scope{background:#fff1d5;padding:1rem}details{margin:1rem 0}code{overflow-wrap:anywhere}pre{white-space:pre-wrap;overflow-wrap:anywhere}</style>',
        '<h1>ProtNote on the existing lower-knowledge reference</h1><p class="scope">DEVELOPMENT: previously exposed CAFA5 NK/LK outcomes. One published seed42 profile, six new point cells and all twelve fixed MFO contrasts are retained beside all42 earlier outcomes. This is not a fresh holdout, a whole-graph biological-accuracy percentage or a new accepted graph fact.</p>',
        '<p>ProtNote scores full canonical amino-acid sequences against a separately fixed GO2023 name/definition axis. Target annotations, FASTA header labels and benchmark terms of interest do not define the numerical prediction axis. Native synthetic parity and strict cached-source/axis checks qualify the interface, not scientific accuracy.</p>',
        '<h2>Molecular function against all three fixed comparators</h2>', table(headers, [row(item) for item in focus]),
        '<h2>All twelve paired MFO intervals</h2>',
        table(['Setting', 'Comparator', 'Readout', '95% lower', '95% upper', 'Bootstrap mean difference'],
            [[names[item['setting']], item['comparator'], item['readout'],
              *item['paired_95_percentile_interval'], item['difference_mean']] for item in value['paired_comparisons']]),
        '<p>ProtNote minus comparator; original native protein frame, 2,000 shared resamples and seed20261113. Conditional percentile intervals are not independent-study replication or multiplicity-adjusted confirmation. Native MFO eligible N remains explicit.</p>',
        '<h2>All six new native point cells</h2>', table(headers, [row(item) for item in new]),
        '<details><summary>All42 unchanged earlier outcomes, including losses, controls and missing states</summary>',
        table(headers, [row(item) for item in old]), '</details>',
        '<h2>Fixed0.5 operating points</h2><p>These are native operating points, not calibrated biological confidence. A missing native value stays missing.</p>',
        table(['Setting', 'Aspect', 'Profile', 'PPV', 'Recall', 'F1', 'Native status'],
            [[names[item['setting']], item['namespace'], item['method'],
              *((item.get('fixed_0_5') or {}).get(key) for key in ('PPV', 'recall', 'F1', 'status'))]
             for item in new + [item for item in old if item['namespace'] == 'molecular_function' and item['method'] in COMPARATORS]]),
        '<h2>Complete forecast admission</h2><p>All547 original identities remain either scored or explicitly unscorable; none is removed from the original evaluation denominators. The independent admission pass checks every scored target × fixed GO class, canonical row order and finite probabilities in[0,1]. Private identities, class arrays and score bodies are omitted here.</p><pre>',
        esc(json.dumps(value['raw_forecast_admission'], indent=2, sort_keys=True)), '</pre>',
        '<h2>Interpretation and source qualification</h2><p>Whole sequences, description conditioning, vocabulary, training dates and model components differ together. This compares practical published profiles and does not isolate one causal mechanism. NK/LK does not establish training-unseen sequences, homology separation or Pharos Tdark. E5 dates and training-overlap limitations make this retrospective development. Reference-unmatched forecasts are unresolved, not biological negatives; Fmax maximizes an evaluation threshold rather than measuring percent scientific accuracy.</p><ul>',
        ''.join('<li>' + esc(item) + '</li>' for item in value['limitations']), '</ul>',
        '<details><summary>Qualified native prediction profile</summary><pre>',
        esc(json.dumps(report['producer_profile'], indent=2, sort_keys=True)), '</pre></details>',
        '<p><a href="report.json">All48 outcomes, twelve intervals, native checks and source hashes</a> · <a href="publication_manifest.json">FILE manifest</a></p>',
        '<p>Source report FILE SHA256: <code>' + esc(report['source_report_file_sha256']) + '</code></p></html>']
    Path(path).write_text(''.join(parts))


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    for key in ('source', 'expected', 'freeze', 'freeze-expected', 'previous', 'previous-expected',
                'protocol', 'protocol-expected', 'output'):
        parser.add_argument('--' + key, required=True)
    value = prepare(**vars(parser.parse_args()))
    print(json.dumps({'format': value['format'], 'content_sha256': value['content_sha256']}))
