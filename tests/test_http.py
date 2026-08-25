from __future__ import annotations

import json
from typing import Any

import httpx2
import pytest
from mcp import Client
from mcp.client.streamable_http import streamable_http_client
from mcp.server.auth.provider import AccessToken

from perenna.config import REMOTE_SCOPES, RemoteSettings
from perenna.http_server import create_http_app, create_local_http_app
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
    protocol_requests: list[httpx2.Request] = []
    protocol_responses: list[httpx2.Response] = []

    async def capture_request(request: httpx2.Request) -> None:
        protocol_requests.append(request)

    async def capture_response(response: httpx2.Response) -> None:
        protocol_responses.append(response)

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
            event_hooks={
                "request": [capture_request],
                "response": [capture_response],
            },
        ) as authenticated:
            client_transport = streamable_http_client(
                "https://memory.example.com/mcp",
                http_client=authenticated,
            )
            async with Client(client_transport) as client:
                assert client.protocol_version == "2026-07-28"
                tools = await client.list_tools()
                listed = await client.call_tool("memory_read", {"action": "list"})
                rejected = await client.call_tool(
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
    assert tools.ttl_ms == 0
    assert tools.cache_scope == "private"
    assert not listed.is_error
    assert listed.structured_content["action"] == "list"
    assert rejected.is_error
    assert "memory:write" in result_text(rejected)
    assert rejected.meta is not None
    assert "mcp/www_authenticate" in rejected.meta
    protocol_posts = [
        request
        for request in protocol_requests
        if request.method == "POST" and request.url.path == "/mcp"
    ]
    assert protocol_posts
    for request in protocol_posts:
        payload = json.loads(request.content)
        method = payload["method"]
        assert request.headers.get("mcp-protocol-version") == "2026-07-28"
        assert request.headers.get("mcp-method") == method
        expected_name = payload.get("params", {}).get("name") if method == "tools/call" else None
        assert request.headers.get("mcp-name") == expected_name
    routed_requests = [
        (
            request.headers.get("mcp-method"),
            request.headers.get("mcp-name"),
            request.headers.get("mcp-protocol-version"),
        )
        for request in protocol_posts
    ]
    assert ("tools/list", None, "2026-07-28") in routed_requests
    assert ("tools/call", "memory_read", "2026-07-28") in routed_requests
    assert ("tools/call", "memory_write", "2026-07-28") in routed_requests
    assert all("mcp-session-id" not in request.headers for request in protocol_requests)
    assert all("mcp-session-id" not in response.headers for response in protocol_responses)


@pytest.mark.asyncio
async def test_http_server_keeps_legacy_protocol_compatibility() -> None:
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
            headers={"authorization": "Bearer read-token"},
        ) as authenticated:
            client_transport = streamable_http_client(
                "https://memory.example.com/mcp",
                http_client=authenticated,
            )
            async with Client(client_transport, mode="legacy") as client:
                assert client.protocol_version == "2025-11-25"
                listed = await client.call_tool("memory_read", {"action": "list"})
                rejected = await client.call_tool(
                    "memory_write",
                    {
                        "action": "create",
                        "title": "Title",
                        "summary": "Summary.",
                        "body": "Body",
                    },
                )

    assert not listed.is_error
    assert listed.structured_content["action"] == "list"
    assert rejected.is_error
    assert "memory:write" in result_text(rejected)


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


@pytest.mark.asyncio
async def test_local_http_server_uses_streamable_http_without_oauth() -> None:
    app = create_local_http_app(
        _Core(),  # type: ignore[arg-type]
        host="127.0.0.1",
        port=8000,
    )
    transport = httpx2.ASGITransport(app=app)

    async with app.router.lifespan_context(app):
        async with httpx2.AsyncClient(
            transport=transport,
            base_url="http://127.0.0.1:8000",
        ) as client:
            health = await client.get("/healthz")
            metadata = await client.get("/.well-known/oauth-protected-resource/mcp")
            wrong_origin = await client.post(
                "/mcp",
                json={"jsonrpc": "2.0", "id": 1, "method": "ping"},
                headers={
                    "accept": "application/json, text/event-stream",
                    "origin": "http://127.0.0.2:8000",
                },
            )
            client_transport = streamable_http_client(
                "http://127.0.0.1:8000/mcp",
                http_client=client,
            )
            async with Client(client_transport) as mcp_client:
                tools = await mcp_client.list_tools()
                listed = await mcp_client.call_tool("memory_read", {"action": "list"})

        async with httpx2.AsyncClient(
            transport=transport,
            base_url="http://127.0.0.2:8000",
        ) as wrong_host_client:
            wrong_host = await wrong_host_client.post(
                "/mcp",
                json={"jsonrpc": "2.0", "id": 1, "method": "ping"},
                headers={"accept": "application/json, text/event-stream"},
            )

    assert health.status_code == 200
    assert metadata.status_code == 404
    assert wrong_origin.status_code == 403
    assert [tool.name for tool in tools.tools] == [
        "memory_read",
        "memory_write",
        "memory_delete",
    ]
    assert [tool.meta for tool in tools.tools] == [None, None, None]
    assert tools.tools[0].annotations.read_only_hint
    assert tools.tools[1].annotations.destructive_hint
    assert tools.tools[2].annotations.destructive_hint
    assert not listed.is_error
    assert listed.structured_content["action"] == "list"
    assert wrong_host.status_code == 421


@pytest.mark.asyncio
async def test_local_http_server_accepts_handshake_streamable_http_clients() -> None:
    app = create_local_http_app(
        _Core(),  # type: ignore[arg-type]
        host="127.0.0.1",
        port=8000,
    )
    transport = httpx2.ASGITransport(app=app)
    base_headers = {"accept": "application/json, text/event-stream"}

    async with app.router.lifespan_context(app):
        async with httpx2.AsyncClient(
            transport=transport,
            base_url="http://127.0.0.1:8000",
        ) as client:
            initialized = await client.post(
                "/mcp",
                headers=base_headers,
                json={
                    "jsonrpc": "2.0",
                    "id": 1,
                    "method": "initialize",
                    "params": {
                        "protocolVersion": "2025-06-18",
                        "capabilities": {},
                        "clientInfo": {"name": "tunnel-client", "version": "test"},
                    },
                },
            )
            session_id = initialized.headers["mcp-session-id"]
            session_headers = {
                **base_headers,
                "mcp-protocol-version": "2025-06-18",
                "mcp-session-id": session_id,
            }
            acknowledged = await client.post(
                "/mcp",
                headers=session_headers,
                json={
                    "jsonrpc": "2.0",
                    "method": "notifications/initialized",
                },
            )
            tools = await client.post(
                "/mcp",
                headers=session_headers,
                json={"jsonrpc": "2.0", "id": 2, "method": "tools/list"},
            )

    assert initialized.status_code == 200
    assert initialized.headers["content-type"].startswith("text/event-stream")
    assert "2025-06-18" in initialized.text
    assert acknowledged.status_code == 202
    assert tools.status_code == 200
    assert '"name":"memory_read"' in tools.text
    assert '"name":"memory_write"' in tools.text
    assert '"name":"memory_delete"' in tools.text
