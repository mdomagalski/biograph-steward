"""Invented-source regression for standalone pathway export byte binding.

The native fixture supplies a synthetic in-memory source through the two source
loaders. The real query reconstruction, saved-file verifier and GET/ZIP routes
execute unchanged. No biological evidence or production source is modified.
"""
from io import BytesIO
import json
import threading
import unittest
from unittest.mock import patch
from urllib.error import HTTPError
from urllib.request import ProxyHandler, build_opener
from zipfile import ZipFile

from biograph_steward.questions import save_answer, verify_pathway_files
from biograph_steward.webapp import create_server
import test_native_pathway_question as native_fixture


class PathwaySavedExportTests(unittest.TestCase):
    def setUp(self):
        native_fixture.NativePathwayQuestionTests.setUp(self)
        self.answer = native_fixture.NativePathwayQuestionTests.question(self)
        # Isolate the existing synthetic archive/graph reader fixture, while
        # retaining real deterministic source-answer reconstruction on reopen.
        for target, value in (
            ('biograph_steward.reviews.read_run', (None, [], self.graph)),
            ('biograph_steward.qualified_workspace.read_pathway_history', self.packet),
        ):
            mocked = patch(target, return_value=value)
            mocked.start()
            self.addCleanup(mocked.stop)
        self.server = create_server(0, self.root)
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

    def saved(self, name):
        folder = self.root / name
        save_answer(self.answer, folder)
        return folder

    def assert_rejected_by_both_routes(self, name):
        for prefix in ('/api/question/', '/api/download/'):
            with self.subTest(route=prefix, artifact=name):
                with self.assertRaises(HTTPError) as caught:
                    self.opener.open(self.url + prefix + name, timeout=10)
                self.assertEqual(caught.exception.code, 400)
                message = json.loads(caught.exception.read())['error']
                self.assertIn('Qualified pathway', message)
                caught.exception.close()

    def test_unchanged_get_and_zip_preserve_native_and_grouped_evidence(self):
        folder = self.saved('unchanged')
        before = {p.relative_to(folder).as_posix(): p.read_bytes()
                  for p in folder.rglob('*') if p.is_file()}
        verify_pathway_files(self.answer, folder)
        with self.opener.open(self.url + '/api/question/unchanged') as response:
            self.assertEqual(json.loads(response.read())['answer'], self.answer)
        with self.opener.open(self.url + '/api/download/unchanged') as response:
            archive = ZipFile(BytesIO(response.read()))
        self.assertEqual({name.removeprefix('unchanged/'): archive.read(name)
                          for name in archive.namelist()}, before)
        self.assertEqual(before, {p.relative_to(folder).as_posix(): p.read_bytes()
                                  for p in folder.rglob('*') if p.is_file()})

    def test_changed_native_groups_proof_and_readable_exports_fail_get_and_download(self):
        names = ['historical_models/WP1_r10.gpml', 'source_context_groups.json',
                 'historical_models/provenance.json', 'qualified_view.json',
                 'summary.txt', 'report.html', 'paths.tsv']
        for number, relative in enumerate(names):
            name = 'changed_' + str(number)
            folder = self.saved(name)
            (folder / relative).write_bytes(b'changed isolated software fixture')
            self.assert_rejected_by_both_routes(name)

    def test_missing_native_or_proof_and_additional_files_fail_get_and_download(self):
        for number, relative in enumerate(('historical_models/WP1_r10.gpml',
                                           'historical_models/provenance.json')):
            name = 'missing_' + str(number)
            folder = self.saved(name)
            (folder / relative).unlink()
            self.assert_rejected_by_both_routes(name)
        folder = self.saved('extra_file')
        (folder / 'historical_models/unbound.gpml').write_bytes(b'unbound source')
        self.assert_rejected_by_both_routes('extra_file')
        folder = self.saved('extra_directory')
        (folder / 'unbound').mkdir()
        self.assert_rejected_by_both_routes('extra_directory')

    def test_identical_native_bytes_via_symlink_fail_get_and_download(self):
        folder = self.saved('symlink')
        model = folder / 'historical_models/WP1_r10.gpml'
        model.unlink()
        model.symlink_to(self.native / 'models/WP1_r10.gpml')
        self.assert_rejected_by_both_routes('symlink')


if __name__ == '__main__':
    unittest.main()
