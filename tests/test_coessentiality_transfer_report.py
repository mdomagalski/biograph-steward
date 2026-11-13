"""Offline rendering controls with explicitly invented formatting fixtures."""
import json
from pathlib import Path
import tempfile
import unittest

from biograph_steward.client import digest, write_json
from tools.coessentiality_transfer import report as renderer
from tools.coessentiality_transfer.evaluate import FORMAT
from tools.coessentiality_transfer.prepare import inventory


class ProspectiveReportTests(unittest.TestCase):
    def source(self, path):
        path.mkdir()
        point = {'N': 1, 'status': 'scorable', 'enrichment': None,
                 'observed_weighted_sum': 0.0, 'expected_weighted_sum': 0.0,
                 'observed_mean_RA_per_slot': 0.0, 'expected_mean_RA_per_slot': 0.0,
                 'fixed_queries': 128, 'available_queries': 128, 'observed_hits': 0.0,
                 'expected_hits': 0.0, 'query_frame': 128, 'reference_available_queries': 128}
        points = [{**point, 'N': n} for n in range(1, 11)]
        names = ['normalized', 'historical'] + [f'historical_{kind}_{i:02}' for kind in ['count', 'degree'] for i in range(20)]
        write_json(path / 'curves.json', {a: {'RA': points, 'binary_diagnostic': points} for a in names})
        envelope = [{'minimum': None, 'median': None, 'maximum': None} for _ in range(10)]
        write_json(path / 'control_envelopes.json', {m: {k: envelope for k in ['count', 'degree']}
                    for m in ['RA', 'binary_diagnostic']})
        coverage = dict(membership_links=0, model_nodes=0, genes_with_memberships=0,
                        co_context_pairs_primary=0, queries_with_primary_co_context_partner=0,
                        zero_context_queries_retained=128)
        data = dict(format=FORMAT, fixed_queries=128, source_arms=42, N=list(range(1, 11)),
            full_curve_descriptive_assessment={'RA': {'project_descriptive_full_curve_rule_met': False,
                'points': [{'historical_exceeds_normalized_and_all_40_draws': False} for _ in range(10)]}},
            source_only_coverage={a: coverage for a in ['normalized', 'historical']}, limitations=['Formatting fixture only.'],
            native_P_status_counts={}, native_sign_status_counts={}, frozen_source_control_content_sha256='f' * 64,
            native_capture_content_sha256='c' * 64, files=inventory(path))
        data['content_sha256'] = digest(data); write_json(path / 'report.json', data)

    def test_preserves_complete_undefined_curve_and_all_arms(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp); self.source(root / 'source')
            receipt = renderer.render(root / 'source', root / 'readable')
            html = (root / 'readable/report.html').read_text()
            self.assertIn('UNKNOWN / undefined', html)
            self.assertIn('historical_count_19', html)
            self.assertIn('historical_degree_19', html)
            self.assertIn('within the fixed 128-gene sample', html)
            self.assertEqual(receipt['arm_count_rendered'], 42)
            self.assertFalse(receipt['new_statistical_estimator_or_outcome_selection'])

    def test_tampered_curve_is_rejected_before_output(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp); self.source(root / 'source')
            with (root / 'source/curves.json').open('a') as f:
                f.write(' ')
            with self.assertRaisesRegex(ValueError, 'inventory'):
                renderer.render(root / 'source', root / 'readable')
            self.assertFalse((root / 'readable').exists())

    def test_missing_arm_is_rejected_even_if_source_is_resealed(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp); self.source(root / 'source')
            path = root / 'source/curves.json'; curves = json.loads(path.read_text())
            curves.pop('historical_degree_19'); write_json(path, curves)
            path = root / 'source/report.json'; data = json.loads(path.read_text())
            data['files'] = inventory(root / 'source'); data.pop('content_sha256')
            data['content_sha256'] = digest(data); write_json(path, data)
            with self.assertRaisesRegex(ValueError, 'curve universe'):
                renderer.render(root / 'source', root / 'readable')


if __name__ == '__main__':
    unittest.main()
