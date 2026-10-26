"""Authenticated construction, saved-work reopening and publication downloads."""
from io import BytesIO
import json
from pathlib import Path
import tempfile
import threading
import unittest
from unittest.mock import patch
from urllib.error import HTTPError
from urllib.request import Request, ProxyHandler, build_opener
from zipfile import ZipFile

from biograph_steward.client import PharosClient
from biograph_steward.webapp import create_server
from test_construction import request_fixture
from test_pharos_inventory import InventoryAPI


class ConstructionHttpTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.server = create_server(0, self.root, access_token='synthetic-construction-test-token')
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()
        self.url = 'http://127.0.0.1:' + str(self.server.server_port)
        self.api = InventoryAPI()

    def tearDown(self):
        self.server.shutdown()
        self.server.server_close()
        self.thread.join()
        self.temp.cleanup()

    def request(self, path, body=None, auth=True):
        headers = {'Authorization': 'Bearer synthetic-construction-test-token'} if auth else {}
        if body is not None:
            headers['Content-Type'] = 'application/json'
        return build_opener(ProxyHandler({})).open(Request(
            self.url + path, data=json.dumps(body).encode() if body is not None else None,
            headers=headers))

    def construct(self, **changes):
        body = {'mode': 'live', **request_fixture(), **changes}
        with patch('biograph_steward.webapp.PharosClient', return_value=PharosClient(transport=self.api)):
            with self.request('/api/construct', body) as response:
                return json.loads(response.read())

    def test_live_construction_reopens_as_saved_work_and_downloads_bound_material(self):
        result = self.construct()
        run_id = result['run_id']
        folder = self.root / run_id
        self.assertEqual(result['question_id'], run_id)
        self.assertTrue(result['question']['citations'])
        original = {p.relative_to(folder): p.read_bytes() for p in folder.rglob('*') if p.is_file()}
        with self.request('/api/run/' + run_id) as response:
            self.assertEqual(json.loads(response.read())['graph'], result['graph'])
        with self.request('/api/question/' + run_id) as response:
            self.assertEqual(json.loads(response.read())['answer'], result['question'])
        with self.request('/api/workspaces') as response:
            workspaces = json.loads(response.read())
        entry = next(r for r in workspaces['runs'] if r['run_id'] == run_id)
        self.assertTrue(any(q['question_id'] == run_id for q in entry['questions']))
        with self.request('/api/download/' + run_id) as response:
            with ZipFile(BytesIO(response.read())) as archive:
                names = archive.namelist()
                for expected in ['snapshot.json', 'graph.json', 'question.json',
                                 'construction_receipt.json', 'answer/report.html']:
                    self.assertTrue(any(n.endswith('/' + expected) or n == expected for n in names), expected)
                snapshot_name = next(n for n in names if n == run_id + '/snapshot.json' or n == 'snapshot.json')
                self.assertEqual(json.loads(archive.read(snapshot_name)),
                                 json.loads((folder / 'snapshot.json').read_text()))
        self.assertEqual(original, {p.relative_to(folder): p.read_bytes()
                                    for p in folder.rglob('*') if p.is_file()})

    def test_auth_and_invalid_scope_fail_before_retrieval(self):
        with self.assertRaises(HTTPError) as error:
            self.request('/api/construct', {'mode': 'live', **request_fixture()}, auth=False)
        self.assertEqual(error.exception.code, 401)
        error.exception.close()
        bad = [
            {'accessions': ['P04637', 'P04637']}, {'accessions': []},
            {'focus_uniprot': 'P01116'}, {'profile': 'whole_database'},
            {'mode': 'anything'}, {'refresh': 1}, {'refresh': 'yes'},
            {'source_file': '/tmp/arbitrary.json'}, {'relations': ['causes']},
            {'endpoint': 'https://other.example/graphql'},
        ]
        for changes in bad:
            with self.subTest(changes=changes), self.assertRaises(HTTPError) as error:
                self.construct(**changes)
            self.assertEqual(error.exception.code, 400)
            error.exception.close()
        self.assertEqual(self.api.calls, [])
        self.assertFalse(any(self.root.iterdir()))

    def test_demo_is_explicitly_synthetic_and_performs_no_http(self):
        with patch.object(PharosClient, '_http', side_effect=AssertionError('Demo used network')):
            with self.request('/api/construct', {'mode': 'demo'}) as response:
                result = json.loads(response.read())
        self.assertEqual(result['graph']['data_kind'], 'synthetic_demo')
        self.assertEqual(result['question']['data_kind'], 'synthetic_demo')
        self.assertTrue(result['question']['summary'])

    def test_changed_or_missing_publication_receipt_blocks_reopening_and_download(self):
        result = self.construct()
        folder = self.root / result['run_id']
        path = folder / 'construction_receipt.json'
        original = path.read_bytes()
        for action in ['changed', 'missing']:
            with self.subTest(action=action):
                if action == 'changed':
                    path.write_text('{}')
                else:
                    path.unlink()
                for route in ['/api/run/', '/api/download/', '/api/question/']:
                    with self.assertRaises(HTTPError) as error:
                        self.request(route + result['run_id'])
                    self.assertEqual(error.exception.code, 400)
                    error.exception.close()
                path.write_bytes(original)


if __name__ == '__main__':
    unittest.main()
