import os
from pathlib import Path

import pytest

from perenna.config import RuntimePaths, RuntimeSettings
from perenna.core import PerennaCore


@pytest.mark.live_provider
def test_configured_vexor_provider_smoke(tmp_path: Path) -> None:
    if os.getenv("PERENNA_RUN_LIVE_PROVIDER") != "1":
        pytest.skip("set PERENNA_RUN_LIVE_PROVIDER=1 to run the live provider smoke test")
    core = PerennaCore(
        RuntimeSettings(
            paths=RuntimePaths(tmp_path / "home"),
            source="provider-smoke",
            git_remote=None,
        )
    )
    result = core.write(title="Provider smoke", body="Temporary provider smoke test memory.")
    assert "committed to Git" in result
    assert "Provider smoke" in core.recall(query="provider smoke")
