from __future__ import annotations

import os
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path

import portalocker

from perenna.errors import RepositoryError

LOCK_TIMEOUT_SECONDS = 60


class RepositoryLocks:
    def __init__(self, index_dir: Path, *, timeout: int = LOCK_TIMEOUT_SECONDS) -> None:
        self.index_dir = index_dir
        self.repository_path = index_dir / "repository.lock"
        self.timeout = timeout

    @contextmanager
    def shared(self) -> Iterator[None]:
        with self._acquire(self.repository_path, portalocker.LockFlags.SHARED):
            yield

    @contextmanager
    def exclusive(self) -> Iterator[None]:
        with self._acquire(self.repository_path, portalocker.LockFlags.EXCLUSIVE):
            yield

    @contextmanager
    def _acquire(self, path: Path, flag: portalocker.LockFlags) -> Iterator[None]:
        self.index_dir.mkdir(parents=True, exist_ok=True)
        flags = flag | portalocker.LockFlags.NON_BLOCKING
        try:
            with portalocker.Lock(
                os.fspath(path),
                mode="a+b",
                timeout=self.timeout,
                check_interval=0.05,
                flags=flags,
            ):
                yield
        except portalocker.exceptions.LockException as exc:
            raise RepositoryError(
                f"Perenna could not acquire the local lock {path} within {self.timeout} seconds. "
                "Wait for the other local Agent operation to finish, then retry."
            ) from exc
