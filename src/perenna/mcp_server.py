from __future__ import annotations

import logging
from typing import Literal, Self, cast

import anyio
import mcp.types as types
from mcp.server import Server, ServerRequestContext
from mcp.server.stdio import stdio_server
from pydantic import BaseModel, ConfigDict, ValidationError, model_validator

from perenna import __version__
from perenna.core import PerennaCore
from perenna.errors import PerennaError

logger = logging.getLogger(__name__)

MEMORY_TOOL_SCHEMA: dict[str, object] = {
    "type": "object",
    "properties": {
        "action": {"type": "string", "enum": ["query", "write"]},
        "query": {"type": "string"},
        "title": {"type": "string"},
        "body": {"type": "string"},
        "project": {"type": "string"},
    },
    "required": ["action"],
    "additionalProperties": False,
}

MEMORY_TOOL = types.Tool(
    name="memory",
    description=(
        "Read or write shared permanent memory. Query without query text returns a lightweight "
        "index; query with text recalls up to five full memories. Write replaces the complete "
        "body of the same normalized title in the selected scope."
    ),
    input_schema=MEMORY_TOOL_SCHEMA,
)

SERVER_INSTRUCTIONS = (
    "Use memory with action=query and no query once near the start of a new session. Recall only "
    "when past information could affect the current task. Write only durable cross-session facts "
    "or decisions, never credentials, temporary progress, or chat logs. Before updating a topic, "
    "recall it and write back the complete desired body. Current user instructions override memory."
)


class MemoryArguments(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)

    action: Literal["query", "write"]
    query: str | None = None
    title: str | None = None
    body: str | None = None
    project: str | None = None

    @model_validator(mode="after")
    def validate_action_fields(self) -> Self:
        explicitly_null = {
            field for field in self.model_fields_set if getattr(self, field, None) is None
        }
        if explicitly_null:
            raise ValueError("tool fields cannot be null")
        if self.action == "query":
            unsupported = self.model_fields_set - {"action", "query", "project"}
            if unsupported:
                raise ValueError("query received write-only fields")
        else:
            if "title" not in self.model_fields_set or "body" not in self.model_fields_set:
                raise ValueError("write requires title and body")
            if "query" in self.model_fields_set:
                raise ValueError("write received query")
        return self


def create_server(core: PerennaCore) -> Server[object]:
    async def list_tools(
        _context: ServerRequestContext[object],
        _params: types.PaginatedRequestParams | None,
    ) -> types.ListToolsResult:
        return types.ListToolsResult(tools=[MEMORY_TOOL])

    async def call_tool(
        _context: ServerRequestContext[object],
        params: types.CallToolRequestParams,
    ) -> types.CallToolResult:
        if params.name != "memory":
            return _error_result("Unknown tool. Perenna exposes only the memory tool.")
        try:
            arguments = MemoryArguments.model_validate(params.arguments or {})
        except ValidationError:
            return _error_result(
                "Invalid memory arguments. Query accepts action, query, and project. Write "
                "requires action, title, and body and optionally accepts project; it rejects "
                "query and unknown fields."
            )

        try:
            if arguments.action == "query":
                if arguments.query is None:
                    text = await anyio.to_thread.run_sync(
                        lambda: core.list_index(project=arguments.project)
                    )
                else:
                    text = await anyio.to_thread.run_sync(
                        lambda: core.recall(query=arguments.query, project=arguments.project)
                    )
            else:
                title = cast(str, arguments.title)
                body = cast(str, arguments.body)
                text = await anyio.to_thread.run_sync(
                    lambda: core.write(
                        title=title,
                        body=body,
                        project=arguments.project,
                    )
                )
        except PerennaError as exc:
            return _error_result(str(exc))
        except Exception as exc:
            logger.error(
                "mcp_tool=memory status=failed error_type=%s",
                type(exc).__name__,
            )
            return _error_result(
                "Perenna could not complete the memory operation. Check the local stderr log and "
                "retry."
            )
        return types.CallToolResult(content=[types.TextContent(text=text)])

    return Server(
        "Perenna",
        version=__version__,
        description="Local-first permanent memory for AI agents",
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


def _error_result(message: str) -> types.CallToolResult:
    return types.CallToolResult(
        content=[types.TextContent(text=message)],
        is_error=True,
    )
