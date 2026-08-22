from __future__ import annotations

from typing import Any

import httpx2
import pytest
from mcp import ClientSession
from mcp.client.streamable_http import streamable_http_client
from mcp.server.auth.provider import AccessToken

from perenna.config import REMOTE_SCOPES, RemoteSettings
from perenna.http_server import create_http_app
from tests.helpers import result_text


class _Core:
    def list_memories(self, *, project: str | None) -> dict[str, Any]:
        return {"action": "list", "project": project, "memories": [], "projects": []}


class _TokenVerifier:
    async def verify_token(self, token: str) -> AccessToken | None:
        if token == "read-token":
            return AccessToken(
                token=token,
                client_id="chatgpt-client",
                scopes=["memory:read"],
                subject="auth0|owner",
                claims={"iss": "https://tenant.example.com"},
            )
        return None


def _settings() -> RemoteSettings:
    return RemoteSettings(
        public_url="https://memory.example.com/mcp",
        issuer="https://tenant.example.com",
        jwks_url="https://tenant.example.com/.well-known/jwks.json",
        allowed_subject="auth0|owner",
    )


@pytest.mark.asyncio
async def test_http_server_exposes_metadata_requires_oauth_and_enforces_tool_scopes() -> None:
    app = create_http_app(
        _Core(),  # type: ignore[arg-type]
        _settings(),
        token_verifier=_TokenVerifier(),
    )
    transport = httpx2.ASGITransport(app=app)

    async with app.router.lifespan_context(app):
        async with httpx2.AsyncClient(
            transport=transport,
            base_url="https://memory.example.com",
        ) as anonymous:
            health = await anonymous.get("/healthz")
            metadata = await anonymous.get("/.well-known/oauth-protected-resource/mcp")
            denied = await anonymous.post(
                "/mcp",
                json={"jsonrpc": "2.0", "id": 1, "method": "ping"},
                headers={"accept": "application/json, text/event-stream"},
            )

        assert health.status_code == 200
        assert health.json() == {"status": "ok"}
        assert metadata.status_code == 200
        assert metadata.json() == {
            "resource": "https://memory.example.com/mcp",
            "authorization_servers": ["https://tenant.example.com"],
            "scopes_supported": list(REMOTE_SCOPES),
            "bearer_methods_supported": ["header"],
            "resource_name": "Perenna",
        }
        assert denied.status_code == 401
        assert (
            'resource_metadata="https://memory.example.com/'
            '.well-known/oauth-protected-resource/mcp"' in denied.headers["www-authenticate"]
        )

        async with httpx2.AsyncClient(
            transport=transport,
            base_url="https://memory.example.com",
            headers={"authorization": "Bearer read-token"},
        ) as authenticated:
            async with streamable_http_client(
                "https://memory.example.com/mcp",
                http_client=authenticated,
            ) as (read_stream, write_stream):
                async with ClientSession(read_stream, write_stream) as session:
                    await session.initialize()
                    tools = await session.list_tools()
                    listed = await session.call_tool("memory_read", {"action": "list"})
                    rejected = await session.call_tool(
                        "memory_write",
                        {
                            "action": "create",
                            "title": "Title",
                            "summary": "Summary.",
                            "body": "Body",
                        },
                    )

    assert [tool.meta for tool in tools.tools] == [
        {"securitySchemes": [{"type": "oauth2", "scopes": ["memory:read"]}]},
        {"securitySchemes": [{"type": "oauth2", "scopes": ["memory:write"]}]},
        {"securitySchemes": [{"type": "oauth2", "scopes": ["memory:delete"]}]},
    ]
    assert not listed.is_error
    assert listed.structured_content["action"] == "list"
    assert rejected.is_error
    assert "memory:write" in result_text(rejected)
    assert rejected.meta is not None
    assert "mcp/www_authenticate" in rejected.meta


@pytest.mark.asyncio
async def test_http_server_rejects_invalid_token_and_host() -> None:
    app = create_http_app(
        _Core(),  # type: ignore[arg-type]
        _settings(),
        token_verifier=_TokenVerifier(),
    )
    transport = httpx2.ASGITransport(app=app)

    async with app.router.lifespan_context(app):
        async with httpx2.AsyncClient(
            transport=transport,
            base_url="https://memory.example.com",
            headers={"authorization": "Bearer invalid-token"},
        ) as client:
            invalid = await client.post(
                "/mcp",
                json={"jsonrpc": "2.0", "id": 1, "method": "ping"},
                headers={"accept": "application/json, text/event-stream"},
            )

        async with httpx2.AsyncClient(
            transport=transport,
            base_url="https://wrong.example.com",
            headers={"authorization": "Bearer read-token"},
        ) as client:
            wrong_host = await client.post(
                "/mcp",
                json={"jsonrpc": "2.0", "id": 1, "method": "ping"},
                headers={"accept": "application/json, text/event-stream"},
            )

    assert invalid.status_code == 401
    assert wrong_host.status_code == 421
