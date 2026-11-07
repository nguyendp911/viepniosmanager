"""Bulk IPA cleanup includes signed/profile builds; tracking removal is explicit."""
import json
from pathlib import Path
from fastapi.testclient import TestClient

from test_api import config
from test_ipa import sample_ipa
from viepn.api import create_app

AUTH = {'Authorization': 'Bearer very-long-test-secret-token'}


def upload(client, path):
    file = sample_ipa(path)
    with file.open('rb') as fh:
        resp = client.post('/api/ipas', headers=AUTH,
                           files={'file': (path.name, fh, 'application/octet-stream')})
    assert resp.status_code == 200
    return resp.json()['id']


def tracked(manager, ipa_id):
    manager.db.exec(
        "INSERT INTO installations "
        "(id,device_udid,bundle_id,source_ipa_id,current_ipa_id,"
        "auto_renew,state,created_at) VALUES (?,?,?,?,?,?,?,?)",
        ('tracked', 'a'*40, 'com.test.app', ipa_id, ipa_id, 1,
         'active', '2026-11-07T00:00:00+00:00')
    )


def test_delete_profiled_ipa_without_installation(tmp_path):
    app = create_app(config(tmp_path))
    with TestClient(app) as c:
        ipa = upload(c, tmp_path / 'profiled.ipa')
        manager = app.state.manager
        manager.db.exec(
            "UPDATE ipa SET signed_candidate=1,profile_expires=? WHERE id=?",
            ('2026-11-14T12:00:00+00:00', ipa)
        )
        result = c.post('/api/ipas/bulk-delete', headers=AUTH, json={
            'all': True, 'force': False, 'confirm': 'DELETE ALL IPAS'
        })
        assert result.status_code == 200, result.text
        assert result.json()['deleted_ids'] == [ipa]
        assert manager.db.one('SELECT id FROM ipa WHERE id=?', (ipa,)) is None


def test_force_delete_detaches_renewal_but_never_uninstalls_phone(tmp_path):
    app = create_app(config(tmp_path))
    with TestClient(app) as c:
        ipa = upload(c, tmp_path / 'tracked.ipa')
        manager = app.state.manager
        record = manager.db.one('SELECT * FROM ipa WHERE id=?', (ipa,))
        target = Path(record['file_path'])
        tracked(manager, ipa)
        assert c.post('/api/ipas/bulk-delete', headers=AUTH,
                      json={'all': True, 'force': False,
                            'confirm': 'DELETE ALL IPAS'}).status_code == 409
        assert c.delete(f'/api/ipas/{ipa}', headers=AUTH).status_code == 409
        response = c.post('/api/ipas/bulk-delete', headers=AUTH,
                          json={'all': True, 'force': True,
                                'confirm': 'DELETE ALL IPAS'})
        assert response.status_code == 200, response.text
        assert response.json()['tracking_removed'] == 1
        assert response.json()['files_removed'] == 1
        assert not target.exists()
        assert manager.db.query('SELECT * FROM ipa') == []
        assert manager.db.query('SELECT * FROM installations') == []


def test_bulk_confirm_and_auth_are_required(tmp_path):
    app = create_app(config(tmp_path))
    with TestClient(app) as c:
        ipa = upload(c, tmp_path / 'test.ipa')
        bad = {'all': True, 'force': True, 'confirm': 'yes'}
        assert c.post('/api/ipas/bulk-delete', json=bad).status_code == 401
        assert c.post('/api/ipas/bulk-delete', headers=AUTH, json=bad).status_code == 400
        assert c.post('/api/ipas/bulk-delete', headers=AUTH, json={
            'all': False, 'ipa_ids': [ipa], 'confirm': 'DELETE ALL IPAS'
        }).status_code == 400
        assert c.get('/api/overview', headers=AUTH).json()['ipas']


def test_bulk_rejects_queued_renewal_even_with_force(tmp_path):
    app = create_app(config(tmp_path))
    with TestClient(app) as c:
        ipa = upload(c, tmp_path / 'test.ipa')
        manager = app.state.manager
        tracked(manager, ipa)
        manager.db.exec(
            "INSERT INTO jobs (id,kind,state,input_json,created_at,updated_at) "
            "VALUES (?,?,?,?,?,?)",
            ('wait', 'renew', 'queued', json.dumps({'installation_id':'tracked'}),
             '2026-11-07T00:00:00+00:00', '2026-11-07T00:00:00+00:00')
        )
        r = c.post('/api/ipas/bulk-delete', headers=AUTH, json={
            'all': True, 'force': True, 'confirm': 'DELETE ALL IPAS'
        })
        assert r.status_code == 409
        assert manager.db.one('SELECT id FROM ipa WHERE id=?', (ipa,))
        assert manager.db.one('SELECT id FROM installations WHERE id=?', ('tracked',))


def test_ipa_alias_changes_visible_build_name_and_can_reset(tmp_path):
    app = create_app(config(tmp_path))
    with TestClient(app) as c:
        ipa = upload(c, tmp_path / 'test.ipa')
        assert c.patch(f'/api/ipas/{ipa}/label', json={'alias': 'TestFlight build #7'}).status_code == 401
        resp = c.patch(f'/api/ipas/{ipa}/label', headers=AUTH,
                       json={'alias': 'TestFlight build #7'})
        assert resp.status_code == 200
        assert resp.json()['alias'] == 'TestFlight build #7'
        assert c.get('/api/overview', headers=AUTH).json()['ipas'][0]['alias'] == 'TestFlight build #7'
        assert c.patch(f'/api/ipas/{ipa}/label', headers=AUTH,
                       json={'alias': ''}).json()['alias'] is None

def test_build_channel_validation_and_filter_metadata(tmp_path):
    app = create_app(config(tmp_path))
    with TestClient(app) as c:
        ipa = upload(c, tmp_path / "channel.ipa")
        url = f'/api/ipas/{ipa}/channel'
        assert c.patch(url, json={'channel': 'stable'}).status_code == 401
        assert c.patch(url, headers=AUTH, json={'channel': 'everything'}).status_code == 400
        assert c.patch(url, headers=AUTH, json={'channel': 'stable'}).json() == {
            'id': ipa, 'channel': 'stable'
        }
        assert c.get('/api/overview', headers=AUTH).json()['ipas'][0]['channel'] == 'stable'
        assert c.patch(url, headers=AUTH, json={'channel': 'unassigned'}).status_code == 200
