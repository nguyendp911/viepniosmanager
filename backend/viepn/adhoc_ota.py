"""Private Tailscale Ad Hoc OTA installation links.

A single-use manifest capability and a bounded-download IPA capability give
iOS the short-lived HTTPS URLs required by itms-services. The session must
never grant general API access. The server *never* claims cryptographic app
signature verification: Apple decides if the device trusts the installed IPA.
"""
from __future__ import annotations

import plistlib
import re
import secrets
import threading
import time
import zipfile
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import quote, urlsplit

from .certificate_vault import inspect_pair, signing_material, _profile_plist
from .ipa import inspect_ipa, parse_provision, supports_bundle

_TTL = 600


def validate_base(url: str) -> str:
    p = urlsplit(url.strip())
    if (p.scheme != "https" or not p.hostname or
            not p.hostname.lower().endswith(".ts.net") or
            p.username or p.password or p.query or p.fragment or
            p.path not in ("", "/") or p.port not in (None, 443)):
        raise ValueError("OTA requires an HTTPS Tailscale Serve .ts.net address")
    return "https://" + p.hostname.lower()


def inspect_adhoc_ipa(ipa_path: Path, device_index: int, vault_root: Path) -> dict:
    """Fail closed unless matching local Distribution P12/profile and Ad Hoc IPA."""
    metadata = inspect_ipa(ipa_path)
    if not metadata["signed_candidate"]:
        raise ValueError("IPA does not include an embedded provisioning profile")
    p12_path, profile_path, password = signing_material(vault_root)
    with zipfile.ZipFile(ipa_path) as z:
        main_infos = [n for n in z.namelist()
                      if re.fullmatch(r"Payload/[^/]+\.app/Info\.plist", n)]
        if len(main_infos) != 1:
            raise ValueError("IPA must contain one main app")
        root = main_infos[0].removesuffix("Info.plist")
        embedded = z.read(root + "embedded.mobileprovision")
        certificate_info = inspect_pair(p12_path.read_bytes(), embedded, password)
        profile_info = parse_provision(embedded)
        if not supports_bundle(profile_info["bundle_pattern"], metadata["bundle_id"]):
            raise ValueError("IPA bundle ID is not authorized by its provisioning profile")
        if not isinstance(device_index, int) or isinstance(device_index, bool) or not (
            0 <= device_index < len(profile_info["devices"])
        ):
            raise ValueError("Selected iPhone is not registered in this Ad Hoc profile")
        device = profile_info["devices"][device_index]
        # Verify current vault profile authorizes exactly this IPA/team/device.
        vault_info = parse_provision(profile_path.read_bytes())
        if (vault_info["team"] != profile_info["team"]
                or not supports_bundle(vault_info["bundle_pattern"], metadata["bundle_id"])
                or device not in vault_info["devices"]):
            raise ValueError("Imported P12/profile do not authorize this IPA and iPhone")
        for info_path in z.namelist():
            if not re.fullmatch(r"Payload/[^/]+\.app/PlugIns/[^/]+\.appex/Info\.plist", info_path):
                continue
            extension_root = info_path.removesuffix("Info.plist")
            provision_path = extension_root + "embedded.mobileprovision"
            if provision_path not in z.namelist():
                raise ValueError("Extension lacks its own Ad Hoc provisioning profile")
            ext_info = plistlib.loads(z.read(info_path))
            ext_bundle = str(ext_info.get("CFBundleIdentifier") or "")
            ext_blob = z.read(provision_path)
            ext_cert = inspect_pair(p12_path.read_bytes(), ext_blob, password)
            ext_profile = parse_provision(ext_blob)
            if (not supports_bundle(ext_profile["bundle_pattern"], ext_bundle)
                    or device not in ext_profile["devices"]
                    or ext_profile["team"] != profile_info["team"]):
                raise ValueError("Keyboard/other extension profile does not match this device")
        expires = datetime.fromisoformat(profile_info["expires_at"])
        if expires <= datetime.now(timezone.utc):
            raise ValueError("Ad Hoc profile is expired")
        return {
            "bundle_id": metadata["bundle_id"],
            "name": metadata["name"],
            "version": metadata["version"],
            "device_index": device_index,
            "device_suffix": device[-6:],
            "expires_at": certificate_info["expires_at"],
        }


class OTAShareStore:
    def __init__(self, ttl_seconds: int = _TTL):
        self.ttl_seconds = ttl_seconds
        self._lock = threading.Lock()
        self._sessions: dict[str, dict] = {}
        self._ipa_tokens: dict[str, str] = {}

    def create(self, path: Path, base_url: str, details: dict) -> dict:
        base = validate_base(base_url)
        if not path.is_file() or path.suffix.lower() != ".ipa":
            raise ValueError("Signed IPA not found")
        manifest_token = secrets.token_urlsafe(32)
        ipa_token = secrets.token_urlsafe(32)
        expires = time.monotonic() + self.ttl_seconds
        with self._lock:
            self._sessions = {k: v for k, v in self._sessions.items() if v["expires"] > time.monotonic()}
            self._ipa_tokens = {k: v for k, v in self._ipa_tokens.items() if v in self._sessions}
            self._sessions[manifest_token] = {
                "ipa_token": ipa_token,
                "path": str(path),
                "details": details.copy(),
                "base": base,
                "expires": expires,
                "manifest_reads": 0,
                "ipa_reads": 0,
            }
            self._ipa_tokens[ipa_token] = manifest_token
        manifest_url = base + "/api/ota/manifest/" + manifest_token
        return {
            "install_url": "itms-services://?action=download-manifest&url=" + quote(manifest_url, safe=""),
            "manifest_url": manifest_url,
            "expires_in_seconds": self.ttl_seconds,
            "device_suffix": details["device_suffix"],
            "bundle_id": details["bundle_id"],
            "note": "iOS validates certificate, provisioning and app signature during installation.",
        }

    def manifest(self, token: str) -> bytes | None:
        with self._lock:
            session = self._sessions.get(token)
            if not session or session["expires"] <= time.monotonic() or session["manifest_reads"] >= 5:
                return None
            session["manifest_reads"] += 1
            url = session["base"] + "/api/ota/package/" + session["ipa_token"]
            info = session["details"]
        return plistlib.dumps({
            "items": [{
                "assets": [{"kind": "software-package", "url": url}],
                "metadata": {
                    "bundle-identifier": info["bundle_id"],
                    "bundle-version": info["version"] or "1.0",
                    "kind": "software",
                    "title": info["name"][:100],
                },
            }]
        }, fmt=plistlib.FMT_XML)

    def package(self, token: str) -> Path | None:
        with self._lock:
            primary = self._ipa_tokens.get(token)
            session = self._sessions.get(primary) if primary else None
            if not session or session["expires"] <= time.monotonic() or session["ipa_reads"] >= 12:
                return None
            session["ipa_reads"] += 1
            path = Path(session["path"])
        return path if path.is_file() else None
