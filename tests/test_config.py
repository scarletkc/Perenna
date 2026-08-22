from __future__ import annotations

from pathlib import Path

import pytest

from perenna.config import (
    DEFAULT_GIT_REMOTE,
    DEFAULT_HOME,
    RuntimePaths,
    resolve_git_remote,
    resolve_home,
    resolve_settings,
    resolve_source,
)
from perenna.errors import ConfigurationError


def test_home_flag_takes_priority_over_environment(tmp_path: Path) -> None:
    cli_home = tmp_path / "from-cli"
    env_home = tmp_path / "from-environment"

    assert resolve_home(cli_home, {"PERENNA_HOME": str(env_home)}) == cli_home.resolve()


def test_home_uses_environment_then_default(tmp_path: Path) -> None:
    env_home = tmp_path / "from-environment"

    assert resolve_home(None, {"PERENNA_HOME": str(env_home)}) == env_home.resolve()
    assert resolve_home(None, {}) == DEFAULT_HOME.expanduser().resolve(strict=False)


@pytest.mark.parametrize(
    ("cli_home", "environment"),
    [
        ("", {}),
        ("   ", {"PERENNA_HOME": "ignored"}),
        (None, {"PERENNA_HOME": "\t"}),
    ],
)
def test_home_rejects_an_explicit_empty_value(
    cli_home: str | None,
    environment: dict[str, str],
) -> None:
    with pytest.raises(ConfigurationError, match="empty"):
        resolve_home(cli_home, environment)


def test_source_flag_takes_priority_and_is_normalized() -> None:
    environment = {"PERENNA_SOURCE": "cursor"}

    assert resolve_source("  codex  ", environment) == "codex"


def test_source_uses_environment() -> None:
    assert resolve_source(None, {"PERENNA_SOURCE": "claude-code"}) == "claude-code"


def test_source_is_required() -> None:
    with pytest.raises(ConfigurationError, match="source is missing"):
        resolve_source(None, {})


@pytest.mark.parametrize("source", ["", "with space", "../agent", "x" * 65])
def test_source_rejects_invalid_values(source: str) -> None:
    with pytest.raises(ConfigurationError, match="is invalid"):
        resolve_source(source, {})


def test_git_remote_defaults_can_be_overridden_or_disabled() -> None:
    assert resolve_git_remote({}) == DEFAULT_GIT_REMOTE
    assert resolve_git_remote({"PERENNA_GIT_REMOTE": " backup "}) == "backup"
    assert resolve_git_remote({"PERENNA_GIT_REMOTE": "  "}) is None


def test_resolve_settings_uses_each_precedence_rule(tmp_path: Path) -> None:
    cli_home = tmp_path / "cli"
    settings = resolve_settings(
        cli_home=cli_home,
        cli_source="codex",
        environ={
            "PERENNA_HOME": str(tmp_path / "environment"),
            "PERENNA_SOURCE": "cursor",
            "PERENNA_GIT_REMOTE": "",
        },
    )

    assert settings.paths == RuntimePaths(cli_home.resolve())
    assert settings.paths.memory == cli_home.resolve() / "memory"
    assert settings.paths.index == cli_home.resolve() / "index"
    assert settings.source == "codex"
    assert settings.git_remote is None
