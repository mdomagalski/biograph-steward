"""Ephemeral authenticated HTTP controls for the saved-data biological view."""
import json
from pathlib import Path
import tempfile
import threading
import unittest
from unittest.mock import patch
from urllib.error import HTTPError
from urllib.request import Request, ProxyHandler, build_opener

from biograph_steward.webapp import create_server, report_html
from test_biological_questions import fixture


class BiologicalHttpTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name).resolve()
        self.folder = self.root / 'saved'; self.folder.mkdir()
        self.graph = fixture()
        # read_run/source_material are boundary doubles in this transport
        # fixture. Its saved envelope must still match the verified graph.
        (self.folder / 'evidence_extension.json').write_text(json.dumps({
            'content_sha256': self.graph['evidence_extension_sha256'],
            'summary': self.graph['evidence_extension']}))
        self.snapshot = {'content_sha256': self.graph['snapshot_sha256']}
        self.read = patch('biograph_steward.reviews.read_run', return_value=(self.snapshot, [], self.graph))
        self.read_mock = self.read.start(); self.addCleanup(self.read.stop)
        self.material = patch('biograph_steward.evidence_extension.source_material', return_value={
            'mapit/source/model.tsv': b'protein\tvalue\nsynthetic\t0.1\n',
            'mapit/source/original.html': b'<script>must remain plain source data</script>'})
        self.material_mock = self.material.start(); self.addCleanup(self.material.stop)
        self.server = create_server(0, self.root, access_token='invented-biological-test-token')
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True); self.thread.start()
        self.url = 'http://127.0.0.1:' + str(self.server.server_port)
        self.opener = build_opener(ProxyHandler({}))

    def tearDown(self):
        self.server.shutdown(); self.server.server_close(); self.thread.join(); self.temp.cleanup()

    def request(self, path, body=None, *, auth=True):
        headers = {'Authorization': 'Bearer invented-biological-test-token'} if auth else {}
        if body is not None: headers['Content-Type'] = 'application/json'
        return self.opener.open(Request(self.url + path, json.dumps(body).encode() if body is not None else None, headers))

    def error(self, status, path, body=None, **kwargs):
        with self.assertRaises(HTTPError) as caught:
            self.request(path, body, **kwargs)
        self.assertEqual(caught.exception.code, status); caught.exception.close()

    def test_question_is_authenticated_read_only_and_uses_verified_run(self):
        self.error(401, '/api/biological-question', {'run_id': 'saved'}, auth=False)
        before = {p.relative_to(self.root).as_posix(): p.read_bytes() for p in self.root.rglob('*') if p.is_file()}
        with patch('biograph_steward.client.PharosClient.execute', side_effect=AssertionError('No retrieval')):
            with self.request('/api/biological-question', {'run_id': 'saved', 'offset': 25}) as response:
                answer = json.loads(response.read())
        self.assertEqual(answer['source_run'], 'saved')
        self.assertEqual(len(answer['records']), 5)
        self.assertTrue(answer['read_only']); self.assertEqual(answer['model_calls'], 0)
        self.read_mock.assert_called_with(self.folder)
        after = {p.relative_to(self.root).as_posix(): p.read_bytes() for p in self.root.rglob('*') if p.is_file()}
        self.assertEqual(before, after)
        self.error(400, '/api/biological-question', {'run_id': 'saved', 'limit': 26})
        self.error(400, '/api/biological-question', {'run_id': 'saved', 'new_source': True})

    def test_source_uses_only_verified_material_and_never_renders_html(self):
        path = '/api/extension-source/saved/extension_sources/mapit/source/model.tsv'
        self.error(401, path, auth=False)
        with self.request(path) as response:
            self.assertEqual(response.read(), b'protein\tvalue\nsynthetic\t0.1\n')
            self.assertEqual(response.headers['X-Content-Type-Options'], 'nosniff')
            self.assertIn('attachment', response.headers['Content-Disposition'])
        with self.request('/api/extension-source/saved/extension_sources/mapit/source/original.html') as response:
            self.assertTrue(response.headers['Content-Type'].startswith('text/plain'))
        self.material_mock.assert_called()
        self.error(400, '/api/extension-source/saved/extension_sources/mapit/unpublished-secret.txt')

    def test_source_path_traversal_symlink_and_failed_replay_are_rejected(self):
        prefix = '/api/extension-source/saved/extension_sources/mapit/'
        for name in ('../secret.txt', 'source//model.tsv', '%2e%2e/secret.txt', 'source/model.tsv%00'):
            self.error(400, prefix + name)
        (self.root / 'alias').symlink_to(self.folder, target_is_directory=True)
        self.error(400, '/api/extension-source/alias/extension_sources/mapit/source/model.tsv')
        envelope = self.folder / 'evidence_extension.json'
        saved = envelope.read_bytes()
        changed = json.loads(saved); changed['content_sha256'] = '0' * 64
        envelope.write_text(json.dumps(changed))
        self.error(400, prefix + 'source/model.tsv')
        envelope.write_bytes(saved)
        self.material_mock.side_effect = ValueError('Changed source bytes')
        self.error(400, prefix + 'source/model.tsv')

    def test_view_reuses_existing_evidence_tab_and_context_labels(self):
        html = report_html(self.graph)
        self.assertIn('id="biologicalPanel"', html)
        self.assertIn('Show EGFR tissue evidence', html)
        self.assertIn('PHAROS + VERSIONED BIOLOGICAL SOURCES', html)
        self.assertIn('Pharos target proteins', html)
        self.assertIn('/api/biological-question', html)
        self.assertNotIn('__GUIDED_SCRIPT__', html)


if __name__ == '__main__':
    unittest.main()
