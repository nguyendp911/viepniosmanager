"""Native Apple signing API tests. No Apple credentials or network needed."""
import asyncio
from fastapi.testclient import TestClient
from test_api import config
from test_ipa import sample_ipa
from viepn.api import create_app
from viepn.native_sign import NativeSigningError, sign_free_ipa
from viepn.service import Manager
import viepn.native_sign as native_sign


HEADERS = {'Authorization': 'Bearer very-long-test-secret-token'}


def test_apple_status_and_authentication(tmp_path):
    with TestClient(create_app(config(tmp_path))) as client:
        assert client.get('/api/apple/status').status_code == 401
        r = client.get('/api/apple/status', headers=HEADERS)
        assert r.status_code == 200
        assert r.json()['backend'] == 'native_apple'
        assert r.json()['requires_p12_upload'] is False
        assert 'password' not in r.json()
        assert client.post('/api/apple/install', json={}).status_code == 401


def test_native_sign_rejects_no_account_before_network(tmp_path, monkeypatch):
    ipa = sample_ipa(tmp_path / 'unsigned.ipa')
    monkeypatch.setattr(native_sign, '_apple_environment', lambda: None)
    monkeypatch.setattr(native_sign.gsa, 'status', lambda: {'authenticated': False})
    try:
        sign_free_ipa(ipa, tmp_path / 'signed.ipa', 'a' * 40)
        assert False, 'Expected no-Apple-session error'
    except NativeSigningError as exc:
        assert 'apple-login' in str(exc)
    assert not (tmp_path / 'signed.ipa').exists()


def test_renew_uses_native_backend_even_if_auto_renew_off(tmp_path, monkeypatch):
    manager = Manager(config(tmp_path))
    manager.db.exec("""INSERT INTO installations
      (id,device_udid,bundle_id,source_ipa_id,current_ipa_id,
       expires_at,auto_renew,signing_mode,state,created_at)
       VALUES(?,?,?,?,?,?,?,?,?,?)""",
       ('test-install', 'a'*40, 'com.test.app', 'orig','signed',
        '2026-11-09T00:00:00+00:00',0,'apple_personal','active',
        '2026-11-07T00:00:00+00:00'))

    async def fake_native(record):
        return {'renewed': record['id']}
    monkeypatch.setattr(manager, '_apple_renew', fake_native)
    result = asyncio.run(manager._renew('test-install'))
    assert result == {'renewed': 'test-install'}


def test_renew_scanner_respects_opt_out(tmp_path):
    manager = Manager(config(tmp_path))
    manager.db.exec("""INSERT INTO installations
      (id,device_udid,bundle_id,source_ipa_id,current_ipa_id,
       expires_at,auto_renew,signing_mode,state,created_at)
       VALUES(?,?,?,?,?,?,?,?,?,?)""",
       ('test-install', 'a'*40, 'com.test.app', 'orig','signed',
        '2026-11-07T00:00:00+00:00',0,'apple_personal','active',
        '2026-11-07T00:00:00+00:00'))
    assert manager.due_installations() == []
