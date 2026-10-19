"""Portable runtime paths and explicit HTTP access policy; no secret logging."""
import base64
import hmac
import ipaddress
import os
from pathlib import Path
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


class AccessPolicy:
    def __init__(self, host='127.0.0.1', allowed_origins=(), access_token=None):
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
