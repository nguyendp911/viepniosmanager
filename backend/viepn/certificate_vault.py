"""Local-only certificate vault for ViePN Ad Hoc signing.

Import is deliberately a Windows command line action, not an HTTP upload.
Apple signing private keys never enter GitHub, Remote Gateway, iOS, or the
dashboard. The P12 remains encrypted with its existing password; that password
is protected using Windows DPAPI under the logged-in Windows user account.
"""
from __future__ import annotations

import json
import os
import plistlib
import re
import tempfile
from datetime import datetime, timezone
from pathlib import Path

from cryptography import x509
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.serialization import (
    Encoding, PublicFormat, pkcs12,
)

from .config import app_data
from .ipa import parse_provision, supports_bundle

P12_MAX = 2 * 1024 * 1024
PROFILE_MAX = 2 * 1024 * 1024


def _profile_plist(blob: bytes) -> dict:
    match = re.search(rb'<\?xml\b.*?</plist\s*>', blob, re.DOTALL)
    if not match:
        raise ValueError("Provisioning profile has no embedded plist")
    obj = plistlib.loads(match.group(0))
    if not isinstance(obj, dict):
        raise ValueError("Invalid provisioning profile")
    return obj


def inspect_pair(p12: bytes, profile_blob: bytes, password: str) -> dict:
    """Validate P12 key/certificate match and Ad Hoc profile scope.

    The plist is useful for matching and preflight, but not proof that Apple's
    CMS signature or the app's executable code signature is trusted.
    """
    if len(p12) > P12_MAX or len(profile_blob) > PROFILE_MAX or not p12 or not profile_blob:
        raise ValueError("Certificate/profile exceeds import size limits")
    try:
        private_key, cert, _ = pkcs12.load_key_and_certificates(
            p12, password.encode('utf-8')
        )
    except (ValueError, TypeError):
        raise ValueError("P12 password is incorrect or the file is invalid") from None
    if private_key is None or cert is None:
        raise ValueError("P12 must contain both a private key and a certificate")
    if private_key.public_key().public_bytes(Encoding.DER, PublicFormat.SubjectPublicKeyInfo) != (
        cert.public_key().public_bytes(Encoding.DER, PublicFormat.SubjectPublicKeyInfo)
    ):
        raise ValueError("P12 private key does not match its certificate")
    profile = _profile_plist(profile_blob)
    certs = profile.get("DeveloperCertificates") or []
    if not any(
        isinstance(item, bytes) and x509.load_der_x509_certificate(item).fingerprint(
            hashes.SHA256()
        ) == cert.fingerprint(hashes.SHA256())
        for item in certs
    ):
        raise ValueError("P12 certificate is NOT included in this provisioning profile")
    info = parse_provision(profile_blob)
    expires = datetime.fromisoformat(info["expires_at"]) if info["expires_at"] else None
    now = datetime.now(timezone.utc)
    cert_expiry = cert.not_valid_after_utc
    if expires is None or expires <= now or cert_expiry <= now:
        raise ValueError("Certificate or provisioning profile has expired")
    if info["team"] == "" or not info["bundle_pattern"]:
        raise ValueError("Profile has no Team ID or bundle identifier")
    ents = profile.get("Entitlements") or {}
    devices = info["devices"]
    if profile.get("ProvisionsAllDevices") or not devices or ents.get("get-task-allow") is not False:
        raise ValueError("Only Ad Hoc Distribution device-scoped profiles are accepted")
    if not all(isinstance(x, str) and re.fullmatch(r"[0-9A-Fa-f-]{16,64}", x) for x in devices):
        raise ValueError("Invalid registered device identifier in profile")
    return {
        "mode": "ad_hoc", "team": info["team"],
        "bundle_pattern": info["bundle_pattern"], "devices_count": len(devices),
        "expires_at": min(expires, cert_expiry).isoformat(),
        "certificate_expires_at": cert_expiry.isoformat(),
        "certificate_name": cert.subject.rfc4514_string()[:160],
        "matched": True, "cms_signature_verified": False,
    }


def _protect_windows(data: bytes) -> bytes:
    if os.name != 'nt':
        raise RuntimeError("DPAPI key storage requires Windows")
    import ctypes
    from ctypes import wintypes
    class BLOB(ctypes.Structure):
        _fields_ = [("cbData", wintypes.DWORD), ("pbData", ctypes.POINTER(ctypes.c_ubyte))]
    input_data = ctypes.create_string_buffer(data)
    original = BLOB(len(data), ctypes.cast(input_data, ctypes.POINTER(ctypes.c_ubyte)))
    output = BLOB()
    crypt32 = ctypes.windll.crypt32
    if not crypt32.CryptProtectData(ctypes.byref(original), "ViePN certificate vault",
                                    None, None, None, 0x01, ctypes.byref(output)):
        raise OSError("Windows DPAPI encryption failed")
    try:
        return ctypes.string_at(output.pbData, output.cbData)
    finally:
        ctypes.windll.kernel32.LocalFree(ctypes.cast(output.pbData, ctypes.c_void_p))


def _unprotect_windows(data: bytes) -> bytes:
    if os.name != 'nt':
        raise RuntimeError("DPAPI key storage requires Windows")
    import ctypes
    from ctypes import wintypes
    class BLOB(ctypes.Structure):
        _fields_ = [("cbData", wintypes.DWORD), ("pbData", ctypes.POINTER(ctypes.c_ubyte))]
    input_data = ctypes.create_string_buffer(data)
    original = BLOB(len(data), ctypes.cast(input_data, ctypes.POINTER(ctypes.c_ubyte)))
    output = BLOB()
    if not ctypes.windll.crypt32.CryptUnprotectData(
        ctypes.byref(original), None, None, None, None, 0x01, ctypes.byref(output)
    ):
        raise OSError("Windows DPAPI decryption failed for this Windows account")
    try:
        return ctypes.string_at(output.pbData, output.cbData)
    finally:
        ctypes.windll.kernel32.LocalFree(ctypes.cast(output.pbData, ctypes.c_void_p))


def vault_dir(root: Path | None = None) -> Path:
    return (root or app_data()) / "certificates"


def import_pair(p12_file: Path, profile_file: Path, password: str,
                root: Path | None = None) -> dict:
    if os.name != 'nt':
        raise RuntimeError("Certificate import is Windows-only to protect the P12 password using DPAPI")
    root = root or app_data()
    p12 = p12_file.read_bytes()
    profile = profile_file.read_bytes()
    result = inspect_pair(p12, profile, password)
    folder = vault_dir(root)
    folder.mkdir(parents=True, exist_ok=True)
    # No embedded secret, no private key or P12 material in metadata.
    sealed = _protect_windows(password.encode('utf-8'))
    files = {"certificate.p12": p12, "profile.mobileprovision": profile,
             "password.dpapi": sealed, "metadata.json": json.dumps(result).encode("utf-8")}
    # Stage under the data root, replace only after validation succeeds.
    for name, blob in files.items():
        with tempfile.NamedTemporaryFile(dir=folder, delete=False) as tmp:
            tmp.write(blob)
            tmp_name = tmp.name
        os.replace(tmp_name, folder / name)
    return result


def metadata(root: Path | None = None) -> dict:
    path = vault_dir(root) / "metadata.json"
    if not path.is_file():
        return {"configured": False, "signing_mode": "not_configured"}
    data = json.loads(path.read_text(encoding="utf-8"))
    return {"configured": True, "signing_mode": "ad_hoc", **data}


def signing_material(root: Path | None = None) -> tuple[Path, Path, str]:
    folder = vault_dir(root)
    p12 = folder / "certificate.p12"
    profile = folder / "profile.mobileprovision"
    pwd = folder / "password.dpapi"
    if not (p12.is_file() and profile.is_file() and pwd.is_file()):
        raise ValueError("Import an Ad Hoc P12 and matching profile locally first")
    password = _unprotect_windows(pwd.read_bytes()).decode('utf-8')
    inspect_pair(p12.read_bytes(), profile.read_bytes(), password)
    return p12, profile, password


def preflight(root: Path, bundle: str, udid: str) -> dict:
    p12, profile, password = signing_material(root)
    info = parse_provision(profile.read_bytes())
    if not supports_bundle(info["bundle_pattern"], bundle):
        raise ValueError("Ad Hoc profile does not allow this bundle ID")
    if udid not in info["devices"]:
        raise ValueError("This iPhone UDID is not included in the Ad Hoc profile")
    return {"profile": profile, "p12": p12, "password": password,
            "expires_at": info["expires_at"]}
