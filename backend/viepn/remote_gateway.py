"""ViePN remote-control gateway: restricted HTTPS-tailnet API surface.

Run on 127.0.0.1:8766 only; proxy via Tailscale Serve to provide TLS.
Never expose the Apple ID password, 2FA or account-session APIs remotely.
"""
from __future__ import annotations

import hmac
import os
import re
from contextlib import asynccontextmanager

import httpx
from fastapi import FastAPI, Header, HTTPException, Request
from fastapi.responses import JSONResponse, Response, StreamingResponse
from starlette.background import BackgroundTask

from .config import Settings, load_settings

# Full method+path allowlist; deny by default including Apple auth/session paths.
_RULES = (
    ("GET", re.compile(r"^/$")),
    ("GET", re.compile(r"^/api/health$")),
    ("GET", re.compile(r"^/api/overview$")),
    ("GET", re.compile(r"^/api/devices$")),
    ("GET", re.compile(r"^/api/device/[A-Za-z0-9-]{8,128}/apps$")),
    ("GET", re.compile(r"^/api/apple/status$")),
    ("GET", re.compile(r"^/api/ipa/[A-Za-z0-9]{1,64}/download$")),
    ("POST", re.compile(r"^/api/ipas$")),
    ("DELETE", re.compile(r"^/api/ipas/[A-Za-z0-9]{1,64}$")),
    ("POST", re.compile(r"^/api/profiles$")),
    ("POST", re.compile(r"^/api/install$")),
    ("POST", re.compile(r"^/api/sign$")),
    ("POST", re.compile(r"^/api/apple/sign$")),
    ("POST", re.compile(r"^/api/apple/install$")),
    ("POST", re.compile(r"^/api/apple/refresh-all$")),
    ("POST", re.compile(r"^/api/renew$")),
    ("POST", re.compile(r"^/api/renew/check$")),
)

_RESPONSE_HEADERS = ("content-type", "content-disposition", "content-security-policy", "cache-control", "etag")


def allowed(method: str, path: str) -> bool:
    return any(m == method and pattern.fullmatch(path) is not None
               for m, pattern in _RULES)


def create_remote_app(settings: Settings | None = None,
                      transport: httpx.AsyncBaseTransport | None = None) -> FastAPI:
    cfg = settings or load_settings()
    upstream_port = cfg.port
    if upstream_port == int(os.getenv("VIEPN_REMOTE_PORT", "8766")):
        raise ValueError("Remote gateway port must be different from API port")

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        async with httpx.AsyncClient(
            base_url=f"http://127.0.0.1:{upstream_port}",
            trust_env=False, follow_redirects=False,
            timeout=httpx.Timeout(120.0, connect=3.0),
            transport=transport
        ) as http_client:
            app.state.http = http_client
            yield

    app = FastAPI(title="ViePN Private Remote Gateway",
                  docs_url=None, redoc_url=None, openapi_url=None,
                  lifespan=lifespan)

    @app.api_route("/{path:path}",
                   methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS", "HEAD"])
    async def proxy(path: str, request: Request,
                    authorization: str | None = Header(default=None)):
        url_path = "/" + path
        if not allowed(request.method, url_path):
            raise HTTPException(404, detail="Not available in remote-control mode")

        # A public health probe exposes no private data. Other calls require
        # the same secret as the primary dashboard, even within the tailnet.
        if url_path not in ("/", "/api/health"):
            expected = f"Bearer {cfg.token}"
            if not authorization or not hmac.compare_digest(authorization, expected):
                raise HTTPException(401, detail="Authentication required")

        # Do not forward user-supplied Host, Cookie, Forwarded, X-Forwarded-For,
        # or other untrusted headers to the local web server.
        headers = {}
        if authorization:
            headers["Authorization"] = authorization
        content_type = request.headers.get("content-type")
        if content_type:
            headers["Content-Type"] = content_type
        # Never redirect a request to another host with the bearer token.
        suffix = str(request.url.query)
        target = url_path + ("?" + suffix if suffix else "")
        client: httpx.AsyncClient = request.app.state.http
        try:
            upstream_request = client.build_request(
                request.method, target, headers=headers,
                content=request.stream() if request.method in ("POST", "PUT", "PATCH") else None,
            )
            response = await client.send(upstream_request, stream=True)
        except (httpx.ConnectError, httpx.ConnectTimeout, httpx.RemoteProtocolError):
            return JSONResponse(status_code=503,
                                content={"detail": "ViePN Windows backend is offline"})
        except (httpx.TimeoutException, httpx.RequestError):
            return JSONResponse(status_code=504,
                                content={"detail": "ViePN Windows backend did not respond"})

        filtered = {k: v for k, v in response.headers.items()
                    if k.lower() in _RESPONSE_HEADERS}
        filtered["X-Content-Type-Options"] = "nosniff"
        filtered["Cache-Control"] = "no-store"
        filtered["Referrer-Policy"] = "no-referrer"
        filtered["X-Frame-Options"] = "DENY"
        # In-memory transports may return a buffered, already-consumed response.
        # Real network responses remain streamed to avoid buffering large IPAs.
        if response.is_stream_consumed:
            buffered = response.content
            await response.aclose()
            return Response(content=buffered, status_code=response.status_code,
                            headers=filtered)
        return StreamingResponse(
            response.aiter_raw(),
            status_code=response.status_code,
            headers=filtered,
            background=BackgroundTask(response.aclose)
        )

    return app
