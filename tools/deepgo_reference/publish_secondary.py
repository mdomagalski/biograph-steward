"""Publish saved exploratory MFO AND CCO uncertainty with existing sanitizers.

No scientific evaluator, predictor, case or raw-forecast reader is imported.
Both secondary aspects and all eight contrasts remain separate from the fixed
fill-primary decision and the common-MAX sensitivity.
"""
import argparse
from copy import deepcopy
from html import escape
import json
from pathlib import Path

from biograph_steward.client import digest, utcnow, write_json
from biograph_steward.file_utils import new_output, sha
from biograph_steward.scientific_assessment import _task_tree
from .archive import need, sealed
from .publish import read, public_paths_absent, table, METRICS

ASPECTS = ('molecular_function', 'cellular_component')
FRAMES = ('primary', 'reserved')
METHODS = ('deepgose', 'strict_alias_localplus')
READOUTS = ('ordinary', 'IA_weighted')
BOUNDARIES = [
    'EXPLORATORY, POST-HOC: all six fill point values were already observed before this uncertainty supplement was frozen. Both molecular function and cellular component, both cohorts and both readouts are retained irrespective of direction.',
    'These eight conditional paired intervals are not multiplicity adjusted, fresh-reference confirmation, or independent biological replication. Protein, graph and source dependencies remain.',
    'The same sealed full joined forecasts and unchanged native fill parser/count pipeline, ontology, known masks, terms of interest, IA and threshold grid are reused. Both methods require agreement with their saved native point curves.',
    'Each cohort/aspect uses 2,000 shared protein draws with seed 20261113. Fmax is recomputed over the fixed benchmark grid; its threshold is not calibrated model confidence.',
    'The original four-interval BPO adoption rule and all 252 fill-primary outcomes remain unchanged. Secondary intervals cannot promote a favorable aspect, add a DeepGO consumer, or replace the retained LocalPlus default.',
    'This appendix is also separate from the common-MAX postprocessing sensitivity. Neither supplement changes models, sources, training, targets or the failed primary decision.'
]


def prepare(source, expected, freeze, freeze_expected, primary, primary_expected, output):
    source, freeze, primary = map(Path, (source, freeze, primary))
    for path, pin in ((source, expected), (freeze, freeze_expected), (primary, primary_expected)):
        need(sha(path) == pin, 'saved secondary source/freeze/primary FILE pin differs.')
    result, policy, parent = map(read, (source, freeze, primary))
    need(result.get('format') == 'biograph-steward.deepgo-secondary-uncertainty.v1.results'
         and policy.get('format') == 'biograph-steward.deepgo-exploratory-secondary-uncertainty.v1.freeze'
         and parent.get('format') == 'biograph-steward.deepgo-development.v1.results', 'saved formats differ.')
    need(result['freeze_file_sha256'] == freeze_expected
         and policy['posthoc_exploratory'] is policy['point_values_already_seen'] is True
         and result['posthoc_exploratory_after_all_six_point_values_seen'] is True
         and result['multiplicity_adjusted'] is False, 'exploratory/exposed-point scope differs.')
    need(policy['namespaces'] == list(ASPECTS) and policy['methods'] == list(METHODS)
         and policy['draws'] == 2000 and policy['seed'] == 20261113
         and policy['propagation'] == 'fill', 'fixed secondary inventory/parameters differ.')
    need(result['runtime'] == policy['runtime'] == {
             'python': '3.10.12', 'numpy': '1.26.4', 'scipy': '1.13.1', 'pandas': '2.2.3'},
         'saved result/freeze measurement runtime differs.')
    primary_pins = [h for p, h in policy['input_files_sha256'].items()
                    if p.endswith('/native_evaluation_v2/aggregate/report.json')]
    need(primary_pins == [primary_expected]
         and all(result['input_files_sha256'].get(p) == h for p, h in policy['input_files_sha256'].items()),
         'the supplement is not bound to this unchanged primary and its source pins.')
    need(result['all_eight_contrasts_retained_regardless_of_direction'] is True
         and result['primary_adoption_rule_changed'] is False
         and result['product_consumer_added'] is False
         and result['new_model_source_or_reference_release'] is False
         and result['raw_reference_or_forecast_rows_included'] is False, 'primary/no-adoption or raw-case boundary differs.')
    inventory = {(f, a, k) for f in FRAMES for a in ASPECTS for k in READOUTS}
    pairs = result['paired_comparisons']
    need(len(pairs) == 8 and {(r['frame'], r['namespace'], r['readout']) for r in pairs} == inventory
         and all(r['candidate'] == 'deepgose' and r['comparator'] == 'strict_alias_localplus' for r in pairs),
         'all eight secondary contrasts are required, without duplicates or favorable-only selection.')
    denominators = {(d['frame'], d['namespace']): d for d in parent['denominators'] if d['setting'] == 'partial'}
    agreements = result['point_count_agreements']; required = {f+'/'+a+'/'+m for f in FRAMES for a in ASPECTS for m in METHODS}
    need(set(agreements) == required, 'all eight fresh native point/count agreements are required.')
    for key, a in agreements.items():
        frame, namespace, method = key.split('/'); d = denominators[frame, namespace]
        need(a['namespace'] == namespace and a['propagation'] == 'fill'
             and a['full_original_all_namespace_parser_pipeline'] is a['author_point_agreement_passed'] is True
             and [a['raw_reference_proteins'], a['ordinary_eligible'], a['IA_weighted_eligible']] ==
                 [d['author_recognized_target_IDs'], d['eligible_proteins'], d['IA_eligible_proteins']]
             and set(a['checks']) == set(READOUTS)
             and all(c['max_absolute_curve_difference'] <= 1e-12 for c in a['checks'].values()),
             'native pipeline, denominator or point agreement differs.')
    reports = result['uncertainty_reports']
    need(set(reports) == {f+'/'+a for f in FRAMES for a in ASPECTS}, 'all four shared-draw reports are required.')
    for key, report in reports.items():
        frame, namespace = key.split('/'); d = denominators[frame, namespace]
        need(report['content_sha256'] == digest({k:v for k,v in report.items() if k != 'content_sha256'})
             and report['draws'] == 2000 and report['seed'] == 20261113
             and report['raw_proteins'] == d['author_recognized_target_IDs']
             and report['shared_protein_samples_across_all_arms'] is True
             and report['numpy'] == '1.26.4' and set(report['scores']) == set(METHODS),
             'saved shared-draw report seal/frame/runtime differs.')
        need([{'frame': frame, 'namespace': namespace, **r} for r in report['comparisons']] ==
             [r for r in pairs if (r['frame'], r['namespace']) == (frame, namespace)],
             'flat and nested paired comparisons differ.')
    points = []
    for row in parent['new_outcome_rows'] + parent['earlier_240_outcome_rows']:
        if row['setting'] == 'partial' and row['namespace'] in ASPECTS and row['method'] in METHODS:
            keys = ('frame', 'namespace', 'method', 'status', 'eligible_proteins', 'IA_eligible_proteins',
                    *METRICS, 'unweighted_Smin', 'IA_weighted_Smin', 'fixed_0_5')
            points.append({k: deepcopy(row[k]) for k in keys if k in row})
    need(len(points) == 8 and {(r['frame'], r['namespace'], r['method']) for r in points} ==
         {(f, a, m) for f in FRAMES for a in ASPECTS for m in METHODS},
         'all eight exact secondary point profile inventory rows are required.')
    public = _task_tree(result, sanitize=True); _task_tree(public); public_paths_absent(public)
    need(public['paired_comparisons'] == pairs and public['point_count_agreements'] == agreements,
         'sanitizer changed a saved interval or agreement.')
    value = sealed({'format': 'biograph-steward.deepgo-development.v1.public-secondary-uncertainty',
        'created_at': utcnow(), 'source_report_file_sha256': expected,
        'source_report_content_sha256': result['content_sha256'], 'source_freeze_file_sha256': freeze_expected,
        'source_freeze_content_sha256': policy['content_sha256'], 'primary_source_report_file_sha256': primary_expected,
        'primary_source_report_content_sha256': parent['content_sha256'],
        'unchanged_primary_BPO_retention_gate': deepcopy(parent['predeclared_development_retention_gate']),
        'results': public, 'already_reported_secondary_point_rows': points, 'delivery_boundaries': BOUNDARIES,
        'intervals': 8, 'posthoc_exploratory': True, 'multiplicity_adjusted': False,
        'primary_outcomes_overwritten': False, 'automatic_adoption': False,
        'operator_paths_or_raw_cases_included': False,
        'publisher_implementation_sha256': sha(__file__)})
    _task_tree(value); public_paths_absent(value)
    out = new_output(output, source, freeze, primary)
    write_json(out/'secondary_uncertainty.json', value); render(value, out/'secondary_uncertainty.html')
    render_markdown(value, out/'secondary_uncertainty.md')
    manifest = sealed({'format': 'biograph-steward.deepgo-development.v1.secondary-publication-manifest',
        'source_report_file_sha256': expected, 'content_sha256_of_public_report': value['content_sha256'],
        'files': {n: sha(out/n) for n in ('secondary_uncertainty.json', 'secondary_uncertainty.html', 'secondary_uncertainty.md')},
        'intervals': 8, 'posthoc_exploratory': True, 'primary_changed': False,
        'operator_paths_or_raw_cases_included': False})
    write_json(out/'publication_manifest.json', manifest)
    return value


def render(value, path):
    result = value['results']; esc = lambda x: escape(str(x), quote=True)
    cohorts = {'primary': 'Original PK', 'reserved': 'Additional PK'}
    aspects = {'molecular_function': 'Molecular function', 'cellular_component': 'Cellular component'}
    parts = ['<!doctype html><html lang="en"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>DeepGO exploratory secondary uncertainty</title><style>body{font:16px system-ui;line-height:1.5;max-width:1300px;margin:2rem auto;padding:0 1rem;color:#203343}.table{overflow:auto}table{border-collapse:collapse;width:100%;font-size:14px}th,td{padding:.6rem;border-bottom:1px solid #ccd5df;text-align:left}.scope{background:#fff1d5;padding:1rem}code{overflow-wrap:anywhere}</style>',
        '<h1>Exploratory uncertainty for both secondary aspects</h1><p class="scope"><strong>POST-HOC; NOT MULTIPLICITY ADJUSTED.</strong> Molecular-function and cellular-component point values were already seen. All eight intervals are shown. The failed primary BPO adoption rule and retained LocalPlus profile remain unchanged.</p>',
        table(['Cohort', 'Aspect', 'Readout', '95% lower', '95% upper', 'Mean difference'],
              [[cohorts[r['frame']], aspects[r['namespace']], r['readout'], *r['paired_95_percentile_interval'], r['difference_mean']]
               for r in result['paired_comparisons']]),
        '<p>Differences are DeepGO minus full strict LocalPlus. These are conditional paired protein-bootstrap intervals, not independent study replication or confirmation. Fmax is a benchmark maximum, not calibrated scientific confidence.</p>',
        '<h2>Already reported point estimates</h2>',
        table(['Cohort', 'Aspect', 'Profile', 'Eligible N', 'Micro Fmax', 'IA micro', 'Macro', 'IA macro', 'Smin', 'IA Smin'],
              [[cohorts[r['frame']], aspects[r['namespace']], r['method'], r['eligible_proteins'],
                *(r.get(k) for k in METRICS), r.get('unweighted_Smin'), r.get('IA_weighted_Smin')]
               for r in value['already_reported_secondary_point_rows']]),
        '<h2>Interpretation boundaries</h2><ul>' + ''.join('<li>'+esc(x)+'</li>' for x in BOUNDARIES) + '</ul>',
        '<p><a href="secondary_uncertainty.json">All eight intervals, point agreements and source/runtime pins</a> · <a href="publication_manifest.json">FILE manifest</a></p>',
        '<p>Source report FILE SHA256: <code>'+esc(value['source_report_file_sha256'])+'</code><br>Post-hoc freeze FILE SHA256: <code>'+esc(value['source_freeze_file_sha256'])+'</code></p></html>']
    Path(path).write_text(''.join(parts))


def render_markdown(value, path):
    """A reviewable insertion copied only from the saved aggregate endpoints."""
    cohorts = {'primary': 'Original PK', 'reserved': 'Additional PK'}
    aspects = {'molecular_function': 'MFO', 'cellular_component': 'CCO'}
    parts = ['## Exploratory secondary uncertainty', '',
        '**Post-hoc and not multiplicity adjusted.** All six original fill point values',
        'were already seen before these secondary intervals were specified. Both MFO',
        'and CCO, both existing cohorts and both readouts are retained regardless of',
        'direction. The original failed BPO adoption rule and retained LocalPlus',
        'profile remain unchanged; these intervals do not authorize a DeepGO consumer.', '',
        '| Cohort | Aspect | Readout | Paired 95% interval | Bootstrap mean difference |',
        '| --- | --- | --- | --- | ---: |']
    for row in value['results']['paired_comparisons']:
        lo, hi = row['paired_95_percentile_interval']
        parts.append('| '+cohorts[row['frame']]+' | '+aspects[row['namespace']]+' | '+row['readout']+
            ' | ['+format(lo,'.6f')+', '+format(hi,'.6f')+'] | '+format(row['difference_mean'],'.6f')+' |')
    parts += ['', 'Differences are DeepGO minus matched full strict-source LocalPlus. Each',
        'cohort/aspect uses the same 2,000 paired protein draws (seed 20261113),',
        'unchanged native fill confusion counts and fixed Fmax threshold grid.',
        'Both methods passed saved native point/count agreement. Protein/source',
        'dependence, incomplete annotations and reused-label exposure remain;',
        'these are conditional descriptive intervals rather than independent',
        'biological confirmation or calibrated confidence.', '',
        'Source aggregate FILE SHA-256: `'+value['source_report_file_sha256']+'`.',
        'Post-hoc source-freeze FILE SHA-256: `'+value['source_freeze_file_sha256']+'`.', '']
    Path(path).write_text('\n'.join(parts))


if __name__ == '__main__':
    p = argparse.ArgumentParser(description=__doc__)
    for key in ('source', 'expected', 'freeze', 'freeze-expected', 'primary', 'primary-expected', 'output'):
        p.add_argument('--'+key, required=True)
    v = prepare(**vars(p.parse_args())); print(json.dumps({'format': v['format'], 'content_sha256': v['content_sha256']}))
