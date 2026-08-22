from __future__ import annotations

import os
import subprocess
import tempfile
from dataclasses import dataclass
from pathlib import Path, PurePosixPath

from perenna.errors import RepositoryDirtyError, RepositoryError

GIT_IDENTITY_NAME = "Perenna"
GIT_IDENTITY_EMAIL = "perenna@localhost"
PUSH_TIMEOUT_SECONDS = 15


@dataclass(frozen=True, slots=True)
class PushOutcome:
    attempted: bool
    succeeded: bool
    reason: str


class GitRepository:
    def __init__(self, path: Path) -> None:
        self.path = path.resolve(strict=False)

    @classmethod
    def initialize(cls, path: Path) -> GitRepository:
        resolved = path.resolve(strict=False)
        if resolved.exists() and not resolved.is_dir():
            raise RepositoryError(
                f"Memory repository path {resolved} is not a directory. "
                "Move that file or choose a different --home, then restart Perenna."
            )
        resolved.mkdir(parents=True, exist_ok=True)
        repo = cls(resolved)

        if not any(resolved.iterdir()):
            repo._run(["init", "--initial-branch=main"])
        result = repo._run(["rev-parse", "--show-toplevel"], check=False)
        common = repo._run(["rev-parse", "--git-common-dir"], check=False)
        git_directory = resolved / ".git"
        common_path = Path(common.stdout.strip())
        if not common_path.is_absolute():
            common_path = resolved / common_path
        if (
            result.returncode != 0
            or common.returncode != 0
            or not _same_path(Path(result.stdout.strip()), resolved)
            or not git_directory.is_dir()
            or git_directory.is_symlink()
            or git_directory.is_junction()
            or not _same_path(common_path, git_directory)
        ):
            raise RepositoryError(
                f"Memory directory {resolved} is not an independent Git repository. "
                "Perenna left its contents unchanged. Move them elsewhere or choose a "
                "different --home, then restart Perenna."
            )

        repo._run(["config", "--local", "user.name", GIT_IDENTITY_NAME])
        repo._run(["config", "--local", "user.email", GIT_IDENTITY_EMAIL])
        repo._run(["config", "--local", "commit.gpgSign", "false"])
        return repo

    def head(self) -> str | None:
        result = self._run(["rev-parse", "--verify", "HEAD"], check=False)
        return result.stdout.strip() if result.returncode == 0 else None

    def current_branch(self) -> str:
        result = self._run(["symbolic-ref", "--quiet", "--short", "HEAD"], check=False)
        branch = result.stdout.strip()
        if result.returncode != 0 or not branch:
            raise RepositoryError(
                f"Memory repository {self.path} is not on a branch. "
                "Check out a branch before writing memories."
            )
        return branch

    def assert_clean(self) -> None:
        result = self._run(["status", "--porcelain=v1", "--untracked-files=all"])
        if result.stdout:
            raise RepositoryDirtyError(
                f"Memory repository {self.path} has uncommitted changes. Perenna did not "
                "write anything. Commit, discard, or move those changes, then retry."
            )
        operation_paths = (
            "MERGE_HEAD",
            "CHERRY_PICK_HEAD",
            "REVERT_HEAD",
            "REBASE_HEAD",
            "rebase-apply",
            "rebase-merge",
            "sequencer",
            "BISECT_LOG",
        )
        if any(self._git_path(name).exists() for name in operation_paths):
            raise RepositoryDirtyError(
                f"Memory repository {self.path} has an unfinished Git operation. Perenna did "
                "not write anything. Finish or abort that operation, then retry."
            )

    def memory_paths_at_commit(self, commit: str) -> list[str]:
        result = self._run_bytes(
            ["ls-tree", "-r", "-z", commit, "--", "global", "projects"]
        )
        paths = []
        for raw_entry in result.stdout.split(b"\0"):
            if not raw_entry:
                continue
            header, separator, raw_path = raw_entry.partition(b"\t")
            fields = header.split()
            if not separator or len(fields) != 3:
                raise RepositoryError(
                    f"Git tree {commit} contains an unreadable entry. Inspect the memory "
                    "repository before retrying."
                )
            try:
                path = raw_path.decode("utf-8", errors="strict")
                mode = fields[0].decode("ascii", errors="strict")
                object_type = fields[1].decode("ascii", errors="strict")
            except UnicodeDecodeError as exc:
                raise RepositoryError(
                    f"Git tree {commit} contains a non-UTF-8 path or mode. Repair the repository "
                    "before retrying."
                ) from exc
            if not path.endswith(".md"):
                continue
            if object_type != "blob" or mode not in {"100644", "100755"}:
                raise RepositoryError(
                    f"Committed memory {path!r} is not a regular file. Replace it with a regular "
                    "UTF-8 Markdown file and commit the correction."
                )
            paths.append(path)
        return sorted(paths)

    def read_at_commit(self, commit: str, relative_path: str) -> str:
        _validate_relative_path(relative_path)
        result = self._run_bytes(["show", f"{commit}:{relative_path}"])
        try:
            return result.stdout.decode("utf-8", errors="strict")
        except UnicodeDecodeError as exc:
            raise RepositoryError(
                f"Committed memory {relative_path!r} is not UTF-8. Repair and commit the file, "
                "then retry."
            ) from exc

    def worktree_path(self, relative_path: str) -> Path:
        path = PurePosixPath(relative_path)
        _validate_relative_path(relative_path)
        candidate = self.path.joinpath(*path.parts)
        current = self.path
        for part in path.parts[:-1]:
            current /= part
            if current.is_symlink() or current.is_junction():
                raise RepositoryError(
                    f"Memory path {relative_path!r} passes through a filesystem link. Replace "
                    "the linked directory with a regular directory before retrying."
                )
        resolved_parent = candidate.parent.resolve(strict=False)
        try:
            if os.path.commonpath((self.path, resolved_parent)) != os.fspath(self.path):
                raise ValueError
        except (ValueError, OSError) as exc:
            raise RepositoryError(f"Memory path {relative_path!r} leaves the repository.") from exc
        return candidate

    def stage(self, relative_path: str) -> None:
        _validate_relative_path(relative_path)
        self._run(["add", "--", relative_path])

    def staged_paths(self) -> list[str]:
        result = self._run_bytes(["diff", "--cached", "--name-only", "-z"])
        return sorted(
            path
            for path in result.stdout.decode("utf-8", errors="strict").split("\0")
            if path
        )

    def commit(self, message: str, relative_path: str) -> str:
        staged = self.staged_paths()
        if staged != [relative_path]:
            raise RepositoryError(
                "Git index contains paths outside the requested memory write. "
                "Perenna stopped before committing; inspect the memory repository index."
            )
        with tempfile.TemporaryDirectory(prefix="perenna-hooks-") as hooks_path:
            self._run(
                [
                    "-c",
                    "commit.gpgSign=false",
                    "-c",
                    f"core.hooksPath={hooks_path}",
                    "commit",
                    "--quiet",
                    "--no-verify",
                    "-m",
                    message,
                ]
            )
        commit = self.head()
        if commit is None:
            raise RepositoryError("Git commit completed without producing a readable HEAD.")
        if self.commit_paths(commit) != [relative_path]:
            raise RepositoryError(
                "Git produced a commit containing paths outside the requested memory write. "
                "Perenna left the commit unchanged; inspect the memory repository before retrying."
            )
        return commit

    def commit_paths(self, commit: str) -> list[str]:
        result = self._run_bytes(
            ["diff-tree", "--root", "--no-commit-id", "--name-only", "-r", "-z", commit]
        )
        return sorted(
            path
            for path in result.stdout.decode("utf-8", errors="strict").split("\0")
            if path
        )

    def unstage(self, relative_path: str, previous_head: str | None) -> None:
        if previous_head is None:
            self._run(
                ["rm", "--cached", "--quiet", "--ignore-unmatch", "--", relative_path],
                check=False,
            )
        else:
            self._run(["reset", "--quiet", previous_head, "--", relative_path])

    def remote_names(self) -> set[str]:
        result = self._run(["remote"])
        return {line.strip() for line in result.stdout.splitlines() if line.strip()}

    def push(self, remote: str | None, timeout: int = PUSH_TIMEOUT_SECONDS) -> PushOutcome:
        if remote is None:
            return PushOutcome(False, False, "disabled")
        if remote not in self.remote_names():
            return PushOutcome(False, False, "remote-missing")
        if self.head() is None:
            return PushOutcome(False, False, "no-commit")

        branch = self.current_branch()
        upstream = self._run(
            ["rev-parse", "--abbrev-ref", "--symbolic-full-name", "@{upstream}"],
            check=False,
        )
        args = ["push", remote, branch]
        if upstream.returncode != 0:
            args = ["push", "--set-upstream", remote, branch]
        try:
            result = self._run(args, check=False, timeout=timeout)
        except subprocess.TimeoutExpired:
            return PushOutcome(True, False, "timeout")
        if result.returncode != 0:
            return PushOutcome(True, False, "failed")
        return PushOutcome(True, True, "pushed")

    def _git_path(self, name: str) -> Path:
        result = self._run(["rev-parse", "--git-path", name])
        path = Path(result.stdout.strip())
        return path if path.is_absolute() else self.path / path

    def _run(
        self,
        args: list[str],
        *,
        check: bool = True,
        timeout: int | None = None,
    ) -> subprocess.CompletedProcess[str]:
        try:
            result = subprocess.run(
                ["git", *args],
                cwd=self.path,
                check=False,
                capture_output=True,
                stdin=subprocess.DEVNULL,
                text=True,
                encoding="utf-8",
                errors="replace",
                env=_git_environment(),
                timeout=timeout,
            )
        except FileNotFoundError as exc:
            raise RepositoryError(
                "Git is not installed or is not available on PATH. Install Git, then restart "
                "Perenna."
            ) from exc
        if check and result.returncode != 0:
            raise RepositoryError(
                f"Git operation {args[0]!r} failed in {self.path}. Inspect the repository and "
                "Git configuration, then retry."
            )
        return result

    def _run_bytes(
        self,
        args: list[str],
        *,
        check: bool = True,
    ) -> subprocess.CompletedProcess[bytes]:
        try:
            result = subprocess.run(
                ["git", *args],
                cwd=self.path,
                check=False,
                capture_output=True,
                stdin=subprocess.DEVNULL,
                env=_git_environment(),
            )
        except FileNotFoundError as exc:
            raise RepositoryError(
                "Git is not installed or is not available on PATH. Install Git, then restart "
                "Perenna."
            ) from exc
        if check and result.returncode != 0:
            raise RepositoryError(
                f"Git operation {args[0]!r} failed in {self.path}. Inspect the repository and "
                "retry."
            )
        return result


def _validate_relative_path(relative_path: str) -> None:
    path = PurePosixPath(relative_path)
    if path.is_absolute() or not path.parts or any(part in {"", ".", ".."} for part in path.parts):
        raise RepositoryError(f"Memory path {relative_path!r} is not a safe relative path.")
    if "\\" in relative_path:
        raise RepositoryError(f"Memory path {relative_path!r} contains a backslash.")


def _same_path(left: Path, right: Path) -> bool:
    return os.path.normcase(os.fspath(left.resolve(strict=False))) == os.path.normcase(
        os.fspath(right.resolve(strict=False))
    )


def _git_environment() -> dict[str, str]:
    environment = os.environ.copy()
    repository_controls = {
        "GIT_ALTERNATE_OBJECT_DIRECTORIES",
        "GIT_ASKPASS",
        "GIT_CEILING_DIRECTORIES",
        "GIT_COMMON_DIR",
        "GIT_DEFAULT_HASH",
        "GIT_DIR",
        "GIT_DISCOVERY_ACROSS_FILESYSTEM",
        "GIT_EXEC_PATH",
        "GIT_GRAFT_FILE",
        "GIT_INDEX_FILE",
        "GIT_INTERNAL_SUPER_PREFIX",
        "GIT_NAMESPACE",
        "GIT_OBJECT_DIRECTORY",
        "GIT_PREFIX",
        "GIT_QUARANTINE_PATH",
        "GIT_REPLACE_REF_BASE",
        "GIT_SHALLOW_FILE",
        "GIT_TEMPLATE_DIR",
        "GIT_WORK_TREE",
        "SSH_ASKPASS",
    }
    for name in tuple(environment):
        if (
            name in repository_controls
            or name.startswith("GIT_AUTHOR_")
            or name.startswith("GIT_COMMITTER_")
            or name.startswith("GIT_CONFIG_")
        ):
            environment.pop(name, None)
    environment["GIT_TERMINAL_PROMPT"] = "0"
    environment["GCM_INTERACTIVE"] = "Never"
    environment["SSH_ASKPASS_REQUIRE"] = "never"
    return environment
