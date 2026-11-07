"""Browser-facing Apple Account session management, local Windows only.

Passwords are transient, kept only in process memory during a 2FA challenge,
never stored in SQLite, logged or returned to the browser. This intentionally
does not expose an Apple sign-in API to LAN/WAN clients.
"""
from __future__ import annotations

import secrets
import threading
import time
from dataclasses import dataclass

from .applekit import gsa
from .native_sign import _apple_environment, configure_anisette, NativeSigningError

PENDING_SECONDS = 300
MAX_2FA_ATTEMPTS = 3


@dataclass
class Pending:
    email: str
    password: str
    challenge: str
    method: str
    expires: float
    attempts: int = 0


class AppleAuthFlow:
    def __init__(self):
        self._lock = threading.RLock()
        self._pending: Pending | None = None

    def _expire(self) -> None:
        if self._pending is not None and time.monotonic() >= self._pending.expires:
            self._clear_pending()

    def _clear_pending(self) -> None:
        self._pending = None
        # Remove the sensitive temporary Apple GSA challenge from disk too.
        from .applekit import paths
        paths.pending_2fa_file().unlink(missing_ok=True)

    def status(self) -> dict:
        with self._lock:
            self._expire()
            data = gsa.accounts()
            return {
                "accounts": [
                    {
                        "email": a["email"],
                        "team_id": a.get("team_id"),
                        "active": bool(a.get("active")),
                        "has_auth_token": bool(a.get("has_auth_token")),
                    }
                    for a in data["accounts"]
                ],
                "active": data.get("active"),
                "pending_2fa": self._pending is not None,
            }

    def configure(self, mode: str, server: str | None, consent: bool) -> dict:
        if mode not in ("private", "community"):
            raise ValueError("Invalid anisette mode")
        if mode == "community" and not consent:
            raise ValueError("Consent required before using a third-party anisette provider")
        with self._lock:
            configure_anisette(
                server if mode == "private" else None,
                allow_community=(mode == "community" and consent),
            )
        return {"configured": True, "external_provider": mode == "community"}

    def begin(self, email: str, password: str) -> dict:
        if not email or "@" not in email or len(email) > 254 or not password:
            raise ValueError("Enter a valid Apple ID and password")
        with self._lock:
            self._expire()
            if self._pending is not None:
                self._clear_pending()
            _apple_environment()
            try:
                response = gsa.begin_login(email, password)
            except Exception:
                # Do not expose raw Apple errors, which may contain private data.
                self._clear_pending()
                raise RuntimeError("Apple login failed. Check credentials, anisette and connectivity") from None

            kind = response.get("status")
            if kind == "2fa_required":
                challenge = secrets.token_urlsafe(32)
                self._pending = Pending(
                    email=email, password=password, challenge=challenge,
                    method=str(response.get("method") or "trusteddevice"),
                    expires=time.monotonic() + PENDING_SECONDS,
                )
                return {"status": "2fa_required", "challenge": challenge,
                        "method": self._pending.method, "expires_in": PENDING_SECONDS}
            if kind != "authenticated":
                self._clear_pending()
                raise RuntimeError("Apple did not confirm authentication")
            return {"status": "authenticated"}

    def verify(self, challenge: str, code: str) -> dict:
        if len(code) != 6 or not code.isascii() or not code.isdecimal():
            raise ValueError("Enter a six-digit verification code")
        with self._lock:
            self._expire()
            pending = self._pending
            if pending is None or not secrets.compare_digest(pending.challenge, challenge):
                raise ValueError("Challenge is missing or expired; sign in again")
            pending.attempts += 1
            try:
                result = gsa.complete_2fa(pending.email, pending.password, code)
            except Exception:
                if pending.attempts >= MAX_2FA_ATTEMPTS:
                    self._clear_pending()
                    raise RuntimeError("Verification failed too many times; sign in again") from None
                raise RuntimeError("Apple did not accept the verification. Try again") from None
            if result.get("status") != "authenticated":
                self._clear_pending()
                raise RuntimeError("Apple did not complete authentication")
            self._clear_pending()
            return {"status": "authenticated"}

    def switch(self, email: str) -> dict:
        with self._lock:
            result = gsa.use_account(email)
            return {"status": "active", "email": result["email"]}

    def logout(self, email: str | None = None) -> dict:
        with self._lock:
            self._clear_pending()
            result = gsa.logout(email)
            return {"status": "signed_out",
                    "removed": result.get("removed") or [],
                    "active": result.get("active")}

    def cancel(self) -> dict:
        with self._lock:
            self._clear_pending()
            return {"cancelled": True}
