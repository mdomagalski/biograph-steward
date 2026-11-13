"""Plot sealed aggregate curves for exploratory and prospective gene cohorts.

Matplotlib is optional. Only nine aggregate JSON files are read: no matrices,
pair values, per-gene outcomes, affinity weights or new scientific selection.
"""
import argparse
import json
import math
from pathlib import Path
import platform
import sys

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from biograph_steward.client import digest, utcnow, write_json
from biograph_steward.file_utils import new_output, sha

ARMS = ('normalized', 'current', 'historical')
COLORS = {'normalized': '#404953', 'current': '#0072B2', 'historical': '#D55E00'}
LABELS = {'normalized': 'Normalized source context', 'current': 'Current-release contrast',
          'historical': 'Historical-xref contrast'}
MARKERS = {'normalized': 'o', 'current': '^', 'historical': 's'}
N = list(range(1, 11))


def need(value, message):
    if not value:
        raise ValueError('Aggregate figure: ' + message)


def read(path):
    path = Path(path)
    need(path.is_file() and not path.is_symlink() and path.stat().st_size <= 3_000_000,
         'input must be a bounded ordinary aggregate JSON.')
    return json.loads(path.read_bytes())


def sealed(path, expected):
    value = read(path)
    need(value.get('format') == expected and value.get('content_sha256') == digest({
        k: v for k, v in value.items() if k != 'content_sha256'}), 'aggregate report seal or format differs.')
    return value


def load_aggregates(binary, ra, transfer):
    """Validate source-bound aggregate profiles before optional plotting imports."""
    binary, ra, transfer = Path(binary), Path(ra), Path(transfer)
    paths = {'binary_report': binary / 'report.json', 'binary_curves': binary / 'curves.json',
             'binary_controls': binary / 'descriptive_control_envelopes.json',
             'ra_report': ra / 'report.json', 'ra_curves': ra / 'curves.json',
             'ra_controls': ra / 'control_envelopes.json', 'transfer_report': transfer / 'report.json',
             'transfer_curves': transfer / 'curves.json', 'transfer_controls': transfer / 'control_envelopes.json'}
    pins = {k: sha(path) for k, path in paths.items()}
    b = sealed(paths['binary_report'], 'biograph-steward.coessentiality-functional-concordance.v1')
    r = sealed(paths['ra_report'], 'biograph-steward.exploratory-RA-context-result.v1')
    t = sealed(paths['transfer_report'], 'biograph-steward.prospective-gene-transfer-result.v1')
    need(r['already_consumed_binary_result'] == b['content_sha256']
         and r['query_genes'] == b['query_genes'] == 92
         and r['primary_pairs'] == b['pair_scope_counts']['nonsyntenic'] == 3968
         and r['N'] == N and r['reference_status'] == 'consumed_exploratory_extension'
         and r.get('calibrated_accuracy_negative_or_prune_labels_created') is False
         and r.get('production_graph_changed') is False, 'binary/RA frame, lineage or scope differs.')
    need(t['fixed_queries'] == 128 and t['primary_pairs'] == 7648 and t['all_unordered_pairs'] == 8128
         and t['source_arms'] == 42 and t['N'] == N
         and t['prospective_gene_transfer_within_same_published_reference'] is True
         and t['independent_experimental_confirmation_or_whole_proteome_accuracy'] is False
         and t['new_model_or_production_graph_change'] is False
         and t['calibrated_negative_truth_or_prune_labels_created'] is False,
         'prospective transfer frame or scope differs.')
    for report, prefix, control in [(b, 'binary', 'descriptive_control_envelopes.json'),
                                    (r, 'ra', 'control_envelopes.json'), (t, 'transfer', 'control_envelopes.json')]:
        need(report['files']['curves.json'] == pins[prefix + '_curves']
             and report['files'][control] == pins[prefix + '_controls'], 'saved aggregate file pin differs.')
    bc, be, rc, re, tc, te = [read(paths[k]) for k in ('binary_curves', 'binary_controls',
        'ra_curves', 'ra_controls', 'transfer_curves', 'transfer_controls')]
    need(set(bc) == set(rc) and len(bc) == r['source_arms'] == 87 and len(tc) == 42,
         'complete source-arm inventory differs.')
    profiles = {
        'exploratory92': {'arms': list(ARMS), 'queries': 92, 'pairs': 3968,
            'binary': {a: bc[a]['nonsyntenic'] for a in ARMS}, 'RA': {a: rc[a] for a in ARMS},
            'binary_bands': {a: {k: be[a][k]['nonsyntenic'] for k in ('count', 'degree')}
                             for a in ('current', 'historical')}, 'RA_bands': re},
        'prospective128': {'arms': ['normalized', 'historical'], 'queries': 128, 'pairs': 7648,
            'binary': {a: tc[a]['binary_diagnostic'] for a in ('normalized', 'historical')},
            'RA': {a: tc[a]['RA'] for a in ('normalized', 'historical')},
            'binary_bands': {'historical': te['binary_diagnostic']}, 'RA_bands': {'historical': te['RA']},
            'source_coverage': t['source_only_coverage']}}
    for profile in profiles.values():
        for metric in ('binary', 'RA'):
            need(all([p['N'] for p in rows] == N for rows in profile[metric].values()), 'every primary N must be shown.')
            need(all(type(p['enrichment']) in (int, float) and math.isfinite(p['enrichment'])
                     for rows in profile[metric].values() for p in rows), 'undefined primary points cannot be silently omitted.')
            for treatment in profile[metric + '_bands'].values():
                for rows in treatment.values():
                    need([p['N'] for p in rows] == N and all(p['draws'] == p['defined_draws'] == 20
                         and p['not_a_confidence_interval'] is True and
                         all(type(p[k]) in (int, float) and math.isfinite(p[k]) for k in ('minimum', 'median', 'maximum'))
                         and p['minimum'] <= p['median'] <= p['maximum'] for p in rows), 'control range scope differs.')
        need(all(type(p['observed_mean_RA_per_slot']) in (int, float) and math.isfinite(p['observed_mean_RA_per_slot'])
                 for rows in profile['RA'].values() for p in rows), 'absolute observed affinity cannot be omitted.')
    plotted = {'N': N, 'cohorts': {name: {'queries': p['queries'], 'primary_pairs': p['pairs'],
        'plotted_arms': p['arms'], 'binary_OE': {a: [x['enrichment'] for x in p['binary'][a]] for a in p['arms']},
        'RA_OE': {a: [x['enrichment'] for x in p['RA'][a]] for a in p['arms']},
        'observed_mean_RA': {a: [x['observed_mean_RA_per_slot'] for x in p['RA'][a]] for a in p['arms']},
        'binary_control_envelopes': p['binary_bands'], 'RA_control_envelopes': p['RA_bands']}
        for name, p in profiles.items()}}
    return paths, pins, (b, r, t), profiles, plotted


def render(binary, ra, transfer, output):
    implementation = sha(__file__)
    paths, pins, reports, profiles, plotted = load_aggregates(binary, ra, transfer)
    out = new_output(output, binary, ra, transfer)
    write_json(out / 'plotted_aggregates.json', plotted)
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    from matplotlib.lines import Line2D
    from matplotlib.patches import Patch
    plt.rcParams.update({'font.family': 'DejaVu Sans', 'font.size': 10, 'axes.titlesize': 12,
        'axes.labelsize': 10, 'axes.spines.top': False, 'axes.spines.right': False,
        'axes.edgecolor': '#68727B', 'axes.linewidth': 0.8, 'xtick.labelsize': 9,
        'ytick.labelsize': 9, 'svg.fonttype': 'none', 'pdf.fonttype': 42,
        'svg.hashsalt': digest(pins), 'hatch.linewidth': 0.45})
    fig, axes = plt.subplots(2, 3, figsize=(15.2, 10.5))
    fig.subplots_adjust(left=0.065, right=0.985, bottom=0.18, top=0.765, wspace=0.34, hspace=0.69)
    fig.suptitle('Source-context concentration did not transfer to a new-gene sample', y=0.975, fontsize=17, weight='bold')
    fig.text(0.5, 0.935, 'Exploratory positive and prospective negative shown together; same published functional reference, not independent studies',
             ha='center', fontsize=10.5, color='#38434E')
    fig.legend(handles=[Line2D([], [], color=COLORS[a], marker=MARKERS[a], linewidth=2, markersize=5,
        label=LABELS[a]) for a in ARMS], loc='upper center', bbox_to_anchor=(0.5, 0.912), ncol=3,
        frameon=False, handlelength=2.8, columnspacing=2.0)
    fig.legend(handles=[Patch(facecolor='#9CA4AC', alpha=0.25, label='Count-matched controls (20 draws)'),
        Patch(facecolor='none', edgecolor='#818A93', hatch='///', label='Degree-preserving controls (20 draws)'),
        Line2D([], [], color='#747D86', linestyle='--', linewidth=1, label='O/E = 1')],
        loc='upper center', bbox_to_anchor=(0.5, 0.875), ncol=3, frameon=False, columnspacing=1.8)
    fig.text(0.5, 0.825, 'Bands: complete minimum–maximum across fixed draws, NOT confidence intervals. No arm or N selected after outcomes.',
             ha='center', fontsize=10, color='#49545E')
    row_headers = [
        'DEVELOPMENT  |  92 measured genes · 3,968 nonsyntenic pairs · consumed-reference exploratory result',
        'PROSPECTIVE GENE TRANSFER  |  128 sampled genes · 7,648 nonsyntenic pairs · no full-curve advantage']
    for row, (name, profile) in enumerate(profiles.items()):
        fig.text(0.065, 0.79 if row == 0 else 0.435, row_headers[row], fontsize=10.5, weight='bold', color='#38434E')
        data = plotted['cohorts'][name]
        for col, (key, title, ylabel) in enumerate([
            ('binary_OE', 'Binary shared context', 'Observed / expected shared-context hits'),
            ('RA_OE', 'Resource allocation (RA)', 'Observed / expected weighted context'),
            ('observed_mean_RA', 'Absolute observed affinity', 'Mean RA per selected reference slot')]):
            ax = axes[row, col]
            if col < 2:
                for treatment, kinds in profile['binary_bands' if col == 0 else 'RA_bands'].items():
                    for kind, rows in kinds.items():
                        kwargs = ({'color': COLORS[treatment], 'alpha': 0.12, 'linewidth': 0}
                            if kind == 'count' else {'facecolor': 'none', 'edgecolor': COLORS[treatment],
                                'hatch': '///', 'alpha': 0.24, 'linewidth': 0.4})
                        ax.fill_between(N, [p['minimum'] for p in rows], [p['maximum'] for p in rows], zorder=1, **kwargs)
                ax.axhline(1, color='#747D86', linestyle='--', linewidth=1, zorder=2)
            for arm in profile['arms']:
                ax.plot(N, data[key][arm], color=COLORS[arm], marker=MARKERS[arm], markersize=4.5,
                        linewidth=2, zorder=4, markeredgewidth=0.6, markeredgecolor='white')
            ax.set(title=chr(65 + row * 3 + col) + '  ' + title, xlabel='Reference neighbours per query (N)',
                   ylabel=ylabel, xlim=(0.7, 10.3))
            ax.set_xticks(N); ax.set_ylim(bottom=0)
            ax.grid(axis='y', color='#E3E7EB', linewidth=0.7); ax.set_axisbelow(True)
    fig.text(0.5, 0.12, 'New-gene historical context: 26 active and 102 zero-context queries. Fixed query frame and absolute means retain all queries.',
             ha='center', fontsize=10, color='#38434E')
    footer = [
        'O/E pools observed and query-matched expected sums. Zero-context queries add zero to both; the ratio is NOT coverage-adjusted.',
        'RA weights shared models by inverse observed degree in each full-gene arm. Absolute affinity may fall as O/E rises.',
        'New-gene ranks are within the sampled cohort, not genomewide top N or significance-defined positives. No fitness fit or new model is involved.',
        'Historical pan-cancer reference; no independent-study confirmation, calibrated biological accuracy, predictive benefit or automatic-pruning claim.'
    ]
    for y, text in zip((0.087, 0.065, 0.043, 0.021), footer):
        fig.text(0.5, y, text, ha='center', fontsize=9.1, color='#49545E')
    for extension in ('png', 'svg', 'pdf'):
        metadata = {'Creator': 'Matplotlib ' + matplotlib.__version__}
        if extension == 'pdf':
            metadata.update(CreationDate=None, ModDate=None)
        elif extension == 'svg':
            metadata['Date'] = None
        fig.savefig(out / ('functional_concordance.' + extension), dpi=260, facecolor='white', metadata=metadata)
    plt.close(fig)
    need(all(sha(paths[k]) == pin for k, pin in pins.items()) and sha(__file__) == implementation,
         'aggregate source or plotting implementation changed during rendering.')
    b, r, t = reports
    receipt = {'format': 'biograph-steward.exploratory-transfer-aggregate-figure.v2', 'created_at': utcnow(),
        'binary_result_content_sha256': b['content_sha256'], 'RA_result_content_sha256': r['content_sha256'],
        'prospective_transfer_result_content_sha256': t['content_sha256'],
        'source_file_sha256': {k: {'file': str(paths[k]), 'sha256': pin} for k, pin in pins.items()},
        'plotting_script_sha256': implementation, 'python_version': platform.python_version(),
        'matplotlib_version': matplotlib.__version__, 'backend': 'Agg', 'complete_primary_N': N,
        'cohorts': {name: {'gene_queries': p['queries'], 'primary_nonsyntenic_pairs': p['pairs'],
                         'plotted_source_arms': p['arms']} for name, p in profiles.items()},
        'control_draws_per_type_per_contrast': 20, 'control_bands_are_confidence_intervals': False,
        'new_scoring_or_selection': False, 'raw_matrix_pair_values_or_gene_outcomes_read_or_copied': False,
        'graph_or_scientific_labels_changed': False, 'independent_accuracy_or_pruning_claim': False,
        'reference_status': 'same_historical_reference_consumed_development_then_prospective_gene_transfer',
        'official_rendering_documentation': 'https://matplotlib.org/3.10.6/api/_as_gen/matplotlib.axes.Axes.fill_between.html',
        'files': {p.name: sha(p) for p in out.iterdir() if p.is_file()}}
    receipt['content_sha256'] = digest(receipt); write_json(out / 'render_receipt.json', receipt)
    return receipt


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ('binary', 'ra', 'transfer', 'out'):
        parser.add_argument('--' + name, required=True, type=Path)
    args = parser.parse_args()
    print(render(args.binary, args.ra, args.transfer, args.out)['content_sha256'])
