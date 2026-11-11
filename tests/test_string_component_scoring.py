"""Synthetic score/join controls; no source retrieval or new outcome access."""
from copy import deepcopy
from pathlib import Path
import json
import sys
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))
import score_string_component as scoring


def fixture(labels=(False, False, True, True), functional=(.1, .4, .35, .8),
            physical=(.1, .4, .35, .8)):
    candidates, labels_rows, predictions = [], [], []
    for index, label in enumerate(labels):
        products, source_row = [f'P{index:04d}', f'Q{index:04d}'], index + 1
        flags = {name: False for name in scoring.EXPOSURE_FLAGS}
        flags['huri_registry_projected_match'] = bool(index % 2)
        flags['inmc_author_crosswalk_match'] = bool(index // 2 % 2)
        huri, inmc = bool(index % 2), bool(index // 2 % 2)
        status = 'detected' if label is True else ('not_detected' if label is False else 'test_failed')
        eligible = label is not None
        constructs = {'ad_orf_id': 'AD' + str(index), 'db_orf_id': 'DB' + str(index),
                      'protein_to_construct_orientation_inferred': False}
        comp = {'products': products, 'source_row': source_row,
            'identity': {'source_row': source_row, 'uniprot_a': products[1], 'uniprot_b': products[0],
                         **{key: constructs[key] for key in ('ad_orf_id', 'db_orf_id')}},
            'pharos_status': 'present_in_raw_ppi', 'comparator': 1, 'resolved_endpoint_count': 2,
            'provider_bundles': ['STRINGDB'], 'previous_pharos_status': 'unassessed',
            'lookup_record_sha256': 'record' + str(index), **flags,
            'huri_overlap': huri, 'inmc_overlap': inmc}
        candidate = {'products': products, 'source_row': source_row, 'constructs': constructs,
            'assay_eligible': eligible, 'assay_exclusion_reason': None if eligible else status,
            'historical_pharos_comparator_eligible': eligible, 'pharos_status': comp['pharos_status'],
            'pharos_present': 1, 'resolved_endpoint_count': 2, 'provider_bundles': ['STRINGDB'],
            'previous_pharos_status': 'unassessed', 'lookup_record_sha256': comp['lookup_record_sha256'],
            'exposure': {**flags, 'huri_overlap': huri, 'inmc_overlap': inmc,
                         'consumed_intact_exact_pair': False}}
        assay = {'products': products, 'source_row': source_row,
            **{key: constructs[key] for key in ('ad_orf_id', 'db_orf_id')},
            'assay_status': status, 'evaluable': eligible, 'detected': label}
        views = {}
        for arm, values in (('functional', functional), ('physical', physical)):
            value = values[index]
            state = ('numeric' if value is not None else
                     'physical_not_returned_under_profile' if arm == 'physical' and functional[index] is not None
                     else 'no_returned_functional_row')
            views[arm] = {'state': state,
                          'native_score': value, 'ranking_score': -1 if value is None else value}
        predictions.append({'products': products, 'source_row': source_row,
            'mapping_states': ['resolved', 'resolved'],
            'mapping_proof': [{'accession': products[0], 'status': 'resolved', 'string_id': f'9606.ENSP{index}A'},
                              {'accession': products[1], 'status': 'resolved', 'string_id': f'9606.ENSP{index}B'}],
            'query_batch': 'batch_' + str(index // 2), 'views': views})
        candidates.append(candidate)
        labels_rows.append({'comparator': comp, 'assay': assay, 'comparator_evaluable': eligible})
    return candidates, labels_rows, predictions


class StringComponentScoringTests(unittest.TestCase):
    def score(self, data=None):
        return scoring.score_rows(*(fixture() if data is None else data))

    def test_reuses_pinned_sklearn_known_example_and_identical_inputs(self):
        report = self.score()
        self.assertAlmostEqual(report['full_panel']['arms']['functional']['average_precision'], 5 / 6)
        self.assertEqual(report['full_panel']['physical_minus_functional_average_precision'], 0)
        self.assertTrue(report['ranking_vectors']['identical_eligible_inputs'])
        self.assertEqual(report['runtime']['scikit_learn'], '1.9.1')
        self.assertFalse(report['study_independence_established'])
        self.assertFalse(report['steward_improvement_tested'])
        self.assertFalse(report['confidence_intervals_computed'])

    def test_unranked_after_explicit_numeric_zero_not_native_zero(self):
        report = self.score(fixture((True, False), (0, .1), (0, None)))
        self.assertEqual(report['full_panel']['arms']['functional']['average_precision'], .5)
        self.assertEqual(report['full_panel']['arms']['physical']['average_precision'], 1)
        self.assertEqual(report['full_panel']['physical_minus_functional_average_precision'], .5)
        self.assertEqual(report['coverage_eligible']['physical']['states'], {'physical_not_returned_under_profile': 1, 'numeric': 1})
        self.assertEqual(report['jointly_numeric']['comparison']['arms']['physical']['pairs'], 1)

    def test_conditional_common_numeric_does_not_replace_full_panel(self):
        report = self.score(fixture((True, False, True), (.8, .7, .2), (.3, None, .9)))
        self.assertEqual(report['primary_population']['assay_eligible'], 3)
        self.assertEqual(report['full_panel']['arms']['functional']['pairs'], 3)
        common = report['jointly_numeric']['comparison']
        self.assertEqual(common['arms']['functional']['pairs'], 2)
        self.assertEqual(common['arms']['physical']['pairs'], 2)
        self.assertEqual(report['coverage_eligible']['physical']['explicit_numeric'], 2)

    def test_all_unranked_arm_is_unscorable(self):
        report = self.score(fixture((True, False), (.7, .1), (None, None)))
        arm = report['full_panel']['arms']['physical']
        self.assertEqual(arm['status'], 'unscorable_no_explicit_numeric_support')
        self.assertIsNone(arm['average_precision'])
        self.assertIsNone(report['full_panel']['physical_minus_functional_average_precision'])

    def test_exclusions_accounted_but_never_ranked(self):
        report = self.score(fixture((True, False, None), (.5, .1, .9), (.8, .3, .1)))
        self.assertEqual(report['primary_population'], {'all_nominations': 3, 'assay_eligible': 2,
            'detected': 1, 'not_detected': 1, 'assay_excluded': 1, 'exclusions': {'test_failed': 1}})
        self.assertEqual(report['coverage_all']['functional']['pairs'], 3)
        self.assertEqual(report['coverage_eligible']['functional']['pairs'], 2)
        self.assertEqual(sum(s['all_nominations'] for s in report['exposure_strata'].values()), 3)

    def test_historical_pharos_missingness_does_not_remove_eligible_pair(self):
        candidates, labels, predictions = fixture((True, False), (.6, .2), (.5, .1))
        comp = labels[0]['comparator']; candidate = candidates[0]
        comp.update(pharos_status='no_match_one_endpoint_resolved', comparator=None, resolved_endpoint_count=1)
        candidate.update(pharos_status=comp['pharos_status'], pharos_present=None,
                         resolved_endpoint_count=1, historical_pharos_comparator_eligible=False)
        labels[0]['comparator_evaluable'] = False
        report = self.score((candidates, labels, predictions))
        self.assertEqual(report['primary_population']['assay_eligible'], 2)
        self.assertEqual(report['historical_pharos_descriptive_anchor']['eligible_with_known_presence'], 1)

    def test_order_independent_join_and_fingerprints(self):
        candidates, labels, predictions = fixture()
        first = self.score((candidates, labels, predictions))
        second = self.score((list(reversed(candidates)), labels[1:] + labels[:1], list(reversed(predictions))))
        self.assertEqual(first, second)

    def test_population_duplicates_missing_and_mismatched_source_row(self):
        for mutate in (lambda c, l, p: p.pop(), lambda c, l, p: p.append(deepcopy(p[0])),
                       lambda c, l, p: p[0].update(source_row=50),
                       lambda c, l, p: p[0].update(products=list(reversed(p[0]['products'])))):
            data = fixture(); mutate(*data)
            with self.subTest(mutate=mutate), self.assertRaises(ValueError):
                self.score(data)

    def test_construct_eligibility_exposure_and_reference_join_must_match(self):
        mutations = [lambda c, l, p: c[0]['constructs'].update(ad_orf_id='AD1'),
            lambda c, l, p: l[0]['assay'].update(db_orf_id='other'),
            lambda c, l, p: c[0].update(assay_eligible=False),
            lambda c, l, p: c[0].update(assay_exclusion_reason='test_failed'),
            lambda c, l, p: l[0]['assay'].update(detected=True),
            lambda c, l, p: c[0]['exposure'].update(huri_overlap=True),
            lambda c, l, p: c[0].update(lookup_record_sha256='another')]
        for mutate in mutations:
            data = fixture(); mutate(*data)
            with self.subTest(mutate=mutate), self.assertRaises(ValueError):
                self.score(data)

    def test_label_bearing_prediction_and_technical_failures_rejected(self):
        data = fixture(); data[2][0]['detected'] = False
        with self.assertRaises(ValueError): self.score(data)
        for state in ('retrieval_failed', 'truncated', 'schema_failed', 'unknown', 'numeric'):
            data = fixture(); data[2][0]['views']['functional'].update(state=state, native_score=None, ranking_score=-1)
            with self.subTest(state=state), self.assertRaises(ValueError): self.score(data)

    def test_numeric_scores_unaltered_finite_and_boolean_not_numeric(self):
        for native, ranking in [(float('nan'), float('nan')), (float('inf'), float('inf')),
                                (-.1, -.1), (1.1, 1.1), (True, True), (.5, .6), (.5, True)]:
            data = fixture(); data[2][0]['views']['functional'].update(native_score=native, ranking_score=ranking)
            with self.subTest(native=native, ranking=ranking), self.assertRaises(ValueError): self.score(data)

    def test_physical_hyphen_distinct_from_no_row_and_mapping_missingness(self):
        data = fixture((True, False), (.8, None), (None, None))
        data[2][0]['views']['physical']['state'] = 'physical_not_returned_under_profile'
        report = self.score(data)
        self.assertEqual(report['coverage_eligible']['physical']['states'],
            {'no_returned_functional_row': 1, 'physical_not_returned_under_profile': 1})
        data[2][0]['views']['functional'].update(state='physical_not_returned_under_profile', native_score=None, ranking_score=-1)
        with self.assertRaises(ValueError): self.score(data)

    def test_no_positive_stratum_has_no_synthetic_metric(self):
        report = self.score(fixture((False,), (.5,), (.4,)))
        self.assertEqual(report['full_panel']['arms']['functional']['status'], 'unscorable_no_recorded_detections')
        self.assertIsNone(report['full_panel']['arms']['functional']['average_precision'])

    def test_mapping_failure_states_keep_complete_population(self):
        for source_state, projected in (('unmapped', 'unmapped'), ('ambiguous', 'ambiguous'),
                                        ('mapping_limit_reached', 'ambiguous')):
            data = fixture()
            prediction = data[2][0]
            prediction['mapping_states'][0] = source_state
            prediction['mapping_proof'][0].update(status=source_state, string_id=None)
            prediction['query_batch'] = None
            for view in prediction['views'].values():
                view.update(state=projected, native_score=None, ranking_score=-1)
            report = self.score(data)
            self.assertEqual(report['primary_population']['assay_eligible'], 4)
            self.assertEqual(report['coverage_eligible']['physical']['states'][projected], 1)

    def test_mapping_or_overlay_inconsistency_cannot_be_justified_by_valid_numbers(self):
        mutations = [lambda p: p['mapping_proof'][0].update(accession='OTHER'),
            lambda p: p['mapping_proof'][0].update(status='unmapped'),
            lambda p: p.update(query_batch=None),
            lambda p: p['mapping_proof'][0].update(string_id='10090.MOUSE'),
            lambda p: p['mapping_proof'][1].update(string_id=p['mapping_proof'][0]['string_id']),
            lambda p: p['views']['functional'].update(state='no_returned_functional_row', native_score=None, ranking_score=-1)]
        for mutate in mutations:
            data = fixture(); mutate(data[2][0])
            with self.subTest(mutate=mutate), self.assertRaises(ValueError): self.score(data)

    def test_result_packet_verifies_capture_first_and_replays_saved_metric(self):
        candidates, labels, predictions = fixture()
        captured = {'protocol': {'content_sha256': 'frozen', 'rules': {'scoring_python': scoring.platform.python_version()}}, 'report': {'content_sha256': 'capture'},
                    'candidates': candidates, 'label_rows': labels, 'predictions': predictions}
        calls = []
        fake = SimpleNamespace(verify_capture=lambda path: (calls.append(path), captured)[1])
        with tempfile.TemporaryDirectory() as temporary, patch.dict(sys.modules, {'run_string_component': fake}):
            capture, out = Path(temporary).resolve() / 'capture', Path(temporary).resolve() / 'results'
            capture.mkdir()
            report = scoring.score_capture(capture, out)
            self.assertEqual(report['status'], 'completed')
            self.assertEqual(len(calls), 2)  # Before metrics and after writing the sealed output.
            self.assertEqual(scoring.verify_result(capture, out), report)
            with self.assertRaises(ValueError): scoring.score_capture(capture, out)
            metric_path = out / 'metrics.json'
            metric = json.loads(metric_path.read_text())
            metric['full_panel']['arms']['physical']['average_precision'] = .99
            metric_path.write_text(json.dumps(metric))
            with self.assertRaises(ValueError): scoring.verify_result(capture, out)

    def test_capture_scoring_and_replay_require_frozen_python_runtime(self):
        fake = SimpleNamespace(verify_capture=lambda path: {'protocol': {'rules': {'scoring_python': '0.0.0'}}})
        with tempfile.TemporaryDirectory() as temporary, patch.dict(sys.modules, {'run_string_component': fake}):
            out = Path(temporary).resolve() / 'results'
            with self.assertRaisesRegex(ValueError, 'Python runtime'):
                scoring.score_capture(Path(temporary).resolve() / 'capture', out)
            with self.assertRaisesRegex(ValueError, 'Python runtime'):
                scoring.verify_result(Path(temporary).resolve() / 'capture', out)
            self.assertFalse(out.exists())

    def test_failed_capture_verification_does_not_emit_metrics(self):
        def fail(path):
            raise ValueError('Source capture failed verification.')
        with tempfile.TemporaryDirectory() as temporary, patch.dict(sys.modules, {'run_string_component': SimpleNamespace(verify_capture=fail)}):
            out = Path(temporary) / 'results'
            with self.assertRaises(ValueError): scoring.score_capture(Path(temporary) / 'capture', out)
            self.assertFalse(out.exists())


if __name__ == '__main__':
    unittest.main()
