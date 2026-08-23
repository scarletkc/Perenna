from __future__ import annotations

from pathlib import Path

import yaml

SKILL_PATH = Path(__file__).parents[1] / "skills" / "perenna-memory" / "SKILL.md"
CURATION_PATH = SKILL_PATH.parent / "references" / "curation.md"
IMPORTING_PATH = SKILL_PATH.parent / "references" / "importing.md"
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
    assert "references/importing.md" in body
    assert "references/unavailable.md" in body
    assert "Do not mirror, dual-write" in body
    assert "host-local advisory cache" in body
    assert "Git auditability" in body
    assert CURATION_PATH.is_file()
    assert IMPORTING_PATH.is_file()
    assert UNAVAILABLE_PATH.is_file()

    curation = CURATION_PATH.read_text(encoding="utf-8")
    flattened_curation = " ".join(curation.split())
    assert "Treat feedback as source material" in flattened_curation
    assert "do not preserve feedback as an event or category" in flattened_curation

    importing = IMPORTING_PATH.read_text(encoding="utf-8")
    flattened_importing = " ".join(importing.split())
    assert "Installing or connecting Perenna does not authorize an import" in flattened_importing
    assert "one-time migration, not permission to mirror" in flattened_importing
    assert "Include the destination project" in flattened_importing
    assert "Do not bypass the MCP tools" in flattened_importing

    combined = "\n".join(
        (
            body,
            CURATION_PATH.read_text(encoding="utf-8"),
            IMPORTING_PATH.read_text(encoding="utf-8"),
            UNAVAILABLE_PATH.read_text(encoding="utf-8"),
        )
    )
    flattened = " ".join(combined.split())
    assert {"memory_read", "memory_write", "memory_delete"} <= set(combined.split("`"))
    assert "https://github.com/scarletkc/Perenna/blob/main/docs/getting-started.md" in combined
    assert "https://github.com/scarletkc/Perenna/blob/main/docs/guides/client-setup.md" in combined
    assert "https://github.com/scarletkc/Perenna/blob/main/docs/guides/self-hosting.md" in combined
    assert "perenna mcp --source <stable-client-name>" in combined
    assert "perenna serve" in combined
    assert "ask the user to configure a persistent Docker deployment" in flattened
    assert "Do not run remote deployment commands" in flattened
    assert "both the local commit result and the synchronization state" in flattened
    assert "Do not repeat a successful local mutation" in flattened
    assert "perenna sync status" in combined
    assert "docs/guides/maintenance.md#recover-from-a-git-synchronization-failure" in combined
