"""Repository-specific SSH deploy-key lifecycle for Git synchronization.

This module owns generating, locating, and validating deploy keys and their
credential directories. Remote setup and inspection orchestration live in
`perenna.sync`.
"""

from __future__ import annotations

import hashlib
import os
import re
import subprocess
from dataclasses import dataclass
from pathlib import Path
from urllib.parse import quote, urlsplit

from perenna.errors import ConfigurationError, RepositoryError


@dataclass(frozen=True, slots=True)
class DeployKey:
    private_key: Path
    public_key: str
    fingerprint: str
    known_hosts: Path
    created: bool


def prepare_deploy_key(home: Path, repository_url: str) -> DeployKey:
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
                    f"perenna-sync-{key_id}",
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


def configured_deploy_key(private_key: Path) -> DeployKey:
    public_key_path = Path(f"{private_key}.pub")
    known_hosts = private_key.parent / "known_hosts"
    if not private_key.is_file() or not public_key_path.is_file():
        raise RepositoryError(
            f"The configured deploy key {private_key} is missing. Restore its credential "
            "directory or run sync setup with --deploy-key again."
        )
    public_key = public_key_path.read_text(encoding="utf-8").strip()
    return DeployKey(
        private_key,
        public_key,
        _deploy_key_fingerprint(public_key_path),
        known_hosts,
        False,
    )


def require_ssh_repository_url(url: str) -> None:
    parsed = urlsplit(url) if "://" in url else None
    ssh_url = (parsed is not None and parsed.scheme.casefold() == "ssh") or bool(
        re.fullmatch(r"[^\s/:]+@[^\s/:]+:.+", url)
    )
    if not ssh_url:
        raise ConfigurationError(
            "Deploy-key setup requires an SSH repository address such as "
            "git@github.com:OWNER/REPO.git. Pass an SSH address or omit --deploy-key."
        )


def github_deploy_key_settings_url(repository_url: str) -> str | None:
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
