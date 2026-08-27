from __future__ import annotations

import subprocess
from pathlib import Path

import pytest

from perenna import DESCRIPTION, __version__, cli
from perenna.cli_output import print_sync_report
from perenna.config import LOCAL_CONFIG_NAME, RemoteSettings, RuntimePaths, RuntimeSettings
from perenna.errors import ConfigurationError, SkillInstallError
from perenna.skill_installer import SkillInstallReport
from perenna.sync import SyncReport


def test_parser_uses_package_description() -> None:
    assert cli.build_parser().description == DESCRIPTION


@pytest.mark.parametrize("flag", ["--version", "-V"])
def test_main_reports_version(flag: str, capsys) -> None:
    with pytest.raises(SystemExit) as exc_info:
        cli.main([flag])

    assert exc_info.value.code == 0
    captured = capsys.readouterr()
    assert captured.out == f"perenna {__version__}\n"
    assert captured.err == ""


def test_main_resolves_settings_builds_core_and_runs_stdio(tmp_path: Path, monkeypatch) -> None:
    settings = RuntimeSettings(RuntimePaths(tmp_path / "home"), None)
    core = object()
    observed: list[object] = []

    async def fake_run_stdio(value: object) -> None:
        observed.append(value)

    monkeypatch.setattr(cli, "resolve_settings", lambda **_kwargs: settings)
    monkeypatch.setattr(cli, "PerennaCore", lambda value: core if value is settings else None)
    monkeypatch.setattr(cli, "run_stdio", fake_run_stdio)

    assert cli.main(["mcp", "--home", str(tmp_path)]) == 0
    assert observed == [core]


def test_main_runs_authenticated_http_server(tmp_path: Path, monkeypatch) -> None:
    settings = RuntimeSettings(RuntimePaths(tmp_path / "home"), None)
    remote = RemoteSettings(
        public_url="https://memory.example.com/mcp",
        issuer="https://tenant.example.com/",
        jwks_url="https://tenant.example.com/.well-known/jwks.json",
        allowed_subject="auth0|owner",
    )
    core = object()
    observed: list[tuple[object, object, str, int]] = []

    monkeypatch.setattr(cli, "resolve_settings", lambda **_kwargs: settings)
    monkeypatch.setattr(cli, "resolve_remote_settings", lambda: remote)
    monkeypatch.setattr(cli, "PerennaCore", lambda value: core if value is settings else None)
    monkeypatch.setattr(
        cli,
        "run_http",
        lambda value, remote_settings, *, host, port: observed.append(
            (value, remote_settings, host, port)
        ),
    )

    assert (
        cli.main(
            [
                "serve",
                "--home",
                str(tmp_path),
                "--host",
                "0.0.0.0",
                "--port",
                "8788",
            ]
        )
        == 0
    )
    assert observed == [(core, remote, "0.0.0.0", 8788)]


def test_main_runs_local_only_http_without_remote_settings(tmp_path: Path, monkeypatch) -> None:
    settings = RuntimeSettings(RuntimePaths(tmp_path / "home"), None)
    core = object()
    observed: list[tuple[object, str, int]] = []

    monkeypatch.setattr(cli, "resolve_settings", lambda **_kwargs: settings)
    monkeypatch.setattr(
        cli,
        "resolve_remote_settings",
        lambda: pytest.fail("local-only HTTP must not resolve OAuth settings"),
    )
    monkeypatch.setattr(cli, "PerennaCore", lambda value: core if value is settings else None)
    monkeypatch.setattr(
        cli,
        "run_local_http",
        lambda value, *, host, port: observed.append((value, host, port)),
    )

    assert (
        cli.main(
            [
                "serve",
                "--local-only",
                "--home",
                str(tmp_path),
                "--port",
                "8788",
            ]
        )
        == 0
    )
    assert observed == [(core, "127.0.0.1", 8788)]


def test_local_only_http_rejects_network_listener(tmp_path: Path, capsys, monkeypatch) -> None:
    settings = RuntimeSettings(RuntimePaths(tmp_path / "home"), None)
    monkeypatch.setattr(cli, "resolve_settings", lambda **_kwargs: settings)
    monkeypatch.setattr(
        cli,
        "PerennaCore",
        lambda _settings: pytest.fail("invalid local-only host must fail before core startup"),
    )

    assert (
        cli.main(
            [
                "serve",
                "--local-only",
                "--home",
                str(tmp_path),
                "--host",
                "0.0.0.0",
            ]
        )
        == 2
    )
    captured = capsys.readouterr()
    assert captured.out == ""
    assert "--local-only requires --host to be a loopback IP address" in captured.err
    assert "omit --local-only and configure OAuth" in captured.err


def test_sync_setup_and_status_do_not_require_vexor(
    tmp_path: Path,
    capsys,
    monkeypatch,
) -> None:
    home = tmp_path / "home"
    remote = tmp_path / "sync.git"
    subprocess.run(
        ["git", "init", "--bare", str(remote)],
        check=True,
        capture_output=True,
        text=True,
        encoding="utf-8",
    )
    monkeypatch.delenv("PERENNA_GIT_REMOTE", raising=False)
    monkeypatch.delenv("VEXOR_CONFIG_JSON", raising=False)

    assert cli.main(["sync", "setup", str(remote), "--home", str(home)]) == 0
    setup_output = capsys.readouterr()
    assert setup_output.err == ""
    assert f"Git remote: origin -> {remote}" in setup_output.out
    assert "Write access: pending" in setup_output.out
    assert "Synchronization state: waiting for the first memory commit" in setup_output.out
    assert "Saved runtime remote: origin" in setup_output.out
    assert "Restart running Perenna clients" in setup_output.out

    assert cli.main(["sync", "status", "--home", str(home)]) == 0
    status_output = capsys.readouterr()
    assert status_output.err == ""
    assert f"Memory repository: {home.resolve() / 'memory'}" in status_output.out
    assert "Git synchronization: enabled (remote: origin)" in status_output.out
    assert "Runtime remote source: saved local preference" in status_output.out


def test_sync_setup_saves_the_remote_while_an_empty_environment_override_stays_local(
    tmp_path: Path,
    capsys,
    monkeypatch,
) -> None:
    home = tmp_path / "home"
    remote = tmp_path / "sync.git"
    subprocess.run(
        ["git", "init", "--bare", str(remote)],
        check=True,
        capture_output=True,
        text=True,
        encoding="utf-8",
    )
    monkeypatch.setenv("PERENNA_GIT_REMOTE", "")

    assert cli.main(["sync", "setup", str(remote), "--home", str(home)]) == 0

    setup_output = capsys.readouterr()
    assert setup_output.err == ""
    assert "Saved runtime remote: origin" in setup_output.out
    assert "Effective runtime remains local because PERENNA_GIT_REMOTE is empty" in setup_output.out

    monkeypatch.delenv("PERENNA_GIT_REMOTE")
    assert cli.main(["sync", "status", "--home", str(home)]) == 0
    status_output = capsys.readouterr()
    assert "Git synchronization: enabled (remote: origin)" in status_output.out
    assert "Runtime remote source: saved local preference" in status_output.out


def test_sync_status_reports_local_authority_without_a_remote(
    tmp_path: Path,
    capsys,
    monkeypatch,
) -> None:
    home = tmp_path / "home"
    (home / "memory").mkdir(parents=True)
    subprocess.run(
        ["git", "init", "--initial-branch=main"],
        cwd=home / "memory",
        check=True,
        capture_output=True,
        text=True,
        encoding="utf-8",
    )
    monkeypatch.setenv("PERENNA_GIT_REMOTE", "")

    assert cli.main(["sync", "status", "--home", str(home)]) == 0

    captured = capsys.readouterr()
    assert captured.err == ""
    assert "Git synchronization: disabled (PERENNA_GIT_REMOTE is empty)" in captured.out


def test_sync_disable_saves_local_only_without_removing_remote(
    tmp_path: Path,
    capsys,
    monkeypatch,
) -> None:
    home = tmp_path / "home"
    memory = home / "memory"
    remote = tmp_path / "sync.git"
    subprocess.run(
        ["git", "init", "--bare", str(remote)],
        check=True,
        capture_output=True,
        text=True,
        encoding="utf-8",
    )
    monkeypatch.delenv("PERENNA_GIT_REMOTE", raising=False)
    assert cli.main(["sync", "setup", str(remote), "--home", str(home)]) == 0
    capsys.readouterr()

    assert cli.main(["sync", "disable", "--home", str(home)]) == 0

    disabled = capsys.readouterr()
    assert disabled.err == ""
    assert "Saved synchronization preference: local-only" in disabled.out
    assert "Git synchronization: disabled (saved local preference)" in disabled.out
    assert "origin" in subprocess.run(
        ["git", "-C", str(memory), "remote"],
        check=True,
        capture_output=True,
        text=True,
        encoding="utf-8",
    ).stdout.split()

    assert cli.main(["sync", "status", "--home", str(home)]) == 0
    status = capsys.readouterr()
    assert "Git synchronization: disabled (saved local preference)" in status.out
    assert "Configured Git remote detected" not in status.out


def test_sync_status_reports_an_existing_remote_without_a_saved_choice(
    tmp_path: Path,
    capsys,
    monkeypatch,
) -> None:
    home = tmp_path / "home"
    memory = home / "memory"
    memory.mkdir(parents=True)
    subprocess.run(
        ["git", "init", "--initial-branch=main"],
        cwd=memory,
        check=True,
        capture_output=True,
        text=True,
        encoding="utf-8",
    )
    subprocess.run(
        ["git", "remote", "add", "origin", "https://example.com/private/memory.git"],
        cwd=memory,
        check=True,
        capture_output=True,
        text=True,
        encoding="utf-8",
    )
    monkeypatch.delenv("PERENNA_GIT_REMOTE", raising=False)

    assert cli.main(["sync", "status", "--home", str(home)]) == 0

    captured = capsys.readouterr()
    assert captured.err == ""
    assert "Git synchronization: disabled (no saved choice" in captured.out
    assert "Configured Git remote detected: origin" in captured.out
    assert "Ask before running 'perenna sync setup REPOSITORY_URL'" in captured.out


def test_sync_disable_reports_an_environment_override(
    tmp_path: Path,
    capsys,
    monkeypatch,
) -> None:
    home = tmp_path / "home"
    monkeypatch.setenv("PERENNA_GIT_REMOTE", "backup")

    assert cli.main(["sync", "disable", "--home", str(home)]) == 0

    captured = capsys.readouterr()
    assert captured.err == ""
    assert "Saved synchronization preference: local-only" in captured.out
    assert "remains enabled by PERENNA_GIT_REMOTE=backup" in captured.out


def test_sync_setup_prints_guided_deploy_key_action(
    tmp_path: Path,
    capsys,
    monkeypatch,
) -> None:
    monkeypatch.delenv("PERENNA_GIT_REMOTE", raising=False)

    assert (
        cli.main(
            [
                "sync",
                "setup",
                "git@github.com:owner/memory.git",
                "--home",
                str(tmp_path / "home"),
                "--deploy-key",
            ]
        )
        == 0
    )

    captured = capsys.readouterr()
    assert captured.err == ""
    assert "Authentication: deploy key SHA256:" in captured.out
    assert "Repository access: pending" in captured.out
    assert "https://github.com/owner/memory/settings/keys" in captured.out
    assert "Public key: ssh-ed25519 " in captured.out
    assert "Enable: Allow write access" in captured.out
    assert "PRIVATE KEY" not in captured.out
    assert not (tmp_path / "home" / LOCAL_CONFIG_NAME).exists()


@pytest.mark.parametrize(
    ("state", "expected"),
    [
        ("synchronized", "Synchronization state: synchronized"),
        ("local-behind", "Synchronization state: local branch is behind the remote"),
        ("local-ahead", "Synchronization state: local branch has unconfirmed commits"),
        ("diverged", "Synchronization state: local and remote branches have diverged"),
    ],
)
def test_sync_status_prints_each_reconciled_state(
    state: str,
    expected: str,
    tmp_path: Path,
    capsys,
) -> None:
    report = SyncReport(
        repository=tmp_path / "memory",
        remote_name="origin",
        remote_url="git@github.com:owner/memory.git",
        branch="main",
        repository_access="ok",
        write_access="ok",
        state=state,
    )

    print_sync_report(report)

    output = capsys.readouterr().out
    assert "Repository access: ok" in output
    assert "Write access: ok" in output
    assert expected in output
    assert "Git synchronization: enabled (remote: origin)" in output


def test_skill_install_requires_an_agent() -> None:
    with pytest.raises(SystemExit) as exc_info:
        cli.build_parser().parse_args(["skill", "install"])

    assert exc_info.value.code == 2


def test_skill_install_supports_multiple_agents_without_runtime_configuration(
    tmp_path: Path,
    capsys,
    monkeypatch,
) -> None:
    reports = (
        SkillInstallReport(
            agent="codex",
            scope="user",
            destination=tmp_path / ".agents" / "skills" / "perenna-memory",
            state="installed",
        ),
        SkillInstallReport(
            agent="claude-code",
            scope="user",
            destination=tmp_path / ".claude" / "skills" / "perenna-memory",
            state="already-installed",
        ),
    )
    observed: list[tuple[object, str, bool]] = []

    def fake_install(agents, *, scope, replace):
        observed.append((agents, scope, replace))
        return reports

    monkeypatch.setattr(cli, "install_bundled_skill", fake_install)
    monkeypatch.setattr(
        cli,
        "resolve_settings",
        lambda **_kwargs: pytest.fail("skill install must not resolve runtime settings"),
    )

    assert (
        cli.main(
            [
                "skill",
                "install",
                "--agent",
                "codex",
                "--agent",
                "claude-code",
            ]
        )
        == 0
    )

    assert observed == [(["codex", "claude-code"], "user", False)]
    captured = capsys.readouterr()
    assert captured.err == ""
    assert "Agent: codex" in captured.out
    assert "Status: installed" in captured.out
    assert "Agent: claude-code" in captured.out
    assert "Status: already installed" in captured.out
    assert str(reports[0].destination) in captured.out
    assert "Restart the client if the skill does not appear." in captured.out


def test_skill_install_reports_a_safe_conflict(capsys, monkeypatch) -> None:
    def fail(*_args, **_kwargs):
        raise SkillInstallError("existing skill differs; re-run with --replace")

    monkeypatch.setattr(cli, "install_bundled_skill", fail)

    assert cli.main(["skill", "install", "--agent", "codex"]) == 2
    captured = capsys.readouterr()
    assert captured.out == ""
    assert "existing skill differs" in captured.err


@pytest.mark.parametrize("port", ["0", "65536"])
def test_serve_rejects_invalid_port(port: str) -> None:
    with pytest.raises(SystemExit) as exc_info:
        cli.build_parser().parse_args(["serve", "--port", port])

    assert exc_info.value.code == 2


def test_main_reports_expected_startup_error_on_stderr(capsys, monkeypatch) -> None:
    def fail(**_kwargs):
        raise ConfigurationError("specific recovery guidance")

    monkeypatch.setattr(cli, "resolve_settings", fail)

    assert cli.main(["mcp"]) == 2
    captured = capsys.readouterr()
    assert captured.out == ""
    assert "specific recovery guidance" in captured.err


def test_main_handles_keyboard_interrupt(monkeypatch) -> None:
    monkeypatch.setattr(cli, "resolve_settings", lambda **_kwargs: object())

    def interrupt(_settings):
        raise KeyboardInterrupt

    monkeypatch.setattr(cli, "PerennaCore", interrupt)
    assert cli.main(["mcp"]) == 130


def test_main_hides_unexpected_exception_details(capsys, caplog, monkeypatch) -> None:
    secret = "unexpected-secret-detail"

    def fail(**_kwargs):
        raise RuntimeError(secret)

    monkeypatch.setattr(cli, "resolve_settings", fail)

    assert cli.main(["mcp"]) == 1
    captured = capsys.readouterr()
    assert captured.out == ""
    assert "startup failed" in captured.err
    assert secret not in captured.err
    assert secret not in caplog.text
