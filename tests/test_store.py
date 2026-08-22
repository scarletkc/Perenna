from __future__ import annotations

import logging
from dataclasses import replace
from datetime import UTC, datetime
from pathlib import Path

import pytest

from perenna.errors import MemoryIntegrityError, RepositoryDirtyError, RepositoryError
from perenna.filesystem import atomic_replace
from perenna.git import GitRepository
from perenna.markdown import serialize_memory
from perenna.models import Memory
from perenna.store import MemoryStore

FIRST_ID = "01ARZ3NDEKTSV4RRFFQ69G5FAV"
SECOND_ID = "01ARZ3NDEKTSV4RRFFQ69G5FAW"
FIRST_TIME = datetime(2026, 8, 22, 1, 2, 3, tzinfo=UTC)
SECOND_TIME = datetime(2026, 8, 22, 2, 3, 4, tzinfo=UTC)


def _store(
    repository: GitRepository,
    *,
    times: tuple[datetime, ...] = (FIRST_TIME,),
    ids: tuple[str, ...] = (FIRST_ID,),
) -> MemoryStore:
    clock_values = iter(times)
    id_values = iter(ids)
    return MemoryStore(
        repository,
        clock=lambda: next(clock_values),
        id_factory=lambda: next(id_values),
    )


def _commit_document(repository: GitRepository, memory: Memory) -> None:
    target = repository.worktree_path(memory.relative_path)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(serialize_memory(memory), encoding="utf-8", newline="")
    repository.stage(memory.relative_path)
    repository.commit("test: add conflicting fixture", memory.relative_path)


def test_create_then_update_preserves_identity_and_creation_time(
    repository: GitRepository,
) -> None:
    store = _store(repository, times=(FIRST_TIME, SECOND_TIME), ids=(FIRST_ID,))

    created = store.write(
        title="  Release   notes ",
        body="first\r\nbody",
        source="claude-code",
        project="Perenna",
    )
    updated = store.write(
        title="release notes",
        body="updated body",
        source="cursor",
        project="perenna",
    )

    assert created.operation == "add"
    assert updated.operation == "update"
    assert updated.memory.id == created.memory.id == FIRST_ID
    assert updated.memory.relative_path == created.memory.relative_path
    assert updated.memory.created_at == created.memory.created_at
    assert updated.memory.updated_at > created.memory.updated_at
    assert updated.memory.source == "cursor"
    assert updated.memory.body == "updated body"
    assert updated.previous_commit == created.commit
    assert updated.commit != created.commit
    assert store.snapshot().memories == (updated.memory,)


def test_same_title_in_different_scopes_creates_distinct_memories(
    repository: GitRepository,
) -> None:
    store = _store(
        repository,
        times=(FIRST_TIME, SECOND_TIME),
        ids=(FIRST_ID, SECOND_ID),
    )

    global_memory = store.write(title="Fact", body="global", source="codex", project=None)
    project_memory = store.write(
        title="fact",
        body="project",
        source="codex",
        project="perenna",
    )

    assert global_memory.memory.id != project_memory.memory.id
    assert {memory.scope for memory in store.snapshot().memories} == {
        "global",
        "project:perenna",
    }


def test_snapshot_rejects_duplicate_ids(repository: GitRepository) -> None:
    store = _store(repository)
    created = store.write(title="First", body="one", source="codex", project=None)
    duplicate = replace(
        created.memory,
        title="Second",
        scope="project:perenna",
        relative_path=f"projects/perenna/{created.memory.id}.md",
    )
    _commit_document(repository, duplicate)

    with pytest.raises(MemoryIntegrityError, match="appears in both"):
        store.snapshot()


def test_snapshot_rejects_duplicate_normalized_titles(repository: GitRepository) -> None:
    store = _store(repository)
    created = store.write(title="Straße", body="one", source="codex", project=None)
    duplicate = replace(
        created.memory,
        id=SECOND_ID,
        title="STRASSE",
        relative_path=f"global/{SECOND_ID}.md",
    )
    _commit_document(repository, duplicate)

    with pytest.raises(MemoryIntegrityError, match="duplicate normalized titles"):
        store.snapshot()


def test_atomic_replace_preserves_old_file_when_replace_fails(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    target = tmp_path / "memory.md"
    target.write_bytes(b"old bytes")

    def fail_replace(source: Path, destination: Path) -> None:
        raise OSError("simulated replace failure")

    monkeypatch.setattr("perenna.filesystem.os.replace", fail_replace)

    with pytest.raises(OSError, match="simulated replace failure"):
        atomic_replace(target, b"new bytes")

    assert target.read_bytes() == b"old bytes"
    assert list(tmp_path.glob(".memory.md.*.tmp")) == []


def test_commit_failure_rolls_back_updated_file_and_git_index(
    repository: GitRepository,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    store = _store(repository, times=(FIRST_TIME, SECOND_TIME))
    created = store.write(title="Fact", body="committed body", source="codex", project=None)
    target = repository.worktree_path(created.memory.relative_path)
    previous_bytes = target.read_bytes()
    previous_head = repository.head()

    def fail_commit(message: str, relative_path: str) -> str:
        raise RepositoryError("simulated commit failure")

    monkeypatch.setattr(repository, "commit", fail_commit)

    with pytest.raises(RepositoryError, match="simulated commit failure"):
        store.write(title="fact", body="uncommitted body", source="cursor", project=None)

    assert target.read_bytes() == previous_bytes
    assert repository.head() == previous_head
    assert repository.staged_paths() == []
    assert repository._run(["status", "--porcelain=v1"]).stdout == ""
    assert store.snapshot().memories == (created.memory,)


def test_commit_failure_removes_a_new_memory_file(
    repository: GitRepository,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    store = _store(repository)

    def fail_commit(message: str, relative_path: str) -> str:
        raise RepositoryError("simulated commit failure")

    monkeypatch.setattr(repository, "commit", fail_commit)

    with pytest.raises(RepositoryError, match="simulated commit failure"):
        store.write(title="Fact", body="body", source="codex", project=None)

    assert repository.head() is None
    assert repository.staged_paths() == []
    assert not repository.worktree_path(f"global/{FIRST_ID}.md").exists()
    assert repository._run(["status", "--porcelain=v1"]).stdout == ""


def test_dirty_repository_refuses_write_but_snapshot_reads_committed_head(
    repository: GitRepository,
) -> None:
    store = _store(repository, times=(FIRST_TIME, SECOND_TIME))
    created = store.write(title="Fact", body="committed body", source="codex", project=None)
    target = repository.worktree_path(created.memory.relative_path)
    target.write_text("uncommitted edit", encoding="utf-8")

    snapshot = store.snapshot()

    assert snapshot.memories == (created.memory,)
    with pytest.raises(RepositoryDirtyError, match="uncommitted changes"):
        store.write(title="Fact", body="replacement", source="cursor", project=None)
    assert target.read_text(encoding="utf-8") == "uncommitted edit"


def test_storage_does_not_log_memory_body(
    repository: GitRepository,
    caplog: pytest.LogCaptureFixture,
) -> None:
    secret_body = "PRIVATE-BODY-SENTINEL"
    caplog.set_level(logging.DEBUG)

    _store(repository).write(
        title="Fact",
        body=secret_body,
        source="codex",
        project=None,
    )

    assert secret_body not in caplog.text
