"""Non-destructive ViePN readiness checks, safe to show to remote app.

Do not return Apple ID accounts, session tokens, filesystem paths, UDIDs,
full environment or credential values. No mutating network requests.
"""
from __future__ import annotations

import asyncio
import importlib.util
import os
import socket
import subprocess
from pathlib import Path
from shutil import which

from .config import Settings


def _port(host: str, port: int) -> bool:
    try:
        with socket.create_connection((host, port), timeout=0.7):
            return True
    except OSError:
        return False


def doctor(cfg: Settings) -> dict:
    details: list[dict] = []
    def add(key: str, ok: bool, tip: str):
        details.append({"key": key, "ok": bool(ok), "tip": tip if not ok else "Sẵn sàng"})

    add("api", _port("127.0.0.1", cfg.port), "Khởi động Start-ViePN.bat trên Windows")
    add("gateway", _port("127.0.0.1", int(os.getenv("VIEPN_REMOTE_PORT", "8766"))),
        "Khởi động gateway và kiểm tra port 8766")
    add("mobiledevice", importlib.util.find_spec("pymobiledevice3") is not None,
        "Cài pymobiledevice3 và ghép đôi iPhone qua USB")
    add("signer", bool(which(cfg.signer) or Path(cfg.signer).is_file()),
        "Cấu hình zsign nếu dùng chế độ P12; Apple Personal Team dùng luồng ký tích hợp")
    add("tailscale", which("tailscale") is not None or
        (os.name == "nt" and (Path(os.environ.get("ProgramFiles", "C:/Program Files")) / "Tailscale" / "tailscale.exe").exists()),
        "Cài Tailscale và đăng nhập cùng tailnet")
    add("storage", cfg.root.is_dir() and os.access(cfg.root, os.W_OK),
        "Kiểm tra quyền ghi vào thư mục dữ liệu ViePN")
    return {"checks": details, "ok_count": sum(x["ok"] for x in details),
            "total": len(details), "note": "Tín hiệu môi trường, không xác minh chữ ký hoặc cài đặt Apple thực tế"}
