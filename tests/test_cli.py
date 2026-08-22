from __future__ import annotations

from pathlib import Path

import pytest

from perenna import DESCRIPTION, __version__, cli
from perenna.config import RuntimePaths, RuntimeSettings
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
