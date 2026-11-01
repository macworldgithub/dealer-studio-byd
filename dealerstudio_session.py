"""Private rolling session, normal password login, and Dealer Studio MFA support."""
import argparse
import base64
import getpass
import hashlib
import hmac
import json
import os
import re
import struct
import time
import uuid
from html.parser import HTMLParser
from http.cookiejar import Cookie
from pathlib import Path
from urllib.parse import urlsplit, urljoin

import httpx
from dotenv import dotenv_values

ROOT = Path(__file__).resolve().parent
BASE = 'https://dashboard.dealerstudio.com.au'


class AuthenticationRequired(RuntimeError):
    pass


class MFARequired(AuthenticationRequired):
    pass


class SessionBusy(RuntimeError):
    pass


class MetaParser(HTMLParser):
    token = ''

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        if tag == 'meta' and attrs.get('name') == 'csrf-token':
            self.token = attrs.get('content', '')


def atomic_json(file, value):
    file = Path(file)
    file.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    temp = file.with_name(file.name + '.' + uuid.uuid4().hex + '.tmp')
    fd = os.open(temp, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(fd, 'w', encoding='utf8') as handle:
        json.dump(value, handle, indent=2)
    temp.replace(file)
    if os.name != 'nt':
        file.chmod(0o600)


def totp(secret, timestamp=None, digits=6):
    """RFC 6238; requires the account owner's actual configured secret."""
    secret = re.sub(r'\s+', '', secret).upper()
    key = base64.b32decode(secret + '=' * (-len(secret) % 8))
    digest = hmac.new(key, struct.pack('>Q', int(timestamp if timestamp is not None else time.time()) // 30), hashlib.sha1).digest()
    offset = digest[-1] & 15
    number = struct.unpack('>I', digest[offset:offset + 4])[0] & 0x7fffffff
    return str(number % (10 ** digits)).zfill(digits)


class DealerStudioSession:
    def __init__(self, config=None, file=None, transport=None):
        self.config = {**dotenv_values(ROOT / '.env'), **os.environ} if config is None else dict(config)
        self.file = Path(file or self.config.get('DEALERSTUDIO_SESSION_FILE') or ROOT / '.runtime/session.json')
        if not self.file.is_absolute():
            self.file = ROOT / self.file
        self.file.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
        self.lock = open(self.file.with_suffix('.lock'), 'a+b')
        if self.lock.seek(0, 2) == 0:
            self.lock.write(b'\0')
            self.lock.flush()
        self.lock.seek(0)
        try:
            if os.name == 'nt':
                import msvcrt
                msvcrt.locking(self.lock.fileno(), msvcrt.LK_NBLCK, 1)
            else:
                import fcntl
                fcntl.flock(self.lock.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        except OSError:
            self.lock.close()
            raise SessionBusy('Another Dealer Studio fetch or session renewal is running.')
        self.slug = self.config.get('DEALERSTUDIO_DEALERSHIP_SLUG', 'denza-melbourne')
        self.client = httpx.Client(timeout=35, follow_redirects=False, transport=transport)
        self.state = json.loads(self.file.read_text(encoding='utf8')) if self.file.exists() else {}
        seed = self.config.get('DEALERSTUDIO_COOKIE') or ''
        seed_hash = hashlib.sha256(seed.encode()).hexdigest()
        if self.state.get('seed_hash') != seed_hash:
            self.state = {'seed_hash': seed_hash, 'csrf': self.config.get('DEALERSTUDIO_CSRF_TOKEN', ''), 'cookies': []}
            self._seed(seed)
        else:
            for item in self.state.get('cookies', []):
                if item.get('expires') and item['expires'] <= time.time():
                    continue
                self.client.cookies.jar.set_cookie(Cookie(version=0, name=item['name'], value=item['value'], port=None, port_specified=False,
                    domain=item['domain'], domain_specified=item.get('domain_specified', False), domain_initial_dot=item['domain'].startswith('.'),
                    path=item.get('path', '/'), path_specified=True, secure=item.get('secure', True), expires=item.get('expires'),
                    discard=item.get('expires') is None, comment=None, comment_url=None, rest={}, rfc2109=False))
        self.checked = False

    def _seed(self, cookie):
        self.client.cookies.clear()
        for part in cookie.split(';'):
            if '=' in part:
                name, value = part.strip().split('=', 1)
                self.client.cookies.set(name, value, domain='dashboard.dealerstudio.com.au', path='/')

    def save(self, status):
        self.state.update(status=status, updatedAt=time.time(), cookies=[{'name': c.name, 'value': c.value, 'domain': c.domain,
            'domain_specified': c.domain_specified, 'path': c.path, 'secure': c.secure, 'expires': c.expires}
            for c in self.client.cookies.jar if not c.is_expired()])
        atomic_json(self.file, self.state)
        atomic_json(self.file.with_name('session-status.json'), {'status': status, 'checkedAt': time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime()),
            'lastSuccessfulCheckAt': self.state.get('lastSuccessfulCheckAt'), 'mfaRequired': status == 'mfa_required'})

    def _raw(self, method, resource, **kwargs):
        url = resource if resource.startswith('https://') else BASE + '/' + resource.lstrip('/')
        if (urlsplit(url).scheme, urlsplit(url).netloc) != ('https', 'dashboard.dealerstudio.com.au'):
            raise ValueError('Dealer Studio credentials cannot be sent to another origin.')
        supplied = kwargs.pop('headers', {})
        headers = {k: v for k, v in supplied.items() if k.lower() not in ('cookie', 'x-csrf-token', 'authorization')}
        headers.update({'Accept': headers.get('Accept', 'application/json'), 'Referer': BASE + '/', 'User-Agent': 'Mozilla/5.0'})
        if method.upper() != 'GET':
            headers['Origin'] = BASE
        if self.state.get('csrf') and headers['Accept'] != 'text/html':
            headers['X-CSRF-Token'] = self.state['csrf']
        if self.config.get('DEALERSTUDIO_API_KEY'):
            headers['Authorization'] = 'Bearer ' + self.config['DEALERSTUDIO_API_KEY']
        for attempt in range(3):
            try:
                response = self.client.request(method, url, headers=headers, **kwargs)
                break
            except httpx.RequestError:
                if method.upper() != 'GET' or attempt == 2:
                    raise
                time.sleep(0.5 * (attempt + 1))
        # Never follow a login redirect or transmit credentials to a different host.
        return response

    def bootstrap(self, resource='/'):
        for _ in range(6):
            response = self._raw('GET', resource, headers={'Accept': 'text/html'})
            if response.status_code not in (301, 302, 303, 307, 308):
                break
            resource = urljoin(str(response.request.url), response.headers.get('location', ''))
            if (urlsplit(resource).scheme, urlsplit(resource).netloc) != ('https', 'dashboard.dealerstudio.com.au'):
                raise AuthenticationRequired('Dealer Studio redirected login outside its own origin.')
        else:
            raise AuthenticationRequired('Dealer Studio login redirects did not complete.')
        if response.status_code >= 500:
            raise RuntimeError('Dealer Studio is temporarily unavailable.')
        if response.status_code == 200:
            parser = MetaParser()
            parser.feed(response.text)
            if parser.token:
                self.state['csrf'] = parser.token

    def probe(self):
        response = self._raw('GET', f'/dealerships/{self.slug}/lead_clusters/postgres_search', params={'rows': 1, 'page': 1, 'first': 0, 'pipeline_id': 'all'})
        if response.status_code >= 500 or response.status_code == 429:
            raise RuntimeError('Dealer Studio is temporarily unavailable; authentication was not reset.')
        try:
            data = response.json()
        except ValueError:
            return False
        valid = response.status_code == 200 and isinstance(data, dict) and isinstance(data.get('lead_clusters'), list)
        if valid:
            self.checked = True
            self.state['lastSuccessfulCheckAt'] = time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime())
            self.save('authenticated')
        return valid

    def methods(self):
        response = self._raw('GET', '/two_factor_auth_methods')
        if response.status_code != 200:
            raise AuthenticationRequired('Dealer Studio login challenge expired. Start login again.')
        return response.json()

    def verify(self, code):
        if not re.fullmatch(r'\d{6}', str(code)):
            raise ValueError('A six-digit verification code is required.')
        self.bootstrap('/users/sign_in')
        response = self._raw('POST', '/users/sign_in', json={'user': {'otp_attempt': str(code), 'remember_2fa': False}})
        if response.status_code == 200 and self.probe():
            return True
        self.save('mfa_required')
        raise MFARequired('Dealer Studio did not accept the verification code. No data was exported.')

    def send_code(self, method):
        if method not in ('email', 'sms'):
            raise ValueError('Choose email or sms.')
        response = self._raw('POST', '/send_two_factor_authentication_code', json={'delivery_method': method})
        if response.status_code != 200:
            raise MFARequired('Dealer Studio could not send a verification code.')
        self.save('mfa_required')

    def login(self, force=False):
        if force:
            self.state.pop('rejectedTotpFingerprint', None)
        if self.state.get('status') == 'mfa_required' and not force:
            if self.config.get('DEALERSTUDIO_TOTP_SECRET'):
                return self.automatic_verification()
            raise MFARequired('Dealer Studio requires a verification code. Run dealerstudio_session.py --verify.')
        email, password = self.config.get('DEALERSTUDIO_EMAIL'), self.config.get('DEALERSTUDIO_PASSWORD')
        if not email or not password:
            raise AuthenticationRequired('Configure Dealer Studio login credentials or reconnect a valid session.')
        fingerprint = hashlib.sha256((email + '\0' + password).encode()).hexdigest()
        if self.state.get('status') == 'authentication_required' and self.state.get('loginFingerprint') == fingerprint and not force:
            raise AuthenticationRequired('The last login was rejected. Update the credentials or explicitly restart login.')
        self.state['loginFingerprint'] = fingerprint
        self.bootstrap('/users/sign_in')
        if not self.state.get('csrf'):
            raise AuthenticationRequired('Dealer Studio did not issue a login CSRF token.')
        response = self._raw('POST', '/users/sign_in', json={'user': {'email': email, 'password': password, 'remember_me': '0'}})
        if response.status_code not in (200, 302, 303):
            self.save('csrf_error' if response.status_code == 422 else 'authentication_required')
            raise AuthenticationRequired(f'Dealer Studio rejected login (HTTP {response.status_code}).')
        if self.probe():
            return True
        self.bootstrap('/users/sign_in')
        self.save('mfa_required')
        if self.config.get('DEALERSTUDIO_TOTP_SECRET'):
            return self.automatic_verification()
        raise MFARequired('Dealer Studio accepted login and requires a verification code. Run dealerstudio_session.py --verify.')

    def automatic_verification(self):
        secret = self.config['DEALERSTUDIO_TOTP_SECRET']
        fingerprint = hashlib.sha256(secret.encode()).hexdigest()
        if self.state.get('rejectedTotpFingerprint') == fingerprint:
            raise MFARequired('Automatic verification was rejected. Update the authenticator configuration or explicitly restart login.')
        try:
            return self.verify(totp(secret))
        except MFARequired:
            self.state['rejectedTotpFingerprint'] = fingerprint
            self.save('mfa_required')
            raise

    def renew(self):
        self.bootstrap(f'/dealerships/{self.slug}/lead_clusters/pipelines/all')
        if not self.probe():
            self.login()
        return {'status': 'authenticated', 'lastSuccessfulCheckAt': self.state['lastSuccessfulCheckAt']}

    def request(self, method, resource, **kwargs):
        if not self.checked:
            self.renew()
        response = self._raw(method, resource, **kwargs)
        if response.status_code in (301, 302, 303, 307, 308, 401, 403, 422):
            # GETs may be retried safely; never replay a business write automatically.
            if method.upper() != 'GET':
                raise AuthenticationRequired('Dealer Studio rejected the request; writes are not automatically retried.')
            self.checked = False
            self.renew()
            response = self._raw(method, resource, **kwargs)
        if response.status_code in (301, 302, 303, 307, 308, 401, 403):
            raise AuthenticationRequired('Dealer Studio authentication is required.')
        if response.status_code == 200:
            self.save('authenticated')
        return response

    def get(self, url, **kwargs):
        return self.request('GET', url, **kwargs)

    def close(self):
        self.client.close()
        self.lock.close()

    def __enter__(self):
        return self

    def __exit__(self, *args):
        self.close()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    action = parser.add_mutually_exclusive_group()
    action.add_argument('--login', action='store_true')
    action.add_argument('--verify', action='store_true')
    action.add_argument('--send-code', choices=['email', 'sms'])
    parser.add_argument('--otp-file', help='Read one current code from a private file instead of prompting.')
    args = parser.parse_args()
    with DealerStudioSession() as session:
        if args.login:
            session.login(force=True)
        elif args.verify:
            code = Path(args.otp_file).read_text().strip() if args.otp_file else getpass.getpass('Dealer Studio verification code: ').strip()
            session.verify(code)
        elif args.send_code:
            session.send_code(args.send_code)
            print(json.dumps({'status': 'mfa_required', 'delivery_method': args.send_code}))
            return
        else:
            session.renew()
        print(json.dumps({'status': 'authenticated', 'lastSuccessfulCheckAt': session.state['lastSuccessfulCheckAt']}))


if __name__ == '__main__':
    try:
        main()
    except SessionBusy:
        print(json.dumps({'status': 'busy', 'message': 'Another Dealer Studio operation holds the session; this check was skipped.'}))
    except (AuthenticationRequired, ValueError, RuntimeError, httpx.RequestError) as error:
        print(json.dumps({'status': 'mfa_required' if isinstance(error, MFARequired) else 'failed', 'message': str(error) if not isinstance(error, httpx.RequestError) else 'Dealer Studio could not be reached.'}))
        raise SystemExit(3 if isinstance(error, MFARequired) else 1)
