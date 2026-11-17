"""Authenticated loopback transport for native GO questions; synthetic data only.

The saved-run boundary is patched to the already-tested native question fixture.
These tests exercise actual HTTP/auth/input dispatch and the real answer engine,
not another copy of its source-verification implementation.
"""
from copy import deepcopy
import json
from pathlib import Path
import tempfile
import threading
import unittest
from unittest.mock import patch
from urllib.error import HTTPError
from urllib.request import ProxyHandler, Request, build_opener

from biograph_steward.webapp import create_server, report_html
from test_goa_questions import PROTEIN, fixture


class NativeGoQuestionHttpTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name).resolve()
        self.folder = self.root / 'saved'; self.folder.mkdir()
        self.graph = fixture()
        self.token = 'invented-native-go-question-token'
        self.reader = patch('biograph_steward.reviews.read_run', return_value=({}, [], self.graph))
        self.read = self.reader.start(); self.addCleanup(self.reader.stop)
        self.server = create_server(0, self.root, access_token=self.token)
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True); self.thread.start()
        self.url = 'http://127.0.0.1:' + str(self.server.server_port)
        self.opener = build_opener(ProxyHandler({}))

    def tearDown(self):
        self.server.shutdown(); self.server.server_close(); self.thread.join(); self.temp.cleanup()

    def request(self, body=None, *, auth=True, origin=None, content_type='application/json'):
        headers = {'Content-Type': content_type}
        if auth: headers['Authorization'] = 'Bearer ' + self.token
        if origin: headers['Origin'] = origin
        value = {'run_id': 'saved', 'protein': PROTEIN} if body is None else body
        return self.opener.open(Request(self.url + '/api/native-go-question', json.dumps(value).encode(), headers))

    def error(self, code, body=None, **options):
        with self.assertRaises(HTTPError) as caught:
            self.request(body, **options)
        self.assertEqual(caught.exception.code, code)
        message = json.loads(caught.exception.read())
        caught.exception.close()
        return message

    def inventory(self):
        return {p.relative_to(self.root).as_posix(): p.read_bytes()
                for p in self.root.rglob('*') if p.is_file()}

    def test_native_source_answer_is_authenticated_read_only_and_preserves_complete_body(self):
        self.error(401, auth=False)
        before_graph, before_files = deepcopy(self.graph), self.inventory()
        with patch('biograph_steward.client.PharosClient.execute', side_effect=AssertionError('No fresh retrieval')):
            with self.request() as response:
                answer = json.loads(response.read())
        self.assertEqual(answer['format'], 'biograph-steward.native-go-question.v1')
        self.assertEqual(answer['source_run'], 'saved')
        self.assertEqual(answer['anchor'], PROTEIN)
        self.assertEqual(answer['summary']['matching_concepts'], 3)
        self.assertEqual(len(answer['records']), 4)
        self.assertEqual((answer['read_only'], answer['model_calls'], answer['source_fetches']), (True, 0, 0))
        by_native = {o['native_record']['id']: o['native_record'] for o in self.graph['extension_observations']}
        for row in answer['records']:
            self.assertEqual(row['native_record'], by_native[row['native_record_id']])
            self.assertEqual(len(row['native_record']['raw_fields']), 17)
            self.assertEqual(row['citations'][0]['url'],
                             'https://pubmed.ncbi.nlm.nih.gov/' + row['reference_identifiers'][0].split(':')[1] + '/')
        self.assertEqual(self.graph, before_graph)
        self.assertEqual(self.inventory(), before_files)
        self.read.assert_called_with(self.folder)

    def test_accepted_view_does_not_promote_source_supported_candidates(self):
        with self.request({'run_id': 'saved', 'protein': PROTEIN, 'view': 'accepted'}) as response:
            answer = json.loads(response.read())
        self.assertEqual(answer['view'], 'accepted')
        self.assertEqual(answer['concepts'], [])
        self.assertEqual(answer['records'], [])
        self.assertEqual(answer['summary']['matching_native_records'], 0)

    def test_origin_content_type_and_exact_option_scope_are_enforced(self):
        self.error(403, origin='https://unrelated.invalid')
        self.error(415, content_type='text/plain')
        invalid = [[], {'run_id': '../saved', 'protein': PROTEIN},
                   {'run_id': '/etc', 'protein': PROTEIN},
                   {'run_id': 'saved', 'protein': PROTEIN, 'context': '/etc'},
                   {'run_id': 'saved', 'protein': PROTEIN, 'new_source': True},
                   {'run_id': 'saved', 'protein': PROTEIN, 'limit': 26},
                   {'run_id': 'saved', 'protein': PROTEIN, 'offset': True},
                   {'run_id': 'missing', 'protein': PROTEIN}]
        for body in invalid:
            with self.subTest(body=body): self.error(400, body)

    def test_symlink_run_cannot_escape_saved_workspace_scope(self):
        (self.root / 'alias').symlink_to(self.folder, target_is_directory=True)
        self.read.reset_mock()
        self.error(400, {'run_id': 'alias', 'protein': PROTEIN})
        self.read.assert_not_called()

    def test_unconfigured_or_failed_source_is_explicit_without_a_fallback(self):
        self.graph['evidence_extension']['sources'].pop('goa')
        with patch('biograph_steward.client.PharosClient.execute', side_effect=AssertionError('No fallback')):
            result = self.error(400)
            self.assertIn('no verified native GO', result['error'])
            self.read.side_effect = ValueError('Native publication cannot be verified.')
            result = self.error(400)
            self.assertIn('cannot be verified', result['error'])

    def test_retained_read_only_workspace_can_query_native_sources(self):
        # Only transport dispatch is under test here; read_run's verified return
        # value is patched above. The marker exercises the immutable-view gate.
        (self.folder / 'qualified_workspace.json').write_text('{}')
        before = self.inventory()
        with self.request() as response:
            answer = json.loads(response.read())
        self.assertEqual(answer['summary']['matching_concepts'], 3)
        self.assertTrue(answer['read_only'])
        self.assertEqual(self.inventory(), before)

    def test_report_includes_compact_existing_tab_controls_and_source_guard_script(self):
        html = report_html(self.graph)
        for text in ('id="nativeGoaPanel"', 'Recovered native GO annotations',
                     'id="nativeGoaView"', '/api/native-go-question',
                     'function setupNativeGoa()', 'setupNativeGoa();',
                     'No accepted native GO annotation', 'Inspect source and recorded conditions'):
            self.assertIn(text, html)
        self.assertNotIn('__GUIDED_SCRIPT__', html)


if __name__ == '__main__':
    unittest.main()
