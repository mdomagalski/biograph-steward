"""Plot all twelve saved fill contrasts; no estimator or reference reader.

Reuses the bounded aggregate reader and Matplotlib style of
``tools.cafa_combined.create_figure``. Dots are exact saved point differences,
not bootstrap means. MAX sensitivity results are deliberately outside this plot.
"""
import argparse
import math
from pathlib import Path

from biograph_steward.client import digest, utcnow, write_json
from biograph_steward.file_utils import new_output, sha
from tools.cafa_combined.create_figure import sealed

FORMAT = 'biograph-steward.deepgo-development.v1'
FRAMES = ('primary', 'reserved')
ASPECTS = ('biological_process', 'molecular_function', 'cellular_component')
READOUTS = (('ordinary', 'micro_Fmax', 'eligible_proteins', 'Ordinary'),
            ('IA_weighted', 'IA_micro_Fmax', 'IA_eligible_proteins', 'IA weighted'))
METHODS = ('deepgose', 'strict_alias_localplus')


def need(value, message):
    if not value:
        raise ValueError('DeepGO figure: ' + message)


def number(value):
    return type(value) in (int, float) and math.isfinite(value)


def prepare_rows(publication, manifest_sha256, secondary, secondary_manifest_sha256):
    """Only public aggregate manifests/JSON enter the plotted point inventory."""
    folder, other = Path(publication), Path(secondary)
    manifest = sealed(folder / 'publication_manifest.json', manifest_sha256)
    sm = sealed(other / 'publication_manifest.json', secondary_manifest_sha256)
    need(manifest.get('format') == FORMAT + '.publication-manifest'
         and sm.get('format') == FORMAT + '.secondary-publication-manifest',
         'use the separately sealed public primary and secondary publications.')
    report = sealed(folder / 'report.json', manifest['files']['report.json'])
    prior = sealed(folder / 'prior_246_outcomes.json', manifest['files']['prior_246_outcomes.json'])
    supplement = sealed(other / 'secondary_uncertainty.json', sm['files']['secondary_uncertainty.json'])
    need(report.get('format') == FORMAT + '.public-results'
         and prior.get('format') == FORMAT + '.public-prior246'
         and supplement.get('format') == FORMAT + '.public-secondary-uncertainty',
         'public aggregate formats differ.')
    primary = report['results']
    need(report['all_outcome_slots'] == manifest['all_outcome_slots'] == 252
         and len(prior['rows']) == 246 and len(primary['new_outcome_rows']) == 6
         and primary['earlier_246_inventory']['file_sha256'] == manifest['files']['prior_246_outcomes.json'],
         'the complete unchanged 252-slot primary inventory is required.')
    need(supplement['primary_source_report_file_sha256'] == report['source_report_file_sha256']
         and supplement['primary_source_report_content_sha256'] == report['source_report_content_sha256']
         and sm['content_sha256_of_public_report'] == supplement['content_sha256'],
         'secondary publication is not bound to this primary source.')
    gate = primary['predeclared_development_retention_gate']
    need(supplement['unchanged_primary_BPO_retention_gate'] == gate
         and gate['passed'] is False
         and supplement['posthoc_exploratory'] is True
         and supplement['multiplicity_adjusted'] is False
         and supplement['primary_outcomes_overwritten'] is False
         and supplement['automatic_adoption'] is False,
         'the failed original gate and exploratory secondary scope must remain explicit.')
    all_points = prior['rows'] + primary['new_outcome_rows']
    points = {}
    for frame in FRAMES:
        for aspect in ASPECTS:
            for method in METHODS:
                rows = [r for r in all_points if
                        (r['frame'], r['setting'], r['namespace'], r['method']) ==
                        (frame, 'partial', aspect, method)]
                need(len(rows) == 1 and rows[0]['status'] == 'scored',
                     'one exact scored point profile is required for every aspect/cohort/method.')
                row = rows[0]
                for _, metric, denominator, _ in READOUTS:
                    need(number(row[metric]) and 0 <= row[metric] <= 1
                         and type(row[denominator]) is int and row[denominator] > 0,
                         'invalid saved Fmax or native eligible denominator.')
                points[frame, aspect, method] = row
    secondary_points = supplement['already_reported_secondary_point_rows']
    need(len(secondary_points) == 8 and
         {(r['frame'], r['namespace'], r['method']) for r in secondary_points} ==
         {(f, a, m) for f in FRAMES for a in ASPECTS[1:] for m in METHODS},
         'all eight secondary profile points are required.')
    for row in secondary_points:
        expected = points[row['frame'], row['namespace'], row['method']]
        need(all(expected[k] == value for k, value in row.items()),
             'secondary point copy differs from the unchanged primary profile.')
    pairs = []
    need(len(primary['paired_comparisons']) == 4
         and len(supplement['results']['paired_comparisons']) == 8,
         'all four fixed plus eight exploratory intervals are required.')
    for row in primary['paired_comparisons']:
        pairs.append({**row, 'namespace': 'biological_process'})
    pairs.extend(supplement['results']['paired_comparisons'])
    need(len(pairs) == 12 and {(r['frame'], r['namespace'], r['readout']) for r in pairs} ==
         {(f, a, k) for f in FRAMES for a in ASPECTS for k, *_ in READOUTS}
         and all(r['candidate'] == METHODS[0] and r['comparator'] == METHODS[1] for r in pairs),
         'exact twelve-contrast method/frame/aspect/readout inventory required.')
    plotted = []
    for aspect in ASPECTS:
        for frame in FRAMES:
            candidate, comparator = (points[frame, aspect, m] for m in METHODS)
            for kind, metric, denominator, label in READOUTS:
                row = next(r for r in pairs if (r['frame'], r['namespace'], r['readout']) ==
                           (frame, aspect, kind))
                interval = row['paired_95_percentile_interval']
                need(len(interval) == 2 and all(number(x) and -1 <= x <= 1 for x in interval)
                     and interval[0] <= interval[1] and number(row['difference_mean'])
                     and candidate[denominator] == comparator[denominator],
                     'invalid saved interval or unmatched eligible denominators.')
                plotted.append({'frame': frame, 'namespace': aspect, 'readout': kind,
                    'label': label, 'metric': metric, 'eligible_proteins': candidate[denominator],
                    'candidate': METHODS[0], 'comparator': METHODS[1],
                    'candidate_saved_point': candidate[metric], 'comparator_saved_point': comparator[metric],
                    'observed_point_difference': candidate[metric] - comparator[metric],
                    'saved_paired_95_interval': list(interval),
                    'saved_bootstrap_mean_difference_NOT_plotted_as_dot': row['difference_mean'],
                    'role': 'fixed BPO primary' if aspect == ASPECTS[0] else 'post-hoc exploratory; unadjusted'})
    return plotted, gate, {
        'primary_publication_manifest_sha256': manifest_sha256,
        'primary_public_report_sha256': manifest['files']['report.json'],
        'primary_public_report_content_sha256': report['content_sha256'],
        'prior_246_file_sha256': manifest['files']['prior_246_outcomes.json'],
        'secondary_publication_manifest_sha256': secondary_manifest_sha256,
        'secondary_public_report_sha256': sm['files']['secondary_uncertainty.json'],
        'secondary_public_report_content_sha256': supplement['content_sha256'],
        'common_raw_primary_source_report_sha256': report['source_report_file_sha256']}


def render(publication, manifest_sha256, secondary, secondary_manifest_sha256, output):
    rows, gate, pins = prepare_rows(publication, manifest_sha256, secondary, secondary_manifest_sha256)
    target = new_output(output, publication, secondary)
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    from matplotlib.lines import Line2D
    from matplotlib.ticker import FuncFormatter
    plt.rcParams.update({'font.family': 'DejaVu Sans', 'font.size': 10,
        'axes.spines.top': False, 'axes.spines.right': False,
        'svg.fonttype': 'none', 'svg.hashsalt': digest(pins)})
    ink, teal, amber, gray = '#172b3a', '#147c83', '#ae6b18', '#71818e'
    aspect_labels = {'biological_process': 'BPO', 'molecular_function': 'MFO*', 'cellular_component': 'CCO*'}
    frame_labels = {'primary': 'Original', 'reserved': 'Additional'}
    fig, axis = plt.subplots(figsize=(13.3, 9.4))
    fig.subplots_adjust(left=.315, right=.705, top=.79, bottom=.265)
    fig.suptitle('DeepGO-SE against retained full-context LocalPlus',
        x=.035, y=.965, ha='left', fontsize=19, fontweight='bold', color=ink)
    fig.text(.035, .918,
        'CAFA5 fill · dots: observed micro-Fmax differences · lines: saved conditional 95% protein-bootstrap intervals',
        fontsize=11, color=ink)
    fig.legend(handles=[Line2D([], [], marker='o', color=teal, linestyle='', label='Ordinary micro Fmax'),
        Line2D([], [], marker='D', color=amber, linestyle='', label='Information-weighted micro Fmax')],
        loc='upper left', bbox_to_anchor=(.03, .889), ncol=2, frameon=False)
    fig.text(.035, .828,
        'BPO = biological process; MFO = molecular function; CCO = cellular component. N = native eligible proteins for that readout.',
        fontsize=9.5, color=ink)
    ys = [i + (i // 4) * .8 for i in range(12)]
    axis.axhspan(-.5, 3.5, color='#e5f3f3', alpha=.7, zorder=0)
    axis.axhspan(4.3, 8.3, color='#f3f5f7', zorder=0)
    axis.axhspan(9.1, 13.1, color='#f3f5f7', zorder=0)
    labels = []
    for y, row in zip(ys, rows):
        weighted = row['readout'] == 'IA_weighted'
        color, marker = (amber, 'D') if weighted else (teal, 'o')
        low, high = row['saved_paired_95_interval']
        axis.hlines(y, low, high, color=color, linewidth=2)
        axis.vlines([low, high], y-.075, y+.075, color=color, linewidth=1.5)
        axis.scatter([row['observed_point_difference']], [y], color=color, marker=marker, s=42, zorder=3)
        labels.append(f"{aspect_labels[row['namespace']]} · {frame_labels[row['frame']]} · {row['label']} (N={row['eligible_proteins']:,})")
        axis.text(1.06, y,
            f"{row['observed_point_difference']:+.6f} [{low:+.6f}, {high:+.6f}]",
            transform=axis.get_yaxis_transform(), va='center', ha='left',
            fontsize=9, fontfamily='DejaVu Sans Mono', color=ink, clip_on=False)
    axis.text(1.06, 1.035, 'Observed difference [95% interval]', transform=axis.transAxes,
        va='bottom', fontsize=9.5, fontweight='bold', color=ink)
    axis.axvline(0, color=gray, linestyle='--', linewidth=1)
    values = [v for r in rows for v in (*r['saved_paired_95_interval'], r['observed_point_difference'], 0.)]
    margin = max((max(values)-min(values))*.12, .002)
    axis.set(yticks=ys, yticklabels=labels, ylim=(13.35, -.75),
        xlim=(min(values)-margin, max(values)+margin),
        xlabel='DeepGO-SE − matched full strict LocalPlus (micro-Fmax units)')
    axis.tick_params(axis='y', length=0, pad=10, labelsize=9.5)
    axis.xaxis.set_major_formatter(FuncFormatter(lambda value, pos: f'{value:+.3f}' if value else '0'))
    axis.grid(axis='x', alpha=.16)
    fig.text(.035, .188, 'Fixed BPO adoption rule: NOT PASSED. Retained LocalPlus and the original 252 outcomes remain unchanged.',
        fontsize=11, fontweight='bold', color=ink)
    fig.text(.035, .143, 'BPO: all four fixed primary contrasts. *MFO/CCO: all eight post-hoc exploratory intervals, not multiplicity adjusted.',
        fontsize=10, color=ink)
    fig.text(.035, .106, 'Previously exposed development labels; 2,000 paired draws per cohort/aspect. Shared proteins, neighbors and sources are not independent replications.',
        fontsize=9.5, color=ink)
    fig.text(.035, .070, 'Different training/resource profiles (reported 2021 checkpoint versus 2023 Local seeds); not an isolated algorithm or ontology-axiom effect.',
        fontsize=9.5, color=ink)
    fig.text(.035, .034, 'Fmax is a benchmark maximum, not scientific accuracy or calibrated confidence. Common MAX sensitivity is separate and is not plotted.',
        fontsize=9.5, color=ink)
    for suffix in ('png', 'svg'):
        fig.savefig(target / ('deepgo_fill_contrasts.' + suffix), dpi=160, facecolor='white')
    plt.close(fig)
    plotted = {'format': FORMAT + '.plotted-fill-contrasts', 'contrasts': rows,
        'source_pins': pins, 'fixed_BPO_retention_gate': gate,
        'all_fill_contrasts': 12, 'BPO_fixed': 4, 'MF_CC_exploratory_unadjusted': 8,
        'dot_definition': 'Saved native point candidate minus matched comparator, not bootstrap mean.',
        'MAX_results_included': False, 'raw_reference_or_forecast_rows_read': False,
        'new_scientific_estimator_or_scores': False}
    plotted['content_sha256'] = digest(plotted)
    write_json(target / 'plotted_aggregates.json', plotted)
    need(sha(Path(publication) / 'publication_manifest.json') == manifest_sha256
         and sha(Path(secondary) / 'publication_manifest.json') == secondary_manifest_sha256,
         'source publication changed while rendering.')
    receipt = {'format': FORMAT + '.fill-figure', 'created_at': utcnow(), 'source_pins': pins,
        'implementation_sha256': sha(__file__), 'aggregate_reader_sha256': sha(Path(__import__(
            'tools.cafa_combined.create_figure', fromlist=['x']).__file__)),
        'matplotlib': matplotlib.__version__, 'raw_reference_or_forecast_rows_read': False,
        'new_scientific_scoring': False,
        'files': {p.name: sha(p) for p in target.iterdir() if p.is_file()}}
    receipt['content_sha256'] = digest(receipt)
    write_json(target / 'report.json', receipt)
    return receipt


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ('publication', 'manifest-sha256', 'secondary', 'secondary-manifest-sha256', 'output'):
        parser.add_argument('--' + name, required=True)
    value = render(**vars(parser.parse_args()))
    print(value['content_sha256'])
