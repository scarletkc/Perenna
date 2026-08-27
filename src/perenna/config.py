from __future__ import annotations

import json
import os
from collections.abc import Mapping
from dataclasses import dataclass
from ipaddress import ip_address
from pathlib import Path
from urllib.parse import urlsplit

from pydantic import AnyHttpUrl, BaseModel, ConfigDict, ValidationError

from perenna.errors import ConfigurationError
from perenna.filesystem import atomic_replace

DEFAULT_HOME = Path.home() / ".perenna"
LOCAL_CONFIG_NAME = "config.json"
REMOTE_SCOPES = ("memory:read", "memory:write", "memory:delete")
_MISSING = object()


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
    git_remote: str | None


@dataclass(frozen=True, slots=True)
class GitRemoteSelection:
    remote: str | None
    source: str


@dataclass(frozen=True, slots=True)
class RemoteSettings:
    public_url: str
    issuer: str
    jwks_url: str
    allowed_subject: str


class _HttpsUrlValue(BaseModel):
    model_config = ConfigDict(url_preserve_empty_path=True)

    value: AnyHttpUrl


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


def resolve_git_remote(
    environ: Mapping[str, str] | None = None,
    *,
    home: Path | None = None,
) -> str | None:
    return resolve_git_remote_selection(environ, home=home).remote


def resolve_git_remote_selection(
    environ: Mapping[str, str] | None = None,
    *,
    home: Path | None = None,
) -> GitRemoteSelection:
    env = os.environ if environ is None else environ
    saved = _MISSING if home is None else _read_saved_git_remote(home)
    if "PERENNA_GIT_REMOTE" in env:
        value = env["PERENNA_GIT_REMOTE"].strip()
        return GitRemoteSelection(value or None, "environment")
    if saved is _MISSING:
        return GitRemoteSelection(None, "default")
    return GitRemoteSelection(saved, "local-config")


def save_git_remote(home: Path, remote: str | None) -> Path:
    normalized = None if remote is None else remote.strip()
    if remote is not None and not normalized:
        raise ConfigurationError(
            "The saved Git remote name is empty. Provide a non-empty remote name or disable "
            "synchronization explicitly."
        )
    path = home / LOCAL_CONFIG_NAME
    payload = json.dumps(
        {"git_remote": normalized},
        ensure_ascii=False,
        indent=2,
        sort_keys=True,
    )
    try:
        atomic_replace(path, f"{payload}\n".encode())
    except OSError as exc:
        raise ConfigurationError(
            f"Perenna could not save the Git synchronization preference to {path}. Check the "
            "directory permissions, then retry."
        ) from exc
    return path


def resolve_settings(
    *,
    cli_home: str | os.PathLike[str] | None,
    environ: Mapping[str, str] | None = None,
) -> RuntimeSettings:
    paths = RuntimePaths(resolve_home(cli_home, environ))
    return RuntimeSettings(
        paths=paths,
        git_remote=resolve_git_remote(environ, home=paths.home),
    )


def _read_saved_git_remote(home: Path) -> str | None | object:
    path = home / LOCAL_CONFIG_NAME
    if not path.exists():
        return _MISSING
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise ConfigurationError(
            f"Perenna local configuration {path} is invalid or unreadable. Repair or remove "
            "that file, then retry."
        ) from exc
    if not isinstance(payload, dict) or set(payload) != {"git_remote"}:
        raise ConfigurationError(
            f"Perenna local configuration {path} must contain exactly the git_remote field. "
            "Repair or remove that file, then retry."
        )
    remote = payload["git_remote"]
    if remote is None:
        return None
    if not isinstance(remote, str) or not remote.strip():
        raise ConfigurationError(
            f"Perenna local configuration {path} has an invalid git_remote value. Use a "
            "non-empty remote name or null for local-only mode."
        )
    return remote.strip()


def resolve_remote_settings(environ: Mapping[str, str] | None = None) -> RemoteSettings:
    env = os.environ if environ is None else environ
    public_url = _required_https_url(env, "PERENNA_PUBLIC_URL")
    if urlsplit(public_url).path != "/mcp":
        raise ConfigurationError(
            "PERENNA_PUBLIC_URL must end with the exact /mcp path, for example "
            "https://memory.example.com/mcp."
        )

    allowed_subject = _required_environment_value(env, "PERENNA_OAUTH_ALLOWED_SUBJECT")
    return RemoteSettings(
        public_url=public_url,
        issuer=_required_https_url(env, "PERENNA_OAUTH_ISSUER"),
        jwks_url=_required_https_url(env, "PERENNA_OAUTH_JWKS_URL"),
        allowed_subject=allowed_subject,
    )


def validate_loopback_host(host: str) -> None:
    try:
        address = ip_address(host)
    except ValueError as exc:
        raise ConfigurationError(
            "--local-only requires --host to be a loopback IP address such as "
            f"127.0.0.1 or ::1; received {host!r}. Remove --host to use the default, "
            "or omit --local-only and configure OAuth for network access."
        ) from exc
    if not address.is_loopback:
        raise ConfigurationError(
            "--local-only requires --host to be a loopback IP address such as "
            f"127.0.0.1 or ::1; received {host!r}. Remove --host to use the default, "
            "or omit --local-only and configure OAuth for network access."
        )


def _required_https_url(env: Mapping[str, str], name: str) -> str:
    value = _required_environment_value(env, name)
    try:
        parsed = _HttpsUrlValue(value=value).value
    except (ValidationError, ValueError) as exc:
        raise ConfigurationError(f"{name} is not a valid HTTPS URL.") from exc
    if (
        parsed.scheme != "https"
        or parsed.username is not None
        or parsed.password is not None
        or parsed.query is not None
        or parsed.fragment is not None
    ):
        raise ConfigurationError(
            f"{name} must be an absolute HTTPS URL without credentials, a query, or a fragment."
        )
    canonical = str(parsed)
    if canonical != value:
        raise ConfigurationError(f"{name} must use its canonical form: {canonical}")
    return canonical


def _required_environment_value(env: Mapping[str, str], name: str) -> str:
    if name not in env:
        raise ConfigurationError(f"{name} is missing from the remote MCP configuration.")
    value = env[name].strip()
    if not value:
        raise ConfigurationError(f"{name} is empty. Provide a non-empty value.")
    return value
