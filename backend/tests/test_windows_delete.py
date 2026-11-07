"""Windows-locked IPA cleanup regressions and clear backup-failure API errors."""
import os
from pathlib import Path

from fastapi.testclient import TestClient

from test_api import config
from test_ipa import sample_ipa
from viepn.api import create_app

AUTH = {"Authorization": "Bearer very-long-test-secret-token"}


def _upload(client, path):
    source = sample_ipa(path)
    with source.open("rb") as f:
        r = client.post("/api/ipas", headers=AUTH,
            files={"file": (source.name, f, "application/octet-stream")})
    assert r.status_code == 200, r.text
    return r.json()["id"]


def test_windows_locked_ipa_removed_from_ui_and_retried_later(tmp_path, monkeypatch):
    app = create_app(config(tmp_path))
    with TestClient(app) as client:
        ipa_id = _upload(client, tmp_path / "source.ipa")
        manager = app.state.manager
        path = Path(manager.db.one("SELECT file_path FROM ipa WHERE id=?", (ipa_id,))["file_path"])
        real_replace = os.replace
        lock = {"active": True}
        def sometimes_locked(src, dst):
            if lock["active"] and Path(src) == path and Path(dst).name.startswith(".delete-"):
                raise PermissionError(13, "Windows process still holds file")
            return real_replace(src, dst)
        monkeypatch.setattr(os, "replace", sometimes_locked)
        response = client.post("/api/ipas/bulk-delete", headers=AUTH,
            json={"all": True, "force": True, "confirm": "DELETE ALL IPAS"})
        assert response.status_code == 200, response.text
        assert response.json()["pending_file_deletes"] == 1
        assert response.json()["files_removed"] == 0
        assert client.get("/api/overview", headers=AUTH).json()["ipas"] == []
        assert path.exists()
        assert len(manager.db.query("SELECT filename FROM pending_ipa_deletes")) == 1
        lock["active"] = False
        assert manager.cleanup_pending_ipa_deletes() == 1
        assert not path.exists()
        assert manager.db.query("SELECT * FROM pending_ipa_deletes") == []


def test_staged_ipa_unlink_locked_after_db_commit(tmp_path, monkeypatch):
    app = create_app(config(tmp_path))
    with TestClient(app) as client:
        ipa_id = _upload(client, tmp_path / "source.ipa")
        manager = app.state.manager
        real_unlink = Path.unlink
        locked = {"yes": True}
        def sometimes_locked(path, *args, **kwargs):
            if locked["yes"] and path.name.startswith(".delete-"):
                raise PermissionError(13, "Antivirus is scanning staged file")
            return real_unlink(path, *args, **kwargs)
        monkeypatch.setattr(Path, "unlink", sometimes_locked)
        response = client.post("/api/ipas/bulk-delete", headers=AUTH,
            json={"all": True, "force": True, "confirm": "DELETE ALL IPAS"})
        assert response.status_code == 200, response.text
        assert response.json()["pending_file_deletes"] == 1
        assert client.get("/api/overview", headers=AUTH).json()["ipas"] == []
        locked["yes"] = False
        assert manager.cleanup_pending_ipa_deletes() == 1
        assert not list((manager.cfg.root / "ipas").glob(".delete-*.ipa"))


def test_backup_permission_error_explains_reason_without_removing_ipa(tmp_path, monkeypatch):
    app = create_app(config(tmp_path))
    with TestClient(app) as client:
        ipa_id = _upload(client, tmp_path / "source.ipa")
        import viepn.api as api_module
        def fail_backup(*args, **kwargs):
            raise PermissionError(13, "access denied", "C:/Users/Sensitive")
        monkeypatch.setattr(api_module, "create_backup", fail_backup)
        response = client.post("/api/ipas/bulk-delete", headers=AUTH,
            json={"all": True, "force": True, "confirm": "DELETE ALL IPAS"})
        assert response.status_code == 409
        assert "sao lưu" in response.json()["detail"]
        assert "C:/Users/Sensitive" not in response.json()["detail"]
        assert app.state.manager.db.one("SELECT id FROM ipa WHERE id=?", (ipa_id,))
