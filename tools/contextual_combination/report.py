"""Render an aggregate-only view of the completed fixed comparison.

This presentation adapter computes no evaluation scores, intervals or model
choices. Case ledgers, protein identities and per-protein arrays stay private.
"""
import argparse
import html
import json
from pathlib import Path
import re


VIEWS = ('native', 'fixed_T0')
PRIMARY = 'PK/biological_process'
CANDIDATE = 'validation_selected_context'
LABELS = {
    'localplus': 'LocalPlus — retained annotations',
    'deepgose': 'DeepGO-SE — sequence model',
    'localplus_soft': 'LocalPlus — same soft processing',
    'deepgose_soft': 'DeepGO-SE — same soft processing',
    'equal_mix': 'Fixed 50/50 combination',
    'development_alpha_mix': 'Development-selected global weight',
    'localplus_model_axis_raw': 'LocalPlus — historical model axis',
    'deepgose_model_axis_raw': 'DeepGO-SE — historical model axis',
    'native_T0_nonexperimental': 'Current nonexperimental annotations',
    'context_mlp': 'Context stacker — zero-layer MLP',
    'context_gcn': 'Context stacker — eight-layer GCN',
    'coded_context_gcn': 'Context GCN — evidence/relation features',
    'localplus_updated_seeds': 'LocalPlus — matched training-label update',
    'localplus_updated_seeds_soft': 'Updated LocalPlus — same soft processing',
    'fit_label_frequency': 'Training-label frequency only',
    'localplus_T0_curated': 'LocalPlus — complete current-T0 curated seeds',
    CANDIDATE: 'Development-selected context stacker',
}
NAMESPACES = ('molecular_function', 'biological_process', 'cellular_component')
SETTINGS = ('PK', 'NK', 'LK')
GATES = (
    ('primary_success_over_literal_LocalPlus_both_views', 'Selected stacker beyond retained LocalPlus'),
    ('primary_success_over_raw_and_soft_LocalPlus_both_views', 'Selected stacker beyond raw and soft retained LocalPlus'),
    ('primary_success_over_nonexperimental_context_both_views', 'Selected stacker beyond current nonexperimental annotations'),
    ('primary_success_beyond_raw_and_soft_seed_refresh_both_views', 'Selected stacker beyond matched training-label updates'),
    ('primary_success_beyond_current_T0_curated_LocalPlus_both_views', 'Selected stacker beyond complete current-T0 curated LocalPlus'),
    ('primary_success_over_all_noncontext_controls_both_views', 'Selected stacker beyond every declared noncontext control'),
)
SOURCE_GATES = (
    ('updated_seed_LocalPlus_gain_raw_and_soft_both_views', 'Matched training-label update beyond retained LocalPlus, raw and soft'),
    ('current_T0_LocalPlus_gain_both_views', 'Complete current-T0 annotation update beyond retained LocalPlus'),
)
SLICES = ('cached-compatible', 'fresh-inference', 'historical-graph-covered', 'historical-graph-absent',
          'sequence-over1022', 'sequence-upTo1022', 'localplus-any-positive-source-score',
          'localplus-all-zero-source-score')


def picked(mapping, keys):
    """Explicit scalar publication boundary; new nested fields are not public."""
    return {key: mapping[key] for key in keys if key in mapping
            and (mapping[key] is None or isinstance(mapping[key], (str, bool, int, float)))}


def interval(mapping, key):
    value = mapping.get(key)
    return ({key: list(value)} if isinstance(value, (list, tuple)) and len(value) == 2
            and all(type(v) in (int, float) for v in value) else {})


def protocol_public(value, template):
    """Retain only the declared public protocol structure, never new fields."""
    if isinstance(template, dict):
        return {k: protocol_public(value[k], v) for k, v in template.items()
                if isinstance(value, dict) and k in value}
    if isinstance(template, list):
        return [v for v in value if v is None or isinstance(v, (str, bool, int, float))] if isinstance(value, list) else []
    return value if value is None or isinstance(value, (str, bool, int, float)) else None


def method_public(method):
    result = picked(method, ('native_micro_fmax', 'status', 'pre_exclusion_GT_proteins',
                     'eligible_proteins', 'raw_native_reference_proteins'))
    if 'forecast_projection' in method:
        result['forecast_projection'] = picked(method['forecast_projection'], (
            'source_heads', 'mapped_heads', 'dropped_heads', 'duplicate_policy', 'propagation',
            'upper_roundoff_tolerance', 'probability_clipping'))
    if 'native_curve_agreement' in method:
        native = method['native_curve_agreement']
        result['native_curve_agreement'] = picked(native, ('status', 'author_point_agreement_passed',
            'namespace', 'raw_protein_rows', 'post_exclusion_GT_proteins', 'thresholds',
            'ordinary_only', 'IA_supplied', 'max_absolute_curve_difference', 'absolute_tolerance',
            'pre_exclusion_native_row_admission_preserved'))
        if 'columns' in native:
            result['native_curve_agreement']['columns'] = picked(native['columns'], (
                'n', 'tp', 'fp', 'fn', 'pr', 'rc', 'cov', 'mi', 'ru', 'f', 's',
                'pr_micro', 'rc_micro', 'f_micro'))
    return result


def bootstrap_public(boot):
    result = picked(boot, ('status', 'reason', 'draws', 'seed', 'raw_proteins',
        'ordinary_only', 'IA_supplied', 'shared_protein_samples_across_all_arms', 'required_prior_gate'))
    if 'candidate_name_adapter' in boot:
        result['candidate_name_adapter'] = picked(boot['candidate_name_adapter'], ('learned_mix',))
    if 'scores' in boot:
        result['scores'] = {arm: {**picked(row, ('bootstrap_mean',)),
                                 **interval(row, 'bootstrap_95_percentile_interval')}
                            for arm, row in boot['scores'].items() if arm in LABELS}
    if 'comparisons' in boot:
        result['comparisons'] = [{**picked(row, ('candidate', 'comparator', 'difference_mean',
            'fraction_draws_above_zero', 'interpretation')), **interval(row, 'paired_95_percentile_interval')}
            for row in boot['comparisons'] if row.get('candidate') in LABELS
            and row.get('comparator') in LABELS]
    return result


def slice_public(slices):
    result = {}
    for name, row in slices.items():
        if name not in SLICES:
            continue
        result[name] = picked(row, ('definition', 'full_source_slice_proteins',
            'raw_native_reference_proteins', 'readout', 'deployed_threshold_or_model_selection',
            'evaluation_threshold_optimization'))
        result[name]['methods'] = {arm: picked(method, ('eligible_proteins', 'derived_micro_fmax',
            'positive_forecast_coverage_on_grid')) for arm, method in row.get('methods', {}).items()
            if arm in LABELS}
    return result


def number(value):
    return 'unavailable' if value is None else f'{value:.6f}'


def inline(text):
    """Display the report's own small Markdown subset after HTML escaping."""
    text = html.escape(text)
    text = re.sub(r'\[([^\]]+)\]\((https://[^\s)]+)\)', r'<a href="\2">\1</a>', text)
    text = re.sub(r'\*\*([^*]+)\*\*', r'<strong>\1</strong>', text)
    return re.sub(r'`([^`]+)`', r'<code>\1</code>', text)


def aggregate(result):
    """Whitelist readouts, without copying reference rows or sampling arrays."""
    from .protocol import PROTOCOL
    out = picked(result, ('created_at', 'forecast_seal_sha256', 'target_count',
                 'automatic_graph_or_app_promotion', 'reference_interpretation',
                 *(key for key, _ in GATES + SOURCE_GATES)))
    out['protocol'] = protocol_public(result.get('protocol', {}), PROTOCOL)
    out['arm_aspect_scopes'] = {arm: [ns for ns in namespaces if ns in NAMESPACES]
        for arm, namespaces in result['arm_aspect_scopes'].items() if arm in LABELS}
    out['model_choices'] = {ns: {'selected_arm': (row['selected_arm'] if row['selected_arm'] in
        ('context_mlp', 'context_gcn', 'coded_context_gcn') else 'unavailable'),
        'validation_scores': row['validation_scores']}
        for ns, row in result['model_choices']['selections'].items() if ns in NAMESPACES}
    for row in out['model_choices'].values():
        row['validation_scores'] = picked(row['validation_scores'],
            ('context_mlp', 'context_gcn', 'coded_context_gcn'))
    out['views'] = {}
    for view in VIEWS:
        row = result.get('views', {}).get(view, {})
        target = {'reference_sha256': {role: spec['sha256']
                  for role, spec in row.get('reference_pins', {}).items()
                  if role in ('obo', 'toi', 'PK', 'PK_known', 'NK', 'LK')}, 'cells': {}}
        for setting, namespace in ((s, ns) for s in SETTINGS for ns in NAMESPACES):
            key = setting + '/' + namespace
            cell = row.get('cells', {}).get(key, {'setting': setting, 'namespace': namespace,
                                                 'status': 'missing_result', 'methods': {}})
            item = picked(cell, ('setting', 'namespace', 'status', 'reason'))
            item['methods'] = {arm: method_public(method) for arm, method in cell.get('methods', {}).items()
                               if arm in LABELS}
            if 'source_slice_points' in cell:
                item['source_slice_points'] = slice_public(cell['source_slice_points'])
            if 'positive_reference_score_ledger' in cell:
                ledger = cell['positive_reference_score_ledger']
                item['reference_positive_pair_count'] = ledger['reference_positive_pairs']
                item['private_score_ledger_sha256'] = ledger['sha256']
            for name, boot in cell.items():
                if not (name == 'bootstrap' or name.endswith('_bootstrap')):
                    continue
                if name in ('bootstrap', 'GCN_MLP_bootstrap', 'updated_seed_bootstrap',
                            'updated_seed_soft_bootstrap', 'current_T0_curated_bootstrap'):
                    item[name] = bootstrap_public(boot)
            target['cells'][key] = item
        out['views'][view] = target
    out['publication_scope'] = ('Aggregate comparison only; no reference protein/term rows, '
        'per-protein counts, prediction matrices or private case ledgers are included.')
    return out


def contrast_rows(cell, bootstrap='bootstrap'):
    rows = []
    for item in cell.get(bootstrap, {}).get('comparisons', []):
        a, b = item['candidate'], item['comparator']
        left = cell['methods'].get(a, {}).get('native_micro_fmax')
        right = cell['methods'].get(b, {}).get('native_micro_fmax')
        bounds = item.get('paired_95_percentile_interval')
        if left is None or right is None or bounds is None:
            continue
        lo, hi = bounds
        rows.append([LABELS.get(a, a), LABELS.get(b, b), f'{left-right:+.6f}',
                     f'[{lo:+.6f}, {hi:+.6f}]'])
    return rows


def gate_text(result, key):
    """Display an already evaluated gate; never infer it from points/intervals."""
    value = result.get(key)
    return 'Passed' if value is True else 'Not established' if value is False else 'Unavailable'


def cell_status(cell):
    status = cell.get('status', 'missing_result')
    return {'reference_absent': 'No native reference', 'missing_result': 'Result unavailable',
            'evaluated': 'Evaluated'}.get(status, status)


def render(results, destination):
    result = aggregate(json.loads(Path(results).read_text()))
    dest = Path(destination)
    dest.mkdir(parents=True, exist_ok=False)
    (dest / 'summary.json').write_text(json.dumps(result, indent=2, sort_keys=True) + '\n')
    success = result.get('primary_success_over_literal_LocalPlus_both_views')
    verdict = ('The preselected context stacker establishes a bounded gain over retained LocalPlus in both reference views.'
               if success is True else 'The preselected context stacker does not establish a gain over retained LocalPlus in both reference views.'
               if success is False else 'The primary retained-LocalPlus gain gate is unavailable in this result.')
    current_success = result.get('primary_success_beyond_current_T0_curated_LocalPlus_both_views')
    beyond = ('The fixed comparison beyond LocalPlus using complete current-T0 curated annotations passes.'
              if current_success is True else 'An advantage beyond LocalPlus using complete current-T0 curated annotations is not established by the fixed gate.'
              if current_success is False else 'The comparison gate beyond complete current-T0 curated LocalPlus is unavailable.')
    lines = ['# Context-aware combination: later curator-annotation recovery', '',
        '**' + verdict + '** ' + beyond, '',
        'This is a bounded human GO function-recovery measurement. It is not a percentage of biologically correct Pharos edges, '
        'a clinical assessment, or evidence that unmatched predictions are false.', '',
        '## Fixed comparison', '',
        'All **3,300** native target identities were forecast before the new reference was opened. '
        'The primary endpoint is **PK biological-process ordinary micro-Fmax**. '
        'PK excludes functions already known at T0. All other settings/aspects remain secondary. '
        'Native epoch-specific and fixed-T0 ontology views are both required by the gain gate.', '',
        '| Forecast | Native primary Fmax | Fixed-T0 primary Fmax |', '|---|---:|---:|']
    arms = list(result['arm_aspect_scopes'])
    for arm in arms:
        points = [number(result['views'][v]['cells'][PRIMARY]['methods'].get(arm, {}).get('native_micro_fmax'))
                  for v in VIEWS]
        lines.append('| ' + LABELS.get(arm, arm) + ' | ' + ' | '.join(points) + ' |')
    lines += ['', 'Fmax is threshold-optimized by the fixed evaluator grid; it is not a deployed confidence threshold. '
        'Intervals below use 2,000 paired whole-protein resamples with shared draws and seed 20261113. '
        'They are conditional, unadjusted descriptive intervals. The point difference and lower interval must both be positive '
        'in both views to pass a declared gate.', '', '## Declared gain gates', '',
        'These statuses copy the completed assessment. The primary question is the selected stacker versus retained LocalPlus. '
        'The stricter controls describe what explains that gain; they do not replace a failed primary gate.', '',
        '| Selected-stacker comparison, required in both views | Stored gate |', '|---|---|']
    lines += ['| ' + label + ' | ' + gate_text(result, key) + ' |' for key, label in GATES]
    lines += ['', '### Separate source-update results', '',
        'These gates compare the same native LocalPlus algorithm with different legal source annotations. '
        'A passed source-update gate supports the value of newer annotations; it does not establish a learned-stacker gain.', '',
        '| Fixed source update, required in both views | Stored gate |', '|---|---|']
    lines += ['| ' + label + ' | ' + gate_text(result, key) + ' |' for key, label in SOURCE_GATES]
    lines += ['', '## What changed in the inputs', '',
        'The native ProtBoost stacker combines saved graph and sequence forecasts with existing nonexperimental GOA context. '
        'One additional BPO GCN uses source-derived evidence-code/relation channels from the author’s CAFA6 update. '
        'Its 40 namespaced channels are views of the same GOA source, not 40 independent resources or studies. '
        'Every candidate, checkpoint recipe and feature contract was fixed before new-reference access.', '',
        'The retained LocalPlus seeds are historical. The matched update adds exactly the allowed full fitting repertoire '
        'for 4,040 training proteins, using the same graph and native scorer. A separate practical current-T0 arm replaces '
        'the historical seeds with all eligible reviewed-human curated April 10 annotations. '
        'That arm is evaluated only on this later window; using it on the older validation would look ahead. '
        'The frequency-only arm tests whether prevalence explains a learned gain.', '',
        '## Development choices', '',
        '| Aspect | Selected arm | Consumed-validation scores |', '|---|---|---|']
    for ns, row in result['model_choices'].items():
        scores = '; '.join(f'{a}: {s:.6f}' for a, s in row['validation_scores'].items())
        lines.append(f"| {ns} | {row['selected_arm']} | {scores} |")
    for view in VIEWS:
        cell = result['views'][view]['cells'][PRIMARY]
        lines += ['', '## ' + view + ' primary paired contrasts', '',
            '| Candidate | Comparator | Fmax difference | Paired 95% interval |', '|---|---|---:|---:|']
        rows = contrast_rows(cell)
        lines += ['| ' + ' | '.join(row) + ' |' for row in rows]
        if not rows:
            lines += ['', 'Paired contrasts unavailable: ' + cell.get('bootstrap', {}).get('reason', cell_status(cell)) + '.']
        lines += ['', '### Fixed source-update contrasts', '',
            '| Candidate | Comparator | Fmax difference | Paired 95% interval |', '|---|---|---:|---:|']
        for key in ('updated_seed_bootstrap', 'updated_seed_soft_bootstrap', 'current_T0_curated_bootstrap'):
            lines += ['| ' + ' | '.join(row) + ' |' for row in contrast_rows(cell, key)]
    lines += ['', '## Complete settings and aspects', '',
        'MF = molecular activity; BP = biological process; CC = cellular location/structure. '
        'NK and LK are the native no-knowledge and limited-knowledge settings. '
        'Unavailable cells and absent coverage are retained explicitly. Full controls and source slices are in summary.json.', '',
        '| View / setting / aspect | Cell status | Residual reference proteins | Selected stacker | Retained LocalPlus | Current-T0 LocalPlus |',
        '|---|---|---:|---:|---:|---:|']
    for view in VIEWS:
        for key, cell in result['views'][view]['cells'].items():
            methods = cell['methods']
            count = methods.get(CANDIDATE, {}).get('eligible_proteins', 'unavailable')
            points = [number(methods.get(a, {}).get('native_micro_fmax'))
                      for a in (CANDIDATE, 'localplus', 'localplus_T0_curated')]
            lines.append('| ' + view + '/' + key + ' | ' + cell_status(cell) + ' | ' + str(count) + ' | ' + ' | '.join(points) + ' |')
    lines += ['', '## Scope and limits', '',
        'The snapshots are April 10–November 4, 2026 human GOA. The corresponding available GO-basic content dates are '
        'March 25 and July 26. The fixed-T0 sensitivity holds the ontology fixed and uses the same primary term mask. '
        'It is not a purified set of newly performed experiments. Native admission includes eleven experimental codes '
        'plus curator inference (IC) and traceable author statements (TAS). Source provenance is assessed separately.', '',
        'The study is retrospective and not wholly developer-blind. Fit, validation and final accessions, identical full '
        'sequences and identical first-1,022-residue sequence inputs were separated. Near-homology, base-checkpoint training '
        'and publication independence are not established. Proteins can share studies, families and graph neighborhoods. '
        'The author’s original stacker used out-of-fold parent forecasts; this is an explicitly qualified temporal adaptation. '
        'GCN versus MLP also changes depth/capacity, so it does not isolate a causal benefit from GO topology.', '',
        'These results do not replace the separate same-learner enriched-graph link-prediction comparisons. '
        'No graph, pruning rule or app default is automatically promoted. Failed controls and all declared cells remain retained.', '',
        '## Reused methods', '',
        '- [ProtBoost paper](https://arxiv.org/abs/2412.04529) and '
        '[pinned official implementation](https://github.com/btbpanda/CAFA5-protein-function-prediction-2nd-place/tree/52dce6c471337f2820550f779a6a1bb201353b2a).',
        '- [Official CAFA6 source update](https://github.com/btbpanda/CAFA6-updates/tree/0ee85d2f07f724be1721ea39211f1b364535f976).',
        '- [LAFA source](https://github.com/FriedbergLab/CAFA_forever/tree/c3fd5b9a5226348d88b9efadddb3214c803b80c4) and '
        '[democafa reference builder](https://github.com/FriedbergLab/democafa_package/tree/0ab84edbaddf5fef11125dc8adbd19167c3cc038).',
        '- [Pinned native evaluator](https://github.com/claradepaolis/CAFA-evaluator-PK/tree/e386b085e204ccfbd75a4f52c1a8b25987d8b465).',
        '- [CAFA4 assessment preprint, June 2026 revision](https://pmc.ncbi.nlm.nih.gov/articles/PMC13174626/): '
        'its historical-baseline comparisons distinguish annotation-data growth from methodological progress.', '']
    (dest / 'report.md').write_text('\n'.join(lines))
    # Reuse Markdown's simple paragraph/table structure without a runtime or CDN.
    body, table, paragraph, listing = [], [], [], []
    def flush_paragraph():
        if paragraph:
            body.append('<p>' + inline(' '.join(paragraph)) + '</p>'); paragraph.clear()
    def flush_table():
        if not table:
            return
        rows = [[v.strip() for v in row.strip('|').split('|')] for row in table]
        body.append('<div class="table"><table><thead><tr>' + ''.join('<th>' + html.escape(v) + '</th>' for v in rows[0]) + '</tr></thead><tbody>')
        for row in rows[2:]:
            body.append('<tr>' + ''.join('<td>' + html.escape(v) + '</td>' for v in row) + '</tr>')
        body.append('</tbody></table></div>'); table.clear()
    def flush_list():
        if listing:
            body.append('<ul>' + ''.join('<li>' + inline(v) + '</li>' for v in listing) + '</ul>')
            listing.clear()
    for line in lines:
        if line.startswith('|'):
            flush_paragraph(); flush_list(); table.append(line); continue
        flush_table()
        if line.startswith('- '):
            flush_paragraph(); listing.append(line[2:]); continue
        flush_list()
        if line.startswith('#'):
            flush_paragraph(); level = len(line) - len(line.lstrip('#'))
            body.append(f'<h{level}>' + html.escape(line[level:].strip()) + f'</h{level}>')
        elif not line:
            flush_paragraph()
        else:
            paragraph.append(line)
    flush_table(); flush_paragraph(); flush_list()
    document = ('<!doctype html><html lang="en"><meta charset="utf-8">'
        '<meta name="viewport" content="width=device-width, initial-scale=1">'
        '<title>Context-aware combination — fixed comparison</title>'
        '<style>body{max-width:1100px;margin:36px auto;padding:0 24px;background:#f9fbfc;color:#1b3340;'
        'font:15px/1.6 system-ui}h1{line-height:1.2}h2{margin-top:36px}.table{overflow:auto}'
        'table{border-collapse:collapse;width:100%;font-size:13px}th,td{padding:9px 11px;'
        'text-align:right;border-bottom:1px solid #d6e0e5}th{background:#e9f1f4}'
        'td:first-child,th:first-child{text-align:left}tr:hover{background:#eef5f7}'
        'a{color:#145e7a}body>p:first-of-type{background:#e6f1f5;padding:18px}'
        '@media print{body{margin:0;max-width:none}table{font-size:10px}}</style>'
        '<p><a href="summary.json">Aggregate JSON</a> · <a href="report.md">Full Markdown report</a></p>'
        + ''.join(body) + '</html>')
    (dest / 'report.html').write_text(document)
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--results', required=True)
    parser.add_argument('--destination', required=True)
    args = parser.parse_args()
    render(args.results, args.destination)


if __name__ == '__main__':
    main()
