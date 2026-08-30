from __future__ import annotations

import argparse
import asyncio
import json
import logging
import sys
from collections.abc import Sequence
from pathlib import Path

from perenna import DESCRIPTION, __version__
from perenna.cli_output import print_skill_report, print_sync_report
from perenna.config import (
    GitRemoteSelection,
    RuntimePaths,
    resolve_git_remote_selection,
    resolve_home,
    resolve_remote_settings,
    resolve_settings,
    save_git_remote,
    validate_loopback_host,
)
from perenna.core import PerennaCore
from perenna.errors import PerennaError
from perenna.git import GitRepository
from perenna.http_server import run_http, run_local_http
from perenna.mcp_server import run_stdio
from perenna.memory_commands import MEMORY_TOOL_NAMES, execute_memory_command
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

    call = subparsers.add_parser(
        "call",
        help="Call a memory tool with its MCP JSON arguments.",
        description=(
            "Call one public Perenna memory tool with the exact JSON argument object used by MCP."
        ),
        epilog=(
            "On success, stdout contains only the structured JSON result. Diagnostics use "
            "stderr. Exit statuses: 0 success, 2 invalid input or an expected operation failure, "
            "1 unexpected failure, 130 interrupted.\n\n"
            "Examples:\n"
            "  perenna call memory_read --input request.json\n"
            "  perenna call memory_write --input - --home /path/to/perenna-home"
        ),
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    call.add_argument(
        "tool_name",
        choices=MEMORY_TOOL_NAMES,
        help="Public memory tool to call.",
    )
    call.add_argument(
        "--input",
        dest="input_source",
        required=True,
        metavar="FILE",
        help="Read one MCP JSON argument object from FILE, or use '-' for standard input.",
    )
    _add_runtime_arguments(call)

    serve = subparsers.add_parser(
        "serve",
        help="Run the MCP server over Streamable HTTP.",
    )
    _add_runtime_arguments(serve)
    serve.add_argument(
        "--local-only",
        action="store_true",
        help=(
            "Serve without OAuth on a loopback IP for a local tunnel client. "
            "Non-loopback --host values are rejected."
        ),
    )
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
    disable = sync_commands.add_parser(
        "disable",
        help="Save local-only mode without removing the configured Git remote.",
    )
    disable.add_argument(
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
        call_input = _read_call_input(args.input_source) if args.command == "call" else None
        settings = resolve_settings(cli_home=args.home)
        local_http = args.command == "serve" and args.local_only
        if local_http:
            validate_loopback_host(args.host)
        remote_settings = (
            resolve_remote_settings() if args.command == "serve" and not local_http else None
        )
        core = PerennaCore(settings)
        if args.command == "call":
            _run_call(args, core, call_input)
        elif args.command == "mcp":
            asyncio.run(run_stdio(core))
        elif local_http:
            run_local_http(core, host=args.host, port=args.port)
        else:
            assert remote_settings is not None
            run_http(core, remote_settings, host=args.host, port=args.port)
    except PerennaError as exc:
        print(f"perenna: {exc}", file=sys.stderr)
        return 2
    except KeyboardInterrupt:
        return 130
    except Exception as exc:
        if args.command == "call":
            logging.getLogger(__name__).error(
                "memory_command=failed tool=%s error_type=%s",
                args.tool_name,
                type(exc).__name__,
            )
            print(
                "perenna: memory command failed. Check the local stderr log and Perenna home, "
                "then retry.",
                file=sys.stderr,
            )
        else:
            logging.getLogger(__name__).error("startup=failed error_type=%s", type(exc).__name__)
            print(
                "perenna: startup failed. Check the local stderr log and configuration, then "
                "retry.",
                file=sys.stderr,
            )
        return 1
    return 0


class _CallInputError(PerennaError):
    """The CLI could not load one JSON argument object."""


def _run_call(args: argparse.Namespace, core: PerennaCore, raw: object) -> None:
    payload = execute_memory_command(core, args.tool_name, raw)
    output = json.dumps(payload, ensure_ascii=False, separators=(",", ":"))
    sys.stdout.write(f"{output}\n")


def _read_call_input(source: str) -> object:
    label = "standard input" if source == "-" else f"{Path(source)}"
    try:
        raw = sys.stdin.read() if source == "-" else Path(source).read_text(encoding="utf-8")
    except (OSError, UnicodeError):
        raise _CallInputError(
            f"Could not read JSON input from {label}. Check the path, permissions, and UTF-8 "
            "encoding, then retry."
        ) from None
    try:
        value = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise _CallInputError(
            f"JSON input from {label} is invalid at line {exc.lineno}, column {exc.colno}. "
            "Provide one JSON object using the selected tool's MCP arguments."
        ) from None
    if not isinstance(value, dict):
        raise _CallInputError(
            f"JSON input from {label} must contain one object. Provide the selected tool's exact "
            "MCP argument object."
        )
    return value


def _run_sync(args: argparse.Namespace) -> None:
    paths = RuntimePaths(resolve_home(args.home))
    selection = resolve_git_remote_selection(home=paths.home)
    if args.sync_command == "setup":
        setup_remote = selection.remote or "origin"
        report = setup_sync(
            paths.memory,
            args.repository_url,
            remote_name=setup_remote,
            replace=args.replace,
            deploy_key=args.deploy_key,
        )
        print_sync_report(report)
        if report.state != "waiting-deploy-key":
            config_path = save_git_remote(paths.home, setup_remote)
            print(f"Saved runtime remote: {setup_remote} ({config_path})")
            effective = resolve_git_remote_selection(home=paths.home)
            if effective.remote != setup_remote:
                print("Effective runtime remains local because PERENNA_GIT_REMOTE is empty.")
                print(
                    "Unset that variable and restart running Perenna clients to use the saved "
                    "remote."
                )
            else:
                print("Restart running Perenna clients to use the saved remote.")
        return

    if args.sync_command == "disable":
        config_path = save_git_remote(paths.home, None)
        print(f"Memory repository: {paths.memory}")
        print(f"Saved synchronization preference: local-only ({config_path})")
        effective = resolve_git_remote_selection(home=paths.home)
        if effective.remote is None:
            _print_disabled_sync(effective)
            print("Restart running Perenna clients to use the saved preference.")
        else:
            print(
                f"Effective Git synchronization remains enabled by PERENNA_GIT_REMOTE="
                f"{effective.remote}."
            )
            print("Unset that variable and restart running Perenna clients to use local-only mode.")
        return

    report = inspect_sync(paths.memory, remote_name=selection.remote)
    if report is None:
        print(f"Memory repository: {paths.memory}")
        _print_disabled_sync(selection)
        if selection.source == "default":
            remotes = _configured_remote_names(paths.memory)
            if remotes:
                print(f"Configured Git remote detected: {', '.join(remotes)}")
                print(
                    "No synchronization choice is saved. Ask before running 'perenna sync setup "
                    "REPOSITORY_URL' or save local-only mode with 'perenna sync disable'."
                )
        return
    print_sync_report(report)
    if selection.source == "environment":
        print(f"Runtime remote source: PERENNA_GIT_REMOTE={selection.remote}")
    else:
        print("Runtime remote source: saved local preference")


def _print_disabled_sync(selection: GitRemoteSelection) -> None:
    if selection.source == "environment":
        print("Git synchronization: disabled (PERENNA_GIT_REMOTE is empty)")
    elif selection.source == "local-config":
        print("Git synchronization: disabled (saved local preference)")
    else:
        print("Git synchronization: disabled (no saved choice; PERENNA_GIT_REMOTE is unset)")


def _configured_remote_names(memory_path: Path) -> list[str]:
    if not (memory_path / ".git").is_dir():
        return []
    try:
        return sorted(GitRepository.open(memory_path).remote_names())
    except PerennaError:
        return []


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
