"""Offline restore with rollback and no restoration of account secrets.

Use only while both ViePN processes are stopped. The ZIP is first verified
and extracted exclusively from an approved manifest. No API route exposes this.
"""
from __future__ import annotations

import os
import shutil
import socket
import tempfile
import uuid
import zipfile
from pathlib import Path

from .backups import create_backup, verify_backup
from .db import Database


def _listening(port: int) -> bool:
    try:
        with socket.create_connection(("127.0.0.1", port), timeout=0.3):
            return True
    except OSError:
        return False


def restore_backup(root: Path, archive: Path, confirm: str = "",
                   ports: tuple[int, ...] = (8765, 8766)) -> dict:
    if confirm != "RESTORE VIEPN":
        raise ValueError("Explicit RESTORE VIEPN confirmation required")
    if any(_listening(port) for port in ports):
        raise RuntimeError("Stop ViePN backend and gateway before offline restore")
    root = root.resolve()
    archive = archive.resolve(strict=True)
    report = verify_backup(archive)
    restore_dir = root / ("restore-stage-" + uuid.uuid4().hex)
    restore_dir.mkdir(parents=True)
    staged = restore_dir / "data"
    staged.mkdir()
    (staged / "ipas").mkdir()
    (staged / "profiles").mkdir()
    old_dir = restore_dir / "previous"
    old_dir.mkdir()
    replaced: list[tuple[Path, Path]] = []
    installed: list[Path] = []
    targets = [
        ("viepn.sqlite3", "viepn.sqlite3"),
        ("ipas", "ipas"),
        ("profiles", "profiles"),
    ]
    try:
        with zipfile.ZipFile(archive, "r") as zipped:
            for name in zipped.namelist():
                if name == "manifest.json":
                    continue
                # verify_backup rejects names outside data/, and unexpected files.
                destination = (restore_dir / name).resolve()
                if not destination.is_relative_to(staged.resolve()):
                    raise ValueError("Unsafe archive path")
                destination.parent.mkdir(parents=True, exist_ok=True)
                with zipped.open(name) as src, destination.open("xb") as dst:
                    shutil.copyfileobj(src, dst)
        if not (staged / "viepn.sqlite3").is_file():
            raise ValueError("Backup lacks SQLite database")
        # Fresh local safety snapshot before replacing any existing data.
        if (root / "viepn.sqlite3").exists():
            create_backup(root, Database(root / "viepn.sqlite3"), "before-restore")
        for original, member in targets:
            target = root / original
            previous = old_dir / original
            if target.exists():
                os.replace(target, previous)
                replaced.append((target, previous))
            new = staged / member
            if new.exists():
                os.replace(new, target)
                installed.append(target)
        # Do not reuse old WAL or SHM after replacing SQLite main file.
        for suffix in ("-wal", "-shm"):
            sidecar = root / ("viepn.sqlite3" + suffix)
            if sidecar.exists():
                os.replace(sidecar, old_dir / sidecar.name)
                replaced.append((sidecar, old_dir / sidecar.name))
        shutil.rmtree(restore_dir)
        return {"restored": True, "verified_files": report["files"],
                "accounts_unchanged": True}
    except Exception:
        for target in reversed(installed):
            if target.is_dir():
                shutil.rmtree(target)
            elif target.exists():
                target.unlink()
        for target, previous in reversed(replaced):
            if previous.exists():
                os.replace(previous, target)
        raise
    finally:
        if restore_dir.exists():
            shutil.rmtree(restore_dir, ignore_errors=True)
