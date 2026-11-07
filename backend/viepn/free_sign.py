"""One-time LAN IPA transfer for SideStore.

This module NEVER handles Apple Account credentials or signing keys. Share links
are random bearer capabilities, stored only in memory, and expire after ten
minutes. A successful GET consumes the capability.
"""
from __future__ import annotations

import secrets
import threading
import time
from pathlib import Path


class ShareStore:
    def __init__(self, ttl_seconds: int = 600):
        self.ttl_seconds = ttl_seconds
        self._links: dict[str, tuple[str, str, float]] = {}
        self._lock = threading.Lock()

    def create(self, ipa_path: str | Path, name: str) -> tuple[str, int]:
        path = Path(ipa_path)
        if not path.is_file() or path.suffix.lower() != '.ipa':
            raise ValueError('IPA is missing')
        token = secrets.token_urlsafe(32)
        now = time.monotonic()
        with self._lock:
            self._links = {k: value for k, value in self._links.items()
                           if value[2] > now}
            self._links[token] = (str(path), name, now + self.ttl_seconds)
        return token, self.ttl_seconds

    def take(self, token: str) -> tuple[Path, str] | None:
        if len(token) > 128 or len(token) < 32:
            return None
        with self._lock:
            value = self._links.pop(token, None)
        if not value or value[2] <= time.monotonic():
            return None
        path = Path(value[0])
        if not path.is_file():
            return None
        return path, value[1]
