from __future__ import annotations

import argparse
import subprocess
import sys
import time
from collections.abc import Callable, Sequence

# The first request plus ten retries covers five minutes of registry propagation.
MAX_ATTEMPTS = 11
RETRY_DELAY_SECONDS = 30
_TRANSIENT_PYPI_LAG_MARKERS = (
    "PyPI package '",
    "exists, but version '",
    "was not found (status: 404)",
    "A newly published release can take a moment to appear on PyPI",
)


def _is_transient_pypi_lag(output: str) -> bool:
    return all(marker in output for marker in _TRANSIENT_PYPI_LAG_MARKERS)


def _write_publisher_output(output: str) -> None:
    if output:
        print(output, end="" if output.endswith("\n") else "\n", flush=True)


def publish(
    *,
    publisher: str,
    attempts: int = MAX_ATTEMPTS,
    delay_seconds: int = RETRY_DELAY_SECONDS,
    run_command: Callable[..., subprocess.CompletedProcess[str]] = subprocess.run,
    sleep: Callable[[float], None] = time.sleep,
) -> int:
    if attempts < 1:
        raise ValueError("attempts must be at least 1")
    if delay_seconds < 0:
        raise ValueError("delay_seconds must not be negative")

    login = run_command([publisher, "login", "github-oidc"], check=False)
    if login.returncode != 0:
        return login.returncode

    for attempt in range(1, attempts + 1):
        result = run_command(
            [publisher, "publish"],
            check=False,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
        )
        output = result.stdout or ""
        _write_publisher_output(output)

        if result.returncode == 0:
            return 0
        if not _is_transient_pypi_lag(output):
            return result.returncode
        if attempt == attempts:
            print(
                "MCP Registry still cannot resolve the PyPI release after "
                f"{attempts} attempts. Rerun the failed job after PyPI "
                "propagation completes.",
                file=sys.stderr,
            )
            return result.returncode

        print(
            "MCP Registry has not observed the PyPI release yet. "
            f"Retrying in {delay_seconds} seconds ({attempt}/{attempts}).",
            flush=True,
        )
        sleep(delay_seconds)

    raise AssertionError("retry loop completed without a result")


def _parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Publish Perenna to the MCP Registry with bounded retries."
    )
    parser.add_argument("--publisher", default="./mcp-publisher")
    return parser.parse_args(argv)


def main(argv: Sequence[str] | None = None) -> int:
    args = _parse_args(argv)
    return publish(publisher=args.publisher)


if __name__ == "__main__":
    raise SystemExit(main())
