from __future__ import annotations

from pathlib import Path

import pytest

from perenna.git import GitRepository
from perenna.store import MemoryStore
from tests.helpers import EmbeddingServer, perenna_session, result_text


@pytest.mark.asyncio
async def test_cross_agent_write_recall_and_update_preserves_identity(tmp_path: Path) -> None:
    home = tmp_path / "home"
    with EmbeddingServer() as server:
        async with perenna_session(home, "claude-code", embedding_server=server) as (
            claude,
            _,
            _,
        ):
            created = await claude.call_tool(
                "memory",
                {
                    "action": "write",
                    "title": "AI collaboration preferences",
                    "body": "Work proactively on clear tasks.",
                },
            )
            assert not created.is_error
            assert "created" in result_text(created)

        repository = GitRepository.initialize(home / "memory")
        first = MemoryStore(repository).snapshot().memories[0]

        async with perenna_session(home, "codex", embedding_server=server) as (codex, _, _):
            recalled = await codex.call_tool(
                "memory",
                {"action": "query", "query": "proactively clear tasks"},
            )
            assert not recalled.is_error
            assert "Work proactively on clear tasks." in result_text(recalled)

        async with perenna_session(home, "cursor", embedding_server=server) as (cursor, _, _):
            updated_result = await cursor.call_tool(
                "memory",
                {
                    "action": "write",
                    "title": "ai collaboration preferences",
                    "body": "Work proactively and explain important design decisions.",
                },
            )
            assert not updated_result.is_error
            assert "updated" in result_text(updated_result)

    final_snapshot = MemoryStore(repository).snapshot()
    assert len(final_snapshot.memories) == 1
    updated = final_snapshot.memories[0]
    assert updated.id == first.id
    assert updated.created_at == first.created_at
    assert updated.updated_at > first.updated_at
    assert updated.source == "cursor"
    assert updated.body == "Work proactively and explain important design decisions."
    assert repository._run(["rev-list", "--count", "HEAD"]).stdout.strip() == "2"
    repository.assert_clean()
    embedded_texts = [text for batch in server.requests for text in batch]
    assert any(
        "AI collaboration preferences" in text and "Work proactively" in text
        for text in embedded_texts
    )
