"""Offline ViePN restore operator command, not a network API."""
from __future__ import annotations

import argparse
from pathlib import Path

from viepn.config import app_data
from viepn.restore import restore_backup


def main() -> None:
    parser = argparse.ArgumentParser(description="Restore ViePN IPA and database offline")
    parser.add_argument("backup", type=Path, help="Local ViePN-*.zip archive")
    parser.add_argument("--confirm", required=True, help="Must be exactly RESTORE VIEPN")
    args = parser.parse_args()
    report = restore_backup(app_data(), args.backup, args.confirm)
    print("ViePN restore completed:", report)
    print("Apple sessions and API token were not touched; re-check all IPA/renewal states.")


if __name__ == "__main__":
    main()
