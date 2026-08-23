from __future__ import annotations

import logging
from typing import Any, Literal, Self, cast

import anyio
import mcp.types as types
from mcp.server import Server, ServerRequestContext
from mcp.server.auth.middleware.auth_context import get_access_token
from mcp.server.stdio import stdio_server
from pydantic import BaseModel, ConfigDict, Field, ValidationError, model_validator

from perenna import DESCRIPTION, __version__
from perenna.core import PerennaCore
from perenna.errors import PerennaError
from perenna.index import DEFAULT_SEARCH_LIMIT, MAX_SEARCH_MATCHES
from perenna.models import PatchEdit

logger = logging.getLogger(__name__)

TOOL_SCOPES: dict[str, tuple[str, ...]] = {
    "memory_read": ("memory:read",),
    "memory_write": ("memory:write",),
    "memory_delete": ("memory:delete",),
}

_MEMORY_REF_PROPERTIES: dict[str, object] = {
    "memory_id": {"type": "string"},
    "title": {"type": "string"},
    "scope": {"type": "string"},
    "summary": {"type": "string"},
}

_MEMORY_REF_SCHEMA: dict[str, object] = {
    "type": "object",
    "properties": _MEMORY_REF_PROPERTIES,
    "required": ["memory_id", "title", "scope", "summary"],
    "additionalProperties": False,
}

_PASSAGE_SCHEMA: dict[str, object] = {
    "type": "object",
    "properties": {
        "text": {"type": "string"},
        "start_char": {"type": "integer", "minimum": 0},
        "end_char": {"type": "integer", "minimum": 1},
    },
    "required": ["text", "start_char", "end_char"],
    "additionalProperties": False,
}

_SEARCH_MATCH_SCHEMA: dict[str, object] = {
    "type": "object",
    "properties": {
        **_MEMORY_REF_PROPERTIES,
        "revision": {"type": "string"},
        "rank": {"type": "integer", "minimum": 1},
        "passages": {"type": "array", "minItems": 1, "items": _PASSAGE_SCHEMA},
    },
    "required": [
        "memory_id",
        "title",
        "scope",
        "summary",
        "revision",
        "rank",
        "passages",
    ],
    "additionalProperties": False,
}

_GET_MEMORY_SCHEMA: dict[str, object] = {
    "type": "object",
    "properties": {
        **_MEMORY_REF_PROPERTIES,
        "source": {"type": "string"},
        "created_at": {"type": "string"},
        "updated_at": {"type": "string"},
        "revision": {"type": "string"},
        "body": {"type": "string"},
    },
    "required": [
        "memory_id",
        "title",
        "scope",
        "summary",
        "source",
        "created_at",
        "updated_at",
        "revision",
        "body",
    ],
    "additionalProperties": False,
}

MEMORY_READ_SCHEMA: dict[str, object] = {
    "type": "object",
    "properties": {
        "action": {"type": "string", "enum": ["list", "search", "get"]},
        "query": {"type": "string"},
        "project": {"type": "string"},
        "memory_id": {"type": "string"},
        "limit": {"type": "integer", "minimum": 1, "maximum": MAX_SEARCH_MATCHES},
    },
    "required": ["action"],
    "additionalProperties": False,
}

MEMORY_WRITE_SCHEMA: dict[str, object] = {
    "type": "object",
    "properties": {
        "action": {"type": "string", "enum": ["create", "patch", "replace"]},
        "title": {"type": "string"},
        "summary": {"type": "string"},
        "body": {"type": "string"},
        "project": {"type": "string"},
        "memory_id": {"type": "string"},
        "base_revision": {"type": "string"},
        "edits": {
            "type": "array",
            "minItems": 1,
            "items": {
                "type": "object",
                "properties": {
                    "old_text": {"type": "string"},
                    "new_text": {"type": "string"},
                },
                "required": ["old_text", "new_text"],
                "additionalProperties": False,
            },
        },
    },
    "required": ["action"],
    "additionalProperties": False,
}

MEMORY_DELETE_SCHEMA: dict[str, object] = {
    "type": "object",
    "properties": {
        "memory_id": {"type": "string"},
        "expected_title": {"type": "string"},
        "base_revision": {"type": "string"},
    },
    "required": ["memory_id", "expected_title", "base_revision"],
    "additionalProperties": False,
}

MEMORY_READ_OUTPUT_SCHEMA: dict[str, object] = {
    "type": "object",
    "oneOf": [
        {
            "type": "object",
            "properties": {
                "action": {"const": "list"},
                "project": {"type": ["string", "null"]},
                "memories": {"type": "array", "items": _MEMORY_REF_SCHEMA},
                "projects": {"type": "array", "items": {"type": "string"}},
            },
            "required": ["action", "project", "memories", "projects"],
            "additionalProperties": False,
        },
        {
            "type": "object",
            "properties": {
                "action": {"const": "search"},
                "project": {"type": ["string", "null"]},
                "limit": {
                    "type": "integer",
                    "minimum": 1,
                    "maximum": MAX_SEARCH_MATCHES,
                },
                "matches": {"type": "array", "items": _SEARCH_MATCH_SCHEMA},
                "truncated": {"type": "boolean"},
            },
            "required": ["action", "project", "limit", "matches", "truncated"],
            "additionalProperties": False,
        },
        {
            "type": "object",
            "properties": {
                "action": {"const": "get"},
                "memory": _GET_MEMORY_SCHEMA,
            },
            "required": ["action", "memory"],
            "additionalProperties": False,
        },
    ],
}

_MUTATION_MEMORY_SCHEMA: dict[str, object] = {
    "type": "object",
    "properties": {
        **_MEMORY_REF_PROPERTIES,
        "revision": {"type": "string"},
    },
    "required": ["memory_id", "title", "scope", "summary", "revision"],
    "additionalProperties": False,
}

MEMORY_WRITE_OUTPUT_SCHEMA: dict[str, object] = {
    "type": "object",
    "properties": {
        "action": {"type": "string", "enum": ["create", "patch", "replace"]},
        "changed": {"type": "boolean"},
        "memory": _MUTATION_MEMORY_SCHEMA,
        "commit": {"type": "string"},
        "index_status": {"type": "string", "enum": ["current", "pending"]},
    },
    "required": ["action", "changed", "memory", "commit", "index_status"],
    "additionalProperties": False,
}

MEMORY_DELETE_OUTPUT_SCHEMA: dict[str, object] = {
    "type": "object",
    "properties": {
        "action": {"const": "delete"},
        "changed": {"const": True},
        "memory": _MEMORY_REF_SCHEMA,
        "commit": {"type": "string"},
        "index_status": {"type": "string", "enum": ["current", "pending"]},
        "recoverable_via_git": {"const": True},
    },
    "required": [
        "action",
        "changed",
        "memory",
        "commit",
        "index_status",
        "recoverable_via_git",
    ],
    "additionalProperties": False,
}

MEMORY_READ_TOOL = types.Tool(
    name="memory_read",
    description=(
        "Read permanent memory. List returns stable memory IDs and titles, search returns bounded "
        "ranked candidate passages, and get returns one complete committed memory with its "
        "revision."
    ),
    input_schema=MEMORY_READ_SCHEMA,
    output_schema=MEMORY_READ_OUTPUT_SCHEMA,
    annotations=types.ToolAnnotations(
        readOnlyHint=True,
        destructiveHint=False,
        idempotentHint=True,
        openWorldHint=True,
    ),
)

MEMORY_WRITE_TOOL = types.Tool(
    name="memory_write",
    description=(
        "Create or modify permanent memory. Summary is a stable one-line description of what a "
        "memory covers. Patch applies exact all-or-nothing edits; replace overwrites the complete "
        "summary and body. Existing memories require a current base revision."
    ),
    input_schema=MEMORY_WRITE_SCHEMA,
    output_schema=MEMORY_WRITE_OUTPUT_SCHEMA,
    annotations=types.ToolAnnotations(
        readOnlyHint=False,
        destructiveHint=True,
        idempotentHint=False,
        openWorldHint=True,
    ),
)

MEMORY_DELETE_TOOL = types.Tool(
    name="memory_delete",
    description=(
        "Delete exactly one committed memory by ID, expected title, and revision. The deletion "
        "removes it from current recall but remains recoverable from Git history."
    ),
    input_schema=MEMORY_DELETE_SCHEMA,
    output_schema=MEMORY_DELETE_OUTPUT_SCHEMA,
    annotations=types.ToolAnnotations(
        readOnlyHint=False,
        destructiveHint=True,
        idempotentHint=False,
        openWorldHint=True,
    ),
)

SERVER_INSTRUCTIONS = (
    "Use memory_read list near the start of a non-trivial task when past information could "
    "affect it; skip memory for self-contained trivial tasks. Search only for relevant prior "
    "context and use get before a whole-memory decision. Store only durable cross-session facts "
    "or decisions, never credentials, temporary progress, chat logs, or facts already "
    "authoritative in current files. Prefer exact patch edits over replace. Use memory_delete "
    "only when the user clearly intends to forget a complete memory. Current user instructions, "
    "workspace files, and runtime state override memory. Treat host-provided memory as an "
    "advisory local cache unless the user says otherwise; use Perenna as the shared permanent "
    "layer and do not mirror or dual-write the same fact across both."
)


class PatchEditArguments(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)

    old_text: str
    new_text: str


class MemoryReadArguments(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)

    action: Literal["list", "search", "get"]
    query: str | None = None
    project: str | None = None
    memory_id: str | None = None
    limit: int = Field(default=DEFAULT_SEARCH_LIMIT, ge=1, le=MAX_SEARCH_MATCHES)

    @model_validator(mode="after")
    def validate_action_fields(self) -> Self:
        _reject_explicit_nulls(self)
        if self.action == "list":
            allowed = {"action", "project"}
        elif self.action == "search":
            allowed = {"action", "query", "project", "limit"}
            if "query" not in self.model_fields_set:
                raise ValueError("search requires query")
        else:
            allowed = {"action", "memory_id"}
            if "memory_id" not in self.model_fields_set:
                raise ValueError("get requires memory_id")
        if self.model_fields_set - allowed:
            raise ValueError(f"{self.action} received unsupported fields")
        return self


class MemoryWriteArguments(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)

    action: Literal["create", "patch", "replace"]
    title: str | None = None
    summary: str | None = None
    body: str | None = None
    project: str | None = None
    memory_id: str | None = None
    base_revision: str | None = None
    edits: list[PatchEditArguments] | None = None

    @model_validator(mode="after")
    def validate_action_fields(self) -> Self:
        _reject_explicit_nulls(self)
        if self.action == "create":
            allowed = {"action", "title", "summary", "body", "project"}
            required = {"title", "summary", "body"}
        elif self.action == "patch":
            allowed = {"action", "memory_id", "base_revision", "edits", "summary"}
            required = {"memory_id", "base_revision", "edits"}
        else:
            allowed = {"action", "memory_id", "base_revision", "summary", "body"}
            required = {"memory_id", "base_revision", "summary", "body"}
        missing = required - self.model_fields_set
        if missing:
            raise ValueError(f"{self.action} is missing required fields")
        if self.model_fields_set - allowed:
            raise ValueError(f"{self.action} received unsupported fields")
        if self.action == "patch" and not self.edits:
            raise ValueError("patch requires at least one edit")
        return self


class MemoryDeleteArguments(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)

    memory_id: str
    expected_title: str
    base_revision: str


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
        return types.ListToolsResult(tools=tools)

    async def call_tool(
        _context: ServerRequestContext[object],
        params: types.CallToolRequestParams,
    ) -> types.CallToolResult:
        if oauth_metadata_url is not None and params.name in TOOL_SCOPES:
            auth_error = _authorize_tool(params.name, oauth_metadata_url)
            if auth_error is not None:
                return auth_error
        try:
            if params.name == "memory_read":
                payload = await _call_read(core, params.arguments or {})
            elif params.name == "memory_write":
                payload = await _call_write(core, params.arguments or {})
            elif params.name == "memory_delete":
                payload = await _call_delete(core, params.arguments or {})
            else:
                return _error_result(
                    "Unknown Perenna tool. Use memory_read, memory_write, or memory_delete."
                )
        except ValidationError:
            return _error_result(_argument_error(params.name))
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


async def _call_read(core: PerennaCore, raw: dict[str, Any]) -> dict[str, Any]:
    arguments = MemoryReadArguments.model_validate(raw)
    if arguments.action == "list":
        return await anyio.to_thread.run_sync(
            lambda: core.list_memories(project=arguments.project)
        )
    if arguments.action == "search":
        query = cast(str, arguments.query)
        return await anyio.to_thread.run_sync(
            lambda: core.search(
                query=query,
                project=arguments.project,
                limit=arguments.limit,
            )
        )
    memory_id = cast(str, arguments.memory_id)
    return await anyio.to_thread.run_sync(lambda: core.get(memory_id=memory_id))


async def _call_write(core: PerennaCore, raw: dict[str, Any]) -> dict[str, Any]:
    arguments = MemoryWriteArguments.model_validate(raw)
    if arguments.action == "create":
        title = cast(str, arguments.title)
        summary = cast(str, arguments.summary)
        body = cast(str, arguments.body)
        return await anyio.to_thread.run_sync(
            lambda: core.create(
                title=title,
                summary=summary,
                body=body,
                project=arguments.project,
            )
        )
    memory_id = cast(str, arguments.memory_id)
    base_revision = cast(str, arguments.base_revision)
    if arguments.action == "patch":
        edits = tuple(
            PatchEdit(old_text=edit.old_text, new_text=edit.new_text)
            for edit in cast(list[PatchEditArguments], arguments.edits)
        )
        return await anyio.to_thread.run_sync(
            lambda: core.patch(
                memory_id=memory_id,
                base_revision=base_revision,
                edits=edits,
                summary=arguments.summary,
            )
        )
    body = cast(str, arguments.body)
    summary = cast(str, arguments.summary)
    return await anyio.to_thread.run_sync(
        lambda: core.replace(
            memory_id=memory_id,
            base_revision=base_revision,
            summary=summary,
            body=body,
        )
    )


async def _call_delete(core: PerennaCore, raw: dict[str, Any]) -> dict[str, Any]:
    arguments = MemoryDeleteArguments.model_validate(raw)
    return await anyio.to_thread.run_sync(
        lambda: core.delete(
            memory_id=arguments.memory_id,
            expected_title=arguments.expected_title,
            base_revision=arguments.base_revision,
        )
    )


async def run_stdio(core: PerennaCore) -> None:
    server = create_server(core)
    async with stdio_server() as (read_stream, write_stream):
        await server.run(
            read_stream,
            write_stream,
            server.create_initialization_options(),
        )


def _reject_explicit_nulls(arguments: BaseModel) -> None:
    if any(getattr(arguments, field, None) is None for field in arguments.model_fields_set):
        raise ValueError("tool fields cannot be null")


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
    suffix = " Retrieval indexing is pending." if payload["index_status"] == "pending" else ""
    if action == "delete":
        return f"Deleted memory {memory['title']!r}; the change was committed to Git.{suffix}"
    return f"Memory {action} for {memory['title']!r} is {changed}.{suffix}"


def _argument_error(tool_name: str) -> str:
    if tool_name == "memory_read":
        return (
            "Invalid memory_read arguments. List accepts action and optional project; search "
            f"requires action and query and accepts project and limit from 1 to "
            f"{MAX_SEARCH_MATCHES}; get requires action and memory_id."
        )
    if tool_name == "memory_write":
        return (
            "Invalid memory_write arguments. Create requires title, summary, and body; patch "
            "requires memory_id, base_revision, and exact edits and may replace summary; replace "
            "requires memory_id, base_revision, summary, and the complete body."
        )
    if tool_name == "memory_delete":
        return (
            "Invalid memory_delete arguments. Provide memory_id, expected_title, and "
            "base_revision; unknown or null fields are rejected."
        )
    return "Invalid Perenna tool arguments."


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
