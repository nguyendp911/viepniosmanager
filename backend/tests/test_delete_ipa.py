"""Deleting a local IPA must not destroy files required by renewal or jobs."""
import json
from pathlib import Path
from fastapi.testclient import TestClient

from test_api import config
from test_ipa import sample_ipa
from viepn.api import create_app

AUTH = {'Authorization': 'Bearer very-long-test-secret-token'}


def _upload(client, tmp_path):
    original = sample_ipa(tmp_path / 'test.ipa')
    with original.open('rb') as file:
        result = client.post('/api/ipas', headers=AUTH,
                             files={'file': ('test.ipa', file, 'application/octet-stream')})
    assert result.status_code == 200, result.text
    return result.json()['id']


def test_delete_removes_record_and_real_file(tmp_path):
    app = create_app(config(tmp_path))
    with TestClient(app) as client:
        ipa_id = _upload(client, tmp_path)
        record = app.state.manager.db.one('SELECT * FROM ipa WHERE id=?', (ipa_id,))
        library_path = Path(record['file_path'])
        assert library_path.exists()
        assert client.delete(f'/api/ipas/{ipa_id}').status_code == 401
        assert client.delete('/api/ipas/unknown', headers=AUTH).status_code == 404
        assert client.delete(f'/api/ipas/{ipa_id}', headers=AUTH).json() == {
            'deleted': True, 'id': ipa_id, 'file_removed': True, 'tracking_removed': 0, 'pending_file_deletes': 0
        }
        assert not library_path.exists()
        assert app.state.manager.db.one('SELECT id FROM ipa WHERE id=?', (ipa_id,)) is None
        assert client.get('/api/overview', headers=AUTH).json()['ipas'] == []
        assert client.delete(f'/api/ipas/{ipa_id}', headers=AUTH).status_code == 404


def test_delete_refuses_ipa_used_by_installation(tmp_path):
    app = create_app(config(tmp_path))
    with TestClient(app) as client:
        ipa_id = _upload(client, tmp_path)
        manager = app.state.manager
        path = Path(manager.db.one('SELECT * FROM ipa WHERE id=?', (ipa_id,))['file_path'])
        manager.db.exec("""INSERT INTO installations
            (id,device_udid,bundle_id,source_ipa_id,current_ipa_id,
             auto_renew,state,created_at)
            VALUES (?,?,?,?,?,?,?,?)""",
            ('install-a', 'a'*40, 'org.test.sample', ipa_id, ipa_id,
             1, 'active', '2026-11-07T00:00:00+00:00'))
        response = client.delete(f'/api/ipas/{ipa_id}', headers=AUTH)
        assert response.status_code == 409
        assert path.exists()
        assert manager.db.one('SELECT id FROM ipa WHERE id=?', (ipa_id,)) is not None


def test_delete_refuses_ipa_used_by_queued_sign_job(tmp_path):
    app = create_app(config(tmp_path))
    with TestClient(app) as client:
        ipa_id = _upload(client, tmp_path)
        manager = app.state.manager
        manager.db.exec("""INSERT INTO jobs
          (id,kind,state,input_json,created_at,updated_at)
          VALUES (?,?,?,?,?,?)""", (
            'queued-1', 'apple_sign', 'queued',
            json.dumps({'ipa_id': ipa_id, 'udid': 'a'*40}),
            '2026-11-07T00:00:00+00:00', '2026-11-07T00:00:00+00:00'))
        assert client.delete(f'/api/ipas/{ipa_id}', headers=AUTH).status_code == 409
        assert manager.db.one('SELECT id FROM ipa WHERE id=?', (ipa_id,)) is not None
