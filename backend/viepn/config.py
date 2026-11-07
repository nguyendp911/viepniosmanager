from __future__ import annotations
import os
import secrets
from dataclasses import dataclass
from pathlib import Path


def app_data() -> Path:
    root = os.environ.get('VIEPN_DATA_DIR')
    if root:
        return Path(root).expanduser().resolve()
    if os.name == 'nt':
        return Path(os.environ.get('LOCALAPPDATA', str(Path.home()))) / 'ViePN-iOS-Manager'
    return Path.home() / '.local' / 'share' / 'viepn-ios-manager'


@dataclass(frozen=True)
class Settings:
    root: Path
    token: str
    host: str
    port: int
    signer: str
    signing_p12: str
    signing_profile: str
    signing_password: str
    renewal_hours: int
    scan_minutes: int
    max_upload_mb: int


def load_settings() -> Settings:
    root = app_data()
    root.mkdir(parents=True, exist_ok=True)
    token_file = root / 'access_token.txt'
    override = os.environ.get('VIEPN_API_TOKEN', '').strip()
    if override:
        token = override
    elif token_file.exists():
        token = token_file.read_text(encoding='utf-8').strip()
    else:
        token = secrets.token_urlsafe(32)
        # Do not add a newline: avoids incorrect copy/paste.
        with token_file.open('x', encoding='utf-8') as f:
            f.write(token)
        try:
            token_file.chmod(0o600)
        except OSError:
            pass
    if len(token) < 20:
        raise ValueError('VIEPN_API_TOKEN must be at least 20 characters')
    return Settings(
        root=root, token=token, host=os.environ.get('VIEPN_HOST', '127.0.0.1'),
        port=int(os.environ.get('VIEPN_PORT', '8765')),
        signer=os.environ.get('VIEPN_ZSIGN', 'zsign'),
        signing_p12=os.environ.get('VIEPN_SIGN_P12', ''),
        signing_profile=os.environ.get('VIEPN_SIGN_PROFILE', ''),
        signing_password=os.environ.get('VIEPN_SIGN_PASSWORD', ''),
        renewal_hours=int(os.environ.get('VIEPN_RENEW_HOURS', '48')),
        scan_minutes=int(os.environ.get('VIEPN_SCAN_MINUTES', '30')),
        max_upload_mb=int(os.environ.get('VIEPN_MAX_UPLOAD_MB', '400')),
    )
