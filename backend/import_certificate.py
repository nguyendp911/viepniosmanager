"""Local Windows operator command to import Apple Ad Hoc P12 + profile.

Never pass a P12 password on the command line or to the Tailscale API.
"""
from __future__ import annotations
import argparse
import getpass
from pathlib import Path

from viepn.certificate_vault import import_pair


def main() -> None:
    parser = argparse.ArgumentParser(description="Import matching Apple Ad Hoc signing credentials")
    parser.add_argument("--p12", type=Path, required=True)
    parser.add_argument("--profile", type=Path, required=True)
    args = parser.parse_args()
    if not args.p12.is_file() or not args.profile.is_file():
        parser.error("P12 or mobileprovision not found")
    password = getpass.getpass("P12 password (hidden, stored under Windows DPAPI): ")
    result = import_pair(args.p12, args.profile, password)
    print("Certificate and profile match:", result["matched"])
    print("Mode:", result["mode"])
    print("Bundle scope:", result["bundle_pattern"])
    print("Number of provisioned devices:", result["devices_count"])
    print("Expires:", result["expires_at"])
    print("CMS signature not cryptographically verified by this metadata check.")
    print("Do not upload certificates to GitHub. Apple validates signatures on installation.")


if __name__ == "__main__":
    main()
