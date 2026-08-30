from __future__ import annotations

import io
import json
import sys
from typing import Any

import mcp.types as types
import pytest

from perenna import cli
from perenna.errors import MemoryConflictError
from perenna.mcp_server import create_server
from perenna.memory_commands import MemoryCommandError, execute_memory_command
from tests.helpers import result_text

MEMORY_ID = "01ARZ3NDEKTSV4RRFFQ69G5FAV"
REVISION = "a" * 64


class RecordingCore:
    def __init__(self) -> None:
        self.calls: list[tuple[str, object]] = []

    def list_memories(self, *, project: str | None) -> dict[str, Any]:
        self.calls.append(("list", project))
        return {"action": "list", "project": project, "memories": [], "projects": []}

    def search(self, *, query: str, project: str | None, limit: int) -> dict[str, Any]:
        self.calls.append(("search", (query, project, limit)))
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
        result = _mutation("create")
        result["index_status"] = "pending"
        result["sync_status"] = "pending"
        return result

    def patch(
        self,
        *,
        memory_id: str,
        base_revision: str,
        edits: object,
        summary: str | None,
    ) -> dict[str, Any]:
        self.calls.append(("patch", (memory_id, base_revision, edits, summary)))
        if base_revision == "b" * 64:
            raise MemoryConflictError(
                f"Memory {memory_id} changed after it was read. Get the current memory and retry "
                "with its revision; no file was changed."
            )
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


def test_shared_executor_dispatches_all_seven_actions() -> None:
    core = RecordingCore()
    calls = [
        ("memory_read", {"action": "list"}),
        ("memory_read", {"action": "search", "query": "topic", "limit": 2}),
        ("memory_read", {"action": "get", "memory_id": MEMORY_ID}),
        (
            "memory_write",
            {"action": "create", "title": "Title", "summary": "Summary.", "body": "Body"},
        ),
        (
            "memory_write",
            {
                "action": "patch",
                "memory_id": MEMORY_ID,
                "base_revision": REVISION,
                "edits": [{"old_text": "Body", "new_text": "Updated"}],
            },
        ),
        (
            "memory_write",
            {
                "action": "replace",
                "memory_id": MEMORY_ID,
                "base_revision": REVISION,
                "summary": "Replacement.",
                "body": "Replacement body",
            },
        ),
        (
            "memory_delete",
            {
                "memory_id": MEMORY_ID,
                "expected_title": "Title",
                "base_revision": REVISION,
            },
        ),
    ]

    results = [
        execute_memory_command(core, tool_name, arguments)  # type: ignore[arg-type]
        for tool_name, arguments in calls
    ]

    assert [result["action"] for result in results] == [
        "list",
        "search",
        "get",
        "create",
        "patch",
        "replace",
        "delete",
    ]
    assert [name for name, _arguments in core.calls] == [
        "list",
        "search",
        "get",
        "create",
        "patch",
        "replace",
        "delete",
    ]


@pytest.mark.parametrize(
    ("tool_name", "arguments", "expected"),
    [
        ("memory_read", {"action": "get", "memory_id": None}, "Invalid memory_read arguments"),
        (
            "memory_write",
            {"action": "create", "title": "Title", "summary": "Summary."},
            "Invalid memory_write arguments",
        ),
        (
            "memory_delete",
            {"memory_id": MEMORY_ID, "expected_title": "Title", "base_revision": REVISION, "x": 1},
            "Invalid memory_delete arguments",
        ),
        ("memory", {}, "Unknown Perenna tool"),
    ],
)
def test_shared_executor_maps_schema_failures_to_the_existing_public_errors(
    tool_name: str,
    arguments: object,
    expected: str,
) -> None:
    with pytest.raises(MemoryCommandError, match=expected):
        execute_memory_command(RecordingCore(), tool_name, arguments)  # type: ignore[arg-type]


@pytest.mark.asyncio
async def test_cli_and_mcp_adapters_preserve_pending_results_and_stale_errors(
    capsys,
    monkeypatch,
) -> None:
    core = RecordingCore()
    monkeypatch.setattr(cli, "resolve_settings", lambda **_kwargs: object())
    monkeypatch.setattr(cli, "PerennaCore", lambda _settings: core)
    pending_request = {
        "action": "create",
        "title": "Private title",
        "summary": "Private summary",
        "body": "Private body",
    }
    monkeypatch.setattr(sys, "stdin", io.StringIO(json.dumps(pending_request)))

    assert cli.main(["call", "memory_write", "--input", "-"]) == 0
    cli_pending = capsys.readouterr()
    cli_payload = json.loads(cli_pending.out)
    assert cli_payload["index_status"] == "pending"
    assert cli_payload["sync_status"] == "pending"
    assert cli_pending.err == ""

    handler = create_server(core)._request_handlers["tools/call"].handler  # type: ignore[arg-type]
    mcp_pending = await handler(
        None,
        types.CallToolRequestParams(name="memory_write", arguments=pending_request),
    )
    assert mcp_pending.structured_content == cli_payload

    stale_request = {
        "action": "patch",
        "memory_id": MEMORY_ID,
        "base_revision": "b" * 64,
        "edits": [{"old_text": "Private body", "new_text": "Changed"}],
    }
    monkeypatch.setattr(sys, "stdin", io.StringIO(json.dumps(stale_request)))
    assert cli.main(["call", "memory_write", "--input", "-"]) == 2
    cli_stale = capsys.readouterr()
    mcp_stale = await handler(
        None,
        types.CallToolRequestParams(name="memory_write", arguments=stale_request),
    )

    assert cli_stale.out == ""
    assert cli_stale.err.strip() == f"perenna: {result_text(mcp_stale)}"
    assert "Private body" not in cli_stale.err
    assert "Private body" not in result_text(mcp_stale)


def _memory_payload() -> dict[str, str]:
    return {
        "memory_id": MEMORY_ID,
        "title": "Title",
        "scope": "global",
        "summary": "Summary.",
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
            "summary": "Summary.",
            **({} if action == "delete" else {"revision": REVISION}),
        },
        "commit": "c" * 40,
        "index_status": "current",
        "sync_status": "local",
    }
