from __future__ import annotations

import logging
import subprocess
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import pytest

from perenna.config import RuntimePaths, RuntimeSettings
from perenna.core import PerennaCore
from perenna.errors import (
    ConfigurationError,
    IndexUnavailableError,
    MemoryNotFoundError,
    MemoryValidationError,
    RepositoryError,
)
from perenna.git import PushOutcome
from perenna.markdown import memory_revision
from perenna.models import (
    MemorySnapshot,
    MutationReceipt,
    PatchEdit,
    SearchMatch,
    SearchPassage,
    SearchResults,
)
from perenna.sync import setup_sync


class MemoryBackedIndex:
    def __init__(self) -> None:
        self.current = True

    def synchronize_after_mutation(
        self,
        _receipt: MutationReceipt,
        _snapshot: MemorySnapshot,
    ) -> None:
        self.current = True

    def is_current(self, _snapshot: MemorySnapshot) -> bool:
        return self.current

    def search(
        self,
        snapshot: MemorySnapshot,
        _query: str,
        project: str | None,
        limit: int,
    ) -> SearchResults:
        allowed = {"global"} if project is None else {"global", f"project:{project}"}
        memories = list(snapshot.memories)
        if project is not None:
            memories = [memory for memory in memories if memory.scope in allowed]
        matches = tuple(
            SearchMatch(
                memory=memory,
                revision=memory_revision(memory),
                rank=rank,
                passages=(SearchPassage(memory.body, 0, len(memory.body)),),
            )
            for rank, memory in enumerate(memories[:limit], start=1)
        )
        return SearchResults(matches, len(memories) > limit)

    def rebuild(self, _snapshot: MemorySnapshot) -> None:
        self.current = True

    def invalidate(self) -> None:
        self.current = False


class FailingMutationIndex(MemoryBackedIndex):
    def synchronize_after_mutation(
        self,
        _receipt: MutationReceipt,
        _snapshot: MemorySnapshot,
    ) -> None:
        raise IndexUnavailableError("offline")


def test_index_failure_keeps_committed_memory(tmp_path: Path) -> None:
    core = _core(tmp_path, index=FailingMutationIndex())

    result = core.create(
        title="Durable topic",
        summary="A durable topic.",
        body="committed body",
    )

    assert result["changed"]
    assert result["index_status"] == "pending"
    assert core.repository.head() is not None
    assert core.repository._run(["rev-list", "--count", "HEAD"]).stdout.strip() == "1"
    assert core.store.snapshot().memories[0].body == "committed body"
    core.repository.assert_clean()


def test_create_get_patch_replace_and_delete_return_current_revisions(tmp_path: Path) -> None:
    core = _core(tmp_path)
    created = core.create(
        title="Policy",
        summary="Rules covered by this policy.",
        body="Alpha rule.",
    )
    memory_id = created["memory"]["memory_id"]
    first_revision = created["memory"]["revision"]

    fetched = core.get(memory_id=memory_id)
    assert fetched["memory"]["body"] == "Alpha rule."
    assert fetched["memory"]["revision"] == first_revision

    patched = core.patch(
        memory_id=memory_id,
        base_revision=first_revision,
        edits=(PatchEdit("Alpha", "Current alpha"),),
        summary="Current rules covered by this policy.",
    )
    assert patched["memory"]["summary"] == "Current rules covered by this policy."
    assert patched["memory"]["revision"] != first_revision
    replaced = core.replace(
        memory_id=memory_id,
        base_revision=patched["memory"]["revision"],
        summary="The complete replacement policy.",
        body="Complete replacement.",
    )
    deleted = core.delete(
        memory_id=memory_id,
        expected_title="Policy",
        base_revision=replaced["memory"]["revision"],
    )

    assert deleted["action"] == "delete"
    assert deleted["recoverable_via_git"]
    assert core.list_memories()["memories"] == []
    assert core.repository._run(["rev-list", "--count", "HEAD"]).stdout.strip() == "4"


def test_local_mode_does_not_access_a_git_remote(tmp_path: Path, monkeypatch) -> None:
    core = _core(tmp_path)
    monkeypatch.setattr(
        core.repository,
        "fetch",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(
            AssertionError("local mode must not fetch")
        ),
    )

    created = core.create(title="Topic", summary="A topic.", body="Body")

    assert created["changed"]
    assert created["sync_status"] == "local"
    assert core.list_memories()["memories"][0]["title"] == "Topic"


def test_missing_configured_remote_keeps_the_local_commit_pending(tmp_path: Path) -> None:
    core = _core(tmp_path, git_remote="origin")

    result = core.create(title="Topic", summary="A topic.", body="Body")

    assert result["sync_status"] == "pending"
    assert core.repository.head() == result["commit"]


def test_dirty_worktree_reads_use_committed_snapshot(tmp_path: Path) -> None:
    core = _core(tmp_path)
    created = core.create(
        title="Stable topic",
        summary="A stable topic.",
        body="committed body",
    )
    memory_id = created["memory"]["memory_id"]
    memory = core.store.snapshot().memories[0]
    target = core.repository.worktree_path(memory.relative_path)
    target.write_text(target.read_text(encoding="utf-8").replace("committed body", "dirty body"))

    listed = core.list_memories()
    fetched = core.get(memory_id=memory_id)

    assert listed["memories"][0]["title"] == "Stable topic"
    assert fetched["memory"]["body"] == "committed body"


def test_logs_do_not_include_body_query_or_patch_text(tmp_path: Path, caplog) -> None:
    caplog.set_level(logging.INFO)
    core = _core(tmp_path)
    body = "BODY-SHOULD-NOT-APPEAR-73d2"
    summary = "SUMMARY-SHOULD-NOT-APPEAR-12ae"
    query = "QUERY-SHOULD-NOT-APPEAR-a9f1"
    replacement = "PATCH-SHOULD-NOT-APPEAR-4c8e"

    created = core.create(
        title="Private logging topic",
        summary=summary,
        body=body,
    )
    core.search(query=query)
    core.patch(
        memory_id=created["memory"]["memory_id"],
        base_revision=created["memory"]["revision"],
        edits=(PatchEdit(body, replacement),),
    )

    assert body not in caplog.text
    assert summary not in caplog.text
    assert query not in caplog.text
    assert replacement not in caplog.text


def test_shared_search_operations_overlap(tmp_path: Path) -> None:
    barrier = threading.Barrier(2)

    class ConcurrentIndex(MemoryBackedIndex):
        def search(
            self,
            snapshot: MemorySnapshot,
            query: str,
            project: str | None,
            limit: int,
        ) -> SearchResults:
            barrier.wait(timeout=5)
            return super().search(snapshot, query, project, limit)

    core = _core(tmp_path)
    core.create(title="Concurrent topic", summary="A concurrent topic.", body="Body")
    core.index = ConcurrentIndex()

    with ThreadPoolExecutor(max_workers=2) as executor:
        futures = [executor.submit(core.search, query=f"query-{index}") for index in range(2)]
        results = [future.result(timeout=10) for future in futures]

    assert all(result["matches"][0]["title"] == "Concurrent topic" for result in results)


def test_rebuild_and_mutation_are_mutually_exclusive(tmp_path: Path) -> None:
    rebuild_entered = threading.Event()
    release_rebuild = threading.Event()

    class BlockingIndex(MemoryBackedIndex):
        def rebuild(self, _snapshot: MemorySnapshot) -> None:
            rebuild_entered.set()
            assert release_rebuild.wait(timeout=5)
            self.current = True

    index = BlockingIndex()
    core = _core(tmp_path, index=index)
    core.create(title="Existing topic", summary="An existing topic.", body="Body")
    index.current = False

    with ThreadPoolExecutor(max_workers=2) as executor:
        search = executor.submit(core.search, query="existing")
        assert rebuild_entered.wait(timeout=5)
        create = executor.submit(
            core.create,
            title="Second topic",
            summary="A second topic.",
            body="Second body",
        )
        time.sleep(0.2)
        assert not create.done()
        release_rebuild.set()
        assert search.result(timeout=10)["matches"][0]["title"] == "Existing topic"
        assert create.result(timeout=10)["changed"]

    assert len(core.store.snapshot().memories) == 2


def test_project_list_contains_global_and_selected_project_only(tmp_path: Path) -> None:
    core = _core(tmp_path)
    core.create(title="Global topic", summary="A global topic.", body="Global")
    core.create(
        title="Vexor topic",
        summary="A Vexor topic.",
        body="Vexor",
        project="vexor",
    )
    core.create(
        title="Other topic",
        summary="Another project topic.",
        body="Other",
        project="other",
    )

    result = core.list_memories(project="VEXOR")

    assert {memory["title"] for memory in result["memories"]} == {
        "Global topic",
        "Vexor topic",
    }
    assert result["projects"] == []
    all_scopes = core.list_memories()
    assert all_scopes["projects"] == ["other", "vexor"]


def test_empty_search_and_invalid_inputs_have_clear_results(tmp_path: Path) -> None:
    core = _core(tmp_path)
    assert core.search(query="anything")["matches"] == []
    with pytest.raises(MemoryValidationError, match="query is empty"):
        core.search(query="  ")
    with pytest.raises(MemoryValidationError, match="limit is invalid"):
        core.search(query="topic", limit=0)
    with pytest.raises(MemoryValidationError, match="limit is invalid"):
        core.search(query="topic", limit=True)
    with pytest.raises(MemoryValidationError, match="control character"):
        core.search(query="bad\x00query")
    with pytest.raises(MemoryValidationError, match="project is invalid"):
        core.list_memories(project="../escape")
    with pytest.raises(MemoryValidationError, match="ID is invalid"):
        core.get(memory_id="bad-id")
    with pytest.raises(MemoryNotFoundError, match="was not found"):
        core.get(memory_id="01ARZ3NDEKTSV4RRFFQ69G5FAV")


def test_search_limit_is_counted_after_memory_deduplication(tmp_path: Path) -> None:
    core = _core(tmp_path)
    for number in range(4):
        core.create(
            title=f"Topic {number}",
            summary=f"Summary for topic {number}.",
            body=f"Body {number}",
        )

    result = core.search(query="topic", limit=2)

    assert len(result["matches"]) == 2
    assert result["limit"] == 2
    assert result["truncated"]


def test_search_failure_invalidates_marker_and_surfaces_error(tmp_path: Path) -> None:
    class FailingSearchIndex(MemoryBackedIndex):
        def __init__(self) -> None:
            super().__init__()
            self.invalidations = 0

        def search(
            self,
            _snapshot: MemorySnapshot,
            _query: str,
            _project: str | None,
            _limit: int,
        ) -> SearchResults:
            raise IndexUnavailableError("search unavailable")

        def invalidate(self) -> None:
            self.invalidations += 1
            super().invalidate()

    index = FailingSearchIndex()
    core = _core(tmp_path, index=index)
    core.create(title="Topic", summary="A topic.", body="Body")

    with pytest.raises(IndexUnavailableError, match="search unavailable"):
        core.search(query="topic")
    assert index.invalidations == 1


def test_exclusive_recheck_failure_rebuilds_before_search(tmp_path: Path) -> None:
    class FailingRecheckIndex(MemoryBackedIndex):
        def __init__(self) -> None:
            super().__init__()
            self.checks = 0
            self.rebuilds = 0

        def is_current(self, _snapshot: MemorySnapshot) -> bool:
            self.checks += 1
            if self.checks == 1:
                return False
            if self.checks == 2:
                raise IndexUnavailableError("broken info")
            return True

        def rebuild(self, _snapshot: MemorySnapshot) -> None:
            self.rebuilds += 1

    index = FailingRecheckIndex()
    core = _core(tmp_path, index=index)
    core.create(title="Topic", summary="A topic.", body="Body")

    assert core.search(query="topic")["matches"][0]["title"] == "Topic"
    assert index.rebuilds == 1


def test_remote_write_is_confirmed_before_success(tmp_path: Path) -> None:
    remote = _bare_repository(tmp_path / "remote.git")
    core = _remote_core(tmp_path / "writer", remote)

    result = core.create(title="Topic", summary="A topic.", body="Body")

    remote_head = _bare_head(remote)
    assert result["commit"] == remote_head
    assert core.repository.head() == remote_head


def test_remote_noop_does_not_push_again(tmp_path: Path, monkeypatch) -> None:
    remote = _bare_repository(tmp_path / "remote.git")
    core = _remote_core(tmp_path / "writer", remote)
    core.create(title="Topic", summary="A topic.", body="Body")
    monkeypatch.setattr(
        core.repository,
        "push",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(
            AssertionError("an unchanged mutation must not push")
        ),
    )

    result = core.create(title="Topic", summary="A topic.", body="Body")

    assert not result["changed"]
    assert result["sync_status"] == "unchanged"


def test_remote_noop_reports_a_stale_or_unavailable_index(
    tmp_path: Path,
    monkeypatch,
) -> None:
    remote = _bare_repository(tmp_path / "remote.git")
    core = _remote_core(tmp_path / "writer", remote)
    core.create(title="Topic", summary="A topic.", body="Body")
    core.index.current = False  # type: ignore[attr-defined]

    stale = core.create(title="Topic", summary="A topic.", body="Body")
    assert stale["index_status"] == "pending"

    monkeypatch.setattr(
        core.index,
        "is_current",
        lambda _snapshot: (_ for _ in ()).throw(IndexUnavailableError("offline")),
    )
    unavailable = core.create(title="Topic", summary="A topic.", body="Body")
    assert unavailable["index_status"] == "pending"


def test_timeout_confirmation_fast_forwards_a_remote_descendant(
    tmp_path: Path,
    monkeypatch,
) -> None:
    remote = _bare_repository(tmp_path / "remote.git")
    core = _remote_core(tmp_path / "writer", remote)
    observer = _remote_core(tmp_path / "observer", remote)
    original_push = core.repository.push

    def push_then_advance(*args, **kwargs) -> PushOutcome:
        outcome = original_push(*args, **kwargs)
        assert outcome.succeeded
        remote_head = observer.repository.fetch("origin", "main")
        assert remote_head is not None
        observer.repository.reset_to(remote_head)
        later = observer.store.create(
            title="Later remote memory",
            summary="A later remote memory.",
            body="Later",
            project=None,
        )
        assert observer.repository.push(
            "origin",
            commit=later.commit,
            branch="main",
        ).succeeded
        return PushOutcome(True, False, "timeout")

    monkeypatch.setattr(core.repository, "push", push_then_advance)

    result = core.create(title="First", summary="The first memory.", body="First")

    assert result["sync_status"] == "synchronized"
    assert result["index_status"] == "current"
    assert core.repository.head() == _bare_head(remote)
    assert {item["title"] for item in core.list_memories()["memories"]} == {
        "First",
        "Later remote memory",
    }


def test_new_instance_setup_imports_an_existing_remote_write(tmp_path: Path) -> None:
    remote = _bare_repository(tmp_path / "remote.git")
    writer = _remote_core(tmp_path / "writer", remote)
    writer.create(title="Shared topic", summary="A shared topic.", body="Body")
    reader = _remote_core(tmp_path / "reader", remote)

    listed = reader.list_memories()

    assert listed["memories"][0]["title"] == "Shared topic"
    assert reader.repository.head() == _bare_head(remote)


def test_restart_fast_forwards_a_clean_configured_repository(tmp_path: Path) -> None:
    remote = _bare_repository(tmp_path / "remote.git")
    writer = _remote_core(tmp_path / "writer", remote)
    _remote_core(tmp_path / "reader", remote)
    writer.create(title="After setup", summary="Written after setup.", body="Body")

    restarted = _core(tmp_path / "reader", git_remote="origin")

    assert restarted.list_memories()["memories"][0]["title"] == "After setup"
    assert restarted.repository.head() == _bare_head(remote)


def test_restart_keeps_safe_local_ahead_history(tmp_path: Path) -> None:
    remote = _bare_repository(tmp_path / "remote.git")
    core = _remote_core(tmp_path / "writer", remote)
    core.create(title="Remote base", summary="A remote base.", body="Base")
    local_only = core.store.create(
        title="Local pending",
        summary="A local pending memory.",
        body="Pending",
        project=None,
    )

    restarted = _core(tmp_path / "writer", git_remote="origin")

    assert restarted.repository.head() == local_only.commit
    assert restarted.repository.sync_conflict_commit() is None


def test_restart_marks_diverged_history_and_blocks_writes(tmp_path: Path) -> None:
    remote = _bare_repository(tmp_path / "remote.git")
    seed = _remote_core(tmp_path / "seed", remote)
    seed.create(title="Base", summary="A shared base.", body="Base")
    local = _remote_core(tmp_path / "local", remote)
    other = _remote_core(tmp_path / "other", remote)
    local_receipt = local.store.create(
        title="Local branch",
        summary="A local branch memory.",
        body="Local",
        project=None,
    )
    other.create(title="Remote branch", summary="A remote branch memory.", body="Remote")

    restarted = _core(tmp_path / "local", git_remote="origin")

    assert restarted.repository.sync_conflict_commit() == local_receipt.commit
    with pytest.raises(RepositoryError, match="writes are blocked"):
        restarted.create(title="Blocked", summary="A blocked write.", body="Blocked")


def test_concurrent_remote_writers_surface_and_block_a_conflict(tmp_path: Path) -> None:
    remote = _bare_repository(tmp_path / "remote.git")
    first = _remote_core(tmp_path / "first", remote)
    second = _remote_core(tmp_path / "second", remote)
    barrier = threading.Barrier(2)
    _pause_first_push(first, barrier)
    _pause_first_push(second, barrier)

    with ThreadPoolExecutor(max_workers=2) as executor:
        futures = (
            executor.submit(
                first.create,
                title="Writer A",
                summary="First writer.",
                body="First body",
            ),
            executor.submit(
                second.create,
                title="Writer B",
                summary="Second writer.",
                body="Second body",
            ),
        )
        results = [future.result(timeout=15) for future in futures]

    verifier = _remote_core(tmp_path / "verifier", remote)
    assert len(verifier.list_memories()["memories"]) == 1
    assert all(result["changed"] for result in results)
    assert {result["sync_status"] for result in results} == {"synchronized", "conflict"}
    conflicted_core = first if first.repository.sync_conflict_commit() else second
    with pytest.raises(RepositoryError, match="writes are blocked"):
        conflicted_core.create(title="Blocked", summary="Blocked write.", body="Body")


def test_remote_push_failure_keeps_a_pending_local_write(tmp_path: Path, monkeypatch) -> None:
    remote = _bare_repository(tmp_path / "remote.git")
    core = _remote_core(tmp_path / "writer", remote)
    monkeypatch.setattr(
        core.repository,
        "push",
        lambda *_args, **_kwargs: PushOutcome(True, False, "failed"),
    )

    result = core.create(title="Pending", summary="A pending write.", body="Body")

    assert result["sync_status"] == "pending"
    assert core.repository.head() == result["commit"]
    core.repository.assert_clean()


def test_push_timeout_is_success_when_remote_contains_the_candidate(
    tmp_path: Path,
    monkeypatch,
) -> None:
    remote = _bare_repository(tmp_path / "remote.git")
    core = _remote_core(tmp_path / "writer", remote)
    original_push = core.repository.push

    def push_then_timeout(*args, **kwargs) -> PushOutcome:
        outcome = original_push(*args, **kwargs)
        assert outcome.succeeded
        return PushOutcome(True, False, "timeout")

    monkeypatch.setattr(core.repository, "push", push_then_timeout)

    result = core.create(title="Confirmed", summary="A confirmed write.", body="Body")

    assert result["changed"]
    assert result["commit"] == _bare_head(remote)


def test_unconfirmed_timeout_remains_a_visible_local_pending_write(
    tmp_path: Path,
    monkeypatch,
) -> None:
    remote = _bare_repository(tmp_path / "remote.git")
    core = _remote_core(tmp_path / "writer", remote)
    monkeypatch.setattr(
        core.repository,
        "push",
        lambda *_args, **_kwargs: PushOutcome(True, False, "timeout"),
    )

    result = core.create(title="Unconfirmed", summary="An unconfirmed write.", body="Body")

    assert result["sync_status"] == "pending"
    assert core.list_memories()["memories"][0]["title"] == "Unconfirmed"


def test_remote_read_remains_local_when_the_network_is_unavailable(
    tmp_path: Path,
    monkeypatch,
) -> None:
    remote = _bare_repository(tmp_path / "remote.git")
    core = _remote_core(tmp_path / "writer", remote)
    core.create(title="Current", summary="A current memory.", body="Body")
    monkeypatch.setattr(
        core.repository,
        "fetch",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(RepositoryError("network unavailable")),
    )

    assert core.list_memories()["memories"][0]["title"] == "Current"


def test_core_accepts_injected_repository_and_rejects_file_home(tmp_path: Path) -> None:
    core = _core(tmp_path)
    settings = RuntimeSettings(RuntimePaths(tmp_path / "home"), None)
    reused = PerennaCore(
        settings,
        repository=core.repository,
        index=MemoryBackedIndex(),
        locks=core.locks,
    )
    assert reused.repository is core.repository

    bad_home = tmp_path / "not-a-directory"
    bad_home.write_text("occupied", encoding="utf-8")
    with pytest.raises(ConfigurationError, match="not a directory"):
        PerennaCore(RuntimeSettings(RuntimePaths(bad_home), None))


def _core(
    tmp_path: Path,
    *,
    index: MemoryBackedIndex | None = None,
    git_remote: str | None = None,
) -> PerennaCore:
    settings = RuntimeSettings(
        paths=RuntimePaths(tmp_path / "home"),
        git_remote=git_remote,
    )
    return PerennaCore(settings, index=index or MemoryBackedIndex())


def _bare_repository(path: Path) -> Path:
    subprocess.run(
        ["git", "init", "--bare", str(path)],
        check=True,
        capture_output=True,
        text=True,
        encoding="utf-8",
    )
    return path


def _bare_head(path: Path) -> str:
    return subprocess.run(
        ["git", "--git-dir", str(path), "rev-parse", "refs/heads/main"],
        check=True,
        capture_output=True,
        text=True,
        encoding="utf-8",
    ).stdout.strip()


def _remote_core(path: Path, remote: Path) -> PerennaCore:
    setup_sync(
        path / "home" / "memory",
        str(remote),
        remote_name="origin",
        replace=False,
    )
    return _core(path, git_remote="origin")


def _pause_first_push(core: PerennaCore, barrier: threading.Barrier) -> None:
    original_push = core.repository.push
    first = True

    def push(*args, **kwargs) -> PushOutcome:
        nonlocal first
        if first:
            first = False
            barrier.wait(timeout=5)
        return original_push(*args, **kwargs)

    core.repository.push = push  # type: ignore[method-assign]
