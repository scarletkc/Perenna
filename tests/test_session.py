from __future__ import annotations

from pathlib import Path

import pytest

from perenna import cli
from perenna.config import RuntimePaths, RuntimeSettings
from perenna.core import PerennaCore
from perenna.errors import (
    ConfigurationError,
    MemoryConflictError,
    MemoryNotFoundError,
    MemoryValidationError,
    RepositoryError,
)
from perenna.markdown import memory_revision
from perenna.models import (
    MemorySnapshot,
    MutationReceipt,
    SearchMatch,
    SearchPassage,
    SearchResults,
)
from perenna.session import (
    discard_session,
    list_sessions,
    normalize_session_name,
    plan_promotion,
    promote_session,
    start_session,
)


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


def _core(home: Path) -> PerennaCore:
    settings = RuntimeSettings(RuntimePaths(home), None)
    return PerennaCore(settings, index=MemoryBackedIndex())


def _checkout(repository, branch: str) -> None:
    repository._run(["checkout", "--quiet", branch])


def _revision(core: PerennaCore, memory_id: str) -> str:
    return core.get(memory_id=memory_id)["memory"]["revision"]


@pytest.mark.parametrize(
    "value",
    ["", "..", "a/b", "has space", "con", "lpt9", "a" * 65],
)
def test_normalize_session_name_rejects_invalid(value: str) -> None:
    with pytest.raises(ConfigurationError, match="Session name is invalid"):
        normalize_session_name(value)


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        ("MyChat-42", "mychat-42"),
        ("  MyChat  ", "mychat"),
        ("A.B_C-D", "a.b_c-d"),
        ("a" * 64, "a" * 64),
    ],
)
def test_normalize_session_name_accepts_and_normalizes(value: str, expected: str) -> None:
    assert normalize_session_name(value) == expected


def test_start_creates_session_branch_and_list_reports(tmp_path: Path) -> None:
    core = _core(tmp_path / "home")
    core.create(title="Stable topic", summary="A fact.", body="Body", project=None)

    info = start_session(core.repository, "chat-42")

    assert info.name == "session/chat-42"
    assert info.commit == core.repository.head()
    assert core.repository.branch_exists("session/chat-42")
    assert [(s.name, s.commit) for s in list_sessions(core.repository)] == [
        ("session/chat-42", info.commit)
    ]


def test_start_refuses_existing_branch(tmp_path: Path) -> None:
    core = _core(tmp_path / "home")
    core.create(title="Stable topic", summary="A fact.", body="Body", project=None)
    start_session(core.repository, "dup")

    with pytest.raises(RepositoryError, match="perenna session discard dup"):
        start_session(core.repository, "dup")


def test_start_requires_committed_memory(tmp_path: Path) -> None:
    core = _core(tmp_path / "home")

    with pytest.raises(RepositoryError, match="no commits"):
        start_session(core.repository, "first")


def test_list_reports_no_sessions(tmp_path: Path) -> None:
    core = _core(tmp_path / "home")
    core.create(title="Stable topic", summary="A fact.", body="Body", project=None)

    assert list_sessions(core.repository) == []


def test_promote_preview_lists_plan_without_applying(tmp_path: Path) -> None:
    core = _core(tmp_path / "home")
    core.create(title="Stable topic", summary="A fact.", body="Original", project=None)
    start_session(core.repository, "work")
    _checkout(core.repository, "session/work")
    session_receipt = core.create(
        title="Session fact",
        summary="From the session.",
        body="Draft.",
        project="demo",
    )
    session_path = session_receipt["memory"]["memory_id"]
    _checkout(core.repository, "main")

    plan, results = promote_session(core.repository, core, "work", apply=False)

    assert plan.base_branch == "main"
    assert [(item.operation, item.path) for item in plan.items] == [
        ("create", f"projects/demo/{session_path}.md")
    ]
    assert results == []
    listed = core.list_memories(project="demo")
    assert all(memory["title"] != "Session fact" for memory in listed["memories"])


def test_promote_apply_replays_create_replace_delete(tmp_path: Path) -> None:
    core = _core(tmp_path / "home")
    alpha = core.create(title="Alpha", summary="A fact.", body="Original", project=None)
    doomed = core.create(title="Doomed", summary="Going away.", body="Gone.", project=None)
    start_session(core.repository, "work")
    _checkout(core.repository, "session/work")
    core.replace(
        memory_id=alpha["memory"]["memory_id"],
        base_revision=_revision(core, alpha["memory"]["memory_id"]),
        summary="A fact.",
        body="Updated on the session branch.",
    )
    core.create(
        title="Beta",
        summary="From the session.",
        body="Draft.",
        project="demo",
    )
    core.delete(
        memory_id=doomed["memory"]["memory_id"],
        expected_title="Doomed",
        base_revision=_revision(core, doomed["memory"]["memory_id"]),
    )
    _checkout(core.repository, "main")

    plan, results = promote_session(core.repository, core, "work", apply=True)

    assert sorted(item.operation for item in plan.items) == ["create", "delete", "replace"]
    assert len(results) == 3
    assert all(payload["changed"] is True for _, payload in results)
    alpha_after = core.get(memory_id=alpha["memory"]["memory_id"])["memory"]
    assert alpha_after["body"] == "Updated on the session branch."
    demo_refs = core.list_memories(project="demo")["memories"]
    beta_ref = next(ref for ref in demo_refs if ref["title"] == "Beta")
    beta_after = core.get(memory_id=beta_ref["memory_id"])["memory"]
    assert beta_after["scope"] == "project:demo"
    assert beta_after["body"] == "Draft."
    with pytest.raises(MemoryNotFoundError, match="was not found"):
        core.get(memory_id=doomed["memory"]["memory_id"])


def test_promote_apply_is_idempotent_on_rerun(tmp_path: Path) -> None:
    core = _core(tmp_path / "home")
    alpha = core.create(title="Alpha", summary="A fact.", body="Original", project=None)
    start_session(core.repository, "work")
    _checkout(core.repository, "session/work")
    core.replace(
        memory_id=alpha["memory"]["memory_id"],
        base_revision=_revision(core, alpha["memory"]["memory_id"]),
        summary="A fact.",
        body="Updated.",
    )
    core.create(title="Beta", summary="From the session.", body="Draft.", project=None)
    _checkout(core.repository, "main")

    first_plan, first_results = promote_session(core.repository, core, "work", apply=True)
    assert sorted(item.operation for item in first_plan.items) == ["create", "replace"]
    assert len(first_results) == 2
    assert all(payload["changed"] is True for _, payload in first_results)
    head_after_first = core.repository.head()

    second_plan, second_results = promote_session(core.repository, core, "work", apply=True)
    assert sorted(item.operation for item in second_plan.items) == ["create", "replace"]
    assert [payload["changed"] for _, payload in second_results] == [False, False]
    assert core.repository.head() == head_after_first


def test_promote_rerun_skips_already_deleted_memory(tmp_path: Path) -> None:
    core = _core(tmp_path / "home")
    doomed = core.create(title="Doomed", summary="Going away.", body="Gone.", project=None)
    start_session(core.repository, "work")
    _checkout(core.repository, "session/work")
    core.delete(
        memory_id=doomed["memory"]["memory_id"],
        expected_title="Doomed",
        base_revision=_revision(core, doomed["memory"]["memory_id"]),
    )
    _checkout(core.repository, "main")

    first_plan, first_results = promote_session(core.repository, core, "work", apply=True)
    assert [item.operation for item in first_plan.items] == ["delete"]
    assert len(first_results) == 1

    second_plan, second_results = promote_session(core.repository, core, "work", apply=True)
    assert second_plan.items == ()
    assert second_results == []


def test_promote_refuses_checked_out_session(tmp_path: Path) -> None:
    core = _core(tmp_path / "home")
    core.create(title="Stable topic", summary="A fact.", body="Body", project=None)
    start_session(core.repository, "work")
    _checkout(core.repository, "session/work")

    with pytest.raises(RepositoryError, match="is checked out"):
        plan_promotion(core.repository, "work")


def test_promote_refuses_missing_session(tmp_path: Path) -> None:
    core = _core(tmp_path / "home")
    core.create(title="Stable topic", summary="A fact.", body="Body", project=None)

    with pytest.raises(RepositoryError, match="does not exist"):
        plan_promotion(core.repository, "ghost")


def test_promote_rejects_invalid_session_memory(tmp_path: Path) -> None:
    core = _core(tmp_path / "home")
    core.create(title="Stable topic", summary="A fact.", body="Body", project=None)
    start_session(core.repository, "work")
    _checkout(core.repository, "session/work")
    target = core.repository.worktree_path("global/01ARZ3NDEKTSV4RRFFQ69G5FAV.md")
    target.write_text("not a memory file", encoding="utf-8")
    core.repository._run(["add", "--", "global/01ARZ3NDEKTSV4RRFFQ69G5FAV.md"])
    core.repository._run(["commit", "--quiet", "--no-verify", "-m", "draft"])
    _checkout(core.repository, "main")

    with pytest.raises(MemoryValidationError, match="invalid memory at global/"):
        plan_promotion(core.repository, "work")


def test_promote_rejects_renamed_memory_file(tmp_path: Path) -> None:
    core = _core(tmp_path / "home")
    first = core.create(title="Stable topic", summary="A fact.", body="Body", project=None)
    start_session(core.repository, "work")
    _checkout(core.repository, "session/work")
    old_path = f"global/{first['memory']['memory_id']}.md"
    new_path = "global/01ARZ3NDEKTSV4RRFFQ69G5FAV.md"
    core.repository._run(["mv", old_path, new_path])
    core.repository._run(["add", "-A"])
    core.repository._run(["commit", "--quiet", "--no-verify", "-m", "rename"])
    _checkout(core.repository, "main")

    with pytest.raises(
        MemoryValidationError,
        match="invalid memory at global/01ARZ3NDEKTSV4RRFFQ69G5FAV",
    ):
        plan_promotion(core.repository, "work")


def test_promote_skips_non_markdown_files(tmp_path: Path) -> None:
    core = _core(tmp_path / "home")
    core.create(title="Stable topic", summary="A fact.", body="Body", project=None)
    start_session(core.repository, "work")
    _checkout(core.repository, "session/work")
    scratch = core.repository.worktree_path("global/scratch.txt")
    scratch.write_text("not a memory", encoding="utf-8")
    core.repository._run(["add", "--", "global/scratch.txt"])
    core.repository._run(["commit", "--quiet", "--no-verify", "-m", "scratch"])
    session_receipt = core.create(
        title="Session fact",
        summary="From the session.",
        body="Draft.",
        project="demo",
    )
    session_path = session_receipt["memory"]["memory_id"]
    _checkout(core.repository, "main")

    plan = plan_promotion(core.repository, "work")

    assert [(item.operation, item.path) for item in plan.items] == [
        ("create", f"projects/demo/{session_path}.md")
    ]


def test_promote_replace_reports_missing_base_target(tmp_path: Path) -> None:
    core = _core(tmp_path / "home")
    alpha = core.create(title="Alpha", summary="A fact.", body="Original", project=None)
    start_session(core.repository, "work")
    _checkout(core.repository, "session/work")
    core.replace(
        memory_id=alpha["memory"]["memory_id"],
        base_revision=_revision(core, alpha["memory"]["memory_id"]),
        summary="A fact.",
        body="Updated on the session branch.",
    )
    _checkout(core.repository, "main")
    core.delete(
        memory_id=alpha["memory"]["memory_id"],
        expected_title="Alpha",
        base_revision=_revision(core, alpha["memory"]["memory_id"]),
    )

    with pytest.raises(
        MemoryConflictError,
        match=f"edits 'global/{alpha['memory']['memory_id']}.md'",
    ):
        promote_session(core.repository, core, "work", apply=True)


def test_discard_deletes_session_branch(tmp_path: Path) -> None:
    core = _core(tmp_path / "home")
    core.create(title="Stable topic", summary="A fact.", body="Body", project=None)
    start_session(core.repository, "work")

    branch = discard_session(core.repository, "work")

    assert branch == "session/work"
    assert not core.repository.branch_exists("session/work")


def test_discard_refuses_checked_out_and_missing(tmp_path: Path) -> None:
    core = _core(tmp_path / "home")
    core.create(title="Stable topic", summary="A fact.", body="Body", project=None)
    start_session(core.repository, "work")
    _checkout(core.repository, "session/work")

    with pytest.raises(RepositoryError, match="checked out"):
        discard_session(core.repository, "work")

    _checkout(core.repository, "main")
    with pytest.raises(RepositoryError, match="does not exist"):
        discard_session(core.repository, "ghost")


def test_session_cli_start_list_discard(tmp_path: Path, capsys, monkeypatch) -> None:
    monkeypatch.delenv("PERENNA_GIT_REMOTE", raising=False)
    home = tmp_path / "home"
    core = _core(home)
    core.create(title="Stable topic", summary="A fact.", body="Body", project=None)

    assert cli.main(["session", "list", "--home", str(home)]) == 0
    assert "No session branches." in capsys.readouterr().out

    assert cli.main(["session", "start", "chat-1", "--home", str(home)]) == 0
    out = capsys.readouterr().out
    assert "Started session branch session/chat-1" in out
    assert "perenna session promote chat-1 --apply" in out

    assert cli.main(["session", "list", "--home", str(home)]) == 0
    out = capsys.readouterr().out
    assert "Session: session/chat-1 (" in out

    assert cli.main(["session", "discard", "chat-1", "--home", str(home)]) == 0
    assert "Discarded session branch session/chat-1" in capsys.readouterr().out


def test_session_cli_promote_preview_then_apply(tmp_path: Path, capsys, monkeypatch) -> None:
    monkeypatch.delenv("PERENNA_GIT_REMOTE", raising=False)
    home = tmp_path / "home"
    core = _core(home)
    core.create(title="Stable topic", summary="A fact.", body="Original", project=None)
    start_session(core.repository, "work")
    _checkout(core.repository, "session/work")
    core.create(title="Beta", summary="From the session.", body="Draft.", project="demo")
    _checkout(core.repository, "main")

    def fake_core(settings):
        assert settings.paths.home == home.resolve()
        return core

    monkeypatch.setattr(cli, "PerennaCore", fake_core)

    assert cli.main(["session", "promote", "work", "--home", str(home)]) == 0
    out = capsys.readouterr().out
    assert "Planned memory changes (1)" in out
    assert "Preview only" in out
    assert all(
        memory["title"] != "Beta" for memory in core.list_memories(project="demo")["memories"]
    )

    assert cli.main(["session", "promote", "work", "--apply", "--home", str(home)]) == 0
    out = capsys.readouterr().out
    assert "create: 'Beta'" in out
    assert "Promoted 1 memory change(s) to main." in out
    demo_titles = [m["title"] for m in core.list_memories(project="demo")["memories"]]
    assert "Beta" in demo_titles
