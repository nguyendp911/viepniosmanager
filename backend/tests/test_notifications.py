"""Opt-in private iPhone notifications. No real ntfy network requests."""
import asyncio
from datetime import datetime, timedelta, timezone

import requests
from fastapi.testclient import TestClient

from test_api import config
from viepn.api import create_app
from viepn.notifications import NotificationService
from viepn.service import Manager

AUTH = {"Authorization": "Bearer very-long-test-secret-token"}
ORIGIN = "http://127.0.0.1:8765"


class Result:
    def __init__(self, status_code=200):
        self.status_code = status_code


def test_disabled_by_default_and_requires_explicit_consent(tmp_path, monkeypatch):
    manager = Manager(config(tmp_path))
    seen = []
    monkeypatch.setattr(requests, "post", lambda *args, **kwargs: seen.append((args, kwargs)) or Result())
    settings = manager.notifications.settings()
    assert settings["enabled"] is False
    assert settings["topic"].startswith("viepn-")
    assert len(settings["topic"]) == 38
    assert manager.notifications.publish("sign_failed") is False
    assert seen == []

    try:
        manager.notifications.configure(True, False)
        assert False, "Consent is required"
    except ValueError:
        pass

    manager.notifications.configure(True, True)
    assert manager.notifications.publish("sign_failed", "job:a") is True
    assert manager.notifications.publish("sign_failed", "job:a") is False
    assert len(seen) == 1
    address = seen[0][0][0]
    assert address == "https://ntfy.sh/" + settings["topic"]
    assert "password" not in str(seen).lower()
    manager.notifications.configure(False)
    assert manager.notifications.publish("renewed", "job:b") is False


def test_failed_delivery_retries_without_marking_notification_sent(tmp_path, monkeypatch):
    manager = Manager(config(tmp_path))
    manager.notifications.configure(True, True)
    called = []
    def fake_post(*args, **kwargs):
        called.append(1)
        return Result(503 if len(called) == 1 else 200)
    monkeypatch.setattr(requests, "post", fake_post)
    assert manager.notifications.publish("expiry_soon", "expiry:one") is False
    assert manager.notifications.publish("expiry_soon", "expiry:one") is True
    assert manager.notifications.publish("expiry_soon", "expiry:one") is False
    assert len(called) == 2


def test_expiry_warning_once_per_expiration_and_no_private_names(tmp_path, monkeypatch):
    manager = Manager(config(tmp_path))
    manager.notifications.configure(True, True)
    calls = []
    def fake_post(*args, **kwargs):
        calls.append((args, kwargs))
        return Result()
    monkeypatch.setattr(requests, "post", fake_post)
    expiry = (datetime.now(timezone.utc) + timedelta(hours=20)).isoformat()
    manager.db.exec(
        "INSERT INTO installations(id,device_udid,bundle_id,source_ipa_id,"
        "current_ipa_id,expires_at,auto_renew,state,created_at)"
        " VALUES(?,?,?,?,?,?,?,?,?)",
        ("install-one", "udid-secret", "com.private.test", "source", "current",
         expiry, 1, "active", datetime.now(timezone.utc).isoformat())
    )
    assert asyncio.run(manager.expiry_alert_scan()) == 1
    assert asyncio.run(manager.expiry_alert_scan()) == 0
    assert len(calls) == 1
    published = calls[0][1]["data"].decode("utf-8")
    assert "udid-secret" not in published
    assert "com.private.test" not in published


def test_notification_routes_are_local_and_protected(tmp_path, monkeypatch):
    app = create_app(config(tmp_path))
    manager = app.state.manager
    monkeypatch.setattr(manager.notifications, "publish", lambda kind, key=None: True)
    with TestClient(app, base_url=ORIGIN, client=("127.0.0.1", 55000)) as client:
        assert client.get("/api/notifications/config").status_code == 401
        r = client.get("/api/notifications/config", headers=AUTH)
        assert r.status_code == 200
        assert r.json()["enabled"] is False
        assert client.post("/api/notifications/test", headers={**AUTH, "Origin": ORIGIN}).status_code == 409
        blocked = client.post("/api/notifications/config",
            headers={**AUTH, "Origin": "https://outside.example"},
            json={"enabled": True, "consent": True})
        assert blocked.status_code == 403
        denied = client.post("/api/notifications/config",
            headers={**AUTH, "Origin": ORIGIN},
            json={"enabled": True, "consent": False})
        assert denied.status_code == 400
        ok = client.post("/api/notifications/config",
            headers={**AUTH, "Origin": ORIGIN},
            json={"enabled": True, "consent": True})
        assert ok.status_code == 200
        assert client.post("/api/notifications/test",
            headers={**AUTH, "Origin": ORIGIN}).status_code == 200
