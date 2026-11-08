"""ViePN remote registry / Bluetooth security and no-Apple-pairing guarantees."""
import asyncio
import sys
import types
from datetime import datetime, timedelta, timezone

from fastapi.testclient import TestClient
from test_api import config
from viepn.api import create_app
from viepn.remote_devices import SERVICE_UUID, TOKEN_UUID, inventory, scan_nearby
from viepn.remote_gateway import allowed

AUTH = {"Authorization": "Bearer very-long-test-secret-token"}
DID = "a75deed7-1fb8-4f0e-af15-112233445566"
BT = "b75deed7-1fb8-4f0e-af15-112233445566"


def test_remote_registry_requires_token_and_is_not_apple_pairing(tmp_path):
    app = create_app(config(tmp_path))
    with TestClient(app) as client:
        payload = {"device_id": DID, "name": "ViePN iPhone",
                   "ble_token": BT}
        assert client.post("/api/remote/devices/register", json=payload).status_code == 401
        response = client.post("/api/remote/devices/register", headers=AUTH, json=payload)
        assert response.status_code == 200, response.text
        result = client.get("/api/remote/devices", headers=AUTH).json()["devices"]
        assert len(result) == 1
        assert result[0]["id"] == DID
        assert result[0]["online"] is True
        assert result[0]["apple_paired"] is False
        assert "ble_token" not in result[0]
        assert client.post("/api/remote/devices/register", headers=AUTH, json={
            **payload, "ble_token": "not-a-uuid"
        }).status_code == 400
        assert client.post("/api/remote/devices/register", headers=AUTH, json={
            **payload, "name": "bad\nname"
        }).status_code in (400, 422)


def test_registration_updates_existing_device_without_duplicates(tmp_path):
    app = create_app(config(tmp_path))
    with TestClient(app) as client:
        for name in ("First", "Second"):
            r=client.post("/api/remote/devices/register", headers=AUTH,
                json={"device_id": DID, "name": name, "ble_token": BT})
            assert r.status_code == 200
        found=client.get("/api/remote/devices", headers=AUTH).json()["devices"]
        assert len(found)==1
        assert found[0]["name"]=="Second"
        assert app.state.manager.db.one("SELECT ble_token FROM remote_devices WHERE id=?", (DID,))["ble_token"]==BT


def test_gateway_whitelist_exact_remote_paths():
    assert allowed("GET", "/api/remote/devices")
    assert allowed("POST", "/api/remote/devices/register")
    assert allowed("POST", "/api/ble/scan")
    assert not allowed("GET", "/api/ble/scan")
    assert not allowed("DELETE", "/api/remote/devices")
    assert not allowed("GET", "/api/apple/auth/login")


def test_ble_recognizes_only_authenticated_registered_token(tmp_path, monkeypatch):
    app = create_app(config(tmp_path))
    manager = app.state.manager
    from viepn.remote_devices import register
    register(manager.db, DID, "My iPhone", BT)

    class FakeAdvertisement:
        service_uuids = [SERVICE_UUID]
    class FakeScanner:
        @staticmethod
        async def discover(**kwargs):
            return {"test": (types.SimpleNamespace(address="fake"), FakeAdvertisement())}
    class FakeClient:
        def __init__(self, device, **kwargs):
            pass
        async def __aenter__(self): return self
        async def __aexit__(self, *args): pass
        async def read_gatt_char(self, uuid):
            assert uuid == TOKEN_UUID
            return BT.encode("utf-8")

    monkeypatch.setitem(sys.modules, "bleak", types.SimpleNamespace(
        BleakScanner=FakeScanner, BleakClient=FakeClient))
    result = asyncio.run(scan_nearby(manager.db, timeout=0.1))
    assert result["available"]
    assert result["nearby"][0]["id"] == DID
    assert "ble_token" not in result["nearby"][0]
    assert "address" not in result["nearby"][0]


def test_remote_offline_is_time_based(tmp_path):
    app = create_app(config(tmp_path))
    from viepn.remote_devices import register
    register(app.state.manager.db, DID, "My iPhone", BT)
    old=(datetime.now(timezone.utc)-timedelta(hours=2)).isoformat()
    app.state.manager.db.exec("UPDATE remote_devices SET seen_at=? WHERE id=?", (old,DID))
    assert inventory(app.state.manager.db)[0]["online"] is False
