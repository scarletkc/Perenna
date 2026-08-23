from __future__ import annotations

from pathlib import Path

import pytest

from perenna import skill_installer
from perenna.errors import SkillInstallError
from perenna.skill_installer import SKILL_NAME, install_bundled_skill

SKILL_SOURCE = Path(__file__).parents[1] / "skills" / SKILL_NAME


def test_installs_for_codex_and_claude_without_touching_other_skills(tmp_path: Path) -> None:
    unrelated = tmp_path / ".agents" / "skills" / "other-skill" / "SKILL.md"
    unrelated.parent.mkdir(parents=True)
    unrelated.write_text("unrelated", encoding="utf-8")

    reports = install_bundled_skill(
        ["codex", "claude-code"],
        user_home=tmp_path,
        source=SKILL_SOURCE,
    )

    assert [(report.agent, report.state) for report in reports] == [
        ("codex", "installed"),
        ("claude-code", "installed"),
    ]
    assert reports[0].destination == tmp_path / ".agents" / "skills" / SKILL_NAME
    assert reports[1].destination == tmp_path / ".claude" / "skills" / SKILL_NAME
    assert (reports[0].destination / "SKILL.md").read_bytes() == (
        SKILL_SOURCE / "SKILL.md"
    ).read_bytes()
    assert (reports[1].destination / "references" / "curation.md").is_file()
    assert unrelated.read_text(encoding="utf-8") == "unrelated"
    assert not list((tmp_path / ".agents").glob(f".{SKILL_NAME}-install-*"))
    assert not list((tmp_path / ".claude").glob(f".{SKILL_NAME}-install-*"))


def test_install_is_idempotent_and_deduplicates_agents(tmp_path: Path) -> None:
    first = install_bundled_skill(
        ["codex", "codex"],
        user_home=tmp_path,
        source=SKILL_SOURCE,
    )
    second = install_bundled_skill(
        ["codex"],
        user_home=tmp_path,
        source=SKILL_SOURCE,
    )

    assert len(first) == 1
    assert first[0].state == "installed"
    assert second[0].state == "already-installed"
    assert second[0].backup is None


def test_uses_the_repository_skill_when_running_from_source(tmp_path: Path) -> None:
    report = install_bundled_skill(["codex"], user_home=tmp_path)[0]

    assert report.state == "installed"
    assert (report.destination / "SKILL.md").read_bytes() == (
        SKILL_SOURCE / "SKILL.md"
    ).read_bytes()


@pytest.mark.parametrize(
    ("agents", "scope", "message"),
    [
        ([], "user", "Choose at least one agent"),
        (["cursor"], "user", "Unsupported agent value"),
        (["codex"], "machine", "scope must be"),
    ],
)
def test_rejects_unsupported_install_targets(agents, scope, message) -> None:
    with pytest.raises(SkillInstallError, match=message):
        install_bundled_skill(agents, scope=scope, source=SKILL_SOURCE)


def test_conflict_preflight_leaves_every_target_unchanged(tmp_path: Path) -> None:
    installed = install_bundled_skill(
        ["codex"],
        user_home=tmp_path,
        source=SKILL_SOURCE,
    )[0].destination
    installed_skill = installed / "SKILL.md"
    installed_skill.write_text("locally modified", encoding="utf-8")
    claude_destination = tmp_path / ".claude" / "skills" / SKILL_NAME

    with pytest.raises(SkillInstallError, match="--replace"):
        install_bundled_skill(
            ["claude-code", "codex"],
            user_home=tmp_path,
            source=SKILL_SOURCE,
        )

    assert not claude_destination.exists()
    assert installed_skill.read_text(encoding="utf-8") == "locally modified"


def test_replace_backs_up_modified_copy_outside_the_skill_scan_path(tmp_path: Path) -> None:
    installed = install_bundled_skill(
        ["claude-code"],
        user_home=tmp_path,
        source=SKILL_SOURCE,
    )[0].destination
    modified = installed / "SKILL.md"
    modified.write_text("locally modified", encoding="utf-8")

    report = install_bundled_skill(
        ["claude-code"],
        user_home=tmp_path,
        source=SKILL_SOURCE,
        replace=True,
    )[0]

    assert report.state == "replaced"
    assert report.backup is not None
    assert report.backup.parent == tmp_path / ".claude" / "skill-backups"
    assert (report.backup / "SKILL.md").read_text(encoding="utf-8") == "locally modified"
    assert modified.read_bytes() == (SKILL_SOURCE / "SKILL.md").read_bytes()


def test_replace_backs_up_a_conflicting_file(tmp_path: Path) -> None:
    destination = tmp_path / ".agents" / "skills" / SKILL_NAME
    destination.parent.mkdir(parents=True)
    destination.write_text("not a skill directory", encoding="utf-8")

    report = install_bundled_skill(
        ["codex"],
        user_home=tmp_path,
        source=SKILL_SOURCE,
        replace=True,
    )[0]

    assert report.state == "replaced"
    assert report.backup is not None
    assert report.backup.read_text(encoding="utf-8") == "not a skill directory"
    assert (destination / "SKILL.md").is_file()


def test_project_scope_uses_the_git_worktree_root(tmp_path: Path, monkeypatch) -> None:
    project = tmp_path / "project"
    nested = project / "packages" / "app"
    (project / ".git").mkdir(parents=True)
    nested.mkdir(parents=True)
    monkeypatch.chdir(nested)

    reports = install_bundled_skill(
        ["codex", "claude-code"],
        scope="project",
        source=SKILL_SOURCE,
    )

    assert reports[0].destination == project / ".agents" / "skills" / SKILL_NAME
    assert reports[1].destination == project / ".claude" / "skills" / SKILL_NAME


def test_project_scope_requires_a_git_worktree(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.chdir(tmp_path)

    with pytest.raises(SkillInstallError, match="Git working tree"):
        install_bundled_skill(["codex"], scope="project", source=SKILL_SOURCE)


def test_project_scope_accepts_an_explicit_project_root(tmp_path: Path) -> None:
    project = tmp_path / "not-yet-a-git-worktree"

    report = install_bundled_skill(
        ["codex"],
        scope="project",
        project_root=project,
        source=SKILL_SOURCE,
    )[0]

    assert report.destination == project / ".agents" / "skills" / SKILL_NAME


def test_rejects_an_incomplete_bundled_skill(tmp_path: Path) -> None:
    source = tmp_path / "incomplete"
    source.mkdir()

    with pytest.raises(SkillInstallError, match="incomplete"):
        install_bundled_skill(["codex"], user_home=tmp_path, source=source)


def test_rolls_back_new_targets_when_a_later_atomic_move_fails(
    tmp_path: Path,
    monkeypatch,
) -> None:
    original_replace = skill_installer.os.replace
    claude_destination = tmp_path / ".claude" / "skills" / SKILL_NAME

    def fail_second_install(source, destination):
        if Path(destination) == claude_destination:
            raise OSError("injected move failure")
        original_replace(source, destination)

    monkeypatch.setattr(skill_installer.os, "replace", fail_second_install)

    with pytest.raises(SkillInstallError, match="injected move failure"):
        install_bundled_skill(
            ["codex", "claude-code"],
            user_home=tmp_path,
            source=SKILL_SOURCE,
        )

    assert not (tmp_path / ".agents" / "skills" / SKILL_NAME).exists()
    assert not claude_destination.exists()


def test_failed_backup_move_preserves_the_existing_copy(
    tmp_path: Path,
    monkeypatch,
) -> None:
    destination = install_bundled_skill(
        ["codex"],
        user_home=tmp_path,
        source=SKILL_SOURCE,
    )[0].destination
    modified = destination / "SKILL.md"
    modified.write_text("keep this copy", encoding="utf-8")
    original_replace = skill_installer.os.replace

    def fail_backup_move(source, target):
        if Path(source) == destination:
            raise OSError("injected backup failure")
        original_replace(source, target)

    monkeypatch.setattr(skill_installer.os, "replace", fail_backup_move)

    with pytest.raises(SkillInstallError, match="injected backup failure"):
        install_bundled_skill(
            ["codex"],
            user_home=tmp_path,
            source=SKILL_SOURCE,
            replace=True,
        )

    assert modified.read_text(encoding="utf-8") == "keep this copy"
