from __future__ import annotations

import subprocess
from pathlib import Path

import pytest

from perenna.backup import inspect_backup, setup_backup
from perenna.errors import ConfigurationError, RepositoryError
from perenna.git import GIT_IDENTITY_EMAIL, GIT_IDENTITY_NAME, GitRepository, PushOutcome


def _bare_repository(path: Path) -> Path:
    subprocess.run(
        ["git", "init", "--bare", str(path)],
        check=True,
        capture_output=True,
        text=True,
        encoding="utf-8",
    )
    return path


def _commit(repository: GitRepository, text: str = "memory") -> str:
    marker = repository.path / "global" / "fact.md"
    marker.parent.mkdir(parents=True, exist_ok=True)
    marker.write_text(text, encoding="utf-8")
    repository._run(["add", "--", "global/fact.md"])
    repository._run(["commit", "-m", "memory(global): create test fact"])
    head = repository.head()
    assert head is not None
    return head


def test_setup_configures_empty_remote_without_requiring_a_memory_commit(
    tmp_path: Path,
) -> None:
    memory = tmp_path / "home" / "memory"
    remote = _bare_repository(tmp_path / "backup.git")

    report = setup_backup(memory, str(remote), remote_name="origin", replace=False)

    repository = GitRepository.open(memory)
    assert report.write_access == "pending"
    assert report.state == "pending-first-commit"
    assert repository.remote_url("origin") == str(remote)
    assert repository._run(["config", "--local", "user.name"]).stdout.strip() == GIT_IDENTITY_NAME
    assert repository._run(["config", "--local", "user.email"]).stdout.strip() == GIT_IDENTITY_EMAIL


def test_setup_pushes_existing_history_and_status_reports_synchronized(tmp_path: Path) -> None:
    memory = tmp_path / "home" / "memory"
    repository = GitRepository.initialize(memory)
    head = _commit(repository)
    remote = _bare_repository(tmp_path / "backup.git")

    setup_report = setup_backup(memory, str(remote), remote_name="origin", replace=False)
    status_report = inspect_backup(memory, remote_name="origin")

    assert setup_report.write_access == "ok"
    assert setup_report.state == "synchronized"
    assert status_report is not None
    assert status_report.state == "synchronized"
    remote_head = subprocess.run(
        ["git", "--git-dir", str(remote), "rev-parse", "refs/heads/main"],
        check=True,
        capture_output=True,
        text=True,
        encoding="utf-8",
    ).stdout.strip()
    assert remote_head == head


def test_setup_is_idempotent_for_the_same_remote(tmp_path: Path) -> None:
    memory = tmp_path / "home" / "memory"
    remote = _bare_repository(tmp_path / "backup.git")

    first = setup_backup(memory, str(remote), remote_name="origin", replace=False)
    second = setup_backup(memory, str(remote), remote_name="origin", replace=False)

    assert first == second
    assert GitRepository.open(memory).remote_names() == {"origin"}


def test_setup_refuses_to_replace_a_different_remote_without_flag(tmp_path: Path) -> None:
    memory = tmp_path / "home" / "memory"
    first = _bare_repository(tmp_path / "first.git")
    second = _bare_repository(tmp_path / "second.git")
    setup_backup(memory, str(first), remote_name="origin", replace=False)

    with pytest.raises(RepositoryError, match="pass --replace"):
        setup_backup(memory, str(second), remote_name="origin", replace=False)

    assert GitRepository.open(memory).remote_url("origin") == str(first)


def test_setup_replaces_a_remote_only_after_the_new_address_is_verified(tmp_path: Path) -> None:
    memory = tmp_path / "home" / "memory"
    first = _bare_repository(tmp_path / "first.git")
    second = _bare_repository(tmp_path / "second.git")
    setup_backup(memory, str(first), remote_name="origin", replace=False)

    setup_backup(memory, str(second), remote_name="origin", replace=True)

    assert GitRepository.open(memory).remote_url("origin") == str(second)


def test_setup_restores_the_previous_remote_when_initial_push_fails(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    memory = tmp_path / "home" / "memory"
    repository = GitRepository.initialize(memory)
    _commit(repository)
    first = _bare_repository(tmp_path / "first.git")
    second = _bare_repository(tmp_path / "second.git")
    setup_backup(memory, str(first), remote_name="origin", replace=False)
    monkeypatch.setattr(
        GitRepository,
        "push",
        lambda _repository, _remote: PushOutcome(True, False, "failed"),
    )

    with pytest.raises(RepositoryError, match="restored the previous remote configuration"):
        setup_backup(memory, str(second), remote_name="origin", replace=True)

    assert repository.remote_url("origin") == str(first)


def test_setup_refuses_remote_history_on_another_branch(tmp_path: Path) -> None:
    memory = tmp_path / "home" / "memory"
    remote = _bare_repository(tmp_path / "backup.git")
    other = GitRepository.initialize(tmp_path / "other")
    _commit(other, "remote history")
    other._run(["branch", "-m", "legacy"])
    other._run(["push", str(remote), "legacy:refs/heads/legacy"])

    with pytest.raises(RepositoryError, match="did not create a parallel history"):
        setup_backup(memory, str(remote), remote_name="origin", replace=False)

    assert GitRepository.open(memory).remote_url("origin") is None


def test_setup_refuses_incompatible_history_on_the_same_branch(tmp_path: Path) -> None:
    memory = tmp_path / "home" / "memory"
    local = GitRepository.initialize(memory)
    _commit(local, "local history")
    remote = _bare_repository(tmp_path / "backup.git")
    other = GitRepository.initialize(tmp_path / "other")
    _commit(other, "remote history")
    other._run(["push", str(remote), "main:refs/heads/main"])

    with pytest.raises(RepositoryError, match="history incompatible"):
        setup_backup(memory, str(remote), remote_name="origin", replace=False)

    assert local.remote_url("origin") is None


def test_setup_rejects_embedded_https_credentials_without_echoing_them(
    tmp_path: Path,
) -> None:
    secret = "owner:super-secret-token"
    url = f"https://{secret}@example.com/memory.git"

    with pytest.raises(ConfigurationError) as exc_info:
        setup_backup(tmp_path / "memory", url, remote_name="origin", replace=False)

    assert "embedded HTTPS credentials" in str(exc_info.value)
    assert secret not in str(exc_info.value)
    assert not (tmp_path / "memory").exists()


def test_setup_rejects_an_option_like_repository_address(tmp_path: Path) -> None:
    with pytest.raises(ConfigurationError, match="option-like"):
        setup_backup(tmp_path / "memory", "--force", remote_name="origin", replace=False)

    assert not (tmp_path / "memory").exists()


def test_setup_respects_an_explicitly_disabled_effective_remote(tmp_path: Path) -> None:
    with pytest.raises(ConfigurationError, match="PERENNA_GIT_REMOTE is empty"):
        setup_backup(
            tmp_path / "memory",
            "git@example.com:owner/memory.git",
            remote_name=None,
            replace=False,
        )

    assert not (tmp_path / "memory").exists()


def test_status_reports_disabled_without_network_access(tmp_path: Path) -> None:
    memory = tmp_path / "memory"
    GitRepository.initialize(memory)

    assert inspect_backup(memory, remote_name=None) is None


def test_status_reports_a_missing_effective_remote(tmp_path: Path) -> None:
    memory = tmp_path / "memory"
    GitRepository.initialize(memory)

    with pytest.raises(RepositoryError, match="remote 'backup'.*missing"):
        inspect_backup(memory, remote_name="backup")


def test_deploy_key_setup_generates_a_persistent_repository_specific_key(
    tmp_path: Path,
) -> None:
    home = tmp_path / "home"
    memory = home / "memory"
    url = "git@github.com:owner/memory.git"

    report = setup_backup(
        memory,
        url,
        remote_name="origin",
        replace=False,
        deploy_key=True,
    )

    repository = GitRepository.open(memory)
    private_key = repository.deploy_key_path()
    assert private_key is not None
    assert private_key.is_file()
    assert private_key.parent.parent.parent == home / "credentials"
    assert Path(f"{private_key}.pub").read_text(encoding="utf-8").strip() == (
        report.deploy_key_public_key
    )
    assert report.authentication == "deploy-key"
    assert report.repository_access == "pending"
    assert report.state == "waiting-deploy-key"
    assert report.deploy_key_fingerprint is not None
    assert report.deploy_key_settings_url == "https://github.com/owner/memory/settings/keys"
    assert repository.remote_url("origin") == url
    ssh_command = repository._run(["config", "--local", "--get", "core.sshCommand"]).stdout
    assert str(private_key) in ssh_command
    assert "IdentitiesOnly=yes" in ssh_command
    assert "StrictHostKeyChecking=accept-new" in ssh_command


def test_deploy_key_setup_reuses_an_unauthorized_key_without_regenerating_it(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    memory = tmp_path / "home" / "memory"
    url = "git@github.com:owner/memory.git"
    first = setup_backup(
        memory,
        url,
        remote_name="origin",
        replace=False,
        deploy_key=True,
    )
    private_key = GitRepository.open(memory).deploy_key_path()
    assert private_key is not None
    original_private_key = private_key.read_bytes()

    def unauthorized(*_args, **_kwargs):
        raise RepositoryError("deploy key is not authorized")

    monkeypatch.setattr(GitRepository, "remote_heads", unauthorized)
    second = setup_backup(
        memory,
        url,
        remote_name="origin",
        replace=False,
        deploy_key=True,
    )

    assert second.state == "waiting-deploy-key"
    assert second.deploy_key_fingerprint == first.deploy_key_fingerprint
    assert private_key.read_bytes() == original_private_key


def test_deploy_key_status_reports_unconfirmed_access_truthfully(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    memory = tmp_path / "home" / "memory"
    setup_backup(
        memory,
        "git@github.com:owner/memory.git",
        remote_name="origin",
        replace=False,
        deploy_key=True,
    )

    def unavailable(*_args, **_kwargs):
        raise RepositoryError("network, authorization, or host-key failure")

    monkeypatch.setattr(GitRepository, "remote_heads", unavailable)

    with pytest.raises(RepositoryError, match="configured deploy key.*network"):
        inspect_backup(memory, remote_name="origin")


def test_deploy_key_setup_rejects_https_before_creating_the_repository(
    tmp_path: Path,
) -> None:
    memory = tmp_path / "home" / "memory"

    with pytest.raises(ConfigurationError, match="requires an SSH repository address"):
        setup_backup(
            memory,
            "https://github.com/owner/memory.git",
            remote_name="origin",
            replace=False,
            deploy_key=True,
        )

    assert not memory.exists()


def test_setup_requires_deploy_key_flag_when_the_repository_uses_one(tmp_path: Path) -> None:
    memory = tmp_path / "home" / "memory"
    url = "git@github.com:owner/memory.git"
    setup_backup(
        memory,
        url,
        remote_name="origin",
        replace=False,
        deploy_key=True,
    )

    with pytest.raises(ConfigurationError, match="Repeat setup with --deploy-key"):
        setup_backup(memory, url, remote_name="origin", replace=False)
