"""Publish saved method-complementarity aggregates without opening case files."""
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

FORMAT = 'biograph-steward.method-overlap.v1'
FRAMES = ('primary', 'reserved', 'no_knowledge', 'limited')
SETTINGS = {'primary': 'partial', 'reserved': 'partial',
            'no_knowledge': 'no_knowledge', 'limited': 'limited'}
ASPECTS = ('biological_process', 'molecular_function', 'cellular_component')
METHODS = ('deepgose', 'strict_alias_localplus')
RUNTIME = {'python': '3.10.12', 'numpy': '1.26.4', 'scipy': '1.13.1', 'pandas': '2.2.3'}
UNCERTAINTY = {'implementation': 'scipy.stats.bootstrap', 'version': '1.13.1',
    'paired': True, 'draws': 2000, 'seed': 20261113, 'method': 'percentile',
    'confidence_level': .95, 'batch': 100, 'multiplicity_adjusted': False}
FORBIDDEN = {'case_id', 'case_ids', 'protein', 'protein_id', 'protein_ids',
    'target', 'target_id', 'target_ids', 'term', 'terms', 'term_ids', 'term_indices',
    'selected_term_indices', 'selected_terms', 'selected_term_ids', 'GO_ID', 'GO_IDs',
    'row_ids', 'case_scores', 'predictions', 'raw_cases', 'raw_rows', 'reference_rows',
    'source_bodies', 'abstract', 'passage', 'statement'}


def frame_descriptors():
    return {frame: {'frame': frame, 'setting': SETTINGS[frame],
             'known_exclusion': 'native_known_t0_closure' if frame in ('primary', 'reserved') else None}
            for frame in FRAMES}


def reject_raw(value):
    """Reject identity-bearing fields even when their values are numeric indices."""
    if isinstance(value, dict):
        for key, item in value.items():
            need(key not in FORBIDDEN and not re.search(r'GO:\d{7}|UniProtKB:|PMID:', key),
                 'raw case or selected identity fields are not aggregate data.')
            reject_raw(item)
    elif isinstance(value, list):
        for item in value:
            reject_raw(item)


def scope(row):
    return row['frame'], row['namespace']


def check_point(row, policy):
    frame, aspect = scope(row)
    need(row['setting'] == SETTINGS[frame] and row['k'] == 3,
         'point task or strict review budget differs.')
    denominator = policy['frames'][frame]['denominators'][aspect]
    normal, weighted = row['ordinary'], row['IA_weighted']
    n = normal['eligible_proteins']
    need(n == denominator['eligible_proteins'] and n > 1
         and weighted['eligible_proteins'] == denominator['IA_eligible_proteins'],
         'native ordinary or IA eligible population differs.')
    returned = normal['returned_candidates']
    need(normal['TP'] + normal['reference_unmatched_predictions'] == returned
         and normal['unused_budget_slots'] == 3 * n - returned
         and 0 <= normal['TP'] <= returned <= 3 * n
         and abs(normal['curator_supported_slots_per_fixed3_budget'] - normal['TP'] / (3 * n)) <= 1e-12
         and normal['shortlist_is_ancestor_closed'] is False,
         'supported-slot or strict budget identity differs.')
    need(isinstance(row['native_reference_protein_order_sha256'], str)
         and re.fullmatch('[a-f0-9]{64}', row['native_reference_protein_order_sha256']),
         'native paired order pin required.')
    checks = row['native_batch_point_agreement']
    need(set(checks) == {'ordinary', 'IA_weighted'}, 'both native count gates required.')
    for kind, check in checks.items():
        need(check['passed'] is True and check['eligible_proteins'] == row[kind]['eligible_proteins']
             and check['columns'] == ['n', 'tp', 'fp', 'fn', 'pr', 'rc']
             and check['relative_tolerance'] == check['absolute_tolerance'] == 1e-12
             and check['same_native_function_same_eligible_frame'] is True
             and check['known_exclusion'] == frame_descriptors()[frame]['known_exclusion'],
             'native full-frame six-column agreement differs.')


def check_diagnostic(row, parents):
    """Check aggregate partitions without reading selected identities or truth."""
    need(set(row) == {'frame', 'setting', 'namespace', 'eligible_proteins', 'IA_eligible_proteins',
                     'exact_overlap', 'ancestor_overlap', 'oracle'}, 'unexpected diagnostic row field.')
    n = row['eligible_proteins']
    exact, related, oracle = (row[key] for key in ('exact_overlap', 'ancestor_overlap', 'oracle'))
    need(set(exact) == {'proteins_with_identical_sets', 'proteins_with_identical_order',
        'proteins_with_different_sets', 'proteins_with_any_returned', 'intersection_pairs',
        'union_pairs', 'pooled_Jaccard', 'buckets'} and set(related) == {
        'nonidentical_cross_method_related_pairs', 'proteins_with_cross_method_related_pair'}
        and set(oracle) == {'union_supported_cap3', 'best_parent_supported_per_protein',
        'union_baseline_absent_supported_cap3', 'best_parent_baseline_absent_supported_per_protein',
        'extra_supported_slots_over_best_parent_per_protein',
        'extra_baseline_absent_supported_slots_over_best_parent_per_protein',
        'ground_truth_aware_ceiling_not_a_deployable_result', 'fixed3_budget_yield'},
        'unexpected overlap, hierarchy or oracle field.')
    def count(value, maximum):
        need(type(value) is int and 0 <= value <= maximum, 'invalid aggregate count.')
    for key in ('proteins_with_identical_sets', 'proteins_with_identical_order',
                'proteins_with_different_sets', 'proteins_with_any_returned'):
        count(exact[key], n)
    need(exact['proteins_with_identical_sets'] + exact['proteins_with_different_sets'] == n
         and exact['proteins_with_identical_order'] <= exact['proteins_with_identical_sets'],
         'exact set/order count identity differs.')
    buckets = exact['buckets']
    need(set(buckets) == {'both_methods', 'deepgose_only', 'strict_alias_localplus_only', 'union'},
         'all shared, parent-only and union buckets required.')
    parts = ('literal_released_baseline', 'baseline_closure_only', 'baseline_absent')
    for bucket in buckets.values():
        need(set(bucket) == {'selected_pairs', 'curator_supported_pairs', 'reference_unmatched_pairs',
                            'curator_supported_IA', *parts}, 'unexpected support-bucket field.')
        selected, supported = bucket['selected_pairs'], bucket['curator_supported_pairs']
        count(selected, 6 * n)
        count(supported, selected)
        need(bucket['reference_unmatched_pairs'] == selected - supported,
             'reference-supported and unmatched partitions differ.')
        need(type(bucket['curator_supported_IA']) in (int, float)
             and math.isfinite(bucket['curator_supported_IA']) and bucket['curator_supported_IA'] >= 0,
             'invalid aggregate information weight.')
        for part in parts:
            need(set(bucket[part]) == {'selected_pairs', 'curator_supported_pairs'},
                 'unexpected baseline-stratum field.')
            count(bucket[part]['selected_pairs'], selected)
            count(bucket[part]['curator_supported_pairs'], bucket[part]['selected_pairs'])
        need(sum(bucket[part]['selected_pairs'] for part in parts) == selected
             and sum(bucket[part]['curator_supported_pairs'] for part in parts) == supported,
             'literal, closure-only and absent baseline partitions differ.')
    shared, left, right, union = (buckets[key] for key in
        ('both_methods', 'deepgose_only', 'strict_alias_localplus_only', 'union'))
    for key in ('selected_pairs', 'curator_supported_pairs', 'reference_unmatched_pairs', 'curator_supported_IA'):
        need(math.isclose(shared[key] + left[key] + right[key], union[key], rel_tol=1e-12, abs_tol=1e-12),
             'shared and parent-only buckets do not reconstruct the union.')
    for part in parts:
        for key in ('selected_pairs', 'curator_supported_pairs'):
            need(shared[part][key] + left[part][key] + right[part][key] == union[part][key],
                 'baseline-stratified buckets do not reconstruct the union.')
    need(exact['intersection_pairs'] == shared['selected_pairs']
         and exact['union_pairs'] == union['selected_pairs'], 'pooled overlap count differs.')
    expected_jaccard = shared['selected_pairs'] / union['selected_pairs'] if union['selected_pairs'] else None
    need(exact['pooled_Jaccard'] == expected_jaccard, 'pooled exact Jaccard differs.')
    for method, own in (('deepgose', left), ('strict_alias_localplus', right)):
        point = parents[row['frame'], row['namespace'], method]
        need(shared['selected_pairs'] + own['selected_pairs'] == point['ordinary']['returned_candidates']
             and shared['curator_supported_pairs'] + own['curator_supported_pairs'] == point['ordinary']['TP'],
             'overlap buckets do not reconstruct the parent shortlist.')
        need(math.isclose(shared['curator_supported_IA'] + own['curator_supported_IA'],
                          point['IA_weighted']['TP'], rel_tol=1e-12, abs_tol=1e-12),
             'overlap buckets do not reconstruct the parent IA support.')
    count(related['nonidentical_cross_method_related_pairs'], 9 * n)
    count(related['proteins_with_cross_method_related_pair'], n)
    need(related['proteins_with_cross_method_related_pair'] <= related['nonidentical_cross_method_related_pairs'],
         'ancestor-related pair/protein counts differ.')
    for key in ('union_supported_cap3', 'best_parent_supported_per_protein',
                'union_baseline_absent_supported_cap3', 'best_parent_baseline_absent_supported_per_protein'):
        count(oracle[key], 3 * n)
    parent_support = [shared['curator_supported_pairs'] + item['curator_supported_pairs'] for item in (left, right)]
    parent_absent_support = [shared['baseline_absent']['curator_supported_pairs']
                            + item['baseline_absent']['curator_supported_pairs'] for item in (left, right)]
    need(max(parent_support) <= oracle['best_parent_supported_per_protein'] <= oracle['union_supported_cap3']
         <= union['curator_supported_pairs']
         and oracle['best_parent_baseline_absent_supported_per_protein'] <= oracle['union_baseline_absent_supported_cap3']
         <= oracle['union_supported_cap3']
         and oracle['union_baseline_absent_supported_cap3'] <= union['baseline_absent']['curator_supported_pairs']
         and max(parent_absent_support) <= oracle['best_parent_baseline_absent_supported_per_protein']
         and oracle['best_parent_baseline_absent_supported_per_protein'] <= oracle['best_parent_supported_per_protein']
         and oracle['extra_supported_slots_over_best_parent_per_protein'] ==
             oracle['union_supported_cap3'] - oracle['best_parent_supported_per_protein']
         and oracle['extra_baseline_absent_supported_slots_over_best_parent_per_protein'] ==
             oracle['union_baseline_absent_supported_cap3'] - oracle['best_parent_baseline_absent_supported_per_protein']
         and oracle['ground_truth_aware_ceiling_not_a_deployable_result'] is True
         and abs(oracle['fixed3_budget_yield'] - oracle['union_supported_cap3'] / (3 * n)) <= 1e-12,
         'truth-aware oracle ceiling identity or deployment boundary differs.')


def prepare(source, expected, freeze, freeze_expected, output):
    source, freeze = map(Path, (source, freeze))
    need(sha(source) == expected and sha(freeze) == freeze_expected,
         'saved overlap source or freeze FILE differs.')
    result, policy = read(source), read(freeze)
    need(result.get('format') == FORMAT + '.results'
         and policy.get('format') == FORMAT + '.freeze'
         and result['source_freeze_file_sha256'] == freeze_expected,
         'overlap format or freeze binding differs.')
    need(result['runtime'] == policy['runtime'] == RUNTIME
         and result['k'] == policy['k'] == 3
         and result['rrf_offset'] == policy['rrf_offset'] == 60
         and policy['focus_namespace'] == 'molecular_function'
         and policy['previous_reference_and_metric_exposure'] is True,
         'frozen runtime, budget, fixed fusion or exposure differs.')
    need(set(policy['frames']) == set(FRAMES) and result['frames'] == frame_descriptors(),
         'all four task frames and their distinct known-mask semantics required.')
    need(result['source_files_sha256'] == policy['input_files_sha256'],
         'executed source lineage differs from the freeze.')
    need(result['PK_parent_reproduction_gate_passed'] is True
         and result['all12_declared_strata_preserved'] is True
         and result['development_only'] is True
         and result['app_default_or_consumer_changed'] is False,
         'parent reproduction, all-strata or no-adoption gate differs.')
    reject_raw(result)
    strata = {(frame, aspect) for frame in FRAMES for aspect in ASPECTS}
    rows = result['rows']
    need(len(rows) == 12 and {scope(row) for row in rows} == strata,
         'all twelve overlap strata required, including unfavorable outcomes.')
    for row in rows:
        frame, aspect = scope(row)
        denominator = policy['frames'][frame]['denominators'][aspect]
        need(row['setting'] == SETTINGS[frame]
             and row['eligible_proteins'] == denominator['eligible_proteins']
             and row['IA_eligible_proteins'] == denominator['IA_eligible_proteins']
             and all(isinstance(row[key], dict) for key in ('exact_overlap', 'ancestor_overlap', 'oracle')),
             'overlap denominator or aggregate sections differ.')
    parents, fusion, comparisons = (result[key] for key in ('parent_points', 'fusion_points', 'comparisons'))
    inventory = {(frame, aspect, method) for frame, aspect in strata for method in METHODS}
    need(len(parents) == 24 and {(r['frame'], r['namespace'], r['method']) for r in parents} == inventory,
         'all twenty-four unchanged parent points required.')
    for row in parents:
        check_point(row, policy)
    parent_index = {(r['frame'], r['namespace'], r['method']): r for r in parents}
    for row in rows:
        check_diagnostic(row, parent_index)
    gate = result['execution_gate']
    need(gate['kind'] == 'any_MFO_qualified_top3_set_differs'
         and type(gate['passed']) is bool and gate['not_truth_aware'] is True,
         'fusion execution must use the declared label-free gate.')
    need(gate['passed'] == any(row['exact_overlap']['proteins_with_different_sets'] > 0
                              for row in rows if row['namespace'] == 'molecular_function'),
         'label-free gate does not match the complete declared MFO set differences.')
    if gate['passed']:
        need(len(fusion) == 12 and {scope(r) for r in fusion} == strata
             and all(r['method'] == 'rrf3' for r in fusion),
             'a passed gate requires all twelve fixed fusion points.')
        need(result['uncertainty'] == UNCERTAINTY, 'fixed paired uncertainty recipe differs.')
        for row in fusion:
            check_point(row, policy)
            diagnostic = next(item for item in rows if scope(item) == scope(row))
            need(row['ordinary']['TP'] <= diagnostic['oracle']['union_supported_cap3'],
                 'fixed fusion exceeds its truth-aware candidate-union ceiling.')
        need(len(comparisons) == 24
             and {(r['frame'], r['namespace'], r['comparator']) for r in comparisons} == inventory,
             'all twenty-four fusion-versus-parent contrasts required.')
    else:
        need(fusion == [] and comparisons == [], 'failed execution gate must not emit synthetic fusion results.')
    points = {(r['frame'], r['namespace'], r['method']): r for r in parents + fusion}
    for frame, aspect in strata:
        same = [r for r in parents + fusion if scope(r) == (frame, aspect)]
        need(len({r['native_reference_protein_order_sha256'] for r in same}) == 1,
             'matched parent and fusion native orders differ.')
    for comparison in comparisons:
        frame, aspect = scope(comparison)
        candidate = points[frame, aspect, 'rrf3']['ordinary']
        comparator = points[frame, aspect, comparison['comparator']]['ordinary']
        difference = candidate['curator_supported_slots_per_fixed3_budget'] - comparator['curator_supported_slots_per_fixed3_budget']
        interval = comparison['paired_95_percentile_interval']
        need(comparison['setting'] == SETTINGS[frame] and comparison['candidate'] == 'rrf3'
             and comparison['metric'] == 'curator_supported_slots_per_fixed3_budget'
             and comparison['role'] == ('designated_focus' if aspect == 'molecular_function' else 'secondary')
             and comparison['eligible_proteins'] == candidate['eligible_proteins'] == comparator['eligible_proteins']
             and abs(comparison['point_difference'] - difference) <= 1e-12
             and isinstance(interval, list) and len(interval) == 2
             and all(type(x) in (int, float) and math.isfinite(x) and -1 <= x <= 1 for x in interval)
             and interval[0] <= interval[1], 'paired contrast differs from the saved matched-budget points.')
    public = _task_tree(result, sanitize=True)
    _task_tree(public)
    public_paths_absent(public)
    need(all(public[key] == result[key] for key in
             ('frames', 'rows', 'parent_points', 'fusion_points', 'comparisons', 'execution_gate')),
         'sanitization changed an outcome, identity-free diagnostic or gate.')
    report = sealed({'format': FORMAT + '.public-results', 'created_at': utcnow(),
        'source_report_file_sha256': expected, 'source_report_content_sha256': result['content_sha256'],
        'source_freeze_file_sha256': freeze_expected, 'source_freeze_content_sha256': policy['content_sha256'],
        'results': public, 'development_exposed_reference': True,
        'operator_paths_or_raw_cases_included': False, 'automatic_adoption': False,
        'publisher_implementation_sha256': sha(__file__)})
    out = new_output(output, source, freeze)
    write_json(out / 'report.json', report)
    render(report, out / 'report.html')
    write_json(out / 'publication_manifest.json', sealed({
        'format': FORMAT + '.publication-manifest', 'source_report_file_sha256': expected,
        'source_freeze_file_sha256': freeze_expected,
        'files': {name: sha(out / name) for name in ('report.json', 'report.html')},
        'overlap_strata': 12, 'parent_points': 24, 'fusion_points': len(fusion),
        'paired_comparisons': len(comparisons), 'operator_paths_or_raw_cases_included': False,
        'automatic_adoption': False}))
    return report


def render(report, path):
    value = report['results']
    esc = lambda item: escape(str(item), quote=True)
    names = {'primary': 'Original PK', 'reserved': 'Additional PK',
             'no_knowledge': 'No knowledge (NK)', 'limited': 'Limited knowledge (LK)'}
    aspects = {'biological_process': 'BPO', 'molecular_function': 'MFO', 'cellular_component': 'CCO'}
    points = value['parent_points'] + value['fusion_points']
    parts = ['<!doctype html><html lang="en"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>Method overlap and fixed-budget fusion</title><style>body{font:16px system-ui;line-height:1.5;max-width:1450px;margin:2rem auto;padding:0 1rem;color:#203343}table{border-collapse:collapse;width:100%;font-size:13px}th,td{padding:.6rem;border-bottom:1px solid #ccd5df;text-align:left}.table{overflow:auto}.scope{background:#fff1d5;padding:1rem}details{margin:1rem 0}code{overflow-wrap:anywhere}pre{white-space:pre-wrap;overflow-wrap:anywhere}</style>',
        '<h1>Method overlap and one fixed three-slot combination</h1><p class="scope">DEVELOPMENT on previously exposed CAFA5 outcomes. Shared predictions are not independent biological evidence. PK and NK/LK task masks remain separate; all twelve declared strata are retained. No app default, accepted graph fact or automatic pruning rule changes.</p>',
        '<p>Exact GO overlap, ancestor relationships and reuse of pre-existing annotations answer different questions. Oracle union support uses reference knowledge and is only a diagnostic upper bound, never a deployable method. Missing curator matches remain unresolved.</p>',
        '<h2>Declared execution gate</h2><p>' + esc(json.dumps(value['execution_gate'], sort_keys=True)) + '</p>',
        '<h2>All saved matched-budget points</h2>',
        table(['Frame', 'Task', 'Aspect', 'Method', 'Eligible N', 'Supported slots / 3-budget', 'PPV among returned', 'Recall', 'Filled budget', 'Coverage'],
            [[names[r['frame']], r['setting'], aspects[r['namespace']], r['method'], r['ordinary']['eligible_proteins'],
              *(r['ordinary'][key] for key in ('curator_supported_slots_per_fixed3_budget', 'PPV_among_returned',
                  'micro_recall', 'filled_slot_fraction', 'prediction_coverage'))] for r in points]),
        '<h2>All paired fusion-versus-parent differences</h2><p>The same three-slot budget applies to every method. Paired conditional percentile intervals use 2,000 shared protein resamples, seed 20261113; they are not multiplicity adjusted or an independent replication.</p>']
    if value['comparisons']:
        parts.append(table(['Frame', 'Aspect', 'Comparator', 'Role', 'Point difference', '95% lower', '95% upper'],
            [[names[r['frame']], aspects[r['namespace']], r['comparator'], r['role'], r['point_difference'],
              *r['paired_95_percentile_interval']] for r in value['comparisons']]))
    else:
        parts.append('<p>The label-free execution gate did not pass. No fusion points or intervals were generated.</p>')
    parts.append('<h2>All overlap and oracle diagnostics</h2><p>Complete aggregate sections are retained below without selected target or term identities.</p>')
    for row in value['rows']:
        parts.extend(['<details><summary>' + esc(names[row['frame']] + ' / ' + aspects[row['namespace']]) + '</summary>',
            '<pre>' + esc(json.dumps(row, indent=2, sort_keys=True)) + '</pre></details>'])
    parts.extend(['<h2>Interpretation and source qualification</h2><p>The fixed RRF baseline combines ranks with offset 60, equal method weights and the same canonical-ID tie-break. It is an adaptation of an established information-retrieval formula, not a validated biomedical truth score. No score calibration, weight search, new model or post-selection ancestor expansion is performed. Existing annotations are a membership control, not an arbitrarily ordered third voter.</p><ul>',
        ''.join('<li>' + esc(item) + '</li>' for item in value['limitations']), '</ul>',
        '<p><a href="report.json">Complete saved aggregates, native checks and source hashes</a> · <a href="publication_manifest.json">FILE manifest</a></p>',
        '<p>Source report FILE SHA256: <code>' + esc(report['source_report_file_sha256']) + '</code></p></html>'])
    Path(path).write_text(''.join(parts))


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    for key in ('source', 'expected', 'freeze', 'freeze-expected', 'output'):
        parser.add_argument('--' + key, required=True)
    result = prepare(**vars(parser.parse_args()))
    print(json.dumps({'format': result['format'], 'content_sha256': result['content_sha256']}))
