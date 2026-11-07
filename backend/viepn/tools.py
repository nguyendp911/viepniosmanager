from __future__ import annotations
import json
import os
import re
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Any

UDID_RE = re.compile(r'^[a-fA-F0-9-]{16,64}$')


class ExternalToolError(RuntimeError):
    pass


def run(args: list[str], timeout: int = 30, secret: str | None = None) -> str:
    try:
        result = subprocess.run(args, capture_output=True, text=True, encoding='utf-8',
                                errors='replace', timeout=timeout, shell=False,
                                creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0))
    except FileNotFoundError as e:
        raise ExternalToolError(f'Executable not found: {args[0]}') from e
    except subprocess.TimeoutExpired as e:
        raise ExternalToolError(f'Command timed out after {timeout}s') from e
    if result.returncode:
        details = (result.stderr or result.stdout).strip()[-1500:]
        if secret:
            details = details.replace(secret, '[REDACTED]')
        raise ExternalToolError(f'Exit {result.returncode}: {details}')
    return result.stdout


def pm3() -> list[str]:
    # Calling module via active interpreter is safer than depending on PATH.
    return [sys.executable, '-m', 'pymobiledevice3']


def connected_devices() -> list[dict[str, Any]]:
    """Normalize pymobiledevice3 usbmux formats for Windows web/iOS clients.

    Current pymobiledevice3 reports Identifier, UniqueDeviceID, DeviceName.
    Older usbmux replies can include nested Properties.SerialNumber.
    """
    raw = run(pm3() + ['usbmux', 'list'], timeout=25)
    try:
        doc = json.loads(raw)
    except json.JSONDecodeError as e:
        raise ExternalToolError('Device tool did not return JSON; update pymobiledevice3') from e
    if isinstance(doc, dict):
        doc = doc.get('devices') or doc.get('Devices') or doc.get('DeviceList') or []
    if not isinstance(doc, list):
        raise ExternalToolError('Unexpected device list response')

    devices = []
    seen = set()
    for entry in doc:
        item = entry if isinstance(entry, dict) else {}
        props = item.get('Properties') if isinstance(item.get('Properties'), dict) else {}
        udid = next((v.strip() for source in (item, props)
                     for key in ('UniqueDeviceID', 'Identifier', 'udid', 'identifier',
                                 'SerialNumber', 'serial_number', 'serial')
                     if isinstance(v := source.get(key), str) and v.strip()), None)
        if not udid and isinstance(entry, str):
            udid = entry.strip()
        if not udid or udid in seen:
            continue
        seen.add(udid)
        name = next((v.strip() for source in (item, props)
                     for key in ('DeviceName', 'device_name', 'name')
                     if isinstance(v := source.get(key), str) and v.strip()), 'iPhone / iPad')
        data = dict(item)
        data.update({'udid': udid, 'name': name})
        devices.append(data)
    if doc and not devices:
        raise ExternalToolError(
            'Device found but no usable identifier. Check pymobiledevice3 version.'
        )
    return devices

def installed_apps(udid: str) -> dict:
    check_udid(udid)
    raw = run(pm3() + ['apps', 'list', '--udid', udid], timeout=60)
    result = json.loads(raw)
    return result if isinstance(result, (dict, list)) else {}


def check_udid(udid: str):
    if not UDID_RE.fullmatch(udid):
        raise ValueError('Invalid device UDID')


def install_signed_ipa(file_path: Path, udid: str) -> str:
    check_udid(udid)
    return run(pm3() + ['apps', 'install', '--udid', udid, str(file_path)], timeout=480)


def sign_with_zsign(executable: str, input_ipa: Path, output_ipa: Path,
                    p12_path: Path, profile_path: Path, password: str) -> str:
    if not p12_path.is_file() or not profile_path.is_file():
        raise ExternalToolError('P12 or .mobileprovision file missing')
    if not shutil.which(executable) and not Path(executable).is_file():
        raise ExternalToolError('zsign not configured; see docs/SIGNING.md')
    args = [executable, '-k', str(p12_path), '-m', str(profile_path), '-o', str(output_ipa)]
    if password:
        # WARNING: -p CLI argument is exposed to local process listing while signing.
        # Only run with trusted local Windows account; never log args.
        args += ['-p', password]
    args.append(str(input_ipa))
    return run(args, timeout=240, secret=password)
