from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from urllib.parse import urlsplit

import uvicorn
from mcp.server.auth.middleware.auth_context import AuthContextMiddleware
from mcp.server.auth.middleware.bearer_auth import BearerAuthBackend, RequireAuthMiddleware
from mcp.server.auth.provider import TokenVerifier
from mcp.server.auth.routes import build_resource_metadata_url, create_protected_resource_routes
from mcp.server.auth.settings import AuthSettings
from mcp.server.streamable_http_manager import (
    StreamableHTTPASGIApp,
    StreamableHTTPSessionManager,
)
from mcp.server.transport_security import TransportSecuritySettings
from starlette.applications import Starlette
from starlette.middleware import Middleware
from starlette.middleware.authentication import AuthenticationMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse
from starlette.routing import Route

from perenna.config import REMOTE_SCOPES, RemoteSettings
from perenna.core import PerennaCore
from perenna.mcp_server import create_server
from perenna.oauth import JWTTokenVerifier


def create_http_app(
    core: PerennaCore,
    settings: RemoteSettings,
    *,
    token_verifier: TokenVerifier | None = None,
) -> Starlette:
    auth_urls = AuthSettings(
        issuer_url=settings.issuer,
        resource_server_url=settings.public_url,
    )
    resource_url = auth_urls.resource_server_url
    if resource_url is None:  # pragma: no cover - required by RemoteSettings
        raise RuntimeError("Remote MCP resource URL is missing.")
    issuer_url = auth_urls.issuer_url
    metadata_url = build_resource_metadata_url(resource_url)
    server = create_server(core, oauth_metadata_url=str(metadata_url))
    verifier = token_verifier or JWTTokenVerifier(
        issuer=settings.issuer,
        audience=settings.public_url,
        jwks_url=settings.jwks_url,
        allowed_subject=settings.allowed_subject,
    )

    public = urlsplit(settings.public_url)
    origin = f"{public.scheme}://{public.netloc}"
    transport_security = TransportSecuritySettings(
        enable_dns_rebinding_protection=True,
        allowed_hosts=[public.netloc],
        allowed_origins=[origin],
    )
    session_manager = StreamableHTTPSessionManager(
        app=server,
        json_response=False,
        stateless=False,
        security_settings=transport_security,
        session_idle_timeout=1800,
    )
    mcp_app = StreamableHTTPASGIApp(session_manager)
    protected_mcp = RequireAuthMiddleware(
        mcp_app,
        required_scopes=[],
        resource_metadata_url=metadata_url,
    )

    routes = [
        Route("/mcp", endpoint=protected_mcp),
        *create_protected_resource_routes(
            resource_url=resource_url,
            authorization_servers=[issuer_url],
            scopes_supported=list(REMOTE_SCOPES),
            resource_name="Perenna",
        ),
        Route("/healthz", endpoint=_health, methods=["GET"]),
    ]
    middleware = [
        Middleware(AuthenticationMiddleware, backend=BearerAuthBackend(verifier)),
        Middleware(AuthContextMiddleware),
    ]

    @asynccontextmanager
    async def lifespan(_: Starlette) -> AsyncIterator[None]:
        async with session_manager.run():
            yield

    return Starlette(routes=routes, middleware=middleware, lifespan=lifespan)


def run_http(
    core: PerennaCore,
    settings: RemoteSettings,
    *,
    host: str,
    port: int,
) -> None:
    app = create_http_app(core, settings)
    uvicorn.run(
        app,
        host=host,
        port=port,
        access_log=False,
        proxy_headers=False,
        server_header=False,
    )


async def _health(_: Request) -> JSONResponse:
    return JSONResponse({"status": "ok"})
