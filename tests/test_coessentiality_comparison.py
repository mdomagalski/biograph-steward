"""Invented numerical fixtures test mechanics; no real outcomes are labels."""
import importlib.util
import io
import json
import math
from pathlib import Path
import tempfile
import types
import unittest
from unittest.mock import patch

from tools.coessentiality_feasibility.compare import fractional_top, curve_point, reference_partners, shared_partners
from tools.coessentiality_feasibility.matrix import header_metadata, column_range, decode_column, validate_response, _fetch
from tools.coessentiality_feasibility.prepare import degree_control, degrees
from tools.coessentiality_feasibility import prepare as preparation
from biograph_steward.client import digest, write_json
from biograph_steward.file_utils import sha


class CoessentialityCurveTests(unittest.TestCase):
    def test_fractional_boundary_ties_are_exact_and_order_invariant(self):
        rows = [('a', 0.0), ('b', 0.1), ('c', 0.1), ('d', 0.1), ('e', 1.0)]
        expected = [('a', 1.0), ('b', 1 / 3), ('c', 1 / 3), ('d', 1 / 3)]
        self.assertEqual(fractional_top(rows, 2)['selected'], expected)
        self.assertEqual(fractional_top(rows[::-1], 2)['selected'], expected)
        self.assertEqual(fractional_top(rows, 5)['selected'], [(x, 1.0) for x in 'abcde'])
        self.assertIsNone(fractional_top(rows, 6))

    def test_query_matched_background_retains_zero_context_queries(self):
        genes = ['a', 'b', 'c']; partners = {'a': [('b', .01), ('c', .2)], 'b': [('a', .01)], 'c': [('a', .2)]}
        selection = {g: fractional_top(rows, 1) for g, rows in partners.items()}
        adjacent = {'a': {'b'}, 'b': {'a'}, 'c': set()}
        point = curve_point(genes, partners, selection, adjacent, 1, True)
        self.assertEqual(point['observed_hits'], 2)
        self.assertEqual(point['expected_hits'], 1.5)  # .5 + 1 + 0, not global-pair density.
        self.assertAlmostEqual(point['enrichment'], 4 / 3)
        self.assertEqual(point['reference_available_queries'], 3)
        self.assertEqual(point['queries'][-1]['expected_hits'], 0)

    def test_incomplete_primary_frame_not_silently_shrunk(self):
        partners = {'a': [('b', .2)], 'b': []}; selected = {g: fractional_top(r, 1) for g, r in partners.items()}
        adj = {'a': set(), 'b': set()}
        primary = curve_point(['a', 'b'], partners, selected, adj, 1, True)
        self.assertIsNone(primary['observed_hits']); self.assertEqual(primary['reference_available_queries'], 1)
        sensitivity = curve_point(['a', 'b'], partners, selected, adj, 1, False)
        self.assertEqual(sensitivity['observed_hits'], 0)
        self.assertIsNone(sensitivity['enrichment'])
        self.assertEqual(sensitivity['aggregation'], 'conditional_reference_available_queries')

    def test_exact_version_and_no_duplicate_pathway_votes(self):
        adj = shared_partners(['a', 'b', 'c'], [('a', 'WP1_r1'), ('b', 'WP1_r1'),
            ('a', 'WP2_r1'), ('b', 'WP2_r1'), ('c', 'WP1_r2')])
        self.assertEqual(adj, {'a': {'b'}, 'b': {'a'}, 'c': set()})
        with self.assertRaises(ValueError):
            shared_partners(['a'], [('a', 'WP1'), ('a', 'WP1')])

    def test_unsigned_zero_one_and_negative_sign_are_not_false_or_missing(self):
        rows = [dict(gene_pair=['a', 'b'], scope='nonsyntenic', p_status='usable_native_two_sided_p',
                     p={'value': 0.0}, sign={'value': -1.0}),
                dict(gene_pair=['a', 'c'], scope='syntenic', p_status='usable_native_two_sided_p',
                     p={'value': 1.0}, sign={'value': None}),
                dict(gene_pair=['b', 'c'], scope='nonsyntenic', p_status='UNKNOWN_nonfinite_or_out_of_range_native_p',
                     p={'value': None}, sign={'value': 1.0})]
        self.assertEqual(reference_partners(['a', 'b', 'c'], rows, 'all')['a'], [('b', 0.0), ('c', 1.0)])
        self.assertEqual(reference_partners(['a', 'b', 'c'], rows, 'nonsyntenic_negative')['a'], [('b', 0.0)])
        self.assertEqual(reference_partners(['a', 'b', 'c'], rows, 'nonsyntenic_positive')['a'], [])
        self.assertEqual(reference_partners(['a', 'b', 'c'], rows, 'syntenic')['a'], [('c', 1.0)])

    def test_degree_null_checks_both_endpoint_vectors_and_types(self):
        rows = [('a', 'x'), ('b', 'y')]
        calls = []
        def valid(edges, **kwargs):
            calls.append(kwargs); return [(0, 3), (1, 2)], {'swap_attempts': 20}
        result, stats = degree_control(rows, valid, 123)
        self.assertEqual(degrees(result), degrees(rows)); self.assertNotEqual(result, rows)
        self.assertEqual(calls[0]['seed'], 123)
        for output in [[(0, 2), (0, 3)], [(0, 1), (1, 2)], [(0, 2), (1, 3)], [(0, 2), (0, 2)]]:
            with self.subTest(output=output), self.assertRaises(ValueError):
                degree_control(rows, lambda edges, **kwargs: (output, {}), 123)

    def test_transport_failure_is_not_biological_unknown(self):
        headers = {'Content-Range': 'bytes 80-95/200', 'Content-Length': '16', 'ETag': '"native"'}
        validate_response(206, headers, 80, 95, 200, '"native"', b'0' * 16)
        for status, change, body in [(200, {}, b'0' * 16), (206, {'ETag': '"changed"'}, b'0' * 16),
            (206, {'Content-Range': 'bytes 81-96/200'}, b'0' * 16), (206, {}, b'0' * 15)]:
            with self.subTest(change=change, status=status), self.assertRaises(ValueError):
                validate_response(status, {**headers, **change}, 80, 95, 200, '"native"', body)

    def test_verified_raw_range_and_Path_receipt_are_both_persisted(self):
        headers = {'Content-Range': 'bytes 80-95/200', 'Content-Length': '16', 'ETag': '"native"'}
        response = types.SimpleNamespace(status=206, headers=headers, url='https://example.invalid/native.npy',
                                         read=lambda length: b'x' * 16)
        from unittest.mock import MagicMock
        context = MagicMock(); context.__enter__.return_value = response
        with tempfile.TemporaryDirectory() as directory, patch('urllib.request.urlopen', return_value=context) as call:
            target = Path(directory) / 'column.bin'
            receipt = _fetch(response.url, '"native"', 80, 95, 200, target)
            self.assertEqual(target.read_bytes(), b'x' * 16)
            self.assertEqual(json.loads(Path(str(target) + '.json').read_text()), receipt)
            self.assertEqual(call.call_count, 1)
            self.assertEqual(receipt['attempt'], 1)


@unittest.skipUnless(importlib.util.find_spec('numpy'), 'optional native NumPy runtime not installed')
class NativeFortranReaderTests(unittest.TestCase):
    def test_rectangular_nonsymmetric_native_np_save_load_offsets(self):
        import numpy as np
        original = np.asfortranarray(np.array([[11., 12., 13., 14.], [21., 22., 23., 24.], [31., 32., 33., 34.]]))
        f = io.BytesIO(); np.save(f, original, allow_pickle=False); raw = f.getvalue()
        f.seek(0); version = np.lib.format.read_magic(f); np.lib.format.read_array_header_1_0(f)
        header = raw[:f.tell()]; meta = header_metadata(header)
        loaded = np.load(io.BytesIO(raw), allow_pickle=False)
        self.assertEqual(meta['shape'], [3, 4]); self.assertEqual(meta['file_bytes'], len(raw))
        for column in range(4):
            start, end = column_range(meta, column)
            np.testing.assert_array_equal(decode_column(raw[start:end + 1], meta), loaded[:, column])
        with self.assertRaises(ValueError):
            decode_column(b'short', meta)
        with self.assertRaises(ValueError):
            column_range(meta, 4)

    def test_c_order_does_not_silently_use_fortran_offsets(self):
        import numpy as np
        f = io.BytesIO(); np.save(f, np.arange(12.).reshape(3, 4), allow_pickle=False)
        raw = f.getvalue(); f.seek(0); np.lib.format.read_magic(f); np.lib.format.read_array_header_1_0(f)
        with self.assertRaisesRegex(ValueError, 'Fortran'):
            header_metadata(raw[:f.tell()])


class FrozenReplayControls(unittest.TestCase):
    def fixture(self, root):
        frozen = root / 'frozen'; frozen.mkdir(); (frozen / 'proof').mkdir()
        locations = {k: root / k for k in ['current', 'historical', 'registry', 'xswap']}
        source_seals = {}
        for key in ['current', 'historical']:
            p = locations[key]; p.mkdir(); write_json(p / 'packet.json', {'arms': {}})
            source = {'files': {'packet.json': sha(p / 'packet.json')}}
            source['content_sha256'] = digest(source); write_json(p / 'report.json', source)
            source_seals[key] = source['content_sha256']
        scope = {'genes': [{'ncbi_gene_id': '1'}], 'pairs': []}
        scope['content_sha256'] = digest(scope); write_json(frozen / 'proof/chromosome_scope_v2.json', scope)
        for name in ['primary_target_mapping.jsonl', 'genes.txt', 'gene_effect_header.csv']:
            (frozen / 'proof' / name).write_text('')
        arms = {'normalized': {'memberships': []}}
        write_json(frozen / 'packet.json', preparation.make_packet(scope, arms))
        (root / 'pinned_source').write_text('original')
        report = {'format': preparation.FORMAT, 'registry_sha256': 'registry',
            'source_files_sha256': {str(root / 'pinned_source'): sha(root / 'pinned_source')},
            'source_locations': {k: str(v) for k, v in locations.items()},
            **{'source_' + k + '_content_sha256': v for k, v in source_seals.items()},
            'files': {p.relative_to(frozen).as_posix(): sha(p) for p in frozen.rglob('*') if p.is_file()}}
        report['content_sha256'] = digest(report); write_json(frozen / 'report.json', report)
        return frozen, report, arms

    def test_recorded_source_pin_drift_fails_not_only_local_inventory(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory); frozen, report, arms = self.fixture(root)
            (root / 'pinned_source').write_text('changed')
            with self.assertRaisesRegex(ValueError, 'source input pins differ'):
                preparation.verify(frozen, code=False)

    def test_resealed_arm_mutation_fails_deterministic_source_replay(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory); frozen, report, arms = self.fixture(root)
            fake = types.ModuleType('xswap.permute'); fake.permute_edge_list = object()
            mocks = {'xswap': types.ModuleType('xswap'), 'xswap.permute': fake}
            with patch.dict('sys.modules', mocks), patch.object(preparation, 'load_registry',
                return_value=({'registry_sha256': 'registry'}, object())), \
                patch.object(preparation, 'replay_scope', return_value={'1'}), \
                patch.object(preparation, 'make_arms', return_value=arms):
                preparation.verify(frozen, code=False)
                packet = json.loads((frozen / 'packet.json').read_text()); packet['arms']['normalized']['memberships'] = [['1', 'fabricated']]
                write_json(frozen / 'packet.json', packet)
                report['files']['packet.json'] = sha(frozen / 'packet.json'); report.pop('content_sha256')
                report['content_sha256'] = digest(report); write_json(frozen / 'report.json', report)
                with self.assertRaisesRegex(ValueError, 'contract replay differs'):
                    preparation.verify(frozen, code=False)


if __name__ == '__main__':
    unittest.main()
