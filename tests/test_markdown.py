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
    next_update_time,
    normalize_body,
    normalize_project,
    normalize_summary,
    normalize_title,
    parse_timestamp,
    title_key,
    validate_revision,
    validate_ulid,
)

MEMORY_ID = "01ARZ3NDEKTSV4RRFFQ69G5FAV"
CREATED_AT = "2026-08-22T01:02:03.000000Z"


def _memory(*, relative_path: str | None = None, scope: str = "global") -> Memory:
    return Memory(
        id=MEMORY_ID,
        title="Release notes",
        summary="What the release notes cover.",
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


@pytest.mark.parametrize(
    ("normalizer", "message"),
    [
        (normalize_title, "title must be a string"),
        (normalize_summary, "summary must be a string"),
        (normalize_body, "body must be a string"),
        (normalize_project, "project must be a string"),
    ],
)
def test_normalizers_reject_non_string_values(normalizer, message: str) -> None:  # type: ignore[no-untyped-def]
    with pytest.raises(ValueError, match=message):
        normalizer(None)


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
    with pytest.raises(ValueError, match="control character"):
        normalize_summary("summary\x00")


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


@pytest.mark.parametrize("revision", [None, "g" * 64])
def test_revision_requires_a_lowercase_sha256_digest(revision: object) -> None:
    with pytest.raises(ValueError, match="lowercase SHA-256"):
        validate_revision(revision)  # type: ignore[arg-type]


def test_ulid_rejects_a_timestamp_before_its_epoch() -> None:
    with pytest.raises(ValueError, match="cannot be encoded"):
        new_ulid(datetime(1969, 12, 31, 23, 59, 59, tzinfo=UTC))


def test_timestamp_helpers_reject_wrong_types_and_keep_updates_monotonic() -> None:
    with pytest.raises(ValueError, match="timestamp must be a string"):
        parse_timestamp(None)  # type: ignore[arg-type]

    previous = "2026-08-22T01:02:03.000000Z"
    assert next_update_time(datetime(2026, 8, 22, 1, 2, 3, tzinfo=UTC), previous) == datetime(
        2026,
        8,
        22,
        1,
        2,
        3,
        1,
        tzinfo=UTC,
    )


def test_serialized_frontmatter_has_only_the_canonical_fields_in_order() -> None:
    text = serialize_memory(_memory())
    frontmatter = text.split("---\n", 2)[1]
    loaded = yaml.safe_load(frontmatter)

    assert tuple(loaded) == FRONTMATTER_FIELDS
    assert set(loaded) == {
        "id",
        "title",
        "summary",
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
    ("mutate", "message"),
    [
        (lambda text: text.removeprefix("---\n"), "start on the first line"),
        (lambda text: text.replace("\n---\n\n", "\n\n", 1), "closing delimiter is missing"),
        (
            lambda text: text.replace("\n---\n\n", "\n---\n", 1),
            "followed by one blank line",
        ),
        (lambda _text: "---\n[]\n---\n\nBody\n", "frontmatter must be a mapping"),
    ],
)
def test_parser_rejects_invalid_document_structure(
    mutate,
    message: str,
) -> None:  # type: ignore[no-untyped-def]
    with pytest.raises(MemoryValidationError, match=message):
        parse_memory(mutate(serialize_memory(_memory())), f"global/{MEMORY_ID}.md")


@pytest.mark.parametrize(
    ("old", "new", "message"),
    [
        (
            f'created_at: "{CREATED_AT}"',
            "created_at: 123",
            "timestamps must be quoted strings",
        ),
        ('title: "Release notes"', 'title: " Release notes "', "title is not normalized"),
        (
            'summary: "What the release notes cover."',
            'summary: " What the release notes cover. "',
            "summary is not normalized",
        ),
        (
            f'updated_at: "{CREATED_AT}"',
            'updated_at: "2026-08-22T01:02:02.000000Z"',
            "updated_at is earlier than created_at",
        ),
    ],
)
def test_parser_rejects_noncanonical_frontmatter_values(
    old: str,
    new: str,
    message: str,
) -> None:
    text = serialize_memory(_memory()).replace(old, new, 1)

    with pytest.raises(MemoryValidationError, match=message):
        parse_memory(text, f"global/{MEMORY_ID}.md")


@pytest.mark.parametrize(
    ("relative_path", "message"),
    [
        (f"projects/con/{MEMORY_ID}.md", "project directory is invalid"),
        (f"projects/Perenna/{MEMORY_ID}.md", "project directory is not normalized"),
        (f"archive/{MEMORY_ID}.md", "path must be global"),
        ("global/not-a-ulid.md", "filename is not a ULID"),
    ],
)
def test_parser_rejects_noncanonical_memory_paths(relative_path: str, message: str) -> None:
    with pytest.raises(MemoryValidationError, match=message):
        parse_memory(serialize_memory(_memory()), relative_path)


@pytest.mark.parametrize(
    "mutate",
    [
        lambda text: text.replace('summary: "What the release notes cover."\n', ""),
        lambda text: text.replace(
            'summary: "What the release notes cover."\n',
            'summary: "What the release notes cover."\nsource: "codex"\n',
        ),
        lambda text: text.replace(
            'summary: "What the release notes cover."\n',
            'summary: "What the release notes cover."\nproject: "perenna"\n',
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
