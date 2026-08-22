from __future__ import annotations

from collections.abc import Callable
from datetime import datetime
from pathlib import Path

from perenna.errors import MemoryIntegrityError, MemoryValidationError, RepositoryError
from perenna.filesystem import atomic_replace
from perenna.git import GitRepository
from perenna.markdown import parse_memory, serialize_memory
from perenna.models import (
    Memory,
    MemorySnapshot,
    WriteReceipt,
    format_timestamp,
    memory_path,
    new_ulid,
    next_update_time,
    normalize_body,
    normalize_project,
    normalize_source,
    normalize_title,
    scope_for_project,
    title_key,
    utc_now,
    validate_ulid,
)


class MemoryStore:
    def __init__(
        self,
        repository: GitRepository,
        *,
        clock: Callable[[], datetime] = utc_now,
        id_factory: Callable[[], str] = new_ulid,
    ) -> None:
        self.repository = repository
        self._clock = clock
        self._id_factory = id_factory

    def snapshot(self) -> MemorySnapshot:
        commit = self.repository.head()
        if commit is None:
            memories: tuple[Memory, ...] = ()
        else:
            memories = tuple(
                parse_memory(self.repository.read_at_commit(commit, path), path)
                for path in self.repository.memory_paths_at_commit(commit)
            )
        self._validate_integrity(memories)
        return MemorySnapshot(commit=commit, memories=memories)

    def write(self, *, title: str, body: str, source: str, project: str | None) -> WriteReceipt:
        normalized_title = _validated("title", normalize_title, title)
        normalized_body = _validated("body", normalize_body, body)
        normalized_source = _validated("source", normalize_source, source)
        normalized_project = (
            None if project is None else _validated("project", normalize_project, project)
        )
        scope = scope_for_project(normalized_project)

        self.repository.assert_clean()
        self.repository.current_branch()
        snapshot = self.snapshot()
        matching = [
            memory
            for memory in snapshot.memories
            if memory.scope == scope and title_key(memory.title) == title_key(normalized_title)
        ]
        if len(matching) > 1:
            raise MemoryIntegrityError(
                f"Scope {scope!r} contains more than one memory with this normalized title. "
                "Repair and commit the duplicate files before retrying."
            )

        instant = self._clock()
        if matching:
            previous = matching[0]
            memory_id = previous.id
            created_at = previous.created_at
            updated_at = format_timestamp(next_update_time(instant, previous.updated_at))
            relative_path = previous.relative_path
            operation = "update"
        else:
            memory_id = _validated("id", validate_ulid, self._id_factory())
            if any(memory.id == memory_id for memory in snapshot.memories):
                raise MemoryIntegrityError(
                    f"Generated memory ID {memory_id} already exists. No file was changed; retry."
                )
            created_at = format_timestamp(instant)
            updated_at = created_at
            relative_path = memory_path(memory_id, normalized_project)
            operation = "add"

        memory = Memory(
            id=memory_id,
            title=normalized_title,
            source=normalized_source,
            created_at=created_at,
            updated_at=updated_at,
            body=normalized_body,
            scope=scope,
            relative_path=relative_path,
        )
        target = self.repository.worktree_path(relative_path)
        if target.is_symlink() or target.is_junction():
            raise RepositoryError(
                f"Memory target {target} is a filesystem link. Replace it with a regular file "
                "before retrying."
            )
        old_bytes = target.read_bytes() if target.exists() else None
        committed = False

        try:
            atomic_replace(target, serialize_memory(memory).encode("utf-8"))
            self.repository.stage(relative_path)
            commit_message = _commit_message(operation, memory)
            commit = self.repository.commit(commit_message, relative_path)
            committed = True
        except Exception as exc:
            current_head = self.repository.head()
            if current_head != snapshot.commit:
                raise RepositoryError(
                    "The Git commit command failed after HEAD changed. Perenna did not alter the "
                    "new commit; inspect the memory repository before retrying."
                ) from exc
            try:
                _restore_target(target, old_bytes)
                self.repository.unstage(relative_path, snapshot.commit)
            except Exception as rollback_exc:
                raise RepositoryError(
                    f"Memory write failed and automatic rollback could not restore {target}. "
                    "Inspect the memory repository before continuing."
                ) from rollback_exc
            raise
        finally:
            if not committed:
                _remove_empty_memory_directories(target.parent, self.repository.path)

        return WriteReceipt(
            memory=memory,
            operation=operation,
            previous_commit=snapshot.commit,
            commit=commit,
        )

    @staticmethod
    def _validate_integrity(memories: tuple[Memory, ...]) -> None:
        ids: dict[str, str] = {}
        titles: dict[tuple[str, str], str] = {}
        for memory in memories:
            if memory.id in ids:
                raise MemoryIntegrityError(
                    f"Memory ID {memory.id} appears in both {ids[memory.id]!r} and "
                    f"{memory.relative_path!r}. Repair and commit one file before retrying."
                )
            ids[memory.id] = memory.relative_path
            key = (memory.scope, title_key(memory.title))
            if key in titles:
                raise MemoryIntegrityError(
                    f"Scope {memory.scope!r} has duplicate normalized titles in "
                    f"{titles[key]!r} and {memory.relative_path!r}. Repair and commit one file "
                    "before retrying."
                )
            titles[key] = memory.relative_path


def _validated(name: str, normalizer: Callable[[str], str], value: str) -> str:
    try:
        return normalizer(value)
    except (TypeError, ValueError) as exc:
        if name == "title":
            guidance = "Use a non-empty title of at most 120 characters."
        elif name == "body":
            guidance = "Use a non-empty body of at most 20,000 characters."
        elif name == "project":
            guidance = (
                "Use at most 64 lowercase letters, digits, dots, underscores, or hyphens; "
                "path traversal is not allowed."
            )
        elif name == "source":
            guidance = "Configure a 1-64 character source in the host process."
        else:
            guidance = "Retry the operation."
        raise MemoryValidationError(f"Memory {name} is invalid. {guidance}") from exc


def _restore_target(target: Path, old_bytes: bytes | None) -> None:
    if old_bytes is None:
        target.unlink(missing_ok=True)
    else:
        atomic_replace(target, old_bytes)


def _remove_empty_memory_directories(directory: Path, repository: Path) -> None:
    current = directory
    while current != repository:
        try:
            current.rmdir()
        except OSError:
            break
        current = current.parent


def _commit_message(operation: str, memory: Memory) -> str:
    scope = "global" if memory.project is None else memory.project
    safe_title = memory.title.replace('"', "'")
    return f'memory({scope}): {operation} "{safe_title}"'
