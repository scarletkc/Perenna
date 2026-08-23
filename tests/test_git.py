from __future__ import annotations

import subprocess
from collections.abc import Callable
from datetime import UTC, datetime
from pathlib import Path

import pytest

from perenna.config import RuntimePaths, RuntimeSettings
from perenna.core import PerennaCore
from perenna.errors import RepositoryError
from perenna.git import GIT_IDENTITY_EMAIL, GIT_IDENTITY_NAME, GitRepository, _git_environment
from perenna.markdown import memory_revision
from perenna.store import MemoryStore

MEMORY_ID = "01ARZ3NDEKTSV4RRFFQ69G5FAV"


def _write_one(repository: GitRepository) -> str:
    store = MemoryStore(
        repository,
        clock=lambda: datetime(2026, 8, 22, tzinfo=UTC),
        id_factory=lambda: MEMORY_ID,
    )
    return store.create(
        title="Fact",
        summary="A fact.",
        body="body",
        source="codex",
        project=None,
    ).commit


def test_core_initializes_runtime_directories_and_memory_repository(tmp_path: Path) -> None:
    home = tmp_path / "nested" / "perenna"
    settings = RuntimeSettings(RuntimePaths(home), source="codex", git_remote=None)

    core = PerennaCore(settings, index=object())  # type: ignore[arg-type]

    assert home.is_dir()
    assert settings.paths.memory.is_dir()
    assert settings.paths.index.is_dir()
    assert core.repository.current_branch() == "main"


def test_initialize_creates_main_repository_with_local_identity(
    tmp_path: Path,
    run_git: Callable[[Path, list[str]], subprocess.CompletedProcess[str]],
) -> None:
    path = tmp_path / "memory"

    repository = GitRepository.initialize(path)

    assert repository.current_branch() == "main"
    assert run_git(path, ["config", "--local", "user.name"]).stdout.strip() == GIT_IDENTITY_NAME
    assert (
        run_git(path, ["config", "--local", "user.email"]).stdout.strip()
        == GIT_IDENTITY_EMAIL
    )
    assert run_git(path, ["config", "--local", "commit.gpgSign"]).stdout.strip() == "false"


def test_initialize_accepts_an_empty_directory(tmp_path: Path) -> None:
    path = tmp_path / "memory"
    path.mkdir()

    repository = GitRepository.initialize(path)

    assert repository.path == path.resolve()
    assert (path / ".git").is_dir()


def test_initialize_refuses_nonempty_non_repository_without_overwriting(tmp_path: Path) -> None:
    path = tmp_path / "memory"
    path.mkdir()
    marker = path / "keep-me.txt"
    marker.write_text("user data", encoding="utf-8")

    with pytest.raises(RepositoryError, match="not an independent Git repository"):
        GitRepository.initialize(path)

    assert marker.read_text(encoding="utf-8") == "user data"
    assert not (path / ".git").exists()


def test_create_and_replace_create_two_commits(
    repository: GitRepository,
    run_git: Callable[[Path, list[str]], subprocess.CompletedProcess[str]],
) -> None:
    times = iter(
        (
            datetime(2026, 8, 22, 1, tzinfo=UTC),
            datetime(2026, 8, 22, 2, tzinfo=UTC),
        )
    )
    store = MemoryStore(
        repository,
        clock=lambda: next(times),
        id_factory=lambda: MEMORY_ID,
    )

    first = store.create(
        title="Fact",
        summary="A fact.",
        body="one",
        source="claude-code",
        project=None,
    )
    second = store.replace(
        memory_id=first.memory.id,
        base_revision=memory_revision(first.memory),
        summary="An updated fact.",
        body="two",
        source="cursor",
    )

    assert first.previous_commit is None
    assert second.previous_commit == first.commit
    assert run_git(repository.path, ["rev-list", "--count", "HEAD"]).stdout.strip() == "2"
    subjects = run_git(repository.path, ["log", "--format=%s"]).stdout.splitlines()
    assert subjects == ['memory(global): replace "Fact"', 'memory(global): create "Fact"']


def test_push_reports_disabled_and_missing_remote(repository: GitRepository) -> None:
    _write_one(repository)

    disabled = repository.push(None)
    missing = repository.push("origin")

    assert (disabled.attempted, disabled.succeeded, disabled.reason) == (
        False,
        False,
        "disabled",
    )
    assert (missing.attempted, missing.succeeded, missing.reason) == (
        False,
        False,
        "remote-missing",
    )


def test_first_push_to_local_bare_repository_sets_upstream(
    repository: GitRepository,
    tmp_path: Path,
    run_git: Callable[[Path, list[str]], subprocess.CompletedProcess[str]],
) -> None:
    commit = _write_one(repository)
    bare = tmp_path / "backup.git"
    subprocess.run(
        ["git", "init", "--bare", str(bare)],
        check=True,
        capture_output=True,
        text=True,
        encoding="utf-8",
    )
    repository._run(["remote", "add", "backup", str(bare)])

    outcome = repository.push("backup")

    assert (outcome.attempted, outcome.succeeded, outcome.reason) == (True, True, "pushed")
    assert run_git(repository.path, ["config", "branch.main.remote"]).stdout.strip() == "backup"
    remote_head = subprocess.run(
        ["git", "--git-dir", str(bare), "rev-parse", "refs/heads/main"],
        check=True,
        capture_output=True,
        text=True,
        encoding="utf-8",
    ).stdout.strip()
    assert remote_head == commit


def test_push_timeout_is_a_best_effort_failure(
    repository: GitRepository,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _write_one(repository)
    repository._run(["remote", "add", "origin", str(tmp_path / "unused.git")])
    original_run = repository._run

    def timeout_push(
        args: list[str],
        *,
        check: bool = True,
        timeout: int | None = None,
    ) -> subprocess.CompletedProcess[str]:
        if args[0] == "push":
            raise subprocess.TimeoutExpired(["git", *args], timeout)
        return original_run(args, check=check, timeout=timeout)

    monkeypatch.setattr(repository, "_run", timeout_push)

    outcome = repository.push("origin", timeout=1)

    assert (outcome.attempted, outcome.succeeded, outcome.reason) == (True, False, "timeout")


def test_push_command_failure_does_not_raise(repository: GitRepository, tmp_path: Path) -> None:
    _write_one(repository)
    repository._run(["remote", "add", "origin", str(tmp_path / "missing.git")])

    outcome = repository.push("origin")

    assert (outcome.attempted, outcome.succeeded, outcome.reason) == (True, False, "failed")


def test_git_environment_does_not_override_repository_deploy_key(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("GIT_SSH", "untrusted-ssh")
    monkeypatch.setenv("GIT_SSH_COMMAND", "untrusted ssh command")
    monkeypatch.setenv("GIT_SSH_VARIANT", "plink")

    environment = _git_environment()

    assert "GIT_SSH" not in environment
    assert "GIT_SSH_COMMAND" not in environment
    assert "GIT_SSH_VARIANT" not in environment
