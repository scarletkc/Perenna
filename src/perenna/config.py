from __future__ import annotations

import os
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path

from perenna.errors import ConfigurationError
from perenna.models import normalize_source

DEFAULT_HOME = Path.home() / ".perenna"
DEFAULT_GIT_REMOTE = "origin"


@dataclass(frozen=True, slots=True)
class RuntimePaths:
    home: Path

    @property
    def memory(self) -> Path:
        return self.home / "memory"

    @property
    def index(self) -> Path:
        return self.home / "index"


@dataclass(frozen=True, slots=True)
class RuntimeSettings:
    paths: RuntimePaths
    source: str
    git_remote: str | None


def resolve_home(
    cli_home: str | os.PathLike[str] | None,
    environ: Mapping[str, str] | None = None,
) -> Path:
    env = os.environ if environ is None else environ
    if cli_home is not None:
        raw = os.fspath(cli_home)
        origin = "--home"
    elif "PERENNA_HOME" in env:
        raw = env["PERENNA_HOME"]
        origin = "PERENNA_HOME"
    else:
        return DEFAULT_HOME.expanduser().resolve(strict=False)

    if not raw.strip():
        raise ConfigurationError(f"{origin} is empty. Provide a directory for Perenna data.")
    expanded = os.path.expandvars(os.path.expanduser(raw.strip()))
    return Path(expanded).resolve(strict=False)


def resolve_source(cli_source: str | None, environ: Mapping[str, str] | None = None) -> str:
    env = os.environ if environ is None else environ
    if cli_source is not None:
        raw = cli_source
        origin = "--source"
    elif "PERENNA_SOURCE" in env:
        raw = env["PERENNA_SOURCE"]
        origin = "PERENNA_SOURCE"
    else:
        raise ConfigurationError(
            "Memory source is missing. Start Perenna with --source SOURCE or set "
            "PERENNA_SOURCE in the host configuration."
        )
    try:
        return normalize_source(raw)
    except ValueError as exc:
        raise ConfigurationError(
            f"{origin} is invalid. Use 1-64 letters, digits, dots, underscores, or hyphens."
        ) from exc


def resolve_git_remote(environ: Mapping[str, str] | None = None) -> str | None:
    env = os.environ if environ is None else environ
    if "PERENNA_GIT_REMOTE" not in env:
        return DEFAULT_GIT_REMOTE
    value = env["PERENNA_GIT_REMOTE"].strip()
    return value or None


def resolve_settings(
    *,
    cli_home: str | os.PathLike[str] | None,
    cli_source: str | None,
    environ: Mapping[str, str] | None = None,
) -> RuntimeSettings:
    return RuntimeSettings(
        paths=RuntimePaths(resolve_home(cli_home, environ)),
        source=resolve_source(cli_source, environ),
        git_remote=resolve_git_remote(environ),
    )
