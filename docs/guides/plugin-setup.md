# Plugin Setup

The Perenna plugin bundles the `perenna-memory` Agent Skill with a local stdio
MCP connection. Use this path for Codex or Claude Code when you want one
marketplace installation instead of installing the Skill and registering the
MCP server separately.

## Prerequisites

Install [uv](https://docs.astral.sh/uv/) and configure a working Vexor
embedding provider first:

```bash
uvx vexor doctor
```

The plugin starts `uvx perenna@latest mcp`. `uvx` checks PyPI for the latest
stable Perenna release at startup and caches the resolved environment between
sessions. Starting the MCP server therefore requires PyPI access.

The client that loads the plugin must inherit `VEXOR_CONFIG_JSON`,
`VEXOR_API_KEY`, or the selected provider's environment variable. A remote
embedding provider receives memory text and search queries.

Successful `uvx perenna@latest sync setup` saves the optional Git
synchronization choice in the Perenna home. The client uses that saved choice
unless `PERENNA_GIT_REMOTE` provides a process-level override. See the
[configuration reference](../reference/configuration.md#git-remote-synchronization)
for remote selection and precedence.

The plugin runs Perenna's base distribution. Local embedding dependencies use
the standalone setup and its `perenna[local]` runtime described in
[Client setup](client-setup.md#use-local-embeddings).

## Codex

Add the repository Marketplace and install Perenna:

```bash
codex plugin marketplace add scarletkc/Perenna --ref main
codex plugin add perenna@perenna
```

Start a new Codex session after installation. The plugin starts:

```text
uvx perenna@latest mcp
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
uvx perenna@latest mcp
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
