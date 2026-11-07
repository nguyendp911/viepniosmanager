"""ViePN native free Apple Account signing flow for Windows.

No SideStore, AltStore, or iLoader runtime. Apple GSA/Developer protocol code
is embedded in viepn.applekit with its original MIT license and attribution.
Authentication runs locally. Browser login is available only on loopback Windows\nwith a separate bearer-token authenticated API; PowerShell remains supported.

Apple does not publish/support the Personal Team web protocol. Actual login,
profile issuance and device installation MUST be verified on physical hardware.
"""
from __future__ import annotations

import getpass
import importlib.util
import json
import os
import shutil
import sys
import tempfile
from pathlib import Path

from .config import app_data
from .ipa import inspect_ipa
from .applekit import gsa, ipa as ipa_tools, provision, signing

CONSENT_FILE = "apple-connection.json"


class NativeSigningError(RuntimeError):
    pass


def _consent_file() -> Path:
    return app_data() / CONSENT_FILE


def _apple_environment() -> None:
    """Require explicit consent before contacting ANY community anisette service."""
    override = os.environ.get("VIEPN_ANISETTE_SERVER", "").strip()
    if not override:
        try:
            settings = json.loads(_consent_file().read_text(encoding="utf-8"))
        except (OSError, ValueError):
            settings = {}
        override = str(settings.get("server") or "")
        community = settings.get("allow_community") is True
    else:
        community = False

    if override:
        if not override.startswith("https://"):
            raise NativeSigningError("VIEPN_ANISETTE_SERVER must be https://")
        os.environ["IPASIDE_ANISETTE_SERVER"] = override
    elif not community:
        raise NativeSigningError(
            "Apple ID login needs Mac-generated anisette. Run "
            "windows\\apple-login.ps1 and explicitly select your own server "
            "or approve use of an external anisette provider. "
            "ViePN never sends Apple credentials to that provider."
        )


def status() -> dict:
    try:
        account = gsa.status()
    except Exception as exc:
        account = {"authenticated": False, "reason": str(exc)[:250]}
    try:
        profile = json.loads(_consent_file().read_text(encoding="utf-8"))
    except (OSError, ValueError):
        profile = {}
    return {
        "backend": "native_apple",
        "authenticated": bool(account.get("authenticated")),
        "email": account.get("email") if account.get("authenticated") else None,
        "anisette_configured": bool(
            os.environ.get("VIEPN_ANISETTE_SERVER") or profile.get("server")
            or profile.get("allow_community")),
        "external_anisette": bool(
            profile.get("allow_community") and not profile.get("server")),
        "python_signer_available": importlib.util.find_spec("ipasign") is not None,
        "zsign_available": bool(shutil.which("zsign") or
                               os.environ.get("VIEPN_ZSIGN") or
                               os.environ.get("IPASIDE_ZSIGN")),
        "requires_p12_upload": False,
        "apple_protocol_supported": False,  # private, subject to change
        "refresh_requires_reachable_iphone": True,
    }


def configure_anisette(server: str | None, allow_community: bool = False) -> None:
    """Save explicit user-selected anisette configuration for the Windows user."""
    from urllib.parse import urlsplit

    if server:
        parsed = urlsplit(server.strip())
        if (parsed.scheme != 'https' or not parsed.hostname
                or parsed.username or parsed.password or parsed.fragment):
            raise NativeSigningError('Anisette server must be a valid HTTPS URL')
        profile = {"server": server.strip().rstrip('/'), "allow_community": False}
    elif allow_community:
        profile = {"server": "", "allow_community": True}
        if not os.environ.get("VIEPN_ANISETTE_SERVER"):
            os.environ.pop("IPASIDE_ANISETTE_SERVER", None)
    else:
        raise NativeSigningError('Select an HTTPS anisette server or consent to community providers')

    path = _consent_file()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(profile), encoding='utf-8')


def select_anisette_interactive() -> None:
    print("\nApple's free Personal Team login needs Mac-generated anisette.")
    print("This data is separate from your Apple ID, password and 2FA.")
    print("You may supply your OWN HTTPS anisette server.")
    own = input("Your server https://... [Enter if none]: ").strip()
    if own:
        if not own.startswith("https://"):
            raise NativeSigningError("Anisette server URL must begin with https://")
        profile = {"server": own, "allow_community": False}
    else:
        print("\nCommunity anisette providers are operated by other parties.")
        print("They can see your IP and random device identity, NOT your Apple ID password.")
        print("If you require no external providers at all, answer N.")
        approval = input("Allow community anisette providers? [y/N]: ").strip().lower()
        if approval not in ("y", "yes"):
            raise NativeSigningError(
                "Cannot complete Windows-only Apple Account login without "
                "accepted Mac anisette data. No credentials were sent."
            )
        profile = {"server": "", "allow_community": True}

    path = _consent_file()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(profile), encoding="utf-8")
    _apple_environment()


def login_interactive() -> dict:
    """Local terminal-only Apple authentication. Never accept credentials via API."""
    if not status()["anisette_configured"]:
        select_anisette_interactive()
    else:
        _apple_environment()
    print("\nApple ID credentials are sent only to Apple's authentication endpoints.")
    email = input("Apple ID email: ").strip()
    if not email or "@" not in email:
        raise NativeSigningError("Enter a valid Apple ID email address")
    password = getpass.getpass("Apple ID password (hidden): ")
    if not password:
        raise NativeSigningError("Empty password")
    try:
        result = gsa.begin_login(email, password)
        if result.get("status") == "2fa_required":
            print("Apple verification required: " + str(result.get("method", "")))
            code = input("6-digit 2FA code: ").strip()
            if len(code) != 6 or not code.isdecimal():
                raise NativeSigningError("Expected 6-digit 2FA code")
            result = gsa.complete_2fa(email, password, code)
        if result.get("status") in ("2fa_required", "error"):
            raise NativeSigningError("Apple authentication was not completed")
        print("Apple ID authenticated. Session will be saved for local re-use.")
        return {"authenticated": True, "email": email}
    finally:
        # Do not persist the password in environment, API, files, or logs.
        del password


def sign_free_ipa(source: Path, destination: Path, udid: str,
                  account_email: str | None = None) -> dict:
    """Sign under the original Apple account, ignoring another active UI account."""
    with gsa.acting_as(account_email):
        return _sign_free_ipa_impl(source, destination, udid, account_email)


def _sign_free_ipa_impl(source: Path, destination: Path, udid: str,
                        account_email: str | None) -> dict:
    """Get NEW Apple profile, sign IPA, return signed file metadata.

    This *only signs*. Installer and account tracking are owned by Manager.
    """
    from .tools import check_udid
    check_udid(udid)
    source = Path(source).resolve()
    destination = Path(destination).resolve()
    if not source.is_file() or source.suffix.lower() != ".ipa":
        raise NativeSigningError("Source IPA not found")
    if source == destination:
        raise NativeSigningError("Output cannot overwrite original IPA")

    _apple_environment()
    try:
        gsa.load_session(account_email)
    except Exception:
        raise NativeSigningError(
            "Apple ID session is missing or expired. Sign in again under the original account "
            "in ViePN or run windows\\apple-login.ps1 locally."
        ) from None
    info = ipa_tools.inspect(str(source))
    if info.get("has_sc_info"):
        raise NativeSigningError("App Store encrypted IPA cannot be re-signed")
    original_bundle = info.get("bundle_id")
    if not original_bundle:
        raise NativeSigningError("IPA has no valid bundle identifier")

    target_bundle = provision.team_scoped_bundle_id(original_bundle)
    assets = provision.ensure_signing_assets(
        target_bundle, udid,
        app_name=str(info.get("display_name") or original_bundle)[:70],
    )
    destination.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="viepnsign_") as scratch:
        prepared = Path(scratch) / "prepared.ipa"
        ipa_tools.prepare(
            str(source), str(prepared), bundle_id=target_bundle,
            strip_extensions=True, remove_device_restrictions=True,
        )
        try:
            # Pure Python signer; avoids asking users to install a separate GUI app.
            from ipasign import Key
            signer = Key(
                assets["p12_path"], assets["profile_path"],
                assets["p12_password"],
            )
            signer.sign(str(prepared), str(destination))
        except ImportError:
            # Fallback for machines that provide a cross-platform zsign binary.
            executable = os.environ.get("VIEPN_ZSIGN") or signing.resolve_zsign()
            os.environ["IPASIDE_ZSIGN"] = executable
            signing.sign_ipa(
                str(prepared), str(destination),
                p12_path=assets["p12_path"],
                p12_password=assets["p12_password"],
                profile_path=assets["profile_path"],
                bundle_id=target_bundle,
                remove_extensions=False,
                remove_watch=False,
                remove_uisd=False,
            )

    metadata = inspect_ipa(destination)
    if not metadata.get("signed_candidate"):
        destination.unlink(missing_ok=True)
        raise NativeSigningError("Signed IPA does not contain provisioning metadata")
    if metadata["bundle_id"] != target_bundle:
        destination.unlink(missing_ok=True)
        raise NativeSigningError("Signing output bundle ID mismatch")
    if not metadata.get("profile_expires"):
        destination.unlink(missing_ok=True)
        raise NativeSigningError("Signing output profile expiration is missing")

    return {
        "original_bundle_id": original_bundle,
        "bundle_id": target_bundle,
        "expires_at": metadata["profile_expires"],
        "account": assets.get("account"),
        "team_id": assets.get("team_id"),
        "output": str(destination),
    }


def main() -> int:
    import argparse
    p = argparse.ArgumentParser(description="ViePN native Apple ID engine")
    p.add_argument("action", choices=["login", "status"])
    args = p.parse_args()
    try:
        if args.action == "login":
            print(login_interactive())
        else:
            print(json.dumps(status(), ensure_ascii=False, indent=2))
        return 0
    except Exception as exc:
        print("ViePN Apple ID error: " + str(exc), file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
