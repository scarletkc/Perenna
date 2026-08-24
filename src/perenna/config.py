from __future__ import annotations

import os
from collections.abc import Mapping
from dataclasses import dataclass
from ipaddress import ip_address
from pathlib import Path
from urllib.parse import urlsplit

from pydantic import AnyHttpUrl, BaseModel, ConfigDict, ValidationError

from perenna.errors import ConfigurationError

DEFAULT_HOME = Path.home() / ".perenna"
REMOTE_SCOPES = ("memory:read", "memory:write", "memory:delete")


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


def resolve_git_remote(environ: Mapping[str, str] | None = None) -> str | None:
    env = os.environ if environ is None else environ
    if "PERENNA_GIT_REMOTE" not in env:
        return None
    value = env["PERENNA_GIT_REMOTE"].strip()
    return value or None


def resolve_settings(
    *,
    cli_home: str | os.PathLike[str] | None,
    environ: Mapping[str, str] | None = None,
) -> RuntimeSettings:
    return RuntimeSettings(
        paths=RuntimePaths(resolve_home(cli_home, environ)),
        git_remote=resolve_git_remote(environ),
    )


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
