from __future__ import annotations

import json
from pathlib import Path

import pytest

from scripts import bump_version
from tests.test_plugin_sync import _write_minimal_sources


def test_bump_version_updates_package_registry_and_both_plugins(tmp_path: Path) -> None:
    _write_minimal_sources(tmp_path)
    _write_server_manifest(tmp_path)

    assert bump_version._run(version="1.2.3", repo_root=tmp_path) == 0

    assert '__version__ = "1.2.3"' in (
        tmp_path / "src/perenna/__init__.py"
    ).read_text(encoding="utf-8")
    server = json.loads((tmp_path / "server.json").read_text(encoding="utf-8"))
    assert server["version"] == "1.2.3"
    assert server["packages"][0]["version"] == "1.2.3"
    for manifest in (
        tmp_path / "plugins/codex/perenna/.codex-plugin/plugin.json",
        tmp_path / "plugins/claude/perenna/.claude-plugin/plugin.json",
    ):
        assert json.loads(manifest.read_text(encoding="utf-8"))["version"] == "1.2.3"


def test_bump_version_starts_an_optional_release_note(tmp_path: Path) -> None:
    _write_minimal_sources(tmp_path)
    _write_server_manifest(tmp_path)

    bump_version._run(
        version="1.2.3",
        repo_root=tmp_path,
        note_title="Native plugin distribution",
    )

    note = tmp_path / "docs/release-notes/1.2.3.md"
    assert note.read_text(encoding="utf-8") == "## Native plugin distribution\n\n"


def test_bump_version_refuses_existing_note_before_changing_versions(tmp_path: Path) -> None:
    _write_minimal_sources(tmp_path)
    _write_server_manifest(tmp_path)
    note = tmp_path / "docs/release-notes/1.2.3.md"
    note.parent.mkdir(parents=True)
    note.write_text("## Existing\n\nKeep me.\n", encoding="utf-8")

    with pytest.raises(SystemExit, match="already exists"):
        bump_version._run(
            version="1.2.3",
            repo_root=tmp_path,
            note_title="Replacement",
        )

    assert '__version__ = "0.1.0"' in (
        tmp_path / "src/perenna/__init__.py"
    ).read_text(encoding="utf-8")
    assert json.loads((tmp_path / "server.json").read_text(encoding="utf-8"))[
        "version"
    ] == "0.1.0"


@pytest.mark.parametrize(
    "argv",
    [
        ["bump_version.py", "1.2"],
        ["bump_version.py", "1.2.3rc1"],
        ["bump_version.py", "--unknown", "1.2.3"],
        ["bump_version.py", "1.2.3", "--note"],
        ["bump_version.py", "1.2.3", "--note", "first\nsecond"],
    ],
)
def test_bump_version_rejects_invalid_arguments(argv: list[str]) -> None:
    with pytest.raises(SystemExit):
        bump_version._parse_args(argv)


def test_bump_version_accepts_v_prefix_and_semver_prerelease() -> None:
    assert bump_version._parse_args(["bump_version.py", "v1.2.3-rc.1"]) == (
        "1.2.3-rc.1",
        None,
    )


def _write_server_manifest(root: Path) -> None:
    (root / "server.json").write_text(
        json.dumps(
            {
                "version": "0.1.0",
                "packages": [{"identifier": "perenna", "version": "0.1.0"}],
            },
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )
