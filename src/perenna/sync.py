"""Remote Git synchronization setup and inspection.

This module orchestrates configuring the memory repository's remote and
reporting its state. Deploy-key credentials live in `perenna.deploy_keys`;
runtime push-after-mutation behavior lives in `perenna.core`.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from urllib.parse import urlsplit

from perenna.deploy_keys import (
    DeployKey,
    configured_deploy_key,
    github_deploy_key_settings_url,
    prepare_deploy_key,
    require_ssh_repository_url,
)
from perenna.errors import ConfigurationError, RepositoryError
from perenna.git import GitRepository


@dataclass(frozen=True, slots=True)
class SyncReport:
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


def setup_sync(
    memory_path: Path,
    repository_url: str,
    *,
    remote_name: str | None,
    replace: bool,
    deploy_key: bool = False,
) -> SyncReport:
    if remote_name is None:
        raise ConfigurationError(
            "Git synchronization is disabled because PERENNA_GIT_REMOTE is unset or empty. "
            "Set it to the remote name used by the Perenna host, then retry."
        )
    url = _validated_repository_url(repository_url)
    if deploy_key:
        require_ssh_repository_url(url)
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
    local_head = repository.head()
    key = None
    changed = previous_url != url
    if deploy_key:
        key = prepare_deploy_key(memory_path.parent, url)
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
    _require_compatible_remote(heads, branch, local_head)

    if changed:
        repository.set_remote_url(remote_name, url)
    try:
        remote_head = repository.fetch(remote_name, branch)
        if local_head is None and remote_head is None:
            repository.clear_sync_conflict()
            return SyncReport(
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

        if remote_head is None:
            assert local_head is not None
            repository.verify_push(url, branch, commit=local_head)
            outcome = repository.push(remote_name, commit=local_head, branch=branch)
            if not outcome.succeeded:
                confirmed = repository.fetch(remote_name, branch)
                if confirmed != local_head:
                    configuration_result = (
                        "restored the previous remote configuration"
                        if changed
                        else "left the existing remote configuration unchanged"
                    )
                    raise RepositoryError(
                        f"Git could not publish local branch {branch!r} to the synchronized "
                        f"repository ({outcome.reason}). Perenna {configuration_result}; check "
                        "the network, credentials, and branch rules, then retry."
                    )
        elif local_head is None:
            repository.verify_push(url, branch, commit=remote_head)
            repository.reset_to(remote_head)
        elif local_head == remote_head:
            repository.verify_push(url, branch, commit=remote_head)
        elif repository.is_ancestor(local_head, remote_head):
            repository.verify_push(url, branch, commit=remote_head)
            repository.reset_to(remote_head)
        elif repository.is_ancestor(remote_head, local_head):
            repository.verify_push(url, branch, commit=local_head)
            outcome = repository.push(remote_name, commit=local_head, branch=branch)
            if not outcome.succeeded:
                confirmed = repository.fetch(remote_name, branch)
                if confirmed != local_head:
                    configuration_result = (
                        "restored the previous remote configuration"
                        if changed
                        else "left the existing remote configuration unchanged"
                    )
                    raise RepositoryError(
                        f"Git could not synchronize local branch {branch!r} "
                        f"({outcome.reason}). Perenna {configuration_result}; check the network, "
                        "credentials, and branch rules, then retry."
                    )
        else:
            raise RepositoryError(
                f"Local branch {branch!r} and the synchronized repository have diverged. "
                "Perenna did not merge, rebase, or force-push either history. Reconcile them "
                "manually, then run sync setup again."
            )

        repository.clear_sync_conflict()
        return SyncReport(
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


def inspect_sync(memory_path: Path, *, remote_name: str | None) -> SyncReport | None:
    repository = GitRepository.open(memory_path)
    if remote_name is None:
        return None
    url = repository.remote_url(remote_name)
    if url is None:
        raise RepositoryError(
            f"Git synchronization uses remote {remote_name!r}, but that remote is missing from "
            f"{repository.path}. Run 'perenna sync setup REPOSITORY_URL' to configure it."
        )

    branch = repository.current_branch()
    local_head = repository.head()
    private_key = repository.deploy_key_path()
    key = None if private_key is None else configured_deploy_key(private_key)
    try:
        heads = repository.remote_heads(url)
    except RepositoryError as exc:
        if key is None:
            raise
        raise RepositoryError(
            "Git could not access the synchronized repository with its configured deploy key. "
            "Confirm the public key is registered, the network is available, and the recorded "
            "SSH host key is current, then retry."
        ) from exc
    _require_compatible_remote(heads, branch, local_head)
    remote_head = repository.fetch(remote_name, branch)
    if local_head is None and remote_head is None:
        return SyncReport(
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

    test_commit = remote_head or local_head
    assert test_commit is not None
    repository.verify_push(url, branch, commit=test_commit)
    if local_head == remote_head:
        state = "synchronized"
    elif local_head is None:
        state = "local-behind"
    elif remote_head is None:
        state = "local-ahead"
    elif repository.is_ancestor(local_head, remote_head):
        state = "local-behind"
    elif repository.is_ancestor(remote_head, local_head):
        state = "local-ahead"
    else:
        state = "diverged"
    return SyncReport(
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


def _deploy_key_pending_report(
    repository: GitRepository,
    remote_name: str,
    repository_url: str,
    branch: str,
    key: DeployKey,
) -> SyncReport:
    return SyncReport(
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
        deploy_key_settings_url=github_deploy_key_settings_url(repository_url),
    )


def _validated_repository_url(value: str) -> str:
    url = value.strip()
    if not url or url.startswith("-") or any(character in url for character in ("\0", "\r", "\n")):
        raise ConfigurationError(
            "The synchronized repository URL is empty, option-like, or contains control "
            "characters. Provide one Git HTTPS or SSH repository address."
        )
    if "://" not in url:
        return url

    parsed = urlsplit(url)
    if parsed.scheme.casefold() == "http":
        raise ConfigurationError(
            "The synchronized repository uses insecure HTTP. Use an HTTPS or SSH repository "
            "address."
        )
    if parsed.scheme.casefold() in {"http", "https"} and (
        parsed.username is not None or parsed.password is not None
    ):
        raise ConfigurationError(
            "The synchronized repository URL contains embedded HTTPS credentials. Save the "
            "credential in Git Credential Manager and pass a credential-free repository URL "
            "instead."
        )
    if parsed.password is not None or parsed.query or parsed.fragment:
        raise ConfigurationError(
            "The synchronized repository URL contains a password, query, or fragment. Use a "
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
        f"The synchronized repository already has branch history ({remote_branches}), and "
        f"{detail}. Perenna did not create a parallel history. Use an empty repository or "
        "configure this remote manually."
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
