"""An actual authenticated read-only route serves the sanitized v3 component."""
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
from biograph_steward.file_utils import sha
from biograph_steward.webapp import create_server
from test_scientific_assessment import fixtures
from test_scientific_assessment_grounding import grounding_fixture


class ScientificAssessmentGroundingHttpTests(unittest.TestCase):
    def test_v3_routes_expose_only_aggregate_and_never_execute_the_component(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp).resolve()
            paths, pins = fixtures(root / 'base')
            _, aggregate, _ = grounding_fixture(root / 'component')
            module.publish(paths, root / 'assessment', expected_source_pins=pins,
                grounding_report=aggregate, expected_grounding_pin=sha(aggregate))
            before = {p.relative_to(root).as_posix(): p.read_bytes() for p in root.rglob('*') if p.is_file()}
            server = create_server(0, root, access_token='invented-grounding-token-1234')
            server.RequestHandlerClass.log_message = lambda *args: None
            thread = threading.Thread(target=server.serve_forever, daemon=True)
            thread.start()
            try:
                opener = build_opener(ProxyHandler({}))
                base = 'http://127.0.0.1:' + str(server.server_port)
                def get(path, token=True):
                    return opener.open(Request(base + path, headers={
                        'Authorization': 'Bearer invented-grounding-token-1234'} if token else {}), timeout=10)
                with ExitStack() as stack:
                    for name in ('biograph_steward.client.PharosClient.execute',
                                 'biograph_steward.model_transport.JSONModelClient.generate',
                                 'tools.grounding_claims.evaluate.evaluate'):
                        stack.enter_context(patch(name, side_effect=AssertionError('saved aggregates only')))
                    with get('/api/scientific-assessments') as response:
                        self.assertEqual(json.loads(response.read())['assessments'][0]['id'], 'assessment')
                    with get('/api/scientific-assessment/assessment') as response:
                        self.assertIsNone(json.loads(response.read())['summary']['whole_graph_scientific_precision'])
                    with get('/api/scientific-assessment/assessment/report') as response:
                        self.assertIn(b'Expert-curator grounding triage', response.read())
                    with get('/api/scientific-assessment/assessment/files/sources/grounding.json') as response:
                        payload = response.read()
                        self.assertEqual(payload, aggregate.read_bytes())
                        self.assertNotIn(b'PRIVATE-', payload)
                        self.assertEqual(response.headers['X-Content-Type-Options'], 'nosniff')
                    for path, token, code in (
                        ('/api/scientific-assessment/assessment/files/sources/grounding.json', False, 401),
                        ('/api/scientific-assessment/assessment/files/sources/private_evaluator.json', True, 404),
                    ):
                        with self.assertRaises(HTTPError) as caught:
                            get(path, token)
                        self.assertEqual(caught.exception.code, code)
                        caught.exception.close()
            finally:
                server.shutdown(); server.server_close(); thread.join()
            self.assertEqual(before, {p.relative_to(root).as_posix(): p.read_bytes()
                for p in root.rglob('*') if p.is_file()})


if __name__ == '__main__':
    unittest.main()
