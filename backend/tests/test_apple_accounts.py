"""Safety tests for loopback Apple account management."""
from fastapi.testclient import TestClient
from test_api import config
from viepn.api import create_app
from viepn.apple_auth import AppleAuthFlow

AUTH = {"Authorization": "Bearer very-long-test-secret-token"}
ORIGIN = "http://127.0.0.1:8765"

def local_client(app):
    return TestClient(app, base_url=ORIGIN, client=("127.0.0.1", 55000))

def test_apple_account_endpoints_require_localhost_and_auth(tmp_path):
    with local_client(create_app(config(tmp_path))) as client:
        assert client.get("/api/apple/accounts").status_code == 401
        assert client.get("/api/apple/accounts", headers=AUTH).status_code == 200
        assert client.post("/api/apple/auth/cancel", headers=AUTH).status_code == 403
        wrong = {**AUTH, "Origin": "https://other.example"}
        assert client.post("/api/apple/auth/cancel", headers=wrong).status_code == 403

def test_apple_controls_forbidden_on_lan_bound_server(tmp_path):
    cfg = config(tmp_path)
    cfg.host = "0.0.0.0"
    with local_client(create_app(cfg)) as client:
        assert client.get("/api/apple/accounts", headers=AUTH).status_code == 403

def test_account_switch_and_logout_local_api(tmp_path, monkeypatch):
    monkeypatch.setattr(AppleAuthFlow, "switch", lambda self, email:
                        {"status": "active", "email": email})
    monkeypatch.setattr(AppleAuthFlow, "logout", lambda self, email:
                        {"status": "signed_out", "removed": [email] if email else [],
                         "active": None})
    headers = {**AUTH, "Origin": ORIGIN}
    with local_client(create_app(config(tmp_path))) as client:
        switch = client.post("/api/apple/auth/switch", headers=headers,
                             json={"email": "person@example.com"})
        assert switch.status_code == 200
        assert switch.json()["email"] == "person@example.com"
        logout = client.post("/api/apple/auth/logout", headers=headers,
                             json={"email": "person@example.com"})
        assert logout.status_code == 200
        assert logout.json()["status"] == "signed_out"
