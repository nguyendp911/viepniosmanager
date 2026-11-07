"""Security and lifecycle tests for free Apple Account IPA handoff."""
import time
from fastapi.testclient import TestClient
from test_api import config
from test_ipa import sample_ipa
from viepn.api import create_app
from viepn.free_sign import ShareStore

AUTH = {'Authorization': 'Bearer very-long-test-secret-token'}


def test_free_status_does_not_require_signing_credentials(tmp_path):
    with TestClient(create_app(config(tmp_path))) as client:
        assert client.get('/api/free/status').status_code == 401
        r = client.get('/api/free/status', headers=AUTH)
        assert r.status_code == 200
        body = r.json()
        assert body['mode'] == 'native_apple'
        assert body['requires_p12_upload'] is False
        assert body['authenticated'] is False


def test_share_authentication_one_time_and_missing_file(tmp_path):
    with TestClient(create_app(config(tmp_path))) as client:
        with sample_ipa(tmp_path / 'test.ipa').open('rb') as stream:
            upload = client.post('/api/ipas', headers=AUTH,
                                 files={'file': ('test.ipa', stream, 'application/octet-stream')})
        assert upload.status_code == 200
        ipa_id = upload.json()['id']
        bad = client.post('/api/free/share/' + ipa_id)
        assert bad.status_code == 401
        missing = client.post('/api/free/share/not-found', headers=AUTH)
        assert missing.status_code == 404
        s = client.post('/api/free/share/' + ipa_id, headers=AUTH)
        assert s.status_code == 200
        path = s.json()['path']
        assert '/api/free/download/' in path
        assert 'very-long-test-secret-token' not in path
        assert client.get(path).status_code == 200
        assert client.get(path).status_code == 404
        assert client.get('/api/free/download/invalid').status_code == 404


def test_share_expiration(tmp_path, monkeypatch):
    path = sample_ipa(tmp_path / 'a.ipa')
    shares = ShareStore(ttl_seconds=2)
    token, ttl = shares.create(path, 'com.example.app')
    assert ttl == 2
    start = time.monotonic()
    monkeypatch.setattr('viepn.free_sign.time.monotonic', lambda: start + 10)
    assert shares.take(token) is None
