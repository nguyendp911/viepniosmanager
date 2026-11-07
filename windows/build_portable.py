"""Create portable Windows distribution with a file-level integrity manifest.

Only approved source paths are included. No passwords, .venv, Git metadata,
IPA user files, Apple credentials, local caches or .env are packaged.
"""
from __future__ import annotations

import hashlib
import json
import zipfile
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
DIST = ROOT / "dist"
DIRECTORIES = ("backend", "web", "windows", "ios", "docs")
TOP_LEVEL = ("Start-ViePN.bat", "Install-ViePN.bat", "Update-ViePN.bat", "README.md")
IGNORED = {".git", ".venv", "__pycache__", ".pytest_cache", ".DS_Store",
           "build", "artifacts", "dist", "node_modules", "incoming", "session"}
ALLOWED_SUFFIXES = {".py", ".txt", ".md", ".ps1", ".bat", ".html", ".swift",
                    ".plist", ".json", ".yml", ".yaml", ".sh", ".xcassets",
                    ".png", ".jpg", ".jpeg", ".svg", ".pem", ".xcconfig", ".entitlements"}


def allowed(path: Path) -> bool:
    rel = path.relative_to(ROOT)
    if any(p in IGNORED or p.startswith(".env") for p in rel.parts):
        return False
    if path.is_symlink() or not path.is_file():
        return False
    if rel.parts[0] not in DIRECTORIES and rel.as_posix() not in TOP_LEVEL:
        return False
    if path.suffix.lower() not in ALLOWED_SUFFIXES:
        return False
    return True


def build() -> tuple[Path, Path]:
    DIST.mkdir(exist_ok=True)
    archive_path = DIST / "ViePN-Windows-Portable.zip"
    checksum_path = DIST / "ViePN-Windows-Portable.sha256"
    members = [ROOT / item for item in TOP_LEVEL]
    for directory in DIRECTORIES:
        members.extend((ROOT / directory).rglob("*"))
    members = sorted([p for p in members if allowed(p)], key=lambda p: p.as_posix())
    manifest = {"schema": 1, "version": "2.1.4", "files": {}}
    with zipfile.ZipFile(archive_path, "w", zipfile.ZIP_DEFLATED, compresslevel=6) as archive:
        for path in members:
            name = path.relative_to(ROOT).as_posix()
            data = path.read_bytes()
            archive.writestr(name, data)
            manifest["files"][name] = hashlib.sha256(data).hexdigest()
        archive.writestr("manifest.json", json.dumps(manifest, indent=2, sort_keys=True))
    digest = hashlib.sha256(archive_path.read_bytes()).hexdigest()
    checksum_path.write_text(f"{digest}  {archive_path.name}\n", encoding="utf-8")
    print(f"ViePN Windows Portable {len(members)} files, sha256={digest}")
    return archive_path, checksum_path


if __name__ == "__main__":
    build()
