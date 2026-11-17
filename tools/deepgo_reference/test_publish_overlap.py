"""Invented aggregate-only complementarity publication checks."""
from copy import deepcopy
import json
from pathlib import Path
import tempfile
import unittest

from biograph_steward.client import digest, write_json
from biograph_steward.file_utils import sha
from .publish_overlap import (ASPECTS, FORMAT, FRAMES, METHODS, RUNTIME, SETTINGS,
                              UNCERTAINTY, frame_descriptors, prepare)


def write(path, value):
    value = {key: item for key, item in value.items() if key != 'content_sha256'}
    write_json(path, {**value, 'content_sha256': digest(value)})


class Publication(unittest.TestCase):
    def fixture(self, root, *, gate=True):
        denominator = {'eligible_proteins': 2, 'IA_eligible_proteins': 2}
        freeze = {'format': FORMAT + '.freeze', 'k': 3, 'rrf_offset': 60,
            'focus_namespace': 'molecular_function', 'previous_reference_and_metric_exposure': True,
            'runtime': RUNTIME, 'input_files_sha256': {'/data/private/forecast.gz': 'b' * 64},
            'frames': {frame: {'setting': SETTINGS[frame],
                'denominators': {aspect: denominator for aspect in ASPECTS}} for frame in FRAMES}}
        write(root / 'freeze.json', freeze)
        rows, parents, fusion, comparisons = [], [], [], []

        def point(frame, aspect, method, tp):
            normal = {'eligible_proteins': 2, 'TP': tp, 'reference_unmatched_predictions': 4 - tp,
                'returned_candidates': 4, 'unused_budget_slots': 2,
                'curator_supported_slots_per_fixed3_budget': tp / 6, 'PPV_among_returned': tp / 4,
                'micro_recall': tp / 4, 'filled_slot_fraction': 2 / 3, 'prediction_coverage': 1.,
                'shortlist_is_ancestor_closed': False}
            checks = {kind: {'passed': True, 'eligible_proteins': 2,
                'columns': ['n', 'tp', 'fp', 'fn', 'pr', 'rc'],
                'relative_tolerance': 1e-12, 'absolute_tolerance': 1e-12,
                'known_exclusion': frame_descriptors()[frame]['known_exclusion'],
                'same_native_function_same_eligible_frame': True}
                for kind in ('ordinary', 'IA_weighted')}
            return {'frame': frame, 'setting': SETTINGS[frame], 'namespace': aspect,
                'method': method, 'k': 3, 'ordinary': normal,
                'IA_weighted': {'eligible_proteins': 2, 'TP': tp, 'PPV_among_returned': .5, 'micro_recall': .5},
                'native_batch_point_agreement': checks,
                'native_reference_protein_order_sha256': 'c' * 64}

        for frame in FRAMES:
            for aspect in ASPECTS:
                def bucket(selected, supported, literal=0, literal_supported=0,
                           closure=0, closure_supported=0):
                    return {'selected_pairs': selected, 'curator_supported_pairs': supported,
                        'reference_unmatched_pairs': selected - supported, 'curator_supported_IA': float(supported),
                        'literal_released_baseline': {'selected_pairs': literal, 'curator_supported_pairs': literal_supported},
                        'baseline_closure_only': {'selected_pairs': closure, 'curator_supported_pairs': closure_supported},
                        'baseline_absent': {'selected_pairs': selected - literal - closure,
                            'curator_supported_pairs': supported - literal_supported - closure_supported}}
                same = not gate and aspect == 'molecular_function'
                shared = bucket(4, 2, 2, 2, 2) if same else bucket(2, 1, 1, 1, 1)
                unique = bucket(0, 0) if same else bucket(2, 1)
                union = deepcopy(shared) if same else bucket(6, 3, 1, 1, 1)
                rows.append({'frame': frame, 'setting': SETTINGS[frame], 'namespace': aspect,
                    'eligible_proteins': 2, 'IA_eligible_proteins': 2,
                    'exact_overlap': {'proteins_with_identical_sets': 2 if same else 0,
                        'proteins_with_identical_order': 2 if same else 0,
                        'proteins_with_different_sets': 0 if same else 2, 'proteins_with_any_returned': 2,
                        'intersection_pairs': shared['selected_pairs'], 'union_pairs': union['selected_pairs'],
                        'pooled_Jaccard': shared['selected_pairs'] / union['selected_pairs'],
                        'buckets': {'both_methods': shared, 'deepgose_only': unique,
                            'strict_alias_localplus_only': deepcopy(unique), 'union': union}},
                    'ancestor_overlap': {'nonidentical_cross_method_related_pairs': 1,
                        'proteins_with_cross_method_related_pair': 1},
                    'oracle': {'union_supported_cap3': 2 if same else 3,
                        'best_parent_supported_per_protein': 2,
                        'union_baseline_absent_supported_cap3': 0 if same else 2,
                        'best_parent_baseline_absent_supported_per_protein': 0 if same else 1,
                        'extra_supported_slots_over_best_parent_per_protein': 0 if same else 1,
                        'extra_baseline_absent_supported_slots_over_best_parent_per_protein': 0 if same else 1,
                        'ground_truth_aware_ceiling_not_a_deployable_result': True,
                        'fixed3_budget_yield': (2 if same else 3) / 6}})
                parents.extend(point(frame, aspect, method, 2) for method in METHODS)
                if gate:
                    tp = 3 if aspect == 'molecular_function' else 1
                    fusion.append(point(frame, aspect, 'rrf3', tp))
                    for method in METHODS:
                        difference = (tp - 2) / 6
                        comparisons.append({'frame': frame, 'setting': SETTINGS[frame], 'namespace': aspect,
                            'candidate': 'rrf3', 'comparator': method,
                            'metric': 'curator_supported_slots_per_fixed3_budget',
                            'role': 'designated_focus' if aspect == 'molecular_function' else 'secondary',
                            'eligible_proteins': 2, 'point_difference': difference,
                            'paired_95_percentile_interval': [difference - .05, difference + .05],
                            'bootstrap_mean_difference': difference, 'fraction_draws_above_zero': float(tp > 2)})
        result = {'format': FORMAT + '.results', 'k': 3, 'rrf_offset': 60,
            'source_freeze_file_sha256': sha(root / 'freeze.json'), 'runtime': RUNTIME,
            'frames': frame_descriptors(), 'rows': rows, 'parent_points': parents,
            'fusion_points': fusion, 'comparisons': comparisons,
            'execution_gate': {'kind': 'any_MFO_qualified_top3_set_differs', 'passed': gate,
                'not_truth_aware': True}, 'uncertainty': UNCERTAINTY,
            'PK_parent_reproduction_gate_passed': True, 'all12_declared_strata_preserved': True,
            'development_only': True, 'app_default_or_consumer_changed': False,
            'source_files_sha256': freeze['input_files_sha256'],
            'numeric_artifact_files_sha256': {'/data/private/numeric.npz': 'd' * 64},
            'limitations': ['INVENTED, not scientific results.', '<script>untrusted</script>']}
        write(root / 'source.json', result)
        return result

    def publish(self, root):
        return prepare(root / 'source.json', sha(root / 'source.json'), root / 'freeze.json',
                       sha(root / 'freeze.json'), root / 'public')

    def test_complete_inventory_negative_results_budget_and_path_privacy(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            source = self.fixture(root)
            result = self.publish(root)
            for key in ('rows', 'parent_points', 'fusion_points', 'comparisons', 'execution_gate'):
                self.assertEqual(result['results'][key], source[key])
            self.assertEqual(len(result['results']['rows']), 12)
            self.assertEqual(len(result['results']['parent_points']), 24)
            self.assertEqual(len(result['results']['fusion_points']), 12)
            self.assertEqual(len(result['results']['comparisons']), 24)
            self.assertTrue(any(row['point_difference'] < 0 for row in result['results']['comparisons']))
            text = (root / 'public/report.json').read_text()
            self.assertNotIn('/data/', text)
            html = (root / 'public/report.html').read_text()
            for marker in ('DEVELOPMENT', 'PK', 'NK', 'LK', 'Oracle', 'PPV among returned', 'offset 60'):
                self.assertIn(marker, html)
            self.assertNotIn('<script>', html)
            self.assertIn('&lt;script&gt;', html)
            self.assertFalse(result['automatic_adoption'])
            manifest = json.loads((root / 'public/publication_manifest.json').read_text())
            for name, expected in manifest['files'].items():
                self.assertEqual(sha(root / 'public' / name), expected)

    def test_failed_label_free_gate_emits_no_invented_fusion_results(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            self.fixture(root, gate=False)
            result = self.publish(root)
            self.assertFalse(result['results']['execution_gate']['passed'])
            self.assertEqual(result['results']['fusion_points'], [])
            self.assertEqual(result['results']['comparisons'], [])
            self.assertIn('No fusion points or intervals were generated', (root / 'public/report.html').read_text())

    def test_missing_outcome_wrong_mask_population_gate_and_unfair_budget_fail_closed(self):
        for mutation in ('drop', 'mask', 'population', 'budget', 'point', 'gate', 'native', 'order', 'offset',
                         'partition', 'oracle', 'IA_support', 'native_branch', 'gate_count'):
            with self.subTest(mutation=mutation), tempfile.TemporaryDirectory() as temporary:
                root = Path(temporary)
                source = self.fixture(root)
                if mutation == 'drop':
                    source['comparisons'].pop()
                elif mutation == 'mask':
                    source['frames']['no_knowledge']['known_exclusion'] = 'native_known_t0_closure'
                elif mutation == 'population':
                    source['rows'][0]['eligible_proteins'] = 3
                elif mutation == 'budget':
                    source['parent_points'][0]['ordinary']['curator_supported_slots_per_fixed3_budget'] = .9
                elif mutation == 'point':
                    source['comparisons'][0]['point_difference'] = .9
                elif mutation == 'gate':
                    source['execution_gate']['not_truth_aware'] = False
                elif mutation == 'native':
                    source['fusion_points'][0]['native_batch_point_agreement']['ordinary']['passed'] = False
                elif mutation == 'order':
                    source['fusion_points'][0]['native_reference_protein_order_sha256'] = 'e' * 64
                elif mutation == 'partition':
                    source['rows'][0]['exact_overlap']['buckets']['deepgose_only']['baseline_absent']['curator_supported_pairs'] = 0
                elif mutation == 'oracle':
                    source['rows'][0]['oracle']['extra_supported_slots_over_best_parent_per_protein'] = 2
                elif mutation == 'IA_support':
                    source['parent_points'][0]['IA_weighted']['TP'] = 3
                elif mutation == 'native_branch':
                    source['parent_points'][-1]['native_batch_point_agreement']['ordinary']['known_exclusion'] = 'native_known_t0_closure'
                elif mutation == 'gate_count':
                    source['execution_gate']['passed'] = False
                else:
                    source['rrf_offset'] = 10
                write(root / 'source.json', source)
                with self.assertRaises(ValueError):
                    self.publish(root)
                self.assertFalse((root / 'public').exists())

    def test_raw_selected_ids_numeric_case_indices_and_operator_outcome_paths_fail_closed(self):
        for key, value in (('selected_term_indices', [[1, 2, 3]]), ('protein_ids', ['P12345']),
                           ('GO:0001234', 2), ('comment', '/data/private/selected.tsv')):
            with self.subTest(key=key), tempfile.TemporaryDirectory() as temporary:
                root = Path(temporary)
                source = self.fixture(root)
                source['rows'][0]['exact_overlap'][key] = deepcopy(value)
                write(root / 'source.json', source)
                with self.assertRaises(ValueError):
                    self.publish(root)
                self.assertFalse((root / 'public').exists())


if __name__ == '__main__':
    unittest.main()
