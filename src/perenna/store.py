from __future__ import annotations

import unicodedata
from collections.abc import Callable, Sequence
from datetime import datetime
from pathlib import Path

from perenna.errors import (
    MemoryConflictError,
    MemoryIntegrityError,
    MemoryNotFoundError,
    MemoryValidationError,
    RepositoryError,
)
from perenna.filesystem import atomic_replace
from perenna.git import GitRepository
from perenna.markdown import memory_revision, parse_memory, serialize_memory
from perenna.models import (
    Memory,
    MemorySnapshot,
    MutationReceipt,
    PatchEdit,
    format_timestamp,
    memory_path,
    new_ulid,
    next_update_time,
    normalize_body,
    normalize_project,
    normalize_summary,
    normalize_title,
    scope_for_project,
    title_key,
    utc_now,
    validate_revision,
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
        self._cached_snapshot: MemorySnapshot | None = None

    def snapshot(self) -> MemorySnapshot:
        commit = self.repository.head()
        cached_snapshot = self._cached_snapshot
        if cached_snapshot is not None and cached_snapshot.commit == commit:
            return cached_snapshot
        if commit is None:
            memories: tuple[Memory, ...] = ()
        else:
            memories = tuple(
                parse_memory(self.repository.read_at_commit(commit, path), path)
                for path in self.repository.memory_paths_at_commit(commit)
            )
        self._validate_integrity(memories)
        snapshot = MemorySnapshot(commit=commit, memories=memories)
        self._cached_snapshot = snapshot
        return snapshot

    def create(
        self,
        *,
        title: str,
        summary: str,
        body: str,
        project: str | None,
    ) -> MutationReceipt:
        normalized_title = _validated("title", normalize_title, title)
        normalized_summary = _validated("summary", normalize_summary, summary)
        normalized_body = _validated("body", normalize_body, body)
        normalized_project = (
            None if project is None else _validated("project", normalize_project, project)
        )
        scope = scope_for_project(normalized_project)

        snapshot = self._writable_snapshot()
        matching = [
            memory
            for memory in snapshot.memories
            if memory.scope == scope and title_key(memory.title) == title_key(normalized_title)
        ]
        if matching:
            existing = matching[0]
            if existing.summary == normalized_summary and existing.body == normalized_body:
                return _unchanged_receipt("create", existing, snapshot)
            raise MemoryConflictError(
                f"Memory {existing.id} already uses this title in {scope}. Read it and use patch "
                "or replace instead; no file was changed."
            )

        memory_id = _validated("id", validate_ulid, self._id_factory())
        if any(memory.id == memory_id for memory in snapshot.memories):
            raise MemoryIntegrityError(
                f"Generated memory ID {memory_id} already exists. No file was changed; retry."
            )
        instant = self._clock()
        created_at = format_timestamp(instant)
        memory = Memory(
            id=memory_id,
            title=normalized_title,
            summary=normalized_summary,
            created_at=created_at,
            updated_at=created_at,
            body=normalized_body,
            scope=scope,
            relative_path=memory_path(memory_id, normalized_project),
        )
        return self._commit_memory(memory, previous=None, snapshot=snapshot, operation="create")

    def patch(
        self,
        *,
        memory_id: str,
        base_revision: str,
        edits: Sequence[PatchEdit],
        summary: str | None = None,
    ) -> MutationReceipt:
        normalized_id = _validated("id", validate_ulid, memory_id)
        normalized_revision = _validated("revision", validate_revision, base_revision)
        normalized_summary = (
            None if summary is None else _validated("summary", normalize_summary, summary)
        )
        normalized_edits = _validated_edits(edits)

        snapshot = self._writable_snapshot()
        previous = _memory_by_id(snapshot, normalized_id)
        _require_revision(previous, normalized_revision)
        body = _apply_edits(previous.body, normalized_edits)
        next_summary = previous.summary if normalized_summary is None else normalized_summary
        if body == previous.body and next_summary == previous.summary:
            return _unchanged_receipt("patch", previous, snapshot)
        memory = self._updated_memory(
            previous,
            summary=next_summary,
            body=body,
        )
        return self._commit_memory(memory, previous=previous, snapshot=snapshot, operation="patch")

    def replace(
        self,
        *,
        memory_id: str,
        base_revision: str,
        summary: str,
        body: str,
    ) -> MutationReceipt:
        normalized_id = _validated("id", validate_ulid, memory_id)
        normalized_revision = _validated("revision", validate_revision, base_revision)
        normalized_summary = _validated("summary", normalize_summary, summary)
        normalized_body = _validated("body", normalize_body, body)

        snapshot = self._writable_snapshot()
        previous = _memory_by_id(snapshot, normalized_id)
        _require_revision(previous, normalized_revision)
        if normalized_summary == previous.summary and normalized_body == previous.body:
            return _unchanged_receipt("replace", previous, snapshot)
        memory = self._updated_memory(
            previous,
            summary=normalized_summary,
            body=normalized_body,
        )
        return self._commit_memory(
            memory,
            previous=previous,
            snapshot=snapshot,
            operation="replace",
        )

    def delete(
        self,
        *,
        memory_id: str,
        expected_title: str,
        base_revision: str,
    ) -> MutationReceipt:
        normalized_id = _validated("id", validate_ulid, memory_id)
        normalized_title = _validated("title", normalize_title, expected_title)
        normalized_revision = _validated("revision", validate_revision, base_revision)

        snapshot = self._writable_snapshot()
        previous = _memory_by_id(snapshot, normalized_id)
        if previous.title != normalized_title:
            raise MemoryConflictError(
                f"Memory {normalized_id} is titled {previous.title!r}, not {normalized_title!r}. "
                "Read the memory again and confirm the intended deletion; no file was changed."
            )
        _require_revision(previous, normalized_revision)
        commit = self._commit_target(
            previous.relative_path,
            new_bytes=None,
            snapshot=snapshot,
            operation="delete",
            memory=previous,
        )
        return MutationReceipt(
            memory=previous,
            operation="delete",
            changed=True,
            previous_memory=previous,
            previous_commit=snapshot.commit,
            commit=commit,
        )

    def _writable_snapshot(self) -> MemorySnapshot:
        self.repository.assert_clean()
        self.repository.current_branch()
        return self.snapshot()

    def _updated_memory(
        self,
        previous: Memory,
        *,
        summary: str,
        body: str,
    ) -> Memory:
        return Memory(
            id=previous.id,
            title=previous.title,
            summary=summary,
            created_at=previous.created_at,
            updated_at=format_timestamp(next_update_time(self._clock(), previous.updated_at)),
            body=body,
            scope=previous.scope,
            relative_path=previous.relative_path,
        )

    def _commit_memory(
        self,
        memory: Memory,
        *,
        previous: Memory | None,
        snapshot: MemorySnapshot,
        operation: str,
    ) -> MutationReceipt:
        commit = self._commit_target(
            memory.relative_path,
            new_bytes=serialize_memory(memory).encode("utf-8"),
            snapshot=snapshot,
            operation=operation,
            memory=memory,
        )
        return MutationReceipt(
            memory=memory,
            operation=operation,
            changed=True,
            previous_memory=previous,
            previous_commit=snapshot.commit,
            commit=commit,
        )

    def _commit_target(
        self,
        relative_path: str,
        *,
        new_bytes: bytes | None,
        snapshot: MemorySnapshot,
        operation: str,
        memory: Memory,
    ) -> str:
        target = self.repository.worktree_path(relative_path)
        if target.is_symlink() or target.is_junction():
            raise RepositoryError(
                f"Memory target {target} is a filesystem link. Replace it with a regular file "
                "before retrying."
            )
        old_bytes = target.read_bytes() if target.exists() else None
        committed = False

        try:
            if new_bytes is None:
                if old_bytes is None:
                    raise RepositoryError(
                        f"Committed memory target {target} is missing from the worktree. Restore "
                        "the clean Git checkout before retrying."
                    )
                target.unlink()
            else:
                atomic_replace(target, new_bytes)
            self.repository.stage(relative_path)
            commit = self.repository.commit(_commit_message(operation, memory), relative_path)
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
                    f"Memory {operation} failed and automatic rollback could not restore "
                    f"{target}. Inspect the memory repository before continuing."
                ) from rollback_exc
            raise
        finally:
            if (new_bytes is None and committed) or (old_bytes is None and not committed):
                _remove_empty_memory_directories(target.parent, self.repository.path)
        return commit

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


def _memory_by_id(snapshot: MemorySnapshot, memory_id: str) -> Memory:
    memory = snapshot.by_id().get(memory_id)
    if memory is None:
        raise MemoryNotFoundError(
            f"Memory {memory_id} was not found in the committed snapshot. List or search "
            "memories again, then retry with a current memory ID."
        )
    return memory


def _require_revision(memory: Memory, base_revision: str) -> None:
    if memory_revision(memory) != base_revision:
        raise MemoryConflictError(
            f"Memory {memory.id} changed after it was read. Get the current memory and retry "
            "with its revision; no file was changed."
        )


def _unchanged_receipt(
    operation: str,
    memory: Memory,
    snapshot: MemorySnapshot,
) -> MutationReceipt:
    if snapshot.commit is None:
        raise MemoryIntegrityError("A committed memory exists without a readable Git HEAD.")
    return MutationReceipt(
        memory=memory,
        operation=operation,
        changed=False,
        previous_memory=memory,
        previous_commit=snapshot.commit,
        commit=snapshot.commit,
    )


def _validated_edits(edits: Sequence[PatchEdit]) -> tuple[PatchEdit, ...]:
    if isinstance(edits, (str, bytes)) or not isinstance(edits, Sequence) or not edits:
        raise MemoryValidationError("Memory patch is invalid. Provide at least one exact edit.")
    normalized: list[PatchEdit] = []
    for edit in edits:
        if not isinstance(edit, PatchEdit):
            raise MemoryValidationError(
                "Memory patch is invalid. Each edit requires old_text and new_text strings."
            )
        old_text = _patch_text(edit.old_text, allow_empty=False)
        new_text = _patch_text(edit.new_text, allow_empty=True)
        normalized.append(PatchEdit(old_text=old_text, new_text=new_text))
    return tuple(normalized)


def _patch_text(value: str, *, allow_empty: bool) -> str:
    if not isinstance(value, str):
        raise MemoryValidationError("Memory patch text is invalid. Use plain text strings.")
    normalized = value.replace("\r\n", "\n").replace("\r", "\n")
    if not allow_empty and not normalized:
        raise MemoryValidationError(
            "Memory patch old_text is empty. Use an exact non-empty anchor."
        )
    if any(
        unicodedata.category(character) == "Cs"
        or (unicodedata.category(character) == "Cc" and character not in {"\n", "\t"})
        for character in normalized
    ):
        raise MemoryValidationError(
            "Memory patch text contains an unsupported control character. Use plain text."
        )
    return normalized


def _apply_edits(body: str, edits: Sequence[PatchEdit]) -> str:
    located: list[tuple[int, int, str]] = []
    for edit in edits:
        start = body.find(edit.old_text)
        if start < 0:
            raise MemoryConflictError(
                "Memory patch could not find one of its exact old_text anchors. Get the current "
                "memory and retry; no edit was applied."
            )
        if body.find(edit.old_text, start + 1) >= 0:
            raise MemoryConflictError(
                "Memory patch found an old_text anchor more than once. Include more surrounding "
                "text so every edit is unique; no edit was applied."
            )
        located.append((start, start + len(edit.old_text), edit.new_text))

    ordered = sorted(located, key=lambda item: item[0])
    for previous, current in zip(ordered, ordered[1:], strict=False):
        if current[0] < previous[1]:
            raise MemoryConflictError(
                "Memory patch edits overlap in the base body. Submit non-overlapping edits; no "
                "edit was applied."
            )

    result = body
    for start, end, replacement in reversed(ordered):
        result = result[:start] + replacement + result[end:]
    normalized = _validated("body", normalize_body, result)
    if normalized != result:
        raise MemoryValidationError(
            "Memory patch result is not canonical. Keep content within the existing body "
            "boundaries instead of adding leading or trailing newlines."
        )
    return normalized


def _validated(name: str, normalizer: Callable[[str], str], value: str) -> str:
    try:
        return normalizer(value)
    except (TypeError, ValueError) as exc:
        if name == "title":
            guidance = "Use a non-empty title of at most 120 characters."
        elif name == "summary":
            guidance = "Use one non-empty plain-text line of at most 300 characters."
        elif name == "body":
            guidance = "Use a non-empty body of at most 20,000 characters."
        elif name == "project":
            guidance = (
                "Use at most 64 lowercase letters, digits, dots, underscores, or hyphens; "
                "path traversal is not allowed."
            )
        elif name == "revision":
            guidance = "Get the memory again and use its current revision."
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
