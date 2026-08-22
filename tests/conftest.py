from __future__ import annotations

import subprocess
from collections.abc import Callable
from pathlib import Path

import pytest

from perenna.git import GitRepository


@pytest.fixture
def repository(tmp_path: Path) -> GitRepository:
    return GitRepository.initialize(tmp_path / "memory")


@pytest.fixture
def run_git() -> Callable[[Path, list[str]], subprocess.CompletedProcess[str]]:
    def run(path: Path, args: list[str]) -> subprocess.CompletedProcess[str]:
        return subprocess.run(
            ["git", *args],
            cwd=path,
            check=True,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="strict",
        )

    return run
