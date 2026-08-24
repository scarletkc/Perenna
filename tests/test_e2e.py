from __future__ import annotations

from pathlib import Path

import pytest

from perenna.git import GitRepository
from perenna.store import MemoryStore
from tests.helpers import EmbeddingServer, perenna_session


@pytest.mark.asyncio
async def test_cross_agent_create_search_get_patch_and_delete(tmp_path: Path) -> None:
    home = tmp_path / "home"
    with EmbeddingServer() as server:
        async with perenna_session(home, embedding_server=server) as (
            claude,
            _,
            _,
        ):
            created = await claude.call_tool(
                "memory_write",
                {
                    "action": "create",
                    "title": "AI collaboration preferences",
                    "summary": "Stable preferences for collaborating with AI agents.",
                    "body": "Work proactively on clear tasks.",
                },
            )
            assert not created.is_error
            memory_id = created.structured_content["memory"]["memory_id"]
            first_revision = created.structured_content["memory"]["revision"]

        repository = GitRepository.initialize(home / "memory")
        first = MemoryStore(repository).snapshot().memories[0]

        async with perenna_session(home, embedding_server=server) as (codex, _, _):
            searched = await codex.call_tool(
                "memory_read",
                {"action": "search", "query": "proactively clear tasks", "limit": 1},
            )
            assert not searched.is_error
            match = searched.structured_content["matches"][0]
            assert match["memory_id"] == memory_id
            assert match["summary"] == "Stable preferences for collaborating with AI agents."
            assert match["passages"][0]["text"] == "Work proactively on clear tasks."

            fetched = await codex.call_tool(
                "memory_read",
                {"action": "get", "memory_id": memory_id},
            )
            assert fetched.structured_content["memory"]["body"] == first.body
            assert fetched.structured_content["memory"]["revision"] == first_revision

        async with perenna_session(home, embedding_server=server) as (cursor, _, _):
            patched = await cursor.call_tool(
                "memory_write",
                {
                    "action": "patch",
                    "memory_id": memory_id,
                    "base_revision": first_revision,
                    "edits": [
                        {
                            "old_text": "Work proactively on clear tasks.",
                            "new_text": (
                                "Work proactively and explain important design decisions."
                            ),
                        }
                    ],
                },
            )
            assert not patched.is_error
            patched_revision = patched.structured_content["memory"]["revision"]

            deleted = await cursor.call_tool(
                "memory_delete",
                {
                    "memory_id": memory_id,
                    "expected_title": "AI collaboration preferences",
                    "base_revision": patched_revision,
                },
            )
            assert not deleted.is_error
            assert deleted.structured_content["recoverable_via_git"]

    assert MemoryStore(repository).snapshot().memories == ()
    assert repository._run(["rev-list", "--count", "HEAD"]).stdout.strip() == "3"
    repository.assert_clean()
    embedded_texts = [text for batch in server.requests for text in batch]
    assert any(
        "AI collaboration preferences" in text
        and "Stable preferences for collaborating" in text
        and "Work proactively" in text
        for text in embedded_texts
    )
