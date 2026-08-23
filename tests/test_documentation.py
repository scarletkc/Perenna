from pathlib import Path

REPOSITORY_ROOT = Path(__file__).parents[1]
README_PATH = REPOSITORY_ROOT / "README.md"
AGENT_INSTALLATION_PATH = REPOSITORY_ROOT / "docs" / "guides" / "agent-installation.md"
DOCUMENTATION_INDEX_PATH = REPOSITORY_ROOT / "docs" / "index.md"
RAW_AGENT_INSTALLATION_URL = (
    "https://raw.githubusercontent.com/scarletkc/Perenna/main/"
    "docs/guides/agent-installation.md"
)
EXPECTED_README_AGENT_INSTALLATION_SECTION = (
    "Paste this into Claude Code, Codex, ChatGPT Desktop, Cursor, or another coding\n"
    "agent with terminal and local MCP configuration access:\n"
    "\n"
    "```text\n"
    "Open the following URL, read the complete instructions, and follow them to\n"
    "install and connect Perenna:\n"
    f"{RAW_AGENT_INSTALLATION_URL}\n"
    "```"
)


def test_readme_delegates_agent_installation_to_the_raw_canonical_guide() -> None:
    readme = README_PATH.read_text(encoding="utf-8")
    section = readme.split("### Install with your AI agent", maxsplit=1)[1].split(
        "### Install a published release", maxsplit=1
    )[0]
    guide = AGENT_INSTALLATION_PATH.read_text(encoding="utf-8")
    documentation_index = DOCUMENTATION_INDEX_PATH.read_text(encoding="utf-8")

    assert section.strip() == EXPECTED_README_AGENT_INSTALLATION_SECTION
    assert section.count(RAW_AGENT_INSTALLATION_URL) == 1
    assert "1. Detect the operating system" in guide
    assert "8. Report sanitized command shapes" in guide
    assert "guides/agent-installation.md" in documentation_index


def test_agent_installation_avoids_mixed_setup_and_propagates_safe_configuration() -> None:
    guide = AGENT_INSTALLATION_PATH.read_text(encoding="utf-8")
    flattened = " ".join(guide.split())

    assert "Choose exactly one path" in flattened
    assert "do not install the standalone Skill" in flattened
    assert guide.count("PERENNA_GIT_REMOTE") >= 2
    assert "Redact secrets and sensitive repository URLs" in flattened
    assert "without exposing its value" in flattened
