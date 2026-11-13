"""Read-only scientific assessment with optional source-bound aggregate components.

This is deliberately separate from the OpenCell publication. It checks saved
aggregate consistency and units, never recreates scientific labels, reads raw
experimental outcomes, chooses a graph or executes a scientific model.
"""
from copy import deepcopy
import hashlib
from html import escape
import json
import math
from pathlib import Path
import re
import statistics

from . import gold_packet
from .assay_attachment import _capture, _decode, _ordinary, _sealed
from .client import digest, utcnow, write_json
from .file_utils import new_output, sha

FORMAT = 'biograph-steward.scientific-assessment-publication.v1'
FORMAT_V2 = 'biograph-steward.scientific-assessment-publication.v2'
FORMAT_V3 = 'biograph-steward.scientific-assessment-publication.v3'
GROUNDING_FORMAT = 'biograph-steward.expert-grounding-aggregate.v1'
GROUNDING_FILE = 'sources/grounding.json'
GROUNDING_ARMS = ('lexical', 'sentence', 'publication')
GROUNDING_GOLDS = ('grounding_error', 'correctly_grounded')
GROUNDING_STATUSES = ('candidate_conflict', 'no_conflict', 'unresolved', 'model_error')
GROUNDING_METRICS = ('precision', 'error_recall', 'false_conflict_rate', 'coverage', 'resolved_accuracy')
GROUNDING_SCOPE = ('Expert-curator-relative human-gene grounding-error triage in a published '
    'stratified mechanistic extraction corpus. Not whole-Pharos precision, protein-form '
    'validation, independent experimental biology or a biological prediction gain. '
    'The grounder merges gene/protein names; its training-paper overlap is unestablished. '
    'A candidate conflict is a review proposal, not a validated replacement or prune.')
GROUNDING_FLAGS = ('native_grounder_training_paper_independence_established',
    'automatic_corrections_or_prunes_performed', 'new_gold_labels_created',
    'underlying_biological_truth_measured', 'whole_graph_accuracy_estimated',
    'source_graph_or_original_reference_changed')
GROUNDING_REFERENCE = {'DOI': '10.15252/msb.202211325', 'Zenodo': 7559353,
    'data_license': 'CC-BY-NC-SA-4.0', 'expert_labels_assigned_by_project_AI': False}
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
COESS_NAMES = {role: 'sources/coess_' + role + '.json'
               for role in ('score', 'frozen', 'capture', 'curves', 'controls')}
V2_PUBLIC_FILES = PUBLIC_FILES | frozenset(COESS_NAMES.values())
ALL_PUBLIC_FILES = V2_PUBLIC_FILES | {GROUNDING_FILE}
COESS_SCOPES = ('nonsyntenic', 'all', 'syntenic', 'nonsyntenic_positive', 'nonsyntenic_negative')
COESS_INTERPRETATION = ('Source qualification did not show a consistent advantage over normalized source context '
    'and the fixed count and degree controls across the complete primary N=1–10 curves.')
COESS_BOUNDARY = ('Historical pan-cancer DepMap18Q3 fitness concordance, not a CRC-specific reference, physical '
    'binding, whole-graph scientific accuracy or proven prediction improvement. This exploratory reference is now '
    'consumed; possible indirect curation reuse and GO-assisted preprocessing remain disclosed. Two-sided native '
    'P ranks are not edge-truth probabilities or biological negative labels. Twenty control draws give descriptive '
    'ranges, not confidence intervals, calibrated null probabilities or significance.')
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
README_V2 = README + ('\nThe optional v2 extension copies five bounded coessentiality aggregate/provenance '
    'files. Complete curves preserve all 87 arms, five declared scopes and N=1–10. Native pair values, '
    'per-query labels and matrix payloads are excluded. Source/freeze/capture bindings are checked; '
    'no scoring, model fitting, endpoint selection or new scientific labels occur in this viewer.\n')
README_GROUNDING = ('\nThe optional v3 grounding component copies one strictly aggregate-only projection '
    'of a previously scored expert-curation component evaluation. Original case IDs, native curation tags, '
    'source statements, names, text and individual predictions are excluded. Native reference licensing '
    'and evaluator/freeze SHA256 commitments remain explicit. Error recall and false-conflict rate '
    'retain all admitted cases of their respective gold class, including abstentions; resolved-only '
    'accuracy and the common-resolved subset are labeled secondary. This task is not pooled with '
    'graph coverage, whole-graph biological accuracy or prediction improvement.\n')


def need(ok, message):
    if not ok:
        raise ValueError('Scientific assessment: ' + message)


def _bounded(path, *, limit=250_000):
    path = Path(path)
    need(path.is_file() and not path.is_symlink() and path.stat().st_size <= limit,
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


def _coessentiality_summary(files, pins, base_utility):
    """Project already-scored aggregates; never open pair values or matrices."""
    need(set(pins) == set(COESS_NAMES) and all(isinstance(pin, str) and re.fullmatch(r'[0-9a-f]{64}', pin)
         for pin in pins.values()), 'provide an explicit file pin for each coessentiality aggregate.')
    values = {}
    for role, name in COESS_NAMES.items():
        raw = files[name]
        need(len(raw) <= 3_000_000 and hashlib.sha256(raw).hexdigest() == pins[role],
             'coessentiality aggregate differs from its size bound or operator pin: ' + role)
        values[role] = _decode(raw)
    score, frozen, capture, curves, controls = [values[k] for k in COESS_NAMES]
    for role, expected in (
        ('score', 'biograph-steward.coessentiality-functional-concordance.v1'),
        ('frozen', 'biograph-steward.coessentiality-frozen-comparison.v1'),
        ('capture', 'biograph-steward.coessentiality-native-column-capture.v1'),
    ):
        need(_sealed(values[role]) and values[role].get('format') == expected,
             'coessentiality receipt format or seal differs: ' + role)
    experiment_seals = {e['qualification_kind']: e['frozen_packet_content_sha256']
                        for e in base_utility['experiments']}
    need(frozen['source_current_content_sha256'] == experiment_seals['current_release_eligibility']
         and frozen['source_historical_content_sha256'] == experiment_seals['historical_native_xref_compatibility'],
         'coessentiality study graph differs from the base utility comparisons.')
    need(score['frozen_comparison_content_sha256'] == frozen['content_sha256']
         and score['native_capture_content_sha256'] == capture['content_sha256']
         and capture['frozen_comparison_content_sha256'] == frozen['content_sha256']
         and capture['frozen_report_file_sha256'] == pins['frozen']
         and len(score['input_report_file_sha256']) == 2
         and set(score['input_report_file_sha256'].values()) == {pins['frozen'], pins['capture']},
         'coessentiality score, frozen transport continuation and native capture differ.')
    need(score['files']['curves.json'] == pins['curves']
         and score['files']['descriptive_control_envelopes.json'] == pins['controls'],
         'coessentiality curves or controls differ from the sealed scorer inventory.')
    need(frozen.get('source_deep_replay_completed') is True
         and frozen.get('scientific_packet_unchanged_since_original_pre_value_freeze') is True
         and re.fullmatch(r'[0-9a-f]{64}', frozen['original_pre_value_scientific_freeze_content_sha256'])
         and re.fullmatch(r'[0-9a-f]{64}', frozen['transport_repair_content_sha256'])
         and capture.get('full_matrix_files_retrieved_or_hashed') is False
         and score.get('all_N_and_all_arms_reported') is True
         and all(score.get(k) is False for k in ('scientific_truth_labels_created',
             'PPIs_or_causal_mechanisms_inferred', 'model_fitted_or_graph_changed', 'FDR_or_significance_reconstructed')),
         'coessentiality source scope or nonbiological interpretation changed.')
    query_n = _count(score['query_genes'])
    pair_n = _count(score['pair_scope_counts']['nonsyntenic'])
    need(query_n == 92 and pair_n == 3968 and score['pair_scope_counts']['syntenic'] == 218,
         'the declared coessentiality measured-query/pair frame differs.')
    need(set(curves) == set(frozen['arm_membership_counts']) and len(curves) == 87
         and all(set(scopes) == set(COESS_SCOPES) for scopes in curves.values()),
         'preserve all 87 frozen arms and five declared scopes.')
    for scopes in curves.values():
        for points in scopes.values():
            need([p['N'] for p in points] == list(range(1, 11))
                 and all(p['query_frame'] == query_n for p in points), 'coessentiality N/query frame differs.')
            for point in points:
                for name in ('observed_hit_fraction', 'expected_hit_fraction'):
                    if point[name] is not None:
                        _metric(point[name])
                need(point['enrichment'] is None or (type(point['enrichment']) in (int, float)
                     and math.isfinite(point['enrichment']) and point['enrichment'] >= 0),
                     'coessentiality enrichment must be nonnegative, finite or undefined.')
    primary = {arm: deepcopy(curves[arm]['nonsyntenic']) for arm in ('normalized', 'current', 'historical')}
    need(all(p['reference_available_queries'] == query_n and p['unavailable_queries'] == 0
         and p['selected_slots_if_reference_available'] == query_n * p['N']
         and p['aggregation'] == 'all_fixed_queries' for points in primary.values() for p in points),
         'primary coessentiality curves must retain all fixed query slots.')
    projected_controls = {}
    need(set(controls) == {'current', 'historical'}, 'coessentiality treatment controls differ.')
    for treatment in ('current', 'historical'):
        need(set(controls[treatment]) == {'count', 'degree'}, 'coessentiality count/degree controls differ.')
        projected_controls[treatment] = {}
        assessment = score['full_curve_descriptive_assessment'][treatment]
        need(assessment.get('is_statistical_significance_or_generalized_biological_gain') is False
             and assessment.get('pointwise_above_baseline_and_all_controls_at_every_N') is False
             and [p['N'] for p in assessment['points']] == list(range(1, 11)),
             'the recorded negative descriptive full-curve finding differs.')
        for kind in ('count', 'degree'):
            need(set(controls[treatment][kind]) == set(COESS_SCOPES), 'control diagnostic scopes differ.')
            names = [f'{treatment}_{kind}_{i:02}' for i in range(20)]
            selected = []
            for scope in COESS_SCOPES:
                envelope = controls[treatment][kind][scope]
                need([p['N'] for p in envelope] == list(range(1, 11)), 'control envelope N differs.')
                for index, point in enumerate(envelope):
                    vals = [curves[arm][scope][index]['enrichment'] for arm in names]
                    valid = [x for x in vals if x is not None]
                    expected = [min(valid), statistics.median(valid), max(valid)] if valid else [None] * 3
                    actual = [point[k] for k in ('minimum', 'median', 'maximum')]
                    need(point['draws'] == 20 and point['defined_draws'] == len(valid)
                         and point.get('not_a_confidence_interval') is True
                         and all(a == b or (a is not None and b is not None
                             and math.isclose(a, b, rel_tol=1e-12, abs_tol=1e-12)) for a, b in zip(actual, expected)),
                         'control envelope does not reproduce its saved aggregate draws.')
                    if scope == 'nonsyntenic':
                        fractions = [curves[arm][scope][index]['observed_hit_fraction'] for arm in names]
                        available = [x for x in fractions if x is not None]
                        selected.append({**deepcopy(point), 'absolute_hit_fraction': {
                            'minimum': min(available) if available else None,
                            'median': statistics.median(available) if available else None,
                            'maximum': max(available) if available else None,
                            'defined_draws': len(available)}})
            projected_controls[treatment][kind] = selected
    return {'title': 'Experimental fitness concordance: frozen exploratory comparison',
        'interpretation': COESS_INTERPRETATION, 'scope': COESS_BOUNDARY,
        'query_genes': query_n, 'primary_pairs': pair_n, 'primary_scope': 'nonsyntenic',
        'N': list(range(1, 11)), 'arm_count': len(curves), 'scope_count': len(COESS_SCOPES),
        'primary_curves': primary, 'controls': projected_controls, 'control_draws_per_kind': 20,
        'all_diagnostic_scopes': list(COESS_SCOPES), 'reference_now_consumed': True,
        'independent_scientific_truth_assessed': False, 'prediction_gain_established': False,
        'biological_negatives_assigned': False, 'raw_pair_or_matrix_values_included': False,
        'scorer_content_sha256': score['content_sha256'],
        'frozen_content_sha256': frozen['content_sha256'], 'capture_content_sha256': capture['content_sha256'],
        'original_pre_value_freeze_content_sha256': frozen['original_pre_value_scientific_freeze_content_sha256'],
        'transport_repair_content_sha256': frozen['transport_repair_content_sha256'],
        'transport_exposure_scope': frozen['preexisting_exposure_scope'],
        'source_current_content_sha256': frozen['source_current_content_sha256'],
        'source_historical_content_sha256': frozen['source_historical_content_sha256'],
        'limitations': deepcopy(score['limitations']),
        'sources': [{'role': 'coess_' + role, 'file': name, 'file_sha256': pins[role],
                     'content_sha256': values[role].get('content_sha256')}
                    for role, name in COESS_NAMES.items()]}


def _keys(value, names, description):
    need(isinstance(value, dict) and set(value) == set(names), description + ' fields differ; only aggregates are accepted.')


def _pin(value):
    need(isinstance(value, str) and re.fullmatch(r'[0-9a-f]{64}', value), 'an explicit SHA256 pin is required.')
    return value


def _grounding_metrics(value, *, expected_n=None, expected_gold=None):
    """Check arithmetic from saved counts, without reconstructing case labels."""
    _keys(value, ('n_cases', 'gold_counts', 'status_counts', 'resolved_cases', 'abstention_cases',
        'confusion_resolved', 'abstentions_by_gold', 'metric_numerators', 'metric_denominators',
        *GROUNDING_METRICS), 'grounding metrics')
    n = _count(value['n_cases'])
    _keys(value['gold_counts'], GROUNDING_GOLDS, 'grounding endpoint classes')
    _keys(value['status_counts'], GROUNDING_STATUSES, 'grounding statuses')
    _keys(value['confusion_resolved'], ('TP', 'FP', 'FN', 'TN'), 'resolved confusion')
    _keys(value['abstentions_by_gold'], GROUNDING_GOLDS, 'grounding abstentions')
    gold = {k: _count(v) for k, v in value['gold_counts'].items()}
    status = {k: _count(v) for k, v in value['status_counts'].items()}
    confusion = {k: _count(v) for k, v in value['confusion_resolved'].items()}
    abstentions = value['abstentions_by_gold']
    for row in abstentions.values():
        _keys(row, ('unresolved', 'model_error'), 'abstention reasons')
        for count in row.values():
            _count(count)
    resolved = sum(confusion.values())
    need(sum(gold.values()) == sum(status.values()) == n
         and _count(value['resolved_cases']) == resolved
         and _count(value['abstention_cases']) == n - resolved
         and gold['grounding_error'] == confusion['TP'] + confusion['FN'] + sum(abstentions['grounding_error'].values())
         and gold['correctly_grounded'] == confusion['FP'] + confusion['TN'] + sum(abstentions['correctly_grounded'].values())
         and status['candidate_conflict'] == confusion['TP'] + confusion['FP']
         and status['no_conflict'] == confusion['FN'] + confusion['TN']
         and all(status[k] == sum(row[k] for row in abstentions.values()) for k in ('unresolved', 'model_error')),
         'grounding full-denominator counts or abstentions differ.')
    need((expected_n is None or n == expected_n) and (expected_gold is None or gold == expected_gold),
         'grounding methods do not retain the same admitted endpoint denominator.')
    nums = {'precision': confusion['TP'], 'error_recall': confusion['TP'],
        'false_conflict_rate': confusion['FP'], 'coverage': resolved,
        'resolved_accuracy': confusion['TP'] + confusion['TN']}
    dens = {'precision': confusion['TP'] + confusion['FP'], 'error_recall': gold['grounding_error'],
        'false_conflict_rate': gold['correctly_grounded'], 'coverage': n, 'resolved_accuracy': resolved}
    for field, expected in (('metric_numerators', nums), ('metric_denominators', dens)):
        _keys(value[field], GROUNDING_METRICS, field)
        need({k: _count(v) for k, v in value[field].items()} == expected, 'grounding metric denominators or numerators differ.')
    for name in GROUNDING_METRICS:
        actual = value[name]
        need((actual is None and dens[name] == 0) or (dens[name] > 0 and actual is not None
             and math.isclose(_metric(actual), nums[name] / dens[name], rel_tol=1e-12, abs_tol=1e-12)),
             'grounding ratio differs or an undefined value was replaced.')
    return deepcopy(value)


def _grounding_receipt(value):
    """Accept only a compact aggregate schema; case/tag/text payloads fail closed."""
    fields = ('format', 'created_at', 'scope', 'reference', 'split', 'primary_frame_cases',
        'admitted_endpoint_cases', 'outside_endpoint_cases', 'metrics_by_arm', 'common_resolved_secondary',
        'paired_comparisons', 'source_report_file_sha256', 'source_report_content_sha256',
        'evaluation_freeze_content_sha256', 'evaluator_implementation_sha256', 'scoring_helper_sha256',
        'aggregate_producer_implementation_sha256', 'raw_reference_rows_or_case_ids_included',
        'native_curation_tags_included', *GROUNDING_FLAGS, 'content_sha256')
    _keys(value, fields, 'grounding receipt')
    need(_sealed(value) and value['format'] == GROUNDING_FORMAT and value['scope'] == GROUNDING_SCOPE
         and value['reference'] == GROUNDING_REFERENCE and value['split'] in {'development', 'test'}
         and isinstance(value['created_at'], str) and value['created_at']
         and all(value[k] is False for k in (*GROUNDING_FLAGS,
             'raw_reference_rows_or_case_ids_included', 'native_curation_tags_included')),
         'grounding reference or separate component scope changed.')
    for name in ('source_report_file_sha256', 'source_report_content_sha256', 'evaluation_freeze_content_sha256',
                 'evaluator_implementation_sha256', 'scoring_helper_sha256', 'aggregate_producer_implementation_sha256'):
        _pin(value[name])
    n = _count(value['admitted_endpoint_cases'])
    need(n + _count(value['outside_endpoint_cases']) == _count(value['primary_frame_cases']),
         'grounding frame and outside-endpoint denominator differ.')
    metrics = value['metrics_by_arm']
    _keys(metrics, GROUNDING_ARMS, 'fixed grounding arms')
    gold = None
    for arm in GROUNDING_ARMS:
        _grounding_metrics(metrics[arm], expected_n=n, expected_gold=gold)
        gold = metrics[arm]['gold_counts']
    common = value['common_resolved_secondary']
    _keys(common, ('scope', 'primary', 'n_cases', 'not_a_replacement_for_full_denominator', 'metrics_by_arm'),
          'common-resolved secondary')
    common_n = _count(common['n_cases'])
    need(common['scope'] == 'all_arms_resolved_intersection.secondary.v1' and common['primary'] is False
         and common['not_a_replacement_for_full_denominator'] is True
         and max(0, sum(m['resolved_cases'] for m in metrics.values()) - 2 * n) <= common_n
         <= min(m['resolved_cases'] for m in metrics.values()), 'common-resolved scope or subset size differs.')
    _keys(common['metrics_by_arm'], GROUNDING_ARMS, 'common-resolved arms')
    common_gold = None
    for arm in GROUNDING_ARMS:
        cm = _grounding_metrics(common['metrics_by_arm'][arm], expected_n=common_n, expected_gold=common_gold)
        common_gold = cm['gold_counts']
        need(cm['resolved_cases'] == common_n
             and all(cm['gold_counts'][k] <= gold[k] for k in GROUNDING_GOLDS)
             and all(cm['confusion_resolved'][k] <= metrics[arm]['confusion_resolved'][k] for k in ('TP', 'FP', 'FN', 'TN')),
             'common-resolved metrics are not a secondary subset of the complete frame.')
    pairs = value['paired_comparisons']
    need(isinstance(pairs, list) and len(pairs) == 3, 'preserve all three paired grounding comparisons.')
    seen = set()
    for pair in pairs:
        _keys(pair, ('left_arm', 'right_arm', 'all_selected_case_count', 'status_transitions',
            'correctness_transitions', 'change_direction', 'confusion_count_changes', 'resolved_case_change',
            'abstention_case_change', 'metric_changes'), 'paired grounding comparison')
        left, right = pair['left_arm'], pair['right_arm']
        need(left in metrics and right in metrics and left < right and (left, right) not in seen
             and _count(pair['all_selected_case_count']) == n and pair['change_direction'] == 'right_minus_left',
             'paired grounding identities or full denominator differ.')
        seen.add((left, right))
        lm, rm = metrics[left], metrics[right]
        outcomes = ('correct', 'error', 'abstention')
        outcome_counts = lambda m: {'correct': m['confusion_resolved']['TP'] + m['confusion_resolved']['TN'],
            'error': m['confusion_resolved']['FP'] + m['confusion_resolved']['FN'], 'abstention': m['abstention_cases']}
        for key, names, lc, rc in (('status_transitions', GROUNDING_STATUSES, lm['status_counts'], rm['status_counts']),
                ('correctness_transitions', outcomes, outcome_counts(lm), outcome_counts(rm))):
            table = pair[key]
            _keys(table, names, key)
            for row in table.values():
                _keys(row, names, key + ' row')
                for count in row.values():
                    _count(count)
            need(all(sum(table[k].values()) == lc[k] and sum(row[k] for row in table.values()) == rc[k]
                     for k in names), 'paired transitions do not preserve saved method marginal counts.')
        _keys(pair['confusion_count_changes'], ('TP', 'FP', 'FN', 'TN'), 'confusion changes')
        expected_changes = {k: rm['confusion_resolved'][k] - lm['confusion_resolved'][k] for k in ('TP', 'FP', 'FN', 'TN')}
        need(all(type(v) is int for v in pair['confusion_count_changes'].values())
             and pair['confusion_count_changes'] == expected_changes
             and type(pair['resolved_case_change']) is int and pair['resolved_case_change'] == rm['resolved_cases'] - lm['resolved_cases']
             and type(pair['abstention_case_change']) is int and pair['abstention_case_change'] == rm['abstention_cases'] - lm['abstention_cases'],
             'paired grounding count changes differ.')
        _keys(pair['metric_changes'], GROUNDING_METRICS, 'paired metric changes')
        for name in GROUNDING_METRICS:
            change = pair['metric_changes'][name]
            expected = rm[name] - lm[name] if lm[name] is not None and rm[name] is not None else None
            need((expected is None and change is None) or (expected is not None and type(change) in (int, float)
                 and math.isfinite(change) and math.isclose(change, expected, rel_tol=1e-12, abs_tol=1e-12)),
                 'paired grounding metric change differs.')
    return value


def prepare_grounding_aggregate(evaluation_report, output_json, *, expected_report_pin):
    """Project an already-scored private receipt; never copy cases or native tags.

    This does not score labels, execute Gilda or select a winning context arm.
    Only the fixed aggregate fields below are accessed and copied. The new JSON
    is suitable for the optional viewer; native NC-SA data remain separate.
    """
    raw = _bounded(evaluation_report)
    implementation_pin = sha(__file__)
    need(hashlib.sha256(raw).hexdigest() == _pin(expected_report_pin), 'grounding evaluator report differs from its operator pin.')
    source = _decode(raw)
    need(_sealed(source) and source.get('format') == 'biograph-steward.expert-grounding-component-evaluation.v1'
         and source.get('reference') == GROUNDING_REFERENCE and all(source.get(k) is False for k in GROUNDING_FLAGS),
         'expected a scored grounding component with unchanged separate-task boundaries.')
    comparison = source['comparison']
    need(comparison.get('format') == 'biograph-steward.grounding-error-triage-comparison.v1'
         and all(comparison.get(k) is False for k in ('new_gold_labels_created',
             'population_scientific_accuracy_or_confidence_intervals_claimed',
             'source_grounding_scores_treated_as_truth_probabilities'))
         and comparison['all_selected_case_count'] == source['admitted_endpoint_cases'],
         'grounding comparison scope or admitted denominator differs.')
    common = comparison['common_resolved_secondary']
    value = {'format': GROUNDING_FORMAT, 'created_at': utcnow(), 'scope': GROUNDING_SCOPE,
        'reference': deepcopy(GROUNDING_REFERENCE), 'split': source['split'],
        **{k: source[k] for k in ('primary_frame_cases', 'admitted_endpoint_cases', 'outside_endpoint_cases')},
        'metrics_by_arm': deepcopy(comparison['metrics_by_arm']),
        'common_resolved_secondary': {k: deepcopy(common[k]) for k in (
            'scope', 'primary', 'n_cases', 'not_a_replacement_for_full_denominator', 'metrics_by_arm')},
        'paired_comparisons': deepcopy(comparison['paired_comparisons']),
        'source_report_file_sha256': expected_report_pin, 'source_report_content_sha256': source['content_sha256'],
        'evaluation_freeze_content_sha256': source['evaluation_freeze_content_sha256'],
        'evaluator_implementation_sha256': source['implementation_sha256'],
        'scoring_helper_sha256': source['scoring_helper_sha256'],
        'aggregate_producer_implementation_sha256': implementation_pin,
        'raw_reference_rows_or_case_ids_included': False, 'native_curation_tags_included': False,
        **{k: False for k in GROUNDING_FLAGS}}
    value['content_sha256'] = digest(value)
    _grounding_receipt(value)
    output = Path(output_json)
    need(output.suffix == '.json' and not output.exists() and not output.is_symlink(), 'use a new JSON output file.')
    need(_bounded(evaluation_report) == raw and sha(__file__) == implementation_pin,
         'grounding evaluator receipt or implementation changed during projection.')
    output.parent.mkdir(parents=True, exist_ok=True)
    with output.open('x', encoding='utf-8') as stream:
        json.dump(value, stream, indent=2, ensure_ascii=False, allow_nan=False)
        stream.write('\n')
    return value


def _grounding_summary(files, pin):
    raw = files[GROUNDING_FILE]
    need(hashlib.sha256(raw).hexdigest() == _pin(pin), 'grounding aggregate differs from its operator pin.')
    receipt = _grounding_receipt(_decode(raw))
    return {**deepcopy(receipt), 'title': 'Expert-curator grounding triage: separate component',
        'unit': 'admitted statement/source grounding cases',
        'interpretation': 'Native curator labels assess source-to-gene identity proposals. All three fixed context arms and abstentions remain visible; this does not score or automatically correct the Pharos graph.',
        'sources': [{'role': 'grounding', 'file': GROUNDING_FILE, 'file_sha256': pin,
                     'content_sha256': receipt['content_sha256']}]}


def _publication_summary(files, pins, format_name):
    summary = _summary(files, {role: pins[role] for role in ROLES})
    if format_name == FORMAT:
        need(set(pins) == set(ROLES), 'v1 accepts only its seven aggregate receipts.')
        return summary
    coess_pins = {'coess_' + k for k in COESS_NAMES}
    has_coess = bool(set(pins) & coess_pins)
    expected = set(ROLES) | (coess_pins if has_coess else set())
    if format_name == FORMAT_V2:
        need(has_coess and set(pins) == expected, 'v2 requires all declared coessentiality aggregate pins.')
    else:
        need(format_name == FORMAT_V3 and set(pins) == expected | {'grounding'},
             'v3 requires a grounding aggregate and either all or no coessentiality aggregates.')
    if has_coess:
        extra = _coessentiality_summary(files, {role: pins['coess_' + role] for role in COESS_NAMES},
                                       _decode(files[SOURCE_NAMES['utility']]))
        summary['coessentiality'] = extra
        summary['sources'] += extra['sources']
        summary['literature'] += [{'title': 'Wainberg et al.: pan-cancer coessentiality',
            'url': 'https://doi.org/10.1038/s41588-021-00840-z'},
            {'title': 'Coessentiality author code', 'url': 'https://github.com/kundajelab/coessentiality'},
            {'title': 'Native XSwap controls', 'url': 'https://github.com/hetio/xswap'}]
    if format_name == FORMAT_V3:
        extra = _grounding_summary(files, pins['grounding'])
        summary['grounding'] = extra
        summary['sources'] += extra['sources']
        summary['literature'] += [{'title': 'Expert-curated mechanistic extraction corpus',
            'url': 'https://doi.org/10.15252/msb.202211325'},
            {'title': 'Gilda contextual entity grounding', 'url': 'https://doi.org/10.1093/bioadv/vbac034'}]
    summary['format'] = format_name + '.summary'
    return summary


def _publication_readme(format_name, has_coess):
    if format_name == FORMAT:
        return README
    if format_name == FORMAT_V2:
        return README_V2
    return (README_V2 if has_coess else README) + README_GROUNDING


def publish(source_reports, output, *, expected_source_pins,
            coessentiality_reports=None, expected_coessentiality_pins=None,
            grounding_report=None, expected_grounding_pin=None):
    """Publish one curated snapshot using explicit operator-selected input pins."""
    need(isinstance(source_reports, dict) and set(source_reports) == set(ROLES), 'supply exactly the seven aggregate source roles.')
    implementation_pin = sha(__file__)
    paths = {role: Path(path) for role, path in source_reports.items()}
    files = {SOURCE_NAMES[role]: _bounded(path) for role, path in paths.items()}
    pins = dict(expected_source_pins)
    format_name = FORMAT
    extra_paths = {}
    if coessentiality_reports is not None or expected_coessentiality_pins is not None:
        need(isinstance(coessentiality_reports, dict) and set(coessentiality_reports) == set(COESS_NAMES)
             and isinstance(expected_coessentiality_pins, dict), 'supply all five optional coessentiality aggregates and pins.')
        extra_paths = {role: Path(path) for role, path in coessentiality_reports.items()}
        files.update({COESS_NAMES[role]: _bounded(path, limit=3_000_000) for role, path in extra_paths.items()})
        pins.update({'coess_' + role: pin for role, pin in expected_coessentiality_pins.items()})
        format_name = FORMAT_V2
    grounding_path = None
    if grounding_report is not None or expected_grounding_pin is not None:
        need(grounding_report is not None and expected_grounding_pin is not None,
             'supply the optional sanitized grounding aggregate and its explicit pin together.')
        grounding_path = Path(grounding_report)
        files[GROUNDING_FILE] = _bounded(grounding_path)
        pins['grounding'] = expected_grounding_pin
        format_name = FORMAT_V3
    summary = _publication_summary(files, pins, format_name)
    folder = new_output(output, *paths.values(), *extra_paths.values(), *([grounding_path] if grounding_path else []))
    for name, raw in files.items():
        target = folder / name
        target.parent.mkdir(exist_ok=True)
        target.write_bytes(raw)
    files['README.txt'] = _publication_readme(format_name, bool(extra_paths)).encode()
    files['report.html'] = render_html(summary).encode()
    for name in ('README.txt', 'report.html'):
        (folder / name).write_bytes(files[name])
    need(all(_bounded(paths[role]) == files[SOURCE_NAMES[role]] for role in ROLES)
         and all(_bounded(path, limit=3_000_000) == files[COESS_NAMES[role]] for role, path in extra_paths.items())
         and (grounding_path is None or _bounded(grounding_path) == files[GROUNDING_FILE])
         and sha(__file__) == implementation_pin, 'source or implementation changed during publication.')
    manifest = {'format': format_name, 'created_at': utcnow(), 'summary': summary,
        'operator_source_pins': pins, 'input_pins_authenticate_publisher': False,
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
    header = _decode(_bounded(folder / 'publication.json'))
    format_name = header.get('format')
    need(format_name in {FORMAT, FORMAT_V2, FORMAT_V3}, 'unsupported publication format.')
    has_coess = any('coess_' + k in header.get('operator_source_pins', {}) for k in COESS_NAMES)
    expected_files = (V2_PUBLIC_FILES if has_coess else PUBLIC_FILES)
    if format_name == FORMAT_V3:
        expected_files = expected_files | {GROUNDING_FILE}
    names = {p.relative_to(folder).as_posix() for p in folder.rglob('*') if p.is_file()}
    need(names == expected_files | {'publication.json'} and not any(p.is_symlink() for p in folder.rglob('*')),
         'publication contains missing or additional files.')
    for name in names:
        _bounded(folder / name, limit=3_000_000 if name in COESS_NAMES.values() else 250_000)
    manifest, captured = _capture(folder, 'publication.json')
    need(manifest.get('format') == format_name and all(manifest.get(k) is False for k in (
         'raw_reference_rows_included', 'scientific_labels_created', 'source_graph_modified', 'input_pins_authenticate_publisher'))
         and manifest.get('read_only') is True, 'publication policy or format changed.')
    summary = _publication_summary(captured, manifest['operator_source_pins'], format_name)
    expected_readme = _publication_readme(format_name, has_coess)
    need(manifest.get('summary') == summary and captured['README.txt'] == expected_readme.encode()
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
            if _decode(_bounded(path)).get('format') not in {FORMAT, FORMAT_V2, FORMAT_V3}:
                continue
            manifest, summary, _ = load_publication(folder)
            rows.append({'id': folder.name, 'created_at': manifest['created_at'], 'content_sha256': manifest['content_sha256'], 'summary': summary})
        except (ValueError, TypeError, KeyError, OSError):
            continue
    return {'assessments': rows}


def render_html(summary):
    """Escape every value; proof links name only allowlisted aggregate JSONs."""
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
    parts += ['<p>' + text(im['scope']) + '</p><p>' + text(im['decision']) + '</p>']
    if summary.get('coessentiality') is not None:
        parts.append(_coessentiality_html(summary['coessentiality']))
    if summary.get('grounding') is not None:
        parts.append(_grounding_html(summary['grounding']))
    parts += ['<h2>Limits and proof</h2><ul>']
    parts += ['<li>' + text(item) + '</li>' for item in summary['remaining_gaps']]
    parts += ['</ul><p>Graph: <code>' + text(summary['graph_sha256']) + '</code></p><ul>']
    parts += ['<li><a href="files/' + text(item['file']) + '">' + text(item['role']) + ' source receipt</a>: <code>'
              + text(item['file_sha256']) + '</code></li>' for item in summary['sources']]
    parts += ['</ul><p>' + ' · '.join('<a href="' + text(item['url']) + '" rel="noreferrer">' + text(item['title']) + '</a>'
                                    for item in summary['literature']) + '</p></html>']
    return ''.join(parts)


def _grounding_html(value):
    """A separate component axis, with full endpoint denominators and abstentions."""
    text = lambda x: escape(str(x), quote=True)
    ratio = lambda m, name: ('undefined' if m[name] is None else format(m[name], '.6f')) + (
        ' (' + str(m['metric_numerators'][name]) + '/' + str(m['metric_denominators'][name]) + ')')
    arms = value['metrics_by_arm']
    gold = arms['lexical']['gold_counts']
    parts = ['<h2>' + text(value['title']) + '</h2><p class=scope>' + text(value['scope']) + '</p>',
        '<p>' + text(value['interpretation']) + '</p><p>' + text(value['split']) + ' partition: '
        + text(value['admitted_endpoint_cases']) + '/' + text(value['primary_frame_cases'])
        + ' cases admitted to this endpoint (' + text(gold['grounding_error']) + ' native grounding-error; '
        + text(gold['correctly_grounded']) + ' native correctly-grounded). '
        + text(value['outside_endpoint_cases']) + ' cases remain outside the endpoint; they are not negatives.</p>',
        '<p>Error recall includes every admitted grounding-error case; false-conflict rate includes every admitted correctly-grounded case. Abstentions stay in those denominators. Precision concerns review proposals, not validated corrections.</p>',
        '<div style="overflow:auto"><table><tr><th>Fixed context arm</th><th>Conflict precision</th><th>Error recall</th><th>False-conflict rate</th><th>Resolved coverage</th><th>Abstentions</th></tr>']
    for arm in GROUNDING_ARMS:
        m = arms[arm]
        parts.append('<tr><td>' + text(arm) + '</td>' + ''.join('<td>' + text(ratio(m, k)) + '</td>'
            for k in ('precision', 'error_recall', 'false_conflict_rate', 'coverage'))
            + '<td>' + text(m['abstention_cases']) + '</td></tr>')
    parts += ['</table></div><details><summary>Resolved-only diagnostics and frozen evaluation identity</summary>',
        '<p>Resolved-only accuracy is conditional and secondary. The common-resolved intersection contains '
        + text(value['common_resolved_secondary']['n_cases']) + ' cases and never replaces the complete admitted frame.</p><ul>']
    for arm in GROUNDING_ARMS:
        m = arms[arm]
        parts.append('<li>' + text(arm) + ': resolved-only accuracy ' + text(ratio(m, 'resolved_accuracy'))
            + '; unresolved ' + text(m['status_counts']['unresolved']) + '; model error '
            + text(m['status_counts']['model_error']) + '.</li>')
    parts += ['</ul><p>Complete paired transitions and secondary aggregates remain in the copied aggregate receipt. No case IDs, source text, native tag records or individual predictions are published.</p>',
        '<p>Evaluation freeze: <code>' + text(value['evaluation_freeze_content_sha256'])
        + '</code><br>Private evaluator report SHA256: <code>' + text(value['source_report_file_sha256'])
        + '</code></p><p>Reference data license: ' + text(value['reference']['data_license'])
        + '. Source commitments are integrity records, not publisher authentication or proof of training independence.</p></details>']
    return ''.join(parts)


def _coessentiality_html(coess):
    """Small optional extension; all scientific numbers are saved aggregates."""
    text = lambda x: escape(str(x), quote=True)
    number = lambda x: 'UNKNOWN / undefined' if x is None else format(x, '.6f')
    envelope = lambda point: ' / '.join(number(point[k]) for k in ('minimum', 'median', 'maximum'))
    def table(headings, rows):
        return ('<div style="overflow:auto"><table><tr>' + ''.join('<th>' + text(x) + '</th>' for x in headings)
            + '</tr>' + ''.join('<tr>' + ''.join('<td>' + text(x) + '</td>' for x in row) + '</tr>' for row in rows)
            + '</table></div>')
    arms = ('normalized', 'current', 'historical')
    labels = ('Normalized source context', 'Current-release eligibility contrast', 'Historical native-xref contrast')
    parts = ['<h2>' + text(coess['title']) + '</h2><p class=scope>' + text(coess['interpretation']) + '</p>',
        '<p>' + text(coess['query_genes']) + ' fixed measured-gene queries; ' + text(coess['primary_pairs'])
        + ' different-chromosome primary pairs; complete N=1–10. Neither source qualification contrast demonstrates prediction improvement.</p>',
        '<p>' + text(coess['scope']) + '</p><details><summary>Complete primary curves, control ranges and absolute coverage</summary>',
        '<p>Enrichment is observed shared-context hits divided by query-matched expected hits. Every primary point retains all 92 queries. Opposite query directions are slots, not independent experiments.</p>',
        table(('N', *labels), [[n] + [number(coess['primary_curves'][a][n-1]['enrichment']) for a in arms] for n in coess['N']])]
    for treatment, label in zip(arms[1:], labels[1:]):
        parts += ['<h3>' + text(label) + ': descriptive controls</h3><p>Twenty count-matched and twenty measured-frame degree-preserving draws. Each range is minimum / median / maximum, not a confidence interval.</p>',
            table(('N', 'Count-matched enrichment', 'Degree-preserving enrichment'), [[n] + [
                envelope(coess['controls'][treatment][kind][n-1]) for kind in ('count', 'degree')] for n in coess['N']])]
    parts += ['<h3>Absolute shared-context hit fractions</h3>', table(('N', *labels), [[n] + [
        number(coess['primary_curves'][a][n-1]['observed_hit_fraction']) for a in arms] for n in coess['N']]),
        '<details><summary>Absolute hit-fraction ranges for all control draws</summary>',
        table(('N', 'Current count', 'Current degree', 'Historical count', 'Historical degree'), [[n] + [
            envelope(coess['controls'][t][k][n-1]['absolute_hit_fraction']) for t in ('current', 'historical')
            for k in ('count', 'degree')] for n in coess['N']]), '</details></details>',
        '<details><summary>Frozen identities and diagnostic coverage</summary><p>All ' + text(coess['arm_count'])
        + ' arms and ' + text(coess['scope_count']) + ' declared scopes remain in the downloadable coess_curves and coess_controls aggregate receipts below. '
        'Sign-restricted and same-chromosome diagnostics do not replace the primary endpoint. Native pair values and matrix payloads are excluded.</p>',
        '<p>Original scientific freeze: <code>' + text(coess['original_pre_value_freeze_content_sha256']) + '</code><br>Transport continuation: <code>'
        + text(coess['transport_repair_content_sha256']) + '</code><br>Native capture: <code>' + text(coess['capture_content_sha256']) + '</code></p>',
        '<p>' + text(coess['transport_exposure_scope']) + '</p><ul>', *['<li>' + text(x) + '</li>' for x in coess['limitations']], '</ul></details>']
    return ''.join(parts)
