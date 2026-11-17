"""Invented source/control fixtures for the isolated prospective wrapper."""
from pathlib import Path
import hashlib
import json
import random
import tempfile
import unittest
from unittest.mock import patch

from tools.coessentiality_transfer.prepare import build_arms, co_context_coverage, COUNT_SEEDS, DEGREE_SEEDS, packet_for
from tools.coessentiality_transfer.matrix import fixed_columns
from tools.coessentiality_transfer import matrix as transfer_matrix
from tools.coessentiality_transfer.evaluate import assessment, envelopes
from biograph_steward.client import digest, write_json
from biograph_steward.file_utils import sha


class TransferSourceControlTests(unittest.TestCase):
    def test42_arms_and_exact_fixed_native_control_seeds(self):
        ordinary = [('a', 'w'), ('a', 'x'), ('b', 'x'), ('b', 'y')]
        historical = [('a', 'w'), ('b', 'x')]; calls = []
        def native(edges, **kwargs):
            calls.append(kwargs); return [(0, 3), (1, 2)], {'swap_attempts': 20}
        arms = build_arms(ordinary, historical, native)
        self.assertEqual(len(arms), 42); self.assertNotIn('current', arms)
        for i, seed in enumerate(COUNT_SEEDS):
            self.assertEqual(arms[f'historical_count_{i:02}']['memberships'],
                             sorted(random.Random(seed).sample(ordinary, len(historical))))
        self.assertEqual([c['seed'] for c in calls], DEGREE_SEEDS)
        self.assertTrue(all(c['allow_self_loops'] is False and c['allow_antiparallel'] is True and c['multiplier'] == 10 for c in calls))
        self.assertTrue(all(arms[f'historical_degree_{i:02}']['both_full_frame_degree_vectors_verified'] for i in range(20)))

    def test_bad_or_noninformative_source_views_cannot_force_a_control_design(self):
        native = lambda *a, **k: self.fail('backend must not run on invalid feature scope')
        ordinary = [('a', 'w'), ('b', 'x')]
        for source, hist in [(ordinary, []), (ordinary, ordinary), (ordinary, [('a', 'outside')]),
                             (ordinary + ordinary[:1], [('a', 'w')])]:
            with self.subTest(source=source, hist=hist), self.assertRaises(ValueError):
                build_arms(source, hist, native)

    def test_source_only_coverage_keeps_zero_queries_and_does_not_weight(self):
        genes = ['a', 'b', 'c', 'isolated']; rows = [('a', 'w'), ('b', 'w'), ('a', 'x'), ('c', 'x')]
        r = co_context_coverage(genes, rows, [['a', 'c'], ['b', 'c']])
        self.assertEqual(r['co_context_pairs_all'], 2)
        self.assertEqual(r['co_context_pairs_primary'], 1)
        self.assertEqual(r['queries_with_primary_co_context_partner'], 2)
        self.assertEqual(r['zero_context_queries_retained'], 2)
        self.assertFalse(r['is_reference_outcome_or_power_estimate'])

    def test_capture_columns_cannot_overlap_old_exposure_or_change128_frame(self):
        report = {'source_paths': {'sample': 'invented'}, 'sample_content_sha256': 'invented'}
        rows = [{'native_matrix_index': i} for i in range(100, 228)]
        protocol = {'reference_exposure': {'old_raw_column_indices': list(range(92))}}
        with patch('tools.coessentiality_transfer.matrix.verify_sample', return_value=({}, protocol, [])):
            self.assertEqual(fixed_columns(report, {'genes': rows}), list(range(100, 228)))
            for bad in [rows[:-1], rows[:-1] + rows[:1], rows[:-1] + [{'native_matrix_index': 4}]]:
                with self.subTest(length=len(bad)), self.assertRaises(ValueError):
                    fixed_columns(report, {'genes': bad})

    def test_complete_curve_rule_never_substitutes_bestN_or_binary(self):
        arms = ['normalized', 'historical'] + [f'historical_{kind}_{i:02}' for kind in ['count', 'degree'] for i in range(20)]
        curves = {a: {metric: [{'enrichment': 2. if a == 'historical' else 1.} for n in range(10)]
                      for metric in ['RA', 'binary_diagnostic']} for a in arms}
        self.assertTrue(assessment(curves, 'RA')['project_descriptive_full_curve_rule_met'])
        curves['historical']['RA'][-1]['enrichment'] = None
        self.assertFalse(assessment(curves, 'RA')['project_descriptive_full_curve_rule_met'])
        self.assertFalse(assessment(curves, 'binary_diagnostic')['is_primary'])
        curves['historical']['RA'][-1]['enrichment'] = 2.
        curves['historical_degree_19']['RA'][0]['enrichment'] = 3.
        self.assertFalse(assessment(curves, 'RA')['project_descriptive_full_curve_rule_met'])
        env = envelopes(curves, 'RA')
        self.assertEqual(env['degree'][0]['maximum'], 3.)
        self.assertEqual(env['degree'][0]['draws'], 20)

    def test_resealed_capture_cannot_disagree_with_native_transport_sidecar(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory); frozen = root / 'frozen'; captured = root / 'captured'
            frozen.mkdir(); captured.mkdir(); (frozen / 'reference_headers').mkdir(); (captured / 'columns').mkdir()
            write_json(frozen / 'report.json', {'invented': 'fixture-only; workflow verifier is mocked'})
            (frozen / 'reference_headers/GLS_p.npy.header').write_bytes(b'invented native header fixture')
            base = {'shape': [1, 1], 'dtype': '<f8', 'fortran_order': True, 'header_bytes': 80, 'itemsize': 8, 'file_bytes': 88}
            meta = {**base, 'url': 'https://example.invalid/native.npy', 'etag': '"fixed"'}
            frozen_report = {'content_sha256': 'f' * 64, 'reference_metadata': {'GLS_p.npy': meta}}
            raw = b'\0' * 8; path = captured / 'columns/one.bin'; path.write_bytes(raw)
            receipt = {'url': meta['url'], 'status': 206, 'headers': {'Content-Range': 'bytes 80-87/88',
                'Content-Length': '8', 'ETag': meta['etag']}, 'request_range': [80, 87], 'payload_bytes': 8,
                'payload_sha256': hashlib.sha256(raw).hexdigest()}
            write_json(Path(str(path) + '.json'), receipt)
            row = {'matrix': 'GLS_p.npy', 'column': 0, 'file': 'columns/one.bin', **receipt}
            plan = {'frozen_source_control_content_sha256': frozen_report['content_sha256'], 'column_indices': [0],
                    'matrix_metadata': frozen_report['reference_metadata']}
            plan['content_sha256'] = digest(plan); write_json(captured / 'capture_plan.json', plan)
            report = {'format': transfer_matrix.FORMAT, 'frozen_source_control_content_sha256': frozen_report['content_sha256'],
                'frozen_report_file_sha256': sha(frozen / 'report.json'), 'column_indices': [0],
                'matrix_metadata': frozen_report['reference_metadata'], 'columns': [row],
                'capture_plan_content_sha256': plan['content_sha256'], 'all_required_ranges_complete': True,
                'missing_transport_imputed': False, 'independent_study_confirmation': False, 'range_payload_total_bytes': 8,
                'files': {p.relative_to(captured).as_posix(): sha(p) for p in captured.rglob('*') if p.is_file()}}
            report['content_sha256'] = digest(report); write_json(captured / 'report.json', report)
            with patch.object(transfer_matrix, 'verify', return_value=(frozen_report, {'invented': True})), \
                 patch.object(transfer_matrix, 'fixed_columns', return_value=[0]), \
                 patch.object(transfer_matrix, 'header_metadata', return_value=base), \
                 patch.object(transfer_matrix, 'decode_column', return_value=[0.]):
                transfer_matrix.load(frozen, captured)
                receipt['request_range'] = [80, 88]; write_json(Path(str(path) + '.json'), receipt)
                report['files']['columns/one.bin.json'] = sha(Path(str(path) + '.json'))
                report.pop('content_sha256'); report['content_sha256'] = digest(report); write_json(captured / 'report.json', report)
                with self.assertRaisesRegex(ValueError, 'raw transport receipt'):
                    transfer_matrix.load(frozen, captured)


if __name__ == '__main__':
    unittest.main()
