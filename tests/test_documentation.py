from pathlib import Path

REPOSITORY_ROOT = Path(__file__).parents[1]
README_PATH = REPOSITORY_ROOT / "README.md"
AGENT_INSTALLATION_PATH = REPOSITORY_ROOT / "docs" / "guides" / "agent-installation.md"
DOCUMENTATION_INDEX_PATH = REPOSITORY_ROOT / "docs" / "index.md"
RAW_AGENT_INSTALLATION_URL = (
    "https://raw.githubusercontent.com/scarletkc/Perenna/main/"
    "docs/guides/agent-installation.md"
)


def test_readme_delegates_agent_installation_to_the_raw_canonical_guide() -> None:
    readme = README_PATH.read_text(encoding="utf-8")
    section = readme.split("### Install with your AI agent", maxsplit=1)[1].split(
        "### Install a published release", maxsplit=1
    )[0]
    guide = AGENT_INSTALLATION_PATH.read_text(encoding="utf-8")
    documentation_index = DOCUMENTATION_INDEX_PATH.read_text(encoding="utf-8")

    assert RAW_AGENT_INSTALLATION_URL in section
    assert "1. Detect the operating system" not in section
    assert "1. Detect the operating system" in guide
    assert "8. Report the commands run" in guide
    assert "guides/agent-installation.md" in documentation_index
