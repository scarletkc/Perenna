from __future__ import annotations

import subprocess
from collections.abc import Sequence
from pathlib import Path
from typing import Any

from scripts import publish_mcp_registry

TRANSIENT_PYPI_LAG = (
    "Error: registry validation failed: PyPI package 'perenna' exists, but version "
    "'0.4.0' was not found (status: 404). A newly published release can take a "
    "moment to appear on PyPI. Wait and retry.\n"
)
REPOSITORY_ROOT = Path(__file__).parents[1]


class CommandRunner:
    def __init__(self, results: Sequence[subprocess.CompletedProcess[str]]) -> None:
        self._results = iter(results)
        self.calls: list[list[str]] = []

    def __call__(self, args: list[str], **_: Any) -> subprocess.CompletedProcess[str]:
        self.calls.append(args)
        return next(self._results)


def _result(returncode: int, stdout: str | None = None) -> subprocess.CompletedProcess[str]:
    return subprocess.CompletedProcess([], returncode, stdout=stdout)


def test_publish_retries_pypi_propagation_lag_then_succeeds(capsys: Any) -> None:
    runner = CommandRunner(
        [_result(0), _result(1, TRANSIENT_PYPI_LAG), _result(0, "published\n")]
    )
    sleeps: list[float] = []

    result = publish_mcp_registry.publish(
        publisher="publisher",
        attempts=3,
        delay_seconds=15,
        run_command=runner,
        sleep=sleeps.append,
    )

    assert result == 0
    assert runner.calls == [
        ["publisher", "login", "github-oidc"],
        ["publisher", "publish"],
        ["publisher", "publish"],
    ]
    assert sleeps == [15]
    output = capsys.readouterr().out
    assert "Retrying in 15 seconds (1/3)." in output
    assert "published" in output


def test_publish_returns_non_retryable_failure_immediately(capsys: Any) -> None:
    runner = CommandRunner([_result(0), _result(1, "authentication failed\n")])
    sleeps: list[float] = []

    result = publish_mcp_registry.publish(
        publisher="publisher",
        run_command=runner,
        sleep=sleeps.append,
    )

    assert result == 1
    assert runner.calls == [
        ["publisher", "login", "github-oidc"],
        ["publisher", "publish"],
    ]
    assert sleeps == []
    assert capsys.readouterr().out == "authentication failed\n"


def test_publish_reports_exhausted_propagation_retries(capsys: Any) -> None:
    runner = CommandRunner(
        [_result(0), _result(1, TRANSIENT_PYPI_LAG), _result(1, TRANSIENT_PYPI_LAG)]
    )
    sleeps: list[float] = []

    result = publish_mcp_registry.publish(
        publisher="publisher",
        attempts=2,
        delay_seconds=5,
        run_command=runner,
        sleep=sleeps.append,
    )

    assert result == 1
    assert sleeps == [5]
    captured = capsys.readouterr()
    assert "Retrying in 5 seconds (1/2)." in captured.out
    assert (
        "MCP Registry still cannot resolve the PyPI release after 2 attempts."
        in captured.err
    )
    assert "Rerun the failed job after PyPI propagation completes." in captured.err


def test_publish_stops_when_oidc_login_fails() -> None:
    runner = CommandRunner([_result(2)])

    result = publish_mcp_registry.publish(
        publisher="publisher",
        run_command=runner,
        sleep=lambda _: None,
    )

    assert result == 2
    assert runner.calls == [["publisher", "login", "github-oidc"]]


def test_publish_workflow_uses_retry_helper() -> None:
    workflow = (REPOSITORY_ROOT / ".github/workflows/publish.yml").read_text(
        encoding="utf-8"
    )

    assert workflow.count("python scripts/publish_mcp_registry.py") == 1
