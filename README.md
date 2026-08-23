<div align="center">

# Perenna

[![Python](https://img.shields.io/badge/python-3.12%2B-blue)](https://www.python.org/downloads/)
[![PyPI](https://img.shields.io/pypi/v/perenna.svg)](https://pypi.org/project/perenna/)
[![CI](https://img.shields.io/github/actions/workflow/status/scarletkc/Perenna/validate.yml?branch=main)](https://github.com/scarletkc/Perenna/actions/workflows/validate.yml)
[![CodeRabbit Pull Request Reviews](https://img.shields.io/coderabbit/prs/github/scarletkc/Perenna?utm_source=oss&utm_medium=github&utm_campaign=scarletkc%2FPerenna&labelColor=171717&color=FF570A&link=https%3A%2F%2Fcoderabbit.ai&label=CodeRabbit+Reviews)](https://coderabbit.ai)
[![License](https://img.shields.io/github/license/scarletkc/Perenna.svg)](https://github.com/scarletkc/Perenna/blob/main/LICENSE)
[![Ask DeepWiki](https://deepwiki.com/badge.svg)](https://deepwiki.com/scarletkc/Perenna)

</div>

---

A lightweight, Git-backed permanent memory for AI agents. Claude Code, Codex,
ChatGPT, Cursor, and other MCP clients can share durable memories without
sharing a vendor account or conversation history.

- Separate MCP tools for reading, writing, and deleting memories
- Local stdio and single-user OAuth-protected Streamable HTTP transports
- Human-readable Markdown stored in an independent Git repository
- Local Vexor retrieval index that can always be rebuilt from Git
- Cross-process locking for multiple local agent processes

## Quickstart

### Install with your AI agent

Paste this into Claude Code, Codex, ChatGPT Desktop, Cursor, or another coding
agent with terminal and local MCP configuration access:

```text
Install Perenna and connect it to this AI agent as a local stdio MCP server.
Work through the complete setup autonomously.

Use these as the source of truth:
- https://github.com/scarletkc/Perenna/blob/main/docs/getting-started.md
- https://github.com/scarletkc/Perenna/blob/main/docs/guides/client-setup.md

1. Detect the operating system, shell, and current MCP client.
2. Check for Python 3.12 or newer, Git, and uv. Install uv in user scope if it
   is missing. If Python or Git needs administrator approval, give me the exact
   command and stop there.
3. Install Perenna with `uv tool install perenna`. If Perenna is already
   installed, upgrade it with `uv tool upgrade perenna`.
   If this client supports Agent Skills, also install the bundled
   `perenna-memory` skill from
   `https://github.com/scarletkc/Perenna/tree/main/skills/perenna-memory`
   through the client's normal skill installation mechanism. Do not replace or
   remove unrelated installed skills.
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
5. Ask whether I want to back up Perenna to an empty private Git repository. If
   I do, ask me to provide or approve its URL, run
   `perenna backup setup <repository-url>`, and verify it with
   `perenna backup status`. Treat repository creation, remote replacement, and
   any existing non-empty remote as separate choices that require my explicit
   approval.
6. Register `perenna mcp --source <stable-client-name>` using the client-specific
   method in the setup guide. Preserve unrelated MCP servers and settings. Use
   a stable source such as `claude-code`, `codex`, or `cursor` for this client.
   For another client, use its official instructions for adding a local stdio
   MCP server. Make sure the Perenna process inherits `VEXOR_CONFIG_JSON`,
   `VEXOR_API_KEY`, or any provider-specific key used in step 4. Report only
   whether a secret is present.
7. Verify `perenna --help` and the saved MCP configuration. Reload MCP servers
   and call `memory_read` with `action: "list"` when the client supports it. If
   a restart is required, tell me the single restart step.
8. Report the commands run, files changed, and verification results. Keep API
   keys out of tracked configuration files.
```

### Install a published release

Perenna requires Python 3.12+, Git, and
[uv](https://docs.astral.sh/uv/).

```bash
uv tool install perenna
```

Perenna needs a working Vexor embedding provider. For interactive provider
selection and configuration, run:

```bash
uvx vexor init
```

Perenna automatically reuses `~/.vexor/config.json`. When using process-level
configuration, make sure the MCP server receives `VEXOR_CONFIG_JSON` plus
`VEXOR_API_KEY` or the selected provider's key from its host environment.
Remote providers receive memory text and search queries.

If you choose local embeddings, also install Perenna's local extra:

```bash
uv tool install "perenna[local]"
```

[Vexor provider configuration](https://github.com/scarletkc/Perenna/blob/main/docs/reference/configuration.md#vexor-provider-configuration)
covers remote and local setup. From the environment that starts the MCP client,
verify the selected provider with:

```bash
uvx vexor doctor
```

Configure an MCP client to start:

```text
perenna mcp --source <client-name>
```

Perenna creates its local data under `~/.perenna/` unless another home is
configured.

For best-effort backup, attach an empty private Git repository:

```bash
perenna backup setup <repository-url>
```

### Install from source for development

```bash
git clone https://github.com/scarletkc/Perenna.git
cd Perenna
uv tool install .
```

## Documentation

Start with the
[documentation index](https://github.com/scarletkc/Perenna/blob/main/docs/index.md),
then follow the path for your task:

- [Getting started](https://github.com/scarletkc/Perenna/blob/main/docs/getting-started.md)
- [Client setup](https://github.com/scarletkc/Perenna/blob/main/docs/guides/client-setup.md)
- [Self-hosting for ChatGPT](https://github.com/scarletkc/Perenna/blob/main/docs/guides/self-hosting.md)
- [Using permanent memory](https://github.com/scarletkc/Perenna/blob/main/docs/guides/using-memory.md)
- [`perenna-memory` Agent Skill](https://github.com/scarletkc/Perenna/blob/main/skills/perenna-memory/SKILL.md)
- [Configuration reference](https://github.com/scarletkc/Perenna/blob/main/docs/reference/configuration.md)
- [Architecture](https://github.com/scarletkc/Perenna/blob/main/docs/concepts/architecture.md)
- [Development guide](https://github.com/scarletkc/Perenna/blob/main/docs/development/contributing.md)

## License

[MIT](https://github.com/scarletkc/Perenna/blob/main/LICENSE)
