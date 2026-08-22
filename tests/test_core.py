from __future__ import annotations

import logging
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from contextlib import contextmanager
from pathlib import Path
from typing import Any

import pytest

from perenna.config import RuntimePaths, RuntimeSettings
from perenna.core import PerennaCore
from perenna.errors import (
    ConfigurationError,
    IndexUnavailableError,
    MemoryValidationError,
    RepositoryError,
)
from perenna.git import PushOutcome
from perenna.models import MemorySnapshot, WriteReceipt


class MemoryBackedIndex:
    def __init__(self) -> None:
        self.current = True

    def synchronize_after_write(
        self,
        _receipt: WriteReceipt,
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
    ) -> list[Any]:
        allowed = {"global"} if project is None else {"global", f"project:{project}"}
        if project is None:
            return list(snapshot.memories)
        return [memory for memory in snapshot.memories if memory.scope in allowed]

    def rebuild(self, _snapshot: MemorySnapshot) -> None:
        self.current = True

    def invalidate(self) -> None:
        self.current = False


class FailingWriteIndex(MemoryBackedIndex):
    def synchronize_after_write(
        self,
        _receipt: WriteReceipt,
        _snapshot: MemorySnapshot,
    ) -> None:
        raise IndexUnavailableError("offline")


def test_index_failure_keeps_committed_memory(tmp_path: Path) -> None:
    core = _core(tmp_path, index=FailingWriteIndex())

    result = core.write(title="Durable topic", body="committed body")

    assert "committed to Git" in result
    assert "indexing is pending" in result
    assert core.repository.head() is not None
    assert core.repository._run(["rev-list", "--count", "HEAD"]).stdout.strip() == "1"
    assert core.store.snapshot().memories[0].body == "committed body"
    core.repository.assert_clean()


def test_push_lock_failure_is_best_effort(tmp_path: Path, monkeypatch) -> None:
    core = _core(tmp_path, git_remote="origin")

    @contextmanager
    def failed_push_lock():
        raise RepositoryError("push lock timeout")
        yield

    monkeypatch.setattr(core.locks, "push", failed_push_lock)

    result = core.write(title="Topic", body="Body")

    assert result == "Memory created in global and committed to Git."
    assert len(core.store.snapshot().memories) == 1


def test_disabled_remote_does_not_wait_for_push_lock(tmp_path: Path, monkeypatch) -> None:
    core = _core(tmp_path)

    @contextmanager
    def forbidden_push_lock():
        raise AssertionError("push lock should not be acquired")
        yield

    monkeypatch.setattr(core.locks, "push", forbidden_push_lock)
    assert "committed to Git" in core.write(title="Topic", body="Body")


def test_dirty_worktree_recall_uses_committed_snapshot(tmp_path: Path) -> None:
    core = _core(tmp_path)
    core.write(title="Stable topic", body="committed body")
    memory = core.store.snapshot().memories[0]
    target = core.repository.worktree_path(memory.relative_path)
    target.write_text(target.read_text(encoding="utf-8").replace("committed body", "dirty body"))

    index_text = core.list_index()
    recalled = core.recall(query="topic")

    assert "Stable topic" in index_text
    assert "committed body" in recalled
    assert "dirty body" not in recalled


def test_logs_do_not_include_body_or_query(tmp_path: Path, caplog) -> None:
    caplog.set_level(logging.INFO)
    core = _core(tmp_path)
    body = "BODY-SHOULD-NOT-APPEAR-73d2"
    query = "QUERY-SHOULD-NOT-APPEAR-a9f1"

    core.write(title="Private logging topic", body=body)
    core.recall(query=query)

    assert body not in caplog.text
    assert query not in caplog.text


def test_shared_recall_operations_overlap(tmp_path: Path) -> None:
    barrier = threading.Barrier(2)

    class ConcurrentIndex(MemoryBackedIndex):
        def search(
            self,
            snapshot: MemorySnapshot,
            query: str,
            project: str | None,
        ) -> list[Any]:
            barrier.wait(timeout=5)
            return super().search(snapshot, query, project)

    core = _core(tmp_path)
    core.write(title="Concurrent topic", body="Body")
    core.index = ConcurrentIndex()

    with ThreadPoolExecutor(max_workers=2) as executor:
        futures = [executor.submit(core.recall, query=f"query-{index}") for index in range(2)]
        results = [future.result(timeout=10) for future in futures]

    assert all("Concurrent topic" in result for result in results)


def test_rebuild_and_write_are_mutually_exclusive(tmp_path: Path) -> None:
    rebuild_entered = threading.Event()
    release_rebuild = threading.Event()

    class BlockingIndex(MemoryBackedIndex):
        def rebuild(self, _snapshot: MemorySnapshot) -> None:
            rebuild_entered.set()
            assert release_rebuild.wait(timeout=5)
            self.current = True

    index = BlockingIndex()
    core = _core(tmp_path, index=index)
    core.write(title="Existing topic", body="Body")
    index.current = False

    with ThreadPoolExecutor(max_workers=2) as executor:
        recall = executor.submit(core.recall, query="existing")
        assert rebuild_entered.wait(timeout=5)
        write = executor.submit(core.write, title="Second topic", body="Second body")
        time.sleep(0.2)
        assert not write.done()
        release_rebuild.set()
        assert "Existing topic" in recall.result(timeout=10)
        assert "committed to Git" in write.result(timeout=10)

    assert len(core.store.snapshot().memories) == 2


def test_project_index_lists_global_and_selected_project_only(tmp_path: Path) -> None:
    core = _core(tmp_path)
    core.write(title="Global topic", body="Global")
    core.write(title="Vexor topic", body="Vexor", project="vexor")
    core.write(title="Other topic", body="Other", project="other")

    result = core.list_index(project="VEXOR")

    assert "Global topic" in result
    assert "Project: vexor" in result
    assert "Vexor topic" in result
    assert "Other topic" not in result


def test_empty_and_invalid_recall_inputs_have_clear_results(tmp_path: Path) -> None:
    core = _core(tmp_path)
    assert core.recall(query="anything") == "No permanent memories have been written yet."
    with pytest.raises(MemoryValidationError, match="query is empty"):
        core.recall(query="  ")
    with pytest.raises(MemoryValidationError, match="project is invalid"):
        core.list_index(project="../escape")


def test_recall_with_no_matches_has_lightweight_message(tmp_path: Path) -> None:
    class EmptySearchIndex(MemoryBackedIndex):
        def search(
            self,
            _snapshot: MemorySnapshot,
            _query: str,
            _project: str | None,
        ) -> list[Any]:
            return []

    core = _core(tmp_path, index=EmptySearchIndex())
    core.write(title="Topic", body="Body")
    assert core.recall(query="missing") == "No matching permanent memories were found."


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
        ) -> list[Any]:
            raise IndexUnavailableError("search unavailable")

        def invalidate(self) -> None:
            self.invalidations += 1
            super().invalidate()

    index = FailingSearchIndex()
    core = _core(tmp_path, index=index)
    core.write(title="Topic", body="Body")

    with pytest.raises(IndexUnavailableError, match="search unavailable"):
        core.recall(query="topic")
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
    core.write(title="Topic", body="Body")

    assert "Topic" in core.recall(query="topic")
    assert index.rebuilds == 1


@pytest.mark.parametrize(
    ("outcome", "log_text"),
    [
        (PushOutcome(True, False, "failed"), "git_push=failed"),
        (PushOutcome(True, False, "timeout"), "git_push=timeout"),
        (PushOutcome(True, True, "pushed"), "git_push=succeeded"),
    ],
)
def test_push_outcomes_only_affect_logs(
    tmp_path: Path,
    monkeypatch,
    caplog,
    outcome: PushOutcome,
    log_text: str,
) -> None:
    caplog.set_level(logging.INFO)
    core = _core(tmp_path, git_remote="origin")
    monkeypatch.setattr(core.repository, "push", lambda _remote: outcome)

    result = core.write(title="Topic", body="Body")

    assert "committed to Git" in result
    assert log_text in caplog.text


def test_core_accepts_injected_repository_and_rejects_file_home(tmp_path: Path) -> None:
    core = _core(tmp_path)
    settings = RuntimeSettings(RuntimePaths(tmp_path / "home"), "cursor", None)
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
        PerennaCore(RuntimeSettings(RuntimePaths(bad_home), "codex", None))


def _core(
    tmp_path: Path,
    *,
    index: MemoryBackedIndex | None = None,
    git_remote: str | None = None,
) -> PerennaCore:
    settings = RuntimeSettings(
        paths=RuntimePaths(tmp_path / "home"),
        source="codex",
        git_remote=git_remote,
    )
    return PerennaCore(settings, index=index or MemoryBackedIndex())
