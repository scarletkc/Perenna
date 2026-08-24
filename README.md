<div align="center">

<img src="https://raw.githubusercontent.com/scarletkc/Perenna/main/assets/logo.svg" alt="Perenna logo" width="160" />

# Perenna

[![Python](https://img.shields.io/badge/python-3.12%2B-blue)](https://www.python.org/downloads/)
[![PyPI](https://img.shields.io/pypi/v/perenna.svg)](https://pypi.org/project/perenna/)
[![CI](https://img.shields.io/github/actions/workflow/status/scarletkc/Perenna/validate.yml?branch=main)](https://github.com/scarletkc/Perenna/actions/workflows/validate.yml)
[![Codecov](https://img.shields.io/codecov/c/github/scarletkc/Perenna/main)](https://codecov.io/github/scarletkc/Perenna)
[![CodeRabbit Pull Request Reviews](https://img.shields.io/coderabbit/prs/github/scarletkc/Perenna?utm_source=oss&utm_medium=github&utm_campaign=scarletkc%2FPerenna&labelColor=171717&color=FF570A&link=https%3A%2F%2Fcoderabbit.ai&label=CodeRabbit+Reviews)](https://coderabbit.ai)
[![License](https://img.shields.io/github/license/scarletkc/Perenna.svg)](https://github.com/scarletkc/Perenna/blob/main/LICENSE)
[![Ask DeepWiki](https://deepwiki.com/badge.svg)](https://deepwiki.com/scarletkc/Perenna)
[![perenna MCP server](https://glama.ai/mcp/servers/scarletkc/perenna/badges/score.svg)](https://glama.ai/mcp/servers/scarletkc/perenna)

</div>

<!-- mcp-name: io.github.scarletkc/perenna -->

---

A lightweight, Git-backed permanent memory for AI agents. Claude Code, Codex,
ChatGPT, Cursor, and other MCP clients can share durable memories without
sharing a vendor account or conversation history.

- Separate MCP tools for reading, writing, and deleting memories
- Local stdio and single-user OAuth-protected Streamable HTTP transports
- Human-readable Markdown stored in an independent Git repository
- Local Vexor retrieval index that can always be rebuilt from Git
- Cross-process locking for multiple local agent processes

## Why Perenna?

Your memory should follow **you**, not the agent you happen to be using.

Claude Code, Codex, Cursor, and ChatGPT keep memory in separate silos. Switch
agents and your memory disappears. Switch machines and local memory stays
behind.

Perenna gives them one **shared, Git-backed memory**. Local agents and ChatGPT
can connect to the same self-hosted Perenna service, while every durable memory
stays ordinary Markdown you can inspect, edit, version, and back up yourself.

| | Perenna | [AgentMemory](https://github.com/rohitg00/agentmemory) | [Mem0](https://github.com/mem0ai/mem0) |
| --- | --- | --- | --- |
| Durable state | Markdown in your Git repository | Runtime-managed persistent state | Memory service with pluggable storage |
| MCP surface | 3 memory tools | Broad MCP/API surface | SDK/API-first memory layer |
| Writes | Explicit agent writes with revision guards | Hooks, skills, and automation | Automatic and explicit memory workflows |
| Retrieval | Rebuildable Vexor index | BM25, vector, graph, and hybrid search | Semantic memory retrieval |
| UI | None | Real-time viewer | Hosted dashboard available |
| Best fit | Small, inspectable, Git-native shared memory | Feature-rich agent memory platform | Managed or embedded application memory |

Perenna is deliberately narrow: **no account, no proprietary memory cloud, no
lock-in.** The retrieval index is disposable. The Markdown is not.

## Quickstart

### Install with your AI agent

Paste this into Claude Code, Codex, ChatGPT Desktop, Cursor, or another coding
agent with terminal and local MCP configuration access:

```text
Open the following URL, read the complete instructions, and follow them to
install and connect Perenna:
https://raw.githubusercontent.com/scarletkc/Perenna/main/docs/guides/agent-installation.md
```

### Install a published release

Perenna requires Python 3.12+, Git, and
[uv](https://docs.astral.sh/uv/).

```bash
uv tool install perenna
```

Install the optional memory behavior skill for the local client:

```bash
perenna skill install --agent codex
# or
perenna skill install --agent claude-code
```

Repeat `--agent` in one command when both clients should receive the skill.
The [configuration reference](https://github.com/scarletkc/Perenna/blob/main/docs/reference/configuration.md#bundled-agent-skill)
documents user and project scope, destinations, and replacement safeguards.

Codex and Claude Code can instead install the combined Skill and MCP connection
from Perenna's repository Marketplace. Follow the
[Plugin setup guide](https://github.com/scarletkc/Perenna/blob/main/docs/guides/plugin-setup.md)
and choose one setup path per client.

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
perenna mcp
```

Perenna creates its local data under `~/.perenna/` unless another home is
configured.

To import, publish, or fast-forward compatible history through a private Git
repository, run:

```bash
perenna sync setup <repository-url>
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
- [Plugin setup](https://github.com/scarletkc/Perenna/blob/main/docs/guides/plugin-setup.md)
- [Self-hosting for ChatGPT](https://github.com/scarletkc/Perenna/blob/main/docs/guides/self-hosting.md)
- [Using permanent memory](https://github.com/scarletkc/Perenna/blob/main/docs/guides/using-memory.md)
- [`perenna-memory` Agent Skill](https://github.com/scarletkc/Perenna/blob/main/skills/perenna-memory)
- [Configuration reference](https://github.com/scarletkc/Perenna/blob/main/docs/reference/configuration.md)
- [Architecture](https://github.com/scarletkc/Perenna/blob/main/docs/concepts/architecture.md)
- [Development guide](https://github.com/scarletkc/Perenna/blob/main/docs/development/contributing.md)

## License

[MIT](https://github.com/scarletkc/Perenna/blob/main/LICENSE)
