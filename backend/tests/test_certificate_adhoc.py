"""Ad Hoc P12/profile matching and private HTTPS OTA security regressions.

Only synthetic certificates are used here. Real user P12/profile are NEVER
uploaded to GitHub/CI and are never part of the Windows installer.
"""
import plistlib
import zipfile
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest
from cryptography import x509
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from cryptography.hazmat.primitives.serialization import pkcs12
from cryptography.x509.oid import NameOID
from fastapi.testclient import TestClient

from test_api import config
from test_ipa import sample_ipa
from viepn.api import create_app
from viepn.adhoc_ota import OTAShareStore, validate_base
from viepn.certificate_vault import inspect_pair

AUTH = {"Authorization": "Bearer very-long-test-secret-token"}


def synthetic_pair(bundle="com.example.allowed", devices=None, allow_debug=False):
    devices = devices or ["00008030-0011223344556677"]
    key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    subject = x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, "Test Distribution Only")])
    now = datetime.now(timezone.utc)
    cert = (x509.CertificateBuilder().subject_name(subject).issuer_name(subject)
        .public_key(key.public_key()).serial_number(x509.random_serial_number())
        .not_valid_before(now - timedelta(days=1))
        .not_valid_after(now + timedelta(days=60)).sign(key, hashes.SHA256()))
    p12 = pkcs12.serialize_key_and_certificates(
        b"synthetic", key, cert, None, serialization.BestAvailableEncryption(b"test-p12-password")
    )
    blob = plistlib.dumps({
        "TeamIdentifier": ["TESTTEAM01"],
        "UUID": "11111111-1111-1111-1111-111111111111",
        "Entitlements": {
            "application-identifier": "TESTTEAM01." + bundle,
            "get-task-allow": allow_debug,
        },
        "ExpirationDate": (now + timedelta(days=30)).replace(tzinfo=None),
        "ProvisionedDevices": devices,
        "DeveloperCertificates": [cert.public_bytes(serialization.Encoding.DER)],
    })
    return p12, blob


def test_adhoc_p12_key_matches_profile_and_enforces_scope():
    p12, profile = synthetic_pair()
    status = inspect_pair(p12, profile, "test-p12-password")
    assert status["mode"] == "ad_hoc"
    assert status["matched"]
    assert status["devices_count"] == 1
    assert status["bundle_pattern"] == "com.example.allowed"
    assert status["cms_signature_verified"] is False
    with pytest.raises(ValueError, match="password"):
        inspect_pair(p12, profile, "incorrect")
    with pytest.raises(ValueError, match="NOT included"):
        inspect_pair(p12, synthetic_pair()[1], "test-p12-password")
    debug_profile = plistlib.loads(profile)
    debug_profile["Entitlements"]["get-task-allow"] = True
    with pytest.raises(ValueError, match="Ad Hoc"):
        inspect_pair(p12, plistlib.dumps(debug_profile), "test-p12-password")


def test_ota_accepts_only_private_tailscale_https():
    assert validate_base("https://viepn-pc.example-tailnet.ts.net") == (
        "https://viepn-pc.example-tailnet.ts.net"
    )
    for url in (
        "http://viepn-pc.example-tailnet.ts.net", "https://example.com",
        "https://evil.ts.net@attacker.com", "https://evil.ts.net:8443",
        "https://evil.ts.net/download?token=abc", "https://evil.ts.net/#frag",
    ):
        with pytest.raises(ValueError):
            validate_base(url)


def test_ota_capabilities_are_expiring_and_bounded(tmp_path):
    path = tmp_path / "signed.ipa"
    path.write_bytes(b"test-mock")
    store = OTAShareStore(ttl_seconds=600)
    result = store.create(path, "https://private.example.ts.net", {
        "bundle_id": "com.example.allowed", "name": "Test",
        "version": "1", "device_suffix": "556677",
    })
    assert result["install_url"].startswith("itms-services://?action=download-manifest")
    manifest = plistlib.loads(store.manifest(result["manifest_url"].rsplit("/", 1)[-1]))
    url = manifest["items"][0]["assets"][0]["url"]
    assert url.startswith("https://private.example.ts.net/api/ota/package/")
    token = url.rsplit("/", 1)[-1]
    assert store.package(token) == path
    for _ in range(11):
        store.package(token)
    assert store.package(token) is None
    assert store.manifest("invalid") is None


def test_ota_requires_auth_and_existing_imported_credential(tmp_path):
    with TestClient(create_app(config(tmp_path))) as client:
        path = sample_ipa(tmp_path / "sample.ipa")
        with path.open("rb") as f:
            created = client.post("/api/ipas", headers=AUTH,
                files={"file": ("sample.ipa", f, "application/octet-stream")})
        assert created.status_code == 200
        payload = {"ipa_id": created.json()["id"], "device_index": 0,
                   "public_base_url": "https://private.example.ts.net"}
        assert client.post("/api/ota/prepare", json=payload).status_code == 401
        assert client.post("/api/ota/prepare", headers=AUTH, json=payload).status_code == 409
        status = client.get("/api/certificates/status", headers=AUTH)
        assert status.json()["configured"] is False
        assert "certificate_name" not in status.json()
        assert client.get("/api/ota/manifest/invalid").status_code == 404
        assert client.get("/api/ota/package/invalid").status_code == 404


def test_ota_embedded_profile_bundle_and_device_scope(tmp_path, monkeypatch):
    from viepn.adhoc_ota import inspect_adhoc_ipa
    from viepn import adhoc_ota
    p12, profile = synthetic_pair("com.example.allowed")
    vault = tmp_path / "certificates"
    vault.mkdir()
    (vault / "certificate.p12").write_bytes(p12)
    (vault / "profile.mobileprovision").write_bytes(profile)
    monkeypatch.setattr(adhoc_ota, "signing_material", lambda root: (
        vault / "certificate.p12", vault / "profile.mobileprovision", "test-p12-password"
    ))
    info = plistlib.dumps({
        "CFBundleIdentifier": "com.example.allowed",
        "CFBundleDisplayName": "Synthetic",
        "CFBundleShortVersionString": "1.0",
    })
    path = tmp_path / "synthetic.ipa"
    with zipfile.ZipFile(path, "w") as z:
        z.writestr("Payload/Test.app/Info.plist", info)
        z.writestr("Payload/Test.app/embedded.mobileprovision", profile)
    assert inspect_adhoc_ipa(path, 0, tmp_path)["bundle_id"] == "com.example.allowed"
    with pytest.raises(ValueError, match="not registered"):
        inspect_adhoc_ipa(path, 1, tmp_path)
    profile_wrong = synthetic_pair("com.example.other")[1]
    with zipfile.ZipFile(path, "w") as z:
        z.writestr("Payload/Test.app/Info.plist", info)
        z.writestr("Payload/Test.app/embedded.mobileprovision", profile_wrong)
    with pytest.raises(ValueError):
        inspect_adhoc_ipa(path, 0, tmp_path)


def test_remote_sign_requires_imported_profile_and_bearer(tmp_path):
    with TestClient(create_app(config(tmp_path))) as client:
        ipa = sample_ipa(tmp_path / "source.ipa")
        with ipa.open("rb") as f:
            created = client.post("/api/ipas", headers=AUTH,
                files={"file": ("source.ipa", f, "application/octet-stream")})
        assert created.status_code == 200
        data = {"ipa_id": created.json()["id"], "device_index": 0}
        assert client.post("/api/adhoc/sign", json=data).status_code == 401
        assert client.post("/api/adhoc/sign", headers=AUTH, json=data).status_code == 409
        assert client.post("/api/adhoc/sign", headers=AUTH,
                           json={**data, "device_index": -1}).status_code == 422
        assert client.post("/api/adhoc/sign", headers=AUTH, json={
            "ipa_id": "missing", "device_index": 0
        }).status_code == 404


def test_remote_ota_allowlist_requires_explicit_method_and_random_capability():
    from viepn.remote_gateway import allowed
    assert allowed("GET", "/api/certificates/status")
    assert allowed("POST", "/api/adhoc/sign")
    assert allowed("POST", "/api/ota/prepare")
    assert allowed("GET", "/api/ota/manifest/" + "a" * 43)
    assert allowed("GET", "/api/ota/package/" + "a" * 43)
    assert not allowed("GET", "/api/ota/prepare")
    assert not allowed("POST", "/api/ota/package/" + "a" * 43)
    assert not allowed("GET", "/api/ota/package/random")
    assert not allowed("POST", "/api/certificates/import")
