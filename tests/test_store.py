from __future__ import annotations

import logging
from dataclasses import replace
from datetime import UTC, datetime
from pathlib import Path

import pytest

from perenna.errors import (
    MemoryConflictError,
    MemoryIntegrityError,
    MemoryNotFoundError,
    MemoryValidationError,
    RepositoryDirtyError,
    RepositoryError,
)
from perenna.filesystem import atomic_replace
from perenna.git import GitRepository
from perenna.markdown import memory_revision, serialize_memory
from perenna.models import Memory, PatchEdit
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


def test_create_then_replace_preserves_identity_and_creation_time(
    repository: GitRepository,
) -> None:
    store = _store(repository, times=(FIRST_TIME, SECOND_TIME), ids=(FIRST_ID,))

    created = store.create(
        title="  Release   notes ",
        summary="Release note policy.",
        body="first\r\nbody",
        source="claude-code",
        project="Perenna",
    )
    updated = store.replace(
        memory_id=created.memory.id,
        base_revision=memory_revision(created.memory),
        summary="Updated release note policy.",
        body="updated body",
        source="cursor",
    )

    assert created.operation == "create"
    assert updated.operation == "replace"
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

    global_memory = store.create(
        title="Fact",
        summary="A global fact.",
        body="global",
        source="codex",
        project=None,
    )
    project_memory = store.create(
        title="fact",
        summary="A project fact.",
        body="project",
        source="codex",
        project="perenna",
    )

    assert global_memory.memory.id != project_memory.memory.id
    assert {memory.scope for memory in store.snapshot().memories} == {
        "global",
        "project:perenna",
    }


def test_snapshot_reuses_validated_snapshot_while_head_is_unchanged(
    repository: GitRepository,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    store = _store(repository)
    store.create(
        title="Fact",
        summary="A cached fact.",
        body="cached body",
        source="codex",
        project=None,
    )
    cached_store = MemoryStore(repository)
    original_paths = repository.memory_paths_at_commit
    original_read = repository.read_at_commit
    paths_calls = 0
    read_calls = 0

    def counted_paths(commit: str) -> list[str]:
        nonlocal paths_calls
        paths_calls += 1
        return original_paths(commit)

    def counted_read(commit: str, relative_path: str) -> str:
        nonlocal read_calls
        read_calls += 1
        return original_read(commit, relative_path)

    monkeypatch.setattr(repository, "memory_paths_at_commit", counted_paths)
    monkeypatch.setattr(repository, "read_at_commit", counted_read)

    first = cached_store.snapshot()
    second = cached_store.snapshot()

    assert second is first
    assert paths_calls == 1
    assert read_calls == 1


def test_snapshot_reloads_after_external_commit(repository: GitRepository) -> None:
    store = _store(repository)
    created = store.create(
        title="Fact",
        summary="A cached fact.",
        body="first body",
        source="codex",
        project=None,
    )
    first = store.snapshot()
    externally_updated = replace(
        created.memory,
        body="externally updated body",
        updated_at="2026-08-22T03:04:05Z",
    )

    _commit_document(repository, externally_updated)
    second = store.snapshot()

    assert second is not first
    assert second.commit != first.commit
    assert second.memories == (externally_updated,)


def test_snapshot_rejects_duplicate_ids(repository: GitRepository) -> None:
    store = _store(repository)
    created = store.create(
        title="First", summary="The first fact.", body="one", source="codex", project=None
    )
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
    created = store.create(
        title="Straße", summary="A normalized fact.", body="one", source="codex", project=None
    )
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
    created = store.create(
        title="Fact",
        summary="A committed fact.",
        body="committed body",
        source="codex",
        project=None,
    )
    target = repository.worktree_path(created.memory.relative_path)
    previous_bytes = target.read_bytes()
    previous_head = repository.head()

    def fail_commit(message: str, relative_path: str) -> str:
        raise RepositoryError("simulated commit failure")

    monkeypatch.setattr(repository, "commit", fail_commit)

    with pytest.raises(RepositoryError, match="simulated commit failure"):
        store.replace(
            memory_id=created.memory.id,
            base_revision=memory_revision(created.memory),
            summary="A committed fact.",
            body="uncommitted body",
            source="cursor",
        )

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
        store.create(
            title="Fact",
            summary="A fact.",
            body="body",
            source="codex",
            project=None,
        )

    assert repository.head() is None
    assert repository.staged_paths() == []
    assert not repository.worktree_path(f"global/{FIRST_ID}.md").exists()
    assert repository._run(["status", "--porcelain=v1"]).stdout == ""


def test_dirty_repository_refuses_write_but_snapshot_reads_committed_head(
    repository: GitRepository,
) -> None:
    store = _store(repository, times=(FIRST_TIME, SECOND_TIME))
    created = store.create(
        title="Fact",
        summary="A committed fact.",
        body="committed body",
        source="codex",
        project=None,
    )
    target = repository.worktree_path(created.memory.relative_path)
    target.write_text("uncommitted edit", encoding="utf-8")

    snapshot = store.snapshot()

    assert snapshot.memories == (created.memory,)
    with pytest.raises(RepositoryDirtyError, match="uncommitted changes"):
        store.replace(
            memory_id=created.memory.id,
            base_revision=memory_revision(created.memory),
            summary="A committed fact.",
            body="replacement",
            source="cursor",
        )
    assert target.read_text(encoding="utf-8") == "uncommitted edit"


def test_storage_does_not_log_memory_body(
    repository: GitRepository,
    caplog: pytest.LogCaptureFixture,
) -> None:
    secret_body = "PRIVATE-BODY-SENTINEL"
    caplog.set_level(logging.DEBUG)

    _store(repository).create(
        title="Fact",
        summary="A private fact.",
        body=secret_body,
        source="codex",
        project=None,
    )

    assert secret_body not in caplog.text


def test_create_is_idempotent_only_when_existing_body_matches(
    repository: GitRepository,
) -> None:
    store = _store(repository)
    created = store.create(
        title="Fact", summary="A fact.", body="body", source="codex", project=None
    )

    repeated = store.create(
        title="fact", summary="A fact.", body="body", source="cursor", project=None
    )

    assert not repeated.changed
    assert repeated.memory == created.memory
    assert repeated.commit == created.commit
    with pytest.raises(MemoryConflictError, match="use patch or replace"):
        store.create(
            title="FACT",
            summary="A fact.",
            body="different",
            source="cursor",
            project=None,
        )
    assert repository._run(["rev-list", "--count", "HEAD"]).stdout.strip() == "1"


def test_create_rejects_a_generated_duplicate_id(repository: GitRepository) -> None:
    store = _store(
        repository,
        times=(FIRST_TIME, SECOND_TIME),
        ids=(FIRST_ID, FIRST_ID),
    )
    store.create(
        title="First",
        summary="The first memory.",
        body="one",
        source="codex",
        project=None,
    )

    with pytest.raises(MemoryIntegrityError, match="already exists"):
        store.create(
            title="Second",
            summary="The second memory.",
            body="two",
            source="codex",
            project=None,
        )


def test_patch_applies_exact_non_overlapping_edits_and_rejects_stale_revision(
    repository: GitRepository,
) -> None:
    store = _store(repository, times=(FIRST_TIME, SECOND_TIME))
    created = store.create(
        title="Policy",
        summary="Rules governing the policy.",
        body="Alpha rule.\nBeta rule.",
        source="codex",
        project=None,
    )

    patched = store.patch(
        memory_id=created.memory.id,
        base_revision=memory_revision(created.memory),
        edits=(
            PatchEdit("Alpha", "Current alpha"),
            PatchEdit("Beta", "Current beta"),
        ),
        source="cursor",
    )

    assert patched.memory.body == "Current alpha rule.\nCurrent beta rule."
    assert patched.memory.id == created.memory.id
    with pytest.raises(MemoryConflictError, match="changed after it was read"):
        store.patch(
            memory_id=created.memory.id,
            base_revision=memory_revision(created.memory),
            edits=(PatchEdit("Current alpha", "Other"),),
            source="cursor",
        )


def test_patch_rejects_missing_ambiguous_and_overlapping_anchors(
    repository: GitRepository,
) -> None:
    store = _store(repository)
    created = store.create(
        title="Policy",
        summary="Rules governing the policy.",
        body="repeat repeat and tail",
        source="codex",
        project=None,
    )
    revision = memory_revision(created.memory)

    with pytest.raises(MemoryConflictError, match="could not find"):
        store.patch(
            memory_id=created.memory.id,
            base_revision=revision,
            edits=(PatchEdit("missing", "new"),),
            source="codex",
        )
    with pytest.raises(MemoryConflictError, match="more than once"):
        store.patch(
            memory_id=created.memory.id,
            base_revision=revision,
            edits=(PatchEdit("repeat", "new"),),
            source="codex",
        )
    with pytest.raises(MemoryConflictError, match="overlap"):
        store.patch(
            memory_id=created.memory.id,
            base_revision=revision,
            edits=(
                PatchEdit("repeat repeat", "new"),
                PatchEdit("repeat and", "other"),
            ),
            source="codex",
        )


def test_patch_validation_and_noop_paths_are_explicit(repository: GitRepository) -> None:
    store = _store(repository)
    created = store.create(
        title="Policy",
        summary="Rules governing the policy.",
        body="Alpha rule.",
        source="codex",
        project=None,
    )
    revision = memory_revision(created.memory)

    unchanged = store.patch(
        memory_id=created.memory.id,
        base_revision=revision,
        edits=(PatchEdit("Alpha", "Alpha"),),
        source="cursor",
    )
    assert not unchanged.changed

    unchanged_replace = store.replace(
        memory_id=created.memory.id,
        base_revision=revision,
        summary=created.memory.summary,
        body=created.memory.body,
        source="cursor",
    )
    assert not unchanged_replace.changed

    with pytest.raises(MemoryNotFoundError, match="was not found"):
        store.patch(
            memory_id=SECOND_ID,
            base_revision=revision,
            edits=(PatchEdit("Alpha", "Beta"),),
            source="cursor",
        )
    with pytest.raises(MemoryValidationError, match="at least one exact edit"):
        store.patch(
            memory_id=created.memory.id,
            base_revision=revision,
            edits=(),
            source="cursor",
        )
    with pytest.raises(MemoryValidationError, match="old_text is empty"):
        store.patch(
            memory_id=created.memory.id,
            base_revision=revision,
            edits=(PatchEdit("", "Beta"),),
            source="cursor",
        )
    with pytest.raises(MemoryValidationError, match="control character"):
        store.patch(
            memory_id=created.memory.id,
            base_revision=revision,
            edits=(PatchEdit("Alpha", "bad\x00text"),),
            source="cursor",
        )
    with pytest.raises(MemoryValidationError, match="not canonical"):
        store.patch(
            memory_id=created.memory.id,
            base_revision=revision,
            edits=(PatchEdit("Alpha rule.", "\nBeta rule.\n"),),
            source="cursor",
        )


def test_delete_requires_title_and_revision_and_commits_one_file(
    repository: GitRepository,
) -> None:
    store = _store(repository)
    created = store.create(
        title="Fact",
        summary="A project fact.",
        body="body",
        source="codex",
        project="perenna",
    )
    revision = memory_revision(created.memory)

    with pytest.raises(MemoryConflictError, match="is titled"):
        store.delete(
            memory_id=created.memory.id,
            expected_title="Other",
            base_revision=revision,
        )
    deleted = store.delete(
        memory_id=created.memory.id,
        expected_title="Fact",
        base_revision=revision,
    )

    assert deleted.operation == "delete"
    assert deleted.changed
    assert store.snapshot().memories == ()
    assert repository.commit_paths(deleted.commit) == [created.memory.relative_path]
    assert not repository.worktree_path(created.memory.relative_path).exists()


def test_delete_commit_failure_restores_file_and_git_index(
    repository: GitRepository,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    store = _store(repository)
    created = store.create(
        title="Fact",
        summary="A recoverable fact.",
        body="body",
        source="codex",
        project=None,
    )
    target = repository.worktree_path(created.memory.relative_path)
    previous_bytes = target.read_bytes()
    previous_head = repository.head()

    def fail_commit(message: str, relative_path: str) -> str:
        raise RepositoryError("simulated delete commit failure")

    monkeypatch.setattr(repository, "commit", fail_commit)

    with pytest.raises(RepositoryError, match="simulated delete commit failure"):
        store.delete(
            memory_id=created.memory.id,
            expected_title=created.memory.title,
            base_revision=memory_revision(created.memory),
        )

    assert target.read_bytes() == previous_bytes
    assert repository.head() == previous_head
    assert repository.staged_paths() == []
    assert store.snapshot().memories == (created.memory,)
