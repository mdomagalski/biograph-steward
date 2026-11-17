"""Plot sealed development aggregates; never read targets, labels or forecasts.

Uses the existing aggregate/source-pin conventions and Matplotlib presentation
from tools.cafa_reference.plot_comparisons. This is a delivery figure, not an
additional estimator, model selection rule or scientific scoring operation.
"""
import argparse
import json
import math
from pathlib import Path

from biograph_steward.client import digest, utcnow, write_json
from biograph_steward.file_utils import new_output, sha


def sealed(path, expected):
    path = Path(path)
    if (not path.is_file() or path.is_symlink() or path.stat().st_size > 10_000_000
            or sha(path) != expected):
        raise ValueError('Use the explicitly pinned aggregate publication.')
    value = json.loads(path.read_bytes())
    if value.get('content_sha256') != digest({k: v for k, v in value.items() if k != 'content_sha256'}):
        raise ValueError('Aggregate content seal differs.')
    return value


def render(publication, manifest_sha256, output):
    folder = Path(publication)
    manifest = sealed(folder / 'publication_manifest.json', manifest_sha256)
    pins = manifest['files']
    summary = sealed(folder / 'summary.json', pins['summary.json'])
    prior = sealed(folder / 'prior_240_outcomes.json', pins['prior_240_outcomes.json'])
    if (summary.get('format') != 'biograph-steward.combined-development-compact-summary.v1'
            or prior.get('format') != 'biograph-steward.combined-development-prior240.v1'
            or len(prior['rows']) != 240 or len(summary['new_outcome_rows']) != 6
            or summary['earlier_240_inventory']['file_sha256'] != pins['prior_240_outcomes.json']):
        raise ValueError('Complete fixed comparison inventory required.')
    namespace = 'biological_process'
    rows = prior['rows'] + summary['new_outcome_rows']

    def point(frame, method):
        found = [r for r in rows if (r['frame'], r['setting'], r['namespace'], r['method'])
                 == (frame, 'partial', namespace, method)]
        if len(found) != 1 or found[0]['status'] != 'scored':
            raise ValueError('Required scored aggregate is missing or duplicated.')
        return found[0]

    methods = ('localplus', 'genemaniaplus', 'strict_alias_localplus', 'combined_strict_genemaniaplus')
    labels = ('Scoped LocalPlus', 'Scoped GeneMANIA+', 'Full qualified LocalPlus', 'Full qualified GeneMANIA+')
    original = [point('primary', method) for method in methods]
    kinds = (('ordinary', 'micro_Fmax', 'Ordinary'), ('IA_weighted', 'IA_micro_Fmax', 'Information-weighted'))
    contrasts = []
    for frame, name in (('primary', 'Original cohort'), ('reserved', 'Additional cohort')):
        new, baseline = point(frame, methods[-1]), point(frame, methods[-2])
        for kind, metric, label in kinds:
            found = [r for r in summary['paired_comparisons'] if
                     (r['frame'], r['candidate'], r['comparator'], r['readout'])
                     == (frame, methods[-1], methods[-2], kind)]
            if len(found) != 1:
                raise ValueError('Missing or duplicate fixed paired contrast.')
            interval = found[0]['paired_95_percentile_interval']
            if (len(interval) != 2 or not all(type(x) in (int, float) and math.isfinite(x) for x in interval)
                    or interval[0] > interval[1]):
                raise ValueError('Invalid saved paired interval.')
            contrasts.append({'cohort': name, 'readout': label, 'metric': metric,
                'observed_difference': new[metric] - baseline[metric], 'interval': interval,
                'bootstrap_mean_difference': found[0]['difference_mean']})
    plotted = {'original_points': original, 'paired_contrasts': contrasts,
        'predeclared_gate': summary['predeclared_development_retention_gate'],
        'source_manifest_sha256': manifest_sha256, 'raw_cases_read': False}
    target = new_output(output, folder)
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    from matplotlib.lines import Line2D
    plt.rcParams.update({'font.family': 'DejaVu Sans', 'font.size': 10,
        'axes.spines.top': False, 'axes.spines.right': False, 'svg.fonttype': 'none',
        'svg.hashsalt': manifest_sha256})
    ink, teal, amber, gray = '#172b3a', '#147c83', '#ae6b18', '#71818e'
    fig, (left, right) = plt.subplots(1, 2, figsize=(14, 7.2), gridspec_kw={'width_ratios': [1.03, 1]})
    fig.subplots_adjust(left=.22, right=.97, top=.75, bottom=.29, wspace=.8)
    fig.suptitle('Full context and published diffusion', x=.035, y=.96, ha='left',
        fontsize=19, fontweight='bold', color=ink)
    fig.text(.035, .91, 'CAFA5 temporal function recovery · one exposed-label development combination', fontsize=11, color=ink)
    for y, row in enumerate(original):
        values = row['micro_Fmax'], row['IA_micro_Fmax']
        left.plot(values, [y, y], color='#cbd5dc', zorder=1)
        left.scatter([values[0]], [y], color=teal, s=48, zorder=3)
        left.scatter([values[1]], [y], color=amber, marker='D', s=40, zorder=3)
        left.annotate(f'{values[0]:.4f} / {values[1]:.4f}', (max(values), y),
            xytext=(0, -21), textcoords='offset points', ha='right', fontsize=9, color=ink)
    left.axhspan(1.55, 3.5, color='#e5f3f3', alpha=.5, zorder=0)
    left.set(yticks=range(4), yticklabels=labels, ylim=(3.6, -.5), xlim=(.10, .145),
        xticks=[.10, .11, .12, .13, .14],
        xlabel='Native micro Fmax', title='Original cohort: source profile × method')
    left.grid(axis='x', alpha=.16)
    for y, row in enumerate(contrasts):
        color = teal if y % 2 == 0 else amber
        low, high = row['interval']
        right.hlines(y, low, high, color=color, linewidth=2)
        right.vlines([low, high], y-.065, y+.065, color=color)
        right.scatter([row['observed_difference']], [y], color=color,
            marker='o' if y % 2 == 0 else 'D', s=42, zorder=3)
        right.annotate(f"{row['observed_difference']:+.4f} [{low:+.5f}, {high:+.5f}]",
            (row['observed_difference'], y), xytext=(0, -22), textcoords='offset points',
            ha='center', fontsize=9, color=ink)
    right.axvline(0, color=gray, linestyle='--', linewidth=1)
    limits = [x for row in contrasts for x in (*row['interval'], row['observed_difference'], 0.)]
    margin = max((max(limits)-min(limits))*.18, .001)
    right.set(yticks=range(4), yticklabels=[r['cohort']+'\n'+r['readout'] for r in contrasts],
        ylim=(3.6, -.5), xlim=(min(limits)-margin, max(limits)+margin),
        xlabel='GM minus matched full-context LocalPlus', title='Both cohorts: observed difference\nand conditional 95% interval')
    right.grid(axis='x', alpha=.16)
    fig.legend(handles=[Line2D([], [], marker='o', color=teal, linestyle='', label='Ordinary micro Fmax'),
        Line2D([], [], marker='D', color=amber, linestyle='', label='Information-weighted micro Fmax')],
        loc='upper left', bbox_to_anchor=(.03, .875), ncol=2, frameon=False)
    passed = plotted['predeclared_gate']['passed']
    fig.text(.035, .205, 'Fixed development retention gate: '+('passed.' if passed else 'not passed.'),
        fontsize=12, fontweight='bold', color=ink)
    fig.text(.035, .16, 'The full profile changes graph context, historical seeds and identifier qualification. Improvements do not add arithmetically.', fontsize=10, color=ink)
    fig.text(.035, .12, 'Both original and additional cohorts were previously evaluated. This follow-up is development reuse, not a new blind confirmation.', fontsize=9.5, color=ink)
    fig.text(.035, .08, 'Intervals: 2,000 paired protein resamples, conditional and descriptive. Fmax is a ranking benchmark metric, not percent biological accuracy.', fontsize=9.5, color=ink)
    fig.text(.035, .04, 'All six aspect outcomes, macro/IA-macro readouts, fixed-0.5 trade-offs and the earlier 240 controls remain in the linked aggregate report.', fontsize=9.5, color=ink)
    for suffix in ('png', 'svg'):
        fig.savefig(target / ('combined_context.'+suffix), dpi=180, facecolor='white')
    plt.close(fig)
    write_json(target / 'plotted_aggregates.json', plotted)
    if sha(folder / 'publication_manifest.json') != manifest_sha256:
        raise ValueError('Source publication changed while rendering.')
    receipt = {'format': 'biograph-steward.combined-development-figure.v1', 'created_at': utcnow(),
        'source_manifest_sha256': manifest_sha256, 'implementation_sha256': sha(__file__),
        'matplotlib': matplotlib.__version__, 'raw_reference_or_forecast_rows_read': False,
        'files': {p.name: sha(p) for p in target.iterdir() if p.is_file()}}
    receipt['content_sha256'] = digest(receipt)
    write_json(target / 'report.json', receipt)
    return receipt


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    for key in ('publication', 'manifest-sha256', 'output'):
        parser.add_argument('--'+key, required=True)
    result = render(**vars(parser.parse_args()))
    print(json.dumps({'content_sha256': result['content_sha256']}))
