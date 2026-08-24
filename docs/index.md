# Perenna Documentation

This directory is organized by purpose. Start at the top and move toward the
more exact layers only when you need them.

## Start here

| Document | Use it to |
| --- | --- |
| [Product overview](overview.md) | Understand what Perenna does and where it fits |
| [Getting started](getting-started.md) | Install Perenna and verify the first local connection |
| [AI-agent installation](guides/agent-installation.md) | Give an AI agent the complete autonomous installation workflow |

## Use Perenna

| Document | Use it to |
| --- | --- |
| [Client setup](guides/client-setup.md) | Connect Claude Code, Codex, ChatGPT Desktop, or Cursor |
| [Plugin setup](guides/plugin-setup.md) | Install the combined Skill and MCP plugin for Codex or Claude Code |
| [Secure MCP Tunnel](guides/secure-mcp-tunnel.md) | Connect ChatGPT to loopback Perenna without public ingress or OAuth |
| [Self-hosting](guides/self-hosting.md) | Run one OAuth-protected Perenna instance for ChatGPT web |
| [Glama MCP in ChatGPT web](guides/glama-chatgpt.md) | Connect a tokenized Glama Perenna endpoint to ChatGPT without OAuth |
| [Using permanent memory](guides/using-memory.md) | List, search, get, create, patch, replace, and delete memories |
| [`perenna-memory` Agent Skill](../skills/perenna-memory/SKILL.md) | Teach a compatible AI client when and how to curate permanent memory |
| [Maintenance and recovery](guides/maintenance.md) | Inspect Git history, handle local edits, and rebuild the index |

## Understand the design

| Document | Use it to |
| --- | --- |
| [Architecture](concepts/architecture.md) | Understand component boundaries and the local-first design |
| [Memory model](concepts/memory-model.md) | Understand identity, summaries, scopes, reads, and mutations |
| [Consistency model](concepts/consistency.md) | Understand commits, locks, snapshots, indexing, and failures |
| [ADR 0001: Cross-device access and Git sync](decisions/0001-cross-device-access-and-git-sync.md) | Understand why active cross-device access uses one HTTP service instead of Git multi-writer coordination |

## Look up an exact contract

| Document | Use it to |
| --- | --- |
| [Configuration reference](reference/configuration.md) | Look up CLI flags, environment variables, paths, and Vexor settings |
| [MCP API reference](reference/mcp-api.md) | Look up the three tool schemas and action rules |
| [Memory file format](reference/memory-format.md) | Look up paths, frontmatter, normalization, and validation rules |

## Develop Perenna

| Document | Use it to |
| --- | --- |
| [Contributing](development/contributing.md) | Set up the repository and follow implementation boundaries |
| [Testing](development/testing.md) | Run offline, concurrency, integration, and live-provider tests |
| [Releasing](development/releasing.md) | Understand and run the GitHub Release to PyPI workflow |

## Review proposals

Proposals are unapproved designs, not current behavior or roadmap commitments.

| Document | Use it to |
| --- | --- |
| [Hosted Git bootstrap](proposals/hosted-git-bootstrap.md) | Review a candidate design for configuring Git synchronization during container startup |

## Directory map

```text
docs/
├── index.md
├── overview.md
├── getting-started.md
├── guides/
│   ├── agent-installation.md
│   ├── client-setup.md
│   ├── glama-chatgpt.md
│   ├── plugin-setup.md
│   ├── secure-mcp-tunnel.md
│   ├── self-hosting.md
│   ├── using-memory.md
│   └── maintenance.md
├── concepts/
│   ├── architecture.md
│   ├── memory-model.md
│   └── consistency.md
├── decisions/
│   └── 0001-cross-device-access-and-git-sync.md
├── reference/
│   ├── configuration.md
│   ├── mcp-api.md
│   └── memory-format.md
├── proposals/
│   └── hosted-git-bootstrap.md
└── development/
    ├── contributing.md
    ├── releasing.md
    └── testing.md
```
