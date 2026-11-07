from pathlib import Path
from fastapi.testclient import TestClient

from viepn.api import create_app
from viepn.config import Settings
from test_ipa import sample_ipa


def config(tmp_path):
    return Settings(root=tmp_path, token='very-long-test-secret-token',
                    host='127.0.0.1', port=8765, signer='zsign', signing_p12='',
                    signing_profile='', signing_password='', renewal_hours=48,
                    scan_minutes=30, max_upload_mb=20)


def test_authenticated_endpoints(tmp_path):
    app = create_app(config(tmp_path))
    with TestClient(app) as client:
        assert client.get('/api/health').json()['ok'] is True
        assert client.get('/api/overview').status_code == 401
        assert client.get('/api/overview', headers={'Authorization': 'Bearer wrong'}).status_code == 401
        headers = {'Authorization': 'Bearer very-long-test-secret-token'}
        assert client.get('/api/overview', headers=headers).status_code == 200
        filename = sample_ipa(tmp_path / 'test.ipa')
        with filename.open('rb') as f:
            res = client.post('/api/ipas', headers=headers,
                              files={'file': ('test.ipa', f, 'application/octet-stream')})
        assert res.status_code == 200, res.text
        ipa_id = res.json()['id']
        assert client.get('/api/overview', headers=headers).json()['ipas'][0]['id'] == ipa_id
        assert client.get(f'/api/ipa/{ipa_id}/download', headers=headers).status_code == 200
        invalid = client.post('/api/install', headers=headers, json={'ipa_id': ipa_id,
                               'udid': '!invalid'})
        assert invalid.status_code == 400
        assert client.post('/api/renew/check', headers=headers).status_code == 200


def test_reject_invalid_upload(tmp_path):
    with TestClient(create_app(config(tmp_path))) as client:
        h = {'Authorization': 'Bearer very-long-test-secret-token'}
        bad = client.post('/api/ipas', headers=h,
                          files={'file': ('bad.ipa', b'broken', 'application/octet-stream')})
        assert bad.status_code == 400
        wrong = client.post('/api/ipas', headers=h,
                            files={'file': ('bad.txt', b'ok', 'text/plain')})
        assert wrong.status_code == 400
