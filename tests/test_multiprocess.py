from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

from perenna.git import GitRepository
from perenna.store import MemoryStore
from tests.helpers import EmbeddingServer

WORKER = """
import sys
from perenna.config import resolve_settings
from perenna.core import PerennaCore

settings = resolve_settings(cli_home=sys.argv[1])
core = PerennaCore(settings)
core.create(
    title=sys.argv[2],
    summary=f'Concurrent memory from {sys.argv[2]}.',
    body=sys.argv[3],
    project='shared-project',
)
"""


def test_two_process_writers_create_two_clean_commits(tmp_path: Path) -> None:
    home = tmp_path / "home"
    with EmbeddingServer() as server:
        environment = os.environ.copy()
        environment.update(server.environment())
        environment["PERENNA_GIT_REMOTE"] = ""
        processes = [
            subprocess.Popen(
                [
                    sys.executable,
                    "-c",
                    WORKER,
                    os.fspath(home),
                    title,
                    body,
                ],
                cwd=Path(__file__).parents[1],
                env=environment,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
            )
            for title, body in (
                ("Writer A", "First concurrent memory"),
                ("Writer B", "Second concurrent memory"),
            )
        ]
        completed = [process.communicate(timeout=45) for process in processes]

    for process, (stdout, stderr) in zip(processes, completed, strict=True):
        assert process.returncode == 0, stderr
        assert stdout == ""

    repository = GitRepository.initialize(home / "memory")
    snapshot = MemoryStore(repository).snapshot()
    assert {memory.title for memory in snapshot.memories} == {"Writer A", "Writer B"}
    assert len({memory.id for memory in snapshot.memories}) == 2
    assert repository._run(["rev-list", "--count", "HEAD"]).stdout.strip() == "2"
    repository.assert_clean()
    assert (home / "index" / "indexed_commit").read_text().strip() == repository.head()
