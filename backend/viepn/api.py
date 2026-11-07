from __future__ import annotations
import asyncio
import hmac
import os
import uuid
from contextlib import asynccontextmanager
from datetime import datetime, timezone
from pathlib import Path

from fastapi import Depends, FastAPI, File, Header, HTTPException, UploadFile
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field

from .config import Settings, load_settings
from .free_sign import ShareStore
from .service import Manager
from .native_sign import status as apple_account_status
from .tools import ExternalToolError, check_udid, connected_devices, installed_apps

WEB_ROOT = Path(__file__).resolve().parents[2] / 'web'


class InstallPayload(BaseModel):
    ipa_id: str
    udid: str
    auto_renew: bool = False
    resign: bool = False
    profile_id: str | None = None


class SignPayload(BaseModel):
    ipa_id: str
    udid: str
    profile_id: str | None = None


class AppleInstallPayload(BaseModel):
    ipa_id: str
    udid: str
    auto_renew: bool = True


class AppleSignPayload(BaseModel):
    ipa_id: str
    udid: str


class RenewPayload(BaseModel):
    installation_id: str


def create_app(settings: Settings | None = None) -> FastAPI:
    cfg = settings or load_settings()
    manager = Manager(cfg)
    ipa_shares = ShareStore(ttl_seconds=600)

    @asynccontextmanager
    async def lifespan(_: FastAPI):
        await manager.start()
        yield
        await manager.stop()

    app = FastAPI(title='ViePN iOS Manager', version='1.2.0', lifespan=lifespan,
                  docs_url=None, redoc_url=None, openapi_url=None)
    app.state.manager = manager

    def auth(authorization: str | None = Header(default=None)):
        expected = f'Bearer {cfg.token}'
        if not authorization or not hmac.compare_digest(authorization, expected):
            raise HTTPException(status_code=401, detail='Authentication required')

    @app.get('/')
    def index():
        return FileResponse(WEB_ROOT / 'index.html', headers={'Cache-Control': 'no-store',
                           'Content-Security-Policy': "default-src 'self'; style-src 'unsafe-inline' 'self'; script-src 'unsafe-inline' 'self'; connect-src 'self'; object-src 'none'; base-uri 'none'"})

    @app.get('/api/health')
    def health():
        return {'ok': True, 'service': 'ViePN iOS Manager', 'version': '1.2.0'}

    @app.get('/api/overview', dependencies=[Depends(auth)])
    def overview():
        from shutil import which
        from importlib.util import find_spec
        apps = manager.db.query('SELECT * FROM ipa ORDER BY created_at DESC')
        installs = manager.db.query('SELECT * FROM installations ORDER BY created_at DESC')
        profiles = manager.db.query('SELECT * FROM profiles ORDER BY expires_at DESC')
        jobs = manager.db.query('SELECT * FROM jobs ORDER BY created_at DESC LIMIT 40')
        events = manager.db.query('SELECT * FROM events ORDER BY id DESC LIMIT 30')
        # Hide actual paths from mobile clients; return only required display metadata.
        for a in apps:
            a.pop('file_path', None)
        for p in profiles:
            p.pop('file_path', None)
        return {
            'ipas': apps, 'installations': installs, 'profiles': profiles,
            'jobs': jobs, 'events': events,
            'tools': {'pymobiledevice3': find_spec('pymobiledevice3') is not None,
                      'zsign': bool(which(cfg.signer) or Path(cfg.signer).is_file()),
                      'signing_p12': bool(cfg.signing_p12 and Path(cfg.signing_p12).is_file())},
            'renewal_hours': cfg.renewal_hours,
        }

    @app.get('/api/devices', dependencies=[Depends(auth)])
    async def devices():
        try:
            return {'devices': await asyncio.to_thread(connected_devices)}
        except (ExternalToolError, ValueError) as e:
            raise HTTPException(503, detail=str(e))

    @app.get('/api/device/{udid}/apps', dependencies=[Depends(auth)])
    async def device_apps(udid: str):
        try:
            check_udid(udid)
            return {'apps': await asyncio.to_thread(installed_apps, udid)}
        except ValueError as e:
            raise HTTPException(400, detail=str(e))
        except (ExternalToolError, RuntimeError) as e:
            raise HTTPException(503, detail=str(e))

    async def receive_upload(file: UploadFile, suffix: str) -> Path:
        if not file.filename or not file.filename.lower().endswith(suffix):
            raise HTTPException(400, detail=f'Only {suffix} files are supported')
        target = cfg.root / 'incoming' / (uuid.uuid4().hex + suffix)
        max_bytes = cfg.max_upload_mb * 1024 * 1024
        used = 0
        try:
            with target.open('xb') as output:
                while chunk := await file.read(1024 * 1024):
                    used += len(chunk)
                    if used > max_bytes:
                        raise HTTPException(413, detail='Upload is too large')
                    output.write(chunk)
        except Exception:
            target.unlink(missing_ok=True)
            raise
        finally:
            await file.close()
        return target

    @app.post('/api/ipas', dependencies=[Depends(auth)])
    async def ipa_upload(file: UploadFile = File(...)):
        target = await receive_upload(file, '.ipa')
        try:
            return manager.add_ipa(target)
        except ValueError as e:
            raise HTTPException(400, detail=str(e))
        finally:
            target.unlink(missing_ok=True)

    @app.post('/api/profiles', dependencies=[Depends(auth)])
    async def profile_upload(file: UploadFile = File(...)):
        original_name = Path(file.filename or '').name
        target = await receive_upload(file, '.mobileprovision')
        try:
            profile = manager.add_profile(target, original_name)
            profile.pop('file_path', None)
            return profile
        except ValueError as e:
            raise HTTPException(400, detail=str(e))
        finally:
            target.unlink(missing_ok=True)

    @app.post('/api/install', dependencies=[Depends(auth)])
    async def install(payload: InstallPayload):
        try:
            check_udid(payload.udid)
        except ValueError as e:
            raise HTTPException(400, detail=str(e))
        if not manager.db.one('SELECT id FROM ipa WHERE id=?', (payload.ipa_id,)):
            raise HTTPException(404, detail='Unknown IPA')
        return {'job_id': manager.submit('install', payload.model_dump())}

    @app.post('/api/sign', dependencies=[Depends(auth)])
    async def sign(payload: SignPayload):
        try:
            check_udid(payload.udid)
        except ValueError as e:
            raise HTTPException(400, detail=str(e))
        if not manager.db.one('SELECT id FROM ipa WHERE id=?', (payload.ipa_id,)):
            raise HTTPException(404, detail='Unknown IPA')
        return {'job_id': manager.submit('sign', payload.model_dump())}

    @app.get('/api/apple/status', dependencies=[Depends(auth)])
    async def apple_status():
        # Never return password, two-factor challenge, account session or token.
        return await asyncio.to_thread(apple_account_status)

    @app.post('/api/apple/sign', dependencies=[Depends(auth)])
    async def apple_sign(payload: AppleSignPayload):
        try:
            check_udid(payload.udid)
        except ValueError as exc:
            raise HTTPException(400, detail=str(exc))
        if not manager.db.one('SELECT id FROM ipa WHERE id=?', (payload.ipa_id,)):
            raise HTTPException(404, detail='IPA not found')
        return {'job_id': manager.submit('apple_sign', payload.model_dump())}

    @app.post('/api/apple/install', dependencies=[Depends(auth)])
    async def apple_install(payload: AppleInstallPayload):
        try:
            check_udid(payload.udid)
        except ValueError as exc:
            raise HTTPException(400, detail=str(exc))
        if not manager.db.one('SELECT id FROM ipa WHERE id=?', (payload.ipa_id,)):
            raise HTTPException(404, detail='IPA not found')
        return {'job_id': manager.submit('apple_install', payload.model_dump())}

    @app.post('/api/apple/refresh-all', dependencies=[Depends(auth)])
    async def apple_refresh_all():
        ids = manager.db.query('SELECT id FROM installations WHERE signing_mode='apple_personal'')
        return {'queued_job_ids': [manager.submit('renew', {'installation_id': row['id']})
                                   for row in ids]}

    @app.post('/api/renew', dependencies=[Depends(auth)])
    async def renew(payload: RenewPayload):
        if not manager.db.one('SELECT id FROM installations WHERE id=?', (payload.installation_id,)):
            raise HTTPException(404, detail='Unknown installation')
        return {'job_id': manager.submit('renew', payload.model_dump())}

    @app.post('/api/renew/check', dependencies=[Depends(auth)])
    async def renew_check():
        jobs = await manager.auto_renew_scan()
        return {'queued_job_ids': jobs}

    @app.get('/api/ipa/{ipa_id}/download', dependencies=[Depends(auth)])
    def download(ipa_id: str):
        record = manager.db.one('SELECT * FROM ipa WHERE id=?', (ipa_id,))
        if not record or not Path(record['file_path']).is_file():
            raise HTTPException(404, detail='IPA not found')
        return FileResponse(record['file_path'], filename=record['bundle_id'] + '.ipa',
                            media_type='application/octet-stream')

    @app.get('/api/free/status', dependencies=[Depends(auth)])
    def free_status():
        # Backward compatibility: the signing backend is now native to ViePN.
        return {**apple_account_status(), 'mode': 'native_apple',
                'lan_enabled': cfg.host not in ('127.0.0.1', 'localhost', '::1'),
                'share_ttl_seconds': ipa_shares.ttl_seconds}

    @app.post('/api/free/share/{ipa_id}', dependencies=[Depends(auth)])
    def create_free_share(ipa_id: str):
        # Never place the dashboard bearer token in a download URL.
        record = manager.db.one('SELECT * FROM ipa WHERE id=?', (ipa_id,))
        if not record:
            raise HTTPException(status_code=404, detail='IPA not found')
        try:
            secret, seconds = ipa_shares.create(record['file_path'], record['bundle_id'])
        except ValueError as exc:
            raise HTTPException(status_code=404, detail=str(exc))
        return {
            'path': '/api/free/download/' + secret,
            'expires_in_seconds': seconds,
            'max_downloads': 1,
            'lan_enabled': cfg.host not in ('127.0.0.1', 'localhost', '::1')
        }

    @app.get('/api/free/download/{share_token}')
    def download_shared_ipa(share_token: str):
        # Public-by-capability endpoint; token is 256-bit random, time-limited,
        # and single use. It grants access to this IPA ONLY, not to dashboard API.
        shared = ipa_shares.take(share_token)
        if shared is None:
            raise HTTPException(status_code=404, detail='Share expired or already used')
        path, bundle = shared
        return FileResponse(
            path, filename=bundle + '.ipa', media_type='application/octet-stream',
            headers={'Cache-Control': 'no-store',
                     'Referrer-Policy': 'no-referrer',
                     'X-Content-Type-Options': 'nosniff'}
        )

    return app


app = create_app()
