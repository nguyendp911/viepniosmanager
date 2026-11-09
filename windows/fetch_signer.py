"""Download the audited, pinned zsign Windows release into the portable package.

The binary signs app + nested extensions with Apple Personal Team credentials
created locally by ViePN. This does not purchase a certificate or require a paid
Apple Developer membership. Never download an unverified latest binary.
"""
from __future__ import annotations
import hashlib
import io
import urllib.request
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
URL = "https://github.com/zhlynn/zsign/releases/download/v1.1.3/zsign-windows-x64.zip"
SHA256 = "6fb5e12a5b7179cfe7e729aa471b35ccf86474eba33d8203df119bf62bad77f7"
DEST = ROOT / "backend" / "viepn" / "applekit" / "vendor" / "zsign.exe"


def main() -> None:
    with urllib.request.urlopen(urllib.request.Request(
        URL, headers={"User-Agent": "ViePN-Release-Builder/2.2.2"}
    ), timeout=90) as response:
        blob = response.read(30 * 1024 * 1024 + 1)
    if len(blob) > 30 * 1024 * 1024:
        raise RuntimeError("Signer download exceeds size limit")
    actual = hashlib.sha256(blob).hexdigest()
    if actual != SHA256:
        raise RuntimeError("Official zsign archive SHA256 mismatch; refusing signer")
    with zipfile.ZipFile(io.BytesIO(blob)) as archive:
        candidates = [
            item for item in archive.infolist()
            if item.filename.replace("\\", "/").split("/")[-1].lower() == "zsign.exe"
            and not item.is_dir()
        ]
        if len(candidates) != 1:
            raise RuntimeError("Expected exactly one zsign.exe in official release")
        binary = archive.read(candidates[0])
    if binary[:2] != b"MZ":
        raise RuntimeError("zsign.exe is not a Windows executable")
    DEST.parent.mkdir(parents=True, exist_ok=True)
    DEST.write_bytes(binary)
    print(f"Pinned zsign.exe bundled: {len(binary)} bytes, archive SHA256 {actual}")


if __name__ == "__main__":
    main()
