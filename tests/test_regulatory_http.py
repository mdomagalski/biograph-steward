"""Authenticated source questions must remain read-only and source bound."""
from copy import deepcopy
from contextlib import redirect_stdout
from io import StringIO
import json
from pathlib import Path
import tempfile
import threading
import unittest
from unittest.mock import patch
from urllib.error import HTTPError
from urllib.request import Request, ProxyHandler, build_opener

from biograph_steward.__main__ import main
from biograph_steward.webapp import create_server, report_html
from test_regulatory_questions import fixture


class RegulatoryHttpTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name).resolve()
        self.run = self.root / 'saved'; self.run.mkdir()
        self.graph = fixture()
        self.read = patch('biograph_steward.reviews.read_run', return_value=({}, [], self.graph))
        self.read_mock = self.read.start(); self.addCleanup(self.read.stop)
        self.server = create_server(0, self.root, access_token='invented-regulatory-fixture-token')
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True); self.thread.start()
        self.url = 'http://127.0.0.1:' + str(self.server.server_port)
        self.opener = build_opener(ProxyHandler({}))

    def tearDown(self):
        self.server.shutdown(); self.server.server_close(); self.thread.join(); self.temp.cleanup()

    def request(self, body, *, auth=True):
        headers = {'Content-Type': 'application/json'}
        if auth:
            headers['Authorization'] = 'Bearer invented-regulatory-fixture-token'
        return self.opener.open(Request(self.url + '/api/regulatory-question', json.dumps(body).encode(), headers))

    def error(self, status, body, **options):
        with self.assertRaises(HTTPError) as caught:
            self.request(body, **options)
        self.assertEqual(caught.exception.code, status); caught.exception.close()

    def test_authentication_and_read_only_ordered_source_question(self):
        self.error(401, {'run_id': 'saved'}, auth=False)
        before = deepcopy(self.graph)
        with patch('biograph_steward.client.PharosClient.execute', side_effect=AssertionError('No source retrieval')):
            with self.request({'run_id': 'saved', 'direction': 'incoming'}) as response:
                answer = json.loads(response.read())
        self.assertEqual(answer['source_run'], 'saved')
        self.assertEqual(answer['summary']['direction_observations'], 2)
        self.assertEqual((answer['read_only'], answer['model_calls'], answer['source_fetches']), (True, 0, 0))
        self.assertEqual(self.graph, before)
        self.assertEqual(list(self.run.iterdir()), [])
        self.read_mock.assert_called_with(self.run)

    def test_input_scope_and_broken_source_binding_fail(self):
        for option in ({'direction': 'activate'}, {'protein': 'EGFR'}, {'limit': 26},
                       {'new_source': True}, {'offset': -1}, {'run_id': '../saved'}):
            self.error(400, {'run_id': 'saved', **option})
        edge = next(e for e in self.graph['edges']
                    if e['subject'] == 'UniProtKB:P00533' and e['object'] != e['subject'])
        edge['subject'], edge['object'] = edge['object'], edge['subject']
        self.error(400, {'run_id': 'saved'})

    def test_cli_uses_the_same_saved_source_answer_and_new_output(self):
        out = self.root / 'answer'
        with redirect_stdout(StringIO()):
            code = main(['regulatory-question', '--run', str(self.run), '--direction', 'both', '--out', str(out)])
        self.assertEqual(code, 0)
        answer = json.loads((out / 'answer.json').read_text())
        self.assertEqual(answer['summary']['direction_observations'], 4)
        self.assertFalse(any(r['biologically_validated'] for r in answer['records']))

    def test_navigation_and_context_use_existing_evidence_workspace(self):
        html = report_html(self.graph)
        for value in ('id="biologicalView"', 'Regulation and experimental context',
                      'id="regulatoryPanel"', '/api/regulatory-question',
                      'Inspect claim, context and citation', 'Unreported'):
            self.assertIn(value, html)


if __name__ == '__main__':
    unittest.main()
