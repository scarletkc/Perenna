import shutil
from pathlib import Path

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
