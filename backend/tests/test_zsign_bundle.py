"""Regression coverage for packaged zsign.exe discovery on Windows.

The official Windows ZIP includes vendor/zsign.exe; a default cfg.signer
value of 'zsign' must resolve it even when PATH has no signer.
"""
from pathlib import Path
from unittest.mock import patch

from fastapi.testclient import TestClient

from test_api import config
from viepn import tools
from viepn.api import create_app
from viepn.tools import ExternalToolError, resolve_zsign_executable, sign_with_zsign

AUTH = {"Authorization": "Bearer very-long-test-secret-token"}


def test_resolves_bundled_signer_when_not_on_path(tmp_path, monkeypatch):
    path = tmp_path / "backend" / "viepn" / "tools.py"
    path.parent.mkdir(parents=True)
    path.write_text("# test module path")
    executable = path.parent / "applekit" / "vendor" / "zsign"
    executable.parent.mkdir(parents=True)
    executable.write_bytes(b"synthetic signer, not an executable")
    monkeypatch.setattr(tools, "__file__", str(path))
    monkeypatch.setattr(tools.shutil, "which", lambda name: None)
    assert resolve_zsign_executable("zsign") == str(executable)
    assert resolve_zsign_executable(str(tmp_path / "missing" / "custom.exe")) is None
    assert resolve_zsign_executable("missing_custom_signer.exe") is None


def test_sign_uses_bundled_signer_path_not_unresolved_command(tmp_path, monkeypatch):
    executable = tmp_path / "zsign.exe"
    executable.write_bytes(b"MZ-mock")
    ipa = tmp_path / "source.ipa"
    p12 = tmp_path / "local.p12"
    profile = tmp_path / "local.mobileprovision"
    for f in (ipa, p12, profile):
        f.write_bytes(b"dummy")
    calls = []
    monkeypatch.setattr(tools, "resolve_zsign_executable", lambda value: str(executable))
    monkeypatch.setattr(tools, "run", lambda args, **kwargs: calls.append(args) or "ok")
    assert sign_with_zsign("zsign", ipa, tmp_path / "signed.ipa", p12, profile, "test-secret") == "ok"
    assert calls[0][0] == str(executable)
    assert calls[0][1:3] == ["-k", str(p12)]


def test_dashboard_reports_resolved_signer_and_imported_cert(tmp_path, monkeypatch):
    import viepn.api as api_module
    monkeypatch.setattr(api_module, "resolve_zsign_executable",
                        lambda name: "C:/ViePN/embedded/zsign.exe")
    monkeypatch.setattr(api_module, "vault_metadata",
                        lambda root: {"configured": True})
    app = create_app(config(tmp_path))
    with TestClient(app) as client:
        tools_status = client.get("/api/overview", headers=AUTH).json()["tools"]
        assert tools_status["zsign"] is True
        assert tools_status["signing_p12"] is True


def test_missing_signer_error_is_actionable(tmp_path, monkeypatch):
    monkeypatch.setattr(tools, "resolve_zsign_executable", lambda value: None)
    p12 = tmp_path / "my.p12"
    profile = tmp_path / "my.mobileprovision"
    p12.write_bytes(b"mock")
    profile.write_bytes(b"mock")
    with __import__('pytest').raises(ExternalToolError, match="Update-ViePN.bat"):
        sign_with_zsign("zsign", tmp_path / "source.ipa", tmp_path / "out.ipa", p12, profile, "")
