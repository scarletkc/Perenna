# Client Setup

This guide connects supported local MCP clients to the same Perenna home. It
assumes that `perenna` is installed and available on `PATH`.

For an OAuth-protected ChatGPT web connection to a VPS, use the separate
[self-hosting guide](self-hosting.md).

Codex and Claude Code users can instead follow the combined
[Plugin setup](plugin-setup.md), which installs the Agent Skill and MCP
connection together. The commands below are the standalone setup path; do not
combine both paths for the same client.

## Claude Code

Install Perenna's optional memory behavior skill for Claude Code:

```bash
perenna skill install --agent claude-code
```

Add Perenna as a user-scoped stdio server:

```bash
claude mcp add --transport stdio --scope user perenna -- perenna mcp
```

Verify the saved configuration and connection:

```bash
claude mcp get perenna
claude mcp list
```

Inside Claude Code, `/mcp` shows the active server and its tools.

Claude Code requires its own options before the server name. The `--`
separator marks the start of the Perenna command and arguments.

## Codex CLI and IDE extension

Install Perenna's optional memory behavior skill for Codex:

```bash
perenna skill install --agent codex
```

Add Perenna with the Codex CLI:

```bash
codex mcp add perenna -- perenna mcp
codex mcp list
```

The equivalent `~/.codex/config.toml` entry is:

```toml
[mcp_servers.perenna]
command = "perenna"
args = ["mcp"]
```

The Codex CLI and IDE extension share this configuration on the same Codex
host. Restart the active client after editing the file manually.

## ChatGPT Desktop

ChatGPT Desktop shares MCP configuration with Codex on the same host. You can
use the Codex CLI command above, or configure the server from the desktop app:

1. Open **Settings**.
2. Select **MCP servers**.
3. Add a server named `perenna`.
4. Choose **STDIO**.
5. Set the command to `perenna`.
6. Set the arguments to `mcp`.
7. Save and restart the app.

Use `/mcp` in the composer to inspect connected servers.

## ChatGPT web

ChatGPT web connects to `perenna serve` through a public HTTPS reverse proxy
and OAuth. It does not start a local process or share the desktop stdio
configuration. Follow [Self-host Perenna for ChatGPT](self-hosting.md).

## Cursor

Add Perenna to the global `~/.cursor/mcp.json` file:

```json
{
  "mcpServers": {
    "perenna": {
      "type": "stdio",
      "command": "perenna",
      "args": ["mcp"]
    }
  }
}
```

Use `.cursor/mcp.json` instead when the server should be available only in one
project. Cursor requires `type`, `command`, and an argument array for a custom
stdio server. Restart Cursor after changing the file, then inspect the server
under **Customize** or in the MCP logs.

## Use a non-default home

Add `--home` to the server arguments when a client should use another Perenna
home:

```text
perenna mcp --home /path/to/perenna-home
```

Clients share memories only when they resolve the same home. The exact
precedence rules are in the
[configuration reference](../reference/configuration.md#perenna-home).

## Pass runtime configuration

Embedding provider settings belong in Vexor configuration or environment
variables inherited by the Perenna process. Do not place API keys in a tracked
client configuration file. See
[Vexor provider configuration](../reference/configuration.md#vexor-provider-configuration)
for the supported sources and privacy boundary.

When optional Git synchronization is enabled, the client process must also
inherit the same `PERENNA_GIT_REMOTE` used by `perenna sync setup` and
`perenna sync status`. Configuring the repository remote without forwarding
that runtime value leaves Perenna in local-only mode. See
[Git remote synchronization](../reference/configuration.md#git-remote-synchronization)
for the complete contract.

## Upstream client documentation

- [Claude Code MCP documentation](https://code.claude.com/docs/en/mcp)
- [OpenAI Docs: Model Context Protocol](https://learn.chatgpt.com/docs/extend/mcp?surface=cli)
- [Cursor MCP documentation](https://prod.cursor.com/docs/mcp)
