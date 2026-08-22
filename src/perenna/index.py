from __future__ import annotations

from collections.abc import Callable, Iterator, Mapping
from contextlib import contextmanager
from pathlib import Path
from typing import Any

from vexor import VexorClient

from perenna.errors import IndexUnavailableError
from perenna.filesystem import atomic_replace
from perenna.models import Memory, MemorySnapshot, WriteReceipt

COLLECTION_NAME = "perenna-memories"
MAX_RECALL_RESULTS = 5


class VexorIndex:
    def __init__(
        self,
        index_dir: Path,
        *,
        client_factory: Callable[..., Any] = VexorClient,
    ) -> None:
        self.index_dir = index_dir
        self.marker_path = index_dir / "indexed_commit"
        self._client_factory = client_factory

    def indexed_commit(self) -> str | None:
        try:
            value = self.marker_path.read_text(encoding="utf-8").strip()
        except (FileNotFoundError, OSError, UnicodeError):
            return None
        return value or None

    def is_current(self, snapshot: MemorySnapshot) -> bool:
        if snapshot.commit is None:
            return not snapshot.memories and self.indexed_commit() is None
        if self.indexed_commit() != snapshot.commit:
            return False
        if not snapshot.memories:
            return True
        try:
            with self._collection() as collection:
                return (
                    collection.info() is not None
                    and collection.count() == len(snapshot.memories)
                )
        except Exception as exc:
            raise _unavailable() from exc

    def rebuild(self, snapshot: MemorySnapshot) -> None:
        self.invalidate()
        try:
            with self._collection() as collection:
                collection.drop()
                if snapshot.memories:
                    collection.upsert_many([_record(memory) for memory in snapshot.memories])
        except Exception as exc:
            raise _unavailable() from exc
        if snapshot.commit is not None:
            self._write_marker(snapshot.commit)

    def synchronize_after_write(
        self,
        receipt: WriteReceipt,
        snapshot: MemorySnapshot,
    ) -> None:
        if snapshot.commit != receipt.commit:
            raise IndexUnavailableError(
                "Memory search index could not synchronize with the committed Git snapshot. "
                "Perenna will retry on the next recall."
            )
        expected_before = len(snapshot.memories) - (1 if receipt.operation == "add" else 0)
        can_increment = receipt.previous_commit is not None and self.indexed_commit() == (
            receipt.previous_commit
        )
        if can_increment:
            try:
                with self._collection() as collection:
                    can_increment = (
                        collection.info() is not None and collection.count() == expected_before
                    )
                    if can_increment:
                        collection.upsert_many([_record(receipt.memory)])
            except Exception as exc:
                raise _unavailable() from exc
        if not can_increment:
            self.rebuild(snapshot)
            return
        self._write_marker(receipt.commit)

    def search(
        self,
        snapshot: MemorySnapshot,
        query: str,
        project: str | None,
    ) -> list[Memory]:
        filters: Mapping[str, object] | None = None
        if project is not None:
            filters = {"scope": {"in": ["global", f"project:{project}"]}}
        try:
            with self._collection() as collection:
                results = collection.search(
                    query,
                    top_k=MAX_RECALL_RESULTS,
                    filters=filters,
                    rerank="off",
                )
        except Exception as exc:
            raise _unavailable() from exc

        memories_by_id = snapshot.by_id()
        recalled: list[Memory] = []
        for result in results[:MAX_RECALL_RESULTS]:
            memory = memories_by_id.get(str(result.id))
            metadata = result.metadata
            if (
                memory is None
                or not isinstance(metadata, Mapping)
                or metadata.get("scope") != memory.scope
                or metadata.get("path") != memory.relative_path
            ):
                raise IndexUnavailableError(
                    "Memory search index contains stale record metadata. Perenna will rebuild it "
                    "on the next recall."
                )
            recalled.append(memory)
        return recalled

    def invalidate(self) -> None:
        try:
            self.marker_path.unlink(missing_ok=True)
        except OSError as exc:
            raise _unavailable() from exc

    def _write_marker(self, commit: str) -> None:
        try:
            atomic_replace(self.marker_path, f"{commit}\n".encode())
        except OSError as exc:
            raise _unavailable() from exc

    @contextmanager
    def _collection(self) -> Iterator[Any]:
        self.index_dir.mkdir(parents=True, exist_ok=True)
        client = self._client_factory(cache_dir=self.index_dir)
        try:
            yield client.collection(COLLECTION_NAME)
        finally:
            close = getattr(client, "close", None)
            if close is not None:
                close()


def _record(memory: Memory) -> dict[str, object]:
    return {
        "id": memory.id,
        "text": f"{memory.title}\n\n{memory.body}",
        "metadata": {
            "scope": memory.scope,
            "path": memory.relative_path,
        },
    }


def _unavailable() -> IndexUnavailableError:
    return IndexUnavailableError(
        "Memory search index is unavailable. Perenna will retry recovery on the next recall. "
        "Check the Vexor provider configuration. To force a rebuild, stop every Perenna process "
        "using this home before deleting the local index directory."
    )
