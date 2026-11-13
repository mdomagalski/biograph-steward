"""Small read-only scientific assessment, bound to seven aggregate receipts.

This is deliberately separate from the OpenCell publication. It checks saved
aggregate consistency and units, never recreates scientific labels, reads raw
experimental outcomes, chooses a graph or executes a scientific model.
"""
from copy import deepcopy
import hashlib
from html import escape
import math
from pathlib import Path
import re

from . import gold_packet
from .assay_attachment import _capture, _decode, _ordinary, _sealed
from .client import digest, utcnow, write_json
from .file_utils import new_output, sha

FORMAT = 'biograph-steward.scientific-assessment-publication.v1'
ROLES = {
    'history': 'biograph-steward.historical-WikiPathways-content-verification.v1',
    'wiki_policy': 'biograph-steward.source-faithful-historical-WikiPathways-decisions.v1',
    'composition': 'biograph-steward.source-qualification-composition.v1',
    'references': 'biograph-steward.bounded-reference-assessment-summary.v2',
    'utility': 'biograph-steward.wiki-utility-combined-assessment.v1',
    'current_score': 'biograph-steward.wiki-utility-development-score.v1',
    'historical_score': 'biograph-steward.wiki-utility-development-score.v1',
}
SOURCE_NAMES = {role: 'sources/' + role + '.json' for role in ROLES}
PUBLIC_FILES = frozenset({*SOURCE_NAMES.values(), 'report.html', 'README.txt'})
ARMS = ('normalized_unqualified', 'fixed_qualified', 'equal_count_random', 'qualified_degree_permutation')
ARM_LABELS = {'normalized_unqualified': 'Normalized source comparator', 'fixed_qualified': 'Qualified feature view',
    'equal_count_random': 'Equal-count random control', 'qualified_degree_permutation': 'Degree-preserving control'}
KINDS = {'current_release_eligibility': 'Current-release eligibility',
         'historical_native_xref_compatibility': 'Historical native xref compatibility'}
LITERATURE = [
    {'title': 'WikiPathways2024: version and source context', 'url': 'https://doi.org/10.1093/nar/gkad960'},
    {'title': 'GO annotation format and evidence codes', 'url': 'https://geneontology.org/docs/go-evidence-codes/'},
    {'title': 'CRC genomic cohort study', 'url': 'https://doi.org/10.1038/s41586-024-07747-9'},
    {'title': 'CIViC expert Assertion curation', 'url': 'https://docs.civicdb.org/en/latest/curating/assertions.html'},
    {'title': 'INMC primary study', 'url': 'https://doi.org/10.1038/s41467-023-37079-7'},
]
BOUNDARIES = [
    'Whole-graph scientific precision remains unidentified. Source encoding, experimental-curation compatibility, genomic cohort support and expert clinical conclusions are separate axes, with different denominators.',
    'UNKNOWN is preserved as unknown. Positive-only coverage does not supply verified negatives or justify a resolved-only accuracy percentage.',
    'Prospective prediction improvement is unproved. INMC is previously consumed development material; model seeds are not independent biological replicates.',
    'This viewer verifies copied aggregate receipts and declared input hashes. Complete native source/archive/registry and Gold replay remain in their separate workspace packages; no raw reference rows are published here.',
]
README = ('Scientific assessment publication\n\n'
    'This immutable snapshot contains seven copied aggregate producer receipts, their SHA256 commitments, '
    'a typed summary and its read-only HTML presentation. No raw experimental tables, native GPML, '
    'clinical records, model predictions or GPL source captures are included.\n\n'
    'The input hashes are operator-provided commitments, not publisher authentication or a new scientific review. '
    'The viewer checks aggregate consistency only. Source compatibility is not independent truth; UNKNOWN remains '
    'unknown. The INMC comparisons are consumed-reference development checks, not prospective confirmation. '
    'Full source, registry, archive and retained-graph reproduction requires the original workspace packages.\n')


def need(ok, message):
    if not ok:
        raise ValueError('Scientific assessment: ' + message)


def _bounded(path):
    path = Path(path)
    need(path.is_file() and not path.is_symlink() and path.stat().st_size <= 250_000,
         'only compact ordinary aggregate reports are accepted.')
    return _ordinary(path)


def _count(value):
    need(type(value) is int and value >= 0, 'a count must be a nonnegative integer.')
    return value


def _metric(value):
    need(type(value) in (int, float) and math.isfinite(value) and 0 <= value <= 1,
         'a saved metric must be a finite number between zero and one.')
    return value


def _summary(files, pins):
    need(set(pins) == set(ROLES) and all(isinstance(x, str) and re.fullmatch(r'[0-9a-f]{64}', x) for x in pins.values()),
         'provide one explicit file SHA256 pin for every source role.')
    reports = {}
    for role, format_name in ROLES.items():
        raw = files[SOURCE_NAMES[role]]
        need(hashlib.sha256(raw).hexdigest() == pins[role], 'copied report differs from its operator pin: ' + role)
        value = _decode(raw)
        need(_sealed(value) and value.get('format') == format_name, 'source format or content seal differs: ' + role)
        reports[role] = value
    h, w, c, r, u = [reports[k] for k in ('history', 'wiki_policy', 'composition', 'references', 'utility')]
    need(w['history_content_sha256'] == h['content_sha256'] and w['history_report_file_sha256'] == pins['history']
         and w['source_graph_file_sha256'] == h['source_graph_file_sha256']
         and w['packet_id'] == c['packet_id'] and w['graph_sha256'] == c['graph_sha256'],
         'history, Wiki policy and default composition are not bound to the same source.')
    need(w.get('source_graph_mutated') is False and w.get('scientific_review_states_promoted') is False
         and w.get('biological_truth_assessed') is False and w.get('missing_native_content_is_negative') is False
         and w.get('current_GMT_ablation_changed') is False and _count(w['counts']['prune']) == 0
         and c.get('source_graph_mutated') is False and c.get('biological_truth_adjudicated') is False,
         'expected source-faithful, unpromoted, nonbiological decisions.')
    inputs = {item['method']: item for item in c['inputs']}
    need(set(inputs) == {'current-go-primary-term-identifiers.v1', w['profile']}
         and inputs[w['profile']]['report_content_sha256'] == w['retained_content_sha256']
         and inputs[w['profile']]['report_file_sha256'] == w['files']['retained/report.json'],
         'default composition does not preserve the declared Wiki/GO policies.')
    rb = r['current_default_disposition_binding']
    need(rb['report_content_sha256'] == c['output_retained_report_content_sha256']
         and rb['report_file_sha256'] == c['output_retained_report_sha256']
         and rb['evidence_edge_counts'] == c['counts'], 'reference assessment belongs to a different retained view.')
    need(r.get('all_independent_scientific_truth_unreviewed') is True
         and r.get('source_graph_changed') is False and r.get('prediction_benefit_measured') is False
         and r.get('source_study_independence_established') is False,
         'bounded source/reference assessment scope changed.')
    hc = h['counts']
    statuses = hc['unique_connection_statuses']
    need(set(statuses) == {'explicitly_encoded_protein_xref', 'compatible_gene_level_xref', 'unresolved'},
         'native source scopes changed.')
    total_connections = _count(hc['original_unique_subject_version_connections'])
    protein, gene, unknown = [_count(statuses[k]) for k in ('explicitly_encoded_protein_xref', 'compatible_gene_level_xref', 'unresolved')]
    need(protein + gene + unknown == total_connections and w['counts']['native_positive_groups_replayed'] == protein + gene
         and h.get('scientific_accuracy_measured') is False and h.get('independent_reference') is False,
         'native content counts or interpretation differ.')
    versions, requested = _count(hc['exact_publisher_bound_versions']), _count(hc['requested_distinct_versions'])
    need(versions <= requested and hc['author_schema_passed_models'] == versions, 'native version denominator differs.')
    counts = {k: _count(c['counts'][k]) for k in ('keep', 'prune', 'abstain')}
    original_edges = sum(counts.values())
    need(original_edges == w['counts']['total_edges'], 'original evidence-row populations differ.')
    go, crc, civic = r['GO'], r['CRC_genomic_cohort'], r['CIViC']
    go_n, go_k, go_unknown = [_count(go[k]) for k in ('original_family_assertions', 'identified_compatible_experimental_assertions', 'remaining_GO_UNKNOWN')]
    crc_n, crc_k, crc_unknown = [_count(crc[k]) for k in ('original_disease_association_assertions', 'identified_exact_context_supported_assertions', 'UNKNOWN_assertions')]
    need(go_k + go_unknown == go_n and go['removed_assertions'] == counts['prune']
         and rb['current_pruned_assertions'] == counts['prune'] and go.get('all_373_identified_compatible_assertions_retained') is True
         and go.get('reference_positive_eligibility_makes_resolved_only_ratio_uninformative') is True,
         'GO family denominator or current-view scope differs.')
    need(crc_k + crc_unknown == crc_n and crc.get('all32_retained_in_source_faithful_default') is True
         and crc.get('negative_labels_assigned') == 0 and crc.get('unseen_confirmatory_holdout') is False
         and crc.get('heterogeneous_GO_and_genomics_axes_pooled') is False,
         'CRC source cohort must remain a separate positive-support axis.')
    civic_n, civic_k = _count(civic['original_reported_response_assertions']), _count(civic['clinical_accuracy_resolved'])
    need(civic_k == 0 and civic.get('exact_context_matched_edges') == 0
         and civic.get('complete_native_conclusions_preserved_in_separate_layer') is True
         and civic.get('aggregate_conclusions_replace_original_observations') is False,
         'expert aggregate conclusions must not replace unmatched observations.')
    native = u['native_source_finding']
    need(native['verified_model_versions'] == versions and native['requested_versions'] == requested
         and native['original_unique_connections'] == total_connections
         and native['literal_protein_xref_connections'] == protein and native['compatible_gene_xref_connections'] == gene
         and native['unknown_connections'] == unknown and u.get('graph_mutated') is False
         and u.get('new_biology_discovery_claimed') is False, 'utility summary and native source scope differ.')
    endpoint = u['endpoint_scope']
    need(endpoint.get('reference_previously_consumed') is True
         and endpoint.get('non_detection_is_universal_noninteraction') is False
         and endpoint.get('seeds_are_independent_biological_replicates') is False
         and endpoint.get('whole_graph_scientific_accuracy_measured') is False
         and endpoint.get('formal_confidence_interval') is None and endpoint.get('p_values') is None,
         'INMC must remain a consumed, task-specific descriptive comparison.')
    n, detected, nondetected = [_count(endpoint[k]) for k in ('primary_measured_QC_eligible_off_diagonal_pairs', 'detected', 'conditional_nondetected')]
    need(detected + nondetected == n, 'recorded-assay endpoint denominator differs.')
    experiments = []
    need({e['qualification_kind'] for e in u['experiments']} == set(KINDS) and len(u['experiments']) == 2,
         'include both declared INMC comparisons exactly once.')
    for experiment in u['experiments']:
        kind = experiment['qualification_kind']
        score_role = 'current_score' if kind == 'current_release_eligibility' else 'historical_score'
        score = reports[score_role]
        need(experiment['scores_report_file_sha256'] == pins[score_role]
             and experiment['scores_content_sha256'] == score['content_sha256']
             and experiment['frozen_packet_report_file_sha256'] == score['packet_report_sha256']
             and score.get('retrospective_consumed_reference') is True and score.get('fresh_independent_confirmation') is False
             and score.get('scientific_truth_accuracy_measured') is False and experiment.get('fresh_confirmation') is False
             and experiment['primary_eligible_pairs'] == n and experiment['positive_count'] == detected
             and experiment['conditional_nondetection_count'] == nondetected, 'INMC score receipt/endpoint binding differs.')
        arms = {a['arm']: a for a in experiment['arms']}
        need(set(arms) == set(ARMS) and len(experiment['arms']) == len(ARMS), 'INMC control arms differ.')
        compact = []
        for arm in ARMS:
            row = arms[arm]
            need(set(row['AP_by_seed']) == set(row['AUROC_by_seed']) == {'17', '43', '101'}, 'expected the three fixed model seeds.')
            ap, auroc = _metric(row['mean_AP']), _metric(row['mean_AUROC'])
            need(all(math.isclose(sum(_metric(x) for x in row[key].values()) / 3, mean, rel_tol=1e-12, abs_tol=1e-12)
                     for key, mean in [('AP_by_seed', ap), ('AUROC_by_seed', auroc)]), 'saved aggregate mean differs from its source seeds.')
            compact.append({'arm': arm, 'label': ARM_LABELS[arm], 'unique_memberships': _count(row['unique_memberships']),
                'mean_AP': ap, 'mean_AUROC': auroc, 'AP_by_seed': deepcopy(row['AP_by_seed']), 'AUROC_by_seed': deepcopy(row['AUROC_by_seed'])})
        experiments.append({'kind': kind, 'title': KINDS[kind], 'unit': 'recorded assay-QC-eligible protein pairs',
            'pairs': n, 'seeds': [17, 43, 101], 'arms': compact,
            'paired_deltas_by_seed': deepcopy(experiment['paired_deltas_by_seed']),
            'fresh_confirmation': False, 'proof_role': score_role})
    return {'format': FORMAT + '.summary', 'title': 'Scientific assessment',
        'scope': 'Current scoped source workspace; source support and biological prediction are assessed separately.',
        'packet_id': c['packet_id'], 'graph_sha256': c['graph_sha256'],
        'whole_graph_scientific_precision': None, 'prospective_prediction_gain_established': False,
        'native_history': {'unit': 'distinct exact pathway-model revisions', 'verified': versions, 'requested': requested,
            'unresolved': requested - versions, 'connection_unit': 'unique original protein/version source connections',
            'original_connections': total_connections, 'literal_protein_xref': protein, 'compatible_gene_xref': gene,
            'source_compatible_connections': protein + gene, 'unknown_connections': unknown,
            'interpretation': 'Native identifier encoding and current-registry gene compatibility are separate. Neither establishes universal protein function or independent biology.'},
        'default_view': {'unit': 'original evidence rows', 'original': original_edges, 'retained': counts['keep'] + counts['abstain'],
            'GO_identifier_currency_excluded': counts['prune'], 'dispositions': counts, 'Wiki_UNKNOWN_retained': True,
            'retained_report_content_sha256': c['output_retained_report_content_sha256'],
            'interpretation': 'Source-faithful default: obsolete-GO identifier exclusions only; unresolved Wiki context is retained. No source or review promotion occurs.'},
        'GO': {'unit': 'original GO assertions', 'compatible_experimental': go_k, 'original': go_n, 'UNKNOWN': go_unknown,
            'all_identified_compatible_retained': True, 'ontology_release': go['ontology_release'], 'GAF_generated': go['source_generated'],
            'interpretation': 'Experimental-curation-compatible coverage; GOA/source lineage may be shared, so this is not independent experimental confirmation. Whole-family UNKNOWNs remain unresolved. Releases are pinned to July2026.'},
        'CRC_cohort': {'unit': 'original disease-association assertions', 'supported': crc_k, 'original': crc_n, 'UNKNOWN': crc_unknown,
            'specimens': _count(crc['specimens']), 'participants': _count(crc['distinct_participants']),
            'interpretation': 'Published statistical putative-driver cohort support, with model priors. This is not expert gold, causal protein evidence or an independent holdout.'},
        'CIViC': {'expert_clinical_conclusions': _count(civic['expert_accepted_clinical_Assertions']),
            'unit': 'original response assertions', 'original': civic_n, 'exact_original_contexts_resolved': civic_k, 'UNKNOWN': civic_n - civic_k,
            'interpretation': 'Expert accepted clinical conclusions are preserved separately; unmatched evidence-level observations are not upgraded into those aggregate conclusions.'},
        'INMC': {'unit': 'recorded measured protein pairs', 'eligible_pairs': n, 'detected': detected, 'conditional_nondetected': nondetected,
            'interpretation': u['conclusion'], 'decision': u['production_decision'], 'experiments': experiments,
            'scope': 'Previously consumed retrospective assay recovery; sparse direct Wiki overlap and indirect graph-message effects. Three seeds are computational repeats, not biological replicates.'},
        'remaining_gaps': list(BOUNDARIES), 'literature': deepcopy(LITERATURE),
        'sources': [{'role': role, 'file': SOURCE_NAMES[role], 'file_sha256': pins[role], 'content_sha256': reports[role]['content_sha256']} for role in ROLES],
        'raw_reference_rows_included': False, 'scientific_labels_created': False, 'graph_modified_by_viewer': False}


def publish(source_reports, output, *, expected_source_pins):
    """Publish one curated snapshot using explicit operator-selected input pins."""
    need(isinstance(source_reports, dict) and set(source_reports) == set(ROLES), 'supply exactly the seven aggregate source roles.')
    implementation_pin = sha(__file__)
    paths = {role: Path(path) for role, path in source_reports.items()}
    files = {SOURCE_NAMES[role]: _bounded(path) for role, path in paths.items()}
    summary = _summary(files, expected_source_pins)
    folder = new_output(output, *paths.values())
    for name, raw in files.items():
        target = folder / name
        target.parent.mkdir(exist_ok=True)
        target.write_bytes(raw)
    files['README.txt'] = README.encode()
    files['report.html'] = render_html(summary).encode()
    for name in ('README.txt', 'report.html'):
        (folder / name).write_bytes(files[name])
    need(all(_bounded(paths[role]) == files[SOURCE_NAMES[role]] for role in ROLES)
         and sha(__file__) == implementation_pin, 'source or implementation changed during publication.')
    manifest = {'format': FORMAT, 'created_at': utcnow(), 'summary': summary,
        'operator_source_pins': dict(expected_source_pins), 'input_pins_authenticate_publisher': False,
        'files': {name: hashlib.sha256(raw).hexdigest() for name, raw in files.items()},
        'producer_implementation_sha256': implementation_pin, 'read_only': True,
        'raw_reference_rows_included': False, 'scientific_labels_created': False, 'source_graph_modified': False}
    manifest['content_sha256'] = digest(manifest)
    write_json(folder / 'publication.json', manifest)
    try:
        return load_publication(folder)[0]
    except Exception:
        (folder / 'publication.json').unlink(missing_ok=True)
        raise


def load_publication(folder):
    """Reproduce typed aggregates from copied receipts; never open raw data."""
    folder = Path(folder)
    need(folder.is_dir() and not folder.is_symlink(), 'publication directory is unavailable or symlinked.')
    folder = folder.resolve()
    names = {p.relative_to(folder).as_posix() for p in folder.rglob('*') if p.is_file()}
    need(names == PUBLIC_FILES | {'publication.json'} and not any(p.is_symlink() for p in folder.rglob('*')),
         'publication contains missing or additional files.')
    for name in names:
        _bounded(folder / name)
    manifest, captured = _capture(folder, 'publication.json')
    need(manifest.get('format') == FORMAT and all(manifest.get(k) is False for k in (
         'raw_reference_rows_included', 'scientific_labels_created', 'source_graph_modified', 'input_pins_authenticate_publisher'))
         and manifest.get('read_only') is True, 'publication policy or format changed.')
    summary = _summary(captured, manifest['operator_source_pins'])
    need(manifest.get('summary') == summary and captured['README.txt'] == README.encode()
         and captured['report.html'] == render_html(summary).encode(), 'publication summary or presentation differs from its receipts.')
    return manifest, summary, captured


def list_publications(runs_dir):
    rows = []
    for folder in sorted(Path(runs_dir).iterdir(), reverse=True):
        if folder.is_symlink() or not folder.is_dir() or not re.fullmatch(r'[A-Za-z0-9_-]{1,80}', folder.name):
            continue
        path = folder / 'publication.json'
        if not path.is_file() or path.stat().st_size > 250_000:
            continue
        try:
            if _decode(_bounded(path)).get('format') != FORMAT:
                continue
            manifest, summary, _ = load_publication(folder)
            rows.append({'id': folder.name, 'created_at': manifest['created_at'], 'content_sha256': manifest['content_sha256'], 'summary': summary})
        except (ValueError, TypeError, KeyError, OSError):
            continue
    return {'assessments': rows}


def render_html(summary):
    """Escape every value; source-proof links name only the seven copied JSONs."""
    e = escape
    n, v, go, crc, cv, im = [summary[k] for k in ('native_history', 'default_view', 'GO', 'CRC_cohort', 'CIViC', 'INMC')]
    text = lambda value: e(str(value), quote=True)
    parts = ["<!doctype html><html lang='en'><meta charset='utf-8'><title>Scientific assessment</title>"
        "<style>body{font:16px system-ui;max-width:1050px;margin:2rem auto;padding:0 1rem;color:#203040}"
        "table{border-collapse:collapse;width:100%}td,th{padding:.6rem;border-bottom:1px solid #ccd5df;text-align:left}"
        "code{overflow-wrap:anywhere}.scope{padding:1rem;background:#fff1d5}h2{margin-top:2rem}</style>",
        '<h1>Scientific assessment</h1><p class=scope>Whole-graph scientific precision remains unidentified. Prospective prediction improvement is unproved.</p>',
        '<p>' + text(summary['scope']) + '</p><h2>Source and reference coverage</h2><table><tr><th>Axis</th><th>Result and unit</th><th>Remaining uncertainty</th></tr>',
        '<tr><td>Native Wiki history</td><td>' + text(n['verified']) + '/' + text(n['requested']) + ' exact model revisions; '
            + text(n['source_compatible_connections']) + '/' + text(n['original_connections']) + ' source connections ('
            + text(n['literal_protein_xref']) + ' literal protein; ' + text(n['compatible_gene_xref']) + ' gene compatible)</td><td>'
            + text(n['unknown_connections']) + ' connections UNKNOWN</td></tr>',
        '<tr><td>Default retained view</td><td>' + text(v['retained']) + '/' + text(v['original']) + ' original evidence rows</td><td>'
            + text(v['GO_identifier_currency_excluded']) + ' GO identifier-currency exclusions; Wiki UNKNOWN retained</td></tr>',
        '<tr><td>GO experimental curation</td><td>' + text(go['compatible_experimental']) + '/' + text(go['original']) + ' original GO assertions compatible</td><td>'
            + text(go['UNKNOWN']) + ' UNKNOWN; coverage, not scientific precision</td></tr>',
        '<tr><td>CRC genomic cohort</td><td>' + text(crc['supported']) + '/' + text(crc['original']) + ' original disease assertions with exact context support</td><td>'
            + text(crc['UNKNOWN']) + ' UNKNOWN; statistical cohort source, not expert gold</td></tr>',
        '<tr><td>CIViC expert conclusions</td><td>' + text(cv['expert_clinical_conclusions']) + ' separate conclusions; '
            + text(cv['exact_original_contexts_resolved']) + '/' + text(cv['original']) + ' original response contexts resolved</td><td>'
            + text(cv['UNKNOWN']) + ' original assertions unresolved by this layer</td></tr></table>']
    for key in ('native_history', 'default_view', 'GO', 'CRC_cohort', 'CIViC'):
        parts.append('<p>' + text(summary[key]['interpretation']) + '</p>')
    parts.append('<p>GO ontology release ' + text(go['ontology_release']) + '; GAF generated ' + text(go['GAF_generated']) + '.</p>')
    parts.append('<h2>Recorded-assay recovery: development comparison</h2><p>' + text(im['interpretation']) + '</p><p>'
        + text(im['eligible_pairs']) + ' measured eligible pairs: ' + text(im['detected']) + ' detected, '
        + text(im['conditional_nondetected']) + ' conditional non-detections. Values below are three-seed means.</p>')
    for experiment in im['experiments']:
        parts.append('<h3>' + text(experiment['title']) + '</h3><table><tr><th>Feature view</th><th>Unique memberships</th><th>Mean AP</th><th>Mean AUROC</th></tr>')
        for row in experiment['arms']:
            parts.append('<tr><td>' + text(row['label']) + '</td><td>' + text(row['unique_memberships']) + '</td><td>'
                + text(format(row['mean_AP'], '.6f')) + '</td><td>' + text(format(row['mean_AUROC'], '.6f')) + '</td></tr>')
        parts.append('</table>')
    parts += ['<p>' + text(im['scope']) + '</p><p>' + text(im['decision']) + '</p><h2>Limits and proof</h2><ul>']
    parts += ['<li>' + text(item) + '</li>' for item in summary['remaining_gaps']]
    parts += ['</ul><p>Graph: <code>' + text(summary['graph_sha256']) + '</code></p><ul>']
    parts += ['<li><a href="files/' + text(item['file']) + '">' + text(item['role']) + ' source receipt</a>: <code>'
              + text(item['file_sha256']) + '</code></li>' for item in summary['sources']]
    parts += ['</ul><p>' + ' · '.join('<a href="' + text(item['url']) + '" rel="noreferrer">' + text(item['title']) + '</a>'
                                    for item in summary['literature']) + '</p></html>']
    return ''.join(parts)
