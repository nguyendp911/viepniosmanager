from __future__ import annotations
import hashlib
import io
import json
import plistlib
import re
import zipfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

MAX_ARCHIVE_ENTRIES = 8000
MAX_UNPACKED_BYTES = 3 * 1024 ** 3


def parse_provision(blob: bytes) -> dict[str, Any]:
    """Extract XML property list from a CMS .mobileprovision blob.

    This is a *metadata parser*, NOT a cryptographic signature validator.
    Apple device installation performs the final signature/trust check.
    """
    match = re.search(rb'<\?xml\b.*?</plist\s*>', blob, re.DOTALL)
    if not match:
        raise ValueError('Cannot locate XML provisioning plist')
    data = plistlib.loads(match.group(0))
    if not isinstance(data, dict):
        raise ValueError('Invalid provisioning profile')
    exp = data.get('ExpirationDate')
    if isinstance(exp, datetime):
        exp = exp.replace(tzinfo=timezone.utc) if exp.tzinfo is None else exp
        expires = exp.astimezone(timezone.utc).isoformat()
    else:
        expires = None
    ent = data.get('Entitlements') or {}
    app_identifier = str(ent.get('application-identifier', ent.get('com.apple.application-identifier', '')))
    team = str((data.get('TeamIdentifier') or [''])[0] if isinstance(data.get('TeamIdentifier'), list) else data.get('TeamIdentifier', ''))
    bundle_pattern = app_identifier[len(team) + 1:] if team and app_identifier.startswith(team + '.') else app_identifier
    devices = data.get('ProvisionedDevices') or []
    return {
        'expires_at': expires,
        'team': team,
        'bundle_pattern': bundle_pattern,
        'uuid': str(data.get('UUID', '')),
        'devices': devices if isinstance(devices, list) else [],
    }


def supports_bundle(pattern: str, bundle_id: str) -> bool:
    return bool(pattern) and (pattern == bundle_id or (pattern.endswith('*') and bundle_id.startswith(pattern[:-1])))


def profile_compatible(profile: dict, bundle_id: str, udid: str, previous_expiry: str | None = None) -> bool:
    if not supports_bundle(profile.get('bundle_pattern') or '', bundle_id):
        return False
    devices = profile.get('devices', [])
    if isinstance(devices, str):
        devices = json.loads(devices)
    # Devices missing means Enterprise/App Store or other unscoped profile;
    # do not silently treat it as suitable for this personal-team workflow.
    if not isinstance(devices, list) or udid not in devices:
        return False
    exp = profile.get('expires_at')
    if not exp:
        return False
    try:
        expiry = datetime.fromisoformat(exp)
        if expiry <= datetime.now(timezone.utc):
            return False
        if previous_expiry and expiry <= datetime.fromisoformat(previous_expiry):
            return False
    except ValueError:
        return False
    return True


def inspect_ipa(path: Path) -> dict[str, Any]:
    try:
        with zipfile.ZipFile(path) as z:
            files = z.infolist()
            if len(files) > MAX_ARCHIVE_ENTRIES or sum(f.file_size for f in files) > MAX_UNPACKED_BYTES:
                raise ValueError('IPA exceeds archive safety limits')
            candidates = sorted(n for n in z.namelist() if re.fullmatch(r'Payload/[^/]+\.app/Info\.plist', n))
            if len(candidates) != 1:
                raise ValueError('Expected exactly one Payload/*.app/Info.plist')
            info = plistlib.loads(z.read(candidates[0]))
            if not isinstance(info, dict):
                raise ValueError('Invalid Info.plist')
            bundle_id = str(info.get('CFBundleIdentifier', ''))
            if not re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9_.-]{2,254}', bundle_id):
                raise ValueError('Invalid bundle ID')
            name = str(info.get('CFBundleDisplayName') or info.get('CFBundleName') or bundle_id)
            version = str(info.get('CFBundleShortVersionString') or info.get('CFBundleVersion') or '')
            app_root = candidates[0].removesuffix('Info.plist')
            has_profile = app_root + 'embedded.mobileprovision' in z.namelist()
            profile = None
            if has_profile:
                try:
                    profile = parse_provision(z.read(app_root + 'embedded.mobileprovision'))
                except Exception:
                    profile = None
            return {
                'name': name[:200], 'bundle_id': bundle_id, 'version': version[:64],
                'signed_candidate': bool(has_profile and profile),
                'profile_expires': (profile or {}).get('expires_at'),
                'profile_team': (profile or {}).get('team'),
                'profile_bundle_id': (profile or {}).get('bundle_pattern'),
                'profile_uuid': (profile or {}).get('uuid'),
                'profile_devices_json': json.dumps((profile or {}).get('devices', [])),
            }
    except (zipfile.BadZipFile, KeyError, plistlib.InvalidFileException) as e:
        raise ValueError(f'Invalid IPA archive: {e}') from e


def sha256_file(path: Path) -> str:
    hash_ = hashlib.sha256()
    with path.open('rb') as f:
        for block in iter(lambda: f.read(1024 * 1024), b''):
            hash_.update(block)
    return hash_.hexdigest()
