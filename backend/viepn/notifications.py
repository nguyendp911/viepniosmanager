"""Opt-in iPhone push alerts via the ntfy iOS app.

Free Apple Personal Team-signed builds cannot rely on APNs entitlements. ViePN
therefore uses the official ntfy service for *optional* push delivery to a
separate iPhone app. Publish only generic status (no Apple ID, IPA names, UDIDs,
passwords, URLs, pairing files, or account identifiers).

Never publish unless the Windows user explicitly enables external delivery.
An unguessable per-installation topic is a bearer secret, not an auth system.
"""
from __future__ import annotations

import json
import os
import secrets
import threading
from pathlib import Path

import requests

from .db import Database, utcnow

NTFY_HOST = "https://ntfy.sh"
ALLOWED_KINDS = {
    "expiry_soon": ("ViePN: sắp hết hạn", "Một ứng dụng sẽ hết hạn chữ ký trong vòng 48 giờ.", 4),
    "sign_failed": ("ViePN: tác vụ thất bại", "Một tác vụ ký, cài đặt hoặc gia hạn đã thất bại. Mở ViePN để xem chi tiết.", 4),
    "renewed": ("ViePN: gia hạn thành công", "Một ứng dụng đã gia hạn chữ ký thành công.", 3),
    "test": ("ViePN: thử thông báo", "Kết nối thông báo trên iPhone đang hoạt động.", 3),
}


class NotificationService:
    def __init__(self, root: Path, db: Database):
        self._file = root / "notifications.json"
        self.db = db
        self._lock = threading.RLock()

    def _read(self) -> dict:
        try:
            obj = json.loads(self._file.read_text(encoding="utf-8"))
        except (OSError, ValueError, TypeError):
            obj = {}
        topic = obj.get("topic")
        if not isinstance(topic, str) or not topic.startswith("viepn-") or len(topic) != 38:
            topic = "viepn-" + secrets.token_hex(16)
        return {"enabled": obj.get("enabled") is True, "topic": topic}

    def _write(self, payload: dict) -> None:
        self._file.parent.mkdir(parents=True, exist_ok=True)
        temp = self._file.with_name(self._file.name + "." + secrets.token_hex(8) + ".tmp")
        try:
            with temp.open("x", encoding="utf-8") as handle:
                os.chmod(temp, 0o600)
                json.dump(payload, handle)
            os.replace(temp, self._file)
        finally:
            temp.unlink(missing_ok=True)

    def settings(self) -> dict:
        """Only return to an authenticated browser running on Windows localhost."""
        with self._lock:
            data = self._read()
        return {
            "enabled": data["enabled"],
            "provider": "ntfy.sh",
            "topic": data["topic"],
            "subscribe_url": f'{NTFY_HOST}/{data["topic"]}',
            "third_party": True,
        }

    def configure(self, enabled: bool, consent: bool = False) -> dict:
        if enabled and not consent:
            raise ValueError("Phải đồng ý dùng dịch vụ ntfy.sh trước khi bật thông báo.")
        with self._lock:
            obj = self._read()
            obj["enabled"] = bool(enabled)
            self._write(obj)
        return self.settings()

    def publish(self, kind: str, key: str | None = None) -> bool:
        """Best effort; duplicate suppression is committed only on HTTP success.

        Never change signing/renewal outcomes if the external notification server
        is unavailable.
        """
        if kind not in ALLOWED_KINDS:
            raise ValueError("Unknown notification event")
        with self._lock:
            config = self._read()
        if not config["enabled"]:
            return False
        if key and self.db.one("SELECT id FROM notification_sent WHERE id=?", (key,)):
            return False

        title, message, priority = ALLOWED_KINDS[kind]
        try:
            response = requests.post(
                f'{NTFY_HOST}/{config["topic"]}',
                headers={"Title": title, "Priority": str(priority),
                         "Content-Type": "text/plain; charset=utf-8",
                         "Cache": "no"},
                data=message.encode("utf-8"), timeout=8,
                allow_redirects=False,
            )
            if response.status_code not in (200, 201, 202):
                return False
            if key:
                self.db.exec(
                    "INSERT OR IGNORE INTO notification_sent (id,created_at) VALUES (?,?)",
                    (key, utcnow()),
                )
            return True
        except (requests.RequestException, OSError):
            return False
