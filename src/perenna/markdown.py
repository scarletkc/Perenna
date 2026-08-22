from __future__ import annotations

import json
from pathlib import PurePosixPath
from typing import Any

import yaml

from perenna.errors import MemoryValidationError
from perenna.models import (
    Memory,
    normalize_body,
    normalize_project,
    normalize_source,
    normalize_title,
    parse_timestamp,
    validate_ulid,
)

FRONTMATTER_FIELDS = ("id", "title", "source", "created_at", "updated_at")


class _UniqueSafeLoader(yaml.SafeLoader):
    pass


def _construct_unique_mapping(
    loader: _UniqueSafeLoader,
    node: yaml.nodes.MappingNode,
    deep: bool = False,
) -> dict[Any, Any]:
    loader.flatten_mapping(node)
    result: dict[Any, Any] = {}
    for key_node, value_node in node.value:
        key = loader.construct_object(key_node, deep=deep)
        if not isinstance(key, str):
            raise yaml.constructor.ConstructorError(
                "while constructing frontmatter",
                node.start_mark,
                "frontmatter field names must be strings",
                key_node.start_mark,
            )
        if key in result:
            raise yaml.constructor.ConstructorError(
                "while constructing frontmatter",
                node.start_mark,
                f"duplicate field {key!r}",
                key_node.start_mark,
            )
        result[key] = loader.construct_object(value_node, deep=deep)
    return result


_UniqueSafeLoader.add_constructor(
    yaml.resolver.BaseResolver.DEFAULT_MAPPING_TAG,
    _construct_unique_mapping,
)


def serialize_memory(memory: Memory) -> str:
    lines = ["---"]
    for field in FRONTMATTER_FIELDS:
        value = getattr(memory, field)
        lines.append(f"{field}: {json.dumps(value, ensure_ascii=False)}")
    lines.extend(("---", "", normalize_body(memory.body)))
    return "\n".join(lines) + "\n"


def parse_memory(text: str, relative_path: str) -> Memory:
    normalized_text = text.replace("\r\n", "\n").replace("\r", "\n")
    if not normalized_text.startswith("---\n"):
        raise _invalid(relative_path, "frontmatter must start on the first line")
    frontmatter_text, separator, remainder = normalized_text[4:].partition("\n---\n")
    if not separator:
        raise _invalid(relative_path, "frontmatter closing delimiter is missing")
    if not remainder.startswith("\n"):
        raise _invalid(relative_path, "frontmatter must be followed by one blank line")

    try:
        raw = yaml.load(frontmatter_text, Loader=_UniqueSafeLoader)
    except yaml.YAMLError as exc:
        raise _invalid(relative_path, "frontmatter is not valid YAML") from exc
    if not isinstance(raw, dict):
        raise _invalid(relative_path, "frontmatter must be a mapping")
    if set(raw) != set(FRONTMATTER_FIELDS):
        missing = sorted(set(FRONTMATTER_FIELDS) - set(raw))
        extra = sorted(str(key) for key in set(raw) - set(FRONTMATTER_FIELDS))
        details = []
        if missing:
            details.append(f"missing fields: {', '.join(missing)}")
        if extra:
            details.append(f"unsupported fields: {', '.join(map(str, extra))}")
        raise _invalid(relative_path, "; ".join(details))

    body = remainder[1:]
    if body.endswith("\n"):
        body = body[:-1]
    try:
        memory_id = validate_ulid(raw["id"])
        title = normalize_title(raw["title"])
        source = normalize_source(raw["source"])
        created_at = _timestamp_string(raw["created_at"])
        updated_at = _timestamp_string(raw["updated_at"])
        normalized_body = normalize_body(body)
    except (TypeError, ValueError) as exc:
        raise _invalid(relative_path, str(exc)) from exc

    if title != raw["title"]:
        raise _invalid(relative_path, "title is not normalized")
    if source != raw["source"]:
        raise _invalid(relative_path, "source is not normalized")
    if parse_timestamp(updated_at) < parse_timestamp(created_at):
        raise _invalid(relative_path, "updated_at is earlier than created_at")

    scope, path_id = _scope_and_id(relative_path)
    if path_id != memory_id:
        raise _invalid(relative_path, "frontmatter id does not match the filename")
    return Memory(
        id=memory_id,
        title=title,
        source=source,
        created_at=created_at,
        updated_at=updated_at,
        body=normalized_body,
        scope=scope,
        relative_path=relative_path,
    )


def _scope_and_id(relative_path: str) -> tuple[str, str]:
    path = PurePosixPath(relative_path)
    parts = path.parts
    if len(parts) == 2 and parts[0] == "global" and path.suffix == ".md":
        memory_id = path.stem
        scope = "global"
    elif len(parts) == 3 and parts[0] == "projects" and path.suffix == ".md":
        try:
            project = normalize_project(parts[1])
        except ValueError as exc:
            raise _invalid(relative_path, "project directory is invalid") from exc
        if project != parts[1]:
            raise _invalid(relative_path, "project directory is not normalized")
        memory_id = path.stem
        scope = f"project:{project}"
    else:
        raise _invalid(relative_path, "path must be global/<ULID>.md or projects/<slug>/<ULID>.md")
    try:
        validate_ulid(memory_id)
    except ValueError as exc:
        raise _invalid(relative_path, "filename is not a ULID") from exc
    return scope, memory_id


def _timestamp_string(value: object) -> str:
    if not isinstance(value, str):
        raise ValueError("timestamps must be quoted strings")
    parse_timestamp(value)
    return value


def _invalid(relative_path: str, reason: str) -> MemoryValidationError:
    return MemoryValidationError(
        f"Committed memory {relative_path!r} is invalid: {reason}. "
        "Repair the Markdown in the memory repository and commit the correction."
    )
