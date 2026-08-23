"""The exact MCP wire contract: tool metadata, schemas, scopes, instructions.

This module is declarative only. Server behavior, argument validation, and
dispatch live in `perenna.mcp_server`.
"""

from __future__ import annotations

import mcp.types as types

from perenna.index import MAX_SEARCH_MATCHES

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

_SYNC_STATUS_SCHEMA: dict[str, object] = {
    "type": "string",
    "enum": ["local", "synchronized", "pending", "conflict", "unchanged"],
}

MEMORY_WRITE_OUTPUT_SCHEMA: dict[str, object] = {
    "type": "object",
    "properties": {
        "action": {"type": "string", "enum": ["create", "patch", "replace"]},
        "changed": {"type": "boolean"},
        "memory": _MUTATION_MEMORY_SCHEMA,
        "commit": {"type": "string"},
        "index_status": {"type": "string", "enum": ["current", "pending"]},
        "sync_status": _SYNC_STATUS_SCHEMA,
    },
    "required": ["action", "changed", "memory", "commit", "index_status", "sync_status"],
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
        "sync_status": _SYNC_STATUS_SCHEMA,
        "recoverable_via_git": {"const": True},
    },
    "required": [
        "action",
        "changed",
        "memory",
        "commit",
        "index_status",
        "sync_status",
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
