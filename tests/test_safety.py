from __future__ import annotations

import os
import stat
import subprocess
from pathlib import Path

import pytest

from perenna.errors import (
    IndexUnavailableError,
    MemoryValidationError,
    RepositoryDirtyError,
    RepositoryError,
)
from perenna.filesystem import atomic_replace
from perenna.git import GitRepository
from perenna.index import VexorIndex
from perenna.markdown import parse_memory
from perenna.models import (
    normalize_body,
    normalize_project,
    normalize_title,
    parse_timestamp,
    validate_ulid,
)
from perenna.store import MemoryStore


@pytest.mark.parametrize(
    "project",
    ["con", "NUL", "com1", "lpt9.log", "portable."],
)
def test_project_rejects_nonportable_windows_directory_names(project: str) -> None:
    with pytest.raises(ValueError, match="portable directory"):
        normalize_project(project)


def test_ulid_rejects_values_larger_than_128_bits() -> None:
    with pytest.raises(ValueError, match="valid ULID"):
        validate_ulid("8" + "0" * 25)


@pytest.mark.parametrize(
    ("field", "value"),
    [("title", "bad\x00title"), ("body", "bad\x00body")],
)
def test_memory_text_rejects_control_characters(field: str, value: str) -> None:
    normalizer = normalize_title if field == "title" else normalize_body
    with pytest.raises(ValueError, match="control character"):
        normalizer(value)


def test_timestamp_requires_rfc3339_separator_and_timezone() -> None:
    with pytest.raises(ValueError, match="RFC 3339"):
        parse_timestamp("2026-08-22 00:00:00")


def test_snapshot_pins_every_git_read_to_captured_commit(tmp_path: Path, monkeypatch) -> None:
    repository = GitRepository.initialize(tmp_path / "memory")
    store = MemoryStore(repository)
    store.create(
        title="Pinned",
        summary="A pinned memory.",
        body="Original",
        source="codex",
        project=None,
    )
    captured_head = repository.head()
    original_paths = repository.memory_paths_at_commit
    observed_commits: list[str] = []

    def move_head_after_capture(commit: str) -> list[str]:
        observed_commits.append(commit)
        repository._run(["commit", "--allow-empty", "--no-verify", "-m", "manual movement"])
        return original_paths(commit)

    original_read = repository.read_at_commit

    def observe_read(commit: str, path: str) -> str:
        observed_commits.append(commit)
        return original_read(commit, path)

    monkeypatch.setattr(repository, "memory_paths_at_commit", move_head_after_capture)
    monkeypatch.setattr(repository, "read_at_commit", observe_read)

    snapshot = store.snapshot()

    assert snapshot.commit == captured_head
    assert repository.head() != captured_head
    assert observed_commits == [captured_head, captured_head]
    assert snapshot.memories[0].body == "Original"


def test_unfinished_git_operation_blocks_write(tmp_path: Path) -> None:
    repository = GitRepository.initialize(tmp_path / "memory")
    store = MemoryStore(repository)
    store.create(
        title="Existing",
        summary="An existing memory.",
        body="Body",
        source="codex",
        project=None,
    )
    repository._git_path("MERGE_HEAD").write_text(f"{repository.head()}\n", encoding="ascii")

    with pytest.raises(RepositoryDirtyError, match="unfinished Git operation"):
        store.create(
            title="Second",
            summary="A second memory.",
            body="Body",
            source="codex",
            project=None,
        )


def test_perenna_commit_ignores_repository_hooks(tmp_path: Path) -> None:
    repository = GitRepository.initialize(tmp_path / "memory")
    hooks = tmp_path / "hooks"
    hooks.mkdir()
    hook = hooks / "pre-commit"
    hook.write_text("#!/bin/sh\nexit 1\n", encoding="ascii")
    hook.chmod(hook.stat().st_mode | stat.S_IXUSR)
    repository._run(["config", "--local", "core.hooksPath", os.fspath(hooks)])

    receipt = MemoryStore(repository).create(
        title="Hook-independent",
        summary="A hook-independent memory.",
        body="Body",
        source="codex",
        project=None,
    )

    assert receipt.commit == repository.head()
    assert repository.commit_paths(receipt.commit) == [receipt.memory.relative_path]


def test_git_subprocesses_never_inherit_mcp_stdin(tmp_path: Path, monkeypatch) -> None:
    repository = GitRepository(tmp_path)
    observed: dict[str, object] = {}

    def fake_run(*args, **kwargs):
        observed.update(kwargs)
        return subprocess.CompletedProcess(args[0], 0, "", "")

    monkeypatch.setattr(subprocess, "run", fake_run)
    repository._run(["status"], check=False)

    assert observed["stdin"] is subprocess.DEVNULL
    environment = observed["env"]
    assert isinstance(environment, dict)
    assert environment["GIT_TERMINAL_PROMPT"] == "0"
    assert environment["GCM_INTERACTIVE"] == "Never"


def test_committed_memory_must_be_a_regular_blob(tmp_path: Path) -> None:
    repository = GitRepository.initialize(tmp_path / "memory")
    memory_id = "01K00000000000000000000001"
    blob = subprocess.run(
        ["git", "hash-object", "-w", "--stdin"],
        cwd=repository.path,
        input="some-target",
        check=True,
        capture_output=True,
        text=True,
    ).stdout.strip()
    relative_path = f"global/{memory_id}.md"
    repository._run(["update-index", "--add", "--cacheinfo", f"120000,{blob},{relative_path}"])
    repository._run(["commit", "--quiet", "-m", "add linked memory"])

    with pytest.raises(RepositoryError, match="not a regular file"):
        MemoryStore(repository).snapshot()


def test_linked_worktree_is_not_accepted_as_independent_repository(tmp_path: Path) -> None:
    main = GitRepository.initialize(tmp_path / "main")
    main._run(["commit", "--allow-empty", "--no-verify", "-m", "initial"])
    main._run(["config", "--local", "user.name", "Repository Owner"])
    linked = tmp_path / "linked"
    main._run(["worktree", "add", "--quiet", "-b", "linked", os.fspath(linked)])

    with pytest.raises(RepositoryError, match="not an independent Git repository"):
        GitRepository.initialize(linked)
    assert main._run(["config", "--local", "user.name"]).stdout.strip() == "Repository Owner"


def test_memory_path_rejects_linked_parent_directory(tmp_path: Path) -> None:
    repository = GitRepository.initialize(tmp_path / "memory")
    projects = repository.path / "projects"
    real = projects / "real"
    real.mkdir(parents=True)
    linked = projects / "linked"
    try:
        linked.symlink_to(real, target_is_directory=True)
    except OSError:
        pytest.skip("creating directory symlinks is not available on this system")

    with pytest.raises(RepositoryError, match="filesystem link"):
        repository.worktree_path("projects/linked/01K00000000000000000000001.md")


@pytest.mark.skipif(os.name == "nt", reason="POSIX mode bits are not preserved by Windows")
def test_atomic_replace_preserves_existing_file_mode(tmp_path: Path) -> None:
    target = tmp_path / "memory.md"
    target.write_bytes(b"old")
    target.chmod(0o755)

    atomic_replace(target, b"new")

    assert stat.S_IMODE(target.stat().st_mode) == 0o755


def test_marker_filesystem_errors_are_reported_as_index_unavailable(
    tmp_path: Path,
    monkeypatch,
) -> None:
    index = VexorIndex(tmp_path / "index")

    def fail_unlink(*_args, **_kwargs):
        raise PermissionError("denied")

    monkeypatch.setattr(type(index.marker_path), "unlink", fail_unlink)
    with pytest.raises(IndexUnavailableError, match="index is unavailable"):
        index.invalidate()


def test_git_repository_ignores_host_repository_and_identity_overrides(
    tmp_path: Path,
    monkeypatch,
) -> None:
    other = GitRepository.initialize(tmp_path / "other")
    other._run(["commit", "--allow-empty", "--no-verify", "-m", "other initial"])
    other_head = other.head()
    injected_index = tmp_path / "injected-index"
    monkeypatch.setenv("GIT_DIR", os.fspath(other.path / ".git"))
    monkeypatch.setenv("GIT_WORK_TREE", os.fspath(other.path))
    monkeypatch.setenv("GIT_INDEX_FILE", os.fspath(injected_index))
    monkeypatch.setenv("GIT_AUTHOR_NAME", "Injected Author")
    monkeypatch.setenv("GIT_COMMITTER_NAME", "Injected Committer")
    monkeypatch.setenv("GIT_CONFIG_COUNT", "1")
    monkeypatch.setenv("GIT_CONFIG_KEY_0", "user.email")
    monkeypatch.setenv("GIT_CONFIG_VALUE_0", "injected@example.invalid")

    repository = GitRepository.initialize(tmp_path / "memory")
    MemoryStore(repository).create(
        title="Isolated",
        summary="An isolated memory.",
        body="Body",
        source="codex",
        project=None,
    )

    identity = repository._run(
        ["show", "-s", "--format=%an|%ae|%cn|%ce", "HEAD"]
    ).stdout.strip()
    assert identity == "Perenna|perenna@localhost|Perenna|perenna@localhost"
    assert repository.path != other.path
    assert other.head() == other_head
    assert not injected_index.exists()


def test_detached_head_refuses_memory_write(tmp_path: Path) -> None:
    repository = GitRepository.initialize(tmp_path / "memory")
    store = MemoryStore(repository)
    store.create(
        title="Attached",
        summary="An attached memory.",
        body="Body",
        source="codex",
        project=None,
    )
    repository._run(["checkout", "--quiet", "--detach", "HEAD"])
    original_head = repository.head()

    with pytest.raises(RepositoryError, match="not on a branch"):
        store.create(
            title="Detached",
            summary="A detached memory.",
            body="Body",
            source="codex",
            project=None,
        )

    assert repository.head() == original_head
    assert len(store.snapshot().memories) == 1


@pytest.mark.parametrize(
    "frontmatter_key",
    ["1", "? [complex]\n"],
)
def test_frontmatter_non_string_keys_return_recoverable_validation_error(
    frontmatter_key: str,
) -> None:
    memory_id = "01K00000000000000000000001"
    text = (
        "---\n"
        f"{frontmatter_key}: \"unexpected\"\n"
        f'id: "{memory_id}"\n'
        'title: "Title"\n'
        'summary: "What this memory covers."\n'
        'source: "codex"\n'
        'created_at: "2026-08-22T00:00:00.000000Z"\n'
        'updated_at: "2026-08-22T00:00:00.000000Z"\n'
        "---\n\nBody\n"
    )

    with pytest.raises(MemoryValidationError, match="frontmatter is not valid YAML"):
        parse_memory(text, f"global/{memory_id}.md")
