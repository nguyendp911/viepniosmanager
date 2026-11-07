"""Regression tests: pymobiledevice3 reports Identifier instead of udid."""
import json
import pytest
from fastapi.testclient import TestClient
from test_api import config
from viepn import tools
from viepn.api import create_app

AUTH = {"Authorization": "Bearer very-long-test-secret-token"}


@pytest.mark.parametrize("payload,expected", [
    ([{"Identifier": "00008030-00123456789ABCDE", "DeviceName": "iPhone 12",
       "ConnectionType": "USB"}],
     [{"udid": "00008030-00123456789ABCDE", "name": "iPhone 12"}]),
    ([{"UniqueDeviceID": "00008030-ABCDEF1234567890", "DeviceName": "iPhone 13"}],
     [{"udid": "00008030-ABCDEF1234567890", "name": "iPhone 13"}]),
    ([{"DeviceID": 7, "Properties": {
        "SerialNumber": "00008030-0011223344556677", "DeviceName": "USB iPhone"}}],
     [{"udid": "00008030-0011223344556677", "name": "USB iPhone"}]),
    ([{"udid": "00008030-0011223344556677", "name": "Old"}],
     [{"udid": "00008030-0011223344556677", "name": "Old"}]),
    ([], []),
])
def test_list_normalized(monkeypatch, payload, expected):
    monkeypatch.setattr(tools, "run", lambda *a, **k: json.dumps(payload))
    result = tools.connected_devices()
    assert [{key: d[key] for key in ("udid", "name")} for d in result] == expected


def test_device_api_returns_normalized_udid_and_requires_auth(tmp_path, monkeypatch):
    monkeypatch.setattr(
        tools, "run", lambda *a, **k: json.dumps([
            {"Identifier": "00008030-00123456789ABCDE", "DeviceName": "iPhone 12"}])
    )
    with TestClient(create_app(config(tmp_path))) as client:
        assert client.get("/api/devices").status_code == 401
        response = client.get("/api/devices", headers=AUTH)
        assert response.status_code == 200
        assert response.json()["devices"][0]["udid"] == "00008030-00123456789ABCDE"


def test_incompatible_nonempty_list_produces_error_not_empty(monkeypatch):
    monkeypatch.setattr(tools, "run", lambda *a, **k: json.dumps([{"Other": True}]))
    with pytest.raises(tools.ExternalToolError):
        tools.connected_devices()
