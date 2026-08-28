# Perenna Plugin

This plugin bundles the `perenna-memory` Agent Skill with a local stdio MCP
connection. The Codex and Claude packages start the latest stable Perenna
release from PyPI with `uvx`.

## Before installing

Install [uv](https://docs.astral.sh/uv/) and configure a working Vexor
embedding provider first:

```bash
uvx vexor doctor
```

The plugin starts `uvx perenna@latest mcp`. `uvx` refreshes the published
Perenna version when the MCP server starts, so startup requires access to
PyPI. The resolved environment is cached between sessions.

The plugin runs Perenna's base distribution. Local embedding dependencies use
the standalone setup in
[Getting Started](https://github.com/scarletkc/Perenna/blob/main/docs/getting-started.md#configure-retrieval).

The plugin process must inherit the selected provider configuration and any
required API key. Remote embedding providers receive memory text and search
queries.

Successful `uvx perenna@latest sync setup` saves the optional Git
synchronization choice in the Perenna home. The plugin process uses that saved
choice unless `PERENNA_GIT_REMOTE` provides a process-level override.

For complete installation, configuration, privacy, synchronization, and troubleshooting
guidance, see the
[Perenna documentation](https://github.com/scarletkc/Perenna/blob/main/docs/index.md).

## Install from the repository Marketplace

Codex:

```bash
codex plugin marketplace add scarletkc/Perenna --ref main
codex plugin add perenna@perenna
```

Claude Code:

```bash
claude plugin marketplace add scarletkc/Perenna
claude plugin install perenna@perenna
```

Start a new session after installation. The plugin replaces the separate
`perenna skill install` and client-specific MCP registration steps. It still
requires `uv` and a working Vexor provider configuration.

## Repository maintenance

This file, Perenna's package metadata, and the top-level
`skills/perenna-memory` directory are canonical sources. Do not edit generated
plugin copies directly. Run:

```bash
python scripts/sync_plugin.py
```
