"""Publish a small read-only view of a completed experimental comparison.

The existing pruning inspector remains bound to its consumed Y2H assessment.
This viewer preserves the separate positive-only reference and its claim scope;
it checks saved results, not experimental truth, and never selects a graph.
"""
from copy import deepcopy
import hashlib
from html import escape
from pathlib import Path

from .assay_attachment import _capture, _decode, _ordinary, _sealed
from .client import digest, utcnow, write_json
from .file_utils import new_output

FORMAT = 'biograph-steward.biological-comparison-publication.v1'
RESULT = 'biograph-steward.opencell-positive-retention.v1.result'
PROTOCOL = 'biograph-steward.opencell-positive-retention.v1'
FILES = frozenset({'report.json', 'protocol.json', 'source_qualification.json', 'selection_receipt.json', 'sources.json'})
QC_FILES = frozenset({'processed_qc_report.json', 'processed_qc_protocol.json'})
LABELS = {'unpruned': 'Original source graph', 'native_top80': 'Native STRING confidence',
    'pa_top80': 'Degree-product control', 'ne_top80': 'Network Enhancement',
    'human_experimental_top80': 'Organism-native experimental support (fixed primary)',
    'mps_top80': 'Edge-masked MPS (exploratory)',
    'combined_experimental_top80': 'Experimental support including transfer (exploratory)'}


def need(condition, message):
    if not condition:
        raise ValueError(message)


def _bounded(path):
    path = Path(path)
    need(path.is_file() and not path.is_symlink() and path.stat().st_size <= 2_000_000,
         'Comparison files must be ordinary bounded files.')
    return _ordinary(path)


def _summary(files):
    report, protocol, source, selection, citations = [_decode(files[name]) for name in
        ('report.json', 'protocol.json', 'source_qualification.json', 'selection_receipt.json', 'sources.json')]
    need(all(_sealed(value) for value in (report, protocol, source, selection)), 'Comparison result binding changed.')
    need(report.get('format') == RESULT and protocol.get('format') == PROTOCOL
         and report.get('status') == 'completed' and protocol.get('status') == 'frozen'
         and report.get('protocol_sha256') == protocol['content_sha256']
         and report.get('source_qualification_sha256') == source['content_sha256']
         and protocol.get('source_qualification_sha256') == source['content_sha256']
         and selection.get('source_qualification_sha256') == source['content_sha256'],
         'Comparison results belong to different frozen inputs.')
    need(report.get('source_graph_changed') is False and report.get('ranking_or_threshold_selection_performed') is False
         and protocol.get('reference_calls_opened') is False, 'Expected a completed assessment of preselected views.')
    need(protocol.get('primary_candidate') == report.get('primary_candidate') == 'human_experimental_top80'
         and protocol.get('controls') == report.get('controls') == ['native_top80', 'pa_top80']
         and set(protocol.get('arms', [])) == set(LABELS)
         and report.get('source_nodes_preserved') == protocol.get('source_nodes')
         and protocol.get('source_pairs') == source.get('original_source_pairs')
         and protocol.get('qualified_eligible_pairs') == source.get('qualified_rankable_pairs')
         and protocol.get('eligible_retention_budget') == source.get('retained_rankable_budget')
         and protocol.get('abstain_retained_pairs') == source.get('abstain_retained_pairs')
         and source.get('qualified_rankable_removals') == source['qualified_rankable_pairs'] - source['retained_rankable_budget']
         and source['qualified_rankable_pairs'] + source['abstain_retained_pairs'] == source['original_source_pairs']
         and protocol['input_files']['artifact_selection_receipt']['sha256'] == hashlib.sha256(files['selection_receipt.json']).hexdigest()
         and selection.get('reference_calls_opened') is False and selection.get('new_outcome_selection') is False
         and selection.get('source_graph_modified') is False,
         'Primary method, controls, source population or preselected-view binding changed.')
    metrics = report['metrics']; arms = metrics['arms']
    count = metrics['primary_unique_eligible_positive_pairs']
    need(type(count) is int and count >= 0 and set(arms) == set(LABELS), 'Unexpected reference population or comparator arms.')
    for arm, value in arms.items():
        kept = value['positive_pairs_retained']
        need(type(kept) is int and 0 <= kept <= count and value['eligible_positive_pairs'] == count
             and value['positive_pairs_lost'] == count - kept, 'Reference denominators differ across graph views.')
        expected = kept / count if count else None
        need(value['micro_retention'] == expected, 'Reference retention differs from its saved counts.')
        need(arm != 'unpruned' or kept == count, 'Unpruned view must retain every source-present reference pair.')
        expected_pairs = source['original_source_pairs'] if arm == 'unpruned' else (
            source['retained_rankable_budget'] + source['abstain_retained_pairs'])
        need(value['source_pairs_retained'] == expected_pairs and value['source_pairs_removed'] == source['original_source_pairs'] - expected_pairs,
             'Comparator graph budgets differ.')
    sufficient = count >= protocol['minimum_eligible_positive_pairs'] and (
        metrics['evaluable_exact_author_bait_labels'] >= protocol['minimum_evaluable_exact_bait_labels'])
    primary = report['primary_candidate']
    gate = sufficient and all(arms[primary]['positive_pairs_retained'] > arms[c]['positive_pairs_retained']
                              for c in report['controls'])
    need(metrics['primary_utility_gate_passed'] is gate and metrics['coverage_gate_passed'] is sufficient
         and metrics['precision_or_scientific_accuracy_established'] is False
         and metrics['raw_noncalls_evaluated'] is False, 'Saved utility claim differs from its bounded endpoint.')
    need(isinstance(citations, dict) and citations.get('raw_reference_rows_included') is False,
         'The small publication must exclude raw reference tables.')
    current_qc = None
    if QC_FILES & set(files):
        need(QC_FILES <= set(files), 'Processed-reference QC files are incomplete.')
        qc, qp = _decode(files['processed_qc_report.json']), _decode(files['processed_qc_protocol.json'])
        need(_sealed(qc) and _sealed(qp)
             and qc.get('format') == 'biograph-steward.processed-opencell-consumed-qc.v1.result'
             and qp.get('format') == 'biograph-steward.processed-opencell-consumed-qc.v1'
             and qc.get('status') == 'completed_consumed_QC_correction'
             and qp.get('status') == 'frozen_consumed_QC_correction'
             and qc.get('protocol_sha256') == qp['content_sha256']
             and qc.get('original_protocol_sha256') == qp.get('original_protocol_sha256') == protocol['content_sha256']
             and qc.get('new_independent_confirmation') is False
             and qc.get('original_confirmation_modified') is False and qc.get('new_winner_selected') is False
             and qc.get('memberships_source_weights_budgets_changed') is False
             and qc.get('scientific_accuracy_precision_direct_binding_established') is False,
             'Processed-reference check differs from the fixed original comparison.')
        need(set(qc['resolutions']) == {'strict_per_call', 'entry_family_per_call'}, 'Unexpected reference identity scopes.')
        for resolution, metrics_ in qc['resolutions'].items():
            n = metrics_['primary_unique_eligible_positive_pairs']
            need(type(n) is int and n >= 0 and set(metrics_['arms']) == set(LABELS)
                 and metrics_['raw_noncalls_evaluated'] is False
                 and metrics_['precision_or_scientific_accuracy_established'] is False,
                 'Unsupported processed-reference endpoint.')
            for arm, value in metrics_['arms'].items():
                k = value['positive_pairs_retained']
                need(type(k) is int and 0 <= k <= n and value['eligible_positive_pairs'] == n
                     and value['positive_pairs_lost'] == n-k
                     and value['micro_retention'] == (k/n if n else None)
                     and value['source_pairs_retained'] == arms[arm]['source_pairs_retained']
                     and value['source_pairs_removed'] == arms[arm]['source_pairs_removed']
                     and (arm != 'unpruned' or k == n), 'Processed-reference denominators or graph budgets differ.')
            sufficient_ = n >= protocol['minimum_eligible_positive_pairs'] and (
                metrics_['evaluable_exact_author_bait_ENSGs'] >= protocol['minimum_evaluable_exact_bait_labels'])
            gate_ = sufficient_ and all(metrics_['arms'][primary]['positive_pairs_retained'] >
                metrics_['arms'][control]['positive_pairs_retained'] for control in report['controls'])
            need(metrics_['coverage_gate_passed'] is sufficient_ and metrics_['posthoc_fixed_rule_met'] is gate_,
                 'Processed-reference descriptive gate differs from the saved endpoint.')
        current_qc = {'phase': 'Same-study author-processed QC correction; not another untouched confirmation',
            'strict': deepcopy(qc['resolutions']['strict_per_call']),
            'entry_family': deepcopy(qc['resolutions']['entry_family_per_call']),
            'protocol_sha256': qp['content_sha256'], 'result_sha256': qc['content_sha256'],
            'reference': qp['policy']['reference'], 'new_independent_confirmation': False}
    return {'format': FORMAT + '.summary', 'title': 'Experimental reference comparison',
        'reference': protocol['reference'], 'reference_resolution': 'Strict single-accession source mapping',
        'scope': report['claim_boundary'], 'source_graph_nodes': report['source_nodes_preserved'],
        'source_pairs': source['original_source_pairs'], 'qualified_eligible_pairs': source['qualified_rankable_pairs'],
        'ranked_view_pairs_retained': source['retained_rankable_budget'] + source['abstain_retained_pairs'],
        'source_pairs_removed_per_ranked_view': source['qualified_rankable_removals'],
        'eligible_retention_budget': source['retained_rankable_budget'],
        'positive_reference_pairs': count, 'primary_arm': primary, 'controls': report['controls'],
        'primary_utility_gate_passed': gate, 'decision': metrics['primary_decision'],
        'arms': deepcopy(arms), 'labels': dict(LABELS),
        'coverage': {key: deepcopy(metrics[key]) for key in ('native_call_rows_preserved', 'mapping_status_counts',
            'evaluation_category_row_counts', 'evaluable_exact_author_bait_labels', 'zero_denominator_bait_labels')},
        'protocol_sha256': protocol['content_sha256'], 'result_sha256': report['content_sha256'],
        'source_qualification_sha256': source['content_sha256'], 'sources': citations,
        'scientific_accuracy_established': False, 'graph_changes_performed_by_viewer': False,
        'current_processed_reference_check': current_qc,
        'interpretation': 'This compares retained author-reported coassociations at the same graph budget. It does not measure pruning precision, direct binding or colorectal-cancer validity.'}


def publish(assessment, frozen, qualification, selection, output, *, processed_qc=None):
    paths = {'report.json': Path(assessment) / 'report.json', 'protocol.json': Path(frozen) / 'protocol.json',
        'source_qualification.json': Path(qualification) / 'source_qualification.json',
        'selection_receipt.json': Path(selection) / 'selection_receipt.json'}
    files = {name: _bounded(path) for name, path in paths.items()}
    if processed_qc is not None:
        files['processed_qc_report.json'] = _bounded(Path(processed_qc) / 'results/report.json')
        files['processed_qc_protocol.json'] = _bounded(Path(processed_qc) / 'frozen/protocol.json')
    import json
    sources = {'raw_reference_rows_included': False,
        'reference_artifact': 'October2021 author figure-data significant-interaction file; not asserted equal to the final published interactome.',
        'primary_study': 'https://doi.org/10.1126/science.abi6983',
        'author_artifact': 'https://github.com/czbiohub-sf/2021-opencell-figures/blob/e0bedae07e6c1870f54c501bfa9a9120c8c38e09/data/ppi_analysis/precision_recall/opencell.csv',
        'historical_input': 'https://doi.org/10.1093/nar/gky1131',
        'source_terms': 'Raw reference tables are retrieved from their providers; this publication contains aggregate results and reproduction commitments.'}
    files['sources.json'] = (json.dumps(sources, indent=2) + '\n').encode()
    summary = _summary(files)
    folder = new_output(output, *(Path(p) for p in paths.values()))
    for name, raw in files.items():
        (folder / name).write_bytes(raw)
    manifest = {'format': FORMAT, 'created_at': utcnow(), 'summary': summary,
        'files': {name: hashlib.sha256(raw).hexdigest() for name, raw in files.items()},
        'read_only': True, 'raw_reference_rows_included': False, 'source_graph_modified': False}
    manifest['content_sha256'] = digest(manifest)
    write_json(folder / 'publication.json', manifest)
    return load_publication(folder)[0]


def load_publication(folder):
    folder = Path(folder)
    manifest = _decode(_bounded(folder / 'publication.json'))
    need(manifest.get('format') == FORMAT, 'Unsupported biological comparison publication.')
    names = {p.relative_to(folder).as_posix() for p in folder.rglob('*') if p.is_file()}
    need(names in (FILES | {'publication.json'}, FILES | QC_FILES | {'publication.json'}),
         'Biological comparison file inventory differs.')
    for name in names:
        _bounded(folder / name)
    manifest, files = _capture(folder, 'publication.json')
    summary = _summary(files)
    need(manifest.get('summary') == summary and manifest.get('raw_reference_rows_included') is False
         and manifest.get('read_only') is True and manifest.get('source_graph_modified') is False,
         'Biological comparison summary changed.')
    return manifest, summary, files


def list_publications(runs_dir):
    """List only validated small publications, without opening workspace graphs."""
    import re
    rows = []
    for folder in sorted(Path(runs_dir).iterdir(), reverse=True):
        if (folder.is_symlink() or not folder.is_dir()
                or not re.fullmatch(r'[A-Za-z0-9_-]{1,80}', folder.name)):
            continue
        try:
            candidate = _decode(_bounded(folder / 'publication.json'))
            if candidate.get('format') != FORMAT:
                continue
            _, summary, _ = load_publication(folder)
            rows.append({'id': folder.name, 'summary': summary})
        except (ValueError, TypeError, KeyError, OSError):
            continue
    return {'comparisons': rows}


def render_html(summary):
    esc = escape
    rows = []
    current = summary.get('current_processed_reference_check')
    displayed = current['strict']['arms'] if current else summary['arms']
    for arm, value in displayed.items():
        retention = 'Unscorable' if value['micro_retention'] is None else f"{100 * value['micro_retention']:.1f}%"
        rows.append('<tr><td>' + esc(summary['labels'][arm]) + '</td><td>' + str(value['positive_pairs_retained'])
            + ' / ' + str(value['eligible_positive_pairs']) + '</td><td>' + retention + '</td><td>'
            + str(value['source_pairs_retained']) + '</td><td>' + str(value['isolated_proteins']) + '</td></tr>')
    return ("<!doctype html><html lang='en'><meta charset='utf-8'><title>Experimental reference comparison</title>"
        "<style>body{font:17px system-ui;max-width:1100px;margin:2rem auto;padding:0 1rem;color:#203040}table{border-collapse:collapse;width:100%}td,th{padding:.7rem;border-bottom:1px solid #ccd5df;text-align:left}.scope{background:#fff3d8;padding:1rem}code{overflow-wrap:anywhere}a{color:#145588}</style>"
        '<h1>Experimental reference comparison</h1><p class=scope>'
        + (esc(current['phase']) + '. The rankings, primary method and graph budgets are unchanged.' if current else esc(summary['sources']['reference_artifact']))
        + '</p><p>' + esc(summary['interpretation'])
        + '</p><p>' + str(summary['source_graph_nodes']) + ' source proteins; '
        + str(summary['qualified_eligible_pairs']) + ' eligible pairs, with exactly '
        + str(summary['eligible_retention_budget']) + ' retained in each ranked view. Protected and quarantined records remain retained.</p>'
        + '<table><thead><tr><th>Graph view</th><th>Reference positives retained</th><th>Retention</th><th>Source pairs retained</th><th>Isolated proteins</th></tr></thead><tbody>'
        + ''.join(rows) + '</tbody></table>'
        + ('<p>Entry-family sensitivity: primary ' + str(current['entry_family']['arms']['human_experimental_top80']['positive_pairs_retained'])
            + '/' + str(current['entry_family']['primary_unique_eligible_positive_pairs']) + '; native '
            + str(current['entry_family']['arms']['native_top80']['positive_pairs_retained']) + '/' + str(current['entry_family']['primary_unique_eligible_positive_pairs'])
            + '. Entry resolution does not establish the exact isoform, sequence, gene of origin or construct.</p>' if current else '')
        + '<p>Most native reference rows could not be uniquely mapped under the strict rule. '
        + 'This is one HEK293T study, with no qualified negative reference and no whole-graph or cancer-specific accuracy estimate.</p>'
        + '<p>Exploratory comparators do not replace the preselected primary after evaluation. Subsequent connectivity safeguards are development checks.</p>'
        + '<p>The original ' + str(summary['positive_reference_pairs']) + '-pair figure-data assessment is retained in the downloadable original result. No source or assessment was overwritten.</p>'
        + '<p><a href="' + esc(summary['sources']['primary_study'], quote=True) + '">Primary OpenCell study</a> · '
        + ('<a href="https://opencell.sf.czbiohub.org/data/datasets/opencell-protein-interactions.csv">Author-processed reference table</a> · ' if current else '')
        + '<a href="' + esc(summary['sources']['author_artifact'], quote=True) + '">Historical figure-data artifact</a> · '
        + ('<a href="files/processed_qc_report.json">Current QC result</a> · <a href="files/processed_qc_protocol.json">Current QC protocol</a> · ' if current else '')
        + '<a href="files/report.json">Original result JSON</a> · <a href="files/protocol.json">Original frozen protocol</a></p>'
        + ('<p>Current QC protocol: <code>' + esc(current['protocol_sha256']) + '</code></p>' if current else '')
        + '<p>Original protocol: <code>' + esc(summary['protocol_sha256']) + '</code></p></html>')
