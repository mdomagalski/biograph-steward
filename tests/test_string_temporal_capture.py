"""Independent archive capture guards: invented IDs and mock HTTP only."""
from copy import deepcopy
import hashlib
import io
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch
from urllib.error import HTTPError

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))
import run_string_temporal as runner
from biograph_steward.string_temporal import MAPPING_COLUMNS, NETWORK_COLUMNS


VERSION = b'string_version\tstable_address\n12.0\thttps://version-12-0.string-db.org\n'


def tsv(columns, rows=()):
    return ('\t'.join(columns) + '\n' + ''.join('\t'.join(row) + '\n' for row in rows)).encode()


def mapped(accessions):
    return tsv(MAPPING_COLUMNS, [
        [str(i), accession, '9606.' + chr(65 + i), '9606', 'Homo sapiens', chr(65 + i), 'invented']
        for i, accession in enumerate(accessions)])


class Response:
    def __init__(self, body, url, headers=None, status=200):
        self.stream = io.BytesIO(body)
        self.status, self.url = status, url
        self.headers = {'Content-Type': 'text/tab-separated-values; charset=utf-8',
                        'String-api-version': '2', 'Content-Length': str(len(body))}
        self.headers.update(headers or {})

    def read(self, limit=-1):
        return self.stream.read(limit)

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return False


def write_receipt(root, *, kind='physical', batch='physical_network_0001',
                  identifiers=None, body=None):
    identifiers = identifiers or ['9606.A', '9606.B']
    body = body if body is not None else tsv(NETWORK_COLUMNS)
    folder = root / 'responses'
    folder.mkdir(exist_ok=True)
    url, params = runner.request_url(kind, identifiers)
    prefix = batch + '_attempt_01'
    record = {'status': 200, 'error': None, 'kind': kind, 'batch_id': batch,
              'attempt': 1, 'url': url, 'final_url': url, 'parameters': params,
              'body_file': prefix + '.tsv', 'body_bytes': len(body),
              'body_sha256': hashlib.sha256(body).hexdigest(),
              'headers': Response(body, url).headers}
    (folder / record['body_file']).write_bytes(body)
    (folder / (prefix + '.json')).write_text(json.dumps(record))
    return prefix + '.json', record, identifiers


class ContractTests(unittest.TestCase):
    def test_archive_requests_use_only_documented_native_parameters(self):
        ids = ['P00001-2', 'P00001']
        url, params = runner.request_url('mapping', ids)
        self.assertTrue(url.startswith('https://version-12-0.string-db.org/api/tsv/get_string_ids?'))
        self.assertEqual(params, {'identifiers': 'P00001-2\rP00001', 'species': '9606',
                                 'caller_identity': 'biograph-steward', 'echo_query': '1'})
        for view in runner.VIEWS:
            _, params = runner.request_url(view, ['9606.A', '9606.B'])
            self.assertEqual(params, {'identifiers': '9606.A\r9606.B', 'species': '9606',
                'caller_identity': 'biograph-steward', 'network_type': view,
                'required_score': '0', 'add_nodes': '0'})
            self.assertNotIn('typed_physical_edges', params)
            self.assertNotIn('network_flavor', params)
        self.assertEqual(runner.request_url('version', []),
                         ('https://version-12-0.string-db.org/api/tsv/version', {}))
        for kind, ids in [('typed', ['9606.A', '9606.B']), ('version', ['9606.A'])]:
            with self.subTest(kind=kind), self.assertRaises(ValueError):
                runner.request_url(kind, ids)

    def test_endpoint_version_is_explicit_not_inferred_from_url(self):
        self.assertEqual(runner.parse_version(VERSION)['string_version'], '12.0')
        for raw in [VERSION.replace(b'12.0', b'12.5'),
                    VERSION.replace(b'version-12-0', b'string-db'), VERSION + b'extra\n',
                    b'', b'<html>Error</html>']:
            with self.subTest(raw=raw), self.assertRaises(ValueError):
                runner.parse_version(raw)


class ReceiptTests(unittest.TestCase):
    def test_receipt_binds_exact_view_archive_and_query(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp).resolve()
            name, data, ids = write_receipt(root)
            self.assertEqual(runner.verified_response(root, name, 'physical',
                             'physical_network_0001', ids), tsv(NETWORK_COLUMNS))
            for kind, identifiers in [('functional', ids), ('physical', list(reversed(ids)))]:
                with self.subTest(kind=kind), self.assertRaises(ValueError):
                    runner.verified_response(root, name, kind, 'physical_network_0001', identifiers)
            path = root / 'responses' / name
            for key, value in [('final_url', data['url'].replace('version-12-0', 'version-12-5')),
                               ('status', 404), ('error', 'timeout'), ('body_file', '../outside.tsv')]:
                changed = {**data, key: value}
                path.write_text(json.dumps(changed))
                with self.subTest(key=key), self.assertRaises(ValueError):
                    runner.verified_response(root, name, 'physical', 'physical_network_0001', ids)
            path.write_text(json.dumps(data))
            (root / 'responses' / data['body_file']).write_bytes(b'changed')
            with self.assertRaises(ValueError):
                runner.verified_response(root, name, 'physical', 'physical_network_0001', ids)

    def test_partial_body_wrong_type_encoding_and_api_version_fail_offline(self):
        for headers in [{'Content-Length': '100000'}, {'Content-Type': 'text/html'},
                        {'String-api-version': '1'}, {'Content-Encoding': 'gzip'}]:
            with self.subTest(headers=headers), tempfile.TemporaryDirectory() as temp:
                root = Path(temp).resolve()
                name, data, ids = write_receipt(root)
                data['headers'].update(headers)
                (root / 'responses' / name).write_text(json.dumps(data))
                with self.assertRaises(ValueError):
                    runner.verified_response(root, name, 'physical', 'physical_network_0001', ids)

    def test_unaccounted_attempts_and_raw_bodies_are_rejected(self):
        for extra in ['body', 'receipt']:
            with self.subTest(extra=extra), tempfile.TemporaryDirectory() as temp:
                root = Path(temp).resolve()
                name, data, _ = write_receipt(root)
                requests = {data['batch_id']: name}
                self.assertEqual(runner.audit_attempts(root, requests), (1, data['body_bytes']))
                if extra == 'body':
                    (root / 'responses/unaccounted.tsv').write_bytes(b'raw')
                else:
                    (root / 'responses/unaccounted.json').write_text(json.dumps({**data,
                                                               'batch_id': 'unplanned'}))
                with self.assertRaises(ValueError):
                    runner.audit_attempts(root, requests)


class TransportTests(unittest.TestCase):
    def test_success_preserves_raw_and_waits_between_calls(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp).resolve()
            client = runner.CaptureClient(root)
            def opened(request, timeout):
                self.assertEqual(timeout, runner.RULES['timeout_seconds'])
                self.assertEqual(request.get_header('Accept-encoding'), 'identity')
                return Response(VERSION, request.full_url)
            with patch.object(runner, 'urlopen', side_effect=opened), \
                    patch.object(runner.time, 'monotonic', return_value=100), \
                    patch.object(runner.time, 'sleep') as sleep:
                raw, name = client.fetch('version', 'source_version', [])
                client.fetch('version', 'second_version', [])
            self.assertEqual(raw, VERSION)
            self.assertEqual((root / name.replace('.json', '.tsv')).read_bytes(), VERSION)
            self.assertEqual(client.total_bytes, len(VERSION) * 2)
            self.assertGreaterEqual(sleep.call_args_list[-1].args[0],
                                    runner.RULES['minimum_request_interval_seconds'])

    def test_429_and_technical_200_do_not_become_missing_scores(self):
        for mode in ['rate', 'partial', 'html', 'redirect']:
            with self.subTest(mode=mode), tempfile.TemporaryDirectory() as temp:
                root = Path(temp).resolve()
                client = runner.CaptureClient(root)
                def opened(request, timeout):
                    if mode == 'rate':
                        error = HTTPError(request.full_url, 429, 'rate limited',
                                          {'Retry-After': '3600'}, io.BytesIO(b'rate limit'))
                        self.addCleanup(error.close)
                        raise error
                    return Response(VERSION,
                        request.full_url if mode != 'redirect' else 'https://string-db.org/api/tsv/version',
                        headers=({'Content-Length': '1000'} if mode == 'partial' else
                                 {'Content-Type': 'text/html'} if mode == 'html' else {}))
                with patch.object(runner, 'urlopen', side_effect=opened) as call, \
                        patch.object(runner.time, 'sleep'):
                    with self.assertRaises(ValueError):
                        client.fetch('version', 'source_version', [])
                self.assertEqual(call.call_count, 1)
                receipt = json.loads((root / 'source_version_attempt_01.json').read_text())
                self.assertIsNotNone(receipt['error'])

    def test_retry_accounting_preserves_previous_failed_attempt(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp).resolve()
            responses = root / 'responses'; responses.mkdir()
            client = runner.CaptureClient(responses)
            calls = []
            def opened(request, timeout):
                calls.append(request.full_url)
                if len(calls) == 1:
                    error = HTTPError(request.full_url, 503, 'temporary', {}, io.BytesIO(b'temporary'))
                    self.addCleanup(error.close)
                    raise error
                return Response(VERSION, request.full_url)
            with patch.object(runner, 'urlopen', side_effect=opened), patch.object(runner.time, 'sleep'):
                raw, name = client.fetch('version', 'source_version', [])
            requests = {'source_version': name}
            self.assertEqual(calls[0], calls[1])
            self.assertEqual(runner.audit_attempts(root, requests), (2, len(raw) + len(b'temporary')))
            path = responses / 'source_version_attempt_01.json'
            receipt = json.loads(path.read_text()); receipt['status'] = 429
            path.write_text(json.dumps(receipt))
            with self.assertRaises(ValueError):
                runner.audit_attempts(root, requests)

    def test_response_byte_caps_preserve_failure_receipt(self):
        for guard in [{'max_body_bytes': 8}, {'max_total_body_bytes': 8}]:
            with self.subTest(guard=guard), tempfile.TemporaryDirectory() as temp:
                root = Path(temp).resolve()
                client = runner.CaptureClient(root)
                def opened(request, timeout):
                    return Response(VERSION, request.full_url)
                with patch.dict(runner.RULES, guard), \
                        patch.object(runner, 'urlopen', side_effect=opened), \
                        patch.object(runner.time, 'sleep'):
                    with self.assertRaises(ValueError):
                        client.fetch('version', 'source_version', [])
                self.assertTrue((root / 'source_version_attempt_01.json').is_file())


class ProtocolTests(unittest.TestCase):
    def synthetic_protocol(self, root):
        accessions = ['P00001', 'P00002', 'P00003', 'P00004']
        candidates = [{'products': accessions[:2], 'source_row': 1, 'assay_eligible': True},
                      {'products': accessions[2:], 'source_row': 2, 'assay_eligible': False}]
        directory = root / 'reference_capture/protocol'; directory.mkdir(parents=True)
        runner.write_json(directory / 'accessions.json', {'uniprot_accessions': accessions})
        reference = {'candidates': candidates, 'label_rows': [], 'predictions': [],
                     'report': {'content_sha256': 'a' * 64}}
        protocol = runner.seal({'format': runner.PROTOCOL_FORMAT,
            'rules': deepcopy(runner.RULES), 'implementation_sha256': runner.implementation(),
            'reference_capture_sha256': reference['report']['content_sha256'],
            'mapping_plan': runner.mapping_plan(accessions), 'files': runner._source_files(root)})
        runner.write_json(root / 'protocol.json', protocol)
        return reference, protocol

    def test_protocol_pins_code_population_plan_and_all_files(self):
        with tempfile.TemporaryDirectory() as temp, patch.dict(runner.RULES,
                {'candidate_pairs': 2, 'assay_eligible': 1, 'accessions': 4}):
            root = Path(temp).resolve(); reference, protocol = self.synthetic_protocol(root)
            with patch.object(runner.original, 'verify_capture', return_value=reference):
                self.assertEqual(runner.validate_protocol(root)[0], protocol)
                (root / 'unplanned.json').write_text('{}')
                with self.assertRaises(ValueError):
                    runner.validate_protocol(root)
                (root / 'unplanned.json').unlink()
                changed = deepcopy(protocol)
                changed['implementation_sha256']['scripts/run_string_temporal.py'] = '0' * 64
                changed.pop('content_sha256')
                runner.write_json(root / 'protocol.json', runner.seal(changed))
                with self.assertRaises(ValueError):
                    runner.validate_protocol(root)
                changed = deepcopy(protocol); changed['mapping_plan'][0]['accessions'].reverse()
                changed.pop('content_sha256')
                runner.write_json(root / 'protocol.json', runner.seal(changed))
                with self.assertRaises(ValueError):
                    runner.validate_protocol(root)

    def test_marker_and_existing_or_nested_output_stop_before_http(self):
        for guard in ['marker', 'existing', 'nested']:
            with self.subTest(guard=guard), tempfile.TemporaryDirectory() as temp:
                root = Path(temp).resolve(); source = root / 'protocol'; source.mkdir()
                output = source / 'nested' if guard == 'nested' else root / 'capture'
                if guard == 'marker':
                    (root / 'protocol_predictor_access.json').write_text('{}')
                elif guard == 'existing':
                    output.mkdir()
                with patch.object(runner, 'validate_protocol', return_value=({}, {})), \
                        patch.object(runner, 'CaptureClient') as client:
                    with self.assertRaises(ValueError):
                        runner.capture(source, output)
                client.assert_not_called()

    def test_complete_mock_capture_replays_physical_only_pair(self):
        with tempfile.TemporaryDirectory() as temp, patch.dict(runner.RULES,
                {'candidate_pairs': 2, 'assay_eligible': 1, 'accessions': 4}):
            root = Path(temp).resolve(); source = root / 'protocol'; source.mkdir()
            reference, _ = self.synthetic_protocol(source)
            network = tsv(NETWORK_COLUMNS, [['9606.A', '9606.B', 'A', 'B', '9606',
                                            '0', '0', '0', '0', '0', '0', '0', '0']])
            calls = []
            def opened(request, timeout):
                url = request.full_url; calls.append(url)
                if url.endswith('/version'):
                    raw = VERSION
                elif '/get_string_ids?' in url:
                    raw = mapped(['P00001', 'P00002', 'P00003', 'P00004'])
                elif 'network_type=physical' in url:
                    raw = network
                else:
                    raw = tsv(NETWORK_COLUMNS)
                return Response(raw, url)
            with patch.object(runner.original, 'verify_capture', return_value=reference), \
                    patch.object(runner, 'urlopen', side_effect=opened), \
                    patch.object(runner.time, 'sleep'):
                report = runner.capture(source, root / 'capture')
                replay = runner.verify_capture(root / 'capture')
            self.assertEqual(report['request_count'], 4)
            self.assertEqual(report['http_attempt_count'], 4)
            self.assertEqual(len(calls), 4)
            prediction = replay['predictions'][0]['views']
            self.assertEqual(prediction['functional']['state'], 'no_returned_native_row')
            self.assertEqual(prediction['physical'], {'state': 'numeric', 'native_score': 0.0,
                                                      'ranking_score': 0.0})
            self.assertTrue((root / 'protocol_predictor_access.json').exists())
            with patch.object(runner, 'validate_protocol', return_value=({}, {})), \
                    patch.object(runner, 'CaptureClient') as client:
                with self.assertRaises(ValueError):
                    runner.capture(source, root / 'repeat')
                client.assert_not_called()


if __name__ == '__main__':
    unittest.main()
