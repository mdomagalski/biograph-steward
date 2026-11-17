"""Render the three complete saved PK contrasts; no new statistics or sources.

Follows the project's existing Matplotlib aggregate-figure workflow. Dots are
observed native Fmax differences, never bootstrap means. Intervals are copied
from the already completed paired comparison, without recomputation/selection.
"""
import argparse
import hashlib
import json
import math
from pathlib import Path
import platform

PANELS = (
    ('molecular_function', 'Molecular function', 240, 'Primary'),
    ('biological_process', 'Biological process', 663, 'Secondary'),
    ('cellular_component', 'Cellular component', 447, 'Secondary'),
)
CONTROLS = (
    ('deepgose', 'DeepGO-SE'),
    ('localplus', 'LocalPlus'),
    ('equal_mix', 'Equal mix (50/50)'),
    ('native_t0_nonexperimental', 'T0 nonexperimental'),
)


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def need(value, message):
    if not value:
        raise ValueError('Learned-combination figure: ' + message)


def finite(value):
    return type(value) in (float, int) and math.isfinite(value)


def prepare_rows(report):
    need(report['primary_success'] is False and report['automatic_adoption'] is False,
         'this result figure preserves the failed primary gate and no adoption.')
    rows = []
    for namespace, title, expected_n, endpoint in PANELS:
        data = report['strata']['PK/' + namespace]
        need(data['status'] == 'evaluated'
             and data['raw_native_recognized_proteins'] == expected_n,
             'expected complete PK protein frame: ' + namespace)
        boot = data['bootstrap']
        need(boot['draws'] == 2000 and boot['seed'] == 20261113
             and boot['ordinary_only'] is True and boot['IA_supplied'] is False,
             'fixed ordinary paired bootstrap required.')
        methods = data['methods']
        candidate = methods['learned_mix']['native_micro_fmax']
        need(finite(candidate) and 0 <= candidate <= 1,
             'valid saved candidate native Fmax required.')
        comparisons = {r['comparator']: r for r in boot['comparisons']}
        need(len(comparisons) == len(boot['comparisons']) == 4
             and set(comparisons) == {name for name, _ in CONTROLS},
             'all four fixed controls are required.')
        for comparator, label in CONTROLS:
            method = methods[comparator]
            need(method['native_curve_agreement']['author_point_agreement_passed'] is True
                 and methods['learned_mix']['native_curve_agreement']['author_point_agreement_passed'] is True,
                 'native complete-curve parity must precede display.')
            point = candidate - method['native_micro_fmax']
            pair = comparisons[comparator]
            interval = pair['paired_95_percentile_interval']
            need(pair['candidate'] == 'learned_mix'
                 and len(interval) == 2 and all(finite(x) for x in interval)
                 and interval[0] <= interval[1] and finite(point),
                 'invalid saved paired interval or point difference.')
            if namespace == 'cellular_component' and comparator == 'equal_mix':
                need(point == 0 and interval == [0, 0]
                     and report['selected_alphas'][namespace] == .5,
                     'CC exact equality with equal mix must remain explicit.')
            rows.append({'namespace': namespace, 'title': title, 'endpoint': endpoint,
                'PK_proteins': expected_n, 'alpha': report['selected_alphas'][namespace],
                'candidate': 'learned_mix', 'comparator': comparator, 'label': label,
                'candidate_Fmax': candidate, 'comparator_Fmax': method['native_micro_fmax'],
                'point_difference': point, 'paired_95_percentile_interval': interval})
    return rows


def render(report_file, output):
    report_file, output = Path(report_file), Path(output)
    before = sha(report_file)
    report = json.loads(report_file.read_text())
    rows = prepare_rows(report)
    output.mkdir(parents=True, exist_ok=True)
    stem = 'learned_combination_pk_forest'
    destinations = {suffix: output / (stem + suffix) for suffix in ('.png', '.svg', '_data.json', '_receipt.json')}
    need(not any(p.exists() for p in destinations.values()), 'choose fresh figure output filenames.')

    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    from matplotlib.ticker import FuncFormatter

    plt.rcParams.update({'font.family': 'DejaVu Sans', 'font.size': 10,
        'axes.titlesize': 11, 'axes.labelsize': 10, 'svg.fonttype': 'none',
        'savefig.facecolor': 'white', 'axes.edgecolor': '#c7ccd1',
        'xtick.color': '#425260', 'ytick.color': '#263746'})
    fig, axes = plt.subplots(1, 3, figsize=(13.4, 5.6), sharex=True, sharey=True)
    fig.subplots_adjust(left=.17, right=.985, top=.73, bottom=.29, wspace=.14)
    fig.suptitle('Learned score mixing: temporal CAFA comparison', x=.17, y=.965,
                 ha='left', fontsize=18, fontweight='bold', color='#172b3a')
    fig.text(.17, .89, 'Observed difference in ordinary native micro-Fmax: learned mix minus each control',
             ha='left', va='center', fontsize=11, color='#425260')
    for ax, (namespace, title, n, endpoint) in zip(axes, PANELS):
        subset = [r for r in rows if r['namespace'] == namespace]
        color = '#376b85' if endpoint == 'Primary' else '#607c8c'
        ax.axvline(0, color='#6d7b85', linewidth=1, linestyle=(0, (4, 3)), zorder=1)
        ax.set_axisbelow(True)
        ax.grid(axis='x', color='#e8ecef', linewidth=.7)
        for index, row in enumerate(subset):
            low, high = row['paired_95_percentile_interval']
            point = row['point_difference']
            # Draw bounds directly: percentile intervals need not center on the
            # observed point, so do not assume symmetric error bars.
            ax.plot([low, high], [index, index], color=color, linewidth=1.9,
                    solid_capstyle='round', zorder=2)
            ax.plot([low, low], [index - .07, index + .07], color=color, linewidth=1.1)
            ax.plot([high, high], [index - .07, index + .07], color=color, linewidth=1.1)
            ax.scatter([point], [index], s=37, color=color, edgecolors='white', linewidths=.7, zorder=3)
            ax.annotate(f'{point:+.3f}', (point, index), xytext=(0, 12),
                        textcoords='offset points', ha='center', va='bottom',
                        fontsize=9, color='#263746')
            if namespace == 'cellular_component' and row['comparator'] == 'equal_mix':
                ax.annotate('Identical to equal mix', (0, index), xytext=(12, -13),
                    textcoords='offset points', ha='left', va='top', fontsize=8.6, color='#526570')
        alpha = subset[0]['alpha']
        ax.set_title(f'{endpoint}: {title}\nPK, N = {n:,}  |  alpha = {alpha:g}',
                     loc='left', pad=16, color='#263746', linespacing=1.6)
        ax.set_xlim(-.065, .185)
        ax.set_ylim(3.6, -.7)
        ax.set_xticks([-.05, 0, .05, .10, .15])
        ax.xaxis.set_major_formatter(FuncFormatter(lambda x, _: '0' if x == 0 else f'{x:+.2f}'))
        ax.set_xlabel('Difference in micro-Fmax', labelpad=9)
        ax.tick_params(axis='both', length=0, pad=7)
        ax.spines[['top', 'right', 'left']].set_visible(False)
    axes[0].set_yticks(range(4), [label for _, label in CONTROLS])
    caption = (
        'Dots show observed differences; bars show saved 95% percentile intervals from 2,000 paired whole-protein draws '
        '(unadjusted, conditional).\n'
        'Primary MF did not beat all four controls: no all-control success. CC learned and equal mix are identical '
        '(alpha = 0.5).\n'
        'PK = partial knowledge; known annotations excluded by the native evaluator. Benchmark agreement is not '
        'whole-graph biological accuracy.'
    )
    fig.text(.025, .13, caption, ha='left', va='center', fontsize=9.1,
             color='#425260', linespacing=1.65)
    for suffix in ('.png', '.svg'):
        fig.savefig(destinations[suffix], dpi=200, metadata={'Creator': 'Matplotlib ' + matplotlib.__version__})
    plt.close(fig)
    need(sha(report_file) == before, 'source aggregate changed during rendering.')
    data = {'source_report_file_sha256': before, 'rows': rows,
            'point_policy': 'observed candidate native micro-Fmax minus comparator; not bootstrap mean',
            'interval_policy': 'copied saved paired intervals; no statistics recomputed'}
    destinations['_data.json'].write_text(json.dumps(data, indent=2) + '\n')
    receipt = {'format': 'biograph-steward.learned-combination-figure.v1',
        'source_report': str(report_file), 'source_report_file_sha256': before,
        'implementation_sha256': sha(__file__), 'python': platform.python_version(),
        'matplotlib': matplotlib.__version__, 'backend': 'Agg', 'panels': 3,
        'all_fixed_PK_contrasts': 12, 'new_statistical_tests': False,
        'raw_reference_or_forecast_rows_read': False, 'primary_success': False,
        'files': {p.name: sha(p) for suffix, p in destinations.items() if suffix != '_receipt.json'}}
    destinations['_receipt.json'].write_text(json.dumps(receipt, indent=2) + '\n')
    return receipt


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--report', required=True)
    parser.add_argument('--output', required=True)
    args = parser.parse_args()
    print(json.dumps(render(args.report, args.output), indent=2))


if __name__ == '__main__':
    main()
