from __future__ import annotations
import asyncio
import json
import os
import shutil
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

from .config import Settings
from .db import Database, utcnow
from .ipa import inspect_ipa, parse_provision, profile_compatible, sha256_file
from .tools import connected_devices, install_signed_ipa, sign_with_zsign
from .native_sign import sign_free_ipa


class Manager:
    def __init__(self, config: Settings):
        self.cfg = config
        self.db = Database(config.root / 'viepn.sqlite3')
        self.lock = asyncio.Lock()
        self.background_task: asyncio.Task | None = None
        (config.root / 'ipas').mkdir(exist_ok=True)
        (config.root / 'profiles').mkdir(exist_ok=True)
        (config.root / 'incoming').mkdir(exist_ok=True)
        self.db.exec("UPDATE jobs SET state='failed', updated_at=?, output_json=? WHERE state IN ('queued','running')",
                     (utcnow(), json.dumps({'error': 'Interrupted by service restart'})))

    def add_ipa(self, temp_path: Path) -> dict:
        meta = inspect_ipa(temp_path)
        checksum = sha256_file(temp_path)
        record = self.db.one('SELECT * FROM ipa WHERE sha256=?', (checksum,))
        if record:
            temp_path.unlink(missing_ok=True)
            return record
        target = self.cfg.root / 'ipas' / f'{checksum}.ipa'
        os.replace(temp_path, target)
        key = checksum[:24]
        self.db.exec('''INSERT INTO ipa
            (id,name,bundle_id,version,file_path,sha256,size_bytes,
             profile_expires,profile_team,profile_bundle_id,profile_uuid,
             profile_devices_json,signed_candidate,created_at)
             VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?)''',
            (key, meta['name'], meta['bundle_id'], meta['version'], str(target), checksum,
             target.stat().st_size, meta['profile_expires'], meta['profile_team'],
             meta['profile_bundle_id'], meta['profile_uuid'], meta['profile_devices_json'],
             int(meta['signed_candidate']), utcnow()))
        self.db.event('ipa_uploaded', f"{meta['name']} {meta['bundle_id']}")
        return self.db.one('SELECT * FROM ipa WHERE id=?', (key,))

    def add_profile(self, temp_path: Path, filename: str) -> dict:
        meta = parse_provision(temp_path.read_bytes())
        checksum = sha256_file(temp_path)
        existing = self.db.one('SELECT * FROM profiles WHERE sha256=?', (checksum,))
        if existing:
            temp_path.unlink(missing_ok=True)
            return existing
        target = self.cfg.root / 'profiles' / f'{checksum}.mobileprovision'
        os.replace(temp_path, target)
        profile_id = checksum[:24]
        self.db.exec('''INSERT INTO profiles
            (id, filename, file_path, sha256, expires_at, team, bundle_pattern, uuid, devices_json, created_at)
            VALUES(?,?,?,?,?,?,?,?,?,?)''',
            (profile_id, filename[:120], str(target), checksum, meta['expires_at'],
             meta['team'], meta['bundle_pattern'], meta['uuid'],
             json.dumps(meta['devices']), utcnow()))
        self.db.event('profile_uploaded', filename[:120])
        return self.db.one('SELECT * FROM profiles WHERE id=?', (profile_id,))

    def get_profile(self, profile_id: str | None, bundle_id: str, udid: str,
                    previous_expiry: str | None = None) -> dict:
        if profile_id:
            profiles = [self.db.one('SELECT * FROM profiles WHERE id=?', (profile_id,))]
        else:
            profiles = self.db.query('SELECT * FROM profiles ORDER BY expires_at DESC')
            if self.cfg.signing_profile and Path(self.cfg.signing_profile).is_file():
                path = Path(self.cfg.signing_profile)
                meta = parse_provision(path.read_bytes())
                profiles.append({'id': 'environment', 'file_path': str(path),
                                 'expires_at': meta['expires_at'], 'bundle_pattern': meta['bundle_pattern'],
                                 'devices_json': json.dumps(meta['devices']), 'team': meta['team']})
            profiles.sort(key=lambda p: (p or {}).get('expires_at') or '', reverse=True)
        for profile in profiles:
            if profile and profile_compatible({'expires_at': profile.get('expires_at'),
                'bundle_pattern': profile.get('bundle_pattern'),
                'devices': json.loads(profile.get('devices_json') or '[]')}, bundle_id, udid, previous_expiry):
                return profile
        raise ValueError('No newer, valid and device-compatible provisioning profile. Import one via Profiles or use SideStore to renew.')

    async def sign(self, ipa_id: str, udid: str, profile_id: str | None = None,
                   previous_expiry: str | None = None) -> dict:
        original = self.db.one('SELECT * FROM ipa WHERE id=?', (ipa_id,))
        if not original:
            raise ValueError('IPA not found')
        if not self.cfg.signing_p12:
            raise ValueError('Configure VIEPN_SIGN_P12 and VIEPN_SIGN_PASSWORD first')
        profile = self.get_profile(profile_id, original['bundle_id'], udid, previous_expiry)
        temp = self.cfg.root / 'incoming' / f'{uuid.uuid4().hex}.ipa'
        try:
            await asyncio.to_thread(sign_with_zsign, self.cfg.signer,
                Path(original['file_path']), temp, Path(self.cfg.signing_p12),
                Path(profile['file_path']), self.cfg.signing_password)
            metadata = inspect_ipa(temp)
            if not metadata['signed_candidate'] or metadata['bundle_id'] != original['bundle_id']:
                raise ValueError('Signer output lacks matching embedded provisioning metadata')
            if metadata['profile_expires'] != profile['expires_at']:
                raise ValueError('Signer output has an unexpected provisioning expiration')
            return self.add_ipa(temp)
        finally:
            temp.unlink(missing_ok=True)

    def submit(self, kind: str, payload: dict) -> str:
        if kind not in ('install', 'sign', 'renew', 'apple_install', 'apple_sign'):
            raise ValueError('Unknown job type')
        job_id = uuid.uuid4().hex
        self.db.exec('''INSERT INTO jobs(id,kind,state,input_json,created_at,updated_at)
            VALUES(?,?,?,?,?,?)''', (job_id, kind, 'queued', json.dumps(payload), utcnow(), utcnow()))
        asyncio.create_task(self._process(job_id))
        return job_id

    async def _process(self, job_id: str):
        async with self.lock:
            job = self.db.one('SELECT * FROM jobs WHERE id=?', (job_id,))
            if not job:
                return
            self.db.exec("UPDATE jobs SET state='running',updated_at=? WHERE id=?", (utcnow(), job_id))
            params = json.loads(job['input_json'])
            try:
                if job['kind'] == 'sign':
                    signed = await self.sign(params['ipa_id'], params['udid'], params.get('profile_id'))
                    output = {'signed_ipa_id': signed['id'], 'expires_at': signed['profile_expires']}
                elif job['kind'] == 'install':
                    output = await self._install(params)
                elif job['kind'] == 'apple_install':
                    output = await self._apple_install(params)
                elif job['kind'] == 'apple_sign':
                    output = await self._apple_sign(params)
                else:
                    output = await self._renew(params['installation_id'])
            except Exception as exc:
                message = str(exc)[:1500]
                self.db.exec('UPDATE jobs SET state=?,output_json=?,updated_at=? WHERE id=?',
                             ('failed', json.dumps({'error': message}), utcnow(), job_id))
                self.db.event('job_failed', f"{job['kind']}: {message}")
                return
            self.db.exec('UPDATE jobs SET state=?,output_json=?,updated_at=? WHERE id=?',
                         ('succeeded', json.dumps(output), utcnow(), job_id))
            self.db.event('job_succeeded', job['kind'])

    async def _apple_sign(self, params: dict) -> dict:
        """Obtain a fresh Apple Personal Team profile and sign without other apps."""
        ipa = self.db.one('SELECT * FROM ipa WHERE id=?', (params['ipa_id'],))
        if not ipa:
            raise ValueError('Source IPA not found')
        udid = str(params['udid'])
        temp = self.cfg.root / 'incoming' / f'{uuid.uuid4().hex}.ipa'
        try:
            details = await asyncio.to_thread(
                sign_free_ipa, Path(ipa['file_path']), temp, udid
            )
            signed = self.add_ipa(temp)
            return {
                'signed_ipa_id': signed['id'],
                'source_ipa_id': ipa['id'],
                'bundle_id': details['bundle_id'],
                'expires_at': signed['profile_expires'],
                'account': details.get('account'),
            }
        finally:
            temp.unlink(missing_ok=True)

    async def _apple_install(self, params: dict) -> dict:
        """Apple GSA -> provisioning -> sign -> install; native ViePN pipeline."""
        result = await self._apple_sign(params)
        installed = await self._install({
            'ipa_id': result['signed_ipa_id'],
            'udid': params['udid'],
            'resign': False,
            'auto_renew': bool(params.get('auto_renew', True)),
        })
        self.db.exec('''UPDATE installations SET source_ipa_id=?,
                       auto_renew=? WHERE id=?''',
                     (result['source_ipa_id'],
                      2 if params.get('auto_renew', True) else 0,
                      installed['installation_id']))
        return {**installed, 'signing_mode': 'free_apple_id',
                'signed_ipa_id': result['signed_ipa_id']}

    async def _apple_renew(self, install: dict) -> dict:
        """Issue NEW Personal Team profile and re-sign original IPA before 7d."""
        installation_id = install['id']
        self.db.exec('UPDATE installations SET last_attempt=?,state=? WHERE id=?',
                     (utcnow(), 'renewing', installation_id))
        try:
            result = await self._apple_sign({
                'ipa_id': install['source_ipa_id'],
                'udid': install['device_udid'],
            })
            if not result.get('expires_at'):
                raise ValueError('Apple did not provide expiry of renewed profile')
            previous = datetime.fromisoformat(install['expires_at'])
            refreshed = datetime.fromisoformat(result['expires_at'])
            if refreshed <= previous:
                raise ValueError('Apple did not issue a newer provisioning profile')
            outcome = await self._install({
                'ipa_id': result['signed_ipa_id'],
                'udid': install['device_udid'],
                'resign': False,
                'auto_renew': True,
            })
            self.db.exec('''UPDATE installations SET source_ipa_id=?,auto_renew=2,
                           current_ipa_id=?,expires_at=?,state='active',
                           last_success=?,last_error=NULL WHERE id=?''',
                         (install['source_ipa_id'], result['signed_ipa_id'],
                          result['expires_at'], utcnow(), installation_id))
            return {**outcome, 'signing_mode': 'free_apple_id',
                    'expires_at': result['expires_at']}
        except Exception as exc:
            self.db.exec('UPDATE installations SET state=?,last_error=? WHERE id=?',
                         ('needs_attention', str(exc)[:1500], installation_id))
            raise

    async def _install(self, params: dict) -> dict:
        ipa = self.db.one('SELECT * FROM ipa WHERE id=?', (params['ipa_id'],))
        if not ipa:
            raise ValueError('IPA does not exist')
        device = str(params['udid'])
        if params.get('resign'):
            signed = await self.sign(ipa['id'], device, params.get('profile_id'))
        else:
            signed = ipa
        if not signed['signed_candidate']:
            raise ValueError('IPA is not signed. Choose Sign before installing. Presence of a profile is not proof of trust.')
        if not signed['profile_expires']:
            raise ValueError('Unable to determine signature expiration')
        expiry = datetime.fromisoformat(signed['profile_expires'])
        if expiry <= datetime.now(timezone.utc):
            raise ValueError('Signing profile has expired')
        # Apple decides whether the real signature and entitlements are valid.
        await asyncio.to_thread(install_signed_ipa, Path(signed['file_path']), device)
        identity = f'{device}:{signed["bundle_id"]}'
        now = utcnow()
        self.db.exec('''INSERT INTO installations
          (id,device_udid,bundle_id,source_ipa_id,current_ipa_id,expires_at,
           auto_renew,state,last_success,created_at)
          VALUES(?,?,?,?,?,?,?,?,?,?)
          ON CONFLICT(device_udid,bundle_id) DO UPDATE SET
          source_ipa_id=excluded.source_ipa_id,current_ipa_id=excluded.current_ipa_id,
          expires_at=excluded.expires_at,auto_renew=excluded.auto_renew,state='active',
          last_success=excluded.last_success,last_error=NULL''',
          (identity, device, signed['bundle_id'], ipa['id'], signed['id'],
           signed['profile_expires'], int(bool(params.get('auto_renew'))), 'active', now, now))
        return {'installation_id': identity, 'bundle_id': signed['bundle_id'],
                'expires_at': signed['profile_expires'], 'note': 'Device installation command completed'}

    async def _renew(self, installation_id: str) -> dict:
        install = self.db.one('SELECT * FROM installations WHERE id=?', (installation_id,))
        if not install:
            raise ValueError('Installation not found')
        if int(install.get('auto_renew') or 0) == 2:
            return await self._apple_renew(install)
        self.db.exec('UPDATE installations SET last_attempt=?,state=? WHERE id=?',
                     (utcnow(), 'renewing', installation_id))
        try:
            # Never reuse an older profile; 7-day profiles must be renewed upstream.
            signed = await self.sign(install['source_ipa_id'], install['device_udid'],
                                     previous_expiry=install['expires_at'])
            await asyncio.to_thread(install_signed_ipa, Path(signed['file_path']), install['device_udid'])
        except Exception as e:
            self.db.exec('UPDATE installations SET state=?,last_error=? WHERE id=?',
                         ('needs_attention', str(e)[:1500], installation_id))
            raise
        self.db.exec('''UPDATE installations SET current_ipa_id=?,expires_at=?,
            state='active',last_success=?,last_error=NULL WHERE id=?''',
            (signed['id'], signed['profile_expires'], utcnow(), installation_id))
        return {'installation_id': installation_id, 'expires_at': signed['profile_expires']}

    def due_installations(self) -> list[dict]:
        now = datetime.now(timezone.utc)
        cutoff = now + timedelta(hours=self.cfg.renewal_hours)
        rows = self.db.query('SELECT * FROM installations WHERE auto_renew IN (1,2)')
        result = []
        for r in rows:
            try:
                expires = datetime.fromisoformat(r['expires_at'])
                attempted = datetime.fromisoformat(r['last_attempt']) if r['last_attempt'] else None
                if expires <= cutoff and (not attempted or attempted < now - timedelta(hours=6)):
                    result.append(r)
            except (ValueError, TypeError):
                continue
        return result

    async def auto_renew_scan(self) -> list[str]:
        queued = []
        for row in self.due_installations():
            existing = self.db.one("SELECT id FROM jobs WHERE kind='renew' AND state IN ('queued','running') AND input_json=?",
                                   (json.dumps({'installation_id': row['id']}),))
            if not existing:
                queued.append(self.submit('renew', {'installation_id': row['id']}))
                self.db.exec('UPDATE installations SET last_attempt=? WHERE id=?', (utcnow(), row['id']))
        return queued

    async def scheduler(self):
        try:
            await self.auto_renew_scan()
            while True:
                await asyncio.sleep(max(60, self.cfg.scan_minutes * 60))
                await self.auto_renew_scan()
        except asyncio.CancelledError:
            raise

    async def start(self):
        self.background_task = asyncio.create_task(self.scheduler())

    async def stop(self):
        if self.background_task:
            self.background_task.cancel()
            try:
                await self.background_task
            except asyncio.CancelledError:
                pass
