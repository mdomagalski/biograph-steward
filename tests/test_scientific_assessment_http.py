"""Authenticated, read-only aggregate assessment routes with no model/source calls."""
from contextlib import ExitStack
import json
from pathlib import Path
import tempfile
import threading
import unittest
from unittest.mock import patch
from urllib.error import HTTPError
from urllib.request import ProxyHandler, Request, build_opener

from biograph_steward import scientific_assessment
from biograph_steward.webapp import create_server, login_return_path
from test_scientific_assessment import fixtures


class ScientificAssessmentHttpTests(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory(); self.addCleanup(tmp.cleanup)
        self.root = Path(tmp.name).resolve()
        paths, pins = fixtures(self.root/'inputs')
        scientific_assessment.publish(paths, self.root/'assessment', expected_source_pins=pins)
        self.server = create_server(0, self.root, access_token='invented-assessment-token-1234')
        self.server.RequestHandlerClass.log_message = lambda *args: None
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True); self.thread.start()
        self.addCleanup(self.close)
        self.url = 'http://127.0.0.1:' + str(self.server.server_port)
        self.opener = build_opener(ProxyHandler({}))

    def close(self):
        self.server.shutdown(); self.server.server_close(); self.thread.join()

    def get(self, path, *, authenticated=True, html=False):
        headers = {'Authorization': 'Bearer invented-assessment-token-1234'} if authenticated else {}
        if html: headers['Accept'] = 'text/html'
        return self.opener.open(Request(self.url+path, headers=headers), timeout=10)

    def error(self, code, path, **kwargs):
        with self.assertRaises(HTTPError) as caught: self.get(path, **kwargs)
        self.assertEqual(caught.exception.code, code); caught.exception.close()

    def test_verified_aggregate_list_report_and_receipts_without_graph_or_model_work(self):
        before = {p.relative_to(self.root).as_posix(): p.read_bytes() for p in self.root.rglob('*') if p.is_file()}
        with ExitStack() as stack:
            for name in ('biograph_steward.reviews.read_run', 'biograph_steward.client.PharosClient.execute',
                         'biograph_steward.model_transport.JSONModelClient.generate'):
                stack.enter_context(patch(name, side_effect=AssertionError('Saved aggregates only')))
            with self.get('/api/scientific-assessments') as response:
                listed = json.loads(response.read())['assessments']
            self.assertEqual([x['id'] for x in listed], ['assessment'])
            with self.get('/api/scientific-assessment/assessment') as response:
                value = json.loads(response.read())
            self.assertIsNone(value['summary']['whole_graph_scientific_precision'])
            with self.get('/api/scientific-assessment/assessment/report') as response:
                self.assertIn('text/html', response.headers['Content-Type'])
                self.assertIn(b'Scientific assessment', response.read())
            for source in value['summary']['sources']:
                path = '/api/scientific-assessment/assessment/files/' + source['file']
                with self.get(path) as response:
                    self.assertEqual(response.read(), (self.root/'assessment'/source['file']).read_bytes())
                    self.assertEqual(response.headers['X-Content-Type-Options'], 'nosniff')
        self.assertEqual(before, {p.relative_to(self.root).as_posix(): p.read_bytes()
            for p in self.root.rglob('*') if p.is_file()})

    def test_authentication_and_narrow_report_return_path(self):
        report = '/api/scientific-assessment/assessment/report'
        self.error(401, '/api/scientific-assessments', authenticated=False)
        self.error(401, report, authenticated=False)
        with self.get(report, authenticated=False, html=True) as response:
            body = response.read().decode()
            self.assertIn('Sign in', body)
            self.assertIn(report, body)
        self.assertEqual(login_return_path(report), report)
        self.assertEqual(login_return_path('//example.org/api/scientific-assessment/assessment/report'), '/')

    def test_changed_source_and_unsupported_queries_are_rejected(self):
        self.error(400, '/api/scientific-assessments?run=other')
        self.error(400, '/api/scientific-assessment/assessment?new=true')
        self.error(404, '/api/scientific-assessment/assessment/files/private.txt')
        source = next((self.root/'assessment/sources').glob('*.json'))
        source.write_text('{}')
        self.error(400, '/api/scientific-assessment/assessment/report')


if __name__ == '__main__':
    unittest.main()
