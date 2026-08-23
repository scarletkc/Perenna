from __future__ import annotations

from pathlib import Path

import yaml

SKILL_PATH = Path(__file__).parents[1] / "skills" / "perenna-memory" / "SKILL.md"
CURATION_PATH = SKILL_PATH.parent / "references" / "curation.md"
UNAVAILABLE_PATH = SKILL_PATH.parent / "references" / "unavailable.md"


def test_perenna_memory_skill_is_discoverable_and_covers_the_tool_surface() -> None:
    text = SKILL_PATH.read_text(encoding="utf-8")
    assert text.startswith("---\n")
    frontmatter_text, body = text[4:].split("\n---\n", maxsplit=1)
    frontmatter = yaml.safe_load(frontmatter_text)

    assert frontmatter["name"] == SKILL_PATH.parent.name
    assert isinstance(frontmatter["description"], str)
    assert frontmatter["description"].strip()
    assert frontmatter["metadata"]["github-repo"] == "https://github.com/scarletkc/Perenna"
    assert "references/curation.md" in body
    assert "references/unavailable.md" in body
    assert "Do not mirror, dual-write" in body
    assert "host-local advisory cache" in body
    assert "Git auditability" in body
    assert CURATION_PATH.is_file()
    assert UNAVAILABLE_PATH.is_file()

    combined = "\n".join(
        (
            body,
            CURATION_PATH.read_text(encoding="utf-8"),
            UNAVAILABLE_PATH.read_text(encoding="utf-8"),
        )
    )
    assert {"memory_read", "memory_write", "memory_delete"} <= set(combined.split("`"))
    assert "https://github.com/scarletkc/Perenna/blob/main/docs/getting-started.md" in combined
    assert "https://github.com/scarletkc/Perenna/blob/main/docs/guides/client-setup.md" in combined
