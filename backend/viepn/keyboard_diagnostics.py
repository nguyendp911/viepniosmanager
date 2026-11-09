"""Inspect app/keyboard-extension packaging and embedded profiles, without signing keys.

Usage: python -m viepn.keyboard_diagnostics path/to/signed.ipa [device-udid]
This performs structural checks, not a cryptographic CodeDirectory verification.
"""
from __future__ import annotations

import argparse
import json
import plistlib
import re
import zipfile
from pathlib import Path

from .ipa import parse_provision, supports_bundle


def diagnose(path: str | Path, udid: str | None = None) -> dict:
    problems: list[str] = []
    items: list[dict] = []
    with zipfile.ZipFile(path) as zf:
        names = set(zf.namelist())
        apps = sorted(x for x in names if re.fullmatch(r"Payload/[^/]+\.app/Info\.plist", x))
        if len(apps) != 1:
            return {"ok": False, "errors": ["IPA must contain exactly one app Info.plist"], "extensions": []}
        root = apps[0].removesuffix("Info.plist")
        app_info = plistlib.loads(zf.read(apps[0]))
        host = app_info.get("CFBundleIdentifier", "")
        appex_infos = sorted(x for x in names if x.startswith(root + "PlugIns/") and x.endswith(".appex/Info.plist"))
        if not appex_infos:
            problems.append("No .appex found in Payload/*.app/PlugIns; iOS cannot offer this keyboard.")
        for plist_name in appex_infos:
            info = plistlib.loads(zf.read(plist_name))
            folder = plist_name.removesuffix("Info.plist")
            identifier = info.get("CFBundleIdentifier", "")
            ext = info.get("NSExtension", {})
            kind = ext.get("NSExtensionPointIdentifier") if isinstance(ext, dict) else None
            executable = info.get("CFBundleExecutable", "")
            exe_present = bool(executable and folder + executable in names)
            profile_path = folder + "embedded.mobileprovision"
            profile_present = profile_path in names
            pattern = None
            device_allowed = None
            if profile_present:
                try:
                    profile = parse_provision(zf.read(profile_path))
                    pattern = profile.get("bundle_pattern")
                    if not supports_bundle(pattern or "", identifier):
                        problems.append(f"Profile does not authorize extension {identifier}")
                    if udid:
                        device_allowed = udid in profile.get("devices", [])
                        if not device_allowed:
                            problems.append(f"Profile does not contain device UDID for {identifier}")
                except (ValueError, KeyError, TypeError, plistlib.InvalidFileException):
                    problems.append(f"Extension provisioning profile unreadable: {identifier}")
            else:
                problems.append(f"Extension has no embedded.mobileprovision: {identifier}")
            if host and not identifier.startswith(host + "."):
                problems.append(f"Extension ID {identifier} is not prefixed by host ID {host}")
            if not exe_present:
                problems.append(f"Missing executable for extension {identifier}")
            if not kind:
                problems.append(f"Missing NSExtensionPointIdentifier for {identifier}")
            items.append({
                "bundle_id": identifier,
                "extension_point": kind,
                "executable_present": exe_present,
                "profile_present": profile_present,
                "profile_bundle_pattern": pattern,
                "device_allowed": device_allowed,
                "keyboard": kind == "com.apple.keyboard-service",
            })
        return {"ok": not problems, "app_bundle_id": host, "extensions": items, "errors": problems,
                "note": "Structural check only; cannot prove cryptographic signature or iOS registration."}


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("ipa")
    parser.add_argument("udid", nargs="?")
    args = parser.parse_args()
    print(json.dumps(diagnose(args.ipa, args.udid), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
