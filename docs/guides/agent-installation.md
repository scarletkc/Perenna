# Install Perenna with Your AI Agent

Install Perenna and connect it to this AI agent as a local stdio MCP server.
Work through the complete setup autonomously.

Use these as the source of truth:

- https://github.com/scarletkc/Perenna/blob/main/docs/getting-started.md
- https://github.com/scarletkc/Perenna/blob/main/docs/guides/client-setup.md
- https://github.com/scarletkc/Perenna/blob/main/docs/guides/plugin-setup.md
- https://github.com/scarletkc/Perenna/blob/main/docs/reference/configuration.md

1. Detect the operating system, shell, and current MCP client. For Codex or
   Claude Code, inspect whether the combined Perenna plugin is already
   installed by using the commands in the plugin setup guide. Choose exactly
   one path for this client: the existing plugin, or standalone Skill plus MCP
   registration.
2. Check for Python 3.12 or newer, Git, and uv. Install uv in user scope if it
   is missing. If Python or Git needs administrator approval, give me the exact
   command and stop there.
3. Install Perenna with `uv tool install perenna`. If Perenna is already
   installed, upgrade it with `uv tool upgrade perenna`.
   On the standalone path, run `perenna skill install --agent codex` for Codex
   or `perenna skill install --agent claude-code` for Claude Code. When the
   combined Perenna plugin is installed, do not install the standalone Skill
   or later register a second Perenna MCP server. Do not replace an existing
   modified copy or remove unrelated installed skills or plugins.
4. Check the effective Vexor embedding provider configuration. Reuse a working
   `~/.vexor/config.json` or inherited environment configuration. If none is
   available, ask me to choose between a remote provider and local embeddings.
   Explain that a remote provider receives memory text and search queries. For
   a remote provider, keep the provider and model in Vexor configuration and
   supply its secret through `VEXOR_API_KEY` or the provider-specific environment
   variable. For local embeddings, install `perenna[local]` and configure the
   local model according to the Perenna configuration reference. Verify the
   selected provider with `uvx vexor doctor` using the same environment that
   the Perenna process will inherit.
5. Ask whether I want to synchronize Perenna with a private Git repository. If
   I do, ask me to provide or approve its URL. Use `origin` unless I approve a
   different remote name, then set `PERENNA_GIT_REMOTE` to that name in the
   environment that runs
   `perenna sync setup <repository-url>`, `perenna sync status`, and the MCP
   process. Verify setup and status in that environment. Treat repository
   creation, remote replacement, and reconciling diverged history as separate
   choices that require my explicit approval.
6. On the standalone path, register `perenna mcp` using the client-specific
   method in the setup guide. Preserve unrelated MCP servers and settings. For
   another client, use its official instructions for adding a local stdio MCP
   server. On the plugin path, retain the bundled Perenna MCP connection and
   skip standalone registration. Make sure the Perenna process inherits
   `PERENNA_GIT_REMOTE` when synchronization is enabled, plus
   `VEXOR_CONFIG_JSON`, `VEXOR_API_KEY`, or any provider-specific key used in
   step 4. Report only whether a secret is present.
7. Verify `perenna --help` and the saved MCP configuration. Reload MCP servers
   and call `memory_read` with `action: "list"` when the client supports it. If
   a restart is required, tell me the single restart step. For Codex or Claude
   Code, confirm that the client does not have both plugin and standalone
   Perenna registrations.
8. Report sanitized command shapes, files changed, and verification results.
   Redact secrets and sensitive repository URLs from commands, environment
   assignments, and tool output. Report whether each secret was present without
   exposing its value, and keep secrets out of tracked configuration files.
