"""Invented saved-aggregate publication tests, without scientific inputs."""
from copy import deepcopy
import json
from pathlib import Path
import tempfile
import unittest

from biograph_steward.client import digest, write_json
from biograph_steward.file_utils import sha
from .publish_secondary import prepare, ASPECTS, FRAMES, METHODS, READOUTS


def write(path, value):
    write_json(path, {**value, 'content_sha256': digest(value)})


class SecondaryPublication(unittest.TestCase):
    def fixture(self, root):
        denoms = [{'frame': f, 'setting': 'partial', 'namespace': a,
            'author_recognized_target_IDs': 2, 'eligible_proteins': 2, 'IA_eligible_proteins': 2}
            for f in FRAMES for a in ASPECTS]
        points = [{'frame': f, 'setting': 'partial', 'namespace': a, 'method': m,
            'status': 'scored', 'eligible_proteins': 2, 'IA_eligible_proteins': 2,
            'micro_Fmax': .2, 'IA_micro_Fmax': .1, 'macro_Fmax': .3, 'IA_macro_Fmax': .2,
            'unweighted_Smin': 3., 'IA_weighted_Smin': 2.,
            'source': '/data/private/oldcurve.tsv',
            'fixed_0_5': {'status': 'no_native_coverage', 'PPV': None, 'recall': None, 'F1': None}}
            for f in FRAMES for a in ASPECTS for m in METHODS]
        gate = {'passed': False, 'automatic_product_or_graph_change': False,
                'independent_confirmatory_gain_claimed': False}
        primary = {'format': 'biograph-steward.deepgo-development.v1.results',
            'denominators': denoms, 'new_outcome_rows': [p for p in points if p['method'] == 'deepgose'],
            'earlier_240_outcome_rows': [p for p in points if p['method'] != 'deepgose'],
            'predeclared_development_retention_gate': gate}
        write(root/'primary.json', primary)
        pins = {'/data/private/native_evaluation_v2/aggregate/report.json': sha(root/'primary.json')}
        freeze = {'format': 'biograph-steward.deepgo-exploratory-secondary-uncertainty.v1.freeze',
            'posthoc_exploratory': True, 'point_values_already_seen': True,
            'namespaces': list(ASPECTS), 'methods': list(METHODS), 'draws': 2000,
            'seed': 20261113, 'propagation': 'fill', 'input_files_sha256': pins,
            'runtime': {'python': '3.10.12', 'numpy': '1.26.4', 'scipy': '1.13.1', 'pandas': '2.2.3'}}
        write(root/'freeze.json', freeze)
        agreements = {f+'/'+a+'/'+m: {'namespace': a, 'propagation': 'fill',
            'full_original_all_namespace_parser_pipeline': True, 'author_point_agreement_passed': True,
            'raw_reference_proteins': 2, 'ordinary_eligible': 2, 'IA_weighted_eligible': 2,
            'checks': {k: {'max_absolute_curve_difference': 0.} for k in READOUTS}}
            for f in FRAMES for a in ASPECTS for m in METHODS}
        reports = {}; pairs = []
        for f in FRAMES:
            for a in ASPECTS:
                comparisons = [{'candidate': 'deepgose', 'comparator': 'strict_alias_localplus',
                    'readout': k, 'paired_95_percentile_interval': [-.2, -.01] if a == 'cellular_component' else [.01, .2],
                    'difference_mean': -.1 if a == 'cellular_component' else .1} for k in READOUTS]
                b = {'draws': 2000, 'seed': 20261113, 'raw_proteins': 2,
                    'shared_protein_samples_across_all_arms': True, 'numpy': '1.26.4',
                    'scores': {m: {} for m in METHODS}, 'comparisons': comparisons}
                b['content_sha256'] = digest(b); reports[f+'/'+a] = b
                pairs.extend({'frame': f, 'namespace': a, **r} for r in comparisons)
        source = {'format': 'biograph-steward.deepgo-secondary-uncertainty.v1.results',
            'freeze_file_sha256': sha(root/'freeze.json'),
            'posthoc_exploratory_after_all_six_point_values_seen': True, 'multiplicity_adjusted': False,
            'all_eight_contrasts_retained_regardless_of_direction': True,
            'primary_adoption_rule_changed': False, 'product_consumer_added': False,
            'new_model_source_or_reference_release': False, 'raw_reference_or_forecast_rows_included': False,
            'point_count_agreements': agreements, 'paired_comparisons': pairs,
            'uncertainty_reports': reports, 'input_files_sha256': pins,
            'runtime': deepcopy(freeze['runtime'])}
        write(root/'source.json', source)
        return points, pairs

    def publish(self, root):
        return prepare(root/'source.json', sha(root/'source.json'), root/'freeze.json',
                       sha(root/'freeze.json'), root/'primary.json', sha(root/'primary.json'), root/'public')

    def test_all_eight_positive_and_negative_intervals_sanitized_without_adoption(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder); points, pairs = self.fixture(root); result = self.publish(root)
            self.assertEqual(result['results']['paired_comparisons'], pairs)
            self.assertEqual(len(result['already_reported_secondary_point_rows']), 8)
            self.assertEqual(result['intervals'], 8)
            self.assertFalse(result['unchanged_primary_BPO_retention_gate']['passed'])
            self.assertFalse(result['automatic_adoption']); self.assertFalse(result['multiplicity_adjusted'])
            self.assertNotIn('/data/', (root/'public/secondary_uncertainty.json').read_text())
            self.assertNotIn('/data/', (root/'public/secondary_uncertainty.html').read_text())
            html = (root/'public/secondary_uncertainty.html').read_text()
            for text in ('POST-HOC', 'NOT MULTIPLICITY ADJUSTED', 'Molecular function', 'Cellular component', '-0.2'):
                self.assertIn(text, html)
            self.assertEqual(len(list((root/'public').iterdir())), 4)
            self.assertIsNone(result['already_reported_secondary_point_rows'][0]['fixed_0_5']['PPV'])
            md = (root/'public/secondary_uncertainty.md').read_text()
            self.assertIn('Post-hoc and not multiplicity adjusted', md)
            self.assertIn('[-0.200000, -0.010000]', md)
            self.assertEqual(sum(line.startswith('| Original PK') or line.startswith('| Additional PK') for line in md.splitlines()), 8)

    def test_missing_contrast_wrong_point_denominator_or_raw_cases_fail_closed(self):
        for mutation in ('drop_negative', 'wrong_denominator', 'raw_case', 'hidden_path', 'promote'):
            with self.subTest(mutation=mutation), tempfile.TemporaryDirectory() as folder:
                root = Path(folder); self.fixture(root)
                d = json.loads((root/'source.json').read_text()); d.pop('content_sha256')
                if mutation == 'drop_negative': d['paired_comparisons'].pop()
                elif mutation == 'wrong_denominator': next(iter(d['point_count_agreements'].values()))['ordinary_eligible'] = 1
                elif mutation == 'raw_case': d['case_id'] = 'not-for-publication'
                elif mutation == 'hidden_path': d['unexpected'] = '/data/private/file.txt'
                elif mutation == 'promote': d['primary_adoption_rule_changed'] = True
                write(root/'source.json', d)
                with self.assertRaises(ValueError): self.publish(root)
                self.assertFalse((root/'public').exists())

    def test_exact_runtime_and_point_profile_inventory_are_required(self):
        for mutation in ('result_runtime', 'freeze_runtime', 'duplicate_profile'):
            with self.subTest(mutation=mutation), tempfile.TemporaryDirectory() as folder:
                root = Path(folder); self.fixture(root)
                source = json.loads((root/'source.json').read_text()); source.pop('content_sha256')
                freeze = json.loads((root/'freeze.json').read_text()); freeze.pop('content_sha256')
                if mutation == 'result_runtime':
                    source['runtime']['scipy'] = '1.11.3'
                elif mutation == 'freeze_runtime':
                    freeze['runtime']['python'] = '3.12.0'
                else:
                    parent = json.loads((root/'primary.json').read_text()); parent.pop('content_sha256')
                    parent['new_outcome_rows'][-1] = deepcopy(parent['new_outcome_rows'][0])
                    write(root/'primary.json', parent)
                    pins = {'/data/private/native_evaluation_v2/aggregate/report.json': sha(root/'primary.json')}
                    freeze['input_files_sha256'] = pins
                    source['input_files_sha256'] = pins
                write(root/'freeze.json', freeze)
                source['freeze_file_sha256'] = sha(root/'freeze.json');write(root/'source.json', source)
                expected = 'point profile inventory' if mutation == 'duplicate_profile' else 'runtime'
                with self.assertRaisesRegex(ValueError, expected): self.publish(root)
                self.assertFalse((root/'public').exists())

    def test_namespace_or_original_primary_binding_cannot_change(self):
        for mutation in ('aspect', 'primary_pin'):
            with self.subTest(mutation=mutation), tempfile.TemporaryDirectory() as folder:
                root = Path(folder); self.fixture(root)
                d = json.loads((root/'freeze.json').read_text()); d.pop('content_sha256')
                if mutation == 'aspect': d['namespaces'] = ['molecular_function']
                else: d['input_files_sha256'] = {'/data/private/native_evaluation_v2/aggregate/report.json': '0'*64}
                write(root/'freeze.json', d)
                s = json.loads((root/'source.json').read_text()); s.pop('content_sha256');s['freeze_file_sha256'] = sha(root/'freeze.json');write(root/'source.json', s)
                with self.assertRaises(ValueError): self.publish(root)
                self.assertFalse((root/'public').exists())


if __name__ == '__main__': unittest.main()
