from __future__ import annotations

from dataclasses import dataclass, replace
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest

from perenna.errors import IndexUnavailableError
from perenna.index import (
    COLLECTION_NAME,
    MAX_CHUNKS_PER_MEMORY,
    MAX_SEARCH_CANDIDATES,
    VexorIndex,
)
from perenna.markdown import memory_revision
from perenna.models import Memory, MemorySnapshot, MutationReceipt


@dataclass
class FakeCollection:
    records: dict[str, dict[str, Any]]
    exists: bool = False
    fail_drop: bool = False
    fail_upsert: bool = False

    def __post_init__(self) -> None:
        self.exists = bool(self.records) or self.exists
        self.upsert_batches: list[list[dict[str, Any]]] = []
        self.searches: list[dict[str, Any]] = []
        self.scores: dict[str, float] = {}

    def info(self) -> object | None:
        return object() if self.exists else None

    def count(self) -> int:
        return len(self.records)

    def drop(self) -> bool:
        if self.fail_drop:
            raise RuntimeError("local collection failed")
        existed = self.exists
        self.records.clear()
        self.exists = False
        return existed

    def upsert_many(self, records: list[dict[str, Any]]) -> None:
        if self.fail_upsert:
            raise RuntimeError("provider failed")
        self.exists = bool(records) or self.exists
        self.upsert_batches.append(records)
        for record in records:
            self.records[str(record["id"])] = record

    def search(self, query: str, **kwargs: Any) -> list[SimpleNamespace]:
        self.searches.append({"query": query, **kwargs})
        scopes = None
        filters = kwargs.get("filters")
        if filters is not None:
            scopes = set(filters["scope"]["in"])
        results = []
        for record in self.records.values():
            metadata = record["metadata"]
            if scopes is None or metadata["scope"] in scopes:
                results.append(
                    SimpleNamespace(
                        id=record["id"],
                        text=record["text"],
                        metadata=metadata,
                        score=self.scores.get(str(record["id"]), 1.0),
                    )
                )
        results.sort(key=lambda result: result.score, reverse=True)
        return results[: kwargs["top_k"]]


class FakeClient:
    def __init__(self, collection: FakeCollection, cache_dir: Path) -> None:
        self._collection = collection
        self.cache_dir = Path(cache_dir)
        self.closed = False

    def collection(self, name: str) -> FakeCollection:
        assert name == COLLECTION_NAME
        return self._collection

    def close(self) -> None:
        self.closed = True


class FakeClientFactory:
    def __init__(self, collection: FakeCollection) -> None:
        self.collection = collection
        self.cache_dirs: list[Path] = []

    def __call__(self, *, cache_dir: Path) -> FakeClient:
        self.cache_dirs.append(Path(cache_dir))
        return FakeClient(self.collection, Path(cache_dir))


def test_rebuild_creates_chunk_records_and_applies_project_filter(tmp_path: Path) -> None:
    collection = FakeCollection({})
    factory = FakeClientFactory(collection)
    index = VexorIndex(tmp_path / "index", client_factory=factory)
    global_memory = _memory("01K00000000000000000000001", "global", "global/a.md")
    project_memory = _memory(
        "01K00000000000000000000002",
        "project:vexor",
        "projects/vexor/b.md",
    )
    other_memory = _memory(
        "01K00000000000000000000003",
        "project:other",
        "projects/other/c.md",
    )
    snapshot = MemorySnapshot("a" * 40, (global_memory, project_memory, other_memory))

    index.rebuild(snapshot)

    assert index.indexed_commit() == snapshot.commit
    assert index.is_current(snapshot)
    assert factory.cache_dirs and set(factory.cache_dirs) == {tmp_path / "index"}
    global_record = collection.records[f"{global_memory.id}:0"]
    assert global_record["text"] == "Title\n\nWhat this memory covers.\n\nBody"
    assert global_record["metadata"] == {
        "memory_id": global_memory.id,
        "scope": "global",
        "path": "global/a.md",
        "revision": memory_revision(global_memory),
        "chunk_index": 0,
        "start_char": 0,
        "end_char": 4,
    }

    results = index.search(snapshot, "topic", "vexor", limit=5)

    assert [match.memory.id for match in results.matches] == [
        global_memory.id,
        project_memory.id,
    ]
    assert collection.searches[-1]["filters"] == {
        "scope": {"in": ["global", "project:vexor"]}
    }
    assert collection.searches[-1]["top_k"] == MAX_SEARCH_CANDIDATES
    assert "rerank" not in collection.searches[-1]


def test_long_memory_is_chunked_with_exact_overlapping_passages(tmp_path: Path) -> None:
    collection = FakeCollection({})
    index = VexorIndex(tmp_path, client_factory=FakeClientFactory(collection))
    memory = replace(
        _memory("01K00000000000000000000001", "global", "global/a.md"),
        body="x" * 2_500,
    )
    snapshot = MemorySnapshot("a" * 40, (memory,))

    index.rebuild(snapshot)

    assert list(collection.records) == [f"{memory.id}:{index}" for index in range(3)]
    assert collection.records[f"{memory.id}:0"]["metadata"]["start_char"] == 0
    assert collection.records[f"{memory.id}:1"]["metadata"]["start_char"] == 1_000
    assert collection.records[f"{memory.id}:2"]["metadata"]["end_char"] == 2_500
    assert index.is_current(snapshot)


def test_search_deduplicates_memories_and_honors_public_limit(tmp_path: Path) -> None:
    collection = FakeCollection({})
    index = VexorIndex(tmp_path, client_factory=FakeClientFactory(collection))
    first = replace(
        _memory("01K00000000000000000000001", "global", "global/a.md"),
        body="a" * 2_500,
    )
    second = _memory("01K00000000000000000000002", "global", "global/b.md")
    third = _memory("01K00000000000000000000003", "global", "global/c.md")
    snapshot = MemorySnapshot("b" * 40, (first, second, third))
    index.rebuild(snapshot)
    collection.scores.update(
        {
            f"{first.id}:0": 0.9,
            f"{first.id}:1": 0.8,
            f"{second.id}:0": 0.7,
            f"{third.id}:0": 0.6,
        }
    )

    results = index.search(snapshot, "topic", None, limit=2)

    assert [match.memory.id for match in results.matches] == [first.id, second.id]
    assert [match.rank for match in results.matches] == [1, 2]
    assert results.truncated


def test_search_aggregates_enough_chunks_to_rank_five_distinct_memories(
    tmp_path: Path,
) -> None:
    collection = FakeCollection({})
    index = VexorIndex(tmp_path, client_factory=FakeClientFactory(collection))
    long_memory = replace(
        _memory("01K00000000000000000000001", "global", "global/a.md"),
        body="a" * 20_000,
    )
    other_memories = tuple(
        _memory(
            f"01K0000000000000000000000{number}",
            "global",
            f"global/{number}.md",
        )
        for number in range(2, 6)
    )
    snapshot = MemorySnapshot("c" * 40, (long_memory, *other_memories))
    index.rebuild(snapshot)
    long_chunk_ids = [
        record_id for record_id in collection.records if record_id.startswith(long_memory.id)
    ]
    assert len(long_chunk_ids) == MAX_CHUNKS_PER_MEMORY
    collection.scores.update(
        {
            record_id: 1.0 - (chunk_index * 0.01)
            for chunk_index, record_id in enumerate(long_chunk_ids)
        }
    )
    collection.scores.update(
        {
            f"{memory.id}:0": 0.7 - (index * 0.01)
            for index, memory in enumerate(other_memories)
        }
    )

    results = index.search(snapshot, "topic", None, limit=5)

    assert [match.memory.id for match in results.matches] == [
        long_memory.id,
        *(memory.id for memory in other_memories),
    ]
    assert collection.searches[-1]["top_k"] == MAX_SEARCH_CANDIDATES
    assert MAX_SEARCH_CANDIDATES == MAX_CHUNKS_PER_MEMORY * 5
    assert not results.truncated


def test_search_has_no_relevance_threshold_and_enforces_character_budget(
    tmp_path: Path,
) -> None:
    collection = FakeCollection({})
    index = VexorIndex(tmp_path, client_factory=FakeClientFactory(collection))
    memories = tuple(
        replace(
            _memory(
                f"01K0000000000000000000000{number}",
                "global",
                f"global/{number}.md",
            ),
            body=str(number) * 1_200,
        )
        for number in range(1, 6)
    )
    snapshot = MemorySnapshot("c" * 40, memories)
    index.rebuild(snapshot)
    collection.scores.update(
        {f"{memory.id}:0": -0.1 * number for number, memory in enumerate(memories, start=1)}
    )

    results = index.search(snapshot, "unrelated", None, limit=5)

    assert len(results.matches) == 4
    assert memories[0].id in {match.memory.id for match in results.matches}
    assert sum(len(match.passages[0].text) for match in results.matches) == 4_800
    assert results.truncated


def test_stale_result_metadata_and_non_finite_scores_are_rejected(tmp_path: Path) -> None:
    collection = FakeCollection({})
    index = VexorIndex(tmp_path, client_factory=FakeClientFactory(collection))
    memory = _memory("01K00000000000000000000001", "global", "global/a.md")
    snapshot = MemorySnapshot("d" * 40, (memory,))
    index.rebuild(snapshot)
    record_id = f"{memory.id}:0"
    collection.records[record_id]["metadata"]["revision"] = "0" * 64

    with pytest.raises(IndexUnavailableError, match="stale record metadata"):
        index.search(snapshot, "topic", None)

    collection.records[record_id]["metadata"]["revision"] = memory_revision(memory)
    collection.scores[record_id] = "invalid"  # type: ignore[assignment]
    with pytest.raises(IndexUnavailableError, match="invalid score"):
        index.search(snapshot, "topic", None)

    collection.scores[record_id] = float("nan")
    with pytest.raises(IndexUnavailableError, match="non-finite"):
        index.search(snapshot, "topic", None)


def test_mutation_rebuilds_from_new_snapshot_and_deletion_removes_chunks(tmp_path: Path) -> None:
    collection = FakeCollection({})
    index = VexorIndex(tmp_path, client_factory=FakeClientFactory(collection))
    previous = replace(
        _memory("01K00000000000000000000001", "global", "global/a.md"),
        body="x" * 2_500,
    )
    old_snapshot = MemorySnapshot("e" * 40, (previous,))
    index.rebuild(old_snapshot)
    updated = replace(previous, body="Updated")
    update = MutationReceipt(
        updated,
        "replace",
        True,
        previous,
        old_snapshot.commit,
        "f" * 40,
    )

    index.synchronize_after_mutation(update, MemorySnapshot(update.commit, (updated,)))

    assert list(collection.records) == [f"{updated.id}:0"]
    assert collection.records[f"{updated.id}:0"]["text"].endswith("Updated")

    delete = MutationReceipt(
        updated,
        "delete",
        True,
        updated,
        update.commit,
        "1" * 40,
    )
    index.synchronize_after_mutation(delete, MemorySnapshot(delete.commit, ()))
    assert collection.records == {}
    assert index.indexed_commit() == delete.commit


def test_provider_failure_does_not_advance_marker_and_can_retry(tmp_path: Path) -> None:
    collection = FakeCollection({}, fail_upsert=True)
    index = VexorIndex(tmp_path, client_factory=FakeClientFactory(collection))
    snapshot = MemorySnapshot(
        "2" * 40,
        (_memory("01K00000000000000000000001", "global", "global/a.md"),),
    )

    with pytest.raises(IndexUnavailableError, match="rebuild failed") as exc_info:
        index.rebuild(snapshot)
    assert "committed memory is safe" in str(exc_info.value)
    assert "Vexor provider configuration" in str(exc_info.value)
    assert index.indexed_commit() is None

    collection.fail_upsert = False
    index.rebuild(snapshot)
    assert index.is_current(snapshot)


def test_sync_mismatch_and_search_provider_failure_are_wrapped(tmp_path: Path) -> None:
    collection = FakeCollection({})
    index = VexorIndex(tmp_path, client_factory=FakeClientFactory(collection))
    memory = _memory("01K00000000000000000000001", "global", "global/a.md")
    receipt = MutationReceipt(memory, "create", True, None, None, "7" * 40)

    with pytest.raises(IndexUnavailableError, match="could not synchronize"):
        index.synchronize_after_mutation(receipt, MemorySnapshot("8" * 40, (memory,)))

    snapshot = MemorySnapshot("9" * 40, (memory,))
    index.rebuild(snapshot)

    def fail_search(_query: str, **_kwargs: Any) -> None:
        raise RuntimeError("provider unavailable")

    collection.search = fail_search  # type: ignore[method-assign]
    with pytest.raises(IndexUnavailableError, match="query failed") as exc_info:
        index.search(snapshot, "query", None)
    assert "invalidated the index" in str(exc_info.value)
    assert "reranker configuration" in str(exc_info.value)


def test_empty_snapshots_and_invalid_limits_have_clear_behavior(tmp_path: Path) -> None:
    collection = FakeCollection({})
    index = VexorIndex(tmp_path, client_factory=FakeClientFactory(collection))

    assert index.is_current(MemorySnapshot(None, ()))
    committed_empty = MemorySnapshot("3" * 40, ())
    index.rebuild(committed_empty)
    assert index.is_current(committed_empty)
    with pytest.raises(ValueError, match="between 1 and 5"):
        index.search(committed_empty, "query", None, limit=0)


def test_collection_failures_and_marker_errors_are_wrapped(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    collection = FakeCollection({})
    index = VexorIndex(tmp_path, client_factory=FakeClientFactory(collection))
    snapshot = MemorySnapshot(
        "4" * 40,
        (_memory("01K00000000000000000000001", "global", "global/a.md"),),
    )
    index.rebuild(snapshot)

    def fail_info() -> None:
        raise RuntimeError("broken database")

    collection.info = fail_info  # type: ignore[method-assign]
    with pytest.raises(IndexUnavailableError, match="could not be inspected"):
        index.is_current(snapshot)

    def fail_replace(_path: Path, _data: bytes) -> None:
        raise PermissionError("denied")

    monkeypatch.setattr("perenna.index.atomic_replace", fail_replace)
    with pytest.raises(IndexUnavailableError, match="could not be updated") as exc_info:
        index.rebuild(MemorySnapshot("5" * 40, ()))
    assert "Vexor provider configuration" not in str(exc_info.value)


def test_local_collection_reset_failure_has_storage_recovery_guidance(tmp_path: Path) -> None:
    collection = FakeCollection({}, fail_drop=True)
    index = VexorIndex(tmp_path, client_factory=FakeClientFactory(collection))

    with pytest.raises(IndexUnavailableError, match="could not reset") as exc_info:
        index.rebuild(MemorySnapshot("6" * 40, ()))

    message = str(exc_info.value)
    assert "committed Git memory is safe" in message
    assert "local index directory" in message
    assert "Vexor provider configuration" not in message


def test_client_without_close_method_is_supported(tmp_path: Path) -> None:
    collection = FakeCollection({})

    class ClientWithoutClose:
        def __init__(self, *, cache_dir: Path) -> None:
            assert cache_dir == tmp_path

        def collection(self, name: str) -> FakeCollection:
            assert name == COLLECTION_NAME
            return collection

    index = VexorIndex(tmp_path, client_factory=ClientWithoutClose)
    index.rebuild(MemorySnapshot("6" * 40, ()))
    assert index.indexed_commit() == "6" * 40


def _memory(memory_id: str, scope: str, path: str) -> Memory:
    return Memory(
        id=memory_id,
        title="Title",
        summary="What this memory covers.",
        created_at="2026-08-22T00:00:00.000000Z",
        updated_at="2026-08-22T00:00:00.000000Z",
        body="Body",
        scope=scope,
        relative_path=path,
    )
