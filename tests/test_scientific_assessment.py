"""Invented aggregate receipts, not scientific labels or experimental data."""
from copy import deepcopy
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from biograph_steward.client import digest, write_json
from biograph_steward.file_utils import sha
from biograph_steward import scientific_assessment as module


def sealed(value):
    value = deepcopy(value)
    value.pop('content_sha256', None)
    value['content_sha256'] = digest(value)
    return value


def fixtures(root):
    """Small invented counts preserve the real producer schema/units."""
    root.mkdir()
    values = {}
    values['history'] = {'format': module.ROLES['history'], 'source_graph_file_sha256': 'a' * 64,
        'scientific_accuracy_measured': False, 'independent_reference': False,
        'counts': {'unique_connection_statuses': {'explicitly_encoded_protein_xref': 1, 'compatible_gene_level_xref': 2, 'unresolved': 2},
            'original_unique_subject_version_connections': 5, 'exact_publisher_bound_versions': 3,
            'requested_distinct_versions': 4, 'author_schema_passed_models': 3}}
    paths = {role: root / (role + '.json') for role in module.ROLES}
    write_json(paths['history'], sealed(values['history']))
    values['history'] = json.loads(paths['history'].read_text())
    profile = 'source-faithful-exact-historical-WikiPathways-native-content.v1'
    values['wiki_policy'] = {'format': module.ROLES['wiki_policy'], 'profile': profile,
        'history_content_sha256': values['history']['content_sha256'], 'history_report_file_sha256': sha(paths['history']),
        'source_graph_file_sha256': 'a' * 64, 'packet_id': 'packet:invented', 'graph_sha256': 'b' * 64,
        'source_graph_mutated': False, 'scientific_review_states_promoted': False, 'biological_truth_assessed': False,
        'missing_native_content_is_negative': False, 'current_GMT_ablation_changed': False,
        'retained_content_sha256': 'c' * 64, 'files': {'retained/report.json': 'd' * 64},
        'counts': {'total_edges': 10, 'prune': 0, 'native_positive_groups_replayed': 3}}
    values['composition'] = {'format': module.ROLES['composition'], 'packet_id': 'packet:invented', 'graph_sha256': 'b' * 64,
        'source_graph_mutated': False, 'biological_truth_adjudicated': False,
        'inputs': [{'method': 'current-go-primary-term-identifiers.v1'}, {'method': profile,
            'report_content_sha256': 'c' * 64, 'report_file_sha256': 'd' * 64}],
        'output_retained_report_content_sha256': 'e' * 64, 'output_retained_report_sha256': 'f' * 64,
        'counts': {'keep': 7, 'prune': 1, 'abstain': 2}}
    values['references'] = {'format': module.ROLES['references'],
        'all_independent_scientific_truth_unreviewed': True, 'source_graph_changed': False,
        'prediction_benefit_measured': False, 'source_study_independence_established': False,
        'current_default_disposition_binding': {'report_content_sha256': 'e' * 64, 'report_file_sha256': 'f' * 64,
            'evidence_edge_counts': {'keep': 7, 'prune': 1, 'abstain': 2}, 'current_pruned_assertions': 1},
        'GO': {'original_family_assertions': 4, 'identified_compatible_experimental_assertions': 1, 'remaining_GO_UNKNOWN': 3,
            'removed_assertions': 1, 'all_373_identified_compatible_assertions_retained': True,
            'reference_positive_eligibility_makes_resolved_only_ratio_uninformative': True,
            'ontology_release': 'invented-release', 'source_generated': 'invented-date'},
        'CRC_genomic_cohort': {'original_disease_association_assertions': 2, 'identified_exact_context_supported_assertions': 1,
            'UNKNOWN_assertions': 1, 'all32_retained_in_source_faithful_default': True, 'negative_labels_assigned': 0,
            'unseen_confirmatory_holdout': False, 'heterogeneous_GO_and_genomics_axes_pooled': False,
            'specimens': 5, 'distinct_participants': 4},
        'CIViC': {'original_reported_response_assertions': 3, 'clinical_accuracy_resolved': 0,
            'exact_context_matched_edges': 0, 'expert_accepted_clinical_Assertions': 2,
            'complete_native_conclusions_preserved_in_separate_layer': True,
            'aggregate_conclusions_replace_original_observations': False}}
    score_roles = ['current_score', 'historical_score']
    for i, role in enumerate(score_roles, 1):
        values[role] = {'format': module.ROLES[role], 'packet_report_sha256': str(i) * 64,
            'retrospective_consumed_reference': True, 'fresh_independent_confirmation': False,
            'scientific_truth_accuracy_measured': False}
        write_json(paths[role], sealed(values[role]))
        values[role] = json.loads(paths[role].read_text())
    experiments = []
    for kind, role in zip(module.KINDS, score_roles):
        arms = []
        for i, arm in enumerate(module.ARMS):
            ap, au = 0.6 + i * 0.01, 0.7 + i * 0.01
            arms.append({'arm': arm, 'mean_AP': ap, 'mean_AUROC': au, 'unique_memberships': 5 if i == 0 else 3,
                'AP_by_seed': {str(s): ap for s in [17, 43, 101]}, 'AUROC_by_seed': {str(s): au for s in [17, 43, 101]}})
        experiments.append({'qualification_kind': kind, 'scores_report_file_sha256': sha(paths[role]),
            'scores_content_sha256': values[role]['content_sha256'], 'frozen_packet_report_file_sha256': values[role]['packet_report_sha256'],
            'fresh_confirmation': False, 'primary_eligible_pairs': 5, 'positive_count': 2,
            'conditional_nondetection_count': 3, 'arms': arms, 'paired_deltas_by_seed': {}})
    values['utility'] = {'format': module.ROLES['utility'], 'graph_mutated': False, 'new_biology_discovery_claimed': False,
        'conclusion': 'Invented development comparison; no biological conclusion.', 'production_decision': 'Preserve unknown context.',
        'native_source_finding': {'verified_model_versions': 3, 'requested_versions': 4, 'original_unique_connections': 5,
            'literal_protein_xref_connections': 1, 'compatible_gene_xref_connections': 2, 'unknown_connections': 2},
        'endpoint_scope': {'reference_previously_consumed': True, 'non_detection_is_universal_noninteraction': False,
            'seeds_are_independent_biological_replicates': False, 'whole_graph_scientific_accuracy_measured': False,
            'formal_confidence_interval': None, 'p_values': None, 'primary_measured_QC_eligible_off_diagonal_pairs': 5,
            'detected': 2, 'conditional_nondetected': 3}, 'experiments': experiments}
    for role, value in values.items():
        if role not in {'history', *score_roles}:
            write_json(paths[role], sealed(value))
    return paths, {role: sha(path) for role, path in paths.items()}


class ScientificAssessmentTests(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.root = Path(tmp.name).resolve()
        self.paths, self.pins = fixtures(self.root / 'sources')

    def change_source(self, role, change):
        value = json.loads(self.paths[role].read_text())
        change(value)
        write_json(self.paths[role], sealed(value))
        self.pins[role] = sha(self.paths[role])

    def publish(self, name='assessment'):
        return module.publish(self.paths, self.root / name, expected_source_pins=self.pins)

    def test_publication_preserves_units_unknowns_both_comparisons_and_exact_source_reports(self):
        manifest = self.publish()
        _, summary, files = module.load_publication(self.root / 'assessment')
        self.assertEqual(summary['native_history']['literal_protein_xref'], 1)
        self.assertEqual(summary['native_history']['compatible_gene_xref'], 2)
        self.assertEqual(summary['native_history']['unknown_connections'], 2)
        self.assertEqual(summary['default_view']['retained'], 9)
        self.assertEqual(summary['GO']['original'], 4)
        self.assertEqual(summary['GO']['UNKNOWN'], 3)
        self.assertEqual(summary['CIViC']['exact_original_contexts_resolved'], 0)
        self.assertEqual(len(summary['INMC']['experiments']), 2)
        self.assertTrue(all(len(x['arms']) == 4 for x in summary['INMC']['experiments']))
        self.assertIsNone(summary['whole_graph_scientific_precision'])
        self.assertFalse(summary['prospective_prediction_gain_established'])
        self.assertEqual(set(files), module.PUBLIC_FILES | {'publication.json'})
        for role, path in self.paths.items():
            self.assertEqual(files[module.SOURCE_NAMES[role]], path.read_bytes())
        self.assertNotIn('OpenCell', files['report.html'].decode())
        listed = module.list_publications(self.root)['assessments']
        self.assertEqual([x['id'] for x in listed], ['assessment'])
        self.assertEqual(listed[0]['content_sha256'], manifest['content_sha256'])

    def test_operator_pin_mismatch_rejects_before_writing(self):
        self.pins['history'] = '0' * 64
        with self.assertRaisesRegex(ValueError, 'operator pin'):
            self.publish()
        self.assertFalse((self.root / 'assessment').exists())

    def test_mixed_source_view_cannot_supply_a_current_default_claim(self):
        self.change_source('composition', lambda x: x.update(output_retained_report_content_sha256='0' * 64))
        with self.assertRaisesRegex(ValueError, 'different retained view'):
            self.publish()

    def test_compatible_subset_cannot_be_recast_as_whole_family_accuracy(self):
        self.change_source('references', lambda x: x['GO'].update(original_family_assertions=1))
        with self.assertRaisesRegex(ValueError, 'GO family denominator'):
            self.publish()
        self.assertFalse((self.root / 'assessment').exists())

    def test_expert_aggregate_conclusions_do_not_upgrade_original_response_claims(self):
        self.change_source('references', lambda x: x['CIViC'].update(clinical_accuracy_resolved=2))
        with self.assertRaisesRegex(ValueError, 'must not replace'):
            self.publish()

    def test_nonnegative_count_requires_integer_not_boolean_or_float(self):
        for value in [True, -1, 5.0]:
            with self.subTest(value=value):
                with self.assertRaisesRegex(ValueError, 'count'):
                    module._count(value)

    def test_source_coverage_cannot_promote_to_independent_truth_or_fresh_prediction(self):
        self.change_source('references', lambda x: x.update(source_study_independence_established=True))
        with self.assertRaisesRegex(ValueError, 'scope changed'):
            self.publish()

    def test_missing_control_or_changed_seed_mean_fails(self):
        self.change_source('utility', lambda x: x['experiments'][0]['arms'].pop())
        with self.assertRaisesRegex(ValueError, 'control arms'):
            self.publish()

    def test_mean_must_equal_its_existing_three_seed_values(self):
        self.change_source('utility', lambda x: x['experiments'][0]['arms'][0].update(mean_AP=0.99))
        with self.assertRaisesRegex(ValueError, 'aggregate mean'):
            self.publish()

    def test_text_is_escaped_and_receipt_links_only_use_fixed_copied_paths(self):
        self.change_source('utility', lambda x: x.update(conclusion='<script>alert("bad")</script>'))
        self.publish()
        raw = (self.root / 'assessment/report.html').read_text()
        self.assertNotIn('<script>', raw)
        self.assertIn('&lt;script&gt;', raw)
        self.assertIn('files/sources/history.json', raw)

    def test_resealed_summary_tamper_is_detected_against_sources(self):
        self.publish()
        path = self.root / 'assessment/publication.json'
        value = json.loads(path.read_text())
        value['summary']['GO']['UNKNOWN'] = 0
        write_json(path, sealed(value))
        with self.assertRaisesRegex(ValueError, 'summary or presentation'):
            module.load_publication(path.parent)

    def test_extra_raw_data_or_changed_embedded_source_is_rejected(self):
        self.publish()
        folder = self.root / 'assessment'
        (folder / 'native.gpml').write_text('<private-native/>')
        with self.assertRaisesRegex(ValueError, 'additional files'):
            module.load_publication(folder)
        (folder / 'native.gpml').unlink()
        (folder / 'sources/history.json').write_text('{}')
        with self.assertRaises(ValueError):
            module.load_publication(folder)
        self.assertEqual(module.list_publications(self.root)['assessments'], [])

    def test_source_mutation_leaves_no_success_manifest(self):
        original = module.render_html
        def mutate(summary):
            self.paths['history'].write_text('{}')
            return original(summary)
        with patch.object(module, 'render_html', side_effect=mutate):
            with self.assertRaisesRegex(ValueError, 'changed during publication'):
                self.publish()
        self.assertFalse((self.root / 'assessment/publication.json').exists())


if __name__ == '__main__':
    unittest.main()
