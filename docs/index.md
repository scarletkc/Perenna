# Perenna Documentation

This directory is organized by purpose. Start at the top and move toward the
more exact layers only when you need them.

## Start here

| Document | Use it to |
| --- | --- |
| [Product overview](overview.md) | Understand what Perenna does and where it fits |
| [Getting started](getting-started.md) | Install Perenna and verify the first local connection |

## Use Perenna

| Document | Use it to |
| --- | --- |
| [Client setup](guides/client-setup.md) | Connect Claude Code, Codex, ChatGPT Desktop, or Cursor |
| [Using permanent memory](guides/using-memory.md) | List, search, get, create, patch, replace, and delete memories |
| [Maintenance and recovery](guides/maintenance.md) | Inspect Git history, handle local edits, and rebuild the index |

## Understand the design

| Document | Use it to |
| --- | --- |
| [Architecture](concepts/architecture.md) | Understand component boundaries and the local-first design |
| [Memory model](concepts/memory-model.md) | Understand identity, summaries, scopes, reads, and mutations |
| [Consistency model](concepts/consistency.md) | Understand commits, locks, snapshots, indexing, and failures |

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

## Directory map

```text
docs/
├── index.md
├── overview.md
├── getting-started.md
├── guides/
│   ├── client-setup.md
│   ├── using-memory.md
│   └── maintenance.md
├── concepts/
│   ├── architecture.md
│   ├── memory-model.md
│   └── consistency.md
├── reference/
│   ├── configuration.md
│   ├── mcp-api.md
│   └── memory-format.md
└── development/
    ├── contributing.md
    ├── releasing.md
    └── testing.md
```
