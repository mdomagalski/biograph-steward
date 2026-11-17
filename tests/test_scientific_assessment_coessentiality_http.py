"""Read-only authenticated v1/v2 routes; no experimental scoring or retrieval."""
from contextlib import ExitStack
import json
from pathlib import Path
import tempfile
import threading
import unittest
from unittest.mock import patch
from urllib.error import HTTPError
from urllib.request import ProxyHandler, Request, build_opener

from biograph_steward import scientific_assessment as module
from biograph_steward.webapp import create_server
from test_scientific_assessment import fixtures
from test_scientific_assessment_coessentiality import coessentiality_fixtures


class ScientificAssessmentCoessentialityHttpTests(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.root = Path(tmp.name).resolve()
        paths, pins = fixtures(self.root / 'base')
        extra, extra_pins = coessentiality_fixtures(self.root / 'extra', paths, pins)
        module.publish(paths, self.root / 'legacy', expected_source_pins=pins)
        module.publish(paths, self.root / 'assessment_v2', expected_source_pins=pins,
            coessentiality_reports=extra, expected_coessentiality_pins=extra_pins)
        self.server = create_server(0, self.root, access_token='invented-coess-token-1234')
        self.server.RequestHandlerClass.log_message = lambda *args: None
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()
        self.addCleanup(self.close)
        self.url = 'http://127.0.0.1:' + str(self.server.server_port)
        self.opener = build_opener(ProxyHandler({}))

    def close(self):
        self.server.shutdown()
        self.server.server_close()
        self.thread.join()

    def get(self, path, *, authenticated=True):
        headers = {'Authorization': 'Bearer invented-coess-token-1234'} if authenticated else {}
        return self.opener.open(Request(self.url + path, headers=headers), timeout=10)

    def assert_error(self, path, code=400, **kwargs):
        with self.assertRaises(HTTPError) as caught:
            self.get(path, **kwargs)
        self.assertEqual(caught.exception.code, code)
        caught.exception.close()

    def test_actual_v1_v2_routes_serve_bound_summary_and_all_aggregate_proofs_readonly(self):
        before = {p.relative_to(self.root).as_posix(): p.read_bytes()
                  for p in self.root.rglob('*') if p.is_file()}
        with ExitStack() as stack:
            for name in ('biograph_steward.reviews.read_run', 'biograph_steward.client.PharosClient.execute',
                         'biograph_steward.model_transport.JSONModelClient.generate'):
                stack.enter_context(patch(name, side_effect=AssertionError('Saved aggregates only')))
            with self.get('/api/scientific-assessments') as response:
                listed = json.loads(response.read())['assessments']
            self.assertEqual({x['id'] for x in listed}, {'legacy', 'assessment_v2'})
            for name, expected in [('legacy', module.FORMAT), ('assessment_v2', module.FORMAT_V2)]:
                with self.get('/api/scientific-assessment/' + name) as response:
                    self.assertEqual(json.loads(response.read())['summary']['format'], expected + '.summary')
            with self.get('/api/scientific-assessment/assessment_v2/report') as response:
                self.assertIn(b'did not show a consistent advantage', response.read())
            summary = next(x['summary'] for x in listed if x['id'] == 'assessment_v2')
            for item in summary['sources']:
                with self.get('/api/scientific-assessment/assessment_v2/files/' + item['file']) as response:
                    self.assertEqual(response.read(), (self.root / 'assessment_v2' / item['file']).read_bytes())
        self.assertEqual(before, {p.relative_to(self.root).as_posix(): p.read_bytes()
                                  for p in self.root.rglob('*') if p.is_file()})

    def test_optional_aggregate_proofs_are_authenticated_and_changes_fail_closed(self):
        path = '/api/scientific-assessment/assessment_v2/files/sources/coess_curves.json'
        self.assert_error(path, 401, authenticated=False)
        self.assert_error(path + '?rerun=true')
        self.assert_error('/api/scientific-assessment/assessment_v2/files/native_pair_values.jsonl', 404)
        (self.root / 'assessment_v2/sources/coess_controls.json').write_text('{}')
        self.assert_error('/api/scientific-assessment/assessment_v2')
        self.assert_error('/api/scientific-assessment/assessment_v2/report')
        self.assert_error(path)


if __name__ == '__main__':
    unittest.main()
