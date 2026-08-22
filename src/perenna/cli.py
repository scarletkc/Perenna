from __future__ import annotations

import argparse
import asyncio
import logging
import sys
from collections.abc import Sequence

from perenna.config import resolve_settings
from perenna.core import PerennaCore
from perenna.errors import PerennaError
from perenna.mcp_server import run_stdio


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="perenna",
        description="Local-first permanent memory for AI agents.",
    )
    subparsers = parser.add_subparsers(dest="command", required=True)
    mcp = subparsers.add_parser("mcp", help="Run the local MCP server over stdio.")
    mcp.add_argument(
        "--source",
        help="Trusted Agent source. Overrides PERENNA_SOURCE and is required if it is unset.",
    )
    mcp.add_argument(
        "--home",
        help="Perenna data directory. Overrides PERENNA_HOME; default: ~/.perenna.",
    )
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    _configure_logging()

    try:
        settings = resolve_settings(cli_home=args.home, cli_source=args.source)
        core = PerennaCore(settings)
        asyncio.run(run_stdio(core))
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


def _configure_logging() -> None:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s %(message)s",
        stream=sys.stderr,
        force=True,
    )
