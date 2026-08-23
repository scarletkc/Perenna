from __future__ import annotations

import json
from pathlib import Path

import pytest

from perenna import __version__
from scripts import sync_plugin

REPO_ROOT = Path(__file__).parents[1]


def test_repository_plugin_artifacts_are_synchronized() -> None:
    assert sync_plugin.sync_plugin(REPO_ROOT, check=True, quiet=True) == 0

    codex = json.loads(
        (REPO_ROOT / "plugins/codex/perenna/.codex-plugin/plugin.json").read_text(
            encoding="utf-8"
        )
    )
    claude = json.loads(
        (REPO_ROOT / "plugins/claude/perenna/.claude-plugin/plugin.json").read_text(
            encoding="utf-8"
        )
    )
    assert codex["version"] == claude["version"] == __version__
    codex_mcp = json.loads(
        (REPO_ROOT / "plugins/codex/perenna/.mcp.json").read_text(encoding="utf-8")
    )
    claude_mcp = json.loads(
        (REPO_ROOT / "plugins/claude/perenna/.mcp.json").read_text(encoding="utf-8")
    )
    assert codex_mcp["mcpServers"]["perenna"]["args"][-1] == "codex"
    assert claude_mcp["mcpServers"]["perenna"]["args"][-1] == "claude-code"
    server = json.loads((REPO_ROOT / "server.json").read_text(encoding="utf-8"))
    environment_variables = server["packages"][0]["environmentVariables"]
    assert codex_mcp["mcpServers"]["perenna"]["env_vars"] == [
        variable["name"] for variable in environment_variables
    ]
    assert "env_vars" not in claude_mcp["mcpServers"]["perenna"]
    assert (
        REPO_ROOT / "plugins/codex/perenna/skills/perenna-memory/SKILL.md"
    ).read_bytes() == (REPO_ROOT / "skills/perenna-memory/SKILL.md").read_bytes()
    assert (
        REPO_ROOT / "plugins/claude/perenna/skills/perenna-memory/SKILL.md"
    ).read_bytes() == (REPO_ROOT / "skills/perenna-memory/SKILL.md").read_bytes()
    assert server["version"] == __version__
    assert all(package["version"] == __version__ for package in server["packages"])


def test_generated_json_uses_the_repository_crlf_contract() -> None:
    generated = sync_plugin._json_bytes({"name": "perenna"})

    assert generated.endswith(b"\r\n")
    assert b"\n" not in generated.replace(b"\r\n", b"")


def test_sync_detects_and_repairs_changed_and_extra_generated_files(tmp_path: Path) -> None:
    _write_minimal_sources(tmp_path)

    assert sync_plugin.sync_plugin(tmp_path, check=False, quiet=True) == 0
    generated = tmp_path / "plugins/codex/perenna/skills/perenna-memory/SKILL.md"
    generated.write_text("stale", encoding="utf-8")
    extra = generated.parent / "obsolete.md"
    extra.write_text("obsolete", encoding="utf-8")

    assert sync_plugin.sync_plugin(tmp_path, check=True, quiet=True) == 1
    assert sync_plugin.sync_plugin(tmp_path, check=False, quiet=True) == 0
    assert generated.read_text(encoding="utf-8") == _skill_text()
    assert not extra.exists()
    assert sync_plugin.sync_plugin(tmp_path, check=True, quiet=True) == 0


def test_sync_rejects_symlinked_generated_destination(
    tmp_path: Path,
    monkeypatch,
) -> None:
    _write_minimal_sources(tmp_path)
    outside = tmp_path / "outside"
    outside.mkdir()
    destination = tmp_path / "plugins" / "codex" / "perenna"
    destination.parent.mkdir(parents=True)
    try:
        destination.symlink_to(outside, target_is_directory=True)
    except OSError:
        pytest.skip("directory symlinks are unavailable")

    with pytest.raises(RuntimeError, match="cannot be a symlink"):
        sync_plugin.sync_plugin(tmp_path, check=False, quiet=True)


def _write_minimal_sources(root: Path) -> None:
    package = root / "src" / "perenna"
    package.mkdir(parents=True)
    (package / "__init__.py").write_text('__version__ = "0.1.0"\n', encoding="utf-8")
    skill = root / "skills" / "perenna-memory"
    skill.mkdir(parents=True)
    (skill / "SKILL.md").write_text(_skill_text(), encoding="utf-8")
    (root / "pyproject.toml").write_text(
        """[project]
name = "Perenna"
version = "0.1.0"
description = "Permanent memory"
license = "MIT"
authors = [{ name = "scarletkc" }]
keywords = ["memory", "mcp"]

[project.urls]
Repository = "https://github.com/scarletkc/Perenna"
""",
        encoding="utf-8",
    )
    (root / "server.json").write_text(
        json.dumps(
            {
                "packages": [
                    {
                        "environmentVariables": [
                            {"name": "VEXOR_API_KEY"},
                            {"name": "VEXOR_CONFIG_JSON"},
                        ]
                    }
                ]
            }
        ),
        encoding="utf-8",
    )
    plugins = root / "plugins"
    plugins.mkdir()
    (plugins / "README.md").write_text("# Perenna Plugin\n", encoding="utf-8")


def _skill_text() -> str:
    return """---
name: perenna-memory
description: Use permanent memory when prior decisions matter.
---

# Perenna Memory
"""
