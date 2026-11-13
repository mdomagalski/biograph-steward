"""HTTP encoding compatibility; invented fixtures, no scientific source calls."""
import gzip
import hashlib
from http.client import HTTPConnection
from io import BytesIO
import json
from pathlib import Path
import tempfile
import threading
import unittest
from zipfile import ZipFile

from biograph_steward.client import digest
from biograph_steward.demo import demo_snapshot
from biograph_steward.graph import save_run
from biograph_steward.questions import answer_question, save_answer, verify_answer
from biograph_steward.webapp import create_server


class HttpJsonEncodingTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name).resolve()
        self.token = 'invented-utf8-transport-token-1234'
        self.unicode = {'scope': 'Invented transport fixture αβ',
            '資料': ['Café', '𝛼 🧬', '"quoted" \\ reverse solidus\nline\tend',
                   '<xml>β & "source"</xml>', '\x00\x1f\u2028\u2029'],
            'numbers': [0, -3, 0.25, 9007199254740993],
            'other': [True, False, None]}
        self.big = {'records': [self.unicode] * 700}
        self.surrogates = {'high': '\ud800', 'low': '\udfff',
            '\udc00key': 'native β with a lone surrogate: \ud800',
            'valid': 'α 🧬'}
        self.ascii = {'scope': 'invented ASCII fixture', 'values': [0, False, None]}
        self._start_server()
        self.addCleanup(self._stop_server)

    def _start_server(self):
        self.server = create_server(0, self.root, access_token=self.token)
        handler = self.server.RequestHandlerClass
        handler.log_message = lambda *args: None
        original = handler.do_GET
        fixtures = {'/fixture/unicode': self.unicode, '/fixture/large': self.big,
                    '/fixture/surrogates': self.surrogates, '/fixture/ascii': self.ascii}

        def fixture_get(request):
            if request.path in fixtures:
                if request.authenticate():
                    request.json_reply(fixtures[request.path])
            else:
                original(request)

        handler.do_GET = fixture_get
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()

    def _stop_server(self):
        self.server.shutdown()
        self.server.server_close()
        self.thread.join()

    def get(self, path, *, encoding=None, auth=True):
        connection = HTTPConnection('127.0.0.1', self.server.server_port, timeout=10)
        try:
            connection.putrequest('GET', path, skip_accept_encoding=True)
            if auth:
                connection.putheader('Authorization', 'Bearer ' + self.token)
            if encoding is not None:
                connection.putheader('Accept-Encoding', encoding)
            connection.endheaders()
            response = connection.getresponse()
            raw = response.read()
            headers = dict(response.getheaders())
            self.assertEqual(int(headers['Content-Length']), len(raw))
            self.assertEqual(headers['Cache-Control'], 'no-store')
            self.assertEqual(headers['X-Content-Type-Options'], 'nosniff')
            return response.status, headers, raw
        finally:
            connection.close()

    def test_native_unicode_astral_quoting_and_control_characters_roundtrip(self):
        status, headers, raw = self.get('/fixture/unicode')
        self.assertEqual(status, 200)
        self.assertEqual(headers['Content-Type'], 'application/json')
        self.assertFalse(raw.startswith(b'\xef\xbb\xbf'))
        self.assertIn('資料'.encode('utf-8'), raw)
        self.assertIn('𝛼 🧬'.encode('utf-8'), raw)
        self.assertNotIn(b'\\u03b1', raw)
        self.assertIn(b'\\n', raw)
        self.assertIn(b'\\u0000', raw)
        self.assertEqual(json.loads(raw.decode('utf-8')), self.unicode)
        legacy = json.dumps(self.unicode, ensure_ascii=True, allow_nan=False).encode('ascii')
        self.assertEqual(json.loads(raw), json.loads(legacy))
        self.assertEqual(digest(json.loads(raw)), digest(self.unicode))

    def test_large_utf8_identity_and_gzip_preserve_the_same_json(self):
        status, identity_headers, identity = self.get('/fixture/large')
        gzip_status, gzip_headers, coded = self.get('/fixture/large', encoding='gzip')
        self.assertEqual((status, gzip_status), (200, 200))
        self.assertGreater(len(identity), 65536)
        self.assertNotIn('Content-Encoding', identity_headers)
        self.assertEqual(gzip_headers['Content-Encoding'], 'gzip')
        self.assertEqual(identity_headers['Vary'], 'Accept-Encoding')
        self.assertEqual(gzip_headers['Vary'], 'Accept-Encoding')
        self.assertEqual(gzip.decompress(coded), identity)
        self.assertEqual(json.loads(identity), self.big)
        self.assertLess(len(identity), len(json.dumps(self.big, ensure_ascii=True).encode('ascii')))
        self.assertLess(len(coded), len(identity))

    def test_lone_surrogates_keep_the_prior_ascii_response(self):
        status, _, raw = self.get('/fixture/surrogates')
        self.assertEqual(status, 200)
        legacy = json.dumps(self.surrogates, ensure_ascii=True, allow_nan=False).encode('ascii')
        self.assertEqual(raw, legacy)
        self.assertEqual(json.loads(raw.decode('utf-8')), self.surrogates)
        self.assertIn(b'\\ud800', raw)
        self.assertIn(b'\\udfff', raw)
        self.assertNotIn(b'\xed\xa0\x80', raw)  # No invalid surrogatepass UTF-8.

    def test_ascii_response_and_authentication_keep_existing_behavior(self):
        status, _, raw = self.get('/fixture/ascii')
        self.assertEqual(status, 200)
        self.assertEqual(raw, json.dumps(self.ascii, ensure_ascii=True, allow_nan=False).encode('ascii'))
        status, headers, raw = self.get('/fixture/large', encoding='gzip', auth=False)
        self.assertEqual(status, 401)
        self.assertNotIn('Content-Encoding', headers)
        self.assertEqual(json.loads(raw)['error'], 'Sign in to the workspace to continue.')

    def test_nonfinite_values_still_fail_before_sending_a_response(self):
        class Unsent:
            def reply(self, *args, **kwargs):
                raise AssertionError('Invalid JSON must not be sent.')
        for value in (float('nan'), float('inf'), float('-inf')):
            with self.subTest(value=value), self.assertRaises(ValueError):
                self.server.RequestHandlerClass.json_reply(Unsent(), {'value': value})

    def test_existing_ascii_saved_question_reopens_after_restart_without_rewriting_exports(self):
        snapshot = demo_snapshot()
        for row in snapshot['targets']:
            if row.get('uniprot') == 'DEMO_PROTEIN_001':
                row['sym'] = 'DEMO_α'
                row['name'] = 'Invented protein β 🧬'
        snapshot['content_sha256'] = digest({k:v for k,v in snapshot.items() if k != 'content_sha256'})
        graph = save_run(snapshot, self.root/'unicode_source')
        answer = answer_question(graph, 'demo:protein:DEMO_PROTEIN_001', view='candidates', source_run='unicode_source')
        question = self.root/'old_question'
        save_answer(answer, question)
        # Persisted v1 writer remains ASCII; HTTP representation alone changes.
        original_json = (question/'question.json').read_bytes()
        self.assertIn(b'\\u03b1', original_json)
        self.assertNotIn('α'.encode('utf-8'), original_json)
        before = {p.relative_to(self.root).as_posix(): hashlib.sha256(p.read_bytes()).hexdigest()
                  for p in self.root.rglob('*') if p.is_file()}
        for restart in (False, True):
            if restart:
                self._stop_server()
                self._start_server()
            status, _, raw = self.get('/api/question/old_question')
            self.assertEqual(status, 200)
            reopened = json.loads(raw)['answer']
            self.assertEqual(reopened, answer)
            self.assertEqual(reopened['answer_sha256'], answer['answer_sha256'])
            verify_answer(reopened)
            self.assertIn('α'.encode('utf-8'), raw)
            status, headers, zipped = self.get('/api/download/old_question', encoding='gzip')
            self.assertEqual(status, 200)
            self.assertNotIn('Content-Encoding', headers)
            with ZipFile(BytesIO(zipped)) as archive:
                expected = {p.relative_to(question).as_posix(): p.read_bytes()
                            for p in question.rglob('*') if p.is_file()}
                self.assertEqual(set(archive.namelist()), {'old_question/'+name for name in expected})
                for name, content in expected.items():
                    self.assertEqual(archive.read('old_question/'+name), content)
        after = {p.relative_to(self.root).as_posix(): hashlib.sha256(p.read_bytes()).hexdigest()
                 for p in self.root.rglob('*') if p.is_file()}
        self.assertEqual(after, before)


if __name__ == '__main__':
    unittest.main()
