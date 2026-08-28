# Client Setup

This guide connects supported local MCP clients to the same Perenna home. It
assumes that [uv](https://docs.astral.sh/uv/) and its `uvx` command are
available on `PATH`. Each registration requests the latest stable Perenna
release from PyPI through `uvx`. The resolved runtime is independent of any
`perenna` executable already installed on `PATH`.

For ChatGPT web, choose the local
[Secure MCP Tunnel guide](secure-mcp-tunnel.md), the OAuth-protected
[self-hosting guide](self-hosting.md), or the third-party [Glama connection
guide](glama-chatgpt.md), according to where Perenna runs.

Codex and Claude Code users can instead follow the combined
[Plugin setup](plugin-setup.md), which installs the Agent Skill and MCP
connection together. The commands below are the standalone setup path; do not
combine both paths for the same client.

## Claude Code

Install Perenna's optional memory behavior skill for Claude Code:

```bash
uvx perenna@latest skill install --agent claude-code
```

Add Perenna as a user-scoped stdio server:

```bash
claude mcp add --transport stdio --scope user perenna -- uvx perenna@latest mcp
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
uvx perenna@latest skill install --agent codex
```

Add Perenna with the Codex CLI:

```bash
codex mcp add perenna -- uvx perenna@latest mcp
codex mcp list
```

The equivalent `~/.codex/config.toml` entry is:

```toml
[mcp_servers.perenna]
command = "uvx"
args = ["perenna@latest", "mcp"]
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
5. Set the command to `uvx`.
6. Add `perenna@latest` and `mcp` as separate arguments, in that order.
7. Save and restart the app.

Use `/mcp` in the composer to inspect connected servers.

## ChatGPT web

ChatGPT web does not start a local process or share the desktop stdio
configuration. It can reach a private Perenna process through Secure MCP Tunnel
or connect to a public Streamable HTTP endpoint.

- To keep Perenna on loopback without OAuth or a public inbound port, follow
  [Connect ChatGPT through Secure MCP Tunnel](secure-mcp-tunnel.md).
- To operate a public endpoint and OAuth resource server yourself, follow
  [Self-host Perenna for ChatGPT](self-hosting.md).
- To connect an existing Glama-hosted Perenna endpoint, follow
  [Connect a Glama MCP server to ChatGPT web](glama-chatgpt.md). The tokenized
  Glama instance URL uses ChatGPT's **No authentication** option, not OAuth.

## Cursor

Add Perenna to the global `~/.cursor/mcp.json` file:

```json
{
  "mcpServers": {
    "perenna": {
      "type": "stdio",
      "command": "uvx",
      "args": ["perenna@latest", "mcp"]
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
uvx perenna@latest mcp --home /path/to/perenna-home
```

Clients share memories only when they resolve the same home. The exact
precedence rules are in the
[configuration reference](../reference/configuration.md#perenna-home).

## Use an installed or source version

An intentionally installed or source-built Perenna version uses this runtime:

```text
perenna mcp
```

Use `perenna` as the command and `mcp` as its first argument in the client
configurations above. This path follows the installed package version until it
is upgraded or reinstalled.

## Pass runtime configuration

Embedding provider settings belong in Vexor configuration or environment
variables inherited by the Perenna process. Do not place API keys in a tracked
client configuration file. See
[Vexor provider configuration](../reference/configuration.md#vexor-provider-configuration)
for the supported sources and privacy boundary.

## Use local embeddings

The default `perenna@latest` runtime installs Perenna's base distribution. A
local Vexor provider also needs the `local` extra. Register this local-extra
command:

```text
uvx --refresh-package perenna --from "perenna[local]" perenna mcp
```

For configuration files, set the command to `uvx` and pass each remaining
token as a separate argument. `--refresh-package perenna` makes uv revalidate
the Perenna package before resolving the local-extra environment.

Successful `perenna sync setup` saves the optional Git synchronization choice
in the Perenna home. The client process uses that saved choice unless
`PERENNA_GIT_REMOTE` provides a process-level override. See
[Git remote synchronization](../reference/configuration.md#git-remote-synchronization)
for remote selection and precedence.

## Upstream client documentation

- [Claude Code MCP documentation](https://code.claude.com/docs/en/mcp)
- [OpenAI Docs: Model Context Protocol](https://learn.chatgpt.com/docs/extend/mcp?surface=cli)
- [Cursor MCP documentation](https://prod.cursor.com/docs/mcp)
