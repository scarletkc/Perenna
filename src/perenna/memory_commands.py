from __future__ import annotations

from typing import Any, Literal, Self, cast

from pydantic import BaseModel, ConfigDict, Field, ValidationError, model_validator

from perenna.core import PerennaCore
from perenna.errors import PerennaError
from perenna.index import DEFAULT_SEARCH_LIMIT, MAX_SEARCH_MATCHES
from perenna.models import PatchEdit

MEMORY_TOOL_NAMES = ("memory_read", "memory_write", "memory_delete")


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


class MemoryCommandError(PerennaError):
    """A tool name or argument object does not match the public memory contract."""


def execute_memory_command(
    core: PerennaCore,
    tool_name: str,
    raw: object,
) -> dict[str, Any]:
    """Validate and execute one public memory tool call without transport behavior."""
    try:
        if tool_name == "memory_read":
            return _execute_read(core, raw)
        if tool_name == "memory_write":
            return _execute_write(core, raw)
        if tool_name == "memory_delete":
            return _execute_delete(core, raw)
    except ValidationError:
        raise MemoryCommandError(argument_error(tool_name)) from None
    raise MemoryCommandError(
        "Unknown Perenna tool. Use memory_read, memory_write, or memory_delete."
    )


def argument_error(tool_name: str) -> str:
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


def _execute_read(core: PerennaCore, raw: object) -> dict[str, Any]:
    arguments = MemoryReadArguments.model_validate(raw)
    if arguments.action == "list":
        return core.list_memories(project=arguments.project)
    if arguments.action == "search":
        return core.search(
            query=cast(str, arguments.query),
            project=arguments.project,
            limit=arguments.limit,
        )
    return core.get(memory_id=cast(str, arguments.memory_id))


def _execute_write(core: PerennaCore, raw: object) -> dict[str, Any]:
    arguments = MemoryWriteArguments.model_validate(raw)
    if arguments.action == "create":
        return core.create(
            title=cast(str, arguments.title),
            summary=cast(str, arguments.summary),
            body=cast(str, arguments.body),
            project=arguments.project,
        )
    memory_id = cast(str, arguments.memory_id)
    base_revision = cast(str, arguments.base_revision)
    if arguments.action == "patch":
        edits = tuple(
            PatchEdit(old_text=edit.old_text, new_text=edit.new_text)
            for edit in cast(list[PatchEditArguments], arguments.edits)
        )
        return core.patch(
            memory_id=memory_id,
            base_revision=base_revision,
            edits=edits,
            summary=arguments.summary,
        )
    return core.replace(
        memory_id=memory_id,
        base_revision=base_revision,
        summary=cast(str, arguments.summary),
        body=cast(str, arguments.body),
    )


def _execute_delete(core: PerennaCore, raw: object) -> dict[str, Any]:
    arguments = MemoryDeleteArguments.model_validate(raw)
    return core.delete(
        memory_id=arguments.memory_id,
        expected_title=arguments.expected_title,
        base_revision=arguments.base_revision,
    )


def _reject_explicit_nulls(arguments: BaseModel) -> None:
    if any(getattr(arguments, field, None) is None for field in arguments.model_fields_set):
        raise ValueError("tool fields cannot be null")
