from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

import mcp.types as types
import pytest
from pydantic import ValidationError

from perenna.errors import MemoryValidationError
from perenna.mcp_server import (
    MEMORY_TOOL_SCHEMA,
    MemoryArguments,
    create_server,
    run_stdio,
)
from tests.helpers import perenna_session, result_text


def test_memory_schema_is_exact_and_source_is_not_agent_controlled() -> None:
    assert MEMORY_TOOL_SCHEMA == {
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
    assert "source" not in MEMORY_TOOL_SCHEMA["properties"]


@pytest.mark.parametrize(
    "arguments",
    [
        {"action": "query", "title": "not allowed"},
        {"action": "query", "query": None},
        {"action": "write", "title": "missing body"},
        {"action": "write", "title": "x", "body": "y", "query": "not allowed"},
        {"action": "query", "unknown": "field"},
    ],
)
def test_action_specific_argument_validation(arguments: dict[str, object]) -> None:
    with pytest.raises(ValidationError):
        MemoryArguments.model_validate(arguments)


@pytest.mark.asyncio
async def test_low_level_handlers_dispatch_all_actions_and_safe_errors(caplog) -> None:
    class FakeCore:
        def __init__(self) -> None:
            self.calls: list[tuple[str, object]] = []

        def list_index(self, *, project: str | None) -> str:
            self.calls.append(("index", project))
            return "index result"

        def recall(self, *, query: str, project: str | None) -> str:
            self.calls.append(("recall", (query, project)))
            if query == "expected-error":
                raise MemoryValidationError("safe expected error")
            if query == "unexpected-error":
                raise RuntimeError("private provider detail")
            return "recall result"

        def write(self, *, title: str, body: str, project: str | None) -> str:
            self.calls.append(("write", (title, body, project)))
            return "write result"

    core = FakeCore()
    server = create_server(core)  # type: ignore[arg-type]
    list_handler = server._request_handlers["tools/list"].handler
    call_handler = server._request_handlers["tools/call"].handler

    listed = await list_handler(None, None)
    assert [tool.name for tool in listed.tools] == ["memory"]
    unknown = await call_handler(None, types.CallToolRequestParams(name="other"))
    invalid = await call_handler(
        None,
        types.CallToolRequestParams(name="memory", arguments={"action": "query", "extra": 1}),
    )
    indexed = await call_handler(
        None,
        types.CallToolRequestParams(name="memory", arguments={"action": "query"}),
    )
    recalled = await call_handler(
        None,
        types.CallToolRequestParams(
            name="memory",
            arguments={"action": "query", "query": "topic", "project": "vexor"},
        ),
    )
    written = await call_handler(
        None,
        types.CallToolRequestParams(
            name="memory",
            arguments={"action": "write", "title": "Title", "body": "Body"},
        ),
    )
    expected = await call_handler(
        None,
        types.CallToolRequestParams(
            name="memory",
            arguments={"action": "query", "query": "expected-error"},
        ),
    )
    unexpected = await call_handler(
        None,
        types.CallToolRequestParams(
            name="memory",
            arguments={"action": "query", "query": "unexpected-error"},
        ),
    )

    assert unknown.is_error and invalid.is_error
    assert result_text(indexed) == "index result"
    assert result_text(recalled) == "recall result"
    assert result_text(written) == "write result"
    assert result_text(expected) == "safe expected error"
    assert "private provider detail" not in result_text(unexpected)
    assert core.calls[:3] == [
        ("index", None),
        ("recall", ("topic", "vexor")),
        ("write", ("Title", "Body", None)),
    ]
    assert "private provider detail" not in caplog.text


@pytest.mark.asyncio
async def test_run_stdio_wires_streams_to_server(monkeypatch) -> None:
    from contextlib import asynccontextmanager

    calls: list[tuple[object, object, object]] = []

    class FakeServer:
        def create_initialization_options(self) -> str:
            return "options"

        async def run(self, read: object, write: object, options: object) -> None:
            calls.append((read, write, options))

    @asynccontextmanager
    async def fake_stdio():
        yield "read", "write"

    monkeypatch.setattr("perenna.mcp_server.create_server", lambda _core: FakeServer())
    monkeypatch.setattr("perenna.mcp_server.stdio_server", fake_stdio)

    await run_stdio(object())  # type: ignore[arg-type]

    assert calls == [("read", "write", "options")]


@pytest.mark.asyncio
async def test_real_stdio_process_lists_only_memory_and_keeps_protocol_clean(
    tmp_path: Path,
) -> None:
    async with perenna_session(tmp_path / "home", "codex") as (
        session,
        initialized,
        stderr,
    ):
        tools = await session.list_tools()
        assert initialized.server_info.name == "Perenna"
        assert [tool.name for tool in tools.tools] == ["memory"]
        assert tools.tools[0].input_schema == MEMORY_TOOL_SCHEMA

        bad = await session.call_tool("memory", {"action": "query", "extra": "rejected"})
        assert bad.is_error
        assert "Invalid memory arguments" in result_text(bad)

        index = await session.call_tool("memory", {"action": "query"})
        assert not index.is_error
        assert "Global memories:" in result_text(index)

    assert "Traceback" not in stderr.getvalue()


def test_missing_source_exits_on_stderr_without_protocol_output(tmp_path: Path) -> None:
    environment = os.environ.copy()
    environment.pop("PERENNA_SOURCE", None)
    environment["PERENNA_GIT_REMOTE"] = ""

    result = subprocess.run(
        [sys.executable, "-m", "perenna", "mcp", "--home", os.fspath(tmp_path / "home")],
        cwd=Path(__file__).parents[1],
        env=environment,
        check=False,
        capture_output=True,
        text=True,
        timeout=15,
    )

    assert result.returncode == 2
    assert result.stdout == ""
    assert "Memory source is missing" in result.stderr
