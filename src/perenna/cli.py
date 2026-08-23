from __future__ import annotations

import argparse
import asyncio
import logging
import sys
from collections.abc import Sequence

from perenna import DESCRIPTION, __version__
from perenna.cli_output import print_skill_report, print_sync_report
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
from perenna.skill_installer import SUPPORTED_AGENTS, install_bundled_skill
from perenna.sync import inspect_sync, setup_sync


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

    sync = subparsers.add_parser(
        "sync",
        help="Configure or inspect optional Git synchronization.",
    )
    sync_commands = sync.add_subparsers(dest="sync_command", required=True)
    setup = sync_commands.add_parser(
        "setup",
        help="Configure a repository and synchronize its current branch.",
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
    status = sync_commands.add_parser(
        "status",
        help="Check the effective remote, access, and synchronization state.",
    )
    status.add_argument(
        "--home",
        help="Perenna data directory. Overrides PERENNA_HOME; default: ~/.perenna.",
    )

    skill = subparsers.add_parser(
        "skill",
        help="Install Perenna's bundled Agent Skill.",
    )
    skill_commands = skill.add_subparsers(dest="skill_command", required=True)
    install = skill_commands.add_parser(
        "install",
        help="Install the perenna-memory skill for a supported agent.",
    )
    install.add_argument(
        "--agent",
        action="append",
        choices=SUPPORTED_AGENTS,
        required=True,
        help="Target agent. Repeat to install for both codex and claude-code.",
    )
    install.add_argument(
        "--scope",
        choices=("user", "project"),
        default="user",
        help="Install for the current user or Git project. Default: user.",
    )
    install.add_argument(
        "--replace",
        action="store_true",
        help="Back up and replace an installed copy that differs from the bundled skill.",
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
        if args.command == "sync":
            _run_sync(args)
            return 0
        if args.command == "skill":
            _run_skill(args)
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


def _run_sync(args: argparse.Namespace) -> None:
    paths = RuntimePaths(resolve_home(args.home))
    remote_name = resolve_git_remote()
    if args.sync_command == "setup":
        setup_remote = remote_name or "origin"
        report = setup_sync(
            paths.memory,
            args.repository_url,
            remote_name=setup_remote,
            replace=args.replace,
            deploy_key=args.deploy_key,
        )
        print_sync_report(report)
        if remote_name is None:
            print(
                f"Runtime mode: local until PERENNA_GIT_REMOTE={setup_remote} is set for "
                "Perenna."
            )
        return

    report = inspect_sync(paths.memory, remote_name=remote_name)
    if report is None:
        print(f"Memory repository: {paths.memory}")
        print("Git synchronization: disabled (PERENNA_GIT_REMOTE is unset or empty)")
        return
    print_sync_report(report)


def _run_skill(args: argparse.Namespace) -> None:
    reports = install_bundled_skill(
        args.agent,
        scope=args.scope,
        replace=args.replace,
    )
    for index, report in enumerate(reports):
        if index:
            print()
        print_skill_report(report)
    print()
    print("Restart the client if the skill does not appear.")


def _configure_logging() -> None:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s %(message)s",
        stream=sys.stderr,
        force=True,
    )
