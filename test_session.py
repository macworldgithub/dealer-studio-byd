import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import httpx
from dealerstudio_session import DealerStudioSession, MFARequired, AuthenticationRequired, SessionBusy, totp, ROOT


class SessionTests(unittest.TestCase):
    def setUp(self):
        base = ROOT / '.runtime'
        base.mkdir(exist_ok=True)
        self.temp = tempfile.TemporaryDirectory(prefix='session-test-', dir=base)
        self.file = Path(self.temp.name) / 'session.json'
        self.config = {'DEALERSTUDIO_COOKIE': '_dealer_studio_session=seed', 'DEALERSTUDIO_CSRF_TOKEN': 'old-csrf', 'DEALERSTUDIO_DEALERSHIP_SLUG': 'denza-melbourne', 'DEALERSTUDIO_EMAIL': 'fixture@example.com', 'DEALERSTUDIO_PASSWORD': 'fixture-password'}

    def tearDown(self):
        self.assertTrue(Path(self.temp.name).resolve().is_relative_to(ROOT / '.runtime'))
        self.temp.cleanup()

    def session(self, handler):
        return DealerStudioSession(config=self.config, file=self.file, transport=httpx.MockTransport(handler))

    def test_rotated_cookies_and_csrf_survive_restart_without_reusing_stale_seed(self):
        def handler(request):
            if request.url.path.endswith('postgres_search'):
                self.assertIn('_dealer_studio_session=rotated', request.headers['cookie'])
                self.assertEqual(request.headers['x-csrf-token'], 'fresh-csrf')
                return httpx.Response(200, json={'lead_clusters': [], 'total_count': 0})
            return httpx.Response(200, text='<meta content="fresh-csrf" name="csrf-token">', headers={'Set-Cookie': '_dealer_studio_session=rotated; Path=/; Secure; HttpOnly'})
        with self.session(handler) as session:
            self.assertEqual(session.renew()['status'], 'authenticated')
        with self.session(lambda request: httpx.Response(200)) as restored:
            self.assertEqual(restored.state['csrf'], 'fresh-csrf')
            self.assertEqual(restored.client.cookies.get('_dealer_studio_session'), 'rotated')
        self.assertNotIn('cookies', json.loads(self.file.with_name('session-status.json').read_text()))

    def test_password_then_real_mfa_verification_without_repeated_password_attempts(self):
        state = {'login': 0, 'verified': False}
        def handler(request):
            if request.url.path.endswith('postgres_search'):
                return httpx.Response(200, json={'lead_clusters': []}) if state['verified'] else httpx.Response(401)
            if request.method == 'POST':
                user = json.loads(request.content)['user']
                if 'password' in user:
                    state['login'] += 1
                    return httpx.Response(200, json={'redirect_to': '/users/sign_in'})
                self.assertEqual(user['otp_attempt'], '123456')
                self.assertFalse(user['remember_2fa'])
                state['verified'] = True
                return httpx.Response(200, json={'redirect_to': '/'})
            return httpx.Response(200, text='<meta name="csrf-token" content="live">')
        with self.session(handler) as session:
            with self.assertRaises(MFARequired): session.renew()
            with self.assertRaises(MFARequired): session.renew()
            self.assertEqual(state['login'], 1)
            session.verify('123456')
            self.assertEqual(session.state['status'], 'authenticated')

    def test_invalid_credentials_are_not_retried_on_every_timer_tick(self):
        calls = []
        def handler(request):
            if request.method == 'POST': calls.append(request); return httpx.Response(401)
            if request.url.path.endswith('postgres_search'): return httpx.Response(401)
            return httpx.Response(200, text='<meta name="csrf-token" content="live">')
        with self.session(handler) as session:
            with self.assertRaises(AuthenticationRequired): session.renew()
            with self.assertRaises(AuthenticationRequired): session.renew()
        self.assertEqual(len(calls), 1)

    def test_totp_matches_rfc6238_vector(self):
        self.assertEqual(totp('GEZDGNBVGY3TQOJQGEZDGNBVGY3TQOJQ', 59, digits=8), '94287082')

    def test_background_renewal_cannot_overwrite_a_running_harvest_session(self):
        with self.session(lambda request: httpx.Response(200)):
            with self.assertRaises(SessionBusy):
                self.session(lambda request: httpx.Response(200))
        with self.session(lambda request: httpx.Response(200)):
            pass

    def test_login_redirects_refresh_csrf_without_following_external_hosts(self):
        def handler(request):
            if request.url.path == '/users/sign_in':
                return httpx.Response(302, headers={'Location': '/'})
            self.assertNotIn('x-csrf-token', request.headers)
            return httpx.Response(200, text='<meta name="csrf-token" content="redirect-csrf">')
        with self.session(handler) as session:
            session.bootstrap('/users/sign_in')
            self.assertEqual(session.state['csrf'], 'redirect-csrf')
        with self.session(lambda request: httpx.Response(302, headers={'Location': 'https://example.com/'})) as session:
            with self.assertRaises(AuthenticationRequired): session.bootstrap()

    def test_unattended_mfa_uses_only_the_configured_authenticator_secret(self):
        self.config['DEALERSTUDIO_TOTP_SECRET'] = 'GEZDGNBVGY3TQOJQGEZDGNBVGY3TQOJQ'
        with self.session(lambda request: httpx.Response(200)) as session:
            session.state['status'] = 'mfa_required'
            with patch('dealerstudio_session.time.time', return_value=59), patch.object(session, 'verify', return_value=True) as verify:
                session.login()
                verify.assert_called_once_with('287082')

    def test_rejected_authenticator_configuration_is_not_retried_by_the_timer(self):
        self.config['DEALERSTUDIO_TOTP_SECRET'] = 'GEZDGNBVGY3TQOJQGEZDGNBVGY3TQOJQ'
        with self.session(lambda request: httpx.Response(200)) as session:
            session.state['status'] = 'mfa_required'
            with patch.object(session, 'verify', side_effect=MFARequired('rejected')) as verify:
                with self.assertRaises(MFARequired): session.login()
                with self.assertRaises(MFARequired): session.login()
                self.assertEqual(verify.call_count, 1)

    def test_cross_origin_credentials_are_blocked_and_writes_are_not_replayed(self):
        posts = []
        with self.session(lambda request: posts.append(request) or httpx.Response(401)) as session:
            session.checked = True
            with self.assertRaises(ValueError): session.get('https://example.com/')
            with self.assertRaises(AuthenticationRequired): session.request('POST', '/business-record', json={})
        self.assertEqual(len(posts), 1)

    def test_failed_authentication_does_not_publish_empty_harvest(self):
        import fetch_complete_data as harvest
        with patch.object(harvest, '_harvest', side_effect=MFARequired('fixture challenge')):
            original = (ROOT / 'api_data/COMPLETE_DATA_MANIFEST.json').read_bytes()
            with self.assertRaises(MFARequired): harvest.main()
            self.assertEqual((ROOT / 'api_data/COMPLETE_DATA_MANIFEST.json').read_bytes(), original)


if __name__ == '__main__':
    unittest.main()
