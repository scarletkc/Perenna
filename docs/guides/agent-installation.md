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
3. On the standalone path, install Perenna with `uv tool install perenna`, or
   upgrade it with `uv tool upgrade perenna`, then run
   `perenna skill install --agent codex` or
   `perenna skill install --agent claude-code` for the current client. When the
   combined Perenna plugin is installed, keep its bundled Skill and use
   `uvx perenna@latest` for Perenna maintenance commands. Do not install a
   second Skill or later register another Perenna MCP server. Do not replace an
   existing modified copy or remove unrelated installed skills or plugins.
4. Check the effective Vexor embedding provider configuration. Reuse a working
   `~/.vexor/config.json` or inherited environment configuration. If none is
   available, ask me to choose between a remote provider and local embeddings.
   Explain that a remote provider receives memory text and search queries. For
   a remote provider, keep the provider and model in Vexor configuration and
   supply its secret through `VEXOR_API_KEY` or the provider-specific
   environment variable. For local embeddings, use the standalone setup and
   register the `perenna[local]` runtime from the client setup guide. Configure
   the local model according to the Perenna configuration reference. Verify the
   selected provider with `uvx vexor doctor` using the same environment that
   the Perenna process will inherit.
5. Use `perenna` on the standalone path and `uvx perenna@latest` on the plugin
   path for every synchronization command in this step. Run `sync status`
   once. If it reports an existing Git remote but no saved synchronization
   choice, ask whether I want to enable that remote or save local-only mode. To
   enable it, reuse the exact remote name and URL that status reports and
   follow the configuration reference's setup command. To save local-only
   mode, run `sync disable` with the same command prefix. If status reports a
   saved preference or environment override, preserve it without asking again.
   When there is no saved choice and no existing remote, ask whether I want to
   synchronize Perenna with a private Git repository. If I do, ask me to
   provide or approve its URL. Use `origin` unless I approve a different remote
   name, then run `sync setup <repository-url>` with the same command prefix.
   Verify `sync status` after any setup or disable command. Successful setup
   saves the selected remote in the Perenna home; use `PERENNA_GIT_REMOTE` only
   when this host needs an environment override. Treat repository creation,
   remote replacement, credential changes, and reconciling diverged history as
   separate choices that require my explicit approval.
6. On the standalone path, register `uvx perenna@latest mcp` using the
   client-specific method in the setup guide. Preserve unrelated MCP servers
   and settings. For another client, use its official instructions for adding
   a local stdio MCP server. On the plugin path, retain the bundled Perenna MCP
   connection as the sole registration. Make sure the Perenna process uses the
   synchronization preference or the approved `PERENNA_GIT_REMOTE` override,
   plus `VEXOR_CONFIG_JSON`, `VEXOR_API_KEY`, or any provider-specific key used
   in step 4. Report only whether a secret is present.
7. Verify `perenna --help` on the standalone path or
   `uvx perenna@latest --help` on the plugin path, then inspect the saved MCP
   configuration. Reload MCP servers and call `memory_read` with action `list`
   when the client supports it. If a restart is required, tell me the single
   restart step. For Codex or Claude Code, confirm that the client does not
   have both plugin and standalone
   Perenna registrations.
8. Report sanitized command shapes, files changed, and verification results.
   Redact secrets and sensitive repository URLs from commands, environment
   assignments, and tool output. Report whether each secret was present without
   exposing its value, and keep secrets out of tracked configuration files.
