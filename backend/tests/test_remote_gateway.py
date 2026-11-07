"""Remote gateway never forwards credential/session management APIs."""
import httpx
from fastapi.testclient import TestClient

from test_api import config
from viepn.remote_gateway import create_remote_app, allowed

BEARER = {"Authorization": "Bearer very-long-test-secret-token"}


def test_allowlist_is_deny_by_default():
    assert allowed("GET", "/")
    assert allowed("GET", "/api/health")
    assert allowed("POST", "/api/apple/install")
    assert allowed("POST", "/api/apple/refresh-all")
    assert allowed("DELETE", "/api/ipas/0123456789abcde")
    for path in (
        "/api/apple/accounts",
        "/api/apple/auth/login",
        "/api/apple/auth/verify",
        "/api/apple/auth/logout",
        "/api/apple/auth/switch",
        "/api/free/download/secret",
        "/api/not-real",
    ):
        assert not allowed("GET", path)
        assert not allowed("POST", path)
    assert not allowed("DELETE", "/api/overview")


def test_remote_requires_token_and_scrubs_forward_headers(tmp_path):
    seen = []
    def handler(request):
        seen.append(request)
        return httpx.Response(200, json={"ok": True},
                              headers={"content-type": "application/json",
                                       "content-security-policy": "default-src 'self'"})
    proxy = create_remote_app(config(tmp_path), transport=httpx.MockTransport(handler))
    with TestClient(proxy) as client:
        assert client.get("/api/overview").status_code == 401
        assert client.get("/api/apple/auth/login", headers=BEARER).status_code == 404
        assert client.post("/api/apple/auth/login", headers=BEARER).status_code == 404
        r = client.get("/api/overview", headers={
            **BEARER, "Cookie": "session=bad",
            "X-Forwarded-For": "203.0.113.8",
            "Host": "spoofed.example",
        })
        assert r.status_code == 200
        assert r.headers.get("Content-Security-Policy") == "default-src 'self'"
        assert seen[-1].headers["authorization"] == BEARER["Authorization"]
        assert "cookie" not in seen[-1].headers
        assert "x-forwarded-for" not in seen[-1].headers
        assert seen[-1].url.host == "127.0.0.1"
        assert client.get("/").status_code == 200
        assert client.get("/api/health").status_code == 200


def test_remote_can_forward_signed_job_requests(tmp_path):
    def handler(request):
        return httpx.Response(200, json={"job_id": "dummy-test-job"})
    with TestClient(create_remote_app(config(tmp_path),
                                     transport=httpx.MockTransport(handler))) as client:
        response = client.post("/api/apple/install", headers=BEARER,
                               json={"ipa_id": "abc", "udid": "123"})
        assert response.status_code == 200
        assert response.json()["job_id"] == "dummy-test-job"
        assert client.post("/api/apple/auth/verify", headers=BEARER,
                           json={"code": "123456"}).status_code == 404

def test_new_remote_allowlist_blocks_backup_and_apple_credentials():
    from viepn.remote_gateway import allowed
    assert allowed("GET", "/api/doctor")
    assert allowed("PATCH", "/api/ipas/abcdef123456/channel")
    assert allowed("POST", "/api/jobs/0123456789abcdef/retry")
    for method, path in [
        ("POST", "/api/backups"), ("GET", "/api/backups"),
        ("GET", "/api/backups/ViePN-test.zip"),
        ("POST", "/api/apple/auth/login"),
        ("POST", "/api/notifications/config"),
    ]:
        assert not allowed(method, path)
