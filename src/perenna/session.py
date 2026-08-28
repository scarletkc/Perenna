"""Session working-memory branches.

A session is a Git branch named ``session/<slug>`` in the memory repository.
It gives one Project / Chat / Agent a private place to draft working memory
without touching the base branch (normally ``main``). Promotion replays only
the memory-level changes under ``global/`` and ``projects/`` as normal Perenna
mutations: it never performs a Git merge, rebase, or force-push.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Any

from perenna.errors import (
    ConfigurationError,
    MemoryConflictError,
    MemoryNotFoundError,
    MemoryValidationError,
    RepositoryError,
)
from perenna.git import GitRepository
from perenna.markdown import parse_memory
from perenna.models import Memory, normalize_project

if TYPE_CHECKING:
    from perenna.core import PerennaCore

SESSION_BRANCH_PREFIX = "session/"
MEMORY_TREE_PATHS = ("global", "projects")


@dataclass(frozen=True, slots=True)
class SessionInfo:
    name: str
    commit: str


@dataclass(frozen=True, slots=True)
class PromoteItem:
    operation: str
    path: str
    memory_id: str | None = None
    title: str | None = None
    summary: str | None = None
    body: str | None = None
    project: str | None = None


@dataclass(frozen=True, slots=True)
class PromotePlan:
    branch: str
    base_branch: str
    items: tuple[PromoteItem, ...]


def normalize_session_name(value: str) -> str:
    try:
        return normalize_project(value)
    except (TypeError, ValueError) as exc:
        raise ConfigurationError(
            "Session name is invalid. Use at most 64 lowercase letters, digits, dots, "
            "underscores, or hyphens; path traversal is not allowed."
        ) from exc


def _session_branch(name: str) -> str:
    return f"{SESSION_BRANCH_PREFIX}{normalize_session_name(name)}"


def list_sessions(repository: GitRepository) -> list[SessionInfo]:
    return [
        SessionInfo(name=name, commit=commit)
        for name, commit in sorted(repository.branches(SESSION_BRANCH_PREFIX).items())
    ]


def start_session(repository: GitRepository, name: str) -> SessionInfo:
    branch = _session_branch(name)
    repository.assert_clean()
    # current_branch() intentionally raises on a detached HEAD.
    repository.current_branch()
    if repository.head() is None:
        raise RepositoryError(
            f"Memory repository {repository.path} has no commits yet. Create a memory through "
            "the MCP server before starting a session."
        )
    if repository.branch_exists(branch):
        raise RepositoryError(
            f"Session branch {branch} already exists. Use 'perenna session promote {name}' to "
            f"apply it, or 'perenna session discard {name}' to remove it."
        )
    repository.create_branch(branch)
    commit = repository.resolve_commit(branch)
    if commit is None:
        raise RepositoryError(
            f"Session branch {branch} was created without a readable commit. Inspect the memory "
            "repository before retrying."
        )
    return SessionInfo(name=branch, commit=commit)


def discard_session(repository: GitRepository, name: str) -> str:
    branch = _session_branch(name)
    if repository.current_branch() == branch:
        raise RepositoryError(
            f"Cannot discard session branch {branch} while it is checked out. Check out the "
            "base branch first."
        )
    if not repository.branch_exists(branch):
        raise RepositoryError(
            f"Session branch {branch} does not exist. Run 'perenna session list' to see the "
            "available sessions."
        )
    repository.delete_branch(branch)
    return branch


def plan_promotion(repository: GitRepository, name: str) -> PromotePlan:
    branch = _session_branch(name)
    base = repository.current_branch()
    if base == branch:
        raise RepositoryError(
            f"Session branch {branch} is checked out. Check out the base branch before "
            "promoting it."
        )
    if not repository.branch_exists(branch):
        raise RepositoryError(
            f"Session branch {branch} does not exist. Run 'perenna session list' to see the "
            "available sessions."
        )
    if repository.head() is None:
        raise RepositoryError(
            f"Memory repository {repository.path} has no commits on {base!r}. Create a memory "
            "before promoting a session."
        )
    changes = repository.diff_name_status("HEAD", branch, MEMORY_TREE_PATHS)
    items: list[PromoteItem] = []
    for status, path in changes:
        if not path.endswith(".md"):
            continue
        if status in {"A", "M", "T"}:
            memory = _parse_session_memory(
                repository.read_at_commit(branch, path),
                path,
                branch,
            )
            if status == "A":
                items.append(
                    PromoteItem(
                        operation="create",
                        path=path,
                        title=memory.title,
                        summary=memory.summary,
                        body=memory.body,
                        project=memory.project,
                    )
                )
            else:
                items.append(
                    PromoteItem(
                        operation="replace",
                        path=path,
                        memory_id=memory.id,
                        title=memory.title,
                        summary=memory.summary,
                        body=memory.body,
                    )
                )
        elif status == "D":
            if not repository.path_exists_at("HEAD", path):
                continue
            memory = _parse_session_memory(
                repository.read_at_commit("HEAD", path),
                path,
                "HEAD",
            )
            items.append(
                PromoteItem(
                    operation="delete",
                    path=path,
                    memory_id=memory.id,
                    title=memory.title,
                )
            )
        else:
            raise RepositoryError(
                f"Session branch {branch} changes memory path {path!r} with unsupported Git "
                f"status {status!r}. Inspect the memory repository before retrying."
            )
    return PromotePlan(branch=branch, base_branch=base, items=tuple(items))


def promote_session(
    repository: GitRepository,
    core: PerennaCore,
    name: str,
    *,
    apply: bool,
) -> tuple[PromotePlan, list[tuple[PromoteItem, dict[str, Any]]]]:
    plan = plan_promotion(repository, name)
    if not apply:
        return plan, []
    repository.assert_clean()
    results: list[tuple[PromoteItem, dict[str, Any]]] = []
    for item in plan.items:
        if item.operation == "create":
            payload = core.create(
                title=item.title,
                summary=item.summary,
                body=item.body,
                project=item.project,
            )
        elif item.operation == "replace":
            try:
                current = core.get(memory_id=item.memory_id)
            except MemoryNotFoundError as exc:
                raise MemoryConflictError(
                    f"Session branch {plan.branch} edits {item.path!r}, but the base branch no "
                    "longer contains that memory. Reconcile the deletion before retrying."
                ) from exc
            payload = core.replace(
                memory_id=item.memory_id,
                base_revision=current["memory"]["revision"],
                summary=item.summary,
                body=item.body,
            )
        else:
            try:
                current = core.get(memory_id=item.memory_id)
            except MemoryNotFoundError:
                continue
            payload = core.delete(
                memory_id=item.memory_id,
                expected_title=current["memory"]["title"],
                base_revision=current["memory"]["revision"],
            )
        results.append((item, payload))
    return plan, results


def _parse_session_memory(text: str, path: str, ref: str) -> Memory:
    try:
        return parse_memory(text, path)
    except MemoryValidationError as exc:
        raise MemoryValidationError(
            f"Session branch {ref} contains an invalid memory at {path}: {exc}"
        ) from exc
