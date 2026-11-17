"""Authenticated read-only routes serve only bound aggregate publications."""
from contextlib import ExitStack
import json
from pathlib import Path
import tempfile
import threading
import unittest
from unittest.mock import patch
from urllib.error import HTTPError
from urllib.request import ProxyHandler, Request, build_opener

from biograph_steward.webapp import create_server
from test_biological_validation import make_comparison, edit_bound


class BiologicalComparisonHttpTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(); self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name).resolve()
        self.publication = make_comparison(self.root)
        self.before = self.files()
        self.server = create_server(0, self.root, access_token='invented-comparison-token')
        self.server.RequestHandlerClass.log_message = lambda *args: None
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True); self.thread.start()
        self.addCleanup(self.stop)
        self.url = 'http://127.0.0.1:' + str(self.server.server_port)
        self.opener = build_opener(ProxyHandler({}))
        self.prefix = '/api/biological-comparison/comparison'

    def stop(self):
        self.server.shutdown(); self.server.server_close(); self.thread.join()

    def files(self):
        return {p.relative_to(self.root).as_posix(): p.read_bytes()
                for p in self.root.rglob('*') if p.is_file() and not p.is_symlink()}

    def get(self, path, *, auth=True):
        headers = {'Authorization': 'Bearer invented-comparison-token'} if auth else {}
        return self.opener.open(Request(self.url + path, headers=headers), timeout=10)

    def get_json(self, path):
        with self.get(path) as response:
            self.assertEqual(response.headers['Cache-Control'], 'no-store')
            return json.loads(response.read())

    def error(self, status, path, **kwargs):
        with self.assertRaises(HTTPError) as caught: self.get(path, **kwargs)
        self.assertEqual(caught.exception.code, status); caught.exception.close()

    def test_list_summary_report_and_downloads_are_authenticated_and_read_only(self):
        with ExitStack() as stack:
            for target in ('biograph_steward.reviews.read_run', 'biograph_steward.client.PharosClient.execute',
                           'biograph_steward.model_transport.JSONModelClient.generate'):
                stack.enter_context(patch(target, side_effect=AssertionError('Read saved aggregates only')))
            self.assertEqual([r['id'] for r in self.get_json('/api/biological-comparisons')['comparisons']], ['comparison'])
            summary = self.get_json(self.prefix)
            self.assertEqual(summary['current_processed_reference_check']['strict']['primary_unique_eligible_positive_pairs'], 2)
            self.assertFalse(summary['scientific_accuracy_established'])
            for name, route in summary['downloads'].items():
                with self.get(route) as response:
                    self.assertEqual(response.read(), (self.publication / name).read_bytes())
                    self.assertEqual(response.headers['X-Content-Type-Options'], 'nosniff')
                    self.assertIn('attachment', response.headers['Content-Disposition'])
            with self.get(summary['report_url']) as response:
                self.assertIn(b'Same-study author-processed QC correction', response.read())
                self.assertIn('text/html', response.headers['Content-Type'])
        self.assertEqual(self.files(), self.before)
        for route in ('/api/biological-comparisons', self.prefix, self.prefix + '/report.html',
                      self.prefix + '/files/report.json'):
            self.error(401, route, auth=False)

    def test_invalid_queries_unknown_resources_and_symlink_runs_are_rejected(self):
        for route in ('/api/biological-comparisons?limit=1', self.prefix + '?write=true',
                      self.prefix + '/files/report.json?raw=true'):
            self.error(400, route)
        for name in ('raw.csv', 'publication.json', '../protocol.json', '%2e%2e%2fprotocol.json'):
            self.error(404, self.prefix + '/files/' + name)
        self.error(404, '/api/biological-comparison/missing')
        (self.root / 'alias').symlink_to(self.publication, target_is_directory=True)
        self.error(404, '/api/biological-comparison/alias')
        self.assertEqual([r['id'] for r in self.get_json('/api/biological-comparisons')['comparisons']], ['comparison'])

    def test_changed_semantic_binding_withholds_every_resource(self):
        edit_bound(self.publication, 'processed_qc_report.json', lambda d: d.update(new_winner_selected=True))
        for suffix in ('', '/report.html', '/files/report.json'):
            self.error(400, self.prefix + suffix)
        self.assertEqual(self.get_json('/api/biological-comparisons')['comparisons'], [])


if __name__ == '__main__':
    unittest.main()
