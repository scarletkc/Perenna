from __future__ import annotations

import logging
from collections.abc import Callable, Sequence
from pathlib import Path
from typing import Any

from perenna.config import RuntimeSettings
from perenna.errors import (
    ConfigurationError,
    IndexUnavailableError,
    MemoryNotFoundError,
    MemoryValidationError,
)
from perenna.git import GitRepository
from perenna.index import DEFAULT_SEARCH_LIMIT, MAX_SEARCH_MATCHES, VexorIndex
from perenna.locking import RepositoryLocks
from perenna.markdown import memory_revision
from perenna.models import Memory, MutationReceipt, PatchEdit, normalize_project, validate_ulid
from perenna.store import MemoryStore

logger = logging.getLogger(__name__)


class PerennaCore:
    def __init__(
        self,
        settings: RuntimeSettings,
        *,
        repository: GitRepository | None = None,
        store: MemoryStore | None = None,
        index: VexorIndex | None = None,
        locks: RepositoryLocks | None = None,
    ) -> None:
        _ensure_directory(settings.paths.home, "Perenna home")
        _ensure_directory(settings.paths.index, "Perenna index")
        self.settings = settings
        self.locks = locks or RepositoryLocks(settings.paths.index)
        if repository is None:
            with self.locks.exclusive():
                self.repository = GitRepository.initialize(settings.paths.memory)
        else:
            self.repository = repository
        self.store = store or MemoryStore(self.repository)
        self.index = index or VexorIndex(settings.paths.index)

    def list_memories(self, *, project: str | None = None) -> dict[str, Any]:
        normalized_project = _project(project)
        with self.locks.shared():
            snapshot = self.store.snapshot()
        if normalized_project is None:
            selected = [memory for memory in snapshot.memories if memory.scope == "global"]
            projects = sorted(
                {
                    memory.project
                    for memory in snapshot.memories
                    if memory.project is not None
                }
            )
        else:
            allowed = {"global", f"project:{normalized_project}"}
            selected = [memory for memory in snapshot.memories if memory.scope in allowed]
            projects = []
        memories = [_memory_ref(memory) for memory in sorted(selected, key=_memory_sort_key)]
        logger.info(
            "tool=memory_read action=list source=%s project=%s results=%d",
            self.settings.source,
            normalized_project or "all",
            len(memories),
        )
        return {
            "action": "list",
            "project": normalized_project,
            "memories": memories,
            "projects": projects,
        }

    def search(
        self,
        *,
        query: str,
        project: str | None = None,
        limit: int = DEFAULT_SEARCH_LIMIT,
    ) -> dict[str, Any]:
        normalized_query = _query(query)
        normalized_project = _project(project)
        normalized_limit = _limit(limit)

        while True:
            try:
                with self.locks.shared():
                    snapshot = self.store.snapshot()
                    if not snapshot.memories:
                        results = None
                        break
                    if self.index.is_current(snapshot):
                        results = self.index.search(
                            snapshot,
                            normalized_query,
                            normalized_project,
                            normalized_limit,
                        )
                        break
            except IndexUnavailableError:
                self._invalidate_failed_index()
                raise

            with self.locks.exclusive():
                snapshot = self.store.snapshot()
                try:
                    current = self.index.is_current(snapshot)
                except IndexUnavailableError:
                    current = False
                    self.index.invalidate()
                if not current:
                    self.index.rebuild(snapshot)

        matches = [] if results is None else [_match_payload(match) for match in results.matches]
        truncated = False if results is None else results.truncated
        logger.info(
            "tool=memory_read action=search source=%s project=%s results=%d",
            self.settings.source,
            normalized_project or "all",
            len(matches),
        )
        return {
            "action": "search",
            "project": normalized_project,
            "limit": normalized_limit,
            "matches": matches,
            "truncated": truncated,
        }

    def get(self, *, memory_id: str) -> dict[str, Any]:
        normalized_id = _memory_id(memory_id)
        with self.locks.shared():
            snapshot = self.store.snapshot()
            memory = snapshot.by_id().get(normalized_id)
        if memory is None:
            raise MemoryNotFoundError(
                f"Memory {normalized_id} was not found in the committed snapshot. List or search "
                "memories again, then retry with a current memory ID."
            )
        logger.info(
            "tool=memory_read action=get source=%s project=%s results=1",
            self.settings.source,
            memory.project or "global",
        )
        return {"action": "get", "memory": _memory_payload(memory)}

    def create(
        self,
        *,
        title: str,
        summary: str,
        body: str,
        project: str | None = None,
    ) -> dict[str, Any]:
        return self._mutate(
            lambda: self.store.create(
                title=title,
                summary=summary,
                body=body,
                source=self.settings.source,
                project=project,
            )
        )

    def patch(
        self,
        *,
        memory_id: str,
        base_revision: str,
        edits: Sequence[PatchEdit],
        summary: str | None = None,
    ) -> dict[str, Any]:
        return self._mutate(
            lambda: self.store.patch(
                memory_id=memory_id,
                base_revision=base_revision,
                edits=edits,
                source=self.settings.source,
                summary=summary,
            )
        )

    def replace(
        self,
        *,
        memory_id: str,
        base_revision: str,
        summary: str,
        body: str,
    ) -> dict[str, Any]:
        return self._mutate(
            lambda: self.store.replace(
                memory_id=memory_id,
                base_revision=base_revision,
                summary=summary,
                body=body,
                source=self.settings.source,
            )
        )

    def delete(
        self,
        *,
        memory_id: str,
        expected_title: str,
        base_revision: str,
    ) -> dict[str, Any]:
        return self._mutate(
            lambda: self.store.delete(
                memory_id=memory_id,
                expected_title=expected_title,
                base_revision=base_revision,
            )
        )

    def _mutate(self, operation: Callable[[], MutationReceipt]) -> dict[str, Any]:
        index_status = "current"
        with self.locks.exclusive():
            receipt = operation()
            snapshot = self.store.snapshot()
            if receipt.changed:
                try:
                    self.index.synchronize_after_mutation(receipt, snapshot)
                except Exception as exc:
                    index_status = "pending"
                    logger.warning(
                        "memory_index=failed operation=%s source=%s project=%s error_type=%s",
                        receipt.operation,
                        self.settings.source,
                        receipt.memory.project or "global",
                        type(exc).__name__,
                    )
            else:
                try:
                    if not self.index.is_current(snapshot):
                        index_status = "pending"
                except Exception:
                    index_status = "pending"

        logger.info(
            "tool=%s action=%s changed=%s source=%s project=%s commit=%s",
            "memory_delete" if receipt.operation == "delete" else "memory_write",
            receipt.operation,
            str(receipt.changed).lower(),
            self.settings.source,
            receipt.memory.project or "global",
            receipt.commit[:12],
        )
        if receipt.changed:
            self._push_best_effort()
        return _mutation_payload(receipt, index_status)

    def _push_best_effort(self) -> None:
        if self.settings.git_remote is None:
            return
        try:
            with self.locks.push():
                outcome = self.repository.push(self.settings.git_remote)
        except Exception as exc:
            logger.warning("git_push=failed error_type=%s", type(exc).__name__)
            return
        if outcome.attempted and not outcome.succeeded:
            logger.warning("git_push=%s", outcome.reason)
        elif outcome.succeeded:
            logger.info("git_push=succeeded")

    def _invalidate_failed_index(self) -> None:
        with self.locks.exclusive():
            self.index.invalidate()


def _memory_ref(memory: Memory) -> dict[str, str]:
    return {
        "memory_id": memory.id,
        "title": memory.title,
        "scope": memory.scope,
        "summary": memory.summary,
    }


def _memory_payload(memory: Memory) -> dict[str, str]:
    return {
        **_memory_ref(memory),
        "source": memory.source,
        "created_at": memory.created_at,
        "updated_at": memory.updated_at,
        "revision": memory_revision(memory),
        "body": memory.body,
    }


def _match_payload(match: Any) -> dict[str, Any]:
    return {
        **_memory_ref(match.memory),
        "revision": match.revision,
        "rank": match.rank,
        "passages": [
            {
                "text": passage.text,
                "start_char": passage.start_char,
                "end_char": passage.end_char,
            }
            for passage in match.passages
        ],
    }


def _mutation_payload(receipt: MutationReceipt, index_status: str) -> dict[str, Any]:
    memory = _memory_ref(receipt.memory)
    if receipt.operation != "delete":
        memory["revision"] = memory_revision(receipt.memory)
    payload: dict[str, Any] = {
        "action": receipt.operation,
        "changed": receipt.changed,
        "memory": memory,
        "commit": receipt.commit,
        "index_status": index_status,
    }
    if receipt.operation == "delete":
        payload["recoverable_via_git"] = True
    return payload


def _memory_sort_key(memory: Memory) -> tuple[str, str]:
    return memory.scope, memory.title.casefold()


def _query(value: str) -> str:
    normalized = value.strip() if isinstance(value, str) else ""
    if not normalized:
        raise MemoryValidationError("Memory search query is empty. Provide non-empty search text.")
    if "\x00" in normalized or any(
        0xD800 <= ord(character) <= 0xDFFF for character in normalized
    ):
        raise MemoryValidationError(
            "Memory search query contains an unsupported control character. Provide plain text."
        )
    return normalized


def _memory_id(value: str) -> str:
    try:
        return validate_ulid(value)
    except (TypeError, ValueError) as exc:
        raise MemoryValidationError(
            "Memory ID is invalid. List or search memories and use a returned memory_id."
        ) from exc


def _limit(value: int) -> int:
    if isinstance(value, bool) or not isinstance(value, int):
        raise MemoryValidationError(
            f"Memory search limit is invalid. Use an integer from 1 to {MAX_SEARCH_MATCHES}."
        )
    if not 1 <= value <= MAX_SEARCH_MATCHES:
        raise MemoryValidationError(
            f"Memory search limit is invalid. Use an integer from 1 to {MAX_SEARCH_MATCHES}."
        )
    return value


def _project(project: str | None) -> str | None:
    if project is None:
        return None
    try:
        return normalize_project(project)
    except (TypeError, ValueError) as exc:
        raise MemoryValidationError(
            "Memory project is invalid. Use at most 64 lowercase letters, digits, dots, "
            "underscores, or hyphens; path traversal is not allowed."
        ) from exc


def _ensure_directory(path: Path, label: str) -> None:
    if path.exists() and not path.is_dir():
        raise ConfigurationError(
            f"{label} path {path} is not a directory. Move that file or choose a different "
            "--home, then restart Perenna."
        )
    path.mkdir(parents=True, exist_ok=True)
