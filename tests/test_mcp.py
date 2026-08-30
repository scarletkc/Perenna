from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path
from typing import Any

import mcp.types as types
import pytest
from jsonschema import Draft202012Validator
from pydantic import ValidationError

from perenna.errors import MemoryValidationError
from perenna.mcp_schemas import (
    MEMORY_DELETE_OUTPUT_SCHEMA,
    MEMORY_DELETE_SCHEMA,
    MEMORY_READ_OUTPUT_SCHEMA,
    MEMORY_READ_SCHEMA,
    MEMORY_WRITE_OUTPUT_SCHEMA,
    MEMORY_WRITE_SCHEMA,
    SERVER_INSTRUCTIONS,
)
from perenna.mcp_server import _summary, create_server, run_stdio
from perenna.memory_commands import (
    MemoryDeleteArguments,
    MemoryReadArguments,
    MemoryWriteArguments,
)
from tests.helpers import perenna_session, result_text

MEMORY_ID = "01ARZ3NDEKTSV4RRFFQ69G5FAV"
REVISION = "a" * 64


def _schema_action(branch: dict[str, Any]) -> str:
    return branch["properties"]["action"]["const"]


def test_tool_schemas_are_separate_exact_and_action_specific() -> None:
    assert [_schema_action(branch) for branch in MEMORY_READ_SCHEMA["oneOf"]] == [
        "list",
        "search",
        "get",
    ]
    assert [_schema_action(branch) for branch in MEMORY_WRITE_SCHEMA["oneOf"]] == [
        "create",
        "patch",
        "replace",
    ]
    assert MEMORY_DELETE_SCHEMA["required"] == [
        "memory_id",
        "expected_title",
        "base_revision",
    ]
    get_output = next(
        branch
        for branch in MEMORY_READ_OUTPUT_SCHEMA["oneOf"]
        if _schema_action(branch) == "get"
    )
    assert "source" not in get_output["properties"]["memory"]["properties"]
    assert all(
        branch["additionalProperties"] is False
        for schema in (MEMORY_READ_SCHEMA, MEMORY_WRITE_SCHEMA)
        for branch in schema["oneOf"]
    )
    assert MEMORY_DELETE_SCHEMA["additionalProperties"] is False


@pytest.mark.parametrize(
    ("schema", "arguments", "valid"),
    [
        (MEMORY_READ_SCHEMA, {"action": "list"}, True),
        (MEMORY_READ_SCHEMA, {"action": "list", "project": "perenna"}, True),
        (MEMORY_READ_SCHEMA, {"action": "search", "query": "topic", "limit": 2}, True),
        (MEMORY_READ_SCHEMA, {"action": "get", "memory_id": MEMORY_ID}, True),
        (
            MEMORY_READ_SCHEMA,
            {"action": "get", "memory_id": MEMORY_ID, "project": "perenna"},
            False,
        ),
        (MEMORY_READ_SCHEMA, {"action": "search"}, False),
        (
            MEMORY_WRITE_SCHEMA,
            {"action": "create", "title": "Title", "summary": "Summary.", "body": "Body"},
            True,
        ),
        (
            MEMORY_WRITE_SCHEMA,
            {
                "action": "patch",
                "memory_id": MEMORY_ID,
                "base_revision": REVISION,
                "edits": [{"old_text": "Body", "new_text": "Updated"}],
            },
            True,
        ),
        (
            MEMORY_WRITE_SCHEMA,
            {
                "action": "replace",
                "memory_id": MEMORY_ID,
                "base_revision": REVISION,
                "summary": "Summary.",
                "body": "Body",
            },
            True,
        ),
        (
            MEMORY_WRITE_SCHEMA,
            {
                "action": "patch",
                "memory_id": MEMORY_ID,
                "base_revision": REVISION,
                "edits": [{"old_text": "Body", "new_text": "Updated"}],
                "project": "perenna",
            },
            False,
        ),
        (
            MEMORY_WRITE_SCHEMA,
            {"action": "create", "title": "Title", "summary": "Summary."},
            False,
        ),
    ],
)
def test_action_specific_input_schemas_match_the_runtime_contract(
    schema: dict[str, object],
    arguments: dict[str, object],
    valid: bool,
) -> None:
    assert Draft202012Validator(schema).is_valid(arguments) is valid


@pytest.mark.parametrize(
    ("model", "arguments"),
    [
        (MemoryReadArguments, {"action": "list", "query": "not allowed"}),
        (MemoryReadArguments, {"action": "search"}),
        (MemoryReadArguments, {"action": "search", "query": "x", "limit": 0}),
        (MemoryReadArguments, {"action": "get", "memory_id": None}),
        (MemoryWriteArguments, {"action": "create", "title": "missing summary", "body": "x"}),
        (
            MemoryWriteArguments,
            {"action": "patch", "memory_id": MEMORY_ID, "base_revision": REVISION, "edits": []},
        ),
        (
            MemoryWriteArguments,
            {
                "action": "replace",
                "memory_id": MEMORY_ID,
                "base_revision": REVISION,
                "summary": "Missing body.",
            },
        ),
        (
            MemoryDeleteArguments,
            {"memory_id": MEMORY_ID, "expected_title": "Title", "base_revision": REVISION, "x": 1},
        ),
    ],
)
def test_action_specific_argument_validation(
    model: type[Any],
    arguments: dict[str, object],
) -> None:
    with pytest.raises(ValidationError):
        model.model_validate(arguments)


@pytest.mark.asyncio
async def test_low_level_handlers_dispatch_every_tool_and_keep_errors_safe(caplog) -> None:
    class FakeCore:
        def __init__(self) -> None:
            self.calls: list[tuple[str, object]] = []

        def list_memories(self, *, project: str | None) -> dict[str, Any]:
            self.calls.append(("list", project))
            return {"action": "list", "project": project, "memories": [], "projects": []}

        def search(self, *, query: str, project: str | None, limit: int) -> dict[str, Any]:
            self.calls.append(("search", (query, project, limit)))
            if query == "expected-error":
                raise MemoryValidationError("safe expected error")
            if query == "unexpected-error":
                raise RuntimeError("private provider detail")
            return {
                "action": "search",
                "project": project,
                "limit": limit,
                "matches": [],
                "truncated": False,
            }

        def get(self, *, memory_id: str) -> dict[str, Any]:
            self.calls.append(("get", memory_id))
            return {"action": "get", "memory": _memory_payload()}

        def create(
            self,
            *,
            title: str,
            summary: str,
            body: str,
            project: str | None,
        ) -> dict[str, Any]:
            self.calls.append(("create", (title, summary, body, project)))
            return _mutation("create")

        def patch(
            self,
            *,
            memory_id: str,
            base_revision: str,
            edits: object,
            summary: str | None,
        ) -> dict[str, Any]:
            self.calls.append(("patch", (memory_id, base_revision, edits, summary)))
            return _mutation("patch")

        def replace(
            self,
            *,
            memory_id: str,
            base_revision: str,
            summary: str,
            body: str,
        ) -> dict[str, Any]:
            self.calls.append(("replace", (memory_id, base_revision, summary, body)))
            return _mutation("replace")

        def delete(
            self,
            *,
            memory_id: str,
            expected_title: str,
            base_revision: str,
        ) -> dict[str, Any]:
            self.calls.append(("delete", (memory_id, expected_title, base_revision)))
            return {**_mutation("delete"), "recoverable_via_git": True}

    core = FakeCore()
    server = create_server(core)  # type: ignore[arg-type]
    list_handler = server._request_handlers["tools/list"].handler
    call_handler = server._request_handlers["tools/call"].handler

    listed = await list_handler(None, None)
    assert [tool.name for tool in listed.tools] == [
        "memory_read",
        "memory_write",
        "memory_delete",
    ]
    assert listed.tools[0].annotations.read_only_hint
    assert listed.tools[1].annotations.destructive_hint
    assert listed.tools[2].annotations.destructive_hint
    assert [tool.output_schema for tool in listed.tools] == [
        MEMORY_READ_OUTPUT_SCHEMA,
        MEMORY_WRITE_OUTPUT_SCHEMA,
        MEMORY_DELETE_OUTPUT_SCHEMA,
    ]
    assert all(tool.meta is None for tool in listed.tools)

    unknown = await call_handler(None, types.CallToolRequestParams(name="memory"))
    invalid = await call_handler(
        None,
        types.CallToolRequestParams(
            name="memory_read",
            arguments={"action": "search", "query": "x", "limit": 6},
        ),
    )
    invalid_write = await call_handler(
        None,
        types.CallToolRequestParams(
            name="memory_write",
            arguments={"action": "create", "title": "Title", "body": "Body"},
        ),
    )
    invalid_delete = await call_handler(
        None,
        types.CallToolRequestParams(
            name="memory_delete",
            arguments={"memory_id": MEMORY_ID},
        ),
    )
    listed_result = await call_handler(
        None,
        types.CallToolRequestParams(name="memory_read", arguments={"action": "list"}),
    )
    searched = await call_handler(
        None,
        types.CallToolRequestParams(
            name="memory_read",
            arguments={"action": "search", "query": "topic", "project": "vexor", "limit": 2},
        ),
    )
    fetched = await call_handler(
        None,
        types.CallToolRequestParams(
            name="memory_read",
            arguments={"action": "get", "memory_id": MEMORY_ID},
        ),
    )
    created = await call_handler(
        None,
        types.CallToolRequestParams(
            name="memory_write",
            arguments={
                "action": "create",
                "title": "Title",
                "summary": "What this memory covers.",
                "body": "Body",
            },
        ),
    )
    patched = await call_handler(
        None,
        types.CallToolRequestParams(
            name="memory_write",
            arguments={
                "action": "patch",
                "memory_id": MEMORY_ID,
                "base_revision": REVISION,
                "summary": "Updated coverage.",
                "edits": [{"old_text": "Body", "new_text": "Updated"}],
            },
        ),
    )
    replaced = await call_handler(
        None,
        types.CallToolRequestParams(
            name="memory_write",
            arguments={
                "action": "replace",
                "memory_id": MEMORY_ID,
                "base_revision": REVISION,
                "summary": "Replacement coverage.",
                "body": "Replacement",
            },
        ),
    )
    deleted = await call_handler(
        None,
        types.CallToolRequestParams(
            name="memory_delete",
            arguments={
                "memory_id": MEMORY_ID,
                "expected_title": "Title",
                "base_revision": REVISION,
            },
        ),
    )
    expected = await call_handler(
        None,
        types.CallToolRequestParams(
            name="memory_read",
            arguments={"action": "search", "query": "expected-error"},
        ),
    )
    unexpected = await call_handler(
        None,
        types.CallToolRequestParams(
            name="memory_read",
            arguments={"action": "search", "query": "unexpected-error"},
        ),
    )

    assert all(result.is_error for result in (unknown, invalid, invalid_write, invalid_delete))
    assert all(
        not result.is_error
        for result in (listed_result, searched, fetched, created, patched, replaced, deleted)
    )
    assert searched.structured_content["limit"] == 2
    assert created.structured_content["memory"]["summary"] == "What this memory covers."
    assert result_text(expected) == "safe expected error"
    assert "private provider detail" not in result_text(unexpected)
    assert [call[0] for call in core.calls[:7]] == [
        "list",
        "search",
        "get",
        "create",
        "patch",
        "replace",
        "delete",
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
async def test_real_stdio_process_lists_three_tools_and_returns_structured_content(
    tmp_path: Path,
) -> None:
    async with perenna_session(tmp_path / "home") as (
        session,
        initialized,
        stderr,
    ):
        tools = await session.list_tools()
        assert initialized.server_info.name == "Perenna"
        assert initialized.instructions == SERVER_INSTRUCTIONS
        assert "do not mirror or dual-write" in initialized.instructions
        assert [tool.name for tool in tools.tools] == [
            "memory_read",
            "memory_write",
            "memory_delete",
        ]
        assert tools.tools[0].input_schema == MEMORY_READ_SCHEMA

        bad = await session.call_tool(
            "memory_read",
            {"action": "search", "query": "x", "limit": 9},
        )
        assert bad.is_error
        assert "Invalid memory_read arguments" in result_text(bad)

        incompatible = await session.call_tool(
            "memory_read",
            {"action": "get", "memory_id": MEMORY_ID, "project": "perenna"},
        )
        assert incompatible.is_error
        assert "get requires action and memory_id" in result_text(incompatible)

        index = await session.call_tool("memory_read", {"action": "list"})
        assert not index.is_error
        assert index.structured_content == {
            "action": "list",
            "project": None,
            "memories": [],
            "projects": [],
        }

    assert "Traceback" not in stderr.getvalue()


def test_removed_source_flag_exits_on_stderr_without_protocol_output(tmp_path: Path) -> None:
    environment = os.environ.copy()
    environment["PERENNA_GIT_REMOTE"] = ""

    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "perenna",
            "mcp",
            "--source",
            "codex",
            "--home",
            os.fspath(tmp_path / "home"),
        ],
        cwd=Path(__file__).parents[1],
        env=environment,
        check=False,
        capture_output=True,
        text=True,
        timeout=15,
    )

    assert result.returncode == 2
    assert result.stdout == ""
    assert "unrecognized arguments: --source codex" in result.stderr


def _memory_payload() -> dict[str, str]:
    return {
        "memory_id": MEMORY_ID,
        "title": "Title",
        "scope": "global",
        "summary": "What this memory covers.",
        "created_at": "2026-08-23T00:00:00.000000Z",
        "updated_at": "2026-08-23T00:00:00.000000Z",
        "revision": REVISION,
        "body": "Body",
    }


def _mutation(action: str) -> dict[str, Any]:
    return {
        "action": action,
        "changed": True,
        "memory": {
            "memory_id": MEMORY_ID,
            "title": "Title",
            "scope": "global",
            "summary": "What this memory covers.",
            **({} if action == "delete" else {"revision": REVISION}),
        },
        "commit": "b" * 40,
        "index_status": "current",
        "sync_status": "local",
    }


def test_mutation_summary_surfaces_remote_pending_and_conflict_states() -> None:
    index_pending = _mutation("create")
    index_pending["index_status"] = "pending"
    pending = _mutation("create")
    pending["sync_status"] = "pending"
    conflict = _mutation("patch")
    conflict["sync_status"] = "conflict"

    assert "indexing failed after the Git commit" in _summary(index_pending)
    assert "next non-empty search will retry" in _summary(index_pending)
    assert "local commit remains complete" in _summary(pending)
    assert "later writes are blocked" in _summary(conflict)
