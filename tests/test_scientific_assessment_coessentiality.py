"""Invented saved aggregates test the optional viewer, not scientific labels."""
from copy import deepcopy
import json
from pathlib import Path
import tempfile
import unittest

from biograph_steward import scientific_assessment as module
from biograph_steward.client import write_json
from biograph_steward.file_utils import sha
from test_scientific_assessment import fixtures, sealed


def coessentiality_fixtures(root, base_paths, base_pins):
    root.mkdir()
    utility = json.loads(base_paths['utility'].read_text())
    for kind, pin in (('current_release_eligibility', '1' * 64),
                      ('historical_native_xref_compatibility', '2' * 64)):
        next(x for x in utility['experiments'] if x['qualification_kind'] == kind)['frozen_packet_content_sha256'] = pin
    write_json(base_paths['utility'], sealed(utility))
    base_pins['utility'] = sha(base_paths['utility'])
    names = ['normalized', 'current', 'historical']
    names += [f'{t}_legacy_{k}' for t in ('current', 'historical')
              for k in ('equal_count_random', 'qualified_degree_permutation')]
    names += [f'{t}_{k}_{i:02}' for t in ('current', 'historical')
              for k in ('count', 'degree') for i in range(20)]
    curves = {}
    for arm in names:
        curves[arm] = {}
        value = 1.0 if arm == 'normalized' else 0.8 if arm in {'current', 'historical'} else 1.2
        for scope in module.COESS_SCOPES:
            curves[arm][scope] = [{'N': n, 'query_frame': 92, 'reference_available_queries': 92,
                'unavailable_queries': 0, 'aggregation': 'all_fixed_queries',
                'selected_slots_if_reference_available': 92 * n, 'observed_hits': 23.0 * n,
                'expected_hits': 23.0 * n / value, 'observed_hit_fraction': 0.25,
                'expected_hit_fraction': 0.25 / value, 'enrichment': value,
                'status': 'scorable', 'zero_expected_enrichment_undefined': False} for n in range(1, 11)]
    controls = {t: {k: {scope: [{'N': n, 'draws': 20, 'defined_draws': 20,
        'minimum': 1.2, 'median': 1.2, 'maximum': 1.2, 'not_a_confidence_interval': True}
        for n in range(1, 11)] for scope in module.COESS_SCOPES} for k in ('count', 'degree')}
        for t in ('current', 'historical')}
    paths = {k: root / (k + '.json') for k in module.COESS_NAMES}
    write_json(paths['curves'], curves)
    write_json(paths['controls'], controls)
    frozen = sealed({'format': 'biograph-steward.coessentiality-frozen-comparison.v1',
        'source_current_content_sha256': '1' * 64, 'source_historical_content_sha256': '2' * 64,
        'source_deep_replay_completed': True, 'scientific_packet_unchanged_since_original_pre_value_freeze': True,
        'original_pre_value_scientific_freeze_content_sha256': '3' * 64,
        'transport_repair_content_sha256': '4' * 64,
        'preexisting_exposure_scope': 'Invented preserved transport failure, not experimental data.',
        'arm_membership_counts': {k: 5 for k in names}})
    write_json(paths['frozen'], frozen)
    capture = sealed({'format': 'biograph-steward.coessentiality-native-column-capture.v1',
        'frozen_comparison_content_sha256': frozen['content_sha256'],
        'frozen_report_file_sha256': sha(paths['frozen']), 'full_matrix_files_retrieved_or_hashed': False})
    write_json(paths['capture'], capture)
    score = sealed({'format': 'biograph-steward.coessentiality-functional-concordance.v1',
        'frozen_comparison_content_sha256': frozen['content_sha256'],
        'native_capture_content_sha256': capture['content_sha256'],
        'input_report_file_sha256': {'invented/frozen/report.json': sha(paths['frozen']),
                                    'invented/captured/report.json': sha(paths['capture'])},
        'files': {'curves.json': sha(paths['curves']), 'descriptive_control_envelopes.json': sha(paths['controls'])},
        'query_genes': 92, 'pair_scope_counts': {'nonsyntenic': 3968, 'syntenic': 218},
        'all_N_and_all_arms_reported': True, 'scientific_truth_labels_created': False,
        'PPIs_or_causal_mechanisms_inferred': False, 'model_fitted_or_graph_changed': False,
        'FDR_or_significance_reconstructed': False,
        'full_curve_descriptive_assessment': {t: {
            'pointwise_above_baseline_and_all_controls_at_every_N': False,
            'is_statistical_significance_or_generalized_biological_gain': False,
            'points': [{'N': n, 'all_enrichments_defined': True,
                        'exceeds_normalized_and_all_40_draws': False} for n in range(1, 11)]}
            for t in ('current', 'historical')},
        'limitations': ['Invented test aggregates. No biological label or prediction claim.']})
    write_json(paths['score'], score)
    return paths, {k: sha(p) for k, p in paths.items()}


class ScientificAssessmentCoessentialityTests(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.root = Path(tmp.name).resolve()
        self.paths, self.pins = fixtures(self.root / 'base')
        self.extra, self.extra_pins = coessentiality_fixtures(self.root / 'extra', self.paths, self.pins)

    def publish(self, name='publication'):
        return module.publish(self.paths, self.root / name, expected_source_pins=self.pins,
            coessentiality_reports=self.extra, expected_coessentiality_pins=self.extra_pins)

    def test_optional_v2_replays_all_curves_controls_and_boundaries_without_raw_values(self):
        manifest = self.publish()
        loaded, summary, files = module.load_publication(self.root / 'publication')
        self.assertEqual(manifest, loaded)
        self.assertEqual(manifest['format'], module.FORMAT_V2)
        value = summary['coessentiality']
        self.assertEqual((value['query_genes'], value['primary_pairs']), (92, 3968))
        self.assertEqual((value['arm_count'], value['scope_count']), (87, 5))
        self.assertEqual(value['N'], list(range(1, 11)))
        self.assertEqual(len(summary['sources']), 12)
        self.assertFalse(value['prediction_gain_established'])
        self.assertFalse(value['biological_negatives_assigned'])
        self.assertFalse(value['raw_pair_or_matrix_values_included'])
        self.assertTrue(value['reference_now_consumed'])
        self.assertIn('not a CRC-specific reference', value['scope'])
        self.assertEqual(set(files), module.ALL_PUBLIC_FILES | {'publication.json'})
        self.assertEqual(json.loads(files['sources/coess_curves.json']), json.loads(self.extra['curves'].read_text()))
        self.assertNotIn('native_pair_values.jsonl', files)
        self.assertEqual(value['controls']['current']['count'][0]['absolute_hit_fraction']['median'], 0.25)
        self.assertIn(b'prediction improvement', files['report.html'])
        self.assertEqual(len(module.list_publications(self.root)['assessments']), 1)

    def test_original_seven_receipt_v1_publishing_and_loading_remains_unchanged(self):
        manifest = module.publish(self.paths, self.root / 'legacy', expected_source_pins=self.pins)
        loaded, summary, files = module.load_publication(self.root / 'legacy')
        self.assertEqual(manifest, loaded)
        self.assertEqual(manifest['format'], module.FORMAT)
        self.assertNotIn('coessentiality', summary)
        self.assertEqual(set(files), module.PUBLIC_FILES | {'publication.json'})
        self.assertEqual(files['README.txt'], module.README.encode())

    def test_mutated_source_and_oversized_curves_fail_explicit_pins_and_bound(self):
        self.extra['curves'].write_bytes(self.extra['curves'].read_bytes() + b' ')
        with self.assertRaisesRegex(ValueError, 'operator pin'):
            self.publish('changed')
        self.extra['curves'].write_bytes(b' ' * 3_000_001)
        with self.assertRaisesRegex(ValueError, 'compact ordinary'):
            self.publish('oversized')

    def test_resealed_study_graph_or_capture_mismatch_is_rejected(self):
        frozen = json.loads(self.extra['frozen'].read_text())
        frozen['source_current_content_sha256'] = 'f' * 64
        write_json(self.extra['frozen'], sealed(frozen))
        self.extra_pins['frozen'] = sha(self.extra['frozen'])
        with self.assertRaisesRegex(ValueError, 'study graph'):
            self.publish('wrong_study')

    def test_resealed_capture_identity_mismatch_is_rejected(self):
        capture = json.loads(self.extra['capture'].read_text())
        capture['frozen_comparison_content_sha256'] = 'f' * 64
        write_json(self.extra['capture'], sealed(capture))
        self.extra_pins['capture'] = sha(self.extra['capture'])
        with self.assertRaisesRegex(ValueError, 'native capture differ'):
            self.publish('wrong_capture')

    def test_resealed_summary_and_mutated_published_aggregate_are_not_trusted(self):
        self.publish()
        folder = self.root / 'publication'
        manifest = json.loads((folder / 'publication.json').read_text())
        manifest['summary']['coessentiality']['interpretation'] = 'Invented biological improvement.'
        write_json(folder / 'publication.json', sealed(manifest))
        with self.assertRaisesRegex(ValueError, 'summary or presentation'):
            module.load_publication(folder)
        self.publish('second')
        (self.root / 'second/sources/coess_controls.json').write_text('{}')
        with self.assertRaises(ValueError):
            module.load_publication(self.root / 'second')

    def test_resealed_scorer_cannot_accept_wrong_curve_inventory_or_gain_claim(self):
        score = json.loads(self.extra['score'].read_text())
        score['files']['curves.json'] = 'e' * 64
        write_json(self.extra['score'], sealed(score))
        self.extra_pins['score'] = sha(self.extra['score'])
        with self.assertRaisesRegex(ValueError, 'scorer inventory'):
            self.publish('wrong_curve')
        score['files']['curves.json'] = sha(self.extra['curves'])
        score['full_curve_descriptive_assessment']['current']['pointwise_above_baseline_and_all_controls_at_every_N'] = True
        write_json(self.extra['score'], sealed(score))
        self.extra_pins['score'] = sha(self.extra['score'])
        with self.assertRaisesRegex(ValueError, 'negative descriptive'):
            self.publish('wrong_gain')

    def test_envelope_must_equal_all_twenty_saved_draws_and_all_scopes_remain(self):
        controls = json.loads(self.extra['controls'].read_text())
        controls['current']['count']['nonsyntenic'][0]['median'] = 1.1
        write_json(self.extra['controls'], controls)
        self.extra_pins['controls'] = sha(self.extra['controls'])
        score = json.loads(self.extra['score'].read_text())
        score['files']['descriptive_control_envelopes.json'] = self.extra_pins['controls']
        write_json(self.extra['score'], sealed(score))
        self.extra_pins['score'] = sha(self.extra['score'])
        with self.assertRaisesRegex(ValueError, 'saved aggregate draws'):
            self.publish('wrong_envelope')

    def test_no_arm_or_diagnostic_scope_can_be_dropped_from_resealed_aggregates(self):
        original = json.loads(self.extra['curves'].read_text())
        for number, missing in enumerate(('arm', 'scope')):
            curves = deepcopy(original)
            if missing == 'arm':
                curves.pop('current_count_19')
            else:
                curves['normalized'].pop('syntenic')
            write_json(self.extra['curves'], curves)
            self.extra_pins['curves'] = sha(self.extra['curves'])
            score = json.loads(self.extra['score'].read_text())
            score['files']['curves.json'] = self.extra_pins['curves']
            write_json(self.extra['score'], sealed(score))
            self.extra_pins['score'] = sha(self.extra['score'])
            with self.subTest(missing=missing), self.assertRaisesRegex(ValueError, '87 frozen arms'):
                self.publish('dropped_' + str(number))


if __name__ == '__main__':
    unittest.main()
