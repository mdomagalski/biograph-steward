"""Plot complete saved binary/RA aggregates; no scoring or reference selection.

Matplotlib is an optional presentation dependency. This tool reads six aggregate
JSONs only and never loads matrices, pair values, per-gene outcomes or RA weights.
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


def render(binary, ra, output):
    binary, ra = Path(binary), Path(ra)
    paths = {'binary_report': binary / 'report.json', 'binary_curves': binary / 'curves.json',
             'binary_controls': binary / 'descriptive_control_envelopes.json',
             'ra_report': ra / 'report.json', 'ra_curves': ra / 'curves.json',
             'ra_controls': ra / 'control_envelopes.json'}
    pins = {k: sha(path) for k, path in paths.items()}
    implementation = sha(__file__)
    b = sealed(paths['binary_report'], 'biograph-steward.coessentiality-functional-concordance.v1')
    r = sealed(paths['ra_report'], 'biograph-steward.exploratory-RA-context-result.v1')
    need(r['already_consumed_binary_result'] == b['content_sha256']
         and r['query_genes'] == b['query_genes'] == 92
         and r['primary_pairs'] == b['pair_scope_counts']['nonsyntenic'] == 3968
         and r['N'] == N and r['reference_status'] == 'consumed_exploratory_extension'
         and r.get('calibrated_accuracy_negative_or_prune_labels_created') is False
         and r.get('production_graph_changed') is False, 'binary/RA frame, lineage or scope differs.')
    need(b['files']['curves.json'] == pins['binary_curves']
         and b['files']['descriptive_control_envelopes.json'] == pins['binary_controls']
         and r['files']['curves.json'] == pins['ra_curves']
         and r['files']['control_envelopes.json'] == pins['ra_controls'], 'saved aggregate file pin differs.')
    bc, be, rc, re = [read(paths[k]) for k in ('binary_curves', 'binary_controls', 'ra_curves', 'ra_controls')]
    need(set(bc) == set(rc) and len(bc) == r['source_arms'] == 87, 'complete source-arm inventory differs.')
    binary_curves = {a: bc[a]['nonsyntenic'] for a in ARMS}
    ra_curves = {a: rc[a] for a in ARMS}
    binary_bands = {t: {k: be[t][k]['nonsyntenic'] for k in ('count', 'degree')}
                    for t in ('current', 'historical')}
    for curves in (binary_curves, ra_curves):
        need(all([p['N'] for p in rows] == N for rows in curves.values()), 'every primary N must be shown.')
        need(all(type(p['enrichment']) in (int, float) and math.isfinite(p['enrichment'])
                 for rows in curves.values() for p in rows), 'undefined primary points cannot be silently omitted.')
    for bands in (binary_bands, re):
        for treatment in ('current', 'historical'):
            for kind in ('count', 'degree'):
                rows = bands[treatment][kind]
                need([p['N'] for p in rows] == N and all(p['draws'] == p['defined_draws'] == 20
                     and p['not_a_confidence_interval'] is True for p in rows), 'control range scope differs.')
    plotted = {'N': N, 'binary_OE': {a: [p['enrichment'] for p in binary_curves[a]] for a in ARMS},
        'RA_OE': {a: [p['enrichment'] for p in ra_curves[a]] for a in ARMS},
        'observed_mean_RA': {a: [p['observed_mean_RA_per_slot'] for p in ra_curves[a]] for a in ARMS},
        'binary_control_envelopes': binary_bands, 'RA_control_envelopes': re}
    out = new_output(output, binary, ra)
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
    fig, axes = plt.subplots(1, 3, figsize=(14.2, 6.7))
    fig.subplots_adjust(left=0.065, right=0.985, bottom=0.30, top=0.70, wspace=0.34)
    fig.suptitle('Source context: concentration and absolute affinity', y=0.97, fontsize=17, weight='bold')
    fig.text(0.5, 0.905, '92 measured genes · 3,968 different-chromosome pairs · complete N = 1–10',
             ha='center', fontsize=11, color='#38434E')
    legend = [Line2D([], [], color=COLORS[a], marker=MARKERS[a], linewidth=2, markersize=5,
                     label=LABELS[a]) for a in ARMS]
    fig.legend(handles=legend, loc='upper center', bbox_to_anchor=(0.5, 0.875), ncol=3, frameon=False,
               handlelength=2.8, columnspacing=2.0)
    fig.legend(handles=[Patch(facecolor='#9CA4AC', alpha=0.25, label='Count-matched controls (20 draws)'),
        Patch(facecolor='none', edgecolor='#818A93', hatch='///', label='Degree-preserving controls (20 draws)'),
        Line2D([], [], color='#747D86', linestyle='--', linewidth=1, label='O/E = 1')],
        loc='upper center', bbox_to_anchor=(0.5, 0.823), ncol=3, frameon=False, columnspacing=1.8)
    fig.text(0.5, 0.755, 'Bands follow contrast colours: minimum–maximum across draws, NOT confidence intervals.',
             ha='center', fontsize=10, color='#49545E')
    def bands(ax, values):
        for treatment in ('current', 'historical'):
            for kind in ('count', 'degree'):
                rows = values[treatment][kind]
                kwargs = ({'color': COLORS[treatment], 'alpha': 0.12, 'linewidth': 0}
                    if kind == 'count' else {'facecolor': 'none', 'edgecolor': COLORS[treatment],
                        'hatch': '///', 'alpha': 0.24, 'linewidth': 0.4})
                ax.fill_between(N, [p['minimum'] for p in rows], [p['maximum'] for p in rows], zorder=1, **kwargs)
    for ax, key, title, ylabel in zip(axes, ('binary_OE', 'RA_OE', 'observed_mean_RA'),
        ('A  Binary context', 'B  Resource allocation (RA)', 'C  Absolute observed affinity'),
        ('Observed / expected shared-context hits', 'Observed / expected weighted context', 'Mean RA per selected reference slot')):
        if key != 'observed_mean_RA':
            bands(ax, binary_bands if key == 'binary_OE' else re)
            ax.axhline(1, color='#747D86', linestyle='--', linewidth=1, zorder=2)
        for arm in ARMS:
            ax.plot(N, plotted[key][arm], color=COLORS[arm], marker=MARKERS[arm], markersize=4.5,
                    linewidth=2, zorder=4, markeredgewidth=0.6, markeredgecolor='white')
        ax.set(title=title, xlabel='Reference neighbours per query (N)', ylabel=ylabel, xlim=(0.7, 10.3))
        ax.set_xticks(N)
        ax.set_ylim(bottom=0)
        ax.grid(axis='y', color='#E3E7EB', linewidth=0.7)
        ax.set_axisbelow(True)
    notes = ['No consistent binary advantage\nover fixed controls.',
             'Degree-aware context shows\nexploratory concentration.',
             'Higher O/E can coincide with\nlower absolute observed affinity.']
    for ax, note in zip(axes, notes):
        position = ax.get_position()
        fig.text(position.x0 + position.width / 2, 0.195, note, ha='center', va='center',
                 fontsize=10, color='#38434E', linespacing=1.5)
    footer = [
        'O/E uses the query-matched background. RA weights each shared model by inverse observed degree in the fixed 92-gene arm.',
        'Historical pan-cancer fitness reference, reused during development. RA is uncalibrated affinity; zero is not a biological negative.',
        'Exploratory concordance only: no independent confirmation, calibrated accuracy or automatic-pruning claim.'
    ]
    for y, text in zip((0.115, 0.075, 0.035), footer):
        fig.text(0.5, y, text, ha='center', fontsize=9.2, color='#49545E')
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
    receipt = {'format': 'biograph-steward.binary-RA-aggregate-figure.v1', 'created_at': utcnow(),
        'binary_result_content_sha256': b['content_sha256'], 'RA_result_content_sha256': r['content_sha256'],
        'source_file_sha256': {k: {'file': str(paths[k]), 'sha256': pin} for k, pin in pins.items()},
        'plotting_script_sha256': implementation, 'python_version': platform.python_version(),
        'matplotlib_version': matplotlib.__version__, 'backend': 'Agg', 'complete_primary_N': N,
        'gene_queries': 92, 'primary_nonsyntenic_pairs': 3968, 'source_arms_preserved_in_source': 87,
        'plotted_source_arms': list(ARMS), 'control_draws_per_type_per_contrast': 20,
        'control_bands_are_confidence_intervals': False, 'new_scoring_or_selection': False,
        'raw_matrix_pair_values_or_gene_outcomes_read_or_copied': False,
        'graph_or_scientific_labels_changed': False, 'independent_accuracy_or_pruning_claim': False,
        'reference_status': 'historical_pan_cancer_consumed_reference',
        'official_rendering_documentation': 'https://matplotlib.org/3.10.6/api/_as_gen/matplotlib.axes.Axes.fill_between.html',
        'files': {p.name: sha(p) for p in out.iterdir() if p.is_file()}}
    receipt['content_sha256'] = digest(receipt)
    write_json(out / 'render_receipt.json', receipt)
    return receipt


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--binary', required=True, type=Path)
    parser.add_argument('--ra', required=True, type=Path)
    parser.add_argument('--out', required=True, type=Path)
    args = parser.parse_args()
    print(render(args.binary, args.ra, args.out)['content_sha256'])
