from __future__ import annotations

import math
from collections.abc import Callable, Iterator, Mapping
from contextlib import contextmanager
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from vexor import VexorClient

from perenna.errors import IndexUnavailableError
from perenna.filesystem import atomic_replace
from perenna.markdown import memory_revision
from perenna.models import (
    Memory,
    MemorySnapshot,
    MutationReceipt,
    SearchMatch,
    SearchPassage,
    SearchResults,
)

COLLECTION_NAME = "perenna-memories"
CHUNK_CHARS = 1_200
CHUNK_OVERLAP_CHARS = 200
MAX_SEARCH_MATCHES = 5
DEFAULT_SEARCH_LIMIT = 3
MAX_SEARCH_CANDIDATES = 20
MAX_SEARCH_PASSAGE_CHARS_TOTAL = 4_800


@dataclass(frozen=True, slots=True)
class _Chunk:
    id: str
    memory: Memory
    revision: str
    index: int
    text: str
    start_char: int
    end_char: int


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
        expected_records = sum(len(_chunks(memory)) for memory in snapshot.memories)
        try:
            with self._collection() as collection:
                return collection.info() is not None and collection.count() == expected_records
        except Exception as exc:
            raise _unavailable() from exc

    def rebuild(self, snapshot: MemorySnapshot) -> None:
        self.invalidate()
        records = [_record(chunk) for memory in snapshot.memories for chunk in _chunks(memory)]
        try:
            with self._collection() as collection:
                collection.drop()
                if records:
                    collection.upsert_many(records)
        except Exception as exc:
            raise _unavailable() from exc
        if snapshot.commit is not None:
            self._write_marker(snapshot.commit)

    def synchronize_after_mutation(
        self,
        receipt: MutationReceipt,
        snapshot: MemorySnapshot,
    ) -> None:
        if snapshot.commit != receipt.commit:
            raise IndexUnavailableError(
                "Memory search index could not synchronize with the committed Git snapshot. "
                "Perenna will retry on the next search."
            )
        self.rebuild(snapshot)

    def search(
        self,
        snapshot: MemorySnapshot,
        query: str,
        project: str | None,
        limit: int = DEFAULT_SEARCH_LIMIT,
    ) -> SearchResults:
        if not 1 <= limit <= MAX_SEARCH_MATCHES:
            raise ValueError(f"limit must be between 1 and {MAX_SEARCH_MATCHES}")
        filters: Mapping[str, object] | None = None
        if project is not None:
            filters = {"scope": {"in": ["global", f"project:{project}"]}}
        try:
            with self._collection() as collection:
                results = collection.search(
                    query,
                    top_k=MAX_SEARCH_CANDIDATES,
                    filters=filters,
                    rerank="off",
                )
        except Exception as exc:
            raise _unavailable() from exc

        chunks_by_id = {
            chunk.id: chunk for memory in snapshot.memories for chunk in _chunks(memory)
        }
        matches: list[SearchMatch] = []
        seen_memories: set[str] = set()
        passage_chars = 0
        truncated = len(results) >= MAX_SEARCH_CANDIDATES
        for result in results[:MAX_SEARCH_CANDIDATES]:
            chunk = chunks_by_id.get(str(result.id))
            metadata = result.metadata
            try:
                score = float(result.score)
            except (TypeError, ValueError) as exc:
                raise IndexUnavailableError(
                    "Memory search index returned an invalid score. Perenna will rebuild it on "
                    "the next search."
                ) from exc
            if not math.isfinite(score):
                raise IndexUnavailableError(
                    "Memory search index returned a non-finite score. Perenna will rebuild it "
                    "on the next search."
                )
            if chunk is None or not isinstance(metadata, Mapping) or not _metadata_matches(
                chunk, metadata
            ):
                raise IndexUnavailableError(
                    "Memory search index contains stale record metadata. Perenna will rebuild it "
                    "on the next search."
                )
            if chunk.memory.id in seen_memories:
                continue
            if len(matches) >= limit:
                truncated = True
                continue
            if passage_chars + len(chunk.text) > MAX_SEARCH_PASSAGE_CHARS_TOTAL:
                truncated = True
                break
            seen_memories.add(chunk.memory.id)
            passage_chars += len(chunk.text)
            matches.append(
                SearchMatch(
                    memory=chunk.memory,
                    revision=chunk.revision,
                    rank=len(matches) + 1,
                    passages=(
                        SearchPassage(
                            text=chunk.text,
                            start_char=chunk.start_char,
                            end_char=chunk.end_char,
                        ),
                    ),
                )
            )
        return SearchResults(matches=tuple(matches), truncated=truncated)

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


def _chunks(memory: Memory) -> tuple[_Chunk, ...]:
    revision = memory_revision(memory)
    chunks: list[_Chunk] = []
    start = 0
    index = 0
    while start < len(memory.body):
        end = min(start + CHUNK_CHARS, len(memory.body))
        chunks.append(
            _Chunk(
                id=f"{memory.id}:{index}",
                memory=memory,
                revision=revision,
                index=index,
                text=memory.body[start:end],
                start_char=start,
                end_char=end,
            )
        )
        if end == len(memory.body):
            break
        start = end - CHUNK_OVERLAP_CHARS
        index += 1
    return tuple(chunks)


def _record(chunk: _Chunk) -> dict[str, object]:
    return {
        "id": chunk.id,
        "text": f"{chunk.memory.title}\n\n{chunk.memory.summary}\n\n{chunk.text}",
        "metadata": {
            "memory_id": chunk.memory.id,
            "scope": chunk.memory.scope,
            "path": chunk.memory.relative_path,
            "revision": chunk.revision,
            "chunk_index": chunk.index,
            "start_char": chunk.start_char,
            "end_char": chunk.end_char,
        },
    }


def _metadata_matches(chunk: _Chunk, metadata: Mapping[str, object]) -> bool:
    return metadata == {
        "memory_id": chunk.memory.id,
        "scope": chunk.memory.scope,
        "path": chunk.memory.relative_path,
        "revision": chunk.revision,
        "chunk_index": chunk.index,
        "start_char": chunk.start_char,
        "end_char": chunk.end_char,
    }


def _unavailable() -> IndexUnavailableError:
    return IndexUnavailableError(
        "Memory search index is unavailable. Perenna will retry recovery on the next search. "
        "Check the Vexor provider configuration. To force a rebuild, stop every Perenna process "
        "using this home before deleting the local index directory."
    )
