# Perenna Plugin

This plugin bundles the `perenna-memory` Agent Skill with a local stdio MCP
connection. The Codex and Claude packages start the same installed Perenna
command with host-specific source identities.

## Before installing

Install Perenna and configure a working Vexor embedding provider first:

```bash
uv tool install perenna
uvx vexor doctor
```

The plugin process must inherit the selected provider configuration and any
required API key. Remote embedding providers receive memory text and search
queries.

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
`perenna skill install` and client-specific MCP registration steps; it does not
replace Perenna or Vexor provider installation.

## Repository maintenance

This file, Perenna's package metadata, and the top-level
`skills/perenna-memory` directory are canonical sources. Do not edit generated
plugin copies directly. Run:

```bash
python scripts/sync_plugin.py
```
