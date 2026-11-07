"""Apple browser 2FA flow without contacting Apple servers."""
from viepn.apple_auth import AppleAuthFlow
import viepn.apple_auth as module
from viepn.applekit import paths


def test_login_challenge_verification_and_clearing(tmp_path, monkeypatch):
    monkeypatch.setattr(module, '_apple_environment', lambda: None)
    monkeypatch.setattr(paths, 'pending_2fa_file', lambda: tmp_path / 'pending.json')
    monkeypatch.setattr(module.gsa, 'begin_login',
                        lambda email, password: {'status': '2fa_required', 'method': 'sms'})
    monkeypatch.setattr(module.gsa, 'complete_2fa',
                        lambda email, password, code: {'status': 'authenticated'})
    flow = AppleAuthFlow()
    start = flow.begin('demo@example.com', 'sample-credential')
    assert start['status'] == '2fa_required'
    assert 'sample-credential' not in str(start)
    assert flow.verify(start['challenge'], '123456') == {'status': 'authenticated'}
    assert flow._pending is None


def test_community_anisette_requires_consent():
    flow = AppleAuthFlow()
    try:
        flow.configure('community', None, False)
    except ValueError as exc:
        assert 'Consent required' in str(exc)
    else:
        raise AssertionError('Community provider must require consent')
