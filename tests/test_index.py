from __future__ import annotations

from dataclasses import dataclass, replace
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest

from perenna.errors import IndexUnavailableError
from perenna.index import COLLECTION_NAME, VexorIndex
from perenna.models import Memory, MemorySnapshot, WriteReceipt


@dataclass
class FakeCollection:
    records: dict[str, dict[str, Any]]
    exists: bool = False
    fail_upsert: bool = False
    upsert_batches: list[list[dict[str, Any]]] | None = None
    searches: list[dict[str, Any]] | None = None

    def __post_init__(self) -> None:
        self.upsert_batches = [] if self.upsert_batches is None else self.upsert_batches
        self.searches = [] if self.searches is None else self.searches

    def info(self) -> object | None:
        return object() if self.exists else None

    def count(self) -> int:
        return len(self.records) if self.exists else 0

    def drop(self) -> bool:
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
                        score=1.0,
                    )
                )
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


def test_rebuild_records_and_project_filter(tmp_path: Path) -> None:
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
    assert collection.records[global_memory.id]["text"] == "Title\n\nBody"
    assert collection.records[project_memory.id]["metadata"] == {
        "scope": "project:vexor",
        "path": "projects/vexor/b.md",
    }

    results = index.search(snapshot, "topic", "vexor")

    assert [memory.id for memory in results] == [global_memory.id, project_memory.id]
    assert collection.searches[-1]["filters"] == {
        "scope": {"in": ["global", "project:vexor"]}
    }
    assert collection.searches[-1]["top_k"] == 5


def test_incremental_update_upserts_one_record(tmp_path: Path) -> None:
    collection = FakeCollection({})
    index = VexorIndex(tmp_path, client_factory=FakeClientFactory(collection))
    previous = _memory("01K00000000000000000000001", "global", "global/a.md")
    old_snapshot = MemorySnapshot("a" * 40, (previous,))
    index.rebuild(old_snapshot)
    collection.upsert_batches.clear()
    updated = replace(
        previous,
        body="Updated",
        source="cursor",
        updated_at="2026-08-22T00:00:01.000000Z",
    )
    receipt = WriteReceipt(updated, "update", old_snapshot.commit, "b" * 40)
    new_snapshot = MemorySnapshot(receipt.commit, (updated,))

    index.synchronize_after_write(receipt, new_snapshot)

    assert len(collection.upsert_batches) == 1
    assert collection.upsert_batches[0][0]["text"] == "Title\n\nUpdated"
    assert index.indexed_commit() == receipt.commit


def test_missing_or_deleted_index_rebuilds(tmp_path: Path) -> None:
    collection = FakeCollection({})
    index_dir = tmp_path / "index"
    index = VexorIndex(index_dir, client_factory=FakeClientFactory(collection))
    snapshot = MemorySnapshot(
        "c" * 40,
        (_memory("01K00000000000000000000001", "global", "global/a.md"),),
    )
    index.rebuild(snapshot)
    assert index.is_current(snapshot)

    for child in list(index_dir.iterdir()):
        if child.is_file():
            child.unlink()
    assert not index.is_current(snapshot)

    index.rebuild(snapshot)
    assert index.is_current(snapshot)


def test_provider_failure_does_not_advance_marker_and_can_retry(tmp_path: Path) -> None:
    collection = FakeCollection({}, fail_upsert=True)
    index = VexorIndex(tmp_path, client_factory=FakeClientFactory(collection))
    snapshot = MemorySnapshot(
        "d" * 40,
        (_memory("01K00000000000000000000001", "global", "global/a.md"),),
    )

    with pytest.raises(IndexUnavailableError, match="retry recovery"):
        index.rebuild(snapshot)
    assert index.indexed_commit() is None

    collection.fail_upsert = False
    index.rebuild(snapshot)
    assert index.is_current(snapshot)


def test_stale_result_metadata_is_rejected(tmp_path: Path) -> None:
    collection = FakeCollection({})
    index = VexorIndex(tmp_path, client_factory=FakeClientFactory(collection))
    memory = _memory("01K00000000000000000000001", "global", "global/a.md")
    snapshot = MemorySnapshot("e" * 40, (memory,))
    index.rebuild(snapshot)
    collection.records[memory.id]["metadata"] = {
        "scope": "global",
        "path": "global/other.md",
    }

    with pytest.raises(IndexUnavailableError, match="stale record metadata"):
        index.search(snapshot, "topic", None)


def test_empty_repository_and_empty_committed_tree_are_current(tmp_path: Path) -> None:
    collection = FakeCollection({})
    index = VexorIndex(tmp_path, client_factory=FakeClientFactory(collection))

    assert index.is_current(MemorySnapshot(None, ()))
    committed_empty = MemorySnapshot("1" * 40, ())
    index.rebuild(committed_empty)
    assert index.is_current(committed_empty)
    assert collection.upsert_batches == []


def test_collection_inspection_failure_is_index_unavailable(tmp_path: Path) -> None:
    collection = FakeCollection({})
    index = VexorIndex(tmp_path, client_factory=FakeClientFactory(collection))
    snapshot = MemorySnapshot(
        "2" * 40,
        (_memory("01K00000000000000000000001", "global", "global/a.md"),),
    )
    index.rebuild(snapshot)

    def fail_info():
        raise RuntimeError("broken database")

    collection.info = fail_info  # type: ignore[method-assign]
    with pytest.raises(IndexUnavailableError, match="index is unavailable"):
        index.is_current(snapshot)


def test_sync_rejects_snapshot_that_does_not_match_receipt(tmp_path: Path) -> None:
    collection = FakeCollection({})
    index = VexorIndex(tmp_path, client_factory=FakeClientFactory(collection))
    memory = _memory("01K00000000000000000000001", "global", "global/a.md")
    receipt = WriteReceipt(memory, "add", None, "3" * 40)

    with pytest.raises(IndexUnavailableError, match="could not synchronize"):
        index.synchronize_after_write(receipt, MemorySnapshot("4" * 40, (memory,)))


def test_incremental_sync_rebuilds_when_collection_disappeared(tmp_path: Path) -> None:
    collection = FakeCollection({})
    index = VexorIndex(tmp_path, client_factory=FakeClientFactory(collection))
    previous = _memory("01K00000000000000000000001", "global", "global/a.md")
    old_snapshot = MemorySnapshot("5" * 40, (previous,))
    index.rebuild(old_snapshot)
    collection.exists = False
    updated = replace(previous, body="Updated")
    receipt = WriteReceipt(updated, "update", old_snapshot.commit, "6" * 40)

    index.synchronize_after_write(receipt, MemorySnapshot(receipt.commit, (updated,)))

    assert index.indexed_commit() == receipt.commit
    assert collection.exists
    assert collection.records[updated.id]["text"].endswith("Updated")


def test_incremental_and_search_provider_failures_are_wrapped(tmp_path: Path) -> None:
    collection = FakeCollection({})
    index = VexorIndex(tmp_path, client_factory=FakeClientFactory(collection))
    previous = _memory("01K00000000000000000000001", "global", "global/a.md")
    old_snapshot = MemorySnapshot("7" * 40, (previous,))
    index.rebuild(old_snapshot)
    updated = replace(previous, body="Updated")
    receipt = WriteReceipt(updated, "update", old_snapshot.commit, "0" * 40)
    collection.fail_upsert = True

    with pytest.raises(IndexUnavailableError, match="index is unavailable"):
        index.synchronize_after_write(receipt, MemorySnapshot(receipt.commit, (updated,)))
    assert index.indexed_commit() == old_snapshot.commit

    collection.fail_upsert = False

    def fail_search(_query: str, **_kwargs: Any):
        raise RuntimeError("provider unavailable")

    collection.search = fail_search  # type: ignore[method-assign]
    with pytest.raises(IndexUnavailableError, match="index is unavailable"):
        index.search(old_snapshot, "query", None)


def test_marker_write_errors_are_wrapped(tmp_path: Path, monkeypatch) -> None:
    index = VexorIndex(tmp_path, client_factory=FakeClientFactory(FakeCollection({})))

    def fail_replace(_path: Path, _data: bytes) -> None:
        raise PermissionError("denied")

    monkeypatch.setattr("perenna.index.atomic_replace", fail_replace)
    with pytest.raises(IndexUnavailableError, match="index is unavailable"):
        index.rebuild(MemorySnapshot("a" * 40, ()))


def test_client_without_close_method_is_supported(tmp_path: Path) -> None:
    collection = FakeCollection({})

    class ClientWithoutClose:
        def __init__(self, *, cache_dir: Path) -> None:
            assert cache_dir == tmp_path

        def collection(self, name: str) -> FakeCollection:
            assert name == COLLECTION_NAME
            return collection

    index = VexorIndex(tmp_path, client_factory=ClientWithoutClose)
    index.rebuild(MemorySnapshot("b" * 40, ()))
    assert index.indexed_commit() == "b" * 40


def _memory(memory_id: str, scope: str, path: str) -> Memory:
    return Memory(
        id=memory_id,
        title="Title",
        source="codex",
        created_at="2026-08-22T00:00:00.000000Z",
        updated_at="2026-08-22T00:00:00.000000Z",
        body="Body",
        scope=scope,
        relative_path=path,
    )
