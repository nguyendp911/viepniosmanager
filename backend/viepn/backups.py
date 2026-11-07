"""Private local IPA/profile backup. No credentials, Apple sessions, or API token.

Snapshots are consistent while Manager.lock is held. SQLite's online backup
API captures committed records; IPA and mobileprovision contents are archived
with SHA256 checksums. No archive is automatically transmitted off Windows.
Restore is an OFFLINE operator action, never exposed over HTTP.
"""
from __future__ import annotations

import hashlib
import json
import os
import secrets
import sqlite3
import tempfile
import zipfile
from datetime import datetime, timezone
from pathlib import Path

from .db import Database


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as src:
        for block in iter(lambda: src.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def create_backup(root: Path, db: Database, reason: str = "manual") -> dict:
    root = root.resolve()
    archive_dir = root / "backups"
    archive_dir.mkdir(parents=True, exist_ok=True)
    name = "ViePN-" + datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S") + "-" + secrets.token_hex(4) + ".zip"
    result = archive_dir / name
    temp_path: Path | None = None
    sqlite_path: Path | None = None
    try:
        with tempfile.NamedTemporaryFile(suffix=".sqlite3", delete=False, dir=str(archive_dir)) as tmp:
            sqlite_path = Path(tmp.name)
        with db.connect() as source, sqlite3.connect(sqlite_path) as dest:
            source.backup(dest)
        files: list[tuple[str, Path]] = [("data/viepn.sqlite3", sqlite_path)]
        for table, folder, ext in (("ipa", "ipas", ".ipa"), ("profiles", "profiles", ".mobileprovision")):
            for row in db.query("SELECT sha256,file_path FROM " + table):
                expected = (root / folder / (row["sha256"] + ext)).resolve()
                actual = Path(row["file_path"]).resolve()
                if actual != expected or actual.parent != (root / folder).resolve():
                    raise ValueError("Unsafe library file location; backup cancelled")
                if not actual.is_file() or sha256(actual) != row["sha256"]:
                    raise ValueError("Missing or modified library file; backup cancelled")
                files.append(("data/" + folder + "/" + actual.name, actual))
        with tempfile.NamedTemporaryFile(suffix=".zip", delete=False, dir=str(archive_dir)) as tmp:
            temp_path = Path(tmp.name)
        manifest: dict = {"format": 1, "reason": reason[:80],
                          "created_at": datetime.now(timezone.utc).isoformat(),
                          "files": {}}
        with zipfile.ZipFile(temp_path, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=4, allowZip64=True) as archive:
            for archive_name, source in files:
                archive.write(source, archive_name)
                manifest["files"][archive_name] = {"sha256": sha256(source), "size": source.stat().st_size}
            archive.writestr("manifest.json", json.dumps(manifest, sort_keys=True))
        os.replace(temp_path, result)
        return {"name": name, "files": len(files), "size_bytes": result.stat().st_size,
                "created_at": manifest["created_at"]}
    finally:
        if sqlite_path is not None:
            sqlite_path.unlink(missing_ok=True)
        if temp_path is not None:
            temp_path.unlink(missing_ok=True)


def verify_backup(filename: Path) -> dict:
    with zipfile.ZipFile(filename) as archive:
        manifest = json.loads(archive.read("manifest.json"))
        if manifest.get("format") != 1 or not isinstance(manifest.get("files"), dict):
            raise ValueError("Unsupported backup manifest")
        expected = set(manifest["files"])
        if set(archive.namelist()) != expected | {"manifest.json"}:
            raise ValueError("Backup contains unexpected or missing files")
        for name, entry in manifest["files"].items():
            if not name.startswith("data/") or ".." in Path(name).parts or name.startswith("/"):
                raise ValueError("Unsafe file in backup")
            digest = hashlib.sha256()
            size = 0
            with archive.open(name) as fh:
                for part in iter(lambda: fh.read(1024 * 1024), b""):
                    digest.update(part)
                    size += len(part)
            if digest.hexdigest() != entry["sha256"] or size != entry["size"]:
                raise ValueError("Backup corrupted: " + name)
        return {"valid": True, "files": len(expected), "created_at": manifest.get("created_at")}


def list_backups(root: Path) -> list[dict]:
    folder = root / "backups"
    if not folder.is_dir():
        return []
    result = []
    for path in sorted(folder.glob("ViePN-*.zip"), reverse=True)[:40]:
        if path.is_file() and not path.is_symlink():
            result.append({"name": path.name, "size_bytes": path.stat().st_size})
    return result
