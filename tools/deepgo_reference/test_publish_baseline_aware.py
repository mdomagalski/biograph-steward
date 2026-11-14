"""Invented aggregate fixtures; no scientific outcomes or reference readers."""
from copy import deepcopy
import json
from pathlib import Path
import tempfile
import unittest

from biograph_steward.client import digest, write_json
from biograph_steward.file_utils import sha
from .publish_baseline_aware import (ASPECTS, FORMAT, FRAMES, GUARDS, METHODS,
    RUNTIME, SETTINGS, UNCERTAINTY, prepare)


def write(path, value):
    value = {key: item for key, item in value.items() if key != 'content_sha256'}
    write_json(path, {**value, 'content_sha256': digest(value)})


class Publication(unittest.TestCase):
    def fixture(self, root):
        denominator = {'eligible_proteins': 3, 'IA_eligible_proteins': 3}
        freeze = {'format': FORMAT + '.freeze', 'k': 3, 'runtime': RUNTIME,
            'status': 'FROZEN_before_new_baseline_aware_endpoint_values',
            'no_new_baseline_aware_endpoint_values_seen': True,
            'invented_native_fixture': {'passed': True, 'file_sha256': 'a' * 64},
            'propagation': 'fill', 'methods': list(METHODS),
            'no_new_model_inference': True, 'no_new_reference_release': True,
            'automatic_adoption': False, 'app_default_or_graph_changes': False,
            'ranking': {'same_full_frozen_forecasts': True, 'positive_scores_only': True},
            'scoring': {key: True for key in
                ('original_native_PK_or_None_exclusion_retained', 'original_native_eligible_N_and_future_GT_retained',
                 'baseline_is_not_subtracted_from_scoring_ground_truth', 'zero_residual_reference_cases_retained',
                 'full_frame_and_per_case_native_count_agreement_required')},
            'own_variant_utility': {'paired_uncertainty_or_model_superiority_claimed': False},
            'development_only': True, 'previous_reference_and_metric_exposure': True,
            'focus_namespace': 'molecular_function',
            'parent_overlap_report': {'file': '/data/private/parent.json', 'sha256': 'e' * 64},
            'parent_overlap_freeze': {'file': '/data/private/parent_freeze.json', 'sha256': 'f' * 64},
            'input_files_sha256': {'/data/private/forecast.gz': 'b' * 64},
            'frames': {frame: {'setting': SETTINGS[frame],
                'known': '/data/private/known.tsv' if frame in ('primary', 'reserved') else None,
                'denominators': {aspect: deepcopy(denominator) for aspect in ASPECTS}} for frame in FRAMES},
            'limitations': ['INVENTED: not scientific results.', '<script>untrusted</script>']}
        write(root / 'freeze.json', freeze)

        def point(frame, returned, tp, related):
            def counts(weight):
                precision = tp / returned if returned else 0.
                recall = tp / 8
                return {'eligible_proteins': 3, 'TP': float(weight * tp),
                    'reference_unmatched_predictions': float(weight * (returned - tp)),
                    'unrecovered_reference_annotations': float(weight * (8 - tp)),
                    'PPV_among_returned': precision, 'micro_recall': recall,
                    'micro_F1': 2 * precision * recall / (precision + recall) if tp else 0.,
                    'macro_PPV_including_abstentions': precision,
                    'macro_recall_including_abstentions': recall,
                    'prediction_coverage': 1. if returned >= 3 else returned / 3}
            normal = {**counts(1), 'returned_candidates': returned, 'unused_budget_slots': 9 - returned,
                'curator_supported_slots_per_fixed3_budget': tp / 9, 'filled_slot_fraction': returned / 9,
                'shortlists_with_ancestor_related_pair': int(bool(related)), 'ancestor_related_pairs': related,
                'mean_IA_per_returned_term': 2. if returned else None,
                'curator_supported_IA_per_fixed3_budget': 2 * tp / 9,
                'shortlist_is_ancestor_closed': False}
            checks = {kind: {'passed': True, 'eligible_proteins': 3,
                'columns': ['n', 'tp', 'fp', 'fn', 'pr', 'rc'],
                'relative_tolerance': 1e-12, 'absolute_tolerance': 1e-12,
                'same_native_function_same_eligible_frame': True,
                'known_exclusion': 'native_known_t0_closure' if frame in ('primary', 'reserved') else None}
                for kind in ('ordinary', 'IA_weighted')}
            return {'ordinary': normal, 'IA_weighted': counts(2),
                'native_batch_point_agreement': checks, 'native_reference_protein_order_sha256': 'c' * 64}

        rows, opportunities, comparisons = [], [], []
        for frame in FRAMES:
            for aspect in ASPECTS:
                successes = (3, 2) if aspect == 'molecular_function' else (1, 2)
                for method, supported in zip(METHODS, successes):
                    old, new = point(frame, 2, 1, 0), point(frame, 6, supported, 2)
                    rows.append({'frame': frame, 'setting': SETTINGS[frame], 'namespace': aspect,
                        'method': method, 'k': 3, 'eligible_proteins': 3, 'IA_eligible_proteins': 3,
                        'native_reference_protein_order_sha256': 'c' * 64,
                        'original_top3': point(frame, 8, 4, 1), 'filtered_after_top3': old,
                        'aware_before_top3': new, 'construction_guards': deepcopy(GUARDS),
                        'scoring_future_reference_unchanged_sha256': 'd' * 64,
                        'utility': {'old_after_filter_returned_candidates': 2,
                            'new_before_filter_returned_candidates': 6,
                            'old_after_filter_unused_slots': 7, 'new_before_filter_unused_slots': 3,
                            'replenished_slots': 4, 'proteins_with_replenishment': 2,
                            'old_baseline_absent_supported_pairs': 1.,
                            'new_baseline_absent_supported_pairs': float(supported),
                            'old_baseline_absent_reference_unmatched_pairs': 1.,
                            'new_baseline_absent_reference_unmatched_pairs': float(6 - supported),
                            'added_curator_supported_pairs': float(supported - 1),
                            'added_reference_unmatched_pairs': float(5 - supported),
                            'old_baseline_absent_supported_IA': 2.,
                            'new_baseline_absent_supported_IA': 2. * supported,
                            'added_curator_supported_IA': 2. * (supported - 1),
                            'marginal_added_curator_support_fraction': (supported - 1) / 4,
                            'old_supported_slots_per_original_fixed3_budget': 1 / 9,
                            'new_supported_slots_per_original_fixed3_budget': supported / 9,
                            'ordinary_support_non_decrease_is_containment_property': True,
                            'own_variant_uncertainty_or_model_superiority_claimed': False}})
                opportunities.append({'frame': frame, 'setting': SETTINGS[frame], 'namespace': aspect,
                    'original_eligible_proteins': 3, 'future_reference_pairs_absent_from_baseline': 5,
                    'original_proteins_with_residual_reference_support': 2,
                    'zero_residual_reference_proteins_retained': 1, 'residual_reference_IA': 10.,
                    'oracle_supported_cap3': 5, 'oracle_supported_slots_per_original_fixed3_budget': 5 / 9,
                    'oracle_is_reference_aware_not_deployable': True,
                    'original_population_and_future_reference_unchanged': True})
                difference = (successes[0] - successes[1]) / 9
                comparisons.append({'frame': frame, 'setting': SETTINGS[frame], 'namespace': aspect,
                    'candidate': 'baseline_aware_deepgose', 'comparator': 'baseline_aware_strict_alias_localplus',
                    'metric': 'baseline_absent_curator_supported_slots_per_original_fixed3_budget',
                    'eligible_proteins': 3,
                    'role': 'designated_focus' if aspect == 'molecular_function' else 'secondary',
                    'not_a_guaranteed_own_variant_containment_comparison': True,
                    'point_difference': difference, 'paired_95_percentile_interval': [difference - .05, difference + .05],
                    'bootstrap_mean_difference': difference, 'fraction_draws_above_zero': float(difference > 0)})
        result = {'format': FORMAT + '.results', 'runtime': RUNTIME, 'k': 3,
            'source_freeze_file_sha256': sha(root / 'freeze.json'),
            'parent_overlap_report_file_sha256': 'e' * 64, 'parent_overlap_freeze_file_sha256': 'f' * 64,
            'source_files_sha256': freeze['input_files_sha256'],
            'numeric_artifact_files_sha256': {'/data/private/numeric.npz': 'a' * 64},
            'rows': rows, 'opportunity': opportunities, 'comparisons': comparisons,
            'original_selected_identities_exactly_reconstructed': True,
            'all_original_populations_and_future_groundtruth_retained': True,
            'all24_method_strata_preserved': True,
            'all12_opportunity_and_method_comparison_strata_preserved': True,
            'own_variant_utility_is_descriptive_containment_not_model_improvement': True,
            'development_only': True, 'new_model_inference': False, 'new_reference_release': False,
            'app_default_or_graph_changed': False, 'automatic_adoption': False,
            'uncertainty': UNCERTAINTY, 'limitations': freeze['limitations']}
        write(root / 'source.json', result)
        return result, freeze

    def publish(self, root):
        return prepare(root / 'source.json', sha(root / 'source.json'), root / 'freeze.json',
                       sha(root / 'freeze.json'), root / 'public')

    def test_all_outcomes_cost_specificity_negative_contrasts_and_privacy_preserved(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary); source, _ = self.fixture(root); report = self.publish(root)
            for key, expected in (('rows', 24), ('opportunity', 12), ('comparisons', 12)):
                self.assertEqual(len(report['results'][key]), expected)
                self.assertEqual(report['results'][key], source[key])
            self.assertTrue(any(row['point_difference'] < 0 for row in report['results']['comparisons']))
            self.assertTrue(any(row['aware_before_top3']['ordinary']['PPV_among_returned'] <
                row['filtered_after_top3']['ordinary']['PPV_among_returned'] for row in source['rows']))
            self.assertNotIn('/data/', (root / 'public/report.json').read_text())
            html = (root / 'public/report.html').read_text()
            for marker in ('DEVELOPMENT', 'benchmark terms of interest', 'PK/None', 'by construction',
                           'reference-unmatched', 'Mean IA', 'No per-target future labels', 'not a blind full-app'):
                self.assertIn(marker, html)
            self.assertNotIn('<script>', html); self.assertIn('&lt;script&gt;', html)
            manifest = json.loads((root / 'public/publication_manifest.json').read_text())
            self.assertEqual(manifest['own_variant_intervals'], 0)
            for name, expected in manifest['files'].items(): self.assertEqual(sha(root / 'public' / name), expected)
            self.assertFalse(report['automatic_adoption'])

    def test_dropped_strata_wrong_native_masks_original_population_or_order_fail_closed(self):
        for mutation in ('drop_row', 'drop_opportunity', 'drop_comparison', 'mask', 'population', 'native',
                         'order', 'paired_order', 'truth', 'GT_count', 'budget', 'reconstruction', 'source_pin'):
            with self.subTest(mutation=mutation), tempfile.TemporaryDirectory() as temporary:
                root = Path(temporary); source, _ = self.fixture(root); row = source['rows'][0]
                if mutation == 'drop_row': source['rows'].pop()
                elif mutation == 'drop_opportunity': source['opportunity'].pop()
                elif mutation == 'drop_comparison': source['comparisons'].pop()
                elif mutation == 'mask':
                    source['rows'][-1]['aware_before_top3']['native_batch_point_agreement']['ordinary']['known_exclusion'] = 'native_known_t0_closure'
                elif mutation == 'population': row['eligible_proteins'] = 2
                elif mutation == 'native': row['aware_before_top3']['native_batch_point_agreement']['ordinary']['passed'] = False
                elif mutation == 'order': row['filtered_after_top3']['native_reference_protein_order_sha256'] = 'a' * 64
                elif mutation == 'paired_order':
                    source['rows'][1]['native_reference_protein_order_sha256'] = 'a' * 64
                    for variant in ('original_top3', 'filtered_after_top3', 'aware_before_top3'):
                        source['rows'][1][variant]['native_reference_protein_order_sha256'] = 'a' * 64
                elif mutation == 'truth': source['rows'][1]['scoring_future_reference_unchanged_sha256'] = 'a' * 64
                elif mutation == 'GT_count': row['aware_before_top3']['ordinary']['unrecovered_reference_annotations'] += 1
                elif mutation == 'budget': row['aware_before_top3']['ordinary']['curator_supported_slots_per_fixed3_budget'] = .9
                elif mutation == 'reconstruction': source['original_selected_identities_exactly_reconstructed'] = False
                else: source['parent_overlap_report_file_sha256'] = 'a' * 64
                write(root / 'source.json', source)
                with self.assertRaises(ValueError): self.publish(root)
                self.assertFalse((root / 'public').exists())

    def test_containment_partitions_and_added_unmatched_cost_cannot_be_hidden(self):
        for mutation in ('added_TP', 'added_unmatched', 'added_slots', 'marginal', 'containment',
                         'original_post', 'unused', 'specificity', 'own_CI', 'old_IA', 'new_IA', 'added_IA'):
            with self.subTest(mutation=mutation), tempfile.TemporaryDirectory() as temporary:
                root = Path(temporary); source, _ = self.fixture(root); row = source['rows'][0]; u = row['utility']
                if mutation == 'added_TP': u['added_curator_supported_pairs'] += 1
                elif mutation == 'added_unmatched': u['added_reference_unmatched_pairs'] = 0
                elif mutation == 'added_slots': u['replenished_slots'] = 3
                elif mutation == 'marginal': u['marginal_added_curator_support_fraction'] = 1.
                elif mutation == 'containment': u['ordinary_support_non_decrease_is_containment_property'] = False
                elif mutation == 'original_post': u['old_baseline_absent_supported_pairs'] = 2
                elif mutation == 'unused': u['old_after_filter_unused_slots'] = 0
                elif mutation == 'specificity': row['aware_before_top3']['ordinary']['mean_IA_per_returned_term'] = None
                elif mutation == 'old_IA': u['old_baseline_absent_supported_IA'] = .1
                elif mutation == 'new_IA': u['new_baseline_absent_supported_IA'] = -1.
                elif mutation == 'added_IA': u['added_curator_supported_IA'] += 1.
                else: u['paired_95_percentile_interval'] = [0., .1]
                write(root / 'source.json', source)
                with self.assertRaises(ValueError): self.publish(root)
                self.assertFalse((root / 'public').exists())

    def test_zero_residual_population_reference_ceiling_and_method_intervals_stay_qualified(self):
        for mutation in ('drop_zero', 'opportunity_N', 'oracle', 'interval', 'own_variant', 'method_point',
                         'role', 'bootstrap_fraction', 'new_reference', 'truth_aware_guard',
                         'freeze_status', 'fixture_pending', 'scoring_truth'):
            with self.subTest(mutation=mutation), tempfile.TemporaryDirectory() as temporary:
                root = Path(temporary); source, freeze = self.fixture(root)
                if mutation == 'drop_zero': source['opportunity'][0]['zero_residual_reference_proteins_retained'] = 0
                elif mutation == 'opportunity_N': source['opportunity'][0]['original_eligible_proteins'] = 2
                elif mutation == 'oracle': source['opportunity'][0]['oracle_supported_cap3'] = 6
                elif mutation == 'interval': source['comparisons'][0]['paired_95_percentile_interval'] = [.2, -.2]
                elif mutation == 'own_variant': source['comparisons'][0]['comparator'] = 'original_deepgose'
                elif mutation == 'method_point': source['comparisons'][0]['point_difference'] = .5
                elif mutation == 'role': source['comparisons'][0]['role'] = 'designated_focus'
                elif mutation == 'bootstrap_fraction': source['comparisons'][0]['fraction_draws_above_zero'] = 1.1
                elif mutation == 'new_reference': source['new_reference_release'] = True
                elif mutation == 'truth_aware_guard': source['rows'][0]['construction_guards']['ranking_uses_future_reference_values'] = True
                else:
                    if mutation == 'freeze_status': freeze['status'] = 'DRAFT'
                    elif mutation == 'fixture_pending': freeze['invented_native_fixture']['passed'] = False
                    else: freeze['scoring']['baseline_is_not_subtracted_from_scoring_ground_truth'] = False
                    write(root / 'freeze.json', freeze)
                    source['source_freeze_file_sha256'] = sha(root / 'freeze.json')
                write(root / 'source.json', source)
                with self.assertRaises(ValueError): self.publish(root)
                self.assertFalse((root / 'public').exists())

    def test_raw_case_ids_numeric_indices_and_operator_paths_fail_closed(self):
        for key, value in (('selected_term_indices', [[1, 2, 3]]), ('protein_ids', ['P12345']),
                           ('GO:0001234', 2), ('case_id', 'private'), ('extra', '/data/private/selected.tsv')):
            with self.subTest(key=key), tempfile.TemporaryDirectory() as temporary:
                root = Path(temporary); source, _ = self.fixture(root)
                source['rows'][0]['utility'][key] = value
                write(root / 'source.json', source)
                with self.assertRaises(ValueError): self.publish(root)
                self.assertFalse((root / 'public').exists())


if __name__ == '__main__': unittest.main()
