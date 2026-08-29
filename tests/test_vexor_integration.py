import json
import shutil
from pathlib import Path

import pytest

from perenna.errors import IndexUnavailableError
from perenna.index import VexorIndex
from perenna.models import Memory, MemorySnapshot
from tests.helpers import EmbeddingServer


def test_real_vexor_collection_scope_and_deleted_index_recovery(
    tmp_path: Path,
    monkeypatch,
) -> None:
    with EmbeddingServer() as server:
        for name, value in server.environment().items():
            monkeypatch.setenv(name, value)
        index_dir = tmp_path / "index"
        global_memory = _memory(
            "01K00000000000000000000001",
            "global",
            "global/01K00000000000000000000001.md",
            "proactive collaboration",
        )
        project_memory = _memory(
            "01K00000000000000000000002",
            "project:vexor",
            "projects/vexor/01K00000000000000000000002.md",
            "collections architecture",
        )
        other_memory = _memory(
            "01K00000000000000000000003",
            "project:other",
            "projects/other/01K00000000000000000000003.md",
            "unrelated release",
        )
        snapshot = MemorySnapshot(
            "f" * 40,
            (global_memory, project_memory, other_memory),
        )
        index = VexorIndex(index_dir)
        index.rebuild(snapshot)

        results = index.search(snapshot, "architecture", "vexor")

        assert {match.memory.id for match in results.matches} <= {
            global_memory.id,
            project_memory.id,
        }
        assert project_memory.id in {match.memory.id for match in results.matches}
        assert (index_dir / "collections.db").exists()

        shutil.rmtree(index_dir)
        assert not index_dir.exists()
        assert not index.is_current(snapshot)
        index.rebuild(snapshot)
        assert index.is_current(snapshot)


def test_real_vexor_collection_inherits_remote_reranker_configuration(
    tmp_path: Path,
    monkeypatch,
) -> None:
    with EmbeddingServer() as server:
        environment = server.environment()
        config = json.loads(environment["VEXOR_CONFIG_JSON"])
        config.update(
            {
                "rerank": "remote",
                "remote_rerank": {
                    "base_url": server.base_url,
                    "model": "perenna-test-reranker",
                },
            }
        )
        environment["VEXOR_CONFIG_JSON"] = json.dumps(config)
        environment["VEXOR_REMOTE_RERANK_API_KEY"] = "offline-rerank-key"
        for name, value in environment.items():
            monkeypatch.setenv(name, value)

        global_memory = _memory(
            "01K00000000000000000000001",
            "global",
            "global/01K00000000000000000000001.md",
            "global candidate",
        )
        project_memory = _memory(
            "01K00000000000000000000002",
            "project:vexor",
            "projects/vexor/01K00000000000000000000002.md",
            "project candidate",
        )
        excluded_memory = _memory(
            "01K00000000000000000000003",
            "project:other",
            "projects/other/01K00000000000000000000003.md",
            "excluded candidate",
        )
        snapshot = MemorySnapshot(
            "e" * 40,
            (global_memory, project_memory, excluded_memory),
        )
        index = VexorIndex(tmp_path / "index")
        index.rebuild(snapshot)

        results = index.search(snapshot, "candidate", "vexor")

        request = server.rerank_requests[-1]
        documents = request["documents"]
        assert request["model"] == "perenna-test-reranker"
        assert request["query"] == "candidate"
        assert len(documents) == 2
        assert excluded_memory.body not in "\n".join(documents)
        assert results.matches[0].memory.body in documents[-1]


def test_real_vexor_remote_reranker_failure_is_wrapped(
    tmp_path: Path,
    monkeypatch,
) -> None:
    provider_detail = "private reranker provider detail"
    with EmbeddingServer(rerank_error=provider_detail) as server:
        environment = server.environment()
        config = json.loads(environment["VEXOR_CONFIG_JSON"])
        config.update(
            {
                "rerank": "remote",
                "remote_rerank": {
                    "base_url": server.base_url,
                    "model": "perenna-test-reranker",
                },
            }
        )
        environment["VEXOR_CONFIG_JSON"] = json.dumps(config)
        environment["VEXOR_REMOTE_RERANK_API_KEY"] = "offline-rerank-key"
        for name, value in environment.items():
            monkeypatch.setenv(name, value)

        memory = _memory(
            "01K00000000000000000000001",
            "global",
            "global/01K00000000000000000000001.md",
            "private candidate text",
        )
        snapshot = MemorySnapshot("d" * 40, (memory,))
        index = VexorIndex(tmp_path / "index")
        index.rebuild(snapshot)

        with pytest.raises(IndexUnavailableError, match="query failed") as exc_info:
            index.search(snapshot, "private query text", None)

        message = str(exc_info.value)
        assert server.rerank_requests
        assert "reranker configuration" in message
        assert provider_detail not in message
        assert "private query text" not in message
        assert memory.body not in message


def _memory(memory_id: str, scope: str, path: str, body: str) -> Memory:
    return Memory(
        id=memory_id,
        title=body.split()[0],
        summary=f"Memory about {body}.",
        created_at="2026-08-22T00:00:00.000000Z",
        updated_at="2026-08-22T00:00:00.000000Z",
        body=body,
        scope=scope,
        relative_path=path,
    )
