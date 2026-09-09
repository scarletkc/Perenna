from __future__ import annotations

import logging
from typing import Any

import anyio
import mcp.types as types
from mcp.server import Server, ServerRequestContext
from mcp.server.auth.middleware.auth_context import get_access_token
from mcp.server.stdio import stdio_server

from perenna import DESCRIPTION, __version__
from perenna.core import PerennaCore
from perenna.errors import PerennaError
from perenna.mcp_schemas import (
    MEMORY_DELETE_TOOL,
    MEMORY_READ_TOOL,
    MEMORY_WRITE_TOOL,
    SERVER_INSTRUCTIONS,
    TOOL_SCOPES,
)
from perenna.memory_commands import execute_memory_command

logger = logging.getLogger(__name__)


def create_server(
    core: PerennaCore,
    *,
    oauth_metadata_url: str | None = None,
) -> Server[object]:
    async def list_tools(
        _context: ServerRequestContext[object],
        _params: types.PaginatedRequestParams | None,
    ) -> types.ListToolsResult:
        tools = [MEMORY_READ_TOOL, MEMORY_WRITE_TOOL, MEMORY_DELETE_TOOL]
        if oauth_metadata_url is not None:
            tools = [_with_oauth(tool) for tool in tools]
        return types.ListToolsResult(
            tools=tools,
            ttlMs=0,
            cacheScope="private",
        )

    async def call_tool(
        _context: ServerRequestContext[object],
        params: types.CallToolRequestParams,
    ) -> types.CallToolResult:
        if oauth_metadata_url is not None and params.name in TOOL_SCOPES:
            auth_error = _authorize_tool(params.name, oauth_metadata_url)
            if auth_error is not None:
                return auth_error
        try:
            payload = await anyio.to_thread.run_sync(
                lambda: execute_memory_command(core, params.name, params.arguments or {})
            )
        except PerennaError as exc:
            return _error_result(str(exc))
        except Exception as exc:
            logger.error(
                "mcp_tool=%s status=failed error_type=%s",
                params.name,
                type(exc).__name__,
            )
            return _error_result(
                "Perenna could not complete the memory operation. Check the local stderr log and "
                "retry."
            )
        return _success_result(payload)

    return Server(
        "Perenna",
        version=__version__,
        description=DESCRIPTION,
        instructions=SERVER_INSTRUCTIONS,
        on_list_tools=list_tools,
        on_call_tool=call_tool,
    )


async def run_stdio(core: PerennaCore) -> None:
    server = create_server(core)
    async with stdio_server() as (read_stream, write_stream):
        await server.run(
            read_stream,
            write_stream,
            server.create_initialization_options(),
        )


def _success_result(payload: dict[str, Any]) -> types.CallToolResult:
    return types.CallToolResult(
        content=[types.TextContent(text=_summary(payload))],
        structured_content=payload,
    )


def _summary(payload: dict[str, Any]) -> str:
    action = payload["action"]
    if action == "list":
        return (
            f"Listed {len(payload['memories'])} memories and "
            f"{len(payload['projects'])} project scopes."
        )
    if action == "search":
        suffix = " Additional results were omitted." if payload["truncated"] else ""
        return f"Returned {len(payload['matches'])} ranked memory candidates.{suffix}"
    if action == "get":
        memory = payload["memory"]
        return f"Retrieved memory {memory['title']!r} from {memory['scope']}."
    memory = payload["memory"]
    changed = "committed" if payload["changed"] else "already current"
    notices = []
    if payload["index_status"] == "pending":
        notices.append(
            "Retrieval indexing failed after the Git commit; the next non-empty search will retry."
        )
    if payload["sync_status"] == "pending":
        notices.append("Remote synchronization is pending; the local commit remains complete.")
    elif payload["sync_status"] == "conflict":
        notices.append(
            "Remote history conflicts with the local commit; later writes are blocked until "
            "reconciliation."
        )
    suffix = "" if not notices else f" {' '.join(notices)}"
    if action == "delete":
        return f"Deleted memory {memory['title']!r}; the change was committed to Git.{suffix}"
    return f"Memory {action} for {memory['title']!r} is {changed}.{suffix}"


def _error_result(message: str) -> types.CallToolResult:
    return types.CallToolResult(
        content=[types.TextContent(text=message)],
        is_error=True,
    )


def _with_oauth(tool: types.Tool) -> types.Tool:
    return tool.model_copy(
        update={
            "meta": {
                "securitySchemes": [{"type": "oauth2", "scopes": list(TOOL_SCOPES[tool.name])}]
            }
        }
    )


def _authorize_tool(tool_name: str, metadata_url: str) -> types.CallToolResult | None:
    access_token = get_access_token()
    required_scopes = TOOL_SCOPES[tool_name]
    if access_token is None:
        return _oauth_error_result(
            metadata_url,
            required_scopes,
            error="invalid_token",
            description="Authentication is required to use Perenna.",
        )
    missing = [scope for scope in required_scopes if scope not in access_token.scopes]
    if missing:
        return _oauth_error_result(
            metadata_url,
            required_scopes,
            error="insufficient_scope",
            description=f"The {tool_name} tool requires the {missing[0]} scope.",
        )
    return None


def _oauth_error_result(
    metadata_url: str,
    scopes: tuple[str, ...],
    *,
    error: str,
    description: str,
) -> types.CallToolResult:
    scope = " ".join(scopes)
    challenge = (
        f'Bearer resource_metadata="{metadata_url}", scope="{scope}", '
        f'error="{error}", error_description="{description}"'
    )
    return types.CallToolResult(
        content=[types.TextContent(text=description)],
        meta={"mcp/www_authenticate": [challenge]},
        is_error=True,
    )
