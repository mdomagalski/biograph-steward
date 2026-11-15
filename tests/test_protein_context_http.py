"""Saved protein context uses existing auth, canonical graph replay and source pins."""
import json
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
from protein_context_fixtures import write_packet
from test_normalization import fixture


class ProteinContextHTTP(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory(); self.addCleanup(temp.cleanup)
        self.root = Path(temp.name).resolve()
        self.graph = save_run(fixture(), self.root / 'saved')
        self.assertion = next(a for a in self.graph['assertions'] if a['kind'] == 'go_annotation')
        self.protein = self.assertion['subject']
        self.packet = write_packet(self.root / 'context', proteins=[self.protein])
        self.body = {'run_id': 'saved', 'selection_id': self.assertion['id'], 'protein': self.protein}
        self.server = create_server(0, self.root, access_token='invented-protein-context-token',
                                    go_context_dir=self.root / 'missing_native_go')
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True); self.thread.start()
        self.url = 'http://127.0.0.1:' + str(self.server.server_port)
        self.opener = build_opener(ProxyHandler({}))
        self.before = self.files()

    def tearDown(self):
        self.server.shutdown(); self.server.server_close(); self.thread.join()

    def files(self):
        return {p.relative_to(self.root).as_posix(): p.read_bytes() for p in self.root.rglob('*') if p.is_file()}

    def request(self, route='/api/protein-context', body=None, *, auth=True, origin=None):
        headers = {'Content-Type': 'application/json'}
        if auth: headers['Authorization'] = 'Bearer invented-protein-context-token'
        if origin: headers['Origin'] = origin
        payload = self.body if body is None else body
        with self.opener.open(Request(self.url + route, json.dumps(payload).encode(), headers)) as response:
            self.assertEqual(response.headers['Cache-Control'], 'no-store')
            return json.loads(response.read())

    def test_read_is_source_bound_without_network_writes_or_model_calls(self):
        with patch('biograph_steward.client.PharosClient.execute', side_effect=AssertionError('No retrieval')):
            result = self.request()
        self.assertEqual(result['context_manifest_sha256'], self.packet.pin)
        self.assertEqual(result['protein'], self.protein)
        self.assertEqual(result['source_run'], 'saved')
        self.assertEqual(result['snapshot_sha256'], self.graph['snapshot_sha256'])
        self.assertEqual(result['content_sha256'], digest({k: v for k, v in result.items() if k != 'content_sha256'}))
        self.assertTrue(result['read_only']); self.assertFalse(result['source_graph_changed'])
        self.assertEqual((result['source_fetches'], result['model_calls']), (0, 0))
        self.assertEqual(self.files(), self.before)

    def test_failed_optional_go_verification_does_not_hide_verified_sequence_context(self):
        with patch('biograph_steward.go_context_inspection.inspect_go_selection', side_effect=ValueError('Missing proof')):
            result = self.request()
        self.assertTrue(result['matches'])
        self.assertTrue(any('GOA source could not be verified' in warning for warning in result['warnings']))
        self.assertEqual(result['goa_lineage']['records'], [])

    def test_guide_exposes_only_registered_exact_selected_proteins(self):
        result = self.request('/api/inspect-source', {'run_id': 'saved', 'selection_id': self.assertion['id']})
        metadata = result['protein_context']
        self.assertTrue(metadata['eligible'])
        self.assertEqual(metadata['proteins'][0]['protein'], self.protein)
        self.assertEqual(metadata['proteins'][0]['manifest_sha256'], self.packet.pin)

    def test_corrupt_optional_packet_is_explicit_and_original_guide_survives(self):
        source = self.packet.folder / self.packet.manifest['proteins'][0]['pharos_file']
        source.write_text('{}')
        result = self.request('/api/inspect-source', {'run_id': 'saved', 'selection_id': self.assertion['id']})
        self.assertEqual(result['protein_context']['status'], 'unverifiable_saved_context')
        self.assertEqual(result['selection']['id'], self.assertion['id'])
        with self.assertRaises(HTTPError) as exc: self.request()
        self.assertEqual(exc.exception.code, 400); exc.exception.close()

    def test_auth_origin_exact_options_endpoint_and_isoform_scope(self):
        with self.assertRaises(HTTPError) as exc: self.request(auth=False)
        self.assertEqual(exc.exception.code, 401); exc.exception.close()
        with self.assertRaises(HTTPError) as exc: self.request(origin='https://unrelated.example')
        self.assertEqual(exc.exception.code, 403); exc.exception.close()
        for altered in ({**self.body, 'run_id': '../saved'}, {**self.body, 'selection_id': 'missing'},
                        {**self.body, 'protein': self.protein + '-2'}, {**self.body, 'protein': 'UniProtKB:Q8TE23'},
                        {**self.body, 'fetch': True}, {k: v for k, v in self.body.items() if k != 'protein'}):
            with self.subTest(altered=altered), self.assertRaises(HTTPError) as exc: self.request(body=altered)
            self.assertEqual(exc.exception.code, 400); exc.exception.close()

    def test_report_embeds_protein_module_before_navigation(self):
        output = report_html(self.graph)
        self.assertLess(output.index('window.ProteinContext ='), output.index('function renderSourceGuide(result)'))
        self.assertIn('Protein sequence & domain context', output)


if __name__ == '__main__': unittest.main()
