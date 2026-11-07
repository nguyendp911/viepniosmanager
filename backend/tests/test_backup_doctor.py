"""Security regression tests for private backups and connection doctor."""
import io
import zipfile
from pathlib import Path

from fastapi.testclient import TestClient

from test_api import config
from test_ipa import sample_ipa
from viepn.api import create_app
from viepn.backups import create_backup, verify_backup

AUTH = {"Authorization": "Bearer very-long-test-secret-token"}
ORIGIN = "http://127.0.0.1:8765"


def test_private_backup_does_not_include_secrets_and_detects_tampering(tmp_path):
    app = create_app(config(tmp_path))
    manager = app.state.manager
    sample = sample_ipa(tmp_path / "source.ipa")
    manager.add_ipa(sample)
    result = create_backup(manager.cfg.root, manager.db, "manual")
    backup = manager.cfg.root / "backups" / result["name"]
    assert verify_backup(backup)["valid"]
    with zipfile.ZipFile(backup) as archive:
        entries = archive.namelist()
        assert "manifest.json" in entries
        assert "data/viepn.sqlite3" in entries
        assert any(name.startswith("data/ipas/") for name in entries)
        assert not any("access_token" in name or "session" in name or ".p12" in name
                       for name in entries)
    with backup.open("ab") as fh:
        fh.write(b"\x00")
    # Appended bytes do not alter ZIP entries; verify entry mutation separately.
    with zipfile.ZipFile(backup, "a") as archive:
        archive.writestr("unexpected.txt", "bad")
    try:
        verify_backup(backup)
        assert False, "Extra archive content should be rejected"
    except ValueError:
        pass


def test_backup_only_on_windows_localhost(tmp_path):
    app = create_app(config(tmp_path))
    with TestClient(app, base_url=ORIGIN, client=("127.0.0.1", 50000)) as client:
        assert client.get("/api/backups").status_code == 401
        assert client.post("/api/backups", headers=AUTH).status_code == 403
        result = client.post("/api/backups", headers={**AUTH, "Origin": ORIGIN})
        assert result.status_code == 200, result.text
        name = result.json()["name"]
        assert client.get("/api/backups/" + name, headers=AUTH).status_code == 200
        assert client.get("/api/backups/../../secrets", headers=AUTH).status_code != 200
        assert client.get("/api/doctor", headers=AUTH).status_code == 200


def test_bulk_delete_snapshots_first(tmp_path):
    app = create_app(config(tmp_path))
    with TestClient(app) as client:
        source = sample_ipa(tmp_path / "source.ipa")
        with source.open("rb") as fd:
            result = client.post("/api/ipas", headers=AUTH,
               files={"file": ("source.ipa", fd, "application/octet-stream")})
        assert result.status_code == 200
        deleted = client.post("/api/ipas/bulk-delete", headers=AUTH,
             json={"all": True, "force": False, "confirm": "DELETE ALL IPAS"})
        assert deleted.status_code == 200, deleted.text
        backups = list((app.state.manager.cfg.root / "backups").glob("*.zip"))
        assert len(backups) == 1
        assert verify_backup(backups[0])["valid"]
