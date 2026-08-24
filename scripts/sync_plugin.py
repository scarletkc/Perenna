#!/usr/bin/env python3
"""Generate Perenna's Codex and Claude plugin artifacts from canonical sources.

Usage:
    python scripts/sync_plugin.py
    python scripts/sync_plugin.py --check

The top-level ``skills/perenna-memory`` directory, ``plugins/README.md``,
``pyproject.toml``, and ``src/perenna/__init__.py`` are authoritative. Files in
the host-specific plugin roots and both repository marketplace manifests are
generated outputs.
"""

from __future__ import annotations

import argparse
import json
import re
import tomllib
from pathlib import Path
from typing import Any

PLUGIN_NAME = "perenna"
SKILL_NAME = "perenna-memory"
CODEX_PLUGIN_ROOT = Path("plugins/codex/perenna")
CLAUDE_PLUGIN_ROOT = Path("plugins/claude/perenna")

_VERSION_RE = re.compile(
    r"^(0|[1-9]\d*)\."
    r"(0|[1-9]\d*)\."
    r"(0|[1-9]\d*)"
    r"(?:-(?:0|[1-9]\d*|\d*[A-Za-z-][0-9A-Za-z-]*)(?:\."
    r"(?:0|[1-9]\d*|\d*[A-Za-z-][0-9A-Za-z-]*))*)?"
    r"(?:\+[0-9A-Za-z-]+(?:\.[0-9A-Za-z-]+)*)?$"
)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--check",
        action="store_true",
        help="Fail if generated plugin files differ from their canonical sources.",
    )
    args = parser.parse_args(argv)
    return sync_plugin(Path(__file__).resolve().parents[1], check=args.check)


def sync_plugin(
    repo_root: Path,
    *,
    check: bool,
    version: str | None = None,
    quiet: bool = False,
) -> int:
    root = repo_root.resolve()
    effective_version = version or read_package_version(root)
    expected = build_expected_files(root, effective_version)
    _reject_symlinked_output_parents(root, expected)
    extra = _extra_generated_skill_files(root, expected)
    changed = [
        relative
        for relative, contents in expected.items()
        if not _matches(root, relative, contents)
    ]

    if check:
        stale = [*changed, *extra]
        if stale:
            print("Generated plugin files are out of sync:")
            for relative in sorted(set(stale), key=lambda path: path.as_posix()):
                print(f"- {relative.as_posix()}")
            print("Run 'python scripts/sync_plugin.py' and commit the generated changes.")
            return 1
        if not quiet:
            print(f"Plugin artifacts are synchronized with Perenna {effective_version}.")
        return 0

    for relative in extra:
        (root / relative).unlink()
    _remove_empty_generated_directories(root)
    for relative in changed:
        destination = root / relative
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_bytes(expected[relative])

    if not quiet:
        if changed or extra:
            print(f"Synchronized plugin artifacts with Perenna {effective_version}.")
            for relative in sorted({*changed, *extra}, key=lambda path: path.as_posix()):
                print(f"- {relative.as_posix()}")
        else:
            print(f"Plugin artifacts are already synchronized with Perenna {effective_version}.")
    return 0


def read_package_version(repo_root: Path) -> str:
    path = repo_root / "src" / "perenna" / "__init__.py"
    match = re.search(
        r'(?m)^__version__\s*=\s*["\']([^"\']+)["\']$',
        path.read_text(encoding="utf-8"),
    )
    if match is None:
        raise RuntimeError(f"Unable to find __version__ in {path}")
    version = match.group(1)
    if _VERSION_RE.fullmatch(version) is None:
        raise RuntimeError(
            f"Perenna version {version!r} is not strict semantic versioning required by plugins."
        )
    return version


def build_expected_files(repo_root: Path, version: str) -> dict[Path, bytes]:
    if _VERSION_RE.fullmatch(version) is None:
        raise ValueError(
            f"Invalid plugin version {version!r}; expected strict semantic versioning."
        )

    metadata = _read_project_metadata(repo_root)
    environment_variables = _read_registry_environment_variable_names(repo_root)
    expected = {
        CODEX_PLUGIN_ROOT / ".codex-plugin/plugin.json": _json_bytes(
            _codex_manifest(metadata, version)
        ),
        CODEX_PLUGIN_ROOT / ".mcp.json": _json_bytes(
            _mcp_manifest(env_vars=environment_variables)
        ),
        CLAUDE_PLUGIN_ROOT / ".claude-plugin/plugin.json": _json_bytes(
            _claude_manifest(metadata, version)
        ),
        CLAUDE_PLUGIN_ROOT / ".mcp.json": _json_bytes(_mcp_manifest()),
        Path(".agents/plugins/marketplace.json"): _json_bytes(_codex_marketplace()),
        Path(".claude-plugin/marketplace.json"): _json_bytes(
            _claude_marketplace(metadata)
        ),
    }

    readme_source = repo_root / "plugins" / "README.md"
    if not readme_source.is_file():
        raise RuntimeError(f"Canonical plugin README is missing {readme_source}")
    for plugin_root in (CODEX_PLUGIN_ROOT, CLAUDE_PLUGIN_ROOT):
        expected[plugin_root / "README.md"] = readme_source.read_bytes()

    source_root = repo_root / "skills" / SKILL_NAME
    if not (source_root / "SKILL.md").is_file():
        raise RuntimeError(f"Canonical skill is missing {source_root / 'SKILL.md'}")
    for source in _regular_files(source_root):
        relative = source.relative_to(source_root)
        for plugin_root in (CODEX_PLUGIN_ROOT, CLAUDE_PLUGIN_ROOT):
            destination = plugin_root / "skills" / SKILL_NAME / relative
            expected[destination] = source.read_bytes()
    return expected


def _read_project_metadata(repo_root: Path) -> dict[str, Any]:
    path = repo_root / "pyproject.toml"
    project = tomllib.loads(path.read_text(encoding="utf-8")).get("project")
    if not isinstance(project, dict):
        raise RuntimeError(f"{path} is missing [project] metadata")

    authors = project.get("authors")
    author = authors[0].get("name") if isinstance(authors, list) and authors else None
    urls = project.get("urls")
    repository = urls.get("Repository") if isinstance(urls, dict) else None
    description = project.get("description")
    license_name = project.get("license")
    keywords = project.get("keywords")
    required = {
        "author": author,
        "repository": repository,
        "description": description,
        "license": license_name,
        "keywords": keywords,
    }
    missing = [key for key, value in required.items() if not value]
    if missing:
        raise RuntimeError(f"{path} is missing plugin metadata: {', '.join(missing)}")
    if not isinstance(keywords, list) or not all(isinstance(value, str) for value in keywords):
        raise RuntimeError(f"{path} project.keywords must be an array of strings")
    return required


def _read_registry_environment_variable_names(repo_root: Path) -> list[str]:
    path = repo_root / "server.json"
    manifest = json.loads(path.read_text(encoding="utf-8"))
    packages = manifest.get("packages")
    if not isinstance(packages, list) or len(packages) != 1:
        raise RuntimeError(f"{path} must declare exactly one package")

    environment_variables = packages[0].get("environmentVariables")
    if not isinstance(environment_variables, list):
        raise RuntimeError(f"{path} package is missing environmentVariables")

    names: list[str] = []
    for variable in environment_variables:
        name = variable.get("name") if isinstance(variable, dict) else None
        if not isinstance(name, str) or not name:
            raise RuntimeError(f"{path} contains an invalid environment variable declaration")
        if name in names:
            raise RuntimeError(f"{path} declares environment variable {name!r} more than once")
        names.append(name)
    return names


def _codex_manifest(metadata: dict[str, Any], version: str) -> dict[str, Any]:
    return {
        "name": PLUGIN_NAME,
        "version": version,
        "description": metadata["description"],
        "author": {"name": metadata["author"]},
        "homepage": metadata["repository"],
        "repository": metadata["repository"],
        "license": metadata["license"],
        "keywords": metadata["keywords"],
        "skills": "./skills/",
        "mcpServers": "./.mcp.json",
        "interface": {
            "displayName": "Perenna",
            "shortDescription": "Permanent shared memory for AI agents",
            "longDescription": (
                "Use Git-backed permanent memory across sessions, clients, and instances."
            ),
            "developerName": metadata["author"],
            "category": "Productivity",
            "capabilities": ["Read memory", "Write memory", "Delete memory"],
            "websiteURL": metadata["repository"],
            "defaultPrompt": [
                "Recall relevant permanent memory before starting this task.",
                "Save this durable decision to Perenna.",
            ],
        },
    }


def _claude_manifest(metadata: dict[str, Any], version: str) -> dict[str, Any]:
    return {
        "$schema": "https://json.schemastore.org/claude-code-plugin-manifest.json",
        "name": PLUGIN_NAME,
        "displayName": "Perenna",
        "version": version,
        "description": metadata["description"],
        "author": {"name": metadata["author"]},
        "homepage": metadata["repository"],
        "repository": metadata["repository"],
        "license": metadata["license"],
        "keywords": metadata["keywords"],
        "skills": "./skills/",
        "mcpServers": "./.mcp.json",
    }


def _mcp_manifest(*, env_vars: list[str] | None = None) -> dict[str, Any]:
    server = {
        "command": "perenna",
        "args": ["mcp"],
    }
    if env_vars:
        server["env_vars"] = env_vars
    return {
        "mcpServers": {
            "perenna": server,
        }
    }


def _codex_marketplace() -> dict[str, Any]:
    return {
        "name": "perenna",
        "interface": {"displayName": "Perenna"},
        "plugins": [
            {
                "name": PLUGIN_NAME,
                "source": {
                    "source": "local",
                    "path": "./plugins/codex/perenna",
                },
                "policy": {
                    "installation": "AVAILABLE",
                    "authentication": "ON_INSTALL",
                },
                "category": "Productivity",
            }
        ],
    }


def _claude_marketplace(metadata: dict[str, Any]) -> dict[str, Any]:
    return {
        "name": "perenna",
        "metadata": {
            "description": "Marketplace for the Perenna memory plugin."
        },
        "owner": {"name": metadata["author"]},
        "plugins": [
            {
                "name": PLUGIN_NAME,
                "source": "./plugins/claude/perenna",
                "description": metadata["description"],
                "category": "productivity",
                "tags": ["memory", "mcp", "git", "agents"],
                "strict": True,
            }
        ],
    }


def _json_bytes(payload: dict[str, Any]) -> bytes:
    text = json.dumps(payload, indent=2, ensure_ascii=False) + "\n"
    return text.replace("\n", "\r\n").encode()


def _regular_files(root: Path) -> list[Path]:
    files: list[Path] = []
    for path in sorted(root.rglob("*"), key=lambda value: value.as_posix()):
        if path.is_symlink():
            raise RuntimeError(f"Generated plugin sources cannot contain symlinks: {path}")
        if path.is_file():
            files.append(path)
    return files


def _matches(repo_root: Path, relative: Path, expected: bytes) -> bool:
    path = repo_root / relative
    return path.is_file() and not path.is_symlink() and path.read_bytes() == expected


def _extra_generated_skill_files(
    repo_root: Path,
    expected: dict[Path, bytes],
) -> list[Path]:
    expected_paths = {repo_root / relative for relative in expected}
    extra: list[Path] = []
    for plugin_root in (CODEX_PLUGIN_ROOT, CLAUDE_PLUGIN_ROOT):
        generated_root = repo_root / plugin_root / "skills" / SKILL_NAME
        if not generated_root.exists():
            continue
        if generated_root.is_symlink():
            raise RuntimeError(
                f"Generated skill destination cannot be a symlink: {generated_root}"
            )
        extra.extend(
            path.relative_to(repo_root)
            for path in _regular_files(generated_root)
            if path not in expected_paths
        )
    return extra


def _reject_symlinked_output_parents(
    repo_root: Path,
    expected: dict[Path, bytes],
) -> None:
    for relative in expected:
        current = repo_root
        for part in relative.parts[:-1]:
            current /= part
            if current.is_symlink():
                raise RuntimeError(f"Generated plugin output parent cannot be a symlink: {current}")


def _remove_empty_generated_directories(repo_root: Path) -> None:
    for plugin_root in (CODEX_PLUGIN_ROOT, CLAUDE_PLUGIN_ROOT):
        generated_root = repo_root / plugin_root / "skills" / SKILL_NAME
        if not generated_root.is_dir():
            continue
        directories = [path for path in generated_root.rglob("*") if path.is_dir()]
        for directory in sorted(directories, key=lambda path: len(path.parts), reverse=True):
            if not any(directory.iterdir()):
                directory.rmdir()


if __name__ == "__main__":
    raise SystemExit(main())
