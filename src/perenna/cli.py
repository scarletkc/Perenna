from __future__ import annotations

import argparse
import asyncio
import logging
import sys
from collections.abc import Sequence

from perenna import DESCRIPTION, __version__
from perenna.backup import BackupReport, inspect_backup, setup_backup
from perenna.config import (
    RuntimePaths,
    resolve_git_remote,
    resolve_home,
    resolve_remote_settings,
    resolve_settings,
)
from perenna.core import PerennaCore
from perenna.errors import PerennaError
from perenna.http_server import run_http
from perenna.mcp_server import run_stdio


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="perenna",
        description=DESCRIPTION,
    )
    parser.add_argument("-V", "--version", action="version", version=f"%(prog)s {__version__}")
    subparsers = parser.add_subparsers(dest="command", required=True)
    mcp = subparsers.add_parser("mcp", help="Run the local MCP server over stdio.")
    _add_runtime_arguments(mcp)

    serve = subparsers.add_parser(
        "serve",
        help="Run the authenticated remote MCP server over Streamable HTTP.",
    )
    _add_runtime_arguments(serve)
    serve.add_argument(
        "--host",
        default="127.0.0.1",
        help="HTTP listen address. Default: 127.0.0.1.",
    )
    serve.add_argument(
        "--port",
        default=8000,
        type=_port,
        help="HTTP listen port. Default: 8000.",
    )

    backup = subparsers.add_parser(
        "backup",
        help="Configure or inspect automatic Git backup.",
    )
    backup_commands = backup.add_subparsers(dest="backup_command", required=True)
    setup = backup_commands.add_parser(
        "setup",
        help="Configure a repository and verify non-interactive push access.",
    )
    setup.add_argument("repository_url", help="Git HTTPS or SSH repository address.")
    setup.add_argument(
        "--home",
        help="Perenna data directory. Overrides PERENNA_HOME; default: ~/.perenna.",
    )
    setup.add_argument(
        "--replace",
        action="store_true",
        help="Replace an existing remote that points to a different address.",
    )
    setup.add_argument(
        "--deploy-key",
        action="store_true",
        help="Generate and use a repository-specific SSH deploy key.",
    )
    status = backup_commands.add_parser(
        "status",
        help="Check the effective remote, access, and backup state.",
    )
    status.add_argument(
        "--home",
        help="Perenna data directory. Overrides PERENNA_HOME; default: ~/.perenna.",
    )
    return parser


def _add_runtime_arguments(command: argparse.ArgumentParser) -> None:
    command.add_argument(
        "--source",
        help="Trusted Agent source. Overrides PERENNA_SOURCE and is required if it is unset.",
    )
    command.add_argument(
        "--home",
        help="Perenna data directory. Overrides PERENNA_HOME; default: ~/.perenna.",
    )


def _port(value: str) -> int:
    port = int(value)
    if not 1 <= port <= 65535:
        raise argparse.ArgumentTypeError("port must be between 1 and 65535")
    return port


def main(argv: Sequence[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    _configure_logging()

    try:
        if args.command == "backup":
            _run_backup(args)
            return 0
        settings = resolve_settings(cli_home=args.home, cli_source=args.source)
        remote_settings = resolve_remote_settings() if args.command == "serve" else None
        core = PerennaCore(settings)
        if args.command == "mcp":
            asyncio.run(run_stdio(core))
        else:
            assert remote_settings is not None
            run_http(core, remote_settings, host=args.host, port=args.port)
    except PerennaError as exc:
        print(f"perenna: {exc}", file=sys.stderr)
        return 2
    except KeyboardInterrupt:
        return 130
    except Exception as exc:
        logging.getLogger(__name__).error("startup=failed error_type=%s", type(exc).__name__)
        print(
            "perenna: startup failed. Check the local stderr log and configuration, then retry.",
            file=sys.stderr,
        )
        return 1
    return 0


def _run_backup(args: argparse.Namespace) -> None:
    paths = RuntimePaths(resolve_home(args.home))
    remote_name = resolve_git_remote()
    if args.backup_command == "setup":
        report = setup_backup(
            paths.memory,
            args.repository_url,
            remote_name=remote_name,
            replace=args.replace,
            deploy_key=args.deploy_key,
        )
        _print_backup_report(report)
        return

    report = inspect_backup(paths.memory, remote_name=remote_name)
    if report is None:
        print(f"Memory repository: {paths.memory}")
        print("Automatic backup: disabled (PERENNA_GIT_REMOTE is empty)")
        return
    _print_backup_report(report)


def _print_backup_report(report: BackupReport) -> None:
    print(f"Memory repository: {report.repository}")
    print(f"Backup remote: {report.remote_name} -> {report.remote_url}")
    print(f"Branch: {report.branch}")
    if report.authentication == "deploy-key":
        print(f"Authentication: deploy key {report.deploy_key_fingerprint}")
    if report.repository_access == "ok":
        print("Repository access: ok")
    else:
        print("Repository access: pending (not confirmed with the configured deploy key)")
    if report.write_access == "ok":
        print("Write access: ok")
    else:
        print("Write access: pending (no local commit is available to test)")
    if report.state == "waiting-deploy-key":
        print("Backup state: waiting for deploy key authorization")
    elif report.state == "synchronized":
        print("Backup state: synchronized")
    elif report.state == "pending-push":
        print("Backup state: pending push")
    else:
        print("Backup state: pending first memory commit")
    if report.state == "waiting-deploy-key":
        print(f"Automatic backup: configured (remote: {report.remote_name})")
        print()
        print("Add this public key to the repository as a deploy key with write access:")
        if report.deploy_key_settings_url is not None:
            print(f"Open: {report.deploy_key_settings_url}")
        print(f"Title: Perenna backup ({report.deploy_key_fingerprint})")
        print(f"Public key: {report.deploy_key_public_key}")
        print("Enable: Allow write access")
        print("Then run the same backup setup command again.")
    else:
        print(f"Automatic backup: enabled (remote: {report.remote_name})")


def _configure_logging() -> None:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s %(message)s",
        stream=sys.stderr,
        force=True,
    )
