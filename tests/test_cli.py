from __future__ import annotations

import subprocess
from pathlib import Path

import pytest

from perenna import DESCRIPTION, __version__, cli
from perenna.config import RemoteSettings, RuntimePaths, RuntimeSettings
from perenna.errors import ConfigurationError


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
    settings = RuntimeSettings(RuntimePaths(tmp_path / "home"), "codex", None)
    core = object()
    observed: list[object] = []

    async def fake_run_stdio(value: object) -> None:
        observed.append(value)

    monkeypatch.setattr(cli, "resolve_settings", lambda **_kwargs: settings)
    monkeypatch.setattr(cli, "PerennaCore", lambda value: core if value is settings else None)
    monkeypatch.setattr(cli, "run_stdio", fake_run_stdio)

    assert cli.main(["mcp", "--source", "codex", "--home", str(tmp_path)]) == 0
    assert observed == [core]


def test_main_runs_authenticated_http_server(tmp_path: Path, monkeypatch) -> None:
    settings = RuntimeSettings(RuntimePaths(tmp_path / "home"), "chatgpt-web", None)
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
                "--source",
                "chatgpt-web",
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


def test_backup_setup_and_status_do_not_require_source_or_vexor(
    tmp_path: Path,
    capsys,
    monkeypatch,
) -> None:
    home = tmp_path / "home"
    remote = tmp_path / "backup.git"
    subprocess.run(
        ["git", "init", "--bare", str(remote)],
        check=True,
        capture_output=True,
        text=True,
        encoding="utf-8",
    )
    monkeypatch.delenv("PERENNA_GIT_REMOTE", raising=False)
    monkeypatch.delenv("PERENNA_SOURCE", raising=False)
    monkeypatch.delenv("VEXOR_CONFIG_JSON", raising=False)

    assert cli.main(["backup", "setup", str(remote), "--home", str(home)]) == 0
    setup_output = capsys.readouterr()
    assert setup_output.err == ""
    assert f"Backup remote: origin -> {remote}" in setup_output.out
    assert "Write access: pending" in setup_output.out
    assert "Backup state: pending first memory commit" in setup_output.out

    assert cli.main(["backup", "status", "--home", str(home)]) == 0
    status_output = capsys.readouterr()
    assert status_output.err == ""
    assert f"Memory repository: {home.resolve() / 'memory'}" in status_output.out
    assert "Automatic backup: enabled (remote: origin)" in status_output.out


def test_backup_status_reports_an_explicit_disable(tmp_path: Path, capsys, monkeypatch) -> None:
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

    assert cli.main(["backup", "status", "--home", str(home)]) == 0

    captured = capsys.readouterr()
    assert captured.err == ""
    assert "Automatic backup: disabled (PERENNA_GIT_REMOTE is empty)" in captured.out


def test_backup_setup_prints_guided_deploy_key_action(
    tmp_path: Path,
    capsys,
    monkeypatch,
) -> None:
    monkeypatch.delenv("PERENNA_GIT_REMOTE", raising=False)

    assert (
        cli.main(
            [
                "backup",
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


@pytest.mark.parametrize("port", ["0", "65536"])
def test_serve_rejects_invalid_port(port: str) -> None:
    with pytest.raises(SystemExit) as exc_info:
        cli.build_parser().parse_args(["serve", "--port", port])

    assert exc_info.value.code == 2


def test_main_reports_expected_startup_error_on_stderr(capsys, monkeypatch) -> None:
    def fail(**_kwargs):
        raise ConfigurationError("specific recovery guidance")

    monkeypatch.setattr(cli, "resolve_settings", fail)

    assert cli.main(["mcp", "--source", "codex"]) == 2
    captured = capsys.readouterr()
    assert captured.out == ""
    assert "specific recovery guidance" in captured.err


def test_main_handles_keyboard_interrupt(monkeypatch) -> None:
    monkeypatch.setattr(cli, "resolve_settings", lambda **_kwargs: object())

    def interrupt(_settings):
        raise KeyboardInterrupt

    monkeypatch.setattr(cli, "PerennaCore", interrupt)
    assert cli.main(["mcp", "--source", "codex"]) == 130


def test_main_hides_unexpected_exception_details(capsys, caplog, monkeypatch) -> None:
    secret = "unexpected-secret-detail"

    def fail(**_kwargs):
        raise RuntimeError(secret)

    monkeypatch.setattr(cli, "resolve_settings", fail)

    assert cli.main(["mcp", "--source", "codex"]) == 1
    captured = capsys.readouterr()
    assert captured.out == ""
    assert "startup failed" in captured.err
    assert secret not in captured.err
    assert secret not in caplog.text
