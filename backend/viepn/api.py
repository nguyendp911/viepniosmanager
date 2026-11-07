from __future__ import annotations
import asyncio
import ipaddress
import hmac
import os
import uuid
from contextlib import asynccontextmanager
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlsplit

from fastapi import Depends, FastAPI, File, Header, HTTPException, UploadFile, Request
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field

from .config import Settings, load_settings
from .free_sign import ShareStore
from .service import Manager
from .backups import create_backup, list_backups, verify_backup
from .doctor import doctor
from .native_sign import status as apple_account_status
from .apple_auth import AppleAuthFlow
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


class AppleAnisetteChoice(BaseModel):
    mode: str
    server: str | None = None
    consent: bool = False


class AppleAccountLogin(BaseModel):
    email: str
    password: str


class AppleAccountVerification(BaseModel):
    challenge: str
    code: str


class AppleAccountSelection(BaseModel):
    email: str


class AppleAccountLogout(BaseModel):
    email: str | None = None


class NotificationChoice(BaseModel):
    enabled: bool
    consent: bool = False


class ChannelIPARequest(BaseModel):
    channel: str


class RenameIPARequest(BaseModel):
    alias: str = Field(default='', max_length=80)


class DeleteIPARequest(BaseModel):
    all: bool = False
    ipa_ids: list[str] = Field(default_factory=list, max_length=10000)
    force: bool = False
    confirm: str


class RetryJobPayload(BaseModel):
    confirm: str


class RenewPayload(BaseModel):
    installation_id: str


def create_app(settings: Settings | None = None) -> FastAPI:
    cfg = settings or load_settings()
    manager = Manager(cfg)
    ipa_shares = ShareStore(ttl_seconds=600)
    apple_auth = AppleAuthFlow()

    @asynccontextmanager
    async def lifespan(_: FastAPI):
        await manager.start()
        yield
        await manager.stop()

    app = FastAPI(title='ViePN iOS Manager', version='2.1.0', lifespan=lifespan,
                  docs_url=None, redoc_url=None, openapi_url=None)
    app.state.manager = manager

    def auth(authorization: str | None = Header(default=None)):
        expected = f'Bearer {cfg.token}'
        if not authorization or not hmac.compare_digest(authorization, expected):
            raise HTTPException(status_code=401, detail='Authentication required')

    def local_apple_control(request: Request):
        """Protect Apple credentials and account controls from LAN access/CSRF.

        Must use localhost on a ViePN instance bound only to loopback. The
        existing bearer token is still required for every endpoint.
        """
        if cfg.host not in ('127.0.0.1', 'localhost', '::1'):
            raise HTTPException(403, detail='Apple account control requires a loopback-only server')
        try:
            peer = ipaddress.ip_address(request.client.host if request.client else '')
            address = ipaddress.ip_address(request.url.hostname or '')
        except ValueError:
            raise HTTPException(403, detail='Open ViePN directly at http://127.0.0.1:8765')
        if not (peer.is_loopback and address.is_loopback):
            raise HTTPException(403, detail='Apple account control is local to this Windows computer')
        if request.method != 'GET':
            origin = request.headers.get('origin')
            if not origin:
                raise HTTPException(403, detail='A local browser Origin is required')
            parsed = urlsplit(origin)
            if (parsed.scheme != 'http' or parsed.hostname != request.url.hostname
                    or parsed.port != request.url.port):
                raise HTTPException(403, detail='Cross-origin Apple account action blocked')

    @app.get('/')
    def index():
        return FileResponse(WEB_ROOT / 'index.html', headers={'Cache-Control': 'no-store',
                           'Content-Security-Policy': "default-src 'self'; style-src 'unsafe-inline' 'self'; script-src 'unsafe-inline' 'self'; connect-src 'self'; object-src 'none'; base-uri 'none'"})

    @app.get('/api/health')
    def health():
        return {'ok': True, 'service': 'ViePN iOS Manager', 'version': '2.1.0'}

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

    @app.patch('/api/ipas/{ipa_id}/channel', dependencies=[Depends(auth)])
    async def channel_library_ipa(ipa_id: str, payload: ChannelIPARequest):
        async with manager.lock:
            try:
                result = manager.classify_ipa(ipa_id, payload.channel)
            except ValueError as exc:
                raise HTTPException(400, detail=str(exc)) from exc
        if result is None:
            raise HTTPException(404, detail='IPA not found')
        return result

    @app.patch('/api/ipas/{ipa_id}/label', dependencies=[Depends(auth)])
    async def rename_library_ipa(ipa_id: str, payload: RenameIPARequest):
        async with manager.lock:
            try:
                result = manager.rename_ipa(ipa_id, payload.alias)
            except ValueError as exc:
                raise HTTPException(status_code=400, detail=str(exc)) from exc
        if result is None:
            raise HTTPException(404, detail='IPA not found')
        return result

    @app.get('/api/doctor', dependencies=[Depends(auth)])
    async def connection_doctor():
        return await asyncio.to_thread(doctor, cfg)

    @app.get('/api/backups', dependencies=[Depends(auth), Depends(local_apple_control)])
    def backups_list():
        return {'backups': list_backups(cfg.root)}

    @app.post('/api/backups', dependencies=[Depends(auth), Depends(local_apple_control)])
    async def backups_create():
        async with manager.lock:
            try:
                return await asyncio.to_thread(create_backup, cfg.root, manager.db, 'manual')
            except (ValueError, OSError) as exc:
                raise HTTPException(409, detail=str(exc)) from exc

    @app.get('/api/backups/{name}', dependencies=[Depends(auth), Depends(local_apple_control)])
    async def backups_download(name: str):
        # Names are generated, never accept arbitrary paths or user files.
        import re
        if not re.fullmatch(r'ViePN-[0-9]{8}-[0-9]{6}-[a-f0-9]{8}\.zip', name):
            raise HTTPException(404, detail='Backup not found')
        source = (cfg.root / 'backups' / name).resolve()
        if source.parent != (cfg.root / 'backups').resolve() or not source.is_file():
            raise HTTPException(404, detail='Backup not found')
        try:
            await asyncio.to_thread(verify_backup, source)
        except (ValueError, OSError, KeyError):
            raise HTTPException(409, detail='Backup failed integrity verification') from None
        return FileResponse(source, media_type='application/zip',
                            filename=name, headers={'Cache-Control': 'no-store'})

    @app.post('/api/ipas/bulk-delete', dependencies=[Depends(auth)])
    async def bulk_delete_ipas(payload: DeleteIPARequest):
        # The confirmation phrase is an additional explicit destructive-action
        # safeguard, NOT an alternative to bearer authentication.
        phrase = 'DELETE ALL IPAS' if payload.all else 'DELETE SELECTED IPAS'
        if payload.confirm != phrase:
            raise HTTPException(400, detail='Please confirm the destructive action')
        async with manager.lock:
            ids = [r['id'] for r in manager.db.query('SELECT id FROM ipa')] if payload.all else payload.ipa_ids
            # Fail closed: an inconsistent or unreadable backup must never
            # silently permit destructive deletion on any device.
            if ids:
                try:
                    await asyncio.to_thread(create_backup, cfg.root, manager.db, 'before-bulk-delete')
                except PermissionError as exc:
                    raise HTTPException(409, detail=(
                        'Không thể sao lưu IPA trước khi xóa: Windows đang khóa một file '
                        'hoặc từ chối quyền đọc/ghi. Đóng ứng dụng dùng IPA, kiểm tra antivirus '
                        'và thử lại. Chưa xóa dữ liệu nào.'
                    )) from exc
                except (OSError, ValueError) as exc:
                    raise HTTPException(409, detail=(
                        'Không tạo được bản sao lưu an toàn trước khi xóa. Kiểm tra dung lượng '
                        'ổ đĩa, quyền thư mục dữ liệu, file IPA/profile còn tồn tại và thử lại. '
                        'Chưa xóa dữ liệu nào.'
                    )) from exc
            try:
                return manager.delete_ipas(ids, force=payload.force)
            except ValueError as exc:
                raise HTTPException(409, detail=str(exc)) from exc
            except PermissionError as exc:
                raise HTTPException(409, detail=(
                    'Windows đang khóa file IPA hoặc không đủ quyền sửa thư mục. '
                    'Hãy đóng ứng dụng đang sử dụng file rồi thử lại.'
                )) from exc
            except OSError as exc:
                raise HTTPException(500, detail=(
                    'Lỗi hệ thống file trong khi xóa IPA. Kiểm tra quyền thư mục '
                    'và dung lượng ổ đĩa Windows.'
                )) from exc

    @app.delete('/api/ipas/{ipa_id}', dependencies=[Depends(auth)])
    async def delete_library_ipa(ipa_id: str, force: bool = False):
        # Removes local file and metadata, not the installed iPhone application.
        # force=True also deletes renewal tracking; never implicit.
        async with manager.lock:
            try:
                result = manager.delete_ipa(ipa_id, force=force)
            except ValueError as exc:
                raise HTTPException(status_code=409, detail=str(exc)) from exc
            except OSError as exc:
                raise HTTPException(status_code=500, detail='Could not delete IPA file on disk') from exc
        if result is None:
            raise HTTPException(status_code=404, detail='IPA not found')
        return result

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

    @app.get('/api/apple/accounts', dependencies=[Depends(auth), Depends(local_apple_control)])
    async def apple_accounts():
        return await asyncio.to_thread(apple_auth.status)

    @app.post('/api/apple/auth/configure', dependencies=[Depends(auth), Depends(local_apple_control)])
    async def apple_configure(payload: AppleAnisetteChoice):
        try:
            return await asyncio.to_thread(
                apple_auth.configure, payload.mode, payload.server, payload.consent)
        except (ValueError, RuntimeError) as exc:
            raise HTTPException(400, detail=str(exc)) from None

    @app.post('/api/apple/auth/login', dependencies=[Depends(auth), Depends(local_apple_control)])
    async def apple_login(payload: AppleAccountLogin):
        try:
            async with manager.lock:
                return await asyncio.to_thread(apple_auth.begin, payload.email, payload.password)
        except ValueError as exc:
            raise HTTPException(400, detail=str(exc)) from None
        except Exception:
            # Never echo Apple API responses or credential-bearing exceptions.
            raise HTTPException(502, detail='Apple login failed. Check your Apple ID and anisette configuration') from None

    @app.post('/api/apple/auth/verify', dependencies=[Depends(auth), Depends(local_apple_control)])
    async def apple_verify(payload: AppleAccountVerification):
        try:
            async with manager.lock:
                return await asyncio.to_thread(apple_auth.verify, payload.challenge, payload.code)
        except ValueError as exc:
            raise HTTPException(400, detail=str(exc)) from None
        except Exception:
            raise HTTPException(502, detail='Apple verification failed or expired') from None

    @app.post('/api/apple/auth/switch', dependencies=[Depends(auth), Depends(local_apple_control)])
    async def apple_switch(payload: AppleAccountSelection):
        try:
            async with manager.lock:
                return await asyncio.to_thread(apple_auth.switch, payload.email)
        except Exception:
            raise HTTPException(400, detail='Could not select this signed-in Apple ID') from None

    @app.post('/api/apple/auth/logout', dependencies=[Depends(auth), Depends(local_apple_control)])
    async def apple_logout(payload: AppleAccountLogout):
        try:
            async with manager.lock:
                return await asyncio.to_thread(apple_auth.logout, payload.email)
        except Exception:
            raise HTTPException(400, detail='Could not sign out this Apple ID') from None

    @app.post('/api/apple/auth/cancel', dependencies=[Depends(auth), Depends(local_apple_control)])
    async def apple_cancel():
        return await asyncio.to_thread(apple_auth.cancel)

    @app.get('/api/notifications/config', dependencies=[Depends(auth), Depends(local_apple_control)])
    def notifications_config():
        # Includes the ntfy topic secret. NEVER expose this route via remote gateway.
        return manager.notifications.settings()

    @app.post('/api/notifications/config', dependencies=[Depends(auth), Depends(local_apple_control)])
    async def notifications_configure(payload: NotificationChoice):
        try:
            result = await asyncio.to_thread(
                manager.notifications.configure, payload.enabled, payload.consent
            )
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from None
        if payload.enabled:
            await manager.expiry_alert_scan()
        return result

    @app.post('/api/notifications/test', dependencies=[Depends(auth), Depends(local_apple_control)])
    async def notifications_test():
        if not manager.notifications.settings()['enabled']:
            raise HTTPException(409, detail='Bật thông báo và xác nhận đồng ý trước khi thử.')
        sent = await asyncio.to_thread(manager.notifications.publish, 'test')
        if not sent:
            raise HTTPException(502, detail='Chưa gửi được thông báo đến ntfy.sh. Kiểm tra Internet của Windows.')
        return {'sent': True}

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
        ids = manager.db.query("SELECT id FROM installations WHERE signing_mode='apple_personal'")
        return {'queued_job_ids': [manager.submit('renew', {'installation_id': row['id']})
                                   for row in ids]}

    @app.post('/api/jobs/{job_id}/retry', dependencies=[Depends(auth)])
    async def retry_failed_job(job_id: str, payload: RetryJobPayload):
        if payload.confirm != 'RETRY JOB':
            raise HTTPException(400, detail='Explicit retry confirmation required')
        async with manager.lock:
            try:
                new_id = manager.retry_job(job_id)
            except ValueError as exc:
                raise HTTPException(409, detail=str(exc)) from exc
        return {'job_id': new_id}

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
