#!/usr/bin/env python3
"""Bump Perenna versions in one command.

Updates the Python package, MCP Registry manifest, Codex plugin, and Claude
plugin. It also regenerates both repository marketplaces and the plugin's Skill
mirror from canonical sources.

Usage:
    python scripts/bump_version.py 0.2.0
    python scripts/bump_version.py v0.2.0
    python scripts/bump_version.py 0.2.0 --note "Native plugin distribution"

``--note`` starts ``docs/release-notes/<version>.md``. Fill in its body before
opening the release pull request; a heading-only note fails the release.
"""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path

if __package__:
    from .sync_plugin import build_expected_files, sync_plugin
else:
    from sync_plugin import build_expected_files, sync_plugin

_VERSION_PATTERN = re.compile(
    r"^(0|[1-9]\d*)\."
    r"(0|[1-9]\d*)\."
    r"(0|[1-9]\d*)"
    r"(?:-(?:0|[1-9]\d*|\d*[A-Za-z-][0-9A-Za-z-]*)(?:\."
    r"(?:0|[1-9]\d*|\d*[A-Za-z-][0-9A-Za-z-]*))*)?"
    r"(?:\+[0-9A-Za-z-]+(?:\.[0-9A-Za-z-]+)*)?$"
)


def main(argv: list[str]) -> int:
    if any(arg in {"-h", "--help"} for arg in argv[1:]):
        print(__doc__.strip())
        return 0

    version, note_title = _parse_args(argv)
    return _run(
        version=version,
        repo_root=Path(__file__).resolve().parents[1],
        note_title=note_title,
    )


def _parse_args(argv: list[str]) -> tuple[str, str | None]:
    positional: list[str] = []
    note_title: str | None = None
    pending_note = False
    for arg in argv[1:]:
        if pending_note:
            note_title = arg
            pending_note = False
            continue
        if arg == "--note":
            pending_note = True
        elif arg.startswith("--note="):
            note_title = arg[len("--note=") :]
        elif arg.startswith("-"):
            raise SystemExit(f"Unknown option {arg!r}. Use --help for usage.")
        else:
            positional.append(arg)

    if pending_note:
        raise SystemExit("Option '--note' requires a title. Use --help for usage.")
    if note_title is not None and not note_title.strip():
        raise SystemExit("Option '--note' requires a non-empty title.")
    if note_title is not None and len(note_title.strip().splitlines()) > 1:
        raise SystemExit("Option '--note' requires a single-line title.")
    if len(positional) != 1:
        print(__doc__.strip())
        raise SystemExit(2)

    raw_input = positional[0]
    version = raw_input.strip()
    if version.startswith("v"):
        version = version[1:]
    if _VERSION_PATTERN.fullmatch(version) is None:
        raise SystemExit(
            f"Invalid version {raw_input!r}. Expected strict semantic versioning like 0.2.0."
        )
    return version, note_title.strip() if note_title is not None else None


def _run(*, version: str, repo_root: Path, note_title: str | None = None) -> int:
    root = repo_root.resolve()
    package_init = root / "src" / "perenna" / "__init__.py"
    server_manifest = root / "server.json"
    note_path = _release_note_path(root, version) if note_title is not None else None

    if note_path is not None and note_path.exists():
        raise SystemExit(f"{note_path} already exists; edit it instead of re-running --note.")

    package_text = _updated_python_version(package_init, version)
    server_text = _updated_server_version(server_manifest, version)
    build_expected_files(root, version)

    package_init.write_text(package_text, encoding="utf-8")
    server_manifest.write_text(server_text, encoding="utf-8")
    sync_plugin(root, check=False, version=version, quiet=True)

    print(f"Updated Perenna version to {version}")
    for relative in (
        Path("src/perenna/__init__.py"),
        Path("server.json"),
        Path("plugins/codex/perenna/.codex-plugin/plugin.json"),
        Path("plugins/claude/perenna/.claude-plugin/plugin.json"),
    ):
        print(f"- {root / relative}")

    if note_path is not None:
        note_path.parent.mkdir(parents=True, exist_ok=True)
        note_path.write_text(f"## {note_title}\n\n", encoding="utf-8")
        print(f"- {note_path} (write the body before opening the release pull request)")
    return 0


def _release_note_path(repo_root: Path, version: str) -> Path:
    return repo_root / "docs" / "release-notes" / f"{version}.md"


def _updated_python_version(path: Path, version: str) -> str:
    updated, count = re.subn(
        r'(?m)^__version__\s*=\s*"[^"]+"$',
        f'__version__ = "{version}"',
        path.read_text(encoding="utf-8"),
        count=1,
    )
    if count != 1:
        raise RuntimeError(f"Expected exactly one __version__ assignment in {path}")
    return updated


def _updated_server_version(path: Path, version: str) -> str:
    manifest = json.loads(path.read_text(encoding="utf-8"))
    manifest["version"] = version
    for package in manifest.get("packages", []):
        package["version"] = version
    return json.dumps(manifest, indent=2, ensure_ascii=False) + "\n"


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
