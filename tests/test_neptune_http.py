"""Authenticated Neptune reads use verified saved sources; no AWS calls."""
from copy import deepcopy
import json
import os
from pathlib import Path
import tempfile
import threading
import unittest
from unittest.mock import patch
from urllib.error import HTTPError
from urllib.request import ProxyHandler, Request, build_opener

from biograph_steward.client import digest
from biograph_steward.graph import save_run
from biograph_steward.webapp import create_server, report_html
from test_civic import fixture


class FakeMirror:
    """The transport seam returns exact source records, not a cloud simulator."""
    def __init__(self):
        self.calls = []
        self.error = None
        self.change = None

    def inspect(self, graph, node_id, limit=100):
        self.calls.append((deepcopy(graph), node_id, limit))
        if self.error:
            raise self.error
        incident = sorted((edge for edge in graph['edges']
                           if node_id in (edge['subject'], edge['object'])), key=lambda edge: edge['id'])
        edges = incident[:limit]
        assertion_ids = sorted({edge['assertion_id'] for edge in edges})
        result = {
            'dataset_id': 'bgs:' + digest(graph), 'graph_sha256': digest(graph),
            'node_id': node_id, 'limit': limit,
            'node': next(node for node in graph['nodes'] if node['id'] == node_id),
            'edges': edges, 'edge_ids': [edge['id'] for edge in edges],
            'assertions': [row for row in graph['assertions'] if row['id'] in assertion_ids],
            'assertion_ids': assertion_ids, 'truncated': len(incident) > limit,
            'full_parity_verified_at': '2026-11-11T12:00:00+00:00',
            'verification_receipt_sha256': 'a' * 64,
        }
        if self.change:
            self.change(result)
        return result


class NeptuneHttpTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        snapshot, civic = fixture()
        self.folder = self.root / 'saved'
        self.graph = save_run(snapshot, self.folder, civic_snapshot=civic)
        self.node_id = next(row['subject'] for row in self.graph['assertions']
                            if row['kind'] == 'variant_therapy_response')
        self.before = {str(path.relative_to(self.root)): path.read_bytes()
                       for path in self.root.rglob('*') if path.is_file()}
        self.env = patch.dict(os.environ, {'BIOGRAPH_NEPTUNE_ENDPOINT': '', 'BIOGRAPH_AWS_REGION': ''})
        self.env.start()
        self.fake = FakeMirror()
        self.opener = build_opener(ProxyHandler({}))
        self.start(self.fake)

    def start(self, mirror):
        self.server = create_server(0, self.root, access_token='invented-neptune-test-token',
                                    neptune_mirror=mirror)
        self.server.RequestHandlerClass.log_message = lambda *args: None
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()
        self.url = 'http://127.0.0.1:' + str(self.server.server_port)

    def stop(self):
        self.server.shutdown(); self.server.server_close(); self.thread.join()

    def tearDown(self):
        self.stop(); self.env.stop(); self.temp.cleanup()

    def request(self, route, body=None, *, auth=True, origin=None):
        headers = {}
        if auth:
            headers['Authorization'] = 'Bearer invented-neptune-test-token'
        if origin:
            headers['Origin'] = origin
        data = None
        if body is not None:
            data = json.dumps(body).encode()
            headers['Content-Type'] = 'application/json'
        with self.opener.open(Request(self.url + route, data, headers)) as response:
            self.assertEqual(response.headers['Cache-Control'], 'no-store')
            return json.loads(response.read())

    def body(self, **options):
        return {'run_id': 'saved', 'node_id': self.node_id, **options}

    def assert_error(self, status, route, body=None, **options):
        with self.assertRaises(HTTPError) as error:
            self.request(route, body, **options)
        self.assertEqual(error.exception.code, status)
        value = json.loads(error.exception.read())
        error.exception.close()
        return value

    def test_status_is_authenticated_configuration_only_and_does_not_probe(self):
        self.assert_error(401, '/api/neptune-status', auth=False)
        self.assertEqual(self.request('/api/neptune-status'), {'configured': True, 'backend': 'neptune'})
        self.assertEqual(self.fake.calls, [])

    def test_selected_cloud_ids_get_existing_readable_guides_without_mutation(self):
        with patch('biograph_steward.client.PharosClient.execute', side_effect=AssertionError('No retrieval')):
            result = self.request('/api/neptune-inspect', self.body(limit=20))
        self.assertEqual(result['backend'], 'neptune')
        self.assertTrue(result['read_only'])
        self.assertEqual(result['source_run'], 'saved')
        self.assertEqual(result['graph_sha256'], digest(self.graph))
        self.assertEqual(result['snapshot_sha256'], self.graph['snapshot_sha256'])
        self.assertTrue(result['full_parity_verified_at'])
        self.assertIn('DOES_NOT_SUPPORT', json.dumps(result['assertions']))
        self.assertEqual(len(result['source_guides']), 3)
        self.assertEqual(result['guides_omitted'], len(result['assertion_ids']) - 3)
        for guide in result['source_guides']:
            self.assertIn(guide['selection']['id'], result['assertion_ids'])
            self.assertTrue(guide['read_only'])
            self.assertEqual(guide['review']['state'], 'candidate')
            self.assertEqual(guide['model_calls'], 0)
            self.assertEqual(guide['source_fetches'], 0)
            self.assertEqual(guide['source_run'], 'saved')
        after = {str(path.relative_to(self.root)): path.read_bytes()
                 for path in self.root.rglob('*') if path.is_file()}
        self.assertEqual(after, self.before)

    def test_auth_origin_unknown_entities_and_strict_bounds_precede_cloud_read(self):
        self.assert_error(401, '/api/neptune-inspect', self.body(), auth=False)
        self.assert_error(403, '/api/neptune-inspect', self.body(), origin='https://unrelated.example')
        for body in [self.body(write=True), self.body(limit=True), self.body(limit=101),
                     self.body(limit=0), self.body(node_id='unknown'), self.body(node_id=None),
                     self.body(run_id='../saved'), self.body(run_id='missing'), {'run_id': 'saved'}]:
            with self.subTest(body=body):
                self.assert_error(400, '/api/neptune-inspect', body)
        self.assertEqual(self.fake.calls, [])

    def test_source_alias_and_tampered_source_are_rejected_before_cloud_read(self):
        (self.root / 'alias').symlink_to(self.folder, target_is_directory=True)
        self.assert_error(400, '/api/neptune-inspect', self.body(run_id='alias'))
        snapshot = self.folder / 'snapshot.json'
        changed = json.loads(snapshot.read_text()); changed['created_at'] = 'changed'
        snapshot.write_text(json.dumps(changed))
        self.assert_error(400, '/api/neptune-inspect', self.body())
        self.assertEqual(self.fake.calls, [])

    def test_missing_configuration_has_no_saved_file_fallback(self):
        self.stop(); self.start(None)
        self.assertEqual(self.request('/api/neptune-status'), {'configured': False, 'backend': None})
        result = self.assert_error(503, '/api/neptune-inspect', self.body())
        self.assertIsNone(result['backend'])
        self.assertNotIn('source_guides', result)

    def test_cloud_failure_or_parity_mismatch_fails_closed_without_secret_details(self):
        self.fake.error = RuntimeError('signed request secret=do-not-expose')
        result = self.assert_error(503, '/api/neptune-inspect', self.body())
        self.assertNotIn('secret', json.dumps(result))
        self.assertNotIn('source_guides', result)
        self.fake.error = None
        for change in [lambda value: value.update(graph_sha256='changed'),
                       lambda value: value.update(node_id='different'),
                       lambda value: value.update(assertion_ids=['unknown'])]:
            self.fake.change = change
            result = self.assert_error(503, '/api/neptune-inspect', self.body())
            self.assertNotIn('source_guides', result)

    def test_configured_mirror_is_lazy_and_reused_for_server_lifetime(self):
        self.stop()
        with patch.dict(os.environ, {'BIOGRAPH_NEPTUNE_ENDPOINT': 'https://private-neptune.example:8182',
                                    'BIOGRAPH_AWS_REGION': 'us-east-1'}):
            self.start(None)
            with patch('biograph_steward.neptune.Mirror', return_value=self.fake) as factory:
                status = self.request('/api/neptune-status')
                self.assertEqual(status, {'configured': True, 'backend': 'neptune'})
                factory.assert_not_called()
                self.request('/api/neptune-inspect', self.body(limit=1))
                self.request('/api/neptune-inspect', self.body(limit=2))
                factory.assert_called_once_with('https://private-neptune.example:8182', 'us-east-1')
        self.assertEqual([call[2] for call in self.fake.calls], [1, 2])

    def test_compact_neptune_card_is_in_existing_evidence_tab(self):
        html = report_html(self.graph)
        self.assertEqual(html.count('id="neptunePanel"'), 1)
        self.assertIn('id="neptuneNode"', html)
        self.assertIn('Read Neptune', html)
        self.assertIn("api('/api/neptune-inspect'", html)
        self.assertIn('result.backend!==\'neptune\'', html)
        self.assertLess(html.index('id="workspaceEvidence"'), html.index('id="neptunePanel"'))
        self.assertLess(html.index('id="neptunePanel"'), html.index('id="workspaceCompare"'))


if __name__ == '__main__':
    unittest.main()
