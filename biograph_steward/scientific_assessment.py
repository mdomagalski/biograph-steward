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
FORMAT_V4 = 'biograph-steward.scientific-assessment-publication.v4'
TASK_LIMIT = 1_000_000
FUNCTION_FILE = 'sources/function_recovery.json'
BIORED_FILE = 'sources/biored.json'
FUNCTION_FORMAT = 'biograph-steward.function-recovery-aggregate.v1'
BIORED_FORMAT = 'biograph-steward.biored-reference-aggregate.v1'
# These are the already frozen recipe names, not a menu selected by outcomes.
FUNCTION_METHODS = {
    'primary': frozenset(('blast_fss_half', 'blast_local_half', 'cohort_frequency',
        'fastsinksourceplus', 'fss_graph_human_experimental_top80', 'fss_graph_native_top80',
        'fss_graph_ne_top80', 'genemaniaplus', 'global_full_allseeds_fss',
        'global_full_allseeds_fss_originalheads', 'global_full_allseeds_local',
        'global_full_allseeds_local_originalheads', 'global_full_oldseeds_fss',
        'global_induced_oldseeds_fss', 'known_frequency', 'localplus', 'official_blast',
        'official_naive', 'official_nonexperimental', 'official_prott5_cosine1',
        'official_prott5_cosine3', 'prott5_cosine1_fss_half', 'prott5_cosine1_local_half',
        'prott5_cosine3_fss_half', 'prott5_cosine3_local_half',
        'strict_alias_fastsinksourceplus', 'strict_alias_localplus')),
    'reserved': frozenset(('global_full_allseeds_fss', 'global_full_allseeds_fss_originalheads',
        'global_full_allseeds_local', 'global_full_allseeds_local_originalheads',
        'global_full_oldseeds_fss', 'official_blast', 'official_naive',
        'official_nonexperimental', 'official_prott5_cosine3', 'prott5_cosine3_full_fss_half',
        'prott5_cosine3_full_local_half', 'strict_alias_fastsinksourceplus', 'strict_alias_localplus')),
}
FUNCTION_SCOPE = ('CAFA5 temporal GO annotation recovery on separately frozen primary and reserved human-protein '
    'frames using historical Pharos/STRING context. Not accuracy of every graph edge, not the 99-target workspace '
    'edge population, and not an independent-study or inductive unseen-gene validation.')
BIORED_SCOPE = ('Expert-curator-relative agreement for relations reported in BioCreative VIII abstracts, with gold '
    'entities supplied. Primary one-pair-per-publication, complete-gene secondary and artifact-consistency scopes '
    'remain separate. Not whole-Pharos biological truth, canonical-protein grounding or direct binding validation.')
BIORED_FORMATS = {'primary':'biograph-steward.biored-source-comparison.v1',
    'gene':'biograph-steward.biored-full-gene-source-assessment.v1',
    'artifact':'biograph-steward.biored-released-artifact-consistency.v1'}
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
# Retain the existing v1-v3 API constant; v4 callers opt into the expanded set.
ALL_PUBLIC_FILES = V2_PUBLIC_FILES | {GROUNDING_FILE}
V4_PUBLIC_FILES = ALL_PUBLIC_FILES | {FUNCTION_FILE, BIORED_FILE}
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


def _task_tree(value, *, sanitize=False, depth=0):
    """Bound aggregate-only data; strip operator paths without following them."""
    need(depth<=18, 'aggregate nesting exceeds the component bound.')
    forbidden={'case_id','pmid','abstract','text','statement','passage','predictions','case_scores',
               'raw_cases','raw_rows','target_ids','GO_ID','protein_id','multiplicities','model_weights'}
    if isinstance(value,dict):
        need(len(value)<=1500 and all(isinstance(k,str) for k in value), 'aggregate object exceeds its bound.')
        out={}
        for i,(key,item) in enumerate(value.items()):
            need(key not in forbidden, 'raw case/text/prediction fields are not public aggregate data.')
            if key.startswith(('/', 'file:')):
                need(sanitize and isinstance(item,str) and re.fullmatch('[a-f0-9]{64}',item), 'operator path key in public aggregate.')
                out['source_'+str(i)]={'file_sha256':item}
            elif key in {'path','file','source','source_snapshot'} and isinstance(item,str) and item.startswith(('/','file:')):
                need(sanitize, 'operator path in public aggregate.')
            else:out[key]=_task_tree(item,sanitize=sanitize,depth=depth+1)
        return out
    if isinstance(value,list):
        need(len(value)<=1500, 'aggregate list exceeds its bound.')
        return [_task_tree(v,sanitize=sanitize,depth=depth+1) for v in value]
    if isinstance(value,str):
        need(len(value)<=16000 and not re.search(r'\b(?:PMID:[0-9]+|GO:[0-9]{7}|UniProtKB:[A-Z0-9]{6})',value),
             'raw reference/target identifiers are not public aggregate data.')
        pattern=r'(?:file://)?/(?:Users|home|private|tmp|var)/[^\s\"<>]+'
        if re.search(pattern,value):
            need(sanitize, 'operator path in public aggregate.')
            value=re.sub(pattern,'[operator path removed]',value)
        return value
    need(value is None or type(value) in (bool,int,float), 'unsupported aggregate value type.')
    need(type(value) is not float or math.isfinite(value), 'aggregate numbers must be finite.')
    return value


def _task_source(path, expected):
    _pin(expected);raw=_bounded(path,limit=TASK_LIMIT)
    need(hashlib.sha256(raw).hexdigest()==expected, 'task source FILE pin differs.')
    value=_decode(raw);need(isinstance(value,dict) and _sealed(value), 'task source content seal differs.')
    return value


def _native_coverage(value, denominator):
    """Author n/ne can retain pre-known rows in n but not in ne; never clamp."""
    eligible=_count(denominator['eligible_proteins']);recognized=_count(denominator['author_recognized_target_IDs'])
    need(eligible>0 and type(value) in (int,float) and math.isfinite(value)
         and 0<=value<=recognized/eligible+1e-12,
         'native coverage ratio exceeds its recognized/eligible count bound.')
    return value


def _function_receipt(value):
    _keys(value,('format','created_at','scope','source_report_file_sha256','source_report_content_sha256',
        'results','raw_cases_or_predictions_included','source_graph_modified','scientific_accuracy_claimed','content_sha256'),
        'function recovery aggregate')
    need(_sealed(value) and value['format']==FUNCTION_FORMAT and value['scope']==FUNCTION_SCOPE
         and all(value[k] is False for k in ('raw_cases_or_predictions_included','source_graph_modified','scientific_accuracy_claimed')),
         'function recovery aggregate scope changed.')
    _pin(value['source_report_file_sha256']);_pin(value['source_report_content_sha256'])
    result=value['results'];_task_tree(result)
    _keys(result,('format','created_at','status','scientific_task','scope','roles','expected_outcome_slots','status_counts','rows',
        'denominators','paired_comparisons','uncertainty_reports','runtime','evaluation_contract','reference','caveats','lineage',
        'source_pins','native_aggregate_source_files_sha256','all_outcomes_including_negatives_and_unsupported_retained',
        'new_model_threshold_or_target_selection_from_this_projection'),'function source aggregate fields')
    need(result.get('expected_outcome_slots')==240 and result.get('all_outcomes_including_negatives_and_unsupported_retained') is True
         and result.get('new_model_threshold_or_target_selection_from_this_projection') is False,
         'the complete frozen function-comparison outcome frame is required.')
    rows=result.get('rows');denominators=result.get('denominators')
    need(isinstance(rows,list) and len(rows)==240 and isinstance(denominators,list) and len(denominators)==12,
         'preserve all declared rows and native denominator scopes.')
    frames={'primary':27,'reserved':13};settings={'partial','partial_publishedaftert0'}
    namespaces={'biological_process','molecular_function','cellular_component'};ds={}
    for row in denominators:
        need(isinstance(row,dict) and all(isinstance(row.get(k),str) for k in ('frame','setting','namespace')), 'invalid native denominator record.')
        key=row['frame'],row['setting'],row['namespace']
        need(key[0] in frames and key[1] in settings and key[2] in namespaces and key not in ds,'duplicate/unknown native denominator scope.')
        n=_count(row['eligible_proteins']);ia=_count(row['IA_eligible_proteins'])
        need(ia<=n and _count(row['author_recognized_target_IDs'])>=n,'native reference denominator differs.')
        _count(row['post_known_TOI_reference_pairs']);ds[key]=row
    seen=set();methods={frame:set() for frame in frames};statuses={}
    for row in rows:
        need(isinstance(row,dict) and all(isinstance(row.get(k),str) for k in ('frame','setting','namespace','method','status')), 'invalid function outcome row.')
        need(set(row)<={'frame','setting','namespace','method','status','eligible_proteins','IA_eligible_proteins',
            'source_curve_sha256','reason','native_curve_rows','micro_Fmax','micro_Fmax_tau','IA_micro_Fmax','IA_micro_Fmax_tau',
            'macro_Fmax','macro_Fmax_tau','IA_macro_Fmax','IA_macro_Fmax_tau','unweighted_Smin','unweighted_Smin_tau',
            'IA_weighted_Smin','IA_weighted_Smin_tau','prediction_coverage_at_micro_Fmax','fixed_0_5'},
            'unexpected case-level field in function outcome row.')
        frame,setting,ns,method=[row[k] for k in ('frame','setting','namespace','method')]
        need(frame in frames and setting in settings and ns in namespaces
             and re.fullmatch('[a-z][a-z0-9_]{0,100}',method),'invalid function outcome identity.')
        key=frame,setting,ns,method
        need(key not in seen,'duplicate function outcome slot.');seen.add(key);methods[frame].add(method)
        denom=ds[frame,setting,ns]
        need(row.get('eligible_proteins')==denom['eligible_proteins']
             and row.get('IA_eligible_proteins')==denom['IA_eligible_proteins'],'outcome denominator differs from its native frame.')
        status=row['status'];need(status in {'scored','pending','no_native_curve','nonfinite_native_curve','unsupported','failed'},'unknown outcome status.')
        statuses[status]=statuses.get(status,0)+1
        if status!='scored':
            need(not set(row)&{'native_curve_rows','micro_Fmax','IA_micro_Fmax','macro_Fmax','IA_macro_Fmax',
                 'unweighted_Smin','IA_weighted_Smin','prediction_coverage_at_micro_Fmax','fixed_0_5'},
                 'unscored outcome must not receive a synthetic score.')
            continue
        _pin(row['source_curve_sha256'])
        need(_count(row['native_curve_rows'])>0,'scored outcome lacks a native curve.')
        for field in ('micro_Fmax','micro_Fmax_tau','IA_micro_Fmax','IA_micro_Fmax_tau','macro_Fmax','macro_Fmax_tau',
                      'IA_macro_Fmax','IA_macro_Fmax_tau','unweighted_Smin_tau','IA_weighted_Smin_tau'):
            _metric(row[field])
        _native_coverage(row['prediction_coverage_at_micro_Fmax'],denom)
        for field in ('unweighted_Smin','IA_weighted_Smin'):
            need(type(row[field]) in (int,float) and math.isfinite(row[field]) and row[field]>=0,'invalid saved Smin.')
        fixed=row.get('fixed_0_5');need(isinstance(fixed,dict) and fixed.get('threshold')==.5
             and fixed.get('namespace')==ns,'preserve the fixed .5 operating point.')
        omitted=fixed.get('status')=='author omits thresholds with zero prediction coverage'
        for field in ('PPV','recall','F1','coverage'):
            if omitted:need(fixed.get(field) is None,'an omitted author operating point is not zero.')
            elif field=='coverage':_native_coverage(fixed[field],denom)
            else:_metric(fixed[field])
    need(all(methods[k]==FUNCTION_METHODS[k] for k in frames)
         and result.get('status_counts')==statuses,'declared method/status totals differ.')
    roles=result.get('roles');need(isinstance(roles,dict) and isinstance(roles.get('original_primary'),dict)
         and roles['original_primary'].get('candidate')=='fastsinksourceplus'
         and roles['original_primary'].get('frame')=='primary' and roles['original_primary'].get('metric')=='micro_Fmax'
         and roles.get('deployed_source_profile')=='strict_alias_localplus', 'the original negative primary and deployed roles must remain explicit.')
    need(isinstance(result.get('paired_comparisons'),list) and isinstance(result.get('caveats'),list)
         and result.get('scope',{}).get('whole_graph_biological_truth_or_clinical_utility_claimed') is False
         and result['scope'].get('no_raw_reference_or_prediction_rows_included') is True,
         'function reference/interpretation boundary differs.')
    for pair in result['paired_comparisons']:
        key=pair['frame'],pair['setting'],pair['namespace'];need(key in ds,'unknown paired comparison scope.')
        need(pair['candidate'] in methods[key[0]] and pair['comparator'] in methods[key[0]],'paired comparison method outside frozen frame.')
        _pin(pair['source_report_sha256']);interval=pair['paired_95_percentile_interval']
        need(isinstance(interval,list) and len(interval)==2 and all(type(v) in (int,float) and math.isfinite(v) and -1<=v<=1 for v in interval)
             and interval[0]<=interval[1], 'invalid saved paired interval.')
    return value


def prepare_function_recovery_aggregate(source, output_json, *, expected_report_pin):
    original=_task_source(source,expected_report_pin)
    need(original.get('format')=='biograph-steward.cafa5-scientific-aggregate-projection.v1', 'expected the sealed CAFA aggregate projection.')
    allowed={'format','created_at','status','scientific_task','scope','roles','expected_outcome_slots','status_counts','rows',
        'denominators','paired_comparisons','uncertainty_reports','runtime','evaluation_contract','reference','caveats','lineage',
        'source_pins','native_aggregate_source_files_sha256','all_outcomes_including_negatives_and_unsupported_retained',
        'new_model_threshold_or_target_selection_from_this_projection','content_sha256'}
    need(set(original)<=allowed, 'unexpected fields in function aggregate source.')
    result=deepcopy(original);result.pop('content_sha256');source_hashes=result['native_aggregate_source_files_sha256']
    for row in result['rows']:
        if 'source' in row:
            need(row['source'] in source_hashes, 'outcome curve has no source FILE pin.')
            row['source_curve_sha256']=source_hashes[row.pop('source')]
    result=_task_tree(result,sanitize=True)
    value={'format':FUNCTION_FORMAT,'created_at':original['created_at'],'scope':FUNCTION_SCOPE,
        'source_report_file_sha256':expected_report_pin,'source_report_content_sha256':original['content_sha256'],
        'results':result,'raw_cases_or_predictions_included':False,'source_graph_modified':False,'scientific_accuracy_claimed':False}
    value['content_sha256']=digest(value);_function_receipt(value)
    need(not Path(output_json).exists(),'choose a new aggregate output.');write_json(output_json,value);return value


def _biored_metrics(value, n=None):
    fields=('cases','exact_correct','exact_accuracy','coverage','unresolved','exact_positive_relation','entity_pair','native_None_cases','confusion')
    _keys(value,fields,'BioRED aggregate metrics');total=_count(value['cases'])
    need(total>0 and (n is None or total==n), 'BioRED complete candidate denominator differs.')
    labels={'None','Association','Bind','Comparison','Conversion','Cotreatment','Drug_Interaction','Negative_Correlation','Positive_Correlation'}
    confusion=value['confusion'];need(isinstance(confusion,dict), 'BioRED aggregate confusion table missing.')
    observed=[]
    for label,count in confusion.items():
        pair=label.split(' -> ');need(len(pair)==2 and pair[0] in labels and pair[1] in labels|{'Unresolved'},'unknown aggregate relation label.')
        observed.append((pair[0],pair[1],_count(count)))
    need(sum(c for _,_,c in observed)==total,'BioRED confusion denominator differs.')
    correct=sum(c for g,p,c in observed if g==p);unresolved=sum(c for _,p,c in observed if p=='Unresolved')
    need(_count(value['exact_correct'])==correct and _count(value['unresolved'])==unresolved
         and _count(value['native_None_cases'])==sum(c for g,_,c in observed if g=='None'), 'BioRED marginal counts differ.')
    need(math.isclose(_metric(value['exact_accuracy']),correct/total,abs_tol=1e-12)
         and math.isclose(_metric(value['coverage']),(total-unresolved)/total,abs_tol=1e-12), 'BioRED accuracy/coverage must retain abstentions.')
    positives=labels-{'None'}
    tp=sum(c for g,p,c in observed if g==p and g in positives)
    fp=sum(c for g,p,c in observed if p in positives and p!=g)
    fn=sum(c for g,p,c in observed if g in positives and p!=g)
    ptp=sum(c for g,p,c in observed if g in positives and p in positives)
    pfp=sum(c for g,p,c in observed if g=='None' and p in positives)
    pfn=sum(c for g,p,c in observed if g in positives and p not in positives)
    for name,counts in [('exact_positive_relation',(tp,fp,fn)),('entity_pair',(ptp,pfp,pfn))]:
        row=value[name];_keys(row,('tp','fp','fn','precision','recall','f1'),'BioRED positive metrics')
        a,b,c=counts;need(tuple(_count(row[k]) for k in ('tp','fp','fn'))==counts,'BioRED positive confusion counts differ.')
        for key,expected in [('precision',a/(a+b) if a+b else 0.),('recall',a/(a+c) if a+c else 0.),('f1',2*a/(2*a+b+c) if 2*a+b+c else 0.)]:
            need(math.isclose(_metric(row[key]),expected,abs_tol=1e-12),'BioRED saved positive metric differs from its confusion counts.')
    return total


def _biored_receipt(value):
    _keys(value,('format','created_at','scope','reports','raw_cases_or_predictions_included','source_graph_modified',
                'scientific_accuracy_claimed','content_sha256'),'BioRED aggregate component')
    need(_sealed(value) and value['format']==BIORED_FORMAT and value['scope']==BIORED_SCOPE
         and all(value[k] is False for k in ('raw_cases_or_predictions_included','source_graph_modified','scientific_accuracy_claimed')),
         'BioRED component scope changed.')
    _keys(value['reports'],BIORED_FORMATS,'BioRED source report roles');reports={}
    fixed=('always_None','typed_co_mention','specialist_native','specialist_type_guard')
    for role,entry in value['reports'].items():
        _keys(entry,('source_report_file_sha256','source_report_content_sha256','report'),'BioRED source binding')
        _pin(entry['source_report_file_sha256']);_pin(entry['source_report_content_sha256'])
        report=entry['report'];_task_tree(report)
        need(isinstance(report,dict) and report.get('format')==BIORED_FORMATS[role], 'BioRED report role/format differs.')
        reports[role]=report
        if role=='artifact':continue
        n=_count(report['test_cases'] if role=='primary' else report['cases'])
        publications=_count(report['test_publications'] if role=='primary' else report['publications'])
        need(0<publications<=n and (role!='primary' or publications==n), 'BioRED publication and pair scopes differ.')
        arms=fixed+('flat_context_LLM','source_audit_agent') if role=='primary' else fixed
        _keys(report['metrics'],arms,'fixed BioRED arms')
        for metrics in report['metrics'].values():_biored_metrics(metrics,n)
        need(sum(_count(c) for c in report['gold_label_counts' if role=='primary' else 'native_gold_label_counts'].values())==n,
             'BioRED gold-class denominator differs.')
        groups=report['per_entity_type_metrics'];need(isinstance(groups,dict) and groups,'BioRED relation-family table missing.')
        for group in groups.values():
            _keys(group,arms,'BioRED family arms')
            group_n=None
            for metrics in group.values():group_n=_biored_metrics(metrics,group_n)
        need(sum(group[fixed[0]]['cases'] for group in groups.values())==n,'BioRED family scopes do not partition candidates.')
    primary,gene,artifact=[reports[k] for k in ('primary','gene','artifact')]
    need(primary['live_graph_changed'] is False and gene['source_graph_changes']==artifact['source_graph_changes']==0
         and gene['training_performed'] is False and artifact['additional_LLM_requests']==0
         and artifact['checkpoint_training_membership_independently_audited'] is False,
         'BioRED graph/training/provenance boundary differs.')
    need(gene['primary_prediction_freeze_content_sha256']==artifact['primary_prediction_freeze_content_sha256']
         ==primary['prediction_freeze_content_sha256'], 'BioRED reports do not share the declared prediction boundary.')
    need(type(primary['agent_default_adoption_criterion_passed']) is bool,'BioRED adoption flag must remain explicit.')
    comparisons=primary['agent_paired_comparisons']
    _keys(comparisons,('specialist_native','specialist_type_guard','flat_context_LLM'),'all fixed agent comparators')
    for pair in comparisons.values():
        for field in ('accuracy_delta_95pct_paired_bootstrap','exact_relation_F1_delta_95pct_paired_bootstrap'):
            interval=pair[field];need(isinstance(interval,list) and len(interval)==2
                and all(type(x) in (int,float) and math.isfinite(x) and -1<=x<=1 for x in interval)
                and interval[0]<=interval[1],'invalid saved BioRED paired interval.')
    adopted=all(p[k][0]>0 for p in comparisons.values() for k in
        ('accuracy_delta_95pct_paired_bootstrap','exact_relation_F1_delta_95pct_paired_bootstrap'))
    need(primary['agent_default_adoption_criterion_passed']==adopted,'BioRED frozen adoption rule differs from saved intervals.')
    for field in ('native_candidate_rows','native_candidate_publications','released_corpus_abstracts'):_count(artifact[field])
    levels=('pair','pair+novelty','relation','relation+novelty','relation+direction','all')
    for key in ('author_metric_reference_agreement','paper_reported_10_seed_mean_F1','single_checkpoint_minus_paper_mean_F1'):
        _keys(artifact[key],levels,'all six native artifact metric levels')
    for level,row in artifact['author_metric_reference_agreement'].items():
        for metric in ('precision','recall','f1'):_metric(row[metric])
        mean=_metric(artifact['paper_reported_10_seed_mean_F1'][level]);delta=artifact['single_checkpoint_minus_paper_mean_F1'][level]
        need(type(delta) in (int,float) and math.isclose(delta,row['f1']-mean,abs_tol=1e-12),'single-checkpoint diagnostic delta differs.')
    return value


def prepare_biored_aggregate(source_reports, output_json, *, expected_report_pins):
    _keys(source_reports,BIORED_FORMATS,'all three BioRED aggregate reports')
    _keys(expected_report_pins,BIORED_FORMATS,'all three explicit BioRED FILE pins')
    reports={}
    allowed={
      'primary':{'format','created_at','labels_first_opened_at','frame_content_sha256','comparison_content_sha256',
        'prediction_freeze_content_sha256','test_cases','test_publications','gold_label_counts','metrics','agent_paired_comparisons',
        'specialist_vs_co_mention_paired_comparisons','per_entity_type_metrics','execution_costs','agent_default_adoption_criterion_passed',
        'live_graph_changed','case_scores_sha256','interpretation','limitations','content_sha256'},
      'gene':{'format','created_at','labels_first_opened_at','frame_content_sha256','predeclaration_content_sha256',
        'execution_freeze_content_sha256','analysis_freeze_content_sha256','primary_prediction_freeze_content_sha256',
        'specialist_execution_content_sha256','predictions_sha256','analysis_implementation_sha256','cases','publications',
        'native_gold_label_counts','metrics','per_entity_type_metrics','publication_cluster_uncertainty','candidate_pairs_per_publication',
        'runtime','device','reported_specialist_elapsed_seconds','comparison_interpretation','label_scope','sampling_scope',
        'uncertainty_scope','reference_limitations','source_graph_changes','training_performed','content_sha256'},
      'artifact':{'format','created_at','labels_first_opened_at','primary_prediction_freeze_content_sha256',
        'predeclaration_content_sha256','analysis_freeze_content_sha256','gene_execution_content_sha256',
        'remaining_execution_content_sha256','native_candidate_rows','native_candidate_publications','released_corpus_abstracts',
        'source_metric_helper_sha256','author_metric_reference_agreement','paper_reported_10_seed_mean_F1',
        'single_checkpoint_minus_paper_mean_F1','checkpoint_training_membership_independently_audited','interpretation',
        'scope','decoding','source_graph_changes','additional_LLM_requests','content_sha256'}}
    for role in BIORED_FORMATS:
        original=_task_source(source_reports[role],expected_report_pins[role])
        need(set(original)<=allowed[role] and original.get('format')==BIORED_FORMATS[role], 'unexpected BioRED source fields or role.')
        result=deepcopy(original);result.pop('content_sha256')
        reports[role]={'source_report_file_sha256':expected_report_pins[role],
            'source_report_content_sha256':original['content_sha256'],'report':_task_tree(result,sanitize=True)}
    value={'format':BIORED_FORMAT,'created_at':reports['primary']['report']['created_at'],'scope':BIORED_SCOPE,
        'reports':reports,'raw_cases_or_predictions_included':False,'source_graph_modified':False,'scientific_accuracy_claimed':False}
    value['content_sha256']=digest(value);_biored_receipt(value)
    need(not Path(output_json).exists(),'choose a new aggregate output.');write_json(output_json,value);return value


def _task_summary(files, role, pin):
    filename=FUNCTION_FILE if role=='function_recovery' else BIORED_FILE
    need(hashlib.sha256(files[filename]).hexdigest()==_pin(pin),'task aggregate differs from its operator FILE pin.')
    value=(_function_receipt if role=='function_recovery' else _biored_receipt)(_decode(files[filename]))
    common={'scope':value['scope'],'scientific_accuracy_claimed':False,
        'sources':[{'role':role,'file':filename,'file_sha256':pin,'content_sha256':value['content_sha256']}]}
    if role=='function_recovery':
        result=value['results']
        coverage_note=['Native coverage is the unchanged author prediction-count / eligible-reference ratio. Known-term exclusion can leave different numerator and denominator scopes, so some later-publication values exceed1; they are preserved, not clamped or interpreted as biological fractions.']
        return {**common,'title':'Temporal GO annotation recovery','unit':'Native eligible protein/function annotation benchmark scopes',
            'rows':deepcopy(result['rows']),'denominators':deepcopy(result['denominators']),
            'roles':deepcopy(result['roles']),'paired_comparisons':deepcopy(result['paired_comparisons']),
            'status_counts':deepcopy(result['status_counts']),'frame_scope':deepcopy(result['scope']),
            'source_metadata':{k:deepcopy(result[k]) for k in ('runtime','reference','evaluation_contract','lineage','source_pins','uncertainty_reports')},
            'limitations':deepcopy(result['caveats'])+coverage_note}
    return {**common,'title':'Curator-reference agreement for reported literature relations',
        'unit':'One source pair per abstract (primary); source-defined candidate pairs (secondary)',
        **{role:deepcopy(entry['report']) for role,entry in value['reports'].items()},
        'source_report_pins':{role:{k:v for k,v in entry.items() if k!='report'} for role,entry in value['reports'].items()},
        'limitations':['Expert source-relation agreement is not whole-graph biological truth or canonical human-protein grounding.',
            'The released specialist checkpoint fine-tuning membership is not independently audited; gold entities are provided.',
            'The frozen native inference decoder and the authors separate summary decoder differ for some multi-positive scores; the single-checkpoint comparison with paper seed means is diagnostic, not an exact reproduction.',
            'The primary and complete-gene candidate denominators differ and are never pooled.',
            'Native Bind does not automatically establish direct physical binding; source None is abstract-relative.',
            'All fixed arms, unresolved outputs, source exposure caveats and the frozen adoption flag remain visible.']}


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
    elif format_name == FORMAT_V3:
        need(format_name == FORMAT_V3 and set(pins) == expected | {'grounding'},
             'v3 requires a grounding aggregate and either all or no coessentiality aggregates.')
    else:
        tasks=set(pins)&{'function_recovery','biored'}
        need(format_name==FORMAT_V4 and tasks and set(pins)==expected|tasks|({'grounding'} if 'grounding' in pins else set()),
             'v4 requires declared independent task aggregates and complete optional legacy components.')
    if has_coess:
        extra = _coessentiality_summary(files, {role: pins['coess_' + role] for role in COESS_NAMES},
                                       _decode(files[SOURCE_NAMES['utility']]))
        summary['coessentiality'] = extra
        summary['sources'] += extra['sources']
        summary['literature'] += [{'title': 'Wainberg et al.: pan-cancer coessentiality',
            'url': 'https://doi.org/10.1038/s41588-021-00840-z'},
            {'title': 'Coessentiality author code', 'url': 'https://github.com/kundajelab/coessentiality'},
            {'title': 'Native XSwap controls', 'url': 'https://github.com/hetio/xswap'}]
    if format_name == FORMAT_V3 or format_name==FORMAT_V4 and 'grounding' in pins:
        extra = _grounding_summary(files, pins['grounding'])
        summary['grounding'] = extra
        summary['sources'] += extra['sources']
        summary['literature'] += [{'title': 'Expert-curated mechanistic extraction corpus',
            'url': 'https://doi.org/10.15252/msb.202211325'},
            {'title': 'Gilda contextual entity grounding', 'url': 'https://doi.org/10.1093/bioadv/vbac034'}]
    if format_name==FORMAT_V4:
        summary['workspace_scope']=summary['scope']
        summary['scope']='Independent task assessments with separate reference frames and units; the legacy 99-target workspace remains a separately scoped component. No pooled scientific-accuracy result is calculated.'
        for role,name in (('function_recovery','function_recovery'),('biored','agent_reference_agreement')):
            if role in pins:
                extra=_task_summary(files,role,pins[role]);summary[name]=extra;summary['sources']+=extra['sources']
    summary['format'] = format_name + '.summary'
    return summary


def _publication_readme(format_name, has_coess, has_grounding=None):
    if format_name == FORMAT:
        return README
    if format_name == FORMAT_V2:
        return README_V2
    if format_name==FORMAT_V3:
        return (README_V2 if has_coess else README) + README_GROUNDING
    return ((README_V2 if has_coess else README) + (README_GROUNDING if has_grounding else '')
        + '\nThe optional v4 task components have independent reference frames and denominators. '
        'CAFA temporal annotation recovery and BioRED abstract-relative agreement are not measurements of '
        'the legacy 99-target graph edges, not pooled whole-graph precision, and not new labels or graph changes. '
        'Every declared outcome slot and fixed comparison arm remains visible, including pending/unsupported '
        'outcomes, negative primary results, macro and fixed-operating-point trade-offs. Operator paths and raw '
        'cases/text/predictions/weights are excluded. Original FILE/content commitments remain explicit.\n')


def publish(source_reports, output, *, expected_source_pins,
            coessentiality_reports=None, expected_coessentiality_pins=None,
            grounding_report=None, expected_grounding_pin=None,
            function_recovery_report=None, expected_function_recovery_pin=None,
            biored_report=None, expected_biored_pin=None):
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
    task_paths={}
    for role,path,pin,filename in (
            ('function_recovery',function_recovery_report,expected_function_recovery_pin,FUNCTION_FILE),
            ('biored',biored_report,expected_biored_pin,BIORED_FILE)):
        if path is not None or pin is not None:
            need(path is not None and pin is not None,'task aggregate and explicit FILE pin must be supplied together.')
            task_paths[role]=Path(path);files[filename]=_bounded(path,limit=TASK_LIMIT);pins[role]=pin
            format_name=FORMAT_V4
    summary = _publication_summary(files, pins, format_name)
    folder = new_output(output, *paths.values(), *extra_paths.values(), *task_paths.values(), *([grounding_path] if grounding_path else []))
    for name, raw in files.items():
        target = folder / name
        target.parent.mkdir(exist_ok=True)
        target.write_bytes(raw)
    files['README.txt'] = _publication_readme(format_name, bool(extra_paths),grounding_path is not None).encode()
    files['report.html'] = render_html(summary).encode()
    for name in ('README.txt', 'report.html'):
        (folder / name).write_bytes(files[name])
    need(all(_bounded(paths[role]) == files[SOURCE_NAMES[role]] for role in ROLES)
         and all(_bounded(path, limit=3_000_000) == files[COESS_NAMES[role]] for role, path in extra_paths.items())
         and (grounding_path is None or _bounded(grounding_path) == files[GROUNDING_FILE])
         and all(_bounded(path,limit=TASK_LIMIT)==files[FUNCTION_FILE if role=='function_recovery' else BIORED_FILE]
                 for role,path in task_paths.items())
         and sha(__file__) == implementation_pin, 'source or implementation changed during publication.')
    manifest = {'format': format_name, 'created_at': utcnow(), 'summary': summary,
        'operator_source_pins': pins, 'input_pins_authenticate_publisher': False,
        'files': {name: hashlib.sha256(raw).hexdigest() for name, raw in files.items()},
        'producer_implementation_sha256': implementation_pin, 'read_only': True,
        'raw_reference_rows_included': False, 'scientific_labels_created': False, 'source_graph_modified': False}
    manifest['content_sha256'] = digest(manifest)
    need(len(json.dumps(manifest).encode())<=(TASK_LIMIT if format_name==FORMAT_V4 else 250_000),
         'publication manifest exceeds its format bound.')
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
    header = _decode(_bounded(folder / 'publication.json',limit=TASK_LIMIT))
    format_name = header.get('format')
    need(format_name in {FORMAT, FORMAT_V2, FORMAT_V3, FORMAT_V4}, 'unsupported publication format.')
    if format_name!=FORMAT_V4:_bounded(folder/'publication.json')
    has_coess = any('coess_' + k in header.get('operator_source_pins', {}) for k in COESS_NAMES)
    expected_files = (V2_PUBLIC_FILES if has_coess else PUBLIC_FILES)
    if format_name == FORMAT_V3 or format_name==FORMAT_V4 and 'grounding' in header.get('operator_source_pins',{}):
        expected_files = expected_files | {GROUNDING_FILE}
    if format_name==FORMAT_V4:
        expected_files=expected_files|{filename for role,filename in (('function_recovery',FUNCTION_FILE),('biored',BIORED_FILE))
                                      if role in header.get('operator_source_pins',{})}
    names = {p.relative_to(folder).as_posix() for p in folder.rglob('*') if p.is_file()}
    need(names == expected_files | {'publication.json'} and not any(p.is_symlink() for p in folder.rglob('*')),
         'publication contains missing or additional files.')
    for name in names:
        _bounded(folder / name, limit=3_000_000 if name in COESS_NAMES.values() else
                 TASK_LIMIT if format_name==FORMAT_V4 and name in {FUNCTION_FILE,BIORED_FILE,'publication.json','report.html'} else 250_000)
    manifest, captured = _capture(folder, 'publication.json')
    need(manifest.get('format') == format_name and all(manifest.get(k) is False for k in (
         'raw_reference_rows_included', 'scientific_labels_created', 'source_graph_modified', 'input_pins_authenticate_publisher'))
         and manifest.get('read_only') is True, 'publication policy or format changed.')
    summary = _publication_summary(captured, manifest['operator_source_pins'], format_name)
    expected_readme = _publication_readme(format_name, has_coess,'grounding' in manifest['operator_source_pins'])
    need(manifest.get('summary') == summary and captured['README.txt'] == expected_readme.encode()
         and captured['report.html'] == render_html(summary).encode(), 'publication summary or presentation differs from its receipts.')
    return manifest, summary, captured


def list_publications(runs_dir):
    rows = []
    for folder in sorted(Path(runs_dir).iterdir(), reverse=True):
        if folder.is_symlink() or not folder.is_dir() or not re.fullmatch(r'[A-Za-z0-9_-]{1,80}', folder.name):
            continue
        path = folder / 'publication.json'
        if not path.is_file() or path.stat().st_size > TASK_LIMIT:
            continue
        try:
            if _decode(_bounded(path,limit=TASK_LIMIT)).get('format') not in {FORMAT, FORMAT_V2, FORMAT_V3, FORMAT_V4}:
                continue
            manifest, summary, _ = load_publication(folder)
            rows.append({'id': folder.name, 'created_at': manifest['created_at'], 'content_sha256': manifest['content_sha256'], 'summary': summary})
        except (ValueError, TypeError, KeyError, OSError):
            continue
    return {'assessments': rows}


def render_html(summary):
    """Escape every value; proof links name only allowlisted aggregate JSONs."""
    if summary.get('format')==FORMAT_V4+'.summary':
        return _v4_html(summary)
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


def _v4_html(summary):
    """Keep new reference-task results separate from the legacy graph scope."""
    esc=lambda v:escape(str(v),quote=True)
    number=lambda v:'Not reported' if v is None else format(v,'.6f') if type(v) in (int,float) else str(v)
    def table(headers,rows):
        return '<div class="table-wrap"><table><thead><tr>'+''.join('<th>'+esc(h)+'</th>' for h in headers)+'</tr></thead><tbody>'+''.join('<tr>'+''.join('<td>'+esc(v)+'</td>' for v in row)+'</tr>' for row in rows)+'</tbody></table></div>'
    parts=["<!doctype html><html lang='en'><meta charset='utf-8'><meta name='viewport' content='width=device-width,initial-scale=1'><title>Separate scientific assessment tasks</title>",
        '<style>body{font:16px system-ui;max-width:1250px;margin:2rem auto;padding:0 1rem;color:#203040}table{border-collapse:collapse;width:100%;font-size:13px}td,th{padding:.6rem;border-bottom:1px solid #ccd5df;text-align:left;vertical-align:top}.table-wrap{overflow:auto}code,pre{overflow-wrap:anywhere;white-space:pre-wrap}.scope{padding:1rem;background:#fff1d5}h2{margin-top:2rem}details{border:1px solid #ccd5df;border-radius:8px;padding:1rem;margin:1rem 0}summary{cursor:pointer;font-weight:600}</style>',
        '<h1>Scientific assessment: separate tasks and source scopes</h1><p class="scope">'+esc(summary['scope'])+'</p>']
    function=summary.get('function_recovery')
    if function:
        parts+=['<h2>'+esc(function['title'])+'</h2><p>'+esc(function['scope'])+'</p>',
            '<p>The original propagation primary and every declared control remain visible. Added-context comparisons are secondary; benchmark Fmax thresholds are not deployment confidence. Macro and fixed .5 results must be interpreted alongside pooled micro results.</p>',
            '<p>'+esc(function['roles']['original_primary'].get('conclusion','Original primary conclusion remains separately declared.'))+'</p>',
            '<p>Snapshot outcome status: '+esc(function['status_counts'])+'. Missing/unsupported outcomes are not replaced with zero.</p>']
        for denominator in function['denominators']:
            key=tuple(denominator[k] for k in ('frame','setting','namespace'))
            rows=[r for r in function['rows'] if tuple(r[k] for k in ('frame','setting','namespace'))==key]
            parts+=['<details><summary>'+esc(' · '.join(key))+' — eligible proteins '+esc(denominator['eligible_proteins'])+'; IA eligible '+esc(denominator['IA_eligible_proteins'])+'</summary>',
                table(['Method','Status','Micro Fmax','IA micro Fmax','Macro Fmax','IA macro Fmax','Fixed .5 precision','Fixed .5 recall','Fixed .5 F1','Fixed .5 native coverage ratio'],
                    [[r['method'],r['status'],*[number(r.get(k)) for k in ('micro_Fmax','IA_micro_Fmax','macro_Fmax','IA_macro_Fmax')],
                      *[number((r.get('fixed_0_5') or {}).get(k)) for k in ('PPV','recall','F1','coverage')]] for r in rows]),'</details>']
        parts+=['<details><summary>All saved paired comparisons</summary>',table(
            ['Frame / reference','Candidate','Comparator','Readout','Bootstrap mean difference','95% descriptive paired interval'],
            [[' / '.join(p[k] for k in ('frame','setting','namespace')),p['candidate'],p['comparator'],p.get('readout',''),
              number(p.get('difference_mean')),str(p['paired_95_percentile_interval'])] for p in function['paired_comparisons']]),
            '<p>Intervals remain conditional protein resamples; shared studies, graph context and annotation reuse limit independence. Reserved proteins are same-study transductive transfer, not a separate study or inductive unseen-gene test.</p></details>',
            '<details><summary>Native denominator definitions, historical sources and evaluator/runtime commitments</summary><pre>'
            +esc(json.dumps({'denominators':function['denominators'],'source_metadata':function['source_metadata']},indent=2))+'</pre></details>',
            '<ul>'+''.join('<li>'+esc(v)+'</li>' for v in function['limitations'])+'</ul>']
    bio=summary.get('agent_reference_agreement')
    if bio:
        parts+=['<h2>'+esc(bio['title'])+'</h2><p>'+esc(bio['scope'])+'</p>']
        for role,title in [('primary','Primary agent comparison'),('gene','Complete-gene secondary')]:
            report=bio[role];n=report['test_cases'] if role=='primary' else report['cases']
            pubs=report['test_publications'] if role=='primary' else report['publications']
            parts+=['<h3>'+title+'</h3><p>'+esc(n)+' candidate pairs; '+esc(pubs)+' source publications. Unresolved outputs remain in accuracy and recall denominators.</p>',
                table(['Fixed arm','Correct / candidates','Exact accuracy','Positive precision','Positive recall','Positive F1','Pair F1','Coverage','Unresolved'],
                    [[arm,str(m['exact_correct'])+' / '+str(m['cases']),number(m['exact_accuracy']),
                      *[number(m['exact_positive_relation'][k]) for k in ('precision','recall','f1')],number(m['entity_pair']['f1']),number(m['coverage']),m['unresolved']]
                     for arm,m in report['metrics'].items()])]
        primary=bio['primary'];artifact=bio['artifact']
        parts+=['<p>Frozen agent adoption criterion passed: <strong>'+esc(primary['agent_default_adoption_criterion_passed'])+'</strong>. This is a recorded numerical criterion, not a graph edit or proof of broad biological accuracy.</p>',
            '<details><summary>All agent comparisons and recorded execution costs</summary><pre>'+esc(json.dumps({'paired_comparisons':primary['agent_paired_comparisons'],'execution_costs':primary['execution_costs']},indent=2))+'</pre></details>',
            '<details><summary>Complete-gene publication-cluster uncertainty and relation-family scopes</summary><pre>'
            +esc(json.dumps({k:bio['gene'].get(k) for k in ('publication_cluster_uncertainty','per_entity_type_metrics',
                'comparison_interpretation','label_scope','sampling_scope','uncertainty_scope','reference_limitations')},indent=2))+'</pre></details>',
            '<details><summary>Released-artifact diagnostic: all native metric levels</summary><p>'+esc(artifact['interpretation'])+'</p>',
            '<p>'+esc(artifact['native_candidate_rows'])+' native candidate rows from '+esc(artifact['native_candidate_publications'])
            +' candidate-bearing publications in '+esc(artifact['released_corpus_abstracts'])+' released abstracts. These are separate denominators from the primary agent and complete-gene assessments.</p>',
            table(['Level','Precision','Recall','Single-checkpoint F1','Paper mean F1','Difference'],
                  [[level,*[number(row[k]) for k in ('precision','recall','f1')],number(artifact['paper_reported_10_seed_mean_F1'][level]),number(artifact['single_checkpoint_minus_paper_mean_F1'][level])]
                   for level,row in artifact['author_metric_reference_agreement'].items()]),'</details>',
            '<ul>'+''.join('<li>'+esc(v)+'</li>' for v in bio['limitations'])+'</ul>']
    legacy=deepcopy(summary);legacy['format']=FORMAT_V3+'.summary';legacy['scope']=summary['workspace_scope']
    old=render_html(legacy);body=old[old.index('<h1>'):].removesuffix('</html>')
    parts+=['<details><summary>Legacy 99-target workspace: source qualification and earlier development assessments</summary><p>'+esc(summary['workspace_scope'])+'</p>'+body+'</details>',
        '<h2>Aggregate source commitments</h2><ul>']
    parts+=['<li><a href="files/'+esc(s['file'])+'">'+esc(s['role'])+'</a>: <code>'+esc(s['file_sha256'])+'</code></li>' for s in summary['sources']]
    parts+=['</ul><p>Copied aggregate consistency and source hashes are checked; schema-valid output is not proof of factual accuracy. No raw cases, source text, model weights or prediction rows are published.</p></html>']
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
