"""Authenticated assay attachment and safe access to preserved source data."""
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

from biograph_steward.graph import save_run
from biograph_steward.webapp import create_server
from test_assay_attachment import cohort_snapshot, make_publication


class AssayHttpTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name).resolve()
        self.source = self.root / 'cohort'
        self.publication = self.root / 'publication'
        save_run(cohort_snapshot(), self.source)
        self.manifest = make_publication(self.publication)
        self.server = create_server(0, self.root, access_token='synthetic-assay-http-test-token')
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()
        self.url = 'http://127.0.0.1:' + str(self.server.server_port)

    def tearDown(self):
        self.server.shutdown()
        self.server.server_close()
        self.thread.join()
        self.temp.cleanup()

    def request(self, path, body=None, auth=True):
        headers = {'Authorization': 'Bearer synthetic-assay-http-test-token'} if auth else {}
        if body is not None:
            headers['Content-Type'] = 'application/json'
        return build_opener(ProxyHandler({})).open(Request(
            self.url + path, data=json.dumps(body).encode() if body is not None else None,
            headers=headers))

    def assert_http_error(self, status, path, body=None, auth=True):
        with self.assertRaises(HTTPError) as error:
            self.request(path, body, auth)
        self.assertEqual(error.exception.code, status)
        error.exception.close()

    def attach(self):
        with self.request('/api/assay-attach', {
                'run_id': self.source.name, 'publication_id': self.publication.name}) as response:
            return json.loads(response.read())

    def test_publication_listing_is_authenticated_and_labels_metadata_only(self):
        self.assert_http_error(401, '/api/assay-publications', auth=False)
        (self.root / 'alias').symlink_to(self.publication, target_is_directory=True)
        invalid = self.root / 'invalid'
        invalid.mkdir()
        (invalid / 'publication.json').write_text('{}')
        with self.request('/api/assay-publications') as response:
            result = json.loads(response.read())
        self.assertEqual(result['publications'], [{
            'publication_id': self.publication.name,
            'publication_sha256': self.manifest['content_sha256']}])
        self.assertIn('metadata only', result['verification'])

    def test_attach_reopen_and_download_preserve_original_source_bytes(self):
        originals = {p.relative_to(self.publication).as_posix(): p.read_bytes()
                     for p in self.publication.rglob('*') if p.is_file()}
        source_before = {p.relative_to(self.source).as_posix(): p.read_bytes()
                         for p in self.source.rglob('*') if p.is_file()}
        result = self.attach()
        run_id = result['run_id']
        self.assertNotEqual(run_id, self.source.name)
        self.assertGreater(result['graph']['assay_evidence']['selected_observations'], 0)
        with self.request('/api/run/' + run_id) as response:
            self.assertEqual(json.loads(response.read())['graph'], result['graph'])
        with self.request('/api/download/' + run_id) as response:
            self.assertEqual(response.headers.get_content_type(), 'application/zip')
            with ZipFile(BytesIO(response.read())) as archive:
                self.assertIn(run_id + '/assay_attachment.json', archive.namelist())
                for name, raw in originals.items():
                    self.assertEqual(archive.read(run_id + '/assay_source/' + name), raw)
        self.assertEqual(source_before, {p.relative_to(self.source).as_posix(): p.read_bytes()
                         for p in self.source.rglob('*') if p.is_file()})
        self.assertEqual(originals, {p.relative_to(self.publication).as_posix(): p.read_bytes()
                         for p in self.publication.rglob('*') if p.is_file()})

    def test_sources_download_as_data_with_attachment_filename(self):
        run_id = self.attach()['run_id']
        for relative, expected_type in (
                ('publication.json', 'application/json'),
                ('evidence.json', 'application/json'),
                ('index.html', 'text/plain'),
                ('source/freeze/source/panel.tsv', 'text/plain')):
            with self.subTest(relative=relative):
                path = '/api/assay-source/' + run_id + '/' + relative
                self.assert_http_error(401, path, auth=False)
                with self.request(path) as response:
                    self.assertEqual(response.headers.get_content_type(), expected_type)
                    self.assertEqual(response.headers['Content-Disposition'],
                                     'attachment; filename="' + Path(relative).name + '"')
                    self.assertEqual(response.headers['X-Content-Type-Options'], 'nosniff')
                    self.assertEqual(response.read(), (self.publication / relative).read_bytes())

    def test_auth_invalid_ids_and_source_aliases_fail_before_attachment(self):
        valid = {'run_id': self.source.name, 'publication_id': self.publication.name}
        (self.root / 'alias').symlink_to(self.publication, target_is_directory=True)
        bad = [
            {}, {**valid, 'source_file': '/tmp/external'},
            {**valid, 'run_id': '../cohort'}, {**valid, 'publication_id': '../publication'},
            {**valid, 'run_id': 1}, {**valid, 'publication_id': None},
            {**valid, 'run_id': 'x' * 81}, {**valid, 'publication_id': 'missing'},
            {**valid, 'publication_id': 'alias'},
        ]
        with patch('biograph_steward.assay_attachment.attach_assay') as attach:
            self.assert_http_error(401, '/api/assay-attach', valid, auth=False)
            for body in bad:
                with self.subTest(body=body):
                    self.assert_http_error(400, '/api/assay-attach', body)
            attach.assert_not_called()
        self.assertFalse(any(p.name.startswith('assay_') for p in self.root.iterdir()))

    def test_source_path_traversal_and_symlinks_are_rejected(self):
        run_id = self.attach()['run_id']
        for relative in ('../snapshot.json', '%2e%2e/snapshot.json',
                         '/snapshot.json', 'source/../../snapshot.json', 'not-published.txt'):
            with self.subTest(relative=relative):
                self.assert_http_error(400, '/api/assay-source/' + run_id + '/' + relative)
        alias = self.root / 'attached_alias'
        alias.symlink_to(self.root / run_id, target_is_directory=True)
        self.assert_http_error(400, '/api/assay-source/attached_alias/publication.json')
        source = self.root / run_id / 'assay_source' / 'source/freeze/source/panel.tsv'
        source.unlink()
        source.symlink_to(self.publication / 'source/freeze/source/panel.tsv')
        self.assert_http_error(400, '/api/assay-source/' + run_id + '/source/freeze/source/panel.tsv')
        self.assert_http_error(400, '/api/download/' + run_id)

    def test_preserved_source_tamper_blocks_reopen_download_and_source_access(self):
        run_id = self.attach()['run_id']
        source = self.root / run_id / 'assay_source' / 'source/freeze/source/panel.tsv'
        source.write_bytes(source.read_bytes() + b'changed')
        for route in ('/api/run/' + run_id, '/api/download/' + run_id,
                      '/api/assay-source/' + run_id + '/publication.json'):
            with self.subTest(route=route):
                self.assert_http_error(400, route)


if __name__ == '__main__':
    unittest.main()
