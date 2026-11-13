"""Authenticated separate GO packet downloads, using invented source data."""
from io import BytesIO
import json
import unittest
from urllib.error import HTTPError
from urllib.request import Request
from zipfile import ZipFile

from biograph_steward import gold_packet
from biograph_steward.client import digest, write_json
from biograph_steward.go_context_export import ROOT, SOURCE_FILES
from biograph_steward.qualified_workspace import publish_workspace


class NativeGoExportHttpTests(unittest.TestCase):
    def setUp(self):
        from test_native_go_context_http import NativeGoContextHttpTests
        self.http = NativeGoContextHttpTests()
        self.http.setUp(); self.addCleanup(self.http.doCleanups)

    def request(self, *, body=None, auth=True, origin=None, headers=None):
        supplied = {'Content-Type': 'application/json', 'Accept-Encoding': 'gzip'}
        if auth:
            supplied['Authorization'] = 'Bearer '+self.http.token
        if origin:
            supplied['Origin'] = origin
        supplied.update(headers or {})
        value = body if body is not None else {'run_id': 'run', 'selection_id': self.http.selected['assertion_id']}
        request = Request(self.http.url+'/api/download-native-go-context',
                          json.dumps(value).encode(), supplied)
        with self.http.opener.open(request) as response:
            return response.headers, response.read()

    def test_separate_download_exact_inventory_headers_binding_and_source_immutability(self):
        before = self.http.inventory()
        headers, content = self.request()
        self.assertEqual(headers['Content-Type'], 'application/zip')
        self.assertIn('attachment; filename="native_go_context_qc_', headers['Content-Disposition'])
        self.assertEqual(headers['Cache-Control'], 'no-store')
        self.assertIsNone(headers['Content-Encoding'])
        self.assertEqual(int(headers['Content-Length']), len(content))
        with ZipFile(BytesIO(content)) as archive:
            self.assertEqual(set(archive.namelist()),
                {ROOT+'/'+name for name in SOURCE_FILES | {'manifest.json', 'README.txt'}})
            manifest = json.loads(archive.read(ROOT+'/manifest.json'))
            self.assertEqual(manifest['current_graph_sha256'], digest(self.http.graph))
            self.assertEqual(manifest['source_run'], 'run')
            self.assertEqual(manifest['selection_id'], self.http.selected['assertion_id'])
            for name in SOURCE_FILES:
                label, relative = name.split('/', 1)
                folder = self.http.context if label == 'context' else self.http.qc
                self.assertEqual(archive.read(ROOT+'/'+name), (folder/relative).read_bytes())
        self.assertEqual(self.http.inventory(), before)
        # The ordinary workspace ZIP stays a separate unchanged file scope.
        with self.http.opener.open(Request(self.http.url+'/api/download/run',
                headers={'Authorization': 'Bearer '+self.http.token})) as response:
            with ZipFile(BytesIO(response.read())) as archive:
                self.assertEqual(set(archive.namelist()),
                    {'run/'+p.relative_to(self.http.root/'run').as_posix()
                     for p in (self.http.root/'run').rglob('*') if p.is_file()})
                self.assertFalse(any('/context/' in name or '/qc/' in name for name in archive.namelist()))

    def test_auth_origin_json_and_exact_selection_options_fail_closed(self):
        for options, status in (({'auth': False}, 401),
                ({'origin': 'https://unrelated.invalid'}, 403),
                ({'headers': {'Content-Type': 'text/plain'}}, 415)):
            with self.subTest(options=options), self.assertRaises(HTTPError) as error:
                self.request(**options)
            self.assertEqual(error.exception.code, status); error.exception.close()
        non_go = next(row for row in self.http.graph['assertions'] if row['kind'] != 'go_annotation')
        for body in ({'run_id': '../run', 'selection_id': self.http.selected['id']},
                     {'run_id': 'run', 'selection_id': self.http.selected['id'], 'qc': '/etc'},
                     {'run_id': 'run', 'selection_id': non_go['id']},
                     {'run_id': 'run', 'selection_id': 'unknown'}):
            with self.subTest(body=body), self.assertRaises(HTTPError) as error:
                self.request(body=body)
            self.assertEqual(error.exception.code, 400); error.exception.close()

    def test_missing_either_configuration_returns_unavailable_not_partial_packet(self):
        for context, qc in ((None, None), (self.http.context, None), (None, self.http.qc)):
            self.http.stop(); self.http.start(context, qc)
            with self.subTest(context=context, qc=qc), self.assertRaises(HTTPError) as error:
                self.request()
            self.assertEqual(error.exception.code, 503)
            self.assertIn('not configured' if context is None else 'must be configured', error.exception.read().decode())
            error.exception.close()

    def test_tampered_and_mismatched_source_never_returns_an_archive(self):
        path = self.http.qc/'official_report.json'; original = path.read_bytes()
        path.write_bytes(original+b' ')
        with self.assertRaises(HTTPError) as error:
            self.request()
        self.assertEqual(error.exception.code, 400)
        self.assertEqual(error.exception.headers['Content-Type'], 'application/json')
        error.exception.close(); path.write_bytes(original)
        self.http.fixture.reseal(lambda report: report.update(snapshot_sha256='f'*64))
        with self.assertRaises(HTTPError) as error:
            self.request()
        self.assertEqual(error.exception.code, 400)
        self.assertIn('snapshot differs', error.exception.read().decode()); error.exception.close()

    def test_qualified_workspace_is_downloadable_without_enabling_mutation_routes(self):
        packet = self.http.fixture.packet
        decisions = json.loads((packet/'decisions.template.json').read_text())
        decisions.update(method='Invented all-retained test', actor='Invented test actor')
        for row in decisions['decisions']:
            row.update(decision='abstain', reason='Invented software test; no biological judgment')
        write_json(self.http.root/'decisions.json', decisions)
        gold_packet.save_decisions(packet, self.http.root/'decisions.json', self.http.root/'retained')
        publish_workspace(self.http.root/'retained', self.http.root/'qualified')
        before = self.http.inventory()
        headers, content = self.request(body={'run_id': 'qualified',
            'selection_id': self.http.selected['assertion_id']})
        self.assertEqual(headers['Content-Type'], 'application/zip')
        with ZipFile(BytesIO(content)) as archive:
            manifest = json.loads(archive.read(ROOT+'/manifest.json'))
            self.assertEqual(manifest['source_run'], 'qualified')
            self.assertNotEqual(manifest['current_graph_sha256'], manifest['original_graph_sha256'])
        self.assertEqual(self.http.inventory(), before)
        with self.assertRaises(HTTPError) as error:
            self.http.request('/api/review', {'run_id': 'qualified'})
        self.assertEqual(error.exception.code, 400)
        self.assertIn('read-only', error.exception.read().decode()); error.exception.close()


if __name__ == '__main__':
    unittest.main()
