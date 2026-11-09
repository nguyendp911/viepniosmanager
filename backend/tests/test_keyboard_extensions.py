"""Regression tests: 7-day signing must not strip iOS keyboard extensions."""
import plistlib
import zipfile
from pathlib import Path
from types import SimpleNamespace

import viepn.native_sign as native
from viepn.applekit import ipa as ipa_tools


def make_keyboard_ipa(path: Path) -> Path:
    app = "Payload/Demo.app/"
    ext = app + "PlugIns/DemoKeyboard.appex/"
    with zipfile.ZipFile(path, "w") as archive:
        archive.writestr(app + "Info.plist", plistlib.dumps({
            "CFBundleIdentifier": "com.example.demo",
            "CFBundleExecutable": "Demo",
            "CFBundleDisplayName": "Demo",
        }))
        archive.writestr(app + "Demo", b"dummy main executable")
        archive.writestr(ext + "Info.plist", plistlib.dumps({
            "CFBundleIdentifier": "com.example.demo.keyboard",
            "CFBundleExecutable": "DemoKeyboard",
            "NSExtension": {
                "NSExtensionPointIdentifier": "com.apple.keyboard-service",
                "NSExtensionPrincipalClass": "DemoKeyboard.KeyboardViewController",
            },
        }))
        archive.writestr(ext + "DemoKeyboard", b"dummy keyboard executable")
    return path


def test_keyboard_ipa_preparation_keeps_extension(tmp_path):
    source = make_keyboard_ipa(tmp_path / "source.ipa")
    output = tmp_path / "prepared.ipa"
    report = ipa_tools.prepare(str(source), str(output), strip_extensions=False)
    assert "PlugIns" not in report["removed"]
    with zipfile.ZipFile(output) as z:
        assert "Payload/Demo.app/PlugIns/DemoKeyboard.appex/Info.plist" in z.namelist()


def test_native_sign_uses_separate_extension_profiles(tmp_path, monkeypatch):
    source = make_keyboard_ipa(tmp_path / "source.ipa")
    output = tmp_path / "output.ipa"
    monkeypatch.setattr(native, "_apple_environment", lambda: None)
    monkeypatch.setattr(native.gsa, "load_session", lambda _email=None: {"email": "test@example.com"})
    monkeypatch.setattr(native.provision, "team_scoped_bundle_id",
                        lambda bundle: bundle + ".TEAM123")
    signed_assets = []

    def fake_assets(bundle, udid, **kwargs):
        signed_assets.append((bundle, kwargs))
        return {
            "p12_path": "test.p12",
            "p12_password": "secret",
            "profile_path": bundle + ".mobileprovision",
            "account": "test@example.com",
            "team_id": "TEAM123",
        }

    monkeypatch.setattr(native.provision, "ensure_signing_assets", fake_assets)
    monkeypatch.setattr(native.signing, "resolve_zsign", lambda: "zsign")
    monkeypatch.setattr(native, "parse_provision", lambda data: {"bundle_pattern": "com.example.demo.keyboard.TEAM123", "devices": ["a" * 40], "expires_at": "2030-01-01T00:00:00+00:00"})
    monkeypatch.setattr(native, "profile_compatible", lambda _profile, _bundle, _udid: True)
    original_run = native.subprocess.run

    def fake_run(command, **kwargs):
        assert command.count("-m") == 2
        prepared = Path(command[-1])
        with zipfile.ZipFile(prepared) as z:
            assert plistlib.loads(
                z.read("Payload/Demo.app/PlugIns/DemoKeyboard.appex/Info.plist")
            )["CFBundleIdentifier"] == "com.example.demo.keyboard.TEAM123"
            with zipfile.ZipFile(output, "w") as dest:
                for entry in z.infolist():
                    dest.writestr(entry, z.read(entry.filename))
                dest.writestr("Payload/Demo.app/PlugIns/DemoKeyboard.appex/embedded.mobileprovision", b"test")
        return SimpleNamespace(returncode=0, stdout="OK", stderr="")

    monkeypatch.setattr(native.subprocess, "run", fake_run)
    monkeypatch.setattr(native, "inspect_ipa", lambda _path: {
        "signed_candidate": True,
        "bundle_id": "com.example.demo.TEAM123",
        "profile_expires": "2030-01-01T00:00:00+00:00",
    })
    result = native.sign_free_ipa(source, output, "a" * 40)
    assert result["bundle_id"] == "com.example.demo.TEAM123"
    assert [item[0] for item in signed_assets] == [
        "com.example.demo.TEAM123", "com.example.demo.keyboard.TEAM123"
    ]
