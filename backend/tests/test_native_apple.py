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


def test_app_id_preflight_reuses_existing_ids_without_creation(monkeypatch):
    """Re-signing an existing app and extension must not consume new ID slots."""
    from viepn.applekit import provision
    monkeypatch.setattr(provision.developer, 'list_teams',
                        lambda: [{'teamId': 'TEAM123'}])
    existing = [{'identifier': 'com.example.app.TEAM123'},
                {'identifier': 'com.example.app.TEAM123.share'}]
    monkeypatch.setattr(provision.developer, 'list_app_ids',
                        lambda team: existing)
    monkeypatch.setattr(provision.developer, 'add_app_id',
                        lambda *a: (_ for _ in ()).throw(AssertionError('unexpected App ID creation')))
    result = provision.preflight_app_ids(
        ['com.example.app.TEAM123', 'com.example.app.TEAM123.share'])
    assert result['missing'] == []
    assert len(result['reused']) == 2


def test_app_id_preflight_blocks_quota_before_creating_main_app(monkeypatch):
    from viepn.applekit import provision
    monkeypatch.setattr(provision.developer, 'list_teams',
                        lambda: [{'teamId': 'TEAM123'}])
    monkeypatch.setattr(provision.developer, 'list_app_ids',
                        lambda team: [{'identifier': f'existing.{n}'} for n in range(9)])
    try:
        provision.preflight_app_ids(
            ['com.example.new.TEAM123', 'com.example.new.TEAM123.share'])
        assert False, 'must refuse a main app + extension requiring two slots'
    except provision.gsa.GsaError as exc:
        assert 'App ID capacity' in str(exc)
        assert 'extension' not in str(exc).lower() or 'App ID' in str(exc)


def test_app_id_error_9120_is_actionable_and_not_retried(monkeypatch):
    from viepn.applekit import provision, developer
    calls = []
    monkeypatch.setattr(developer, 'list_app_ids', lambda team: [])
    def refused(*args):
        calls.append(args)
        raise developer.DeveloperServicesError(
            '9120: Your maximum App ID limit has been reached. '
            'You may create up to 10 App IDs every 7 days.'
        )
    monkeypatch.setattr(developer, 'add_app_id', refused)
    try:
        provision._ensure_app_id('TEAM123', 'com.example.new.TEAM123', 'App')
        assert False, 'expected informative quota error'
    except provision.gsa.GsaError as exc:
        assert '9120' in str(exc)
        assert '7-day' in str(exc)
    assert len(calls) == 1


def test_app_id_race_reuses_newly_registered_id(monkeypatch):
    from viepn.applekit import provision, developer
    calls = iter([[], [{'identifier': 'com.example.app'}]])
    monkeypatch.setattr(developer, 'list_app_ids', lambda team: next(calls))
    def race(*args):
        raise developer.DeveloperServicesError('already exists')
    monkeypatch.setattr(developer, 'add_app_id', race)
    app = provision._ensure_app_id('TEAM123', 'com.example.app', 'App')
    assert app['identifier'] == 'com.example.app'
