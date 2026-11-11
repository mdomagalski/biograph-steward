"""Authenticated read-only exploration uses the validated saved workspace."""
import json
from pathlib import Path
import tempfile
import threading
import unittest
from unittest.mock import patch
from urllib.error import HTTPError
from urllib.request import ProxyHandler, Request, build_opener

from biograph_steward.demo import demo_snapshot
from biograph_steward.graph import save_run
from biograph_steward.webapp import create_server, report_html


class ExplorationHttpTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.folder = self.root / 'saved'
        self.graph = save_run(demo_snapshot(), self.folder)
        self.before = {str(p.relative_to(self.root)): p.read_bytes()
                       for p in self.root.rglob('*') if p.is_file()}
        self.server = create_server(0, self.root, access_token='invented-read-only-test-token')
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()
        self.url = 'http://127.0.0.1:' + str(self.server.server_port)
        self.opener = build_opener(ProxyHandler({}))

    def tearDown(self):
        self.server.shutdown(); self.server.server_close(); self.thread.join()
        self.temp.cleanup()

    def request(self, route, body, *, auth=True, origin=None):
        headers = {'Content-Type': 'application/json'}
        if auth:
            headers['Authorization'] = 'Bearer invented-read-only-test-token'
        if origin:
            headers['Origin'] = origin
        with self.opener.open(Request(self.url + route, json.dumps(body).encode(), headers)) as response:
            self.assertEqual(response.headers['Cache-Control'], 'no-store')
            return json.loads(response.read())

    def test_paths_are_source_bound_and_do_not_write_or_request_sources(self):
        source = self.graph['assertions'][0]['subject']
        with patch('biograph_steward.client.PharosClient.execute', side_effect=AssertionError('No retrieval')):
            result = self.request('/api/explore', {'run_id': 'saved', 'source': source,
                'target': None, 'view': 'candidates', 'max_hops': 2})
        self.assertEqual(result['source_run'], 'saved')
        self.assertEqual(result['snapshot_sha256'], self.graph['snapshot_sha256'])
        self.assertTrue(result['paths'])
        self.assertTrue(all(step['review_state'] == 'candidate'
                            for path in result['paths'] for step in path['steps']))
        after = {str(p.relative_to(self.root)): p.read_bytes()
                 for p in self.root.rglob('*') if p.is_file()}
        self.assertEqual(after, self.before)

    def test_source_guide_does_not_accept_candidates(self):
        assertion = self.graph['assertions'][0]
        result = self.request('/api/inspect-source', {'run_id': 'saved', 'selection_id': assertion['id']})
        self.assertTrue(result['read_only'])
        self.assertEqual(result['source_run'], 'saved')
        self.assertEqual(result['selection']['id'], assertion['id'])
        self.assertEqual(result['review']['state'], 'candidate')
        self.assertEqual(result['model_calls'], 0)
        self.assertEqual(result['source_fetches'], 0)
        self.assertEqual(result['actions'], [])

    def test_unverifiable_optional_reuse_is_explicit_and_does_not_hide_source(self):
        with patch('biograph_steward.assay_source_reuse.reuse_view', side_effect=ValueError('Stale proof')):
            result = self.request('/api/inspect-source', {'run_id': 'saved',
                'selection_id': self.graph['assertions'][0]['id']})
        self.assertEqual(result['reuse']['status'], 'unverifiable_saved_annotation')
        self.assertFalse(result['reuse']['records'])
        self.assertNotEqual(result['reuse']['status'], 'independent')

    def test_authentication_origin_and_exact_options_are_enforced(self):
        body = {'run_id': 'saved', 'source': self.graph['nodes'][0]['id']}
        for route in ('/api/explore', '/api/inspect-source'):
            with self.subTest(route=route), self.assertRaises(HTTPError) as error:
                self.request(route, body, auth=False)
            self.assertEqual(error.exception.code, 401); error.exception.close()
        for payload in ({**body, 'write': True}, {**body, 'max_hops': True},
                        {**body, 'max_hops': 99}, {**body, 'max_paths': 10000},
                        {**body, 'run_id': '../saved'}, {**body, 'run_id': 'missing'}):
            with self.subTest(payload=payload), self.assertRaises(HTTPError) as error:
                self.request('/api/explore', payload)
            self.assertEqual(error.exception.code, 400); error.exception.close()
        with self.assertRaises(HTTPError) as error:
            self.request('/api/explore', body, origin='https://unrelated.example')
        self.assertEqual(error.exception.code, 403); error.exception.close()

    def test_symlink_is_rejected_and_cached_graph_cannot_override_source_replay(self):
        (self.root / 'alias').symlink_to(self.folder, target_is_directory=True)
        body = {'source': self.graph['assertions'][0]['subject']}
        with self.assertRaises(HTTPError) as error:
            self.request('/api/explore', {'run_id': 'alias', **body})
        self.assertEqual(error.exception.code, 400); error.exception.close()
        graph_file = self.folder / 'graph.json'
        graph = json.loads(graph_file.read_text()); graph['nodes'][0]['name'] = 'changed saved content'
        graph_file.write_text(json.dumps(graph))
        # Non-assay runs are rebuilt from their source snapshots by read_run;
        # their cached graph.json must never override that canonical replay.
        result = self.request('/api/explore', {'run_id': 'saved', **body})
        from biograph_steward.questions import graph_basis
        self.assertEqual(result['graph_basis_sha256'], graph_basis(self.graph))
        self.assertFalse(any(n.get('name') == 'changed saved content' for n in result['nodes']))

    def test_embedded_report_includes_task_panels_and_uses_safe_inline_data(self):
        output = report_html(self.graph)
        for name in ('workspaceData', 'workspaceAsk', 'workspaceEvidence', 'workspaceCompare', 'workspaceExport'):
            self.assertEqual(output.count('id="' + name + '"'), 1)
        self.assertIn('initializeWorkspaceNavigation();', output)
        self.assertIn('revealWorkspaceTarget(target)', output)

    def test_saved_comparator_reports_are_authenticated_verified_and_allowlisted(self):
        from biograph_steward.client import digest
        from biograph_steward.file_utils import sha
        from biograph_steward.support_comparator import FORMAT, UPSTREAM_COMMIT
        folder = self.root / 'comparator' / 'prepared'; folder.mkdir(parents=True)
        case = {'case_id': 'invented-method-fit-case'}
        case['request_sha256'] = digest(case)
        files = {'cases.json': json.dumps([case]), 'report.html': '<html>Invented method-fit fixture</html>',
                 'report.json': json.dumps({'status': 'prepared_not_executed', 'case_count': 1,
                    'unique_query_count': 1, 'hosted_model_calls': 0}),
                 'sampled_edges_development.csv': 'case_id\ninvented-method-fit-case\n',
                 'OPTIMUSKG_LICENSE.txt': 'Invented fixture license placeholder'}
        for name, value in files.items():
            (folder / name).write_text(value)
        manifest = {'format': FORMAT, 'upstream_commit': UPSTREAM_COMMIT,
                    'files': {name: sha(folder / name) for name in files}}
        manifest['content_sha256'] = digest(manifest)
        (folder / 'manifest.json').write_text(json.dumps(manifest))
        def get(route, auth=True):
            headers = {'Authorization': 'Bearer invented-read-only-test-token'} if auth else {}
            return self.opener.open(Request(self.url + route, headers=headers))
        with self.assertRaises(HTTPError) as error:
            get('/api/support-comparators', auth=False)
        self.assertEqual(error.exception.code, 401); error.exception.close()
        with get('/api/support-comparators') as response:
            self.assertEqual(json.loads(response.read())['reports'][0]['id'], 'comparator')
        for name, value in {**files, 'manifest.json': (folder / 'manifest.json').read_text()}.items():
            with get('/api/support-comparator/comparator/' + name) as response:
                self.assertEqual(response.read().decode(), value)
        with self.assertRaises(HTTPError) as error:
            get('/api/support-comparator/comparator/snapshot.json')
        self.assertEqual(error.exception.code, 404); error.exception.close()
        (folder / 'cases.json').write_text('[]')
        with self.assertRaises(HTTPError) as error:
            get('/api/support-comparator/comparator/report.html')
        self.assertEqual(error.exception.code, 400); error.exception.close()
        with get('/api/support-comparators') as response:
            self.assertEqual(json.loads(response.read())['reports'], [])


if __name__ == '__main__':
    unittest.main()
