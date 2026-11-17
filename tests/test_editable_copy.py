"""Prepared complete-workspace downloads preserve the shared site's read-only scope."""
from contextlib import ExitStack, contextmanager
import hashlib
import json
import os
from pathlib import Path
import tempfile
import threading
import unittest
from unittest.mock import patch
from urllib.error import HTTPError
from urllib.request import Request, ProxyHandler, build_opener
from zipfile import ZipFile, ZIP_STORED

from biograph_steward import editable_copy
from biograph_steward.graph import save_run
from biograph_steward.questions import answer_question, save_answer
from biograph_steward.webapp import create_server
from test_questions import fixture


TOKEN = 'invented-editable-copy-check-token'


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


class EditableCopyTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name).resolve()
        self.runs = self.root / 'runs'; self.runs.mkdir()
        self.delivery = self.root / 'delivery'; self.delivery.mkdir()
        self.run = self.runs / 'source'
        self.graph = save_run(fixture(), self.run)
        answer = answer_question(self.graph, 'UniProtKB:P04637', view='candidates', source_run='source')
        save_answer(answer, self.runs / 'saved_question')
        self.archive = self.delivery / 'Example_Editable_Workspace.zip'
        with ZipFile(self.archive, 'w', compression=ZIP_STORED) as archive:
            archive.writestr('START_EDITABLE_LOCAL.py', '# Invented fixture launcher\n')
            archive.writestr('README.txt', 'Invented complete-source download fixture, not biological evidence.\n')
        manifest = json.loads((self.run / 'run_manifest.json').read_text())
        self.row = {'run_id': 'source', 'filename': self.archive.name,
                    'bytes': self.archive.stat().st_size, 'sha256': sha(self.archive),
                    'source_manifest_sha256': sha(self.run / 'run_manifest.json'),
                    'source_graph_sha256': sha(self.run / 'graph.json'),
                    'snapshot_sha256': manifest['snapshot_sha256'],
                    'question_id': 'saved_question',
                    'question_sha256': sha(self.runs / 'saved_question/question.json'),
                    'label': 'Editable source workspace (local copy)'}
        self.register()
        self.before = {str(p.relative_to(self.runs)): sha(p) for p in self.runs.rglob('*') if p.is_file()}

    def register(self):
        (self.delivery / 'index.json').write_text(json.dumps({'format': editable_copy.FORMAT,
                                                            'downloads': [self.row]}))

    def test_metadata_binds_original_source_and_question_without_network_or_replay(self):
        with ExitStack() as stack:
            guarded = [stack.enter_context(patch(name, side_effect=AssertionError('No source/model operation'))) for name in
                       ('biograph_steward.reviews.read_run', 'biograph_steward.webapp.PharosClient',
                        'biograph_steward.planning.configured_planner')]
            value = editable_copy.describe_editable_copy(self.delivery, self.runs, 'source')
            self.assertTrue(value['available'])
            self.assertEqual(value['source_graph_sha256'], self.row['source_graph_sha256'])
            self.assertEqual(value['download_url'], '/api/editable-copy/source/download')
            self.assertEqual(value['launch_command'], 'python3 START_EDITABLE_LOCAL.py')
            self.assertEqual(value['local_entry_query'], '?run=source&question=saved_question&view=ask')
            self.assertEqual(value['requires'], {'python': '3.10+', 'model': False, 'AWS': False})
            for guard in guarded:
                guard.assert_not_called()
        self.assertEqual(self.before, {str(p.relative_to(self.runs)): sha(p) for p in self.runs.rglob('*') if p.is_file()})

    def test_default_disabled_and_unregistered_workspace_have_no_download_link(self):
        for directory, identifier in ((None, 'source'), (self.delivery, 'other')):
            value = editable_copy.describe_editable_copy(directory, self.runs, identifier)
            self.assertFalse(value['available'])
            self.assertNotIn('download_url', value)
            with self.assertRaises(LookupError):
                with editable_copy.open_editable_copy(directory, self.runs, identifier):
                    self.fail('Unregistered download was opened.')

    def test_archive_same_size_tamper_and_source_drift_fail_closed(self):
        original = self.archive.read_bytes(); before = self.archive.stat()
        raw = bytearray(original); raw[-1] ^= 1; self.archive.write_bytes(raw)
        os.utime(self.archive, ns=(before.st_atime_ns, before.st_mtime_ns))
        with self.assertRaises(ValueError):
            editable_copy.describe_editable_copy(self.delivery, self.runs, 'source')
        self.archive.write_bytes(original)
        (self.run / 'graph.json').write_text('Changed source graph')
        with self.assertRaises(ValueError):
            editable_copy.describe_editable_copy(self.delivery, self.runs, 'source')

    def test_registration_rejects_path_escape_symlink_header_injection_and_qualified_view(self):
        old = dict(self.row)
        for filename in ('../outside.zip', '/outside.zip', 'file.zip\r\nX-Fake: yes'):
            self.row = {**old, 'filename': filename}; self.register()
            with self.assertRaises(ValueError):
                editable_copy.describe_editable_copy(self.delivery, self.runs, 'source')
        self.row = old; self.register()
        outside = self.root / 'outside.zip'; self.archive.rename(outside); self.archive.symlink_to(outside)
        with self.assertRaises(ValueError):
            editable_copy.describe_editable_copy(self.delivery, self.runs, 'source')
        self.archive.unlink(); outside.rename(self.archive)
        (self.run / 'qualified_workspace.json').write_text('{}')
        with self.assertRaises(ValueError):
            editable_copy.describe_editable_copy(self.delivery, self.runs, 'source')

    def test_question_for_another_source_and_duplicate_registrations_fail_closed(self):
        path = self.runs / 'saved_question/question.json'
        value = json.loads(path.read_text()); value['source_run'] = 'another_source'
        path.write_text(json.dumps(value)); self.row['question_sha256'] = sha(path); self.register()
        with self.assertRaises(ValueError):
            editable_copy.describe_editable_copy(self.delivery, self.runs, 'source')
        (self.delivery / 'index.json').write_text(json.dumps({'format': editable_copy.FORMAT,
                                                             'downloads': [self.row, self.row]}))
        with self.assertRaises(ValueError):
            editable_copy.describe_editable_copy(self.delivery, self.runs, 'source')

    def test_existing_human_review_mode_can_be_registered_as_a_new_source_copy(self):
        # review_run publishes human_review, not a guessed "review" mode.
        path = self.run / 'run_manifest.json'
        value = json.loads(path.read_text()); value['run_mode'] = 'human_review'
        path.write_text(json.dumps(value)); self.row['source_manifest_sha256'] = sha(path); self.register()
        self.assertTrue(editable_copy.describe_editable_copy(self.delivery, self.runs, 'source')['available'])

    def test_environment_configuration_is_read_once_by_server_and_http_stream_is_bounded(self):
        # A multi-block fixture catches accidental read_bytes()/read() archive
        # responses without requiring a giant real-data package in the tests.
        with ZipFile(self.archive, 'w', compression=ZIP_STORED) as archive:
            archive.writestr('fixture.bin', b'x' * (3 * 1024 * 1024 + 17))
        self.row.update(bytes=self.archive.stat().st_size, sha256=sha(self.archive)); self.register()
        with patch.dict(os.environ, {'BIOGRAPH_EDITABLE_COPY_DIR': str(self.delivery)}):
            server = create_server(0, self.runs, saved_data_only=True, access_token=TOKEN)
        thread = threading.Thread(target=server.serve_forever, daemon=True); thread.start()
        self.addCleanup(lambda: (server.shutdown(), server.server_close(), thread.join()))
        opener = build_opener(ProxyHandler({})); url = 'http://127.0.0.1:' + str(server.server_port)
        ordinary = editable_copy._ordinary

        class BoundedReader:
            def __init__(self, stream): self.stream = stream
            def __getattr__(self, name): return getattr(self.stream, name)
            def read(self, amount=-1):
                if amount < 0 or amount > 1024 * 1024:
                    raise AssertionError('The prepared archive must be read in bounded blocks.')
                return self.stream.read(amount)

        @contextmanager
        def bounded(path):
            with ordinary(path) as (stream, info):
                yield (BoundedReader(stream) if Path(path) == self.archive else stream), info

        with patch.object(editable_copy, '_ordinary', bounded):
            request = Request(url + '/api/editable-copy/source/download',
                              headers={'Authorization': 'Bearer ' + TOKEN}, method='HEAD')
            with opener.open(request) as response:
                self.assertEqual(response.status, 200)
                self.assertEqual(response.headers['Content-Length'], str(self.row['bytes']))
                self.assertEqual(response.headers['ETag'], '"' + self.row['sha256'] + '"')
                self.assertEqual(response.read(), b'')
            request = Request(url + '/api/editable-copy/source/download', headers={'Authorization': 'Bearer ' + TOKEN})
            with opener.open(request) as response:
                self.assertEqual(response.status, 200)
                self.assertEqual(response.headers['Content-Type'], 'application/zip')
                self.assertEqual(response.headers['Content-Length'], str(self.row['bytes']))
                self.assertEqual(response.headers['ETag'], '"' + self.row['sha256'] + '"')
                self.assertEqual(hashlib.sha256(response.read()).hexdigest(), self.row['sha256'])
        with self.assertRaises(HTTPError) as error:
            opener.open(url + '/api/editable-copy/source/download')
        self.assertEqual(error.exception.code, 401); error.exception.close()
        with patch('biograph_steward.reviews.read_run', side_effect=AssertionError('No review source read')):
            request = Request(url + '/api/review', b'{}', {'Authorization': 'Bearer ' + TOKEN,
                                                          'Content-Type': 'application/json'})
            with self.assertRaises(HTTPError) as error:
                opener.open(request)
            self.assertEqual(error.exception.code, 403); error.exception.close()
        self.archive.write_bytes(b'not a valid prepared archive')
        request = Request(url + '/api/editable-copy/source', headers={'Authorization': 'Bearer ' + TOKEN})
        with self.assertRaises(HTTPError) as error:
            opener.open(request)
        self.assertEqual(error.exception.code, 400)
        self.assertEqual(json.loads(error.exception.read())['error_code'], 'editable_copy_integrity_failed')
        error.exception.close()


if __name__ == '__main__':
    unittest.main()
