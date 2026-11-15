"""Aggregate-only PK/BPO forests; no fitting, source cases or new statistics.

Reuses the established learned_combination figure's validation helpers and
Matplotlib convention: observed point differences and saved paired intervals,
drawn directly because intervals need not center on the observed difference.
All predeclared non-context controls are retained in protocol order.
"""
import argparse
import json
from pathlib import Path
import platform

from tools.learned_combination.plot_results import finite, need, sha
from .protocol import PROTOCOL


CANDIDATE = 'validation_selected_context'
CONTEXT_ARMS = ('context_mlp', 'context_gcn', 'coded_context_gcn')
VIEWS = (('native', 'Native ontology'), ('fixed_T0', 'Fixed-T0 sensitivity'))
CELL = 'PK/biological_process'
LABELS = {
    'localplus': 'LocalPlus: retained seeds', 'deepgose': 'DeepGO-SE',
    'localplus_soft': 'LocalPlus: matched soft', 'deepgose_soft': 'DeepGO-SE: matched soft',
    'equal_mix': 'Equal mix (50/50)', 'development_alpha_mix': 'Development-weighted mix',
    'localplus_model_axis_raw': 'LocalPlus: fixed model axis',
    'deepgose_model_axis_raw': 'DeepGO-SE: fixed model axis',
    'native_T0_nonexperimental': 'T0 nonexperimental GOA',
    'localplus_updated_seeds': 'LocalPlus: updated fit labels',
    'localplus_updated_seeds_soft': 'Updated fit labels + soft',
    'fit_label_frequency': 'Fit-label frequency',
    'localplus_T0_curated': 'LocalPlus: all T0 curated',
}
MODEL_LABELS = {'context_mlp': 'same-input MLP', 'context_gcn': 'one-context GCN',
                'coded_context_gcn': '40-context GCN'}
UPDATES = (
    ('updated_seed_bootstrap', 'localplus_updated_seeds', 'localplus', 'Updated fit labels: raw'),
    ('updated_seed_soft_bootstrap', 'localplus_updated_seeds_soft', 'localplus_soft', 'Updated fit labels: soft'),
    ('current_T0_curated_bootstrap', 'localplus_T0_curated', 'localplus', 'Complete T0 curated: raw'),
)


def controls(protocol):
    result = tuple(name for name in protocol['evaluation']['controls'] if name not in CONTEXT_ARMS)
    need(result and len(result) == len(set(result)), 'complete unique declared non-context controls required.')
    return result


def checked_cell(report, view):
    need(report['protocol'] == PROTOCOL, 'aggregate protocol differs from the source-frozen comparison.')
    need(report.get('fresh_final_reference_opened_at_model_choice') is False,
         'model choice must precede final-reference opening.')
    cell = report['views'][view]['cells'][CELL]
    need(cell['status'] == 'evaluated', 'complete evaluated PK/BPO cell required: ' + view)
    expected = set(controls(report['protocol']))
    methods = cell['methods']
    need({name for name in methods if name not in (*CONTEXT_ARMS, CANDIDATE)} == expected,
         'every declared non-context control, and no unregistered control, must be displayed.')
    selected = report['model_choices']['biological_process']['selected_arm']
    need(selected in CONTEXT_ARMS and selected in methods
         and methods[selected]['native_micro_fmax'] == methods[CANDIDATE]['native_micro_fmax'],
         'saved selected-model alias differs from its declared forecast scores.')
    return cell


def checked_point(method):
    point = method['native_micro_fmax']
    need(method['status'] == 'evaluated' and finite(point) and 0 <= point <= 1,
         'a saved finite evaluated native Fmax is required.')
    parity = method['native_curve_agreement']
    need(parity['author_point_agreement_passed'] is True
         and finite(parity['max_absolute_curve_difference'])
         and parity['max_absolute_curve_difference'] <= 1e-12,
         'complete native/contribution curve agreement must precede plotting.')
    return point


def checked_bootstrap(bootstrap):
    need(bootstrap['draws'] == 2000 and bootstrap['seed'] == 20261113
         and bootstrap['ordinary_only'] is True and bootstrap['IA_supplied'] is False
         and bootstrap['shared_protein_samples_across_all_arms'] is True,
         'the saved predeclared ordinary paired bootstrap is required.')
    pairs = {pair['comparator']: pair for pair in bootstrap['comparisons']}
    need(len(pairs) == len(bootstrap['comparisons']), 'duplicate saved comparator intervals.')
    return pairs


def row_from_pair(cell, bootstrap, candidate, comparator, view, title, label):
    pairs = checked_bootstrap(bootstrap)
    need(comparator in pairs, 'a declared saved comparison is absent: ' + comparator)
    pair = pairs[comparator]
    interval = pair['paired_95_percentile_interval']
    need(pair['candidate'] == candidate and len(interval) == 2
         and all(finite(x) and -1 <= x <= 1 for x in interval) and interval[0] <= interval[1],
         'invalid saved paired interval or candidate identity.')
    methods = cell['methods']; left, right = methods[candidate], methods[comparator]
    first, second = checked_point(left), checked_point(right)
    need(left['raw_native_reference_proteins'] == right['raw_native_reference_proteins']
         == bootstrap['raw_proteins'] and left['eligible_proteins'] == right['eligible_proteins'],
         'paired comparison protein frames differ.')
    return {'view': view, 'title': title, 'setting': 'PK', 'namespace': 'biological_process',
            'candidate': candidate, 'comparator': comparator, 'label': label,
            'candidate_Fmax': first, 'comparator_Fmax': second,
            'point_difference': first - second,
            'paired_95_percentile_interval': list(interval),
            'raw_reference_proteins': bootstrap['raw_proteins'],
            'residual_reference_proteins': left['eligible_proteins']}


def prepare_rows(report):
    rows = []
    for view, title in VIEWS:
        cell = checked_cell(report, view); bootstrap = cell['bootstrap']
        pairs = checked_bootstrap(bootstrap)
        need(set(pairs) == set(cell['methods']) - {CANDIDATE},
             'all saved candidate comparisons must be accounted for before display.')
        for name in controls(report['protocol']):
            rows.append(row_from_pair(cell, bootstrap, CANDIDATE, name, view, title,
                                      LABELS.get(name, name)))
    return rows


def prepare_update_rows(report):
    rows = []
    for view, title in VIEWS:
        cell = checked_cell(report, view)
        for key, candidate, comparator, label in UPDATES:
            rows.append(row_from_pair(cell, cell[key], candidate, comparator, view, title, label))
    return rows


def _draw(rows, output, stem, *, title, subtitle, caption):
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    from matplotlib.ticker import FuncFormatter, MaxNLocator

    plt.rcParams.update({'font.family': 'DejaVu Sans', 'font.size': 10,
        'axes.titlesize': 12, 'axes.labelsize': 10, 'svg.fonttype': 'none',
        'savefig.facecolor': 'white', 'axes.edgecolor': '#c7ccd1',
        'xtick.color': '#425260', 'ytick.color': '#263746'})
    n = len(rows) // 2
    need(n and len(rows) == 2 * n, 'two complete matched panels required.')
    height = max(5.4, 3.35 + n * .43)
    fig, axes = plt.subplots(1, 2, figsize=(14.8, height), sharex=True, sharey=True)
    fig.subplots_adjust(left=.235, right=.945, top=1 - 1.55 / height,
                        bottom=1.45 / height, wspace=.26)
    fig.suptitle(title, x=.235, y=1 - .25 / height, ha='left', fontsize=18,
                 fontweight='bold', color='#172b3a')
    fig.text(.235, 1 - .83 / height, subtitle, ha='left', va='center',
             fontsize=10.5, color='#425260')
    endpoints = [0.] + [number for row in rows for number in
        [row['point_difference'], *row['paired_95_percentile_interval']]]
    low, high = min(endpoints), max(endpoints); padding = max(.008, (high - low) * .08)
    for axis, (view, panel_title), color in zip(axes, VIEWS, ('#376b85', '#607c8c')):
        subset = [row for row in rows if row['view'] == view]
        need(len(subset) == n, 'matched view contains a different number of controls.')
        axis.axvline(0, color='#6d7b85', linewidth=1, linestyle=(0, (4, 3)), zorder=1)
        axis.set_axisbelow(True); axis.grid(axis='x', color='#e8ecef', linewidth=.7)
        for index, row in enumerate(subset):
            left, right = row['paired_95_percentile_interval']; point = row['point_difference']
            # Bounds are drawn directly; percentile intervals need not contain
            # or center on the observed sample difference.
            axis.plot([left, right], [index, index], color=color, linewidth=1.9,
                      solid_capstyle='round', zorder=2)
            axis.plot([left, left], [index - .07, index + .07], color=color, linewidth=1.1)
            axis.plot([right, right], [index - .07, index + .07], color=color, linewidth=1.1)
            axis.scatter([point], [index], s=36, color=color, edgecolors='white', linewidths=.7, zorder=3)
            text = (f'{point:+.1e}' if 0 < abs(point) < .0005 else f'{point:+.3f}')
            axis.text(1.025, index, text, transform=axis.get_yaxis_transform(),
                      ha='left', va='center', fontsize=9, color='#263746')
        first = subset[0]
        axis.set_title(panel_title + '\nPK/BPO: N = ' + str(first['raw_reference_proteins'])
                       + ' | residual N = ' + str(first['residual_reference_proteins']),
                       loc='left', pad=14, color='#263746', fontsize=11)
        axis.set_xlim(low - padding, high + padding); axis.set_ylim(n - .45, -.65)
        axis.xaxis.set_major_locator(MaxNLocator(nbins=5))
        axis.xaxis.set_major_formatter(FuncFormatter(lambda x, _: '0' if x == 0 else f'{x:+.3g}'))
        axis.set_xlabel('Difference in micro-Fmax', labelpad=8)
        axis.tick_params(axis='both', length=0, pad=7)
        axis.spines[['top', 'right', 'left']].set_visible(False)
    axes[0].set_yticks(range(n), [row['label'] for row in rows[:n]])
    fig.text(.025, .48 / height, caption, ha='left', va='center', fontsize=9,
             color='#425260', linespacing=1.6)
    files = []
    for suffix in ('.png', '.svg', '.pdf'):
        target = output / (stem + suffix)
        fig.savefig(target, dpi=200, metadata={'Creator': 'Matplotlib ' + matplotlib.__version__})
        files.append(target)
    plt.close(fig)
    return files, matplotlib.__version__


def render(report_file, output):
    """Read one aggregate report, preserving every saved model/statistic."""
    report_file, output = Path(report_file), Path(output); before = sha(report_file)
    report = json.loads(report_file.read_text()); rows = prepare_rows(report)
    updates = prepare_update_rows(report)
    selected = report['model_choices']['biological_process']['selected_arm']
    need(selected in CONTEXT_ARMS, 'saved selected BPO model identity is invalid.')
    output.mkdir(parents=True, exist_ok=False)
    caption = ('Dots: observed differences. Bars: saved 95% paired whole-protein percentile intervals '
               '(2,000 draws; conditional, unadjusted).\n'
               'PK: partial knowledge; T0-known annotations excluded. Later-curator recovery '
               'does not establish whole-graph biological accuracy.')
    prefix = 'INVENTED QA DATA | ' if report.get('synthetic_fixture') is True else ''
    files, version = _draw(rows, output, 'contextual_pk_bpo_forest',
        title=prefix + 'Contextual integration: temporal annotation recovery',
        subtitle='Observed selected-context minus control micro-Fmax | selected on consumed validation: '
                 + MODEL_LABELS[selected], caption=caption)
    additional, _ = _draw(updates, output, 'source_update_pk_bpo_forest',
        title=prefix + 'Annotation refresh: fixed source-update contrasts',
        subtitle='Observed refreshed LocalPlus minus its declared retained control | no new model selection',
        caption=caption)
    files.extend(additional)
    need(sha(report_file) == before, 'source aggregate changed during rendering.')
    data = output / 'figure_data.json'
    data.write_text(json.dumps({'source_report_sha256': before, 'context_rows': rows,
        'source_update_rows': updates, 'point_policy': 'observed point difference, never bootstrap mean',
        'interval_policy': 'copy saved intervals exactly; no statistics/model choices recomputed'},
        indent=2, allow_nan=False) + '\n'); files.append(data)
    receipt = {'format': 'biograph-steward.contextual-figure.v1', 'source_report_file': str(report_file),
        'source_report_sha256': before, 'implementation_sha256': sha(__file__),
        'python': platform.python_version(), 'matplotlib': version, 'backend': 'Agg',
        'primary_forest_panels': 2, 'displayed_noncontext_controls_per_view': len(controls(report['protocol'])),
        'source_update_contrasts_per_view': len(UPDATES), 'new_statistics_or_model_selection': False,
        'raw_reference_or_forecast_rows_read': False,
        'files': {p.name: sha(p) for p in files}}
    (output / 'figure_receipt.json').write_text(json.dumps(receipt, indent=2) + '\n')
    return receipt


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--report', required=True); parser.add_argument('--output', required=True)
    args = parser.parse_args(); print(json.dumps(render(args.report, args.output), indent=2))


if __name__ == '__main__':
    main()
