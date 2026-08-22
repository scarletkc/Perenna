# Product Overview

Perenna gives local AI agents a shared, durable memory that is independent of
their native memory features and conversation histories.

## The problem it solves

An agent often needs information that outlives one conversation:

- stable user preferences;
- long-lived project constraints;
- architectural decisions and their current outcome;
- workflows that another agent must follow later;
- historical context that should not be rediscovered from scratch.

Native agent memory is usually tied to one platform. Perenna provides a local
source that different MCP clients can read and update.

## Core capabilities

Perenna exposes one MCP tool named `memory` with two actions:

- `query` lists available topics or recalls relevant full memories;
- `write` creates or replaces a named memory in one scope.

Internally, Perenna provides:

- Markdown as the only permanent data format;
- one Git commit for every successful logical write;
- global and project-specific scopes;
- semantic retrieval through a rebuildable Vexor collection;
- safe coordination between multiple local Perenna processes;
- optional best-effort Git push for backup.

The exact tool contract is documented in the
[MCP API reference](reference/mcp-api.md).

## Interaction model

Perenna does not inject every memory into every prompt. The intended flow is:

```text
Start a session
      ↓
Read the lightweight memory index
      ↓
Recall a full memory only when history matters
      ↓
Write only information that should survive future sessions
```

This keeps irrelevant history out of the active context and leaves the agent
in control of when retrieval is useful.

## Data ownership

The Markdown Git repository is the permanent source of truth. The Vexor index
is derived cache data. If Perenna or Vexor disappears, the memories remain
ordinary versioned Markdown files that can be read without proprietary tools.

## Current product boundary

Perenna runs as a local stdio MCP server. It does not provide a network MCP
endpoint, multi-user accounts, server authentication, remote synchronization,
a web interface, or automatic extraction from conversations.

For the technical boundary, see [Architecture](concepts/architecture.md).
For practical memory choices, see
[Using permanent memory](guides/using-memory.md).
