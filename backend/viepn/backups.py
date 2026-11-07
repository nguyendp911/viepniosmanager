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
import time
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


class BackupError(OSError):
    """A sanitized backup error with the failing operation, no personal paths."""


def _create_backup_once(root: Path, db: Database, reason: str = "manual") -> dict:
    root = root.resolve()
    archive_dir = root / "backups"
    archive_dir.mkdir(parents=True, exist_ok=True)
    name = "ViePN-" + datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S") + "-" + secrets.token_hex(4) + ".zip"
    result = archive_dir / name
    temp_path: Path | None = None
    sqlite_path: Path | None = None
    stage = "khởi tạo file sao lưu"
    label = ""
    try:
        stage = "sao lưu SQLite"
        with tempfile.NamedTemporaryFile(suffix=".sqlite3", delete=False, dir=str(archive_dir)) as tmp:
            sqlite_path = Path(tmp.name)
        with db.connect() as source, sqlite3.connect(sqlite_path) as dest:
            source.backup(dest)
        files: list[tuple[str, Path, str | None]] = [("data/viepn.sqlite3", sqlite_path, None)]
        for table, folder, ext in (("ipa", "ipas", ".ipa"), ("profiles", "profiles", ".mobileprovision")):
            for row in db.query("SELECT sha256,file_path FROM " + table):
                stage = "kiểm tra IPA" if folder == "ipas" else "kiểm tra profile"
                label = str(row["sha256"])[:12]
                expected = (root / folder / (row["sha256"] + ext)).resolve()
                actual = Path(row["file_path"]).resolve()
                if actual != expected or actual.parent != (root / folder).resolve():
                    raise ValueError("Unsafe library file location; backup cancelled")
                if not actual.is_file() or sha256(actual) != row["sha256"]:
                    raise ValueError("Missing or modified library file; backup cancelled")
                files.append(("data/" + folder + "/" + actual.name, actual, row["sha256"]))
        with tempfile.NamedTemporaryFile(suffix=".zip", delete=False, dir=str(archive_dir)) as tmp:
            temp_path = Path(tmp.name)
        manifest: dict = {"format": 1, "reason": reason[:80],
                          "created_at": datetime.now(timezone.utc).isoformat(),
                          "files": {}}
        stage = "ghi ZIP"
        with zipfile.ZipFile(temp_path, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=4, allowZip64=True) as archive:
            for archive_name, source, expected_digest in files:
                label = (expected_digest or "")[:12]
                stage = "đọc và nén SQLite" if expected_digest is None else (
                    "đọc và nén IPA" if "/ipas/" in archive_name else "đọc và nén profile"
                )
                digest = hashlib.sha256()
                size = 0
                with source.open("rb") as input_file, archive.open(archive_name, "w", force_zip64=True) as output:
                    for chunk in iter(lambda: input_file.read(1024 * 1024), b""):
                        output.write(chunk)
                        digest.update(chunk)
                        size += len(chunk)
                computed = digest.hexdigest()
                if expected_digest and computed != expected_digest:
                    raise ValueError("Checksum mismatch")
                manifest["files"][archive_name] = {"sha256": computed, "size": size}
            stage = "ghi manifest"
            label = ""
            archive.writestr("manifest.json", json.dumps(manifest, sort_keys=True))
        stage = "kiểm tra toàn vẹn ZIP"
        verify_backup(temp_path)
        stage = "lưu ZIP"
        os.replace(temp_path, result)
        return {"name": name, "files": len(files), "size_bytes": result.stat().st_size,
                "created_at": manifest["created_at"]}
    except (OSError, ValueError, sqlite3.Error, zipfile.BadZipFile) as exc:
        category = ("Windows từ chối truy cập hoặc file bị khóa"
                    if isinstance(exc, PermissionError)
                    else "file hoặc dữ liệu sao lưu không hợp lệ"
                    if isinstance(exc, ValueError)
                    else "lỗi ổ đĩa hoặc cơ sở dữ liệu")
        identifier = " (SHA " + label + ")" if label else ""
        raise BackupError(
            "Không thể sao lưu tại bước " + stage + identifier + ": "
            + category + ". Chưa xóa dữ liệu nào."
        ) from exc
    finally:
        for candidate in (sqlite_path, temp_path):
            if candidate is not None:
                try:
                    candidate.unlink(missing_ok=True)
                except OSError:
                    pass


def create_backup(root: Path, db: Database, reason: str = "manual") -> dict:
    """Retry transient Windows locks without ever proceeding with incomplete backup."""
    for attempt in range(3):
        try:
            return _create_backup_once(root, db, reason)
        except BackupError as exc:
            if "file bị khóa" not in str(exc) or attempt == 2:
                raise
            time.sleep((attempt + 1) * 0.5)
    raise BackupError("Không tạo được bản sao lưu an toàn")


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
