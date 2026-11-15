"""Portable runtime paths and explicit HTTP access policy; no secret logging."""
import base64
import hashlib
import hmac
from http.cookies import CookieError, SimpleCookie
import ipaddress
import os
from pathlib import Path
import secrets
import threading
import time
from urllib.parse import urlsplit


def runs_directory():
    root = os.environ.get('BIOGRAPH_DATA_DIR')
    return Path(os.environ.get('BIOGRAPH_RUNS_DIR', str(Path(root) / 'runs') if root else 'runs'))


def cache_directory():
    root = os.environ.get('BIOGRAPH_DATA_DIR')
    return Path(os.environ.get('BIOGRAPH_CACHE_DIR', str(Path(root) / 'cache') if root else '.pharos_cache'))


def origin_identity(value):
    try:
        u = urlsplit(value)
        if (u.scheme not in {'http', 'https'} or not u.hostname or u.username is not None or u.password is not None
                or '*' in u.hostname or u.path not in {'', '/'} or u.query or u.fragment or any(c.isspace() for c in value)):
            raise ValueError
        port = u.port if u.port is not None else (443 if u.scheme == 'https' else 80)
        return u.scheme, u.hostname.lower(), port
    except (ValueError, TypeError, AttributeError):
        raise ValueError('Allowed origins must be exact HTTP(S) origins without credentials, paths, query or fragment.') from None


def loopback_host(host):
    if host == 'localhost':
        return True
    try:
        return ipaddress.ip_address(host).is_loopback
    except ValueError:
        return False


class BrowserSessions:
    """Bounded, opaque browser sessions; restarting the server revokes them."""
    cookie_name = 'biograph_session'
    lifetime = 8 * 60 * 60
    capacity = 256

    def __init__(self):
        self._sessions = {}
        self._lock = threading.Lock()

    def _key(self, cookie):
        if not isinstance(cookie, str) or len(cookie) > 8192:
            return None
        try:
            value = SimpleCookie(cookie).get(self.cookie_name)
            if value and len(value.value) == 43 and value.value.isascii():
                return hashlib.sha256(value.value.encode('ascii')).digest()
        except CookieError:
            pass
        return None

    def authenticated(self, cookie):
        key = self._key(cookie)
        with self._lock:
            expires = self._sessions.get(key, 0)
            if expires > time.monotonic():
                return True
            self._sessions.pop(key, None)
            return False

    def issue(self):
        value = secrets.token_urlsafe(32)
        now = time.monotonic()
        with self._lock:
            self._sessions = {k: expires for k, expires in self._sessions.items() if expires > now}
            if len(self._sessions) >= self.capacity:
                self._sessions.pop(next(iter(self._sessions)))
            self._sessions[hashlib.sha256(value.encode('ascii')).digest()] = now + self.lifetime
        return value

    def revoke(self, cookie):
        with self._lock:
            self._sessions.pop(self._key(cookie), None)

    def cookie_header(self, value='', *, secure=False):
        age = self.lifetime if value else 0
        return (f'{self.cookie_name}={value}; Path=/; HttpOnly; SameSite=Strict; Max-Age={age}'
                + ('; Secure' if secure else ''))


SAVED_REVIEW_POSTS = frozenset({
    '/auth/login', '/auth/logout', '/api/question', '/api/explore', '/api/inspect-source',
    '/api/protein-context', '/api/neptune-inspect', '/api/native-go-context',
    '/api/download-native-go-context', '/api/native-go-question',
})
SAVED_REVIEW_MESSAGE = ('Saved-data review mode: live source ranking, construction, model planning, '
    'retrieval, review changes and new decision exports are unavailable on this server. '
    'Saved questions, source inspection and existing downloads remain available.')


class AccessPolicy:
    def __init__(self, host='127.0.0.1', allowed_origins=(), access_token=None, *, saved_data_only=False):
        if type(saved_data_only) is not bool:
            raise ValueError('saved_data_only must be an explicit boolean.')
        self.saved_data_only = saved_data_only
        if host != 'localhost':
            try:
                ipaddress.ip_address(host)
            except ValueError:
                raise ValueError('Bind host must be an IP address or localhost.') from None
        if access_token is not None and (not isinstance(access_token, str) or not 24 <= len(access_token) <= 256
                                         or not access_token.isascii() or any(c.isspace() for c in access_token)):
            raise ValueError('BIOGRAPH_ACCESS_TOKEN must contain 24–256 non-whitespace ASCII characters.')
        if not loopback_host(host) and access_token is None:
            raise ValueError('Non-loopback hosting requires BIOGRAPH_ACCESS_TOKEN. Use a loopback SSH tunnel for unauthenticated local access.')
        self.host = host; self.token = access_token
        if isinstance(allowed_origins, str):
            allowed_origins = [s.strip() for s in allowed_origins.split(',') if s.strip()]
        self.origins = frozenset(origin_identity(s) for s in allowed_origins)
        if access_token is None and any(not loopback_host(name) for _, name, _ in self.origins):
            raise ValueError('Remote browser origins require BIOGRAPH_ACCESS_TOKEN.')
        if any(scheme != 'https' and not loopback_host(name) for scheme, name, _ in self.origins):
            raise ValueError('Remote browser origins must use HTTPS.')

    def allows_action(self, method, path, body=None):
        """Operator-owned action scope, separate from authentication and Origin.

        Match the existing reviewer gateway's saved routes, then inspect parsed
        JSON for the one saved-question option that can otherwise fetch sources.
        Host, Origin and client headers never enable or disable this policy.
        """
        if not self.saved_data_only:
            return True
        if method in {'GET', 'HEAD'}:
            return path != '/api/planner'
        if method != 'POST' or path not in SAVED_REVIEW_POSTS:
            return False
        return not (path == '/api/question' and body is not None
                    and body.get('ranking', 'alphabetical') != 'alphabetical')

    def capabilities(self):
        return {'saved_data_only': self.saved_data_only,
                'live_physical_ranking': not self.saved_data_only,
                'model_planning': not self.saved_data_only}

    def allows_origin(self, value, port):
        if not value:
            # CLI clients need not send Origin; authentication still applies.
            return True
        try:
            identity = origin_identity(value)
        except ValueError:
            return False
        return identity in self.origins or (identity[0] == 'http' and loopback_host(identity[1]) and identity[2] == port)

    def authenticated(self, authorization):
        if self.token is None:
            return True
        if not isinstance(authorization, str):
            return False
        if authorization.startswith('Bearer '):
            candidate = authorization[7:]
        elif authorization.startswith('Basic '):
            try:
                user, candidate = base64.b64decode(authorization[6:], validate=True).decode('utf-8').split(':', 1)
                if user != 'steward':
                    return False
            except (ValueError, UnicodeError):
                return False
        else:
            return False
        return hmac.compare_digest(candidate.encode('utf-8'), self.token.encode('ascii'))
