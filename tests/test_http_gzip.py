"""Actual HTTP transport equivalence; payload fixtures are not scientific data."""
import gzip
from http.client import HTTPConnection
from io import BytesIO
import json
from pathlib import Path
import tempfile
import threading
import unittest
from zipfile import ZipFile, ZIP_STORED

from biograph_steward.webapp import create_server


class HttpGzipTests(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.token = 'invented-gzip-test-token-1234'
        self.server = create_server(0, Path(tmp.name), access_token=self.token)
        handler = self.server.RequestHandlerClass
        handler.log_message = lambda *args: None
        self.json_body = json.dumps({'scope': 'invented transport fixture',
                                    'records': ['preserved literal evidence text'] * 6000}).encode()
        self.html_body = ('<!doctype html><html><p>' + 'invented transport text ' * 6000 + '</p></html>').encode()
        self.native_body = b'<InventedNativeFixture>' + b'not scientific data ' * 6000 + b'</InventedNativeFixture>'
        zipped = BytesIO()
        with ZipFile(zipped, 'w', ZIP_STORED) as archive:
            archive.writestr('invented.gpml', self.native_body)
        self.zip_body = zipped.getvalue()
        # Exercise the unmodified production reply/authenticate methods over
        # real sockets. These fixture routes exist only on this test handler.
        fixtures = {
            '/fixture/json': (self.json_body, 'application/json', None),
            '/fixture/html': (self.html_body, 'text/html; charset=utf-8', None),
            '/fixture/json_attachment': (self.json_body, 'application/json', 'question.json'),
            '/fixture/native_attachment': (self.native_body, 'application/xml', 'invented.gpml'),
            '/fixture/zip_attachment': (self.zip_body, 'application/zip', 'evidence.zip'),
            '/fixture/text': (self.html_body, 'text/plain', None),
            '/fixture/small': (b'{"status":"small"}', 'application/json', None),
        }
        original_get = handler.do_GET
        def fixture_get(request):
            if request.path in fixtures:
                if not request.authenticate():
                    return
                payload, mime, filename = fixtures[request.path]
                request.reply(payload, content_type=mime, filename=filename)
            else:
                original_get(request)
        handler.do_GET = fixture_get
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()
        self.addCleanup(self.close)

    def close(self):
        self.server.shutdown()
        self.server.server_close()
        self.thread.join()

    def request(self, path, encodings=(), *, auth=True, method='GET', body=None, extra=()):
        connection = HTTPConnection('127.0.0.1', self.server.server_port, timeout=10)
        try:
            connection.putrequest(method, path, skip_accept_encoding=True)
            if auth:
                connection.putheader('Authorization', 'Bearer ' + self.token)
            for value in encodings:
                connection.putheader('Accept-Encoding', value)
            for name, value in extra:
                connection.putheader(name, value)
            if body is not None:
                connection.putheader('Content-Length', str(len(body)))
            connection.endheaders(body)
            response = connection.getresponse()
            data = response.read()
            headers = dict(response.getheaders())
            self.assertEqual(int(headers['Content-Length']), len(data))
            self.assertEqual(headers['Cache-Control'], 'no-store')
            self.assertEqual(headers['X-Content-Type-Options'], 'nosniff')
            self.assertEqual(headers['Referrer-Policy'], 'same-origin')
            self.assertEqual(headers['X-Frame-Options'], 'DENY')
            return response.status, headers, data
        finally:
            connection.close()

    def test_gzip_and_identity_have_exact_json_and_html_equivalence(self):
        for path, expected in [('/fixture/json', self.json_body), ('/fixture/html', self.html_body)]:
            with self.subTest(path=path):
                status, identity_headers, identity = self.request(path)
                coded_status, coded_headers, coded = self.request(path, ['br, gzip'])
                self.assertEqual((status, coded_status), (200, 200))
                self.assertNotIn('Content-Encoding', identity_headers)
                self.assertEqual(coded_headers['Content-Encoding'], 'gzip')
                self.assertEqual(identity_headers['Vary'], 'Accept-Encoding')
                self.assertEqual(coded_headers['Vary'], 'Accept-Encoding')
                self.assertEqual(gzip.decompress(coded), identity)
                self.assertEqual(identity, expected)
                self.assertLess(len(coded), len(identity))

    def test_explicit_positive_weights_case_and_multiple_field_lines_are_supported(self):
        for headers in (['GZip'], ['br;q=1, gzip;q=0.001'], ['gzip;Q=1.000'],
                        ['br', 'gzip;q=0.5']):
            with self.subTest(headers=headers):
                status, reply, raw = self.request('/fixture/json', headers)
                self.assertEqual(status, 200)
                self.assertEqual(reply.get('Content-Encoding'), 'gzip')
                self.assertEqual(gzip.decompress(raw), self.json_body)

    def test_zero_missing_wildcard_and_malformed_gzip_preferences_never_compress(self):
        for headers in ([], [''], ['identity'], ['*'], ['gzip;q=0'], ['gzip;q=0.000, *;q=1'],
                        ['gzip;q=0, gzip;q=1'], ['gzip', 'gzip;q=0'], ['gzip;q=NaN'],
                        ['gzip;q=1.001'], ['gzip;q=-1'], ['gzip;q=.5'], ['gzip;q=0.0000'],
                        ['gzip;q=1;q=0'], ['notgzip']):
            with self.subTest(headers=headers):
                status, reply, raw = self.request('/fixture/json', headers)
                self.assertEqual(status, 200)
                self.assertNotIn('Content-Encoding', reply)
                self.assertEqual(raw, self.json_body)
                self.assertEqual(reply['Vary'], 'Accept-Encoding')

    def test_attachments_native_zip_small_and_other_mime_payloads_are_unchanged(self):
        expected = {'json_attachment': self.json_body, 'native_attachment': self.native_body,
                    'zip_attachment': self.zip_body, 'text': self.html_body, 'small': b'{"status":"small"}'}
        for name, body in expected.items():
            with self.subTest(name=name):
                status, headers, raw = self.request('/fixture/' + name, ['gzip'])
                self.assertEqual(status, 200)
                self.assertEqual(raw, body)
                self.assertNotIn('Content-Encoding', headers)
                self.assertNotIn('Vary', headers)
                if name.endswith('attachment'):
                    self.assertIn('attachment', headers['Content-Disposition'])

    def test_gzip_preference_cannot_change_authentication_origin_or_error_status(self):
        status, headers, raw = self.request('/fixture/json', ['gzip'], auth=False)
        self.assertEqual(status, 401)
        self.assertEqual(json.loads(raw)['error'], 'Sign in to the workspace to continue.')
        self.assertNotIn('Content-Encoding', headers)
        status, _, raw = self.request('/api/question', ['gzip'], method='POST', body=b'{}',
            extra=[('Content-Type', 'application/json'), ('Origin', 'https://not-allowed.invalid')])
        self.assertEqual(status, 403)
        self.assertIn('origin', json.loads(raw)['error'])
        status, _, raw = self.request('/api/question', ['gzip'], method='POST', body=b'{}',
            extra=[('Content-Type', 'text/plain')])
        self.assertEqual(status, 415)
        self.assertIn('application/json', json.loads(raw)['error'])
        status, _, raw = self.request('/not-a-route', ['gzip'])
        self.assertEqual(status, 404)
        self.assertEqual(json.loads(raw)['error'], 'Not found')


if __name__ == '__main__':
    unittest.main()
