"""Publish only aggregate readouts from the fixed annotation-prior follow-up.

This renderer never evaluates predictions, selects models or recomputes
intervals. Its input is the completed consumed-reference assessment, not
reference rows, prediction matrices or per-protein contribution files.
"""
import argparse
import hashlib
import html
import json
import math
from pathlib import Path

from .report import LABELS as ORIGINAL_LABELS, NAMESPACES, SETTINGS, VIEWS


CANDIDATE = 'context_plus_T0_annotation_prior'
MATCHED_PRIOR = 'T0_annotation_only_099'
ORIGINAL_PRIOR = 'native_T0_nonexperimental'
ORIGINAL_SELECTED = 'validation_selected_context'
LABELS = {**ORIGINAL_LABELS,
          CANDIDATE: 'Selected stacker + legal T0 annotation prior',
          MATCHED_PRIOR: 'Matched annotation-only prior at author Float32(0.99)'}
ASPECTS = {'molecular_function': 'Molecular function',
           'biological_process': 'Biological process',
           'cellular_component': 'Cellular component'}
FLAGS = {'development_followup_on_consumed_reference': True,
         'independent_confirmation': False,
         'original_primary_comparison_unchanged': True,
         'new_success_gate_or_model_selection': False,
         'graph_pruning_or_app_promotion': False}


def require(condition, message):
    if not condition:
        raise ValueError(message)


def numeric(value, *, nullable=False):
    require((nullable and value is None) or
            (type(value) in (int, float) and math.isfinite(value)),
            'aggregate readout must be a finite number.')
    return value


def pair(value):
    require(isinstance(value, (tuple, list)) and len(value) == 2,
            'stored interval must contain two bounds.')
    result = [numeric(v) for v in value]
    require(result[0] <= result[1], 'stored interval bounds are reversed.')
    return result


def pin(spec):
    """Retain content hashes while excluding private filesystem locations."""
    value = spec.get('sha256')
    require(isinstance(value, str) and len(value) == 64
            and all(c in '0123456789abcdef' for c in value), 'invalid public source hash.')
    return value


def public_method(method):
    status = method.get('status')
    require(status in ('evaluated', 'no_native_coverage'), 'unknown method status.')
    result = {'status': status, 'native_micro_fmax': numeric(method.get('native_micro_fmax'), nullable=True)}
    for field in ('pre_exclusion_GT_proteins', 'eligible_proteins', 'raw_native_reference_proteins'):
        value = method[field]
        require(type(value) is int and value >= 0, 'invalid aggregate protein count.')
        result[field] = value
    agreement = method['native_curve_agreement']
    result['native_full_curve_point_agreement_passed'] = (
        agreement.get('author_point_agreement_passed') is True)
    return result


def public_bootstrap(boot, methods):
    if boot.get('status') == 'unavailable':
        return {'status': 'unavailable'}
    require(boot.get('draws') == 2000 and boot.get('seed') == 20261113
            and boot.get('original_native_gated_draws_reused_without_recomputation') is True
            and boot.get('development_followup_on_consumed_reference') is True
            and boot.get('independent_confirmation') is False,
            'completed follow-up must retain the original paired bootstrap design.')
    require(set(boot['scores']) == set(methods), 'a declared method is missing from the saved bootstrap.')
    comparisons = boot['comparisons']
    expected = set(methods) - {CANDIDATE}
    require(len(comparisons) == len(expected)
            and {row['comparator'] for row in comparisons} == expected
            and all(row.get('candidate') == CANDIDATE for row in comparisons),
            'every saved candidate-versus-control contrast must remain visible.')
    result = {'draws': 2000, 'seed': 20261113, 'raw_proteins': boot['raw_proteins'],
              'original_native_gated_draws_reused_without_recomputation': True,
              'scores': {}, 'comparisons': []}
    require(type(result['raw_proteins']) is int and result['raw_proteins'] >= 0,
            'invalid full bootstrap protein frame.')
    for arm in methods:
        row = boot['scores'][arm]
        result['scores'][arm] = {'bootstrap_mean': numeric(row['bootstrap_mean']),
            'bootstrap_95_percentile_interval': pair(row['bootstrap_95_percentile_interval'])}
    by_arm = {row['comparator']: row for row in comparisons}
    for arm in LABELS:
        if arm not in expected:
            continue
        row = by_arm[arm]
        result['comparisons'].append({'candidate': CANDIDATE, 'comparator': arm,
            'difference_mean': numeric(row['difference_mean']),
            'paired_95_percentile_interval': pair(row['paired_95_percentile_interval']),
            'fraction_draws_above_zero': numeric(row['fraction_draws_above_zero'])})
    return result


def aggregate(raw):
    """Copy all 18 fixed cells and controls through a narrow numeric boundary."""
    require(raw.get('format') == 'biograph-steward.annotation-prior-development-assessment.v1'
            and all(raw.get(key) is value for key, value in FLAGS.items()),
            'only the explicitly consumed-reference development assessment is accepted.')
    require(type(raw['target_count']) is int and raw['target_count'] > 0, 'invalid target count.')
    scopes = raw['arm_aspect_scopes']
    require(set(scopes) == set(LABELS), 'all original controls and both new arms must be retained.')
    require(all(isinstance(value, list) and value and len(value) == len(set(value))
                and set(value) <= set(NAMESPACES) for value in scopes.values()), 'invalid declared aspect scope.')
    require(all(set(scopes[arm]) == set(NAMESPACES) for arm in (CANDIDATE, MATCHED_PRIOR)),
            'both fixed new arms must cover all three aspects.')
    require(set(raw['views']) == set(VIEWS), 'both original ontology views are required.')
    plan_file = Path(__file__).with_name('annotation_prior_protocol.json')
    require(hashlib.sha256(plan_file.read_bytes()).hexdigest() == pin(raw['plan']),
            'the publication plan differs from the source-qualified fixed plan.')
    plan = json.loads(plan_file.read_text())
    require(pin(raw['original_report']) == plan['original_raw_report_sha256'],
            'the original aggregate report differs from the fixed plan.')
    require(raw['original_forecast_seal_sha256'] == plan['original_forecast_seal_sha256'],
            'the original forecast seal differs from the fixed plan.')
    out = {'format': 'biograph-steward.annotation-prior-development-public.v1', **FLAGS,
           'target_count': raw['target_count'],
           'original_report_sha256': pin(raw['original_report']),
           'original_public_summary_sha256': plan['original_public_summary_sha256'],
           'development_plan_sha256': pin(raw['plan']),
           'original_forecast_seal_sha256': pin({'sha256': raw['original_forecast_seal_sha256']}),
           'original_declared_method_count': len(ORIGINAL_LABELS),
           'new_fixed_method_count': 2, 'total_declared_method_count': len(LABELS),
           'arm_aspect_scopes': {arm: list(scopes[arm]) for arm in LABELS}, 'views': {},
           'publication_scope': 'Aggregate points, copied intervals and integration gates only; no cases, identifiers, paths, predictions or sampling draws.',
           'interpretation': 'Post-opening development on a consumed later-snapshot curator-annotation reference; no independent confirmation or new success gate.'}
    expected_cells = {setting + '/' + ns for setting in SETTINGS for ns in NAMESPACES}
    for view in VIEWS:
        source = raw['views'][view]
        require(set(source['cells']) == expected_cells, 'all nine cells per ontology view must be retained.')
        target = {'reference_sha256': {role: pin(spec) for role, spec in source['reference_pins'].items()
                  if role in ('obo', 'toi', 'PK', 'PK_known', 'NK', 'LK')}, 'cells': {}}
        out['views'][view] = target
        for setting in SETTINGS:
            for ns in NAMESPACES:
                key = setting + '/' + ns; cell = source['cells'][key]
                require(cell.get('setting') == setting and cell.get('namespace') == ns
                        and cell.get('status') in ('evaluated', 'reference_absent'), 'cell identity/status differs.')
                item = {'setting': setting, 'namespace': ns, 'status': cell['status'], 'methods': {}}
                target['cells'][key] = item
                if cell['status'] == 'reference_absent':
                    require(not cell['methods'], 'reference-absent cell cannot publish invented readouts.')
                    item['matched_prior_integration_gate'] = {'status': 'unavailable_no_reference'}
                    item['bootstrap'] = {'status': 'unavailable'}
                    continue
                expected_methods = {arm for arm, names in scopes.items() if ns in names}
                require(set(cell['methods']) == expected_methods, 'a scoped method is missing or undeclared.')
                item['methods'] = {arm: public_method(cell['methods'][arm]) for arm in LABELS if arm in expected_methods}
                item['original_method_count'] = len(expected_methods - {CANDIDATE, MATCHED_PRIOR})
                item['new_method_count'] = 2
                gate = cell['matched_prior_integration_gate']
                if gate.get('status') == 'passed':
                    require(gate.get('native_point_exactly_equal') is True
                            and gate.get('all_2000_paired_draw_peaks_exactly_equal') is True
                            and item['methods'][ORIGINAL_PRIOR]['native_micro_fmax'] ==
                                item['methods'][MATCHED_PRIOR]['native_micro_fmax'],
                            'matched-prior integration gate is incomplete.')
                    item['matched_prior_integration_gate'] = {'status': 'passed',
                        'native_point_exactly_equal': True,
                        'all_2000_paired_draw_peaks_exactly_equal': True, 'draw_count': 2000}
                else:
                    require(gate.get('status') == 'unavailable_no_native_prior_coverage'
                            and gate.get('equivalence_claimed') is False, 'unknown or failed matched-prior gate.')
                    item['matched_prior_integration_gate'] = {'status': 'unavailable_no_native_prior_coverage',
                                                            'equivalence_claimed': False}
                item['bootstrap'] = public_bootstrap(cell['bootstrap'], item['methods'])
    return out


def number(value, signed=False):
    return 'unavailable' if value is None else format(value, '+.6f' if signed else '.6f')


def table(headers, rows):
    md = ['| ' + ' | '.join(headers) + ' |', '|' + '|'.join('---' for _ in headers) + '|']
    md += ['| ' + ' | '.join(str(v) for v in row) + ' |' for row in rows]
    document = '<div class="table"><table><thead><tr>' + ''.join('<th>' + html.escape(h) + '</th>' for h in headers) + '</tr></thead><tbody>'
    document += ''.join('<tr>' + ''.join('<td>' + html.escape(str(value)) + '</td>' for value in row) + '</tr>' for row in rows)
    return md, document + '</tbody></table></div>'


def render(results, destination):
    source = Path(results); result = aggregate(json.loads(source.read_text()))
    result['source_aggregate_sha256'] = hashlib.sha256(source.read_bytes()).hexdigest()
    dest = Path(destination); dest.mkdir(parents=True, exist_ok=False)
    md = ['# Annotation-prior development follow-up', '',
          '**DEVELOPMENT — reference already consumed; no independent confirmation.**', '',
          'One fixed published operation combines the previously selected stacker with the complete legal T0 nonexperimental annotation prior. '
          'This report preserves all 18 cells, every original method and every saved contrast, including losses. '
          'The original frozen study and its success gates remain unchanged.', '']
    body = ['<h1>Annotation-prior development follow-up</h1>',
            '<p class="banner"><strong>DEVELOPMENT — reference already consumed; no independent confirmation.</strong></p>',
            '<p>' + html.escape(md[-2]) + '</p>',
            '<nav><a href="#overview">PK overview</a> · <a href="#all-cells">All 18 cells</a> · <a href="#method">Method and limits</a> · <a href="summary.json">Aggregate JSON</a> · <a href="report.md">Markdown</a></nav>']
    md += ['## PK overview', '', 'These are descriptive readouts from the existing PK endpoint, not newly selected endpoints or new success gates. '
           'Every NK/LK readout remains in the complete tables below.', '']
    body += ['<h2 id="overview">PK overview</h2>', '<p>' + html.escape(md[-2]) + '</p>']
    rows = []
    for view in VIEWS:
        for ns in NAMESPACES:
            cell = result['views'][view]['cells']['PK/' + ns]
            methods = cell['methods']
            points = [number(methods.get(a, {}).get('native_micro_fmax'))
                      for a in (ORIGINAL_SELECTED, CANDIDATE, ORIGINAL_PRIOR, MATCHED_PRIOR)]
            gate = cell['matched_prior_integration_gate']['status']
            rows.append([view, ASPECTS[ns], *points, gate])
    lines, markup = table(['View', 'Aspect', 'Original selected', 'Selected + prior', 'Original prior', 'Matched prior 0.99', 'Prior parity'], rows)
    md += lines + ['']; body.append(markup)
    explanation = ('Fmax is optimized over the unchanged .001–.999 evaluator grid; 0.99 is an author-defined annotation score, not calibrated confidence. '
        'Intervals use the same 2,000 paired whole-protein draws as the original study and remain conditional, unadjusted development descriptions. '
        'Compare methods within each view; the two views have different reference populations. No model, threshold or new success gate is selected here.')
    md += [explanation, '', '## All 18 cells', '']; body += ['<p>' + html.escape(explanation) + '</p>', '<h2 id="all-cells">All 18 cells</h2>']
    for view in VIEWS:
        for setting in SETTINGS:
            for ns in NAMESPACES:
                cell = result['views'][view]['cells'][setting + '/' + ns]
                title = view + ' · ' + setting + ' · ' + ASPECTS[ns]
                md += ['### ' + title, '']; body.append('<details><summary>' + html.escape(title) + '</summary>')
                if cell['status'] == 'reference_absent':
                    md += ['No native reference; no score or equivalence claim.', '']
                    body += ['<p>No native reference; no score or equivalence claim.</p></details>']; continue
                raw_frame = cell['bootstrap'].get('raw_proteins', 'unavailable')
                residual = cell['methods'][CANDIDATE]['eligible_proteins']
                text = f'Full native/bootstrap protein frame: {raw_frame}; proteins with residual positive labels: {residual}. Matched-prior parity: ' + cell['matched_prior_integration_gate']['status'] + '.'
                md += [text, '']; body.append('<p>' + html.escape(text) + '</p>')
                rows = [[LABELS[arm], number(value['native_micro_fmax']), value['raw_native_reference_proteins'], value['eligible_proteins']]
                        for arm, value in cell['methods'].items()]
                lines, markup = table(['Method', 'Ordinary micro-Fmax', 'Raw protein rows', 'Residual-positive proteins'], rows)
                md += lines + ['']; body.append(markup)
                boot = cell['bootstrap']
                if boot.get('status') == 'unavailable':
                    md += ['Paired intervals unavailable; no interval claim.', '']; body.append('<p>Paired intervals unavailable; no interval claim.</p>')
                else:
                    rows = []
                    for contrast in boot['comparisons']:
                        comparator = contrast['comparator']
                        left = cell['methods'][CANDIDATE]['native_micro_fmax']
                        right = cell['methods'][comparator]['native_micro_fmax']
                        lo, hi = contrast['paired_95_percentile_interval']
                        rows.append([LABELS[comparator], number(left - right, True),
                                     '[' + number(lo, True) + ', ' + number(hi, True) + ']'])
                    lines, markup = table(['Selected + prior versus control', 'Observed Fmax difference', 'Copied paired 95% interval'], rows)
                    md += lines + ['']; body.append(markup)
                body.append('</details>')
    notes = [
        'The author’s final CAFA6 operation concatenates predictions and annotation rows scored as Float32(0.99), then takes MAX for each literal target/term key. '
        'Here only the original sealed strict T0 nonexperimental prior replaces the author’s competition-known-label input. This is an explicit input adaptation, not reproduction of the full CAFA6 pipeline.',
        'All 3,300 target rows and the complete literal union of model and prior heads are preserved. The merge follows the already completed soft processing. '
        'Only the unchanged evaluator canonicalization and upward fill follow; no additional MIN/soft pass, fitting, retrieval or outcome-based routing was introduced.',
        'The matched annotation-only 0.99 arm uses the same union axis with an exactly zero model. Each available native Fmax point and all 2,000 paired-draw peaks must exactly match the original score-1 annotation prior. '
        'Complete threshold curves need not be identical above 0.99. This gate checks integration, not biological superiority.',
        'Every original method remains visible. The saved intervals compare the merged candidate with every available original method and the matched prior. '
        'The matched prior is an algebraic integration control; no additional pairwise intervals were invented for it.',
        'PK means partial knowledge: the unchanged native evaluator excludes T0-known functions. NK and LK retain their original no/limited-knowledge definitions. '
        'MF, BP and CC describe molecular function, biological process and cellular component. Native and fixed-T0 denote different ontology/reference views.',
        'The reference measures recovery of later-snapshot curated annotations. It does not establish first public knowledge, publication dates, independent experiments or a percentage of biologically correct Pharos edges. '
        'Annotations are incomplete; an unmatched prediction is not established false.',
        'This follow-up was chosen after the reference was opened. Even a favorable development interval requires independent confirmation on an untouched reference. '
        'There is no new success gate, model selection, automatic graph pruning, application-default change or clinical claim.'
    ]
    md += ['## Method and limits', '']; body.append('<h2 id="method">Method and limits</h2>')
    for note in notes:
        md += ['- ' + note, '']; body.append('<p>' + html.escape(note) + '</p>')
    md += ['Source: [pinned CAFA6 author operation](https://github.com/btbpanda/CAFA6-updates/blob/0ee85d2f07f724be1721ea39211f1b364535f976/model_scripts/postproc_and_sub.py).', '']
    body.append('<p><a href="https://github.com/btbpanda/CAFA6-updates/blob/0ee85d2f07f724be1721ea39211f1b364535f976/model_scripts/postproc_and_sub.py">Pinned CAFA6 author operation</a></p>')
    (dest / 'summary.json').write_text(json.dumps(result, indent=2, sort_keys=True) + '\n')
    (dest / 'report.md').write_text('\n'.join(md))
    document = ('<!doctype html><html lang="en"><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">'
        '<title>Annotation-prior development follow-up</title><style>body{max-width:1200px;margin:36px auto;padding:0 24px;background:#f8fafb;color:#203544;font:15px/1.6 system-ui}'
        'h1{line-height:1.2}.banner{background:#fff1c9;border-left:5px solid #aa6e00;padding:16px}nav{margin:20px 0}.table{overflow:auto}'
        'table{border-collapse:collapse;width:100%;font-size:12px}th,td{padding:8px 10px;text-align:right;border-bottom:1px solid #d5e0e5}'
        'th{background:#e8f0f4}td:first-child,th:first-child{text-align:left}details{background:white;border:1px solid #d5e0e5;border-radius:6px;padding:12px 16px;margin:12px 0}'
        'summary{cursor:pointer;font-weight:650}a{color:#145e7a}h2{margin-top:32px}@media print{details{display:block}table{font-size:9px}body{max-width:none;margin:0}}</style>'
        + ''.join(body) + '</html>')
    (dest / 'report.html').write_text(document)
    digest = lambda p: hashlib.sha256(Path(p).read_bytes()).hexdigest()
    manifest = {'format': 'biograph-steward.annotation-prior-publication.v1',
                'source_aggregate_sha256': digest(source), 'renderer_source_sha256': digest(__file__),
                'evaluation_scores_intervals_or_model_choices_recomputed': False,
                'consumed_reference_development_only': True, 'raw_cases_draws_or_paths_published': False,
                'original_report_sha256': result['original_report_sha256'],
                'files': {name: {'sha256': digest(dest / name), 'bytes': (dest / name).stat().st_size}
                          for name in ('summary.json', 'report.html', 'report.md')}}
    (dest / 'publication_manifest.json').write_text(json.dumps(manifest, indent=2, sort_keys=True) + '\n')
    return result


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--results', required=True); parser.add_argument('--destination', required=True)
    args = parser.parse_args(); render(args.results, args.destination)
