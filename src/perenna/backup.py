from __future__ import annotations

import hashlib
import os
import re
import subprocess
from dataclasses import dataclass
from pathlib import Path
from urllib.parse import quote, urlsplit

from perenna.errors import ConfigurationError, RepositoryError
from perenna.git import GitRepository


@dataclass(frozen=True, slots=True)
class BackupReport:
    repository: Path
    remote_name: str
    remote_url: str
    branch: str
    repository_access: str
    write_access: str
    state: str
    authentication: str | None = None
    deploy_key_fingerprint: str | None = None
    deploy_key_public_key: str | None = None
    deploy_key_settings_url: str | None = None


@dataclass(frozen=True, slots=True)
class DeployKey:
    private_key: Path
    public_key: str
    fingerprint: str
    known_hosts: Path
    created: bool


def setup_backup(
    memory_path: Path,
    repository_url: str,
    *,
    remote_name: str | None,
    replace: bool,
    deploy_key: bool = False,
) -> BackupReport:
    if remote_name is None:
        raise ConfigurationError(
            "Automatic Git backup is disabled because PERENNA_GIT_REMOTE is empty. Remove the "
            "empty override from the Perenna host configuration, then retry."
        )
    url = _validated_repository_url(repository_url)
    if deploy_key:
        _require_ssh_repository_url(url)
    repository = GitRepository.initialize(memory_path)
    previous_url = repository.remote_url(remote_name)
    if previous_url is not None and previous_url != url and not replace:
        raise RepositoryError(
            f"Git remote {remote_name!r} already points to {previous_url!r}. Perenna left it "
            "unchanged; pass --replace to replace that address explicitly."
        )
    if not deploy_key and repository.deploy_key_path() is not None:
        raise ConfigurationError(
            f"Git remote {remote_name!r} is configured to use a repository-specific deploy key. "
            "Repeat setup with --deploy-key so Perenna verifies and reports the effective "
            "authentication method."
        )

    branch = repository.current_branch()
    head = repository.head()
    key = None
    changed = previous_url != url
    if deploy_key:
        key = _prepare_deploy_key(memory_path.parent, url)
        if changed:
            repository.set_remote_url(remote_name, url)
        repository.configure_deploy_key(key.private_key, key.known_hosts)
        if key.created:
            return _deploy_key_pending_report(repository, remote_name, url, branch, key)
        try:
            heads = repository.remote_heads(url)
        except RepositoryError:
            return _deploy_key_pending_report(repository, remote_name, url, branch, key)
    else:
        heads = repository.remote_heads(url)
    _require_compatible_remote(heads, branch, head)
    if head is not None:
        repository.verify_push(url, branch)

    if changed:
        repository.set_remote_url(remote_name, url)
    try:
        if head is None:
            return BackupReport(
                repository=repository.path,
                remote_name=remote_name,
                remote_url=url,
                branch=branch,
                repository_access="ok",
                write_access="pending",
                state="pending-first-commit",
                authentication="deploy-key" if key is not None else None,
                deploy_key_fingerprint=key.fingerprint if key is not None else None,
            )

        outcome = repository.push(remote_name)
        if not outcome.succeeded:
            remote_head = repository.remote_heads(url).get(branch)
            if remote_head != head:
                configuration_result = (
                    "restored the previous remote configuration"
                    if changed
                    else "left the existing remote configuration unchanged"
                )
                raise RepositoryError(
                    f"Git could not complete the initial backup of branch {branch!r} "
                    f"({outcome.reason}). Perenna {configuration_result}; "
                    "check the network, credentials, and branch rules, then retry."
                )
        return BackupReport(
            repository=repository.path,
            remote_name=remote_name,
            remote_url=url,
            branch=branch,
            repository_access="ok",
            write_access="ok",
            state="synchronized",
            authentication="deploy-key" if key is not None else None,
            deploy_key_fingerprint=key.fingerprint if key is not None else None,
        )
    except Exception:
        if changed:
            _restore_remote(repository, remote_name, previous_url)
        raise


def inspect_backup(memory_path: Path, *, remote_name: str | None) -> BackupReport | None:
    repository = GitRepository.open(memory_path)
    if remote_name is None:
        return None
    url = repository.remote_url(remote_name)
    if url is None:
        raise RepositoryError(
            f"Automatic backup uses Git remote {remote_name!r}, but that remote is missing from "
            f"{repository.path}. Run 'perenna backup setup REPOSITORY_URL' to configure it."
        )

    branch = repository.current_branch()
    head = repository.head()
    key = _configured_deploy_key(repository)
    try:
        heads = repository.remote_heads(url)
    except RepositoryError as exc:
        if key is None:
            raise
        raise RepositoryError(
            "Git could not access the backup repository with its configured deploy key. "
            "Confirm the public key is registered, the network is available, and the recorded "
            "SSH host key is current, then retry."
        ) from exc
    _require_compatible_remote(heads, branch, head)
    if head is None:
        return BackupReport(
            repository=repository.path,
            remote_name=remote_name,
            remote_url=url,
            branch=branch,
            repository_access="ok",
            write_access="pending",
            state="pending-first-commit",
            authentication="deploy-key" if key is not None else None,
            deploy_key_fingerprint=key.fingerprint if key is not None else None,
        )

    repository.verify_push(url, branch)
    state = "synchronized" if heads.get(branch) == head else "pending-push"
    return BackupReport(
        repository=repository.path,
        remote_name=remote_name,
        remote_url=url,
        branch=branch,
        repository_access="ok",
        write_access="ok",
        state=state,
        authentication="deploy-key" if key is not None else None,
        deploy_key_fingerprint=key.fingerprint if key is not None else None,
    )


def _prepare_deploy_key(home: Path, repository_url: str) -> DeployKey:
    key_id = hashlib.sha256(repository_url.encode("utf-8")).hexdigest()[:16]
    directory = home / "credentials" / "git" / key_id
    _ensure_private_directory(directory)
    private_key = directory / "id_ed25519"
    public_key_path = directory / "id_ed25519.pub"
    known_hosts = directory / "known_hosts"
    for path in (private_key, public_key_path, known_hosts):
        if path.is_symlink() or path.is_junction():
            raise RepositoryError(
                f"Deploy-key path {path} is a filesystem link. Replace it with a regular file, "
                "then retry."
            )

    private_exists = private_key.exists()
    public_exists = public_key_path.exists()
    if private_exists != public_exists:
        raise RepositoryError(
            f"Deploy-key files are incomplete in {directory}. Restore both id_ed25519 files or "
            "move the directory aside, then retry."
        )
    if private_exists and (not private_key.is_file() or not public_key_path.is_file()):
        raise RepositoryError(
            f"Deploy-key paths in {directory} are not regular files. Move the credential "
            "directory aside, then retry."
        )
    if known_hosts.exists() and not known_hosts.is_file():
        raise RepositoryError(
            f"Deploy-key host file {known_hosts} is not a regular file. Move it aside, then retry."
        )
    created = not private_exists
    if created:
        try:
            result = subprocess.run(
                [
                    "ssh-keygen",
                    "-q",
                    "-t",
                    "ed25519",
                    "-N",
                    "",
                    "-C",
                    f"perenna-backup-{key_id}",
                    "-f",
                    os.fspath(private_key),
                ],
                check=False,
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
            )
        except FileNotFoundError as exc:
            raise RepositoryError(
                "OpenSSH ssh-keygen is not installed or is not available on PATH. Install the "
                "OpenSSH client, then retry with --deploy-key."
            ) from exc
        if result.returncode != 0:
            raise RepositoryError(
                f"OpenSSH could not generate a deploy key in {directory}. Check that the "
                "directory is writable, then retry."
            )

    private_key.chmod(0o600)
    public_key_path.chmod(0o644)
    if not known_hosts.exists():
        known_hosts.touch(mode=0o600)
    else:
        known_hosts.chmod(0o600)
    public_key = public_key_path.read_text(encoding="utf-8").strip()
    if not public_key.startswith("ssh-ed25519 ") or "\n" in public_key:
        raise RepositoryError(
            f"Deploy-key public file {public_key_path} is not one valid Ed25519 public key. "
            "Move the credential directory aside, then retry."
        )
    fingerprint = _deploy_key_fingerprint(public_key_path)
    return DeployKey(private_key, public_key, fingerprint, known_hosts, created)


def _configured_deploy_key(repository: GitRepository) -> DeployKey | None:
    private_key = repository.deploy_key_path()
    if private_key is None:
        return None
    public_key_path = Path(f"{private_key}.pub")
    known_hosts = private_key.parent / "known_hosts"
    if not private_key.is_file() or not public_key_path.is_file():
        raise RepositoryError(
            f"The configured deploy key {private_key} is missing. Restore its credential "
            "directory or run backup setup with --deploy-key again."
        )
    public_key = public_key_path.read_text(encoding="utf-8").strip()
    return DeployKey(
        private_key,
        public_key,
        _deploy_key_fingerprint(public_key_path),
        known_hosts,
        False,
    )


def _deploy_key_fingerprint(public_key_path: Path) -> str:
    try:
        result = subprocess.run(
            ["ssh-keygen", "-lf", os.fspath(public_key_path)],
            check=False,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
        )
    except FileNotFoundError as exc:
        raise RepositoryError(
            "OpenSSH ssh-keygen is not installed or is not available on PATH. Install the "
            "OpenSSH client, then retry."
        ) from exc
    fields = result.stdout.split()
    if result.returncode != 0 or len(fields) < 2 or not fields[1].startswith("SHA256:"):
        raise RepositoryError(
            f"OpenSSH could not read the deploy-key fingerprint from {public_key_path}. "
            "Restore or replace that key, then retry."
        )
    return fields[1]


def _ensure_private_directory(directory: Path) -> None:
    missing: list[Path] = []
    current = directory
    while not current.exists():
        missing.append(current)
        current = current.parent
    if not current.is_dir() or current.is_symlink() or current.is_junction():
        raise RepositoryError(
            f"Deploy-key directory parent {current} is not a regular directory. Choose a "
            "different Perenna home, then retry."
        )
    for path in reversed(missing):
        path.mkdir()
        path.chmod(0o700)
    for path in (directory.parent.parent, directory.parent, directory):
        if path.exists() and (not path.is_dir() or path.is_symlink() or path.is_junction()):
            raise RepositoryError(
                f"Deploy-key directory {path} is not a regular directory. Move it aside, then "
                "retry."
            )
        if path.exists():
            path.chmod(0o700)


def _deploy_key_pending_report(
    repository: GitRepository,
    remote_name: str,
    repository_url: str,
    branch: str,
    key: DeployKey,
) -> BackupReport:
    return BackupReport(
        repository=repository.path,
        remote_name=remote_name,
        remote_url=repository_url,
        branch=branch,
        repository_access="pending",
        write_access="pending",
        state="waiting-deploy-key",
        authentication="deploy-key",
        deploy_key_fingerprint=key.fingerprint,
        deploy_key_public_key=key.public_key,
        deploy_key_settings_url=_github_deploy_key_settings_url(repository_url),
    )


def _require_ssh_repository_url(url: str) -> None:
    parsed = urlsplit(url) if "://" in url else None
    ssh_url = (parsed is not None and parsed.scheme.casefold() == "ssh") or bool(
        re.fullmatch(r"[^\s/:]+@[^\s/:]+:.+", url)
    )
    if not ssh_url:
        raise ConfigurationError(
            "Deploy-key setup requires an SSH repository address such as "
            "git@github.com:OWNER/REPO.git. Pass an SSH address or omit --deploy-key."
        )


def _github_deploy_key_settings_url(repository_url: str) -> str | None:
    match = re.fullmatch(
        r"(?:git@)?github\.com:([^/]+)/(.+?)(?:\.git)?",
        repository_url,
        flags=re.IGNORECASE,
    )
    if match is None and "://" in repository_url:
        parsed = urlsplit(repository_url)
        if parsed.scheme.casefold() == "ssh" and parsed.hostname == "github.com":
            parts = [part for part in parsed.path.split("/") if part]
            if len(parts) == 2:
                match_parts = (parts[0], re.sub(r"\.git$", "", parts[1]))
            else:
                match_parts = None
        else:
            match_parts = None
    elif match is not None:
        match_parts = (match.group(1), re.sub(r"\.git$", "", match.group(2)))
    else:
        match_parts = None
    if match_parts is None:
        return None
    owner, repository = match_parts
    return f"https://github.com/{quote(owner, safe='')}/{quote(repository, safe='')}/settings/keys"


def _validated_repository_url(value: str) -> str:
    url = value.strip()
    if not url or url.startswith("-") or any(character in url for character in ("\0", "\r", "\n")):
        raise ConfigurationError(
            "The backup repository URL is empty, option-like, or contains control characters. "
            "Provide one Git HTTPS or SSH repository address."
        )
    if "://" not in url:
        return url

    parsed = urlsplit(url)
    if parsed.scheme.casefold() == "http":
        raise ConfigurationError(
            "The backup repository uses insecure HTTP. Use an HTTPS or SSH repository address."
        )
    if parsed.scheme.casefold() in {"http", "https"} and (
        parsed.username is not None or parsed.password is not None
    ):
        raise ConfigurationError(
            "The backup repository URL contains embedded HTTPS credentials. Save the credential "
            "in Git Credential Manager and pass a credential-free repository URL instead."
        )
    if parsed.password is not None or parsed.query or parsed.fragment:
        raise ConfigurationError(
            "The backup repository URL contains a password, query, or fragment. Use a "
            "credential-free Git HTTPS or SSH repository address."
        )
    return url


def _require_compatible_remote(
    heads: dict[str, str],
    branch: str,
    local_head: str | None,
) -> None:
    if not heads or branch in heads:
        return
    remote_branches = ", ".join(sorted(heads))
    if local_head is None:
        detail = "the local memory repository has no commit to compare"
    else:
        detail = f"it has no {branch!r} branch to compare"
    raise RepositoryError(
        f"The backup repository already has branch history ({remote_branches}), and {detail}. "
        "Perenna did not create a parallel history. Use an empty repository or configure this "
        "remote manually."
    )


def _restore_remote(
    repository: GitRepository,
    remote_name: str,
    previous_url: str | None,
) -> None:
    if previous_url is None:
        repository.remove_remote(remote_name)
    else:
        repository.set_remote_url(remote_name, previous_url)
