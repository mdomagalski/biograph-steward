"""Publish only saved DeepGO aggregate results and the complete prior inventory.

Adapts tools.cafa_combined.publish's static delivery and reuses the application's
aggregate-tree sanitizer. No predictor, evaluator, reference, sequence, checkpoint
or raw forecast reader is imported. Source aggregates and all numeric endpoints
remain unchanged; operator paths are removed or replaced by existing FILE pins.
"""
import argparse
from copy import deepcopy
from html import escape
import json
from pathlib import Path
import re

from biograph_steward.client import digest, utcnow, write_json
from biograph_steward.file_utils import new_output, sha
from biograph_steward.scientific_assessment import _task_tree
from .archive import need, sealed

FORMAT = 'biograph-steward.deepgo-development.v1'
ASPECTS = ('biological_process', 'molecular_function', 'cellular_component')
FRAMES = ('primary', 'reserved')
METRICS = ('micro_Fmax', 'IA_micro_Fmax', 'macro_Fmax', 'IA_macro_Fmax')
BOUNDARIES = [
    'This is DEVELOPMENT reuse of 1,294 original and 4,806 additional partial-knowledge proteins. The reference outcomes were previously exposed; no fresh holdout or independent confirmation is claimed.',
    'These are temporal recovery scores against incomplete curator annotations, not whole-graph biological accuracy. Fmax is a benchmark threshold maximum, not percent scientific accuracy or a calibrated acceptance probability.',
    'The published DeepGO-SE sequence/ontology profile uses six checkpoint members per aspect and float32 averaging. Corrected cellular-component model artifacts and native author CLI parity are required by the separate producer.',
    'The source reports 2021 model training, whereas the matched Local profile uses known annotations available in 2023. This compares practical profiles; it does not isolate algorithm, topology, sequence, or ontology-axiom effects.',
    'Actual author training membership and homology separation were not reconstructed. Partial knowledge does not mean proteins were unseen during model training; ESM pretraining overlap is not independently audited.',
    'The inference and CAFA evaluation runtimes are separate and explicitly pinned. Raw scores before the author CLI display cutoff and rounding are evaluated; no score calibration or model retraining is introduced.',
    'All 6,100 dated source sequences are covered. The native first-1,022-residue limit truncates 770 of them; these proteins remain in the fixed evaluation denominators.',
    'The fixed retention rule requires all FOUR paired 95% lower difference bounds against full strict Local to exceed zero: ordinary and information-accretion-weighted BPO in both cohorts. The same native 2,000 shared protein draws are conditional descriptive uncertainty, not independent biological replication.',
    'All 252 outcomes, negative and unsupported controls, all six new aspect/cohort cells, macro and weighted metrics, Smin, and fixed-0.5 trade-offs remain available. No automatic app, graph, pruning, review or model-default change follows.'
]
MAX_BOUNDARIES = [
    'This is a separately declared common postprocessing sensitivity. The CAFA5 fill primary, all 252 primary outcomes and its original four-interval retention rule remain unchanged, even when MAX differences are positive.',
    'The same official native evaluator applies max propagation to BOTH frozen profiles using the common 2023 is_a/part_of ontology, known masks, terms of interest, IA, threshold grid and evaluation runtime. Both profiles have fresh point/count agreement checks; fill counts are not reused.',
    'MAX is applied after the frozen six-model raw-mean DeepGO ensemble. The archived author saved-test path propagates individual model predictions and uses a 2021 ontology with different relationship handling. This is not a literal reproduction of paper postprocessing or its ensemble order.',
    'All 12 aspect/cohort/profile cells and four paired BPO intervals are retained. The same previously exposed development reference, training-overlap limits, native truncation and incomplete-annotation caveats apply. No automatic adoption or whole-graph accuracy claim follows.'
]


def read(path):
    path = Path(path)
    need(path.is_file() and not path.is_symlink() and path.stat().st_size <= 5_000_000,
         'bounded ordinary aggregate file required.')
    value = json.loads(path.read_text())
    need(isinstance(value, dict) and value.get('content_sha256') == digest(
        {k: v for k, v in value.items() if k != 'content_sha256'}), 'aggregate content seal differs.')
    return value


def public_paths_absent(value):
    """Reject remaining operator path spellings after the shared sanitizer."""
    if isinstance(value, dict):
        for key, item in value.items():
            public_paths_absent(key); public_paths_absent(item)
    elif isinstance(value, list):
        for item in value: public_paths_absent(item)
    elif isinstance(value, str):
        need(not value.startswith(('/', 'file:')) and not re.search(
            r'(?:file://)?/(?:Users|home|private|tmp|var|data|opt|root)/[^\s\"<>]+|[A-Za-z]:\\', value),
            'operator path remains in public aggregate.')


def max_appendix(source, expected, execution_file, execution_expected, primary, primary_expected):
    """Bind two saved aggregate receipts; never read a curve or prediction."""
    source, execution_file = Path(source), Path(execution_file)
    need(sha(source) == expected and sha(execution_file) == execution_expected,
         'MAX saved aggregate or execution FILE pin differs.')
    result, execution = read(source), read(execution_file)
    need(result.get('format') == 'biograph-steward.deepgo-common-max-sensitivity.results.v1'
         and execution.get('format') == 'biograph-steward.deepgo-common-max-sensitivity.execution.v1',
         'separate MAX aggregate/execution formats differ.')
    for key in ('source_freeze_file_sha256', 'execution_freeze_file_sha256'):
        need(isinstance(result[key], str) and re.fullmatch('[a-f0-9]{64}', result[key])
             and result[key] == execution[key], 'MAX source/execution freeze binding differs.')
    primary_status = [pin for path, pin in primary['input_files_sha256'].items()
                      if Path(path).name == 'status.json']
    need(len(primary_status) == 1 and execution['primary_completion_file_sha256'] == primary_status[0],
         'MAX execution does not bind this completed primary fill status.')
    need(result['actual_propagation'] == execution['actual_author_propagation'] == 'max'
         and execution['sequential_native_jobs'] is True
         and execution['parent_fill_primary_and_adoption_rule_unchanged'] is True
         and execution['new_model_calls'] == 0 and execution['new_reference_release'] is False,
         'MAX execution scope or primary-preservation flags differ.')
    need(len(result['rows']) == result['new_outcome_slots'] == 12
         and {(r['frame'], r['namespace'], r['method'], r['setting'], r['propagation'])
              for r in result['rows']} ==
             {(f, a, m, 'partial', 'max') for f in FRAMES for a in ASPECTS
              for m in ('deepgose_max', 'strict_alias_localplus_max')},
         'all twelve separate MAX outcomes are required.')
    paired = result['paired_comparisons']
    need(len(paired) == 4 and {(r['frame'], r['readout']) for r in paired} ==
         {(f, k) for f in FRAMES for k in ('ordinary', 'IA_weighted')}
         and all(r['candidate'] == 'deepgose_max' and r['comparator'] == 'strict_alias_localplus_max'
                 for r in paired), 'all four MAX paired comparisons are required.')
    need(result['primary_fill_252_outcomes_overwritten'] is False
         and result['primary_four_CI_adoption_rule_changed'] is False
         and result['automatic_adoption_from_sensitivity'] is False
         and result['new_source_model_training_or_reference_release'] is False
         and result['raw_reference_or_forecast_rows_included'] is False,
         'MAX sensitivity must not replace the primary or add raw cases.')
    public = _task_tree(result, sanitize=True)
    public_execution = _task_tree(execution, sanitize=True)
    _task_tree(public); _task_tree(public_execution)
    public_paths_absent(public); public_paths_absent(public_execution)
    need(public['rows'] == result['rows'] and public['paired_comparisons'] == paired,
         'sanitization changed a MAX point or interval.')
    return sealed({'format': FORMAT + '.public-max-sensitivity',
        'source_report_file_sha256': expected, 'source_report_content_sha256': result['content_sha256'],
        'source_execution_file_sha256': execution_expected,
        'source_execution_content_sha256': execution['content_sha256'],
        'primary_source_report_file_sha256': primary_expected,
        'primary_source_report_content_sha256': primary['content_sha256'],
        'primary_fill_retention_gate_unchanged': deepcopy(primary['predeclared_development_retention_gate']),
        'results': public, 'execution': public_execution, 'delivery_boundaries': MAX_BOUNDARIES,
        'outcome_slots': 12, 'primary_outcome_slots': 252,
        'operator_paths_or_raw_cases_included': False, 'automatic_adoption': False})


def prepare(source, previous_report, old_report, expected, output, *, max_source=None,
            max_expected=None, max_execution=None, max_execution_expected=None):
    source, previous_report, old_report = map(Path, (source, previous_report, old_report))
    need(sha(source) == expected, 'DeepGO saved aggregate FILE pin differs.')
    original, previous, old = map(read, (source, previous_report, old_report))
    need(original.get('format') == FORMAT + '.results'
         and previous.get('format') == 'biograph-steward.combined-development-results.v1',
         'saved aggregate format differs.')
    need(original['earlier_complete_comparison_file_sha256'] == sha(previous_report)
         and previous['earlier_240_report_file_sha256'] == sha(old_report)
         and previous['earlier_240_report_content_sha256'] == old['content_sha256'],
         'complete prior aggregate binding differs.')
    need(len(original['new_outcome_rows']) == 6 and len(original['earlier_240_outcome_rows']) == 240
         and len(original['earlier_six_combined_GM_outcome_rows']) == 6,
         'all 252 outcome slots are required.')
    need(original['earlier_240_outcome_rows'] == previous['earlier_240_outcome_rows'] == old['rows']
         and original['earlier_six_combined_GM_outcome_rows'] == previous['new_outcome_rows'],
         'prior outcome inventory changed.')
    need({(r['frame'], r['namespace'], r['setting'], r['method']) for r in original['new_outcome_rows']} ==
         {(f, a, 'partial', 'deepgose') for f in FRAMES for a in ASPECTS},
         'all fixed new cohort/aspect profiles are required.')
    comparisons = original['paired_comparisons']
    need(len(comparisons) == 4 and {(r['frame'], r['readout']) for r in comparisons} ==
         {(f, k) for f in FRAMES for k in ('ordinary', 'IA_weighted')}
         and all(r['candidate'] == 'deepgose' and r['comparator'] == 'strict_alias_localplus'
                 for r in comparisons), 'all four predeclared paired comparisons are required.')
    gate = original['predeclared_development_retention_gate']
    need(type(gate['passed']) is bool and gate['passed'] == all(
        r['paired_95_percentile_interval'][0] > 0 for r in comparisons)
        and gate['automatic_product_or_graph_change'] is False
        and gate['independent_confirmatory_gain_claimed'] is False,
        'saved four-CI retention gate differs.')
    max_args = (max_source, max_expected, max_execution, max_execution_expected)
    need(all(x is None for x in max_args) or all(isinstance(x, (str, Path)) and x for x in max_args),
         'supply all four optional MAX aggregate/execution arguments together.')
    appendix = None if max_source is None else max_appendix(
        max_source, max_expected, max_execution, max_execution_expected, original, expected)
    value = deepcopy(original); value.pop('content_sha256')
    for row in value['earlier_240_outcome_rows']:
        if 'source' in row:
            path = row.pop('source')
            need(path in old['native_aggregate_source_files_sha256'],
                 'earlier native curve has no saved FILE binding.')
            row['source_curve_sha256'] = old['native_aggregate_source_files_sha256'][path]
    public = _task_tree(value, sanitize=True); _task_tree(public); public_paths_absent(public)
    need(public['new_outcome_rows'] == original['new_outcome_rows']
         and public['earlier_six_combined_GM_outcome_rows'] == original['earlier_six_combined_GM_outcome_rows']
         and public['paired_comparisons'] == comparisons
         and public['predeclared_development_retention_gate'] == gate,
         'sanitization changed a fixed outcome, interval or rule.')
    prior_rows = public.pop('earlier_240_outcome_rows') + public.pop('earlier_six_combined_GM_outcome_rows')
    baselines = {(r['frame'], r['namespace']): r for r in prior_rows
                 if r['setting'] == 'partial' and r['method'] == 'strict_alias_localplus'}
    need(set(baselines) == {(f, a) for f in FRAMES for a in ASPECTS},
         'complete full-strict Local matched comparator is required.')
    changes = []
    for row in public['new_outcome_rows']:
        baseline = baselines[row['frame'], row['namespace']]
        changes.append({'frame': row['frame'], 'namespace': row['namespace'],
            'comparison': 'DeepGO-SE versus matched full strict Local',
            'eligible_proteins': row['eligible_proteins'],
            'candidate_status': row['status'], 'comparator_status': baseline['status'],
            'point_differences': {k: row[k] - baseline[k] for k in METRICS}
                if row['status'] == baseline['status'] == 'scored' else None,
            'candidate_fixed_0_5': row.get('fixed_0_5'),
            'comparator_fixed_0_5': baseline.get('fixed_0_5')})
    public['matched_profile_metric_changes'] = changes
    public['delivery_boundaries'] = BOUNDARIES
    controls = {'combined_strict_genemaniaplus', 'genemaniaplus', 'localplus', 'strict_alias_localplus',
                'official_nonexperimental', 'official_prott5_cosine3', 'official_naive', 'official_blast', 'fastsinksourceplus'}
    public['prior_BPO_control_rows'] = [r for r in prior_rows if r['namespace'] == 'biological_process'
                                      and r['setting'] == 'partial' and r['method'] in controls]
    inputs = [source, previous_report, old_report] + ([] if appendix is None else [max_source, max_execution])
    out = new_output(output, *inputs)
    prior = sealed({'format': FORMAT + '.public-prior246',
        'earlier_combined_report_file_sha256': sha(previous_report),
        'earlier_combined_report_content_sha256': previous['content_sha256'],
        'earlier_240_report_file_sha256': sha(old_report),
        'earlier_240_report_content_sha256': old['content_sha256'],
        'rows': prior_rows, 'denominators': public['denominators'],
        'outcome_count': 246, 'raw_reference_or_forecast_rows_included': False,
        'operator_paths_included': False})
    write_json(out / 'prior_246_outcomes.json', prior)
    public['earlier_246_inventory'] = {'file_name': 'prior_246_outcomes.json', 'rows': 246,
        'file_sha256': sha(out / 'prior_246_outcomes.json'), 'content_sha256': prior['content_sha256']}
    report_value = {'format': FORMAT + '.public-results', 'created_at': utcnow(),
        'source_report_file_sha256': expected, 'source_report_content_sha256': original['content_sha256'],
        'results': public, 'all_outcome_slots': 252, 'operator_paths_included': False,
        'raw_reference_or_forecast_rows_included': False, 'app_graph_or_default_changed': False,
        'source_sanitizer_implementation_sha256': sha(Path(__import__(
            'biograph_steward.scientific_assessment', fromlist=['x']).__file__)),
        'publisher_implementation_sha256': sha(__file__)}
    if appendix is not None:
        write_json(out / 'max_sensitivity.json', appendix)
        render_max(appendix, out / 'max_sensitivity.html')
        report_value['common_max_sensitivity'] = {'file_name': 'max_sensitivity.json',
            'file_sha256': sha(out / 'max_sensitivity.json'), 'content_sha256': appendix['content_sha256'],
            'html_file_name': 'max_sensitivity.html', 'outcome_slots': 12,
            'separate_from_primary_252_outcomes_and_retention_gate': True}
    report = sealed(report_value)
    _task_tree(report); public_paths_absent(report)
    write_json(out / 'report.json', report); render(report, prior, out / 'report.html')
    summary_value = {'format': FORMAT + '.public-summary',
        'source_public_report_file_sha256': sha(out / 'report.json'),
        'source_public_report_content_sha256': report['content_sha256'],
        **{k: public[k] for k in ('scope', 'new_outcome_rows', 'matched_profile_metric_changes',
            'paired_comparisons', 'predeclared_development_retention_gate', 'earlier_246_inventory',
            'delivery_boundaries', 'caveats')},
        'all_outcome_slots': 252, 'all_new_aspects_macro_IA_Smin_and_fixed_cutoff_retained': True,
        'raw_cases_or_operator_paths_included': False}
    if appendix is not None:
        summary_value['common_max_sensitivity'] = deepcopy(report['common_max_sensitivity'])
    summary = sealed(summary_value)
    write_json(out / 'summary.json', summary)
    manifest = sealed({'format': FORMAT + '.publication-manifest', 'created_at': report['created_at'],
        'source_report_file_sha256': expected, 'report_content_sha256': report['content_sha256'],
        'files': {name: sha(out / name) for name in
                  ('report.json', 'report.html', 'summary.json', 'prior_246_outcomes.json') +
                  (() if appendix is None else ('max_sensitivity.json', 'max_sensitivity.html'))},
        'all_outcome_slots': 252, 'operator_paths_or_raw_cases_included': False,
        'app_graph_or_default_changed': False})
    write_json(out / 'publication_manifest.json', manifest)
    return report


def table(headers, rows):
    def number(value):
        return 'Not returned' if value is None else format(value, '.6f') if type(value) is float else str(value)
    esc = lambda value: escape(str(value), quote=True)
    return '<div class="table"><table><thead><tr>' + ''.join('<th>' + esc(x) + '</th>' for x in headers) + '</tr></thead><tbody>' + ''.join('<tr>' + ''.join('<td>' + esc(number(x)) + '</td>' for x in row) + '</tr>' for row in rows) + '</tbody></table></div>'


def render_max(appendix, path):
    value = appendix['results']; esc = lambda x: escape(str(x), quote=True)
    cohorts = {'primary': 'Original PK', 'reserved': 'Additional PK'}
    methods = {'deepgose_max': 'DeepGO-SE + common MAX', 'strict_alias_localplus_max': 'Full strict Local + common MAX'}
    rows = value['rows']
    html = ['<!doctype html><html lang="en"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>Separate common MAX sensitivity</title><style>body{font:16px system-ui;line-height:1.5;max-width:1500px;margin:2rem auto;padding:0 1rem;color:#203343}table{border-collapse:collapse;font-size:13px;width:100%}th,td{padding:.6rem;border-bottom:1px solid #ccd5df;text-align:left}.table{overflow:auto}.scope{background:#fff1d5;padding:1rem}code{overflow-wrap:anywhere}</style>',
        '<h1>Separate common 2023 MAX sensitivity</h1><p class="scope"><strong>DEVELOPMENT appendix.</strong> This does not replace the CAFA5 fill primary or change its retention decision. Primary four-CI rule: <strong>' +
        ('passed' if appendix['primary_fill_retention_gate_unchanged']['passed'] else 'not passed') + '</strong>, unchanged.</p>',
        '<p>Common official-native MAX closure is applied to both profiles. It follows the frozen raw-mean ensemble and is not a literal reproduction of the DeepGO 2021 paper postprocessing order.</p>',
        '<h2>All 12 saved aspect/cohort/profile outcomes</h2>',
        table(['Cohort', 'Aspect', 'Profile', 'Native status', 'Eligible N', 'Micro Fmax', 'IA micro', 'Macro', 'IA macro', 'Smin', 'IA Smin'],
              [[cohorts[r['frame']], r['namespace'], methods[r['method']], r['status'], r['eligible_proteins'],
                *(r.get(k) for k in METRICS), r.get('unweighted_Smin'), r.get('IA_weighted_Smin')] for r in rows]),
        '<h2>All four separate paired BPO intervals</h2>',
        table(['Cohort', 'Readout', '95% lower', '95% upper', 'Mean difference'],
              [[cohorts[r['frame']], r['readout'], *r['paired_95_percentile_interval'], r['difference_mean']]
               for r in value['paired_comparisons']]),
        '<h2>Fixed-0.5 trade-offs for both profiles</h2><p>Missing native endpoints remain missing; they are not invented zeros.</p>',
        table(['Cohort', 'Aspect', 'Profile', 'PPV', 'Recall', 'F1', 'Native status'],
              [[cohorts[r['frame']], r['namespace'], methods[r['method']],
                *((r.get('fixed_0_5') or {}).get(k) for k in ('PPV', 'recall', 'F1', 'status'))] for r in rows]),
        '<h2>Boundaries</h2><ul>' + ''.join('<li>' + esc(x) + '</li>' for x in appendix['delivery_boundaries']) + '</ul>',
        '<p><a href="report.html">Unchanged fill-primary outcomes and decision</a> · <a href="max_sensitivity.json">Complete 12-cell/four-interval aggregate</a> · <a href="publication_manifest.json">FILE manifest</a></p>',
        '<p>The JSON preserves saved thresholds, count agreement, both uncertainty reports and source/runtime pins. No raw forecasts or reference cases are included.</p>',
        '<p>MAX source FILE SHA256: <code>' + esc(appendix['source_report_file_sha256']) + '</code><br>Execution FILE SHA256: <code>' + esc(appendix['source_execution_file_sha256']) + '</code></p></html>']
    Path(path).write_text(''.join(html))


def render(report, prior, path):
    value = report['results']; esc = lambda x: escape(str(x), quote=True)
    cohorts = {'primary': 'Original PK', 'reserved': 'Additional PK'}
    aspects = {'biological_process': 'Biological process', 'molecular_function': 'Molecular function', 'cellular_component': 'Cellular component'}
    methods = {'deepgose': 'DeepGO-SE', 'combined_strict_genemaniaplus': 'Full GM+ (development)',
        'genemaniaplus': 'Old scoped GM+', 'localplus': 'Old scoped Local+',
        'strict_alias_localplus': 'Full strict Local+', 'official_nonexperimental': 'Nonexperimental annotations',
        'official_prott5_cosine3': 'ProtT5 k=3', 'official_naive': 'Frequency', 'official_blast': 'BLAST',
        'fastsinksourceplus': 'Old FSS+ (prior primary)'}
    def point(row):
        return [cohorts.get(row['frame'], row['frame']), aspects.get(row['namespace'], row['namespace']),
            methods.get(row['method'], row['method']), row.get('setting'), row['status'], row['eligible_proteins'],
            *(row.get(k) for k in METRICS), row.get('unweighted_Smin'), row.get('IA_weighted_Smin')]
    headers = ['Cohort', 'Aspect', 'Method', 'Setting', 'Native status', 'Eligible N',
               'Micro Fmax', 'IA micro', 'Macro', 'IA macro', 'Smin', 'IA Smin']
    new = value['new_outcome_rows']; gate = value['predeclared_development_retention_gate']
    focus = [r for r in new + value['prior_BPO_control_rows'] if r['namespace'] == 'biological_process']
    parts = ['<!doctype html><html lang="en"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>Published DeepGO-SE: development comparison</title><style>body{font:16px system-ui;line-height:1.5;max-width:1500px;margin:2rem auto;padding:0 1rem;color:#203343}table{border-collapse:collapse;font-size:13px;width:100%}th,td{padding:.6rem;border-bottom:1px solid #ccd5df;text-align:left}.table{overflow:auto}details{border:1px solid #ccd5df;padding:1rem;margin:1rem 0}.scope{background:#fff1d5;padding:1rem}code{overflow-wrap:anywhere}</style>',
        '<h1>Published DeepGO-SE on the fixed historical function reference</h1>',
        '<p class="scope"><strong>DEVELOPMENT comparison, not independent whole-graph biological accuracy.</strong> The same 1,294 original and 4,806 additional partial-knowledge proteins were previously evaluated. No live graph, application default or review decision is changed.</p>',
        '<p><strong>Four-interval development retention rule: ' + ('passed' if gate['passed'] else 'not passed') + '.</strong> Both ordinary and IA-weighted biological-process (BPO) paired 95% lower difference bounds must exceed zero versus full strict Local in BOTH cohorts. This is a conditional development decision, not confirmatory validation.</p>',
        '<h2>Primary biological-process comparison</h2><p>DeepGO-SE versus the matched full strict Local profile is the fixed contrast. Earlier native controls and the unsuccessful full GM+ combination remain visible.</p>',
        table(headers, [point(r) for r in focus]),
        '<h2>All six new aspect/cohort outcomes</h2><p>Native eligible counts vary by aspect. Smin is minimized separately; smaller values indicate less semantic error under the fixed benchmark. Missing native endpoints remain missing.</p>',
        table(headers, [point(r) for r in new]),
        '<h2>All-aspect changes against full strict Local</h2>',
        table(['Cohort', 'Aspect', 'Micro difference', 'IA micro difference', 'Macro difference', 'IA macro difference'],
            [[cohorts[r['frame']], aspects[r['namespace']], *(r['point_differences'].get(k) if r['point_differences'] else None for k in METRICS)]
             for r in value['matched_profile_metric_changes']]),
        '<h2>All FOUR fixed paired BPO comparisons</h2>',
        table(['Cohort', 'Readout', '95% lower', '95% upper', 'Mean difference'],
            [[cohorts[r['frame']], r['readout'], *r['paired_95_percentile_interval'], r['difference_mean']]
             for r in value['paired_comparisons']]),
        '<p>Intervals use the same 2,000 shared protein bootstrap draws. Dependencies among proteins and incomplete curator labels remain; these are not independent study replications or multiplicity-adjusted confirmation.</p>',
        '<details open><summary>Fixed-0.5 operating-point trade-offs</summary><p>Not returned means the native evaluator did not supply that value. It does not mean zero precision, zero recall, or no biological support.</p>',
        table(['Cohort', 'Aspect', 'Method', 'PPV', 'Recall', 'F1', 'Native status'],
            [[cohorts[r['frame']], aspects[r['namespace']], method,
              fixed.get('PPV'), fixed.get('recall'), fixed.get('F1'), fixed.get('status')]
             for r in value['matched_profile_metric_changes']
             for method, fixed in (('DeepGO-SE', r['candidate_fixed_0_5'] or {}),
                                   ('Full strict Local', r['comparator_fixed_0_5'] or {}))]), '</details>',
        '<details><summary>Complete earlier 246 outcomes, including negative and unsupported controls</summary>',
        table(headers, [point(r) for r in prior['rows']]), '</details>',
        '<h2>Interpretation and boundaries</h2><ul>',
        ''.join('<li>' + esc(text) + '</li>' for text in value['delivery_boundaries']), '</ul>',
        '<p>Primary sources: <a href="https://doi.org/10.1038/s42256-024-00795-w">DeepGO-SE paper</a>, '
        '<a href="https://doi.org/10.5281/zenodo.10369694">archived author code</a>, '
        '<a href="https://doi.org/10.5281/zenodo.10369249">published model data</a>, '
        '<a href="https://github.com/bio-ontology-research-group/deepgo2/issues/16#issuecomment-6435122743">maintainer CCO correction</a>.</p>',
        '<p><a href="report.json">Complete aggregate report</a> · <a href="summary.json">Compact summary with all six new cells</a> · <a href="prior_246_outcomes.json">All 246 earlier outcomes</a> · <a href="publication_manifest.json">FILE manifest</a></p>',
        '<p>Native thresholds, counts, uncertainty, source/runtime pins and unchanged source caveats remain in the aggregate JSON. No raw reference cases, sequences, identifiers, weights or forecast rows are published.</p>',
        '<p>Source FILE SHA256: <code>' + esc(report['source_report_file_sha256']) + '</code><br>Source content SHA256: <code>' + esc(report['source_report_content_sha256']) + '</code></p></html>']
    if 'common_max_sensitivity' in report:
        parts.insert(-1, '<p class="scope"><a href="max_sensitivity.html">Separate common 2023 MAX sensitivity: all 12 outcomes and four intervals</a>. The CAFA5 fill primary, all 252 primary outcomes and its four-CI decision above remain unchanged.</p>')
    Path(path).write_text(''.join(parts))


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    for key in ('source', 'previous-report', 'old-report', 'expected', 'output'):
        parser.add_argument('--' + key, required=True)
    for key in ('max-source', 'max-expected', 'max-execution', 'max-execution-expected'):
        parser.add_argument('--' + key)
    value = prepare(**vars(parser.parse_args()))
    print(json.dumps({'format': value['format'], 'content_sha256': value['content_sha256']}))
