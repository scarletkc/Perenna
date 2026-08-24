# Product Overview

Perenna gives AI agents a shared, durable memory that is independent of their
native memory features and conversation histories.

## The problem it solves

An agent often needs information that outlives one conversation:

- stable user preferences;
- long-lived project constraints;
- architectural decisions and their current outcome;
- workflows that another agent must follow later;
- historical context that should not be rediscovered from scratch.

Native agent memory is usually tied to one platform. Perenna provides a
self-owned source that different MCP clients can read and update.

## Core capabilities

Perenna exposes three MCP tools:

- `memory_read` lists topics, searches ranked passages, or gets one complete
  memory;
- `memory_write` creates, exactly patches, or deliberately replaces a memory;
- `memory_delete` removes one exact current memory while Git retains history.

Internally, Perenna provides:

- Markdown as the only permanent data format;
- one Git commit for every successful changed mutation;
- global and project-specific scopes;
- semantic retrieval through a rebuildable Vexor collection;
- safe coordination between multiple local Perenna processes;
- local stdio, loopback-only HTTP, and single-user authenticated HTTP access;
- optional Git import, fast-forward, and push with explicit conflict reporting.

The exact tool contract is documented in the
[MCP API reference](reference/mcp-api.md).

## Interaction model

Perenna does not inject every memory into every prompt. The intended flow is:

```text
Start a session
      ↓
Read the lightweight memory index
      ↓
Search bounded candidate passages when history matters
      ↓
Get a complete memory only when needed
      ↓
Create or revise only durable information
```

This keeps irrelevant history out of the active context and leaves the agent
in control of when retrieval is useful.

## Data ownership

The Markdown Git repository is the permanent source of truth. The Vexor index
is derived cache data. If Perenna or Vexor disappears, the memories remain
ordinary versioned Markdown files that can be read without proprietary tools.

## Current product boundary

Perenna runs locally over stdio, over loopback-only Streamable HTTP for a local
tunnel client, or as one OAuth-protected Streamable HTTP service for one owner.
It does not provide multi-user accounts, an OAuth authorization server,
automatic reconciliation for concurrent remote writers, a web interface,
bundled TLS or reverse-proxy management, or automatic extraction from
conversations.

For the technical boundary, see [Architecture](concepts/architecture.md).
For practical memory choices, see
[Using permanent memory](guides/using-memory.md).
