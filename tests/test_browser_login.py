"""Browser sign-in and existing API authentication, with invented credentials."""
from contextlib import contextmanager
from http.cookies import SimpleCookie
import json
from pathlib import Path
import tempfile
import threading
import unittest
from unittest.mock import patch
from urllib.error import HTTPError
from urllib.parse import urlencode
from urllib.request import HTTPRedirectHandler, ProxyHandler, Request, build_opener

from biograph_steward.runtime import BrowserSessions
from biograph_steward.webapp import create_server, login_return_path, report_html

TOKEN = 'invented-browser-login-token-for-testing'


class NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, *args, **kwargs):
        return None


@contextmanager
def hosted():
    with tempfile.TemporaryDirectory() as root:
        server = create_server(0, Path(root), access_token=TOKEN, allowed_origins=['https://workspace.example.org'])
        thread = threading.Thread(target=server.serve_forever, daemon=True); thread.start()
        try:
            yield f'http://127.0.0.1:{server.server_port}', Path(root)
        finally:
            server.shutdown(); server.server_close(); thread.join()


class BrowserLoginTests(unittest.TestCase):
    def request(self, url, *, data=None, headers=None):
        try:
            result = build_opener(ProxyHandler({}), NoRedirect()).open(Request(url, data=data, headers=headers or {}), timeout=5)
        except HTTPError as exc:
            result = exc
        with result:
            return result.code, result.headers, result.read()

    def login(self, base, *, token=TOKEN, return_to='/', origin=None, extra=None):
        return self.request(base+'/auth/login', data=urlencode({'token': token, 'return_to': return_to}).encode(),
                            headers={'Origin': origin or base, 'Content-Type': 'application/x-www-form-urlencoded', **(extra or {})})

    def test_deep_link_login_and_cookie_allow_the_saved_workflow_without_native_auth_challenge(self):
        with hosted() as (url, root):
            return_to = '/?run=saved_run&question=saved_question'
            code, headers, page = self.request(url+return_to)
            self.assertEqual(code, 200); self.assertNotIn('WWW-Authenticate', headers)
            self.assertIn(b'action="/auth/login"', page); self.assertIn(b'run=saved_run&amp;question=saved_question', page)
            self.assertNotIn(TOKEN.encode(), page)
            code, headers, _ = self.login(url, return_to=return_to)
            self.assertEqual(code, 303); self.assertEqual(headers['Location'], return_to)
            cookie = SimpleCookie(headers['Set-Cookie'])['biograph_session']
            self.assertTrue(cookie['httponly']); self.assertEqual(cookie['samesite'], 'Strict')
            self.assertEqual(cookie['path'], '/'); self.assertEqual(cookie['max-age'], str(8*60*60))
            self.assertFalse(cookie['secure']); self.assertNotEqual(cookie.value, TOKEN)
            auth = {'Cookie': 'biograph_session='+cookie.value}
            code, _, page = self.request(url+return_to, headers=auth)
            self.assertEqual(code, 200); self.assertIn(b'Sign out', page); self.assertNotIn(b'action="/auth/login"', page)
            code, _, body = self.request(url+'/api/build', data=b'{"mode":"demo"}',
                                         headers={**auth, 'Origin': url, 'Content-Type': 'application/json'})
            self.assertEqual(code, 200); self.assertEqual(json.loads(body)['graph']['data_kind'], 'synthetic_demo')
            self.assertEqual(len(list(root.iterdir())), 1)

    def test_wrong_token_or_cookie_cannot_read_data_and_no_secret_is_echoed(self):
        with hosted() as (url, root):
            code, headers, body = self.login(url, token='wrong-token-with-<script>')
            self.assertEqual(code, 403); self.assertNotIn('Set-Cookie', headers)
            self.assertNotIn(b'wrong-token', body)
            for auth in ({}, {'Authorization': 'Bearer wrong'}, {'Cookie': 'biograph_session='+'a'*43}):
                code, headers, _ = self.request(url+'/api/planner', headers=auth)
                self.assertEqual(code, 401); self.assertNotIn('WWW-Authenticate', headers)
            self.assertEqual(list(root.iterdir()), [])

    def test_native_forms_preserve_same_origin_and_the_login_get_route_is_public(self):
        with hosted() as (url, _):
            for route in ['/', '/auth/login']:
                code, headers, page = self.request(url+route)
                self.assertEqual(code, 200)
                self.assertEqual(headers['Referrer-Policy'], 'same-origin')
                self.assertIn(b'action="/auth/login"', page)
            _, headers, _ = self.login(url)
            code, headers, page = self.request(url+'/', headers={'Cookie': headers['Set-Cookie'].split(';')[0]})
            self.assertEqual(code, 200); self.assertIn(b'/auth/logout', page)
            self.assertEqual(headers['Referrer-Policy'], 'same-origin')

    def test_html_report_navigation_signs_in_and_returns_to_report_but_api_clients_stay_unauthorized(self):
        with hosted() as (url, root):
            folder = root / 'saved_report'; folder.mkdir()
            (folder/'metrics.json').write_text('{}'); (folder/'report.html').write_text('<h1>Saved source report</h1>')
            route = '/api/evaluation/saved_report/'
            code, _, body = self.request(url+route)
            self.assertEqual(code, 401); self.assertNotIn(b'<form', body)
            code, headers, body = self.request(url+route, headers={'Accept': 'text/html,application/xhtml+xml'})
            self.assertEqual(code, 200); self.assertIn(('value="'+route+'"').encode(), body)
            code, headers, _ = self.login(url, return_to=route)
            self.assertEqual(code, 303); self.assertEqual(headers['Location'], route)
            code, _, body = self.request(url+route, headers={'Cookie': headers['Set-Cookie'].split(';')[0]})
            self.assertEqual(code, 200); self.assertIn(b'Saved source report', body)
            for route in ['/api/evaluation/saved_report/metrics.json', '/api/download/saved_report']:
                code, _, _ = self.request(url+route, headers={'Accept': 'text/html'})
                self.assertEqual(code, 401)
            self.assertEqual(login_return_path('/api/evaluation/saved_report/report.html'), '/api/evaluation/saved_report/report.html')
            for route in ['/api/evaluation/../secret/', '/api/evaluation/saved_report/?x=1', '/api/evaluation/saved_report/metrics.json', '/api/download/saved_report']:
                self.assertEqual(login_return_path(route), '/')

    def test_login_and_cookie_writes_require_an_explicit_approved_origin(self):
        with hosted() as (url, root):
            for origin in ['https://evil.example.org', 'null', 'http://localhost:9']:
                code, headers, _ = self.login(url, origin=origin)
                self.assertEqual(code, 403); self.assertNotIn('Set-Cookie', headers)
            code, _, _ = self.request(url+'/auth/login', data=urlencode({'token': TOKEN, 'return_to': '/'}).encode(),
                                     headers={'Content-Type': 'application/x-www-form-urlencoded'})
            self.assertEqual(code, 403)
            _, headers, _ = self.login(url)
            auth = {'Cookie': headers['Set-Cookie'].split(';')[0], 'Content-Type': 'application/json'}
            for origin in [None, 'https://evil.example.org', 'null']:
                code, _, _ = self.request(url+'/api/build', data=b'{"mode":"demo"}',
                                         headers={**auth, **({'Origin': origin} if origin else {})})
                self.assertEqual(code, 403)
            self.assertEqual(list(root.iterdir()), [])
            # CLI clients retain explicit Bearer access without a browser Origin.
            code, _, _ = self.request(url+'/api/build', data=b'{"mode":"demo"}',
                                     headers={'Authorization': 'Bearer '+TOKEN, 'Content-Type': 'application/json'})
            self.assertEqual(code, 200)

    def test_https_proxy_login_sets_secure_cookie_and_logout_revokes_the_session(self):
        with hosted() as (url, _):
            _, headers, _ = self.login(url, origin='https://workspace.example.org')
            self.assertTrue(SimpleCookie(headers['Set-Cookie'])['biograph_session']['secure'])
            auth = {'Cookie': headers['Set-Cookie'].split(';')[0], 'Origin': 'https://workspace.example.org'}
            code, _, _ = self.request(url+'/health', headers=auth)
            self.assertEqual(code, 200)
            code, _, _ = self.request(url+'/auth/logout', data=b'', headers={**auth, 'Origin': 'https://evil.example.org'})
            self.assertEqual(code, 403)
            code, headers, _ = self.request(url+'/auth/logout', data=b'', headers=auth)
            self.assertEqual(code, 303); self.assertEqual(headers['Location'], '/')
            self.assertEqual(SimpleCookie(headers['Set-Cookie'])['biograph_session']['max-age'], '0')
            code, _, _ = self.request(url+'/health', headers=auth)
            self.assertEqual(code, 401)

    def test_malformed_login_forms_and_unsafe_redirects_fail_closed(self):
        with hosted() as (url, root):
            for data in [b'token=a&token=b&return_to=/', b'token=a', b'\xff', b'x'*8193]:
                code, headers, _ = self.request(url+'/auth/login', data=data,
                                                headers={'Origin': url, 'Content-Type': 'application/x-www-form-urlencoded'})
                self.assertEqual(code, 400); self.assertNotIn('Set-Cookie', headers)
            code, _, _ = self.request(url+'/auth/login', data=b'{}', headers={'Origin': url, 'Content-Type': 'application/json'})
            self.assertEqual(code, 415)
            code, headers, _ = self.login(url, return_to='https://evil.example.org/')
            self.assertEqual(code, 303); self.assertEqual(headers['Location'], '/')
            self.assertEqual(list(root.iterdir()), [])
        for value in ['//evil.example.org/', '///?next=evil', '/\\evil.example.org', '/\r\nX: bad',
                      'javascript:alert(1)', '/auth/login', '/?x='+'a'*2048]:
            self.assertEqual(login_return_path(value), '/')
        self.assertEqual(login_return_path('/?run=saved'), '/?run=saved')
        self.assertNotIn('__AUTH_CONTROL__', report_html())
        self.assertNotIn('Sign out', report_html())

    def test_sessions_expire_are_bounded_and_do_not_survive_server_restart(self):
        sessions = BrowserSessions()
        with patch('biograph_steward.runtime.time.monotonic', return_value=100):
            value = sessions.issue()
            cookie = sessions.cookie_name+'='+value
            self.assertTrue(sessions.authenticated(cookie))
        for invalid in [None, '', 'bad; cookie', sessions.cookie_name+'='+'x'*9000,
                        sessions.cookie_name+'='+value[:-1]+'!']:
            self.assertFalse(sessions.authenticated(invalid))
        self.assertFalse(BrowserSessions().authenticated(cookie))
        with patch('biograph_steward.runtime.time.monotonic', return_value=100+sessions.lifetime):
            self.assertFalse(sessions.authenticated(cookie))
        with patch.object(sessions, 'capacity', 2):
            first = sessions.issue(); second = sessions.issue(); third = sessions.issue()
            self.assertFalse(sessions.authenticated(sessions.cookie_name+'='+first))
            self.assertTrue(sessions.authenticated(sessions.cookie_name+'='+second))
            self.assertTrue(sessions.authenticated(sessions.cookie_name+'='+third))


if __name__ == '__main__':
    unittest.main()
