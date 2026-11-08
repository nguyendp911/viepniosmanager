"""ViePN Bluetooth proximity detection (not Apple usbmux pairing).

The iOS ViePN app advertises a private service only while the user enables
BLE in foreground. Windows Bleak central reads an ephemeral random UUID
characteristic; the UUID is associated to an authenticated HTTPS registration.
No API token/UDID/Apple session/password crosses Bluetooth.
"""
from __future__ import annotations

import asyncio
import uuid
from datetime import datetime, timedelta, timezone

from .db import Database, utcnow

SERVICE_UUID = "2a4e9a9d-5f50-42b9-86ba-92d2670979c3"
TOKEN_UUID = "2a4e9a9d-5f50-42b9-86ba-92d2670979c4"


def validate_uuid(value: str) -> str:
    try:
        return str(uuid.UUID(value))
    except (ValueError, TypeError, AttributeError) as exc:
        raise ValueError("Invalid device or Bluetooth session ID") from exc


def register(db: Database, device_id: str, name: str, token: str) -> dict:
    device_id = validate_uuid(device_id)
    token = validate_uuid(token)
    name = name.strip()
    if not name or len(name) > 64 or any(ord(ch) < 32 for ch in name):
        raise ValueError("Device name must contain 1-64 visible characters")
    existing = db.one("SELECT id FROM remote_devices WHERE id=?", (device_id,))
    if existing:
        db.exec("UPDATE remote_devices SET name=?,ble_token=?,seen_at=? WHERE id=?",
                (name, token, utcnow(), device_id))
    else:
        db.exec(
            "INSERT INTO remote_devices(id,name,ble_token,created_at,seen_at) VALUES(?,?,?,?,?)",
            (device_id, name, token, utcnow(), utcnow()),
        )
    return {"id": device_id, "registered": True}


def inventory(db: Database) -> list[dict]:
    now = datetime.now(timezone.utc)
    items = db.query("SELECT id,name,seen_at FROM remote_devices ORDER BY seen_at DESC")
    return [{
        **item,
        "online": ((now - datetime.fromisoformat(item["seen_at"])) < timedelta(minutes=3)),
        "connection": "tailscale",
        "apple_paired": False,
    } for item in items]


async def scan_nearby(db: Database, timeout: float = 7.0) -> dict:
    """Best-effort BLE proximity check, requires Windows Bluetooth + bleak.

    Only known, authenticated device IDs are shown. This is explicitly NOT a
    proof of cryptographic possession / secure Apple pairing or IPA install.
    """
    try:
        from bleak import BleakScanner, BleakClient
    except ImportError:
        return {"available": False, "nearby": [], "detail":
                "Thiếu Bleak trên Windows. Chạy windows/Enable-ViePN-Bluetooth.bat."}
    known = {x["ble_token"]: x for x in db.query(
        "SELECT id,name,ble_token FROM remote_devices"
    )}
    if not known:
        return {"available": True, "nearby": [], "detail":
                "Chưa có iPhone đăng ký qua Tailscale. Mở ViePN iOS và bật BLE."}
    try:
        scanned = await BleakScanner.discover(timeout=timeout, return_adv=True,
                                             service_uuids=[SERVICE_UUID])
    except (OSError, RuntimeError, asyncio.TimeoutError) as exc:
        return {"available": False, "nearby": [], "detail":
                "Không quét được Bluetooth Windows. Kiểm tra adapter và quyền Bluetooth."}

    found = []
    for _, (device, advertisement) in scanned.items():
        if SERVICE_UUID not in [str(x).lower() for x in advertisement.service_uuids]:
            continue
        try:
            async with BleakClient(device, timeout=5.0) as client:
                token = (await client.read_gatt_char(TOKEN_UUID)).decode("utf-8").strip()
            entry = known.get(validate_uuid(token))
            if entry and not any(existing["id"] == entry["id"] for existing in found):
                found.append({"id": entry["id"], "name": entry["name"],
                              "nearby": True, "connection": "bluetooth-ble"})
        except (OSError, RuntimeError, ValueError, UnicodeError, asyncio.TimeoutError):
            continue
    return {"available": True, "nearby": found,
            "detail": "BLE chỉ xác định iPhone ở gần; lệnh quản lý vẫn qua HTTPS Tailscale."}
