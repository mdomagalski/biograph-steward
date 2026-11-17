"""Capture guards use invented IDs and mocked transports; no public queries."""
from copy import deepcopy
import hashlib
import io
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
from urllib.error import HTTPError
from urllib.parse import urlencode
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))
import run_string_component as runner


def mapping(value, status='resolved'):
    return {'status': status, 'string_id': value if status == 'resolved' else None}


class FakeResponse:
    def __init__(self, body, url, *, headers=None, status=200):
        self._stream = io.BytesIO(body)
        self.status, self.url = status, url
        self.headers = {'Content-Type': 'text/tab-separated-values; charset=utf-8',
                        'string-api-version': '2'}
        self.headers.update(headers or {})
    def read(self, n=-1):
        return self._stream.read(n)
    def __enter__(self):
        return self
    def __exit__(self, *args):
        return False


def receipt(folder, raw=b'invented\trow\n', *, kind='mapping', batch='mapping_0001', ids=None):
    ids = ids or ['P00001', 'P00002-2']
    directory = folder / 'responses'; directory.mkdir(exist_ok=True)
    params = runner.parameters(kind, ids)
    url = runner.BASE + runner.RULES[kind + '_api'] + '?' + urlencode(params)
    name = batch + '_attempt_01.json'
    body_name = batch + '_attempt_01.tsv'
    record = {'status': 200, 'error': None, 'kind': kind, 'batch_id': batch,
              'parameters': params, 'url': url, 'final_url': url,
              'body_file': body_name, 'body_bytes': len(raw),
              'body_sha256': hashlib.sha256(raw).hexdigest(),
              'headers': {'Content-Type': 'text/tab-separated-values; charset=utf-8',
                          'string-api-version': '2'}}
    (directory / body_name).write_bytes(raw)
    (directory / name).write_text(json.dumps(record))
    return name, record, ids


class RequestPlanTests(unittest.TestCase):
    def test_documented_parameters_preserve_exact_inputs_without_labels(self):
        ids = ['P00001-2', 'P00001']
        mapping_params = runner.parameters('mapping', ids)
        self.assertEqual(mapping_params, {'identifiers': 'P00001-2\rP00001',
            'species': '9606', 'caller_identity': 'biograph-steward', 'echo_query': '1'})
        self.assertNotIn('limit', mapping_params)
        network = runner.parameters('network', ['9606.A', '9606.B'])
        self.assertEqual(network['required_score'], '0')
        self.assertEqual(network['network_type'], 'functional')
        self.assertEqual(network['network_flavor'], 'typed')
        self.assertEqual(network['typed_regulatory_edges'], '0')
        self.assertEqual(network['typed_physical_edges'], '1')
        self.assertEqual(network['add_nodes'], '0')

    def test_plan_preserves_every_nomination_and_bounds_network_size(self):
        candidates, mappings = [], {}
        for i in range(52):
            pair = ['P%05d' % (2*i), 'P%05d' % (2*i+1)]
            candidates.append({'products': pair, 'source_row': i,
                               'assay_eligible': i % 2 == 0, 'detected': i % 3 == 0})
            for j, p in enumerate(pair):
                mappings[p] = mapping('9606.X%d' % (2*i+j))
        mappings[candidates[1]['products'][0]] = mapping(None, 'unmapped')
        mappings[candidates[2]['products'][1]] = mapping(None, 'ambiguous')
        mappings[candidates[3]['products'][1]] = mappings[candidates[3]['products'][0]].copy()
        before = deepcopy(candidates)
        plan = runner.network_plan(candidates, mappings)
        self.assertEqual([i for b in plan for i in b['candidate_indices']], list(range(52)))
        self.assertEqual([len(b['candidate_indices']) for b in plan], [25, 25, 2])
        self.assertTrue(all(len(b['string_ids']) <= 50 for b in plan))
        self.assertTrue(all(len(b['string_ids']) != 1 for b in plan))
        self.assertEqual(candidates, before)
        altered = [{**c, 'detected': not c['detected'], 'assay_eligible': not c['assay_eligible']}
                   for c in candidates]
        self.assertEqual(runner.network_plan(altered, mappings), plan)
        for batch in plan:
            for index in batch['candidate_indices']:
                endpoints = [mappings[p] for p in candidates[index]['products']]
                if all(e['status'] == 'resolved' for e in endpoints) and endpoints[0] != endpoints[1]:
                    self.assertTrue({e['string_id'] for e in endpoints} <= set(batch['string_ids']))

    def test_all_unresolved_or_collapsed_batch_does_not_create_singleton_query(self):
        candidates = [{'products': ['P00001', 'P00002'], 'source_row': 1},
                      {'products': ['P00003', 'P00004'], 'source_row': 2}]
        mappings = {'P00001': mapping(None, 'unmapped'), 'P00002': mapping('9606.A'),
                    'P00003': mapping('9606.B'), 'P00004': mapping('9606.B')}
        self.assertEqual(runner.network_plan(candidates, mappings), [
            {'batch_id': 'network_0001', 'candidate_indices': [0, 1], 'string_ids': []}])


class ReceiptBindingTests(unittest.TestCase):
    def test_complete_receipt_binds_exact_request_and_raw_body(self):
        with tempfile.TemporaryDirectory() as tmp:
            folder = Path(tmp).resolve(); name, data, ids = receipt(folder)
            self.assertEqual(runner._verified_response(folder, name, 'mapping', 'mapping_0001', ids), b'invented\trow\n')
            with self.assertRaises(ValueError):
                runner._verified_response(folder, name, 'mapping', 'mapping_0001', list(reversed(ids)))
            (folder / 'responses' / data['body_file']).write_bytes(b'tampered')
            with self.assertRaises(ValueError):
                runner._verified_response(folder, name, 'mapping', 'mapping_0001', ids)

    def test_error_redirect_version_type_and_traversal_are_not_missing_evidence(self):
        mutations = [('status', 404), ('error', 'timeout'), ('kind', 'network'),
                     ('batch_id', 'mapping_0002'), ('final_url', 'https://string-db.org/'),
                     ('body_file', '../outside.tsv'),
                     ('headers', {'Content-Type': 'text/html', 'string-api-version': '2'}),
                     ('headers', {'Content-Type': 'text/tab-separated-values', 'string-api-version': '1'})]
        for key, value in mutations:
            with self.subTest(key=key, value=value), tempfile.TemporaryDirectory() as tmp:
                folder = Path(tmp).resolve(); name, data, ids = receipt(folder)
                data[key] = value
                (folder / 'responses' / name).write_text(json.dumps(data))
                with self.assertRaises(ValueError):
                    runner._verified_response(folder, name, 'mapping', 'mapping_0001', ids)
        with tempfile.TemporaryDirectory() as tmp:
            with self.assertRaises(ValueError):
                runner._verified_response(Path(tmp).resolve(), '../receipt.json', 'mapping', 'mapping_0001', ['P00001'])

    def test_content_length_mismatch_is_rejected_on_reopen(self):
        with tempfile.TemporaryDirectory() as tmp:
            folder = Path(tmp).resolve(); name, data, ids = receipt(folder)
            data['headers']['Content-Length'] = str(data['body_bytes'] + 20)
            (folder / 'responses' / name).write_text(json.dumps(data))
            with self.assertRaises(ValueError):
                runner._verified_response(folder, name, 'mapping', 'mapping_0001', ids)


class ProtocolAndImmutabilityTests(unittest.TestCase):
    def make_protocol(self, folder):
        candidates = [{'products': ['P00001', 'P00002'], 'source_row': 1, 'assay_eligible': True},
                      {'products': ['P00003', 'P00004'], 'source_row': 2, 'assay_eligible': False}]
        accessions = {'uniprot_accessions': ['P00001', 'P00002', 'P00003', 'P00004']}
        runner.write_json(folder / 'candidates.json', candidates)
        runner.write_json(folder / 'accessions.json', accessions)
        runner.write_json(folder / 'assessment_rows.json', [{'invented': 'already consumed outcomes'}])
        scope = runner.seal({'format': 'biograph-steward.biological-comparison-scope.v1',
            'files': {'candidates.json': runner.sha(folder / 'candidates.json'),
                      'accession_inventory.json': runner.sha(folder / 'accessions.json')}})
        runner.write_json(folder / 'scope_report.json', scope)
        assessment = runner.seal({'outcomes_consumed_for_future_development': True,
            'files': {'rows.json': runner.sha(folder / 'assessment_rows.json')}})
        runner.write_json(folder / 'assessment_report.json', assessment)
        runner.write_json(folder / 'historical_protocol.json', {'invented': True})
        runner.write_json(folder / 'reference_verification.json', {'reference_already_consumed': True})
        protocol = runner.seal({'format': runner.PROTOCOL_FORMAT, 'rules': deepcopy(runner.RULES),
            'implementation_sha256': runner.implementation(),
            'assessment_rows_sha256': runner.sha(folder / 'assessment_rows.json'),
            'assessment_report_sha256': runner.sha(folder / 'assessment_report.json'),
            'mapping_plan': [{'batch_id': 'mapping_0001', 'accessions': accessions['uniprot_accessions']}],
            'files': runner._source_files(folder)})
        runner.write_json(folder / 'protocol.json', protocol)
        return protocol

    def test_protocol_seal_population_payload_and_code_pins_are_enforced(self):
        with tempfile.TemporaryDirectory() as tmp, patch.dict(runner.RULES,
                {'candidate_pairs': 2, 'assay_eligible': 1, 'accessions': 4}):
            folder = Path(tmp).resolve(); protocol = self.make_protocol(folder)
            replay, files = runner.validate_protocol(folder)
            self.assertEqual(replay, protocol)
            self.assertEqual(len(files['candidates.json']), 2)
            original = (folder / 'candidates.json').read_bytes()
            (folder / 'candidates.json').write_bytes(original + b' ')
            with self.assertRaises(ValueError):
                runner.validate_protocol(folder)
            (folder / 'candidates.json').write_bytes(original)
            protocol['implementation_sha256']['scripts/run_string_component.py'] = '0' * 64
            protocol.pop('content_sha256')
            runner.write_json(folder / 'protocol.json', runner.seal(protocol))
            with self.assertRaises(ValueError):
                runner.validate_protocol(folder)

    def test_started_access_marker_blocks_second_capture_before_network(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp).resolve(); protocol_dir = root / 'protocol'; protocol_dir.mkdir()
            marker = root / 'protocol_predictor_access.json'; marker.write_text('{}')
            with patch.object(runner, 'validate_protocol', return_value=({}, {})), \
                    patch.object(runner, 'CaptureClient') as client:
                with self.assertRaises(ValueError):
                    runner.capture(protocol_dir, root / 'fresh_output')
            client.assert_not_called()
            self.assertFalse((root / 'fresh_output').exists())

    def test_existing_or_nested_output_is_rejected_before_marker_and_network(self):
        for choice in ['existing', 'nested']:
            with self.subTest(choice=choice), tempfile.TemporaryDirectory() as tmp:
                root = Path(tmp).resolve(); source = root / 'protocol'; source.mkdir()
                output = root / 'existing' if choice == 'existing' else source / 'nested'
                if choice == 'existing': output.mkdir()
                with patch.object(runner, 'validate_protocol', return_value=({}, {})), \
                        patch.object(runner, 'CaptureClient') as client:
                    with self.assertRaises(ValueError):
                        runner.capture(source, output)
                client.assert_not_called()
                self.assertFalse((root / 'protocol_predictor_access.json').exists())


class MockCaptureTests(unittest.TestCase):
    def test_success_preserves_exact_raw_bytes_and_rate_interval(self):
        with tempfile.TemporaryDirectory() as tmp:
            folder = Path(tmp).resolve(); client = runner.CaptureClient(folder)
            raw = b'header\tfield\nvalue\tvalue\n\n'
            def fake_open(request, timeout):
                self.assertEqual(timeout, runner.RULES['timeout_seconds'])
                self.assertIn('P00001%0DP00002', request.full_url)
                self.assertNotIn('detected', request.full_url)
                return FakeResponse(raw, request.full_url, headers={'Content-Length': str(len(raw))})
            with patch.object(runner, 'urlopen', side_effect=fake_open), \
                    patch.object(runner.time, 'sleep') as sleep, \
                    patch.object(runner.time, 'monotonic', return_value=100):
                body, name = client.fetch('mapping', 'mapping_0001', ['P00001', 'P00002'])
                client.fetch('mapping', 'mapping_0002', ['P00001', 'P00002'])
            self.assertEqual(body, raw)
            self.assertEqual(client.total_bytes, 2 * len(raw))
            self.assertEqual((folder / 'mapping_0001_attempt_01.tsv').read_bytes(), raw)
            self.assertGreaterEqual(sleep.call_args_list[1].args[0], runner.RULES['minimum_request_interval_seconds'])
            record = json.loads((folder / name).read_text())
            self.assertEqual(record['body_bytes'], len(raw))
            self.assertEqual(record['body_sha256'], hashlib.sha256(raw).hexdigest())

    def test_partial_content_length_is_stopped_not_accepted_as_complete(self):
        with tempfile.TemporaryDirectory() as tmp:
            client = runner.CaptureClient(Path(tmp).resolve())
            def fake_open(request, timeout):
                return FakeResponse(b'complete_row\n', request.full_url, headers={'Content-Length': '1000'})
            with patch.object(runner, 'urlopen', side_effect=fake_open), \
                    patch.object(runner.time, 'sleep'), \
                    patch.dict(runner.RULES, {'max_attempts_per_request': 1}):
                with self.assertRaises(ValueError):
                    client.fetch('mapping', 'mapping_0001', ['P00001'])

    def test_http404_and_html200_stop_without_retry_or_imputation(self):
        for mode in ['404', 'html']:
            with self.subTest(mode=mode), tempfile.TemporaryDirectory() as tmp:
                client = runner.CaptureClient(Path(tmp).resolve())
                def fake_open(request, timeout):
                    if mode == '404':
                        raise HTTPError(request.full_url, 404, 'Not Found', {}, io.BytesIO(b'error not mapping'))
                    return FakeResponse(b'<html>error</html>', request.full_url,
                                        headers={'Content-Type': 'text/html'})
                with patch.object(runner, 'urlopen', side_effect=fake_open) as opened, \
                        patch.object(runner.time, 'sleep'):
                    with self.assertRaises(ValueError):
                        client.fetch('mapping', 'mapping_0001', ['P00001'])
                self.assertEqual(opened.call_count, 1)
                record = json.loads((Path(tmp).resolve() / 'mapping_0001_attempt_01.json').read_text())
                self.assertIsNotNone(record['error'])

    def test_rate_limit_response_stops_without_ignoring_retry_after(self):
        with tempfile.TemporaryDirectory() as tmp:
            client = runner.CaptureClient(Path(tmp).resolve())
            def fake_open(request, timeout):
                raise HTTPError(request.full_url, 429, 'Too Many Requests',
                                {'Retry-After': '3600'}, io.BytesIO(b'Rate limited'))
            with patch.object(runner, 'urlopen', side_effect=fake_open) as opened, \
                    patch.object(runner.time, 'sleep'):
                with self.assertRaises(ValueError):
                    client.fetch('mapping', 'mapping_0001', ['P00001'])
            self.assertEqual(opened.call_count, 1)
            self.assertEqual(client.attempt_count, 1)
            self.assertFalse((Path(tmp).resolve() / 'mapping_0001_attempt_02.json').exists())

    def test_transient_attempts_are_bound_and_accounted_on_reopen(self):
        with tempfile.TemporaryDirectory() as tmp:
            folder = Path(tmp).resolve(); responses = folder / 'responses'; responses.mkdir()
            client = runner.CaptureClient(responses); calls = []
            def fake_open(request, timeout):
                calls.append(request.full_url)
                if len(calls) == 1:
                    raise HTTPError(request.full_url, 503, 'Unavailable', {}, io.BytesIO(b'temporary'))
                return FakeResponse(b'header\tvalue\n', request.full_url)
            with patch.object(runner, 'urlopen', side_effect=fake_open), \
                    patch.object(runner.time, 'sleep'):
                body, final_name = client.fetch('mapping', 'mapping_0001', ['P00001'])
            requests = {'mapping_0001': final_name}
            self.assertEqual(runner.audit_attempts(folder, requests), (2, len(b'temporary') + len(body)))
            prior_path = responses / 'mapping_0001_attempt_01.json'
            original = prior_path.read_bytes(); prior = json.loads(original)
            for field, value in [('status', 429), ('body_bytes', 0), ('parameters', {})]:
                changed = {**prior, field: value}; prior_path.write_text(json.dumps(changed))
                with self.subTest(field=field), self.assertRaises(ValueError):
                    runner.audit_attempts(folder, requests)
            prior_path.write_bytes(original)
            with self.assertRaises(ValueError):
                runner.audit_attempts(folder, {'mapping_0001': 'mapping_0001_attempt_01.json'})
            prior_path.unlink()
            with self.assertRaises(ValueError):
                runner.audit_attempts(folder, requests)

    def test_body_and_total_caps_stop_capture_and_preserve_failure_receipt(self):
        for bounds in [{'max_body_bytes': 8}, {'max_total_body_bytes': 8}]:
            with self.subTest(bounds=bounds), tempfile.TemporaryDirectory() as tmp:
                client = runner.CaptureClient(Path(tmp).resolve())
                def fake_open(request, timeout):
                    return FakeResponse(b'x' * 20, request.full_url)
                with patch.object(runner, 'urlopen', side_effect=fake_open), \
                        patch.object(runner.time, 'sleep'), \
                        patch.dict(runner.RULES, {**bounds, 'max_attempts_per_request': 1}):
                    with self.assertRaises(ValueError):
                        client.fetch('mapping', 'mapping_0001', ['P00001'])
                self.assertTrue((Path(tmp).resolve() / 'mapping_0001_attempt_01.json').is_file())


if __name__ == '__main__':
    unittest.main()
