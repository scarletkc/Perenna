from __future__ import annotations

from dataclasses import replace
from datetime import UTC, datetime

import pytest
import yaml

from perenna.errors import MemoryValidationError
from perenna.markdown import FRONTMATTER_FIELDS, memory_revision, parse_memory, serialize_memory
from perenna.models import (
    MAX_BODY_LENGTH,
    MAX_SUMMARY_LENGTH,
    Memory,
    memory_path,
    new_ulid,
    normalize_body,
    normalize_project,
    normalize_summary,
    normalize_title,
    title_key,
    validate_ulid,
)

MEMORY_ID = "01ARZ3NDEKTSV4RRFFQ69G5FAV"
CREATED_AT = "2026-08-22T01:02:03.000000Z"


def _memory(*, relative_path: str | None = None, scope: str = "global") -> Memory:
    return Memory(
        id=MEMORY_ID,
        title="Release notes",
        summary="What the release notes cover.",
        source="codex",
        created_at=CREATED_AT,
        updated_at=CREATED_AT,
        body="First line\nSecond line",
        scope=scope,
        relative_path=relative_path or f"global/{MEMORY_ID}.md",
    )


def test_title_uses_nfkc_whitespace_collapse_and_casefold_key() -> None:
    assert normalize_title("  Ｒｅｌｅａｓｅ\t\n notes  ") == "Release notes"
    assert title_key("Straße") == title_key("STRASSE")


@pytest.mark.parametrize("title", ["", " \t\n ", "x" * 121])
def test_title_rejects_empty_and_overlong_values(title: str) -> None:
    with pytest.raises(ValueError):
        normalize_title(title)


def test_body_normalizes_line_endings_and_enforces_limits() -> None:
    assert normalize_body("\r\nfirst\rsecond\r\n") == "first\nsecond"
    with pytest.raises(ValueError, match="empty"):
        normalize_body("\r\n \t\r\n")
    with pytest.raises(ValueError, match="too long"):
        normalize_body("x" * (MAX_BODY_LENGTH + 1))


def test_summary_is_required_single_line_plain_text() -> None:
    assert normalize_summary("  What\nthis\tmemory covers.  ") == "What this memory covers."
    with pytest.raises(ValueError, match="empty"):
        normalize_summary(" \n ")
    with pytest.raises(ValueError, match="too long"):
        normalize_summary("x" * (MAX_SUMMARY_LENGTH + 1))


@pytest.mark.parametrize(
    "project",
    ["", ".", "..", "a..b", "../escape", "a/b", "a\\b", "space name", "x" * 65],
)
def test_project_rejects_empty_traversal_and_unsupported_values(project: str) -> None:
    with pytest.raises(ValueError):
        normalize_project(project)


def test_project_is_nfkc_normalized_lowercase() -> None:
    assert normalize_project("  Ｍｙ_Project-1.0  ") == "my_project-1.0"


def test_ulid_generation_validation_and_memory_paths() -> None:
    generated = new_ulid(datetime(2026, 8, 22, tzinfo=UTC))

    assert validate_ulid(generated) == generated
    assert len(generated) == 26
    assert memory_path(generated, None) == f"global/{generated}.md"
    assert memory_path(generated, "My_Project") == f"projects/my_project/{generated}.md"
    with pytest.raises(ValueError, match="valid ULID"):
        validate_ulid("01ARZ3NDEKTSV4RRFFQ69G5FAI")


def test_serialized_frontmatter_has_only_the_canonical_fields_in_order() -> None:
    text = serialize_memory(_memory())
    frontmatter = text.split("---\n", 2)[1]
    loaded = yaml.safe_load(frontmatter)

    assert tuple(loaded) == FRONTMATTER_FIELDS
    assert set(loaded) == {
        "id",
        "title",
        "summary",
        "source",
        "created_at",
        "updated_at",
    }
    assert text.endswith("First line\nSecond line\n")


@pytest.mark.parametrize(
    ("relative_path", "scope"),
    [
        (f"global/{MEMORY_ID}.md", "global"),
        (f"projects/perenna/{MEMORY_ID}.md", "project:perenna"),
    ],
)
def test_memory_round_trip_uses_scope_from_the_trusted_path(
    relative_path: str,
    scope: str,
) -> None:
    original = _memory(relative_path=relative_path, scope=scope)

    assert parse_memory(serialize_memory(original), relative_path) == original


def test_revision_covers_authoritative_summary() -> None:
    original = _memory()

    assert memory_revision(replace(original, summary="Different coverage.")) != memory_revision(
        original
    )


@pytest.mark.parametrize(
    "mutate",
    [
        lambda text: text.replace('summary: "What the release notes cover."\n', ""),
        lambda text: text.replace('source: "codex"\n', ""),
        lambda text: text.replace(
            'source: "codex"\n',
            'source: "codex"\nproject: "perenna"\n',
        ),
    ],
)
def test_frontmatter_rejects_missing_or_extra_fields(mutate) -> None:  # type: ignore[no-untyped-def]
    text = mutate(serialize_memory(_memory()))

    with pytest.raises(MemoryValidationError):
        parse_memory(text, f"global/{MEMORY_ID}.md")


def test_frontmatter_rejects_duplicate_fields() -> None:
    text = serialize_memory(_memory()).replace(
        'title: "Release notes"\n',
        'title: "Release notes"\ntitle: "Shadow title"\n',
    )

    with pytest.raises(MemoryValidationError, match="frontmatter is not valid YAML"):
        parse_memory(text, f"global/{MEMORY_ID}.md")


def test_frontmatter_id_must_match_the_filename() -> None:
    other_id = "01ARZ3NDEKTSV4RRFFQ69G5FAW"

    with pytest.raises(MemoryValidationError, match="does not match"):
        parse_memory(serialize_memory(_memory()), f"global/{other_id}.md")
