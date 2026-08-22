from __future__ import annotations

import logging
from pathlib import Path

from perenna.config import RuntimeSettings
from perenna.errors import ConfigurationError, IndexUnavailableError, MemoryValidationError
from perenna.git import GitRepository
from perenna.index import VexorIndex
from perenna.locking import RepositoryLocks
from perenna.models import Memory, normalize_project
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

    def list_index(self, *, project: str | None = None) -> str:
        normalized_project = _project(project)
        with self.locks.shared():
            snapshot = self.store.snapshot()
        global_titles = sorted(
            (memory.title for memory in snapshot.memories if memory.scope == "global"),
            key=str.casefold,
        )
        lines = ["Global memories:"]
        lines.extend(_title_lines(global_titles))

        if normalized_project is None:
            projects = sorted(
                {
                    memory.project
                    for memory in snapshot.memories
                    if memory.project is not None
                }
            )
            lines.extend(("", "Projects:"))
            lines.extend(_title_lines(projects))
            displayed_count = len(global_titles) + len(projects)
        else:
            project_titles = sorted(
                (
                    memory.title
                    for memory in snapshot.memories
                    if memory.scope == f"project:{normalized_project}"
                ),
                key=str.casefold,
            )
            lines.extend(("", f"Project: {normalized_project}"))
            lines.extend(_title_lines(project_titles))
            displayed_count = len(global_titles) + len(project_titles)

        logger.info(
            "action=query mode=index source=%s project=%s results=%d",
            self.settings.source,
            normalized_project or "all",
            displayed_count,
        )
        return "\n".join(lines)

    def recall(self, *, query: str, project: str | None = None) -> str:
        normalized_query = query.strip() if isinstance(query, str) else ""
        if not normalized_query:
            raise MemoryValidationError(
                "Memory query is empty. Omit query to read the lightweight memory index, or "
                "provide text to recall matching memories."
            )
        if "\x00" in normalized_query or any(
            0xD800 <= ord(character) <= 0xDFFF for character in normalized_query
        ):
            raise MemoryValidationError(
                "Memory query contains an unsupported control character. Provide plain text or "
                "omit query to read the lightweight memory index."
            )
        normalized_project = _project(project)

        while True:
            try:
                with self.locks.shared():
                    snapshot = self.store.snapshot()
                    if not snapshot.memories:
                        return "No permanent memories have been written yet."
                    if self.index.is_current(snapshot):
                        memories = self.index.search(snapshot, normalized_query, normalized_project)
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

        logger.info(
            "action=query mode=recall source=%s project=%s results=%d",
            self.settings.source,
            normalized_project or "all",
            len(memories),
        )
        return _format_recall(memories)

    def write(
        self,
        *,
        title: str,
        body: str,
        project: str | None = None,
    ) -> str:
        index_synchronized = True
        with self.locks.exclusive():
            receipt = self.store.write(
                title=title,
                body=body,
                source=self.settings.source,
                project=project,
            )
            snapshot = self.store.snapshot()
            try:
                self.index.synchronize_after_write(receipt, snapshot)
            except Exception as exc:
                index_synchronized = False
                logger.warning(
                    "action=write index=failed source=%s project=%s error_type=%s",
                    self.settings.source,
                    receipt.memory.project or "global",
                    type(exc).__name__,
                )

        logger.info(
            "action=write operation=%s source=%s project=%s commit=%s",
            receipt.operation,
            self.settings.source,
            receipt.memory.project or "global",
            receipt.commit[:12],
        )
        if self.settings.git_remote is not None:
            try:
                with self.locks.push():
                    outcome = self.repository.push(self.settings.git_remote)
            except Exception as exc:
                logger.warning("git_push=failed error_type=%s", type(exc).__name__)
            else:
                if outcome.attempted and not outcome.succeeded:
                    logger.warning("git_push=%s", outcome.reason)
                elif outcome.succeeded:
                    logger.info("git_push=succeeded")

        verb = "created" if receipt.operation == "add" else "updated"
        scope = "global" if receipt.memory.project is None else f"project:{receipt.memory.project}"
        result = f"Memory {verb} in {scope} and committed to Git."
        if not index_synchronized:
            result += " Retrieval indexing is pending and will be retried on the next recall."
        return result

    def _invalidate_failed_index(self) -> None:
        with self.locks.exclusive():
            self.index.invalidate()


def _ensure_directory(path: Path, label: str) -> None:
    if path.exists() and not path.is_dir():
        raise ConfigurationError(
            f"{label} path {path} is not a directory. Move that file or choose a different "
            "--home, then restart Perenna."
        )
    path.mkdir(parents=True, exist_ok=True)


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


def _title_lines(values: list[str] | list[str | None]) -> list[str]:
    strings = [value for value in values if value is not None]
    return [f"- {value}" for value in strings] if strings else ["- (none)"]


def _format_recall(memories: list[Memory]) -> str:
    if not memories:
        return "No matching permanent memories were found."
    blocks = []
    for memory in memories:
        label = "Global" if memory.project is None else f"Project: {memory.project}"
        blocks.append(
            "\n".join(
                (
                    f"[{label}]",
                    f"Title: {memory.title}",
                    f"Source: {memory.source}",
                    f"Updated: {memory.updated_at}",
                    "",
                    memory.body,
                )
            )
        )
    return "\n\n---\n\n".join(blocks)
