"""Invented ProtNote aggregate delivery fixtures; no model or case readers."""
from copy import deepcopy
from pathlib import Path
import json
import tempfile
import unittest

from biograph_steward.client import digest, write_json
from biograph_steward.file_utils import sha
from . import test_nonpk_publish as prior_fixture
from .publish_protnote import (ASPECTS, COMPARATORS, FORMAT, METHOD, METRICS,
                               READOUTS, SETTINGS, prepare)


def write(path, value):
    value = {k: v for k, v in value.items() if k != 'content_sha256'}
    write_json(path, {**value, 'content_sha256': digest(value)})


class Publication(unittest.TestCase):
    def fixture(self, root):
        old = prior_fixture.NativePublication().fixture(root)
        for row in old['denominators'] + old['earlier_36_outcome_rows'] + old['new_outcome_rows']:
            row['TOI_reference_pairs'] = 5
            row['author_recognized_target_IDs'] = 2
        write(root / 'previous.json', old)
        plan = {'format': 'biograph-steward.protnote-development.v1.protocol',
            'status': 'FROZEN_before_any_target_forecast', 'development_only': True,
            'previous_reference_and_metric_exposure': True,
            'model': {'seed': 42, 'trained_or_fit_here': False, 'ensembles_or_seed_selection': False},
            'target_scope': {'target_count': 547, 'population_counts': {'no_knowledge': 133, 'limited': 414}},
            'prediction_axis': {'headers_or_future_labels_or_TOI_used': False},
            'inference': {'sequence_batch': 1, 'text_batch': 8, 'label_pair_chunk': 1024},
            'evaluation': {'settings': list(SETTINGS), 'all_aspects': list(ASPECTS),
                'focus_namespace': 'molecular_function', 'paired_comparisons': [[METHOD, m] for m in COMPARATORS],
                'paired_contrasts': 12, 'original_ground_truth_masks_and_denominators_retained': True,
                'eligible_N': {s: {a: 2 for a in ASPECTS} for s in SETTINGS}},
            'adoption': {'new_accepted_graph_facts': False, 'automatic_adoption': False, 'AWS_or_app_default_changes': False},
            'producer_input_qualification': {'file': '/data/private/qualified.json', 'sha256': 'a' * 64},
            'producer_label_cache': {'file': '/data/private/cache.json', 'sha256': 'b' * 64},
            'limitations': ['INVENTED, not scientific results.', '<script>untrusted</script>']}
        write(root / 'protocol.json', plan)
        policy = {'format': FORMAT + '.freeze',
            'protocol': {'file': str(root / 'protocol.json'), 'sha256': sha(root / 'protocol.json')},
            'previous_report': {'file': str(root / 'previous.json'), 'sha256': sha(root / 'previous.json')},
            'predictions': {'file': '/data/private/predictions.json', 'sha256': 'c' * 64},
            'producer_config': {'file': '/data/private/config.json', 'sha256': 'd' * 64},
            'producer_done': {'file': '/data/private/DONE.json', 'sha256': 'e' * 64},
            'input_files_sha256': {'/data/private/helper.py': 'f' * 64}}
        write(root / 'freeze.json', policy)
        rows = deepcopy(old['new_outcome_rows'])
        for row in rows:
            row['method'] = METHOD
            for key in METRICS: row[key + '_tau'] = .25
            for key in ('unweighted_Smin', 'IA_weighted_Smin'): row[key + '_tau'] = .25
        pairs, reports = [], {}
        for setting in SETTINGS:
            means = {METHOD: .5, 'deepgose': .4, 'strict_alias_localplus': .6, 'official_nonexperimental': .7}
            comparisons = [{'candidate': METHOD, 'comparator': method, 'readout': readout,
                'difference_mean': means[METHOD] - means[method],
                'paired_95_percentile_interval': [means[METHOD] - means[method] - .05,
                                                   means[METHOD] - means[method] + .05],
                'fraction_draws_above_zero': float(means[METHOD] > means[method])}
                for method in COMPARATORS for readout in READOUTS]
            value = {'draws': 2000, 'seed': 20261113, 'numpy': '1.26.4',
                'shared_protein_samples_across_all_arms': True, 'raw_proteins': 2,
                'scores': {method: {readout: {'bootstrap_mean': mean,
                    'bootstrap_95_percentile_interval': [mean - .05, mean + .05]} for readout in READOUTS}
                    for method, mean in means.items()}, 'comparisons': comparisons}
            value['content_sha256'] = digest(value); reports[setting] = value
            pairs.extend({'setting': setting, 'namespace': 'molecular_function', **row} for row in comparisons)
        agreements = {s + '/' + METHOD: deepcopy(old['native_MFO_point_count_agreements'][s + '/deepgose'])
                      for s in SETTINGS}
        result = {'format': FORMAT + '.results', 'evaluation_freeze_sha256': sha(root / 'freeze.json'),
            'protocol_sha256': sha(root / 'protocol.json'), 'prediction_manifest_sha256': 'c' * 64,
            'previous_report_sha256': sha(root / 'previous.json'), 'runtime': old['runtime'],
            'raw_forecast_admission': {'all547_original_identities_accounted_for': True,
                'scorable_targets': 546, 'explicit_unscorable_targets': 1, 'fixed_ontology_classes': 10,
                'finite_unit_interval_cartesian_rows': 5460,
                'pre_forward_input_qualification_sha256': 'a' * 64, 'pre_target_label_cache_manifest_sha256': 'b' * 64,
                'private_inventory_sha256': 'c' * 64, 'producer_config_file_sha256': 'd' * 64,
                'producer_complete_DONE_file_sha256': 'e' * 64, 'all_raw_scores_finite_in_unit_interval': True,
                'exact_full_cartesian_forecast_verified': True, 'no_reference_or_TOI_values_used_for_admission': True},
            'actual_imported_helper_sources': policy['input_files_sha256'],
            'source_files_sha256': policy['input_files_sha256'], 'new_outcome_rows': rows,
            'earlier42_outcome_rows': old['earlier_36_outcome_rows'] + old['new_outcome_rows'],
            'paired_comparisons': pairs, 'uncertainty_reports': reports,
            'native_MFO_point_count_agreements': agreements,
            'all_original_populations_and_reference_masks_retained': True, 'development_only': True,
            'new_reference_release': False, 'app_default_or_graph_changed': False, 'automatic_adoption': False,
            'limitations': plan['limitations']}
        write(root / 'source.json', result)
        return result

    def publish(self, root):
        return prepare(root / 'source.json', sha(root / 'source.json'), root / 'freeze.json', sha(root / 'freeze.json'),
            root / 'previous.json', sha(root / 'previous.json'), root / 'protocol.json', sha(root / 'protocol.json'), root / 'public')

    def test_all48_points12_mixed_intervals_abstention_and_privacy_preserved(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary); source = self.fixture(root); report = self.publish(root)
            self.assertEqual(report['outcome_slots'], 48); self.assertEqual(report['MFO_paired_intervals'], 12)
            for key in ('new_outcome_rows', 'earlier42_outcome_rows', 'paired_comparisons', 'raw_forecast_admission'):
                self.assertEqual(report['results'][key], source[key])
            self.assertTrue(any(r['paired_95_percentile_interval'][1] < 0 for r in source['paired_comparisons']))
            self.assertIsNone(report['results']['new_outcome_rows'][0]['fixed_0_5']['PPV'])
            self.assertNotIn('/data/', (root / 'public/report.json').read_text())
            html = (root / 'public/report.html').read_text()
            for text in ('DEVELOPMENT', 'all42 earlier', 'all twelve', 'All547 original', 'training-unseen', 'not biological negatives'):
                self.assertIn(text, html)
            self.assertNotIn('<script>', html); self.assertIn('&lt;script&gt;', html)
            manifest = json.loads((root / 'public/publication_manifest.json').read_text())
            for name, expected in manifest['files'].items(): self.assertEqual(sha(root / 'public' / name), expected)

    def test_missing_outcomes_native_denominators_masks_admission_and_source_gates_fail_closed(self):
        for mutation in ('old', 'new', 'contrast', 'mask', 'N', 'GT', 'native', 'population', 'Cartesian',
                         'finite', 'DONE', 'source', 'runtime', 'scored_range'):
            with self.subTest(mutation=mutation), tempfile.TemporaryDirectory() as temporary:
                root = Path(temporary); source = self.fixture(root)
                if mutation == 'old': source['earlier42_outcome_rows'].pop()
                elif mutation == 'new': source['new_outcome_rows'].pop()
                elif mutation == 'contrast': source['paired_comparisons'].pop()
                elif mutation == 'mask': source['new_outcome_rows'][0]['known_exclusion'] = 'PK'
                elif mutation == 'N': source['new_outcome_rows'][0]['eligible_proteins'] = 1
                elif mutation == 'GT': source['new_outcome_rows'][0]['TOI_reference_pairs'] = 4
                elif mutation == 'native': source['native_MFO_point_count_agreements']['limited/' + METHOD]['author_point_agreement_passed'] = False
                elif mutation == 'population': source['raw_forecast_admission']['explicit_unscorable_targets'] = 0
                elif mutation == 'Cartesian': source['raw_forecast_admission']['finite_unit_interval_cartesian_rows'] = 5459
                elif mutation == 'finite': source['raw_forecast_admission']['all_raw_scores_finite_in_unit_interval'] = False
                elif mutation == 'DONE': source['raw_forecast_admission']['producer_complete_DONE_file_sha256'] = 'a' * 64
                elif mutation == 'source': source['actual_imported_helper_sources'] = {'/data/private/other.py': 'a' * 64}
                elif mutation == 'runtime': source['runtime']['numpy'] = '2.0.0'
                else: source['new_outcome_rows'][0]['micro_Fmax'] = 1.5
                write(root / 'source.json', source)
                with self.assertRaises(ValueError): self.publish(root)
                self.assertFalse((root / 'public').exists())

    def test_raw_ids_operator_paths_and_unpaired_or_unbound_uncertainty_fail_closed(self):
        for mutation in ('case', 'GOaxis', 'indices', 'operator', 'nested', 'mean', 'interval', 'shared'):
            with self.subTest(mutation=mutation), tempfile.TemporaryDirectory() as temporary:
                root = Path(temporary); source = self.fixture(root)
                if mutation == 'case': source['new_outcome_rows'][0]['case_id'] = 'secret'
                elif mutation == 'GOaxis': source['axis_go_ids'] = ['GO:0008150']
                elif mutation == 'indices': source['selected_term_indices'] = [[1, 2, 3]]
                elif mutation == 'operator': source['new_outcome_rows'][0]['extra'] = '/data/private/cases.jsonl'
                elif mutation == 'nested': source['paired_comparisons'][0]['difference_mean'] = .9
                elif mutation == 'mean':
                    source['uncertainty_reports']['limited']['scores'][METHOD]['ordinary']['bootstrap_mean'] = .9
                    value = source['uncertainty_reports']['limited']; value.pop('content_sha256'); value['content_sha256'] = digest(value)
                elif mutation == 'interval': source['paired_comparisons'][0]['paired_95_percentile_interval'] = [.2, -.2]
                else:
                    value = source['uncertainty_reports']['limited']; value['shared_protein_samples_across_all_arms'] = False
                    value.pop('content_sha256'); value['content_sha256'] = digest(value)
                write(root / 'source.json', source)
                with self.assertRaises(ValueError): self.publish(root)
                self.assertFalse((root / 'public').exists())


if __name__ == '__main__': unittest.main()
