from __future__ import annotations
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


def utcnow() -> str:
    return datetime.now(timezone.utc).isoformat()


class Database:
    def __init__(self, path: Path):
        path.parent.mkdir(parents=True, exist_ok=True)
        self.path = path
        self.initialize()

    def connect(self):
        db = sqlite3.connect(self.path, timeout=15)
        db.row_factory = sqlite3.Row
        db.execute('PRAGMA foreign_keys=ON')
        db.execute('PRAGMA busy_timeout=15000')
        return db

    def initialize(self):
        with self.connect() as db:
            db.execute('PRAGMA journal_mode=WAL')
            db.executescript('''
                CREATE TABLE IF NOT EXISTS ipa (
                    id TEXT PRIMARY KEY, name TEXT NOT NULL, bundle_id TEXT NOT NULL,
                    version TEXT, file_path TEXT NOT NULL, sha256 TEXT UNIQUE NOT NULL,
                    size_bytes INTEGER NOT NULL, profile_expires TEXT,
                    profile_team TEXT, profile_bundle_id TEXT, profile_uuid TEXT,
                    profile_devices_json TEXT NOT NULL DEFAULT '[]',
                    signed_candidate INTEGER NOT NULL DEFAULT 0,
                    created_at TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS profiles (
                    id TEXT PRIMARY KEY, filename TEXT NOT NULL,
                    file_path TEXT NOT NULL, sha256 TEXT UNIQUE NOT NULL,
                    expires_at TEXT, team TEXT, bundle_pattern TEXT,
                    uuid TEXT, devices_json TEXT NOT NULL DEFAULT '[]',
                    created_at TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS installations (
                    id TEXT PRIMARY KEY, device_udid TEXT NOT NULL,
                    bundle_id TEXT NOT NULL, source_ipa_id TEXT NOT NULL,
                    current_ipa_id TEXT NOT NULL, expires_at TEXT,
                    auto_renew INTEGER NOT NULL DEFAULT 0, state TEXT NOT NULL,
                    last_attempt TEXT, last_success TEXT, last_error TEXT,
                    created_at TEXT NOT NULL,
                    UNIQUE(device_udid,bundle_id)
                );
                CREATE TABLE IF NOT EXISTS jobs (
                    id TEXT PRIMARY KEY, kind TEXT NOT NULL, state TEXT NOT NULL,
                    input_json TEXT NOT NULL, output_json TEXT, created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS events (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    kind TEXT NOT NULL, detail TEXT NOT NULL, created_at TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS notification_sent (
                    id TEXT PRIMARY KEY, created_at TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS pending_ipa_deletes (
                    filename TEXT PRIMARY KEY,
                    sha256 TEXT NOT NULL,
                    created_at TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS remote_devices (
                    id TEXT PRIMARY KEY,
                    name TEXT NOT NULL,
                    ble_token TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    seen_at TEXT NOT NULL
                );
            ''')
            ipa_columns = {row['name'] for row in db.execute('PRAGMA table_info(ipa)')}
            if 'alias' not in ipa_columns:
                db.execute("ALTER TABLE ipa ADD COLUMN alias TEXT")
            if 'channel' not in ipa_columns:
                db.execute("ALTER TABLE ipa ADD COLUMN channel TEXT NOT NULL DEFAULT 'unassigned'")
            columns = {row['name'] for row in db.execute('PRAGMA table_info(installations)')}
            if 'signing_mode' not in columns:
                db.execute("ALTER TABLE installations ADD COLUMN signing_mode TEXT NOT NULL DEFAULT 'legacy'")
            if 'apple_account' not in columns:
                db.execute("ALTER TABLE installations ADD COLUMN apple_account TEXT")
            if 'retry_failures' not in columns:
                db.execute("ALTER TABLE installations ADD COLUMN retry_failures INTEGER NOT NULL DEFAULT 0")
            job_columns = {row['name'] for row in db.execute('PRAGMA table_info(jobs)')}
            if 'retry_of' not in job_columns:
                db.execute("ALTER TABLE jobs ADD COLUMN retry_of TEXT")

            # Compatibility with early experimental mode encoding (auto_renew=2).
            db.execute("""UPDATE installations
                       SET signing_mode='apple_personal', auto_renew=1
                       WHERE auto_renew=2 AND signing_mode='legacy'""")

    def query(self, sql: str, args: tuple = ()) -> list[dict[str, Any]]:
        with self.connect() as db:
            return [dict(r) for r in db.execute(sql, args).fetchall()]

    def one(self, sql: str, args: tuple = ()) -> dict[str, Any] | None:
        records = self.query(sql, args)
        return records[0] if records else None

    def exec(self, sql: str, args: tuple = ()):
        with self.connect() as db:
            db.execute(sql, args)

    def event(self, kind: str, detail: str):
        self.exec('INSERT INTO events(kind,detail,created_at) VALUES(?,?,?)', (kind, detail[:1000], utcnow()))
