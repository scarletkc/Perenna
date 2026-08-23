from __future__ import annotations

import hashlib
import os
import shutil
import tempfile
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Literal
from uuid import uuid4

from perenna.errors import SkillInstallError

SKILL_NAME = "perenna-memory"
SUPPORTED_AGENTS = ("codex", "claude-code")

_AGENT_SKILL_DIRECTORIES = {
    "codex": Path(".agents") / "skills",
    "claude-code": Path(".claude") / "skills",
}

InstallScope = Literal["user", "project"]
InstallState = Literal["installed", "already-installed", "replaced"]


@dataclass(frozen=True, slots=True)
class SkillInstallReport:
    agent: str
    scope: InstallScope
    destination: Path
    state: InstallState
    backup: Path | None = None


@dataclass(slots=True)
class _InstallPlan:
    agent: str
    destination: Path
    state: InstallState
    original_present: bool
    staging: Path | None = None
    backup: Path | None = None
    original_moved: bool = False
    new_installed: bool = False


def install_bundled_skill(
    agents: Sequence[str],
    *,
    scope: InstallScope = "user",
    replace: bool = False,
    user_home: Path | None = None,
    project_root: Path | None = None,
    source: Path | None = None,
) -> tuple[SkillInstallReport, ...]:
    """Install Perenna's bundled skill for one or more supported agents."""

    selected_agents = tuple(dict.fromkeys(agents))
    if not selected_agents:
        raise SkillInstallError("Choose at least one agent: codex or claude-code.")

    unsupported = [agent for agent in selected_agents if agent not in SUPPORTED_AGENTS]
    if unsupported:
        values = ", ".join(repr(agent) for agent in unsupported)
        raise SkillInstallError(
            f"Unsupported agent value: {values}. Choose codex or claude-code."
        )
    if scope not in ("user", "project"):
        raise SkillInstallError("Skill scope must be 'user' or 'project'.")

    skill_source = (source or _bundled_skill_path()).resolve()
    _validate_skill_source(skill_source)
    root = _installation_root(scope, user_home=user_home, project_root=project_root)

    plans = [_plan_install(agent, root, skill_source) for agent in selected_agents]
    conflicts = [plan.destination for plan in plans if plan.state == "replaced" and not replace]
    if conflicts:
        paths = ", ".join(str(path) for path in conflicts)
        raise SkillInstallError(
            f"The installed {SKILL_NAME} skill differs from the bundled copy at: {paths}. "
            "Re-run with --replace to back up and replace only those copies."
        )

    changed = [plan for plan in plans if plan.state != "already-installed"]
    try:
        for plan in changed:
            plan.staging = _stage_skill(skill_source, plan.destination)
        _apply_plans(changed)
    except OSError as exc:
        _clean_staging(changed)
        raise SkillInstallError(
            f"Could not install {SKILL_NAME}: {exc}. Check the destination permissions and retry."
        ) from exc

    return tuple(
        SkillInstallReport(
            agent=plan.agent,
            scope=scope,
            destination=plan.destination,
            state=plan.state,
            backup=plan.backup,
        )
        for plan in plans
    )


def _bundled_skill_path() -> Path:
    packaged = Path(__file__).with_name("_bundled") / "skills" / SKILL_NAME
    if packaged.is_dir():
        return packaged

    checkout = Path(__file__).resolve().parents[2] / "skills" / SKILL_NAME
    if checkout.is_dir():
        return checkout

    raise SkillInstallError(
        f"The installed Perenna package does not contain the bundled {SKILL_NAME} skill. "
        "Reinstall or upgrade Perenna, then retry."
    )


def _validate_skill_source(source: Path) -> None:
    if source.is_symlink() or not source.is_dir() or not (source / "SKILL.md").is_file():
        raise SkillInstallError(
            f"The bundled skill at {source} is incomplete. Reinstall or upgrade Perenna."
        )
    for entry in source.rglob("*"):
        if entry.is_symlink() or not (entry.is_dir() or entry.is_file()):
            raise SkillInstallError(
                f"The bundled skill contains an unsupported entry at {entry}. "
                "Reinstall or upgrade Perenna."
            )


def _installation_root(
    scope: InstallScope,
    *,
    user_home: Path | None,
    project_root: Path | None,
) -> Path:
    if scope == "user":
        return (user_home or Path.home()).expanduser().resolve()
    if project_root is not None:
        return project_root.expanduser().resolve()
    return _find_project_root(Path.cwd())


def _find_project_root(start: Path) -> Path:
    resolved = start.resolve()
    for candidate in (resolved, *resolved.parents):
        if os.path.lexists(candidate / ".git"):
            return candidate
    raise SkillInstallError(
        "Project-scoped skill installation requires a Git working tree. "
        "Run the command inside the target repository or use --scope user."
    )


def _plan_install(
    agent: str,
    root: Path,
    source: Path,
) -> _InstallPlan:
    destination = root / _AGENT_SKILL_DIRECTORIES[agent] / SKILL_NAME
    if not os.path.lexists(destination):
        return _InstallPlan(agent, destination, "installed", False)
    if _directories_match(source, destination):
        return _InstallPlan(agent, destination, "already-installed", True)
    return _InstallPlan(agent, destination, "replaced", True)


def _directories_match(source: Path, destination: Path) -> bool:
    if destination.is_symlink() or not destination.is_dir():
        return False
    try:
        return _directory_manifest(source) == _directory_manifest(destination)
    except OSError:
        return False


def _directory_manifest(root: Path) -> tuple[tuple[str, str, str], ...]:
    entries: list[tuple[str, str, str]] = []
    for entry in sorted(root.rglob("*"), key=lambda path: path.as_posix()):
        relative = entry.relative_to(root).as_posix()
        if entry.is_symlink():
            entries.append((relative, "symlink", ""))
        elif entry.is_dir():
            entries.append((relative, "directory", ""))
        elif entry.is_file():
            digest = hashlib.sha256(entry.read_bytes()).hexdigest()
            entries.append((relative, "file", digest))
        else:
            entries.append((relative, "other", ""))
    return tuple(entries)


def _stage_skill(source: Path, destination: Path) -> Path:
    destination.parent.mkdir(parents=True, exist_ok=True)
    staging_parent = destination.parent.parent
    staging = Path(
        tempfile.mkdtemp(prefix=f".{SKILL_NAME}-install-", dir=staging_parent)
    )
    try:
        shutil.copytree(source, staging, dirs_exist_ok=True)
        if not _directories_match(source, staging):
            raise OSError("the staged skill does not match the bundled source")
    except BaseException:
        shutil.rmtree(staging, ignore_errors=True)
        raise
    return staging


def _apply_plans(plans: Sequence[_InstallPlan]) -> None:
    applied: list[_InstallPlan] = []
    try:
        for plan in plans:
            assert plan.staging is not None
            applied.append(plan)
            if plan.original_present:
                plan.backup = _backup_path(plan.destination)
                plan.backup.parent.mkdir(parents=True, exist_ok=True)
                os.replace(plan.destination, plan.backup)
                plan.original_moved = True
            os.replace(plan.staging, plan.destination)
            plan.new_installed = True
            plan.staging = None
    except OSError as exc:
        rollback_failures = _rollback(applied)
        _clean_staging(plans)
        if rollback_failures:
            paths = ", ".join(str(path) for path in rollback_failures)
            raise OSError(f"{exc}; rollback also failed for: {paths}") from exc
        raise


def _backup_path(destination: Path) -> Path:
    timestamp = datetime.now(UTC).strftime("%Y%m%dT%H%M%S.%fZ")
    name = f"{SKILL_NAME}-{timestamp}-{uuid4().hex[:8]}"
    return destination.parent.parent / "skill-backups" / name


def _rollback(plans: Sequence[_InstallPlan]) -> list[Path]:
    failures: list[Path] = []
    for plan in reversed(plans):
        try:
            if plan.new_installed and os.path.lexists(plan.destination):
                _remove_path(plan.destination)
            if (
                plan.original_moved
                and plan.backup is not None
                and os.path.lexists(plan.backup)
            ):
                os.replace(plan.backup, plan.destination)
        except OSError:
            failures.append(plan.destination)
    return failures


def _clean_staging(plans: Sequence[_InstallPlan]) -> None:
    for plan in plans:
        if plan.staging is not None and os.path.lexists(plan.staging):
            try:
                _remove_path(plan.staging)
            except OSError:
                pass
            plan.staging = None


def _remove_path(path: Path) -> None:
    if path.is_symlink() or path.is_file():
        path.unlink()
    elif path.is_dir():
        shutil.rmtree(path)
    else:
        path.unlink()
