"""Publish saved nonredundant-recommendation aggregates, never private cases.

This projects the sealed producer report through the existing aggregate-only
sanitizer. It imports neither a forecast/reference reader nor an evaluator and
does not follow input, numeric-artifact or parent paths listed in the receipts.
"""
import argparse
from html import escape
import json
import math
from pathlib import Path
import re

from biograph_steward.client import utcnow, write_json
from biograph_steward.file_utils import new_output, sha
from biograph_steward.scientific_assessment import _task_tree
from .archive import need, sealed
from .publish import read, public_paths_absent, table
from .publish_overlap import (ASPECTS, FRAMES, METHODS, RUNTIME, SETTINGS,
                              UNCERTAINTY, check_point, reject_raw)

FORMAT = 'biograph-steward.baseline-aware.v1'
VARIANTS = ('original_top3', 'filtered_after_top3', 'aware_before_top3')
GUARDS = {'all_previous_baseline_absent_predictions_retained': True,
    'all_new_choices_disjoint_from_baseline_closure': True,
    'ranking_uses_future_reference_values': False,
    'before_and_after_use_same_model_scores': True,
    'containment_is_not_evidence_of_model_improvement': True}
UTILITY_KEYS = {'old_after_filter_returned_candidates', 'new_before_filter_returned_candidates',
    'old_after_filter_unused_slots', 'new_before_filter_unused_slots', 'replenished_slots',
    'proteins_with_replenishment', 'old_baseline_absent_supported_pairs',
    'new_baseline_absent_supported_pairs', 'old_baseline_absent_reference_unmatched_pairs',
    'new_baseline_absent_reference_unmatched_pairs', 'added_curator_supported_pairs',
    'added_reference_unmatched_pairs', 'old_baseline_absent_supported_IA',
    'new_baseline_absent_supported_IA', 'added_curator_supported_IA', 'marginal_added_curator_support_fraction',
    'old_supported_slots_per_original_fixed3_budget', 'new_supported_slots_per_original_fixed3_budget',
    'ordinary_support_non_decrease_is_containment_property',
    'own_variant_uncertainty_or_model_superiority_claimed'}
POINT_KEYS = {'ordinary', 'IA_weighted', 'native_batch_point_agreement',
              'native_reference_protein_order_sha256'}
NORMAL_KEYS = {'eligible_proteins', 'TP', 'reference_unmatched_predictions',
    'unrecovered_reference_annotations', 'PPV_among_returned', 'micro_recall', 'micro_F1',
    'macro_PPV_including_abstentions', 'macro_recall_including_abstentions',
    'prediction_coverage', 'curator_supported_slots_per_fixed3_budget', 'filled_slot_fraction',
    'returned_candidates', 'unused_budget_slots', 'shortlists_with_ancestor_related_pair',
    'ancestor_related_pairs', 'mean_IA_per_returned_term',
    'curator_supported_IA_per_fixed3_budget', 'shortlist_is_ancestor_closed'}
WEIGHTED_KEYS = {'eligible_proteins', 'TP', 'reference_unmatched_predictions',
    'unrecovered_reference_annotations', 'PPV_among_returned', 'micro_recall', 'micro_F1',
    'macro_PPV_including_abstentions', 'macro_recall_including_abstentions', 'prediction_coverage'}


def close(a, b):
    return type(a) in (int, float) and type(b) in (int, float) and math.isfinite(a) and math.isfinite(b) \
        and math.isclose(a, b, rel_tol=1e-12, abs_tol=1e-12)


def count(value, maximum=None):
    need(type(value) in (int, float) and math.isfinite(value) and value >= 0
         and float(value).is_integer() and (maximum is None or value <= maximum),
         'nonnegative bounded integer aggregate required.')


def pin(value):
    need(isinstance(value, str) and re.fullmatch('[a-f0-9]{64}', value), 'FILE/order seal required.')


def check_saved_point(point, row, policy):
    need(set(point) == POINT_KEYS and set(point['ordinary']) == NORMAL_KEYS
         and set(point['IA_weighted']) == WEIGHTED_KEYS, 'unexpected saved point field.')
    full = {key: row[key] for key in ('frame', 'setting', 'namespace', 'method', 'k')}
    check_point({**full, **point}, policy)
    n = point['ordinary']['eligible_proteins']
    normal = point['ordinary']
    for key in ('TP', 'reference_unmatched_predictions', 'unrecovered_reference_annotations',
                'returned_candidates', 'unused_budget_slots'):
        count(normal[key])
    count(normal['shortlists_with_ancestor_related_pair'], n)
    count(normal['ancestor_related_pairs'], 3 * n)
    need(normal['shortlists_with_ancestor_related_pair'] <= normal['ancestor_related_pairs']
         and close(normal['filled_slot_fraction'], normal['returned_candidates'] / (3 * n)),
         'ancestor diagnostics or filled-budget fraction differs.')
    information = normal['mean_IA_per_returned_term']
    need((information is None) == (normal['returned_candidates'] == 0)
         and (information is None or (type(information) in (int, float)
              and math.isfinite(information) and information >= 0)), 'invalid returned-term specificity.')
    for kind in ('ordinary', 'IA_weighted'):
        value = point[kind]
        for key in ('TP', 'reference_unmatched_predictions', 'unrecovered_reference_annotations'):
            need(type(value[key]) in (int, float) and math.isfinite(value[key]) and value[key] >= 0,
                 'invalid native support or reference total.')
        tp, unmatched, fn = (value[key] for key in
            ('TP', 'reference_unmatched_predictions', 'unrecovered_reference_annotations'))
        need(close(value['PPV_among_returned'], tp / (tp + unmatched) if tp + unmatched else 0.)
             and close(value['micro_recall'], tp / (tp + fn) if tp + fn else 0.),
             'saved precision or recall differs from native counts.')


def check_row(row, policy):
    need(set(row) == {'frame', 'setting', 'namespace', 'method', 'k', 'eligible_proteins',
        'IA_eligible_proteins', 'native_reference_protein_order_sha256', *VARIANTS,
        'construction_guards', 'utility', 'scoring_future_reference_unchanged_sha256'},
        'unexpected method/task row field.')
    den = policy['frames'][row['frame']]['denominators'][row['namespace']]
    need(row['eligible_proteins'] == den['eligible_proteins']
         and row['IA_eligible_proteins'] == den['IA_eligible_proteins']
         and row['construction_guards'] == GUARDS, 'original population or label-free construction differs.')
    pin(row['native_reference_protein_order_sha256'])
    pin(row['scoring_future_reference_unchanged_sha256'])
    for variant in VARIANTS:
        check_saved_point(row[variant], row, policy)
        need(row[variant]['native_reference_protein_order_sha256'] == row['native_reference_protein_order_sha256'],
             'original/after/before native case orders differ.')
    original, old, new = (row[key]['ordinary'] for key in VARIANTS)
    n = row['eligible_proteins']; u = row['utility']
    need(set(u) == UTILITY_KEYS, 'unexpected replenishment/cost field or own-variant interval.')
    for key in UTILITY_KEYS - {'marginal_added_curator_support_fraction',
            'old_baseline_absent_supported_IA', 'new_baseline_absent_supported_IA', 'added_curator_supported_IA',
            'old_supported_slots_per_original_fixed3_budget', 'new_supported_slots_per_original_fixed3_budget',
            'ordinary_support_non_decrease_is_containment_property', 'own_variant_uncertainty_or_model_superiority_claimed'}:
        count(u[key])
    for key in ('old_baseline_absent_supported_IA', 'new_baseline_absent_supported_IA', 'added_curator_supported_IA'):
        need(type(u[key]) in (int, float) and math.isfinite(u[key]) and u[key] >= -1e-12,
             'finite nonnegative information-accretion support required.')
    old_ia, new_ia = (row[variant]['IA_weighted']['TP'] for variant in ('filtered_after_top3', 'aware_before_top3'))
    need(close(u['old_baseline_absent_supported_IA'], old_ia)
         and close(u['new_baseline_absent_supported_IA'], new_ia)
         and close(u['added_curator_supported_IA'], new_ia - old_ia),
         'saved IA support or added information-accretion partition differs.')
    need(old['returned_candidates'] <= original['returned_candidates']
         and old['TP'] <= original['TP'] and old['reference_unmatched_predictions'] <= original['reference_unmatched_predictions']
         and new['TP'] >= old['TP'] and new['reference_unmatched_predictions'] >= old['reference_unmatched_predictions']
         and u['old_after_filter_returned_candidates'] == old['returned_candidates']
         and u['new_before_filter_returned_candidates'] == new['returned_candidates']
         and u['old_after_filter_unused_slots'] == old['unused_budget_slots']
         and u['new_before_filter_unused_slots'] == new['unused_budget_slots']
         and u['old_baseline_absent_supported_pairs'] == old['TP']
         and u['new_baseline_absent_supported_pairs'] == new['TP']
         and u['old_baseline_absent_reference_unmatched_pairs'] == old['reference_unmatched_predictions']
         and u['new_baseline_absent_reference_unmatched_pairs'] == new['reference_unmatched_predictions'],
         'saved original/post/aware support or cost reconstruction differs.')
    added = new['returned_candidates'] - old['returned_candidates']
    added_tp = new['TP'] - old['TP']
    added_unmatched = new['reference_unmatched_predictions'] - old['reference_unmatched_predictions']
    need(u['replenished_slots'] == added == added_tp + added_unmatched
         and u['added_curator_supported_pairs'] == added_tp
         and u['added_reference_unmatched_pairs'] == added_unmatched
         and 0 <= u['proteins_with_replenishment'] <= min(n, added)
         and (u['proteins_with_replenishment'] == 0) == (added == 0)
         and close(u['old_supported_slots_per_original_fixed3_budget'], old['TP'] / (3 * n))
         and close(u['new_supported_slots_per_original_fixed3_budget'], new['TP'] / (3 * n))
         and u['ordinary_support_non_decrease_is_containment_property'] is True
         and u['own_variant_uncertainty_or_model_superiority_claimed'] is False,
         'replenishment partition, original budget or containment interpretation differs.')
    need((u['marginal_added_curator_support_fraction'] is None if not added else
          close(u['marginal_added_curator_support_fraction'], added_tp / added)),
         'marginal support fraction differs.')
    for kind in ('ordinary', 'IA_weighted'):
        values = [row[key][kind] for key in VARIANTS]
        need(all(close(value['TP'] + value['unrecovered_reference_annotations'],
                       values[0]['TP'] + values[0]['unrecovered_reference_annotations']) for value in values),
             'original future reference was reduced for scoring.')
        need(values[2]['TP'] + 1e-12 >= values[1]['TP'], 'contained choices lost weighted/native support.')


def check_opportunity(row, policy):
    need(set(row) == {'frame', 'setting', 'namespace', 'original_eligible_proteins',
        'future_reference_pairs_absent_from_baseline', 'original_proteins_with_residual_reference_support',
        'zero_residual_reference_proteins_retained', 'residual_reference_IA', 'oracle_supported_cap3',
        'oracle_supported_slots_per_original_fixed3_budget', 'oracle_is_reference_aware_not_deployable',
        'original_population_and_future_reference_unchanged'}, 'unexpected opportunity field.')
    n = policy['frames'][row['frame']]['denominators'][row['namespace']]['eligible_proteins']
    pairs = row['future_reference_pairs_absent_from_baseline']
    positive = row['original_proteins_with_residual_reference_support']
    zero = row['zero_residual_reference_proteins_retained']; cap = row['oracle_supported_cap3']
    for item in (pairs, positive, zero, cap): count(item)
    need(row['setting'] == SETTINGS[row['frame']] and row['original_eligible_proteins'] == n
         and positive + zero == n and positive <= cap <= min(3 * positive, pairs)
         and (positive == 0) == (pairs == 0)
         and close(row['oracle_supported_slots_per_original_fixed3_budget'], cap / (3 * n))
         and type(row['residual_reference_IA']) in (int, float)
         and math.isfinite(row['residual_reference_IA']) and row['residual_reference_IA'] >= 0
         and row['oracle_is_reference_aware_not_deployable'] is True
         and row['original_population_and_future_reference_unchanged'] is True,
         'opportunity ceiling redefines the original population or scoring truth.')


def prepare(source, expected, freeze, freeze_expected, output):
    source, freeze = map(Path, (source, freeze))
    need(sha(source) == expected and sha(freeze) == freeze_expected, 'saved report or freeze FILE differs.')
    result, policy = read(source), read(freeze)
    need(result['format'] == FORMAT + '.results' and policy['format'] == FORMAT + '.freeze'
         and result['source_freeze_file_sha256'] == freeze_expected
         and result['runtime'] == policy['runtime'] == RUNTIME
         and result['k'] == policy['k'] == 3 and policy['development_only'] is True
         and policy['previous_reference_and_metric_exposure'] is True
         and policy['focus_namespace'] == 'molecular_function', 'frozen task, budget, runtime or exposure differs.')
    need(policy['status'] == 'FROZEN_before_new_baseline_aware_endpoint_values'
         and policy['no_new_baseline_aware_endpoint_values_seen'] is True
         and policy['invented_native_fixture']['passed'] is True
         and policy['propagation'] == 'fill' and policy['methods'] == list(METHODS)
         and policy['no_new_model_inference'] is True and policy['no_new_reference_release'] is True
         and policy['automatic_adoption'] is False and policy['app_default_or_graph_changes'] is False
         and policy['ranking']['same_full_frozen_forecasts'] is True
         and policy['ranking']['positive_scores_only'] is True
         and all(policy['scoring'][key] is True for key in
            ('original_native_PK_or_None_exclusion_retained', 'original_native_eligible_N_and_future_GT_retained',
             'baseline_is_not_subtracted_from_scoring_ground_truth', 'zero_residual_reference_cases_retained',
             'full_frame_and_per_case_native_count_agreement_required'))
         and policy['own_variant_utility']['paired_uncertainty_or_model_superiority_claimed'] is False,
         'source-frozen native fixture, label-free ranking or original scoring policy differs.')
    need(set(policy['frames']) == set(FRAMES), 'all original task frames required.')
    for frame in FRAMES:
        value = policy['frames'][frame]
        need(value['setting'] == SETTINGS[frame]
             and ((value['known'] is None) == (frame in ('no_knowledge', 'limited')))
             and set(value['denominators']) == set(ASPECTS), 'original PK/None frame contract differs.')
    need(result['source_files_sha256'] == policy['input_files_sha256']
         and result['parent_overlap_report_file_sha256'] == policy['parent_overlap_report']['sha256']
         and result['parent_overlap_freeze_file_sha256'] == policy['parent_overlap_freeze']['sha256']
         and result['uncertainty'] == UNCERTAINTY and result['limitations'] == policy['limitations'],
         'source/parent pins, conditional uncertainty or limitations differ.')
    for key in ('original_selected_identities_exactly_reconstructed',
                'all_original_populations_and_future_groundtruth_retained', 'all24_method_strata_preserved',
                'all12_opportunity_and_method_comparison_strata_preserved',
                'own_variant_utility_is_descriptive_containment_not_model_improvement', 'development_only'):
        need(result[key] is True, 'original selection, population or no-superiority gate differs.')
    for key in ('new_model_inference', 'new_reference_release', 'app_default_or_graph_changed', 'automatic_adoption'):
        need(result[key] is False, 'new computation/source or automatic adoption boundary differs.')
    reject_raw(result)
    strata = {(frame, aspect) for frame in FRAMES for aspect in ASPECTS}
    rows, opportunities, comparisons = (result[key] for key in ('rows', 'opportunity', 'comparisons'))
    need(len(rows) == 24 and {(r['frame'], r['namespace'], r['method']) for r in rows}
         == {(f, a, m) for f, a in strata for m in METHODS}, 'all 24 method/task rows required.')
    for row in rows: check_row(row, policy)
    need(len(opportunities) == 12 and {(r['frame'], r['namespace']) for r in opportunities} == strata,
         'all 12 opportunity rows required, including zero-residual cases.')
    for row in opportunities: check_opportunity(row, policy)
    index = {(r['frame'], r['namespace'], r['method']): r for r in rows}
    for frame, aspect in strata:
        matched = [index[frame, aspect, method] for method in METHODS]
        need(len({r['native_reference_protein_order_sha256'] for r in matched}) == 1
             and len({r['scoring_future_reference_unchanged_sha256'] for r in matched}) == 1,
             'paired methods have different native case order or reference.')
    need(len(comparisons) == 12 and {(r['frame'], r['namespace']) for r in comparisons} == strata,
         'all 12 method contrasts required; no own-variant intervals.')
    for row in comparisons:
        need(set(row) == {'frame', 'setting', 'namespace', 'candidate', 'comparator', 'metric',
            'eligible_proteins', 'role', 'not_a_guaranteed_own_variant_containment_comparison',
            'point_difference', 'paired_95_percentile_interval', 'bootstrap_mean_difference',
            'fraction_draws_above_zero'}, 'unexpected contrast field.')
        candidate, comparator = (index[row['frame'], row['namespace'], method]['aware_before_top3']['ordinary']
                                 for method in METHODS)
        difference = candidate['curator_supported_slots_per_fixed3_budget'] - comparator['curator_supported_slots_per_fixed3_budget']
        interval = row['paired_95_percentile_interval']
        need(row['setting'] == SETTINGS[row['frame']] and row['candidate'] == 'baseline_aware_deepgose'
             and row['comparator'] == 'baseline_aware_strict_alias_localplus'
             and row['metric'] == 'baseline_absent_curator_supported_slots_per_original_fixed3_budget'
             and row['eligible_proteins'] == candidate['eligible_proteins'] == comparator['eligible_proteins']
             and row['role'] == ('designated_focus' if row['namespace'] == 'molecular_function' else 'secondary')
             and row['not_a_guaranteed_own_variant_containment_comparison'] is True
             and close(row['point_difference'], difference)
             and isinstance(interval, list) and len(interval) == 2
             and all(type(x) in (int, float) and math.isfinite(x) and -1 <= x <= 1 for x in interval)
             and interval[0] <= interval[1]
             and type(row['bootstrap_mean_difference']) in (int, float)
             and math.isfinite(row['bootstrap_mean_difference']) and -1 <= row['bootstrap_mean_difference'] <= 1
             and type(row['fraction_draws_above_zero']) in (int, float)
             and 0 <= row['fraction_draws_above_zero'] <= 1,
             'matched-budget method contrast differs.')
    public = _task_tree(result, sanitize=True)
    _task_tree(public); public_paths_absent(public)
    need(all(public[key] == result[key] for key in ('rows', 'opportunity', 'comparisons')),
         'sanitization changed an aggregate outcome.')
    report = sealed({'format': FORMAT + '.public-results', 'created_at': utcnow(),
        'source_report_file_sha256': expected, 'source_report_content_sha256': result['content_sha256'],
        'source_freeze_file_sha256': freeze_expected, 'source_freeze_content_sha256': policy['content_sha256'],
        'results': public, 'development_exposed_reference': True,
        'operator_paths_or_raw_cases_included': False, 'automatic_adoption': False,
        'publisher_implementation_sha256': sha(__file__)})
    out = new_output(output, source, freeze)
    write_json(out / 'report.json', report); render(report, out / 'report.html')
    write_json(out / 'publication_manifest.json', sealed({'format': FORMAT + '.publication-manifest',
        'source_report_file_sha256': expected, 'source_freeze_file_sha256': freeze_expected,
        'files': {name: sha(out / name) for name in ('report.json', 'report.html')},
        'method_task_rows': 24, 'opportunity_strata': 12, 'paired_method_comparisons': 12,
        'own_variant_intervals': 0, 'operator_paths_or_raw_cases_included': False, 'automatic_adoption': False}))
    return report


def render(report, path):
    value = report['results']; esc = lambda item: escape(str(item), quote=True)
    frames = {'primary': 'Original PK', 'reserved': 'Additional PK',
              'no_knowledge': 'No knowledge (NK)', 'limited': 'Limited knowledge (LK)'}
    aspects = {'biological_process': 'BPO', 'molecular_function': 'MFO', 'cellular_component': 'CCO'}
    parts = ['<!doctype html><html lang="en"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>Nonredundant three-slot recommendations</title><style>body{font:16px system-ui;line-height:1.5;max-width:1550px;margin:2rem auto;padding:0 1rem;color:#203343}table{border-collapse:collapse;width:100%;font-size:13px}th,td{padding:.6rem;border-bottom:1px solid #ccd5df;text-align:left}.table{overflow:auto}.scope{background:#fff1d5;padding:1rem}details{margin:1rem 0}code{overflow-wrap:anywhere}pre{white-space:pre-wrap;overflow-wrap:anywhere}</style>',
        '<h1>Nonredundant recommendations with a three-slot budget</h1><p class="scope">DEVELOPMENT on previously exposed CAFA5 reference outcomes and benchmark terms of interest. This changes ranking eligibility, not the underlying predictor or official CAFA scoring. All original proteins, future-reference labels and PK/None scoring masks remain intact, including proteins with no baseline-absent reference opportunity. This is not a blind full-app novelty or whole-graph biological-accuracy result.</p>',
        '<p>The old control removes baseline-covered terms <em>after</em> choosing three and leaves holes. The candidate removes the dated baseline closure <em>before</em> choosing up to three from the same full score ranking. It retains every old baseline-absent choice. Its own support therefore cannot decrease by construction; extra supported choices must be read beside additional reference-unmatched proposals and review cost. No own-variant confidence interval or new-predictor win is claimed.</p>',
        '<h2>All saved original, after-filter and before-filter points</h2>',
        table(['Frame', 'Aspect', 'Method', 'Selection', 'Original N', 'Supported / 3N', 'PPV among returned', 'Recall', 'Returned', 'Unused slots', 'Mean IA / returned', 'Ancestor-related pairs'],
            [[frames[r['frame']], aspects[r['namespace']], r['method'], variant, p['eligible_proteins'],
              *(p[key] for key in ('curator_supported_slots_per_fixed3_budget', 'PPV_among_returned', 'micro_recall',
                'returned_candidates', 'unused_budget_slots', 'mean_IA_per_returned_term', 'ancestor_related_pairs'))]
             for r in value['rows'] for variant in VARIANTS for p in [r[variant]['ordinary']]]),
        '<h2>Added review slots: support and unresolved cost</h2>',
        table(['Frame', 'Aspect', 'Method', 'Added slots', 'Added supported', 'Added reference-unmatched', 'Marginal support fraction', 'Original zero-opportunity cases retained'],
            [[frames[r['frame']], aspects[r['namespace']], r['method'],
              *(r['utility'][key] for key in ('replenished_slots', 'added_curator_supported_pairs', 'added_reference_unmatched_pairs',
                 'marginal_added_curator_support_fraction')),
              next(o['zero_residual_reference_proteins_retained'] for o in value['opportunity']
                   if (o['frame'], o['namespace']) == (r['frame'], r['namespace']))] for r in value['rows']]),
        '<h2>All twelve DeepGO-minus-LocalPlus method contrasts</h2><p>Both methods use the same baseline-aware eligibility and three-slot budget. These genuine method contrasts have no subset guarantee. Paired conditional 95% percentile intervals reuse 2,000 protein resamples, seed 20261113; they are not multiplicity-adjusted confirmation.</p>',
        table(['Frame', 'Aspect', 'Role', 'Supported / 3N difference', '95% lower', '95% upper'],
            [[frames[r['frame']], aspects[r['namespace']], r['role'], r['point_difference'],
              *r['paired_95_percentile_interval']] for r in value['comparisons']]),
        '<h2>Reference opportunity and all saved IA/point diagnostics</h2><p>Reference-aware oracle capacity describes incomplete curator-label headroom; it is not a deployable selector. Reference-unmatched proposals are unresolved, not established biological errors. Baseline absence is absence from the dated released forecast closure, not proof of a newly discovered function or a literal original GAF assertion.</p>']
    for label, rows in (('Opportunity', value['opportunity']), ('Complete method/task diagnostics', value['rows'])):
        parts.extend(['<details><summary>' + esc(label) + '</summary><pre>',
                      esc(json.dumps(rows, indent=2, sort_keys=True)), '</pre></details>'])
    parts.extend(['<h2>Source qualification and limits</h2><p>No per-target future labels enter selection. The official benchmark terms-of-interest vocabulary and reference outcomes were already exposed; this is not a claim of deployment without benchmark information. No new labels, models, calibration, threshold sweep, source retrieval, app default, accepted graph fact or automatic pruning change follows.</p><ul>',
        ''.join('<li>' + esc(item) + '</li>' for item in value['limitations']), '</ul>',
        '<p><a href="report.json">Complete saved aggregates and source hashes</a> · <a href="publication_manifest.json">FILE manifest</a></p>',
        '<p>Source report FILE SHA256: <code>' + esc(report['source_report_file_sha256']) + '</code></p></html>'])
    Path(path).write_text(''.join(parts))


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    for key in ('source', 'expected', 'freeze', 'freeze-expected', 'output'):
        parser.add_argument('--' + key, required=True)
    value = prepare(**vars(parser.parse_args()))
    print(json.dumps({'format': value['format'], 'content_sha256': value['content_sha256']}))
