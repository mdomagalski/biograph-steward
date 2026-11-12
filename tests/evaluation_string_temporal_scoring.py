"""Synthetic native 12.0 scoring controls; no network or fresh assay access."""
from copy import deepcopy
import json
from pathlib import Path
import sys
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))
import score_string_temporal as scoring
from evaluation_string_component_scoring import fixture as original_fixture


def fixture(labels=(False, False, True, True), functional=(.1, .4, .35, .8),
            physical=(.1, .4, .35, .8)):
    # The consumed overlay-compatible reference stays separate from new native
    # predictions. Physical-only support does not require inventing a reference.
    candidates, labels_rows, reference = original_fixture(
        labels, tuple(.5 for _ in labels), tuple(.4 for _ in labels))
    predictions = deepcopy(reference)
    for index, row in enumerate(predictions):
        base = 'network_' + str(index // 2)
        row['query_batch'] = {arm: arm + '_' + base for arm in scoring.ARMS}
        for arm, values in (('functional', functional), ('physical', physical)):
            value = values[index]
            row['views'][arm] = {'state': 'numeric' if value is not None else 'no_returned_native_row',
                                 'native_score': value, 'ranking_score': -1 if value is None else value}
    return candidates, labels_rows, predictions, reference


class StringTemporalScoringTests(unittest.TestCase):
    def score(self, data=None):
        return scoring.score_rows(*(fixture() if data is None else data))

    def test_established_sklearn_ap_and_control_claims(self):
        result = self.score()
        self.assertAlmostEqual(result['full_panel']['arms']['functional']['average_precision'], 5 / 6)
        self.assertEqual(result['full_panel']['physical_minus_functional_average_precision'], 0)
        self.assertTrue(result['ranking_vectors']['identical_eligible_inputs'])
        self.assertEqual(result['runtime']['scikit_learn'], '1.9.1')
        self.assertEqual(result['source_release'], '12.0')
        self.assertEqual(result['predictor_design'], 'separate_native_networks')
        self.assertTrue(result['temporal_control'])
        for flag in ('study_independence_established', 'steward_improvement_tested',
                     'scientific_accuracy_measured', 'thresholds_tuned', 'graph_modified'):
            self.assertIs(result[flag], False)

    def test_physical_only_native_row_is_valid(self):
        result = self.score(fixture((True, False), (None, .3), (.8, None)))
        self.assertEqual(result['coverage_eligible']['functional']['states'],
                         {'numeric': 1, 'no_returned_native_row': 1})
        self.assertEqual(result['coverage_eligible']['physical']['states'],
                         {'numeric': 1, 'no_returned_native_row': 1})
        self.assertEqual(result['full_panel']['arms']['physical']['average_precision'], 1)
        self.assertEqual(result['jointly_numeric']['comparison']['arms']['functional']['pairs'], 0)

    def test_native_zero_ranks_above_valid_missing_row(self):
        result = self.score(fixture((True, False), (0, .1), (0, None)))
        self.assertEqual(result['full_panel']['arms']['physical']['average_precision'], 1)
        self.assertEqual(result['full_panel']['physical_minus_functional_average_precision'], .5)
        self.assertEqual(result['coverage_eligible']['physical']['explicit_numeric'], 1)
        self.assertEqual(result['unranked_policy']['ordinal_value'], -1)

    def test_common_numeric_uses_actual_new_release_denominator(self):
        data = fixture((True, False, True), (.8, None, .2), (None, .1, .9))
        result = self.score(data)
        self.assertEqual(result['primary_population']['assay_eligible'], 3)
        self.assertEqual(result['jointly_numeric']['comparison']['arms']['physical']['pairs'], 1)
        self.assertEqual(result['jointly_numeric']['comparison']['arms']['physical']['detected'], 1)
        self.assertEqual(result['full_panel']['arms']['functional']['pairs'], 3)
        self.assertEqual(sum(row['views']['functional']['state'] == 'numeric' for row in data[3]), 3)

    def test_all_unranked_view_is_unscorable(self):
        result = self.score(fixture((True, False), (.7, .1), (None, None)))
        item = result['full_panel']['arms']['physical']
        self.assertEqual(item['status'], 'unscorable_no_explicit_numeric_support')
        self.assertIsNone(item['average_precision'])
        self.assertIsNone(result['full_panel']['physical_minus_functional_average_precision'])

    def test_no_positive_population_unscorable_and_four_strata_preserved(self):
        result = self.score(fixture((False,), (.5,), (.4,)))
        self.assertEqual(result['full_panel']['arms']['functional']['status'],
                         'unscorable_no_recorded_detections')
        self.assertEqual(len(result['exposure_strata']), 4)
        self.assertEqual(result['exposure_strata']['huri=True,inmc=True']['full_panel']['arms']['functional']['status'],
                         'unscorable_empty_population')

    def test_exclusions_stay_out_of_scoring_and_strata_retain_all_nominations(self):
        result = self.score(fixture((True, False, None), (.5, .1, .9), (.8, .3, .1)))
        self.assertEqual(result['primary_population'], {'all_nominations': 3, 'assay_eligible': 2,
            'detected': 1, 'not_detected': 1, 'assay_excluded': 1, 'exclusions': {'test_failed': 1}})
        self.assertEqual(sum(item['all_nominations'] for item in result['exposure_strata'].values()), 3)
        self.assertEqual(sum(item['assay_eligible'] for item in result['exposure_strata'].values()), 2)

    def test_missing_historical_pharos_does_not_exclude_native_eligible_pair(self):
        data = fixture((True, False), (.6, .2), (.5, .1))
        candidate, comp = data[0][0], data[1][0]['comparator']
        comp.update(pharos_status='no_match_one_endpoint_resolved', comparator=None, resolved_endpoint_count=1)
        candidate.update(pharos_status=comp['pharos_status'], pharos_present=None,
                         resolved_endpoint_count=1, historical_pharos_comparator_eligible=False)
        data[1][0]['comparator_evaluable'] = False
        result = self.score(data)
        self.assertEqual(result['primary_population']['assay_eligible'], 2)
        self.assertEqual(result['historical_pharos_descriptive_anchor']['eligible_with_known_presence'], 1)

    def test_exact_population_missing_duplicates_source_rows_rejected(self):
        mutations = [lambda d: d[2].pop(), lambda d: d[2].append(deepcopy(d[2][0])),
                     lambda d: d[2][0].update(source_row=50),
                     lambda d: d[2][0].update(products=list(reversed(d[2][0]['products']))),
                     lambda d: d[3].pop()]
        for mutation in mutations:
            data = fixture(); mutation(data)
            with self.subTest(mutation=mutation), self.assertRaises(ValueError):
                self.score(data)

    def test_construct_label_exposure_and_reference_integrity_replayed(self):
        mutations = [lambda d: d[0][0]['constructs'].update(ad_orf_id='AD1'),
            lambda d: d[1][0]['assay'].update(db_orf_id='other'),
            lambda d: d[0][0].update(assay_eligible=False),
            lambda d: d[0][0].update(assay_exclusion_reason='test_failed'),
            lambda d: d[1][0]['assay'].update(detected=True),
            lambda d: d[0][0]['exposure'].update(huri_overlap=True),
            lambda d: d[0][0].update(lookup_record_sha256='changed'),
            lambda d: d[3][0].update(detected=False)]
        for mutation in mutations:
            data = fixture(); mutation(data)
            with self.subTest(mutation=mutation), self.assertRaises(ValueError):
                self.score(data)

    def test_new_predictions_cannot_bear_labels_or_legacy_overlay_states(self):
        data = fixture(); data[2][0]['detected'] = False
        with self.assertRaises(ValueError): self.score(data)
        for state in ('physical_not_returned_under_profile', 'no_returned_functional_row',
                      'retrieval_failed', 'truncated', 'schema_failed', 'unknown'):
            data = fixture()
            data[2][0]['views']['physical'].update(state=state, native_score=None, ranking_score=-1)
            with self.subTest(state=state), self.assertRaises(ValueError): self.score(data)

    def test_numeric_scores_finite_unchanged_and_boolean_not_numeric(self):
        for native, ranking in [(float('nan'), float('nan')), (float('inf'), float('inf')),
                                (-.1, -.1), (1.1, 1.1), (True, True), (.5, .6), (.5, True)]:
            data = fixture(); data[2][0]['views']['functional'].update(native_score=native, ranking_score=ranking)
            with self.subTest(native=native, ranking=ranking), self.assertRaises(ValueError): self.score(data)
        for native, ranking in [(0, -1), (None, 0), (None, True), (None, -2)]:
            data = fixture()
            data[2][0]['views']['functional'].update(state='no_returned_native_row',
                                                    native_score=native, ranking_score=ranking)
            with self.subTest(native=native, ranking=ranking), self.assertRaises(ValueError): self.score(data)

    def test_mapping_missingness_states_preserve_population(self):
        for state, projected in (('unmapped', 'unmapped'), ('ambiguous', 'ambiguous'),
                                 ('mapping_limit_reached', 'ambiguous')):
            data = fixture(); row = data[2][0]
            row['mapping_states'][0] = state
            row['mapping_proof'][0].update(status=state, string_id=None)
            row['query_batch'] = dict.fromkeys(scoring.ARMS)
            for view in row['views'].values():
                view.update(state=projected, native_score=None, ranking_score=-1)
            result = self.score(data)
            self.assertEqual(result['primary_population']['assay_eligible'], 4)
            self.assertEqual(result['coverage_eligible']['physical']['states'][projected], 1)

    def test_collapsed_representative_unqueried_and_unranked(self):
        data = fixture(); row = data[2][0]
        row['mapping_proof'][1]['string_id'] = row['mapping_proof'][0]['string_id']
        row['query_batch'] = dict.fromkeys(scoring.ARMS)
        for view in row['views'].values():
            view.update(state='collapsed_representative', native_score=None, ranking_score=-1)
        self.assertEqual(self.score(data)['coverage_eligible']['physical']['states']['collapsed_representative'], 1)
        row['query_batch']['physical'] = 'physical_network_1'
        with self.assertRaises(ValueError): self.score(data)

    def test_mapping_proofs_query_profiles_and_native_states_consistent(self):
        mutations = [lambda p: p['mapping_proof'][0].update(accession='OTHER'),
            lambda p: p['mapping_proof'][0].update(status='unmapped'),
            lambda p: p['mapping_proof'][0].update(string_id='10090.MOUSE'),
            lambda p: p.update(query_batch='legacy_overlay_batch'),
            lambda p: p['query_batch'].update(functional=None),
            lambda p: p['query_batch'].update(other='batch'),
            lambda p: p['views']['physical'].update(state='unmapped', native_score=None, ranking_score=-1)]
        for mutation in mutations:
            data = fixture(); mutation(data[2][0])
            with self.subTest(mutation=mutation), self.assertRaises(ValueError): self.score(data)

    def test_join_order_independent(self):
        candidates, labels, predictions, reference = fixture()
        first = self.score((candidates, labels, predictions, reference))
        second = self.score((candidates[::-1], labels[1:] + labels[:1], predictions[::-1], reference[::-1]))
        self.assertEqual(first, second)

    def test_result_verifies_capture_before_write_and_replays_without_changes(self):
        candidates, labels, predictions, reference = fixture()
        captured = {'protocol': {'content_sha256': 'protocol', 'rules': {'scoring_python': scoring.SCORING_PYTHON}},
                    'report': {'content_sha256': 'capture'}, 'candidates': candidates,
                    'label_rows': labels, 'predictions': predictions, 'reference_predictions': reference}
        calls = []
        fake = SimpleNamespace(verify_capture=lambda path: (calls.append(path), captured)[1])
        with tempfile.TemporaryDirectory() as temporary, patch.dict(sys.modules, {'run_string_temporal': fake}):
            capture = Path(temporary).resolve() / 'capture'; capture.mkdir()
            out = Path(temporary).resolve() / 'result'
            report = scoring.score_capture(capture, out)
            self.assertEqual(report['status'], 'completed')
            self.assertEqual(len(calls), 2)
            self.assertEqual(scoring.verify_result(capture, out), report)
            html = (out / 'report.html').read_text()
            self.assertIn('STRING 12.0 temporal development control', html)
            self.assertIn('Separate native functional and physical networks', html)
            self.assertNotIn('STRING functional scores and physical overlay', html)
            with self.assertRaises(ValueError): scoring.score_capture(capture, out)
            metric_path = out / 'metrics.json'; metric = json.loads(metric_path.read_text())
            metric['full_panel']['arms']['physical']['average_precision'] = .99
            metric_path.write_text(json.dumps(metric))
            with self.assertRaises(ValueError): scoring.verify_result(capture, out)

    def test_runtime_or_capture_failure_does_not_emit_scores(self):
        def fail(path):
            raise ValueError('Capture failed verification.')
        for fake in (SimpleNamespace(verify_capture=fail),
                     SimpleNamespace(verify_capture=lambda path: {'protocol': {'rules': {'scoring_python': '0.0.0'}}})):
            with tempfile.TemporaryDirectory() as temporary, patch.dict(sys.modules, {'run_string_temporal': fake}):
                out = Path(temporary) / 'results'
                with self.assertRaises(ValueError): scoring.score_capture(Path(temporary) / 'capture', out)
                self.assertFalse(out.exists())


if __name__ == '__main__':
    unittest.main()
