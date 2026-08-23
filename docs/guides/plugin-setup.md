# Plugin Setup

The Perenna plugin bundles the `perenna-memory` Agent Skill with a local stdio
MCP connection. Use this path for Codex or Claude Code when you want one
marketplace installation instead of installing the Skill and registering the
MCP server separately.

## Prerequisites

Install Perenna and configure a working Vexor embedding provider first:

```bash
uv tool install perenna
uvx vexor doctor
```

The client that loads the plugin must inherit `VEXOR_CONFIG_JSON`,
`VEXOR_API_KEY`, or the selected provider's environment variable. A remote
embedding provider receives memory text and search queries.

When optional Git synchronization is enabled, the client must also inherit the
same `PERENNA_GIT_REMOTE` used by `perenna sync setup` and
`perenna sync status`. See the
[configuration reference](../reference/configuration.md#git-remote-synchronization)
for the runtime contract.

## Codex

Add the repository Marketplace and install Perenna:

```bash
codex plugin marketplace add scarletkc/Perenna --ref main
codex plugin add perenna@perenna
```

Start a new Codex session after installation. The plugin starts:

```text
perenna mcp --source codex
```

Inspect the installed plugin and its Marketplace with:

```bash
codex plugin list
codex plugin marketplace list
```

Refresh the Git-backed Marketplace before reinstalling an updated plugin:

```bash
codex plugin marketplace upgrade perenna
codex plugin add perenna@perenna
```

## Claude Code

Add the repository Marketplace and install Perenna:

```bash
claude plugin marketplace add scarletkc/Perenna
claude plugin install perenna@perenna
```

Start a new Claude Code session after installation. The plugin starts:

```text
perenna mcp --source claude-code
```

Inspect or update the installed plugin with:

```bash
claude plugin details perenna@perenna
claude plugin update perenna@perenna
```

Claude Code can update a Marketplace and its installed plugins in the
background after auto-update is enabled for that Marketplace. New plugin
components load after `/reload-plugins` or in the next session.

## Verify memory access

After starting the new session:

1. Confirm that the `perenna` MCP server is active.
2. Call `memory_read` with `action: "list"`.
3. Confirm that the `perenna-memory` Skill is available.

Do not also run `perenna skill install` or add a second client-level Perenna MCP
entry for the same client. Those are the standalone setup path; using both
creates duplicate Skill or server registrations without creating another
memory store.
