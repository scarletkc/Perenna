# Architecture

Perenna is a local stdio MCP server around a transport-independent core. Its
permanent state is an independent Git repository of Markdown files; semantic
retrieval is derived through Vexor.

## System view

```text
Claude Code / Codex / ChatGPT Desktop / Cursor
                        │
                    MCP stdio
                        │
                        ▼
                     Perenna
                   ┌────┴────┐
                   │         │
            Git + Markdown  Vexor
            permanent data  local index
                   │
                   └── optional best-effort push
                                │
                                ▼
                         private Git remote
                              backup
```

Each local client starts its own Perenna process. The processes coordinate
through file locks in the shared Perenna home.

## Component responsibilities

### stdio MCP adapter

The adapter:

- advertises exactly one `memory` tool;
- validates action-specific arguments;
- dispatches to the core in a worker thread;
- converts expected domain failures into MCP error results;
- keeps protocol output on stdout and diagnostics on stderr.

It does not own storage, indexing, source resolution, or Git behavior.

### Core

The core exposes three operations to the adapter:

- list the lightweight memory index;
- recall full memories;
- write a memory.

It coordinates locks, committed snapshots, storage, index synchronization, and
best-effort backup. It has no dependency on stdio and no generic transport
interface.

### Markdown store

The store parses and writes the canonical memory format. It performs
normalization, path derivation, duplicate detection, title-based upsert, atomic
replacement, and Git commit creation.

### Git repository

Git provides durability, history, auditability, manual recovery, and optional
remote backup. The runtime repository is separate from the Perenna source-code
repository.

### Vexor collection

Vexor embeds memory titles and bodies, applies scope filters before scoring,
and returns candidate memory IDs. Perenna resolves final results against the
trusted committed Markdown snapshot instead of trusting an arbitrary path from
index metadata.

## Trust boundaries

- MCP arguments are untrusted and validated before they affect paths or data.
- `source` comes from host startup configuration, not from tool arguments.
- Memory paths are derived from validated scope and ULID values.
- Committed Markdown is trusted only after strict schema and integrity checks.
- Vexor metadata is treated as a cache hint and cross-checked against Git.
- Remote embedding providers receive text only when the user configures one.

The exact input and file contracts live in the
[MCP API reference](../reference/mcp-api.md) and
[memory file format](../reference/memory-format.md).

## Local-first boundary

The implemented product deliberately excludes:

- HTTP or other network MCP transports;
- server-side authentication and user accounts;
- multi-user storage;
- a remote synchronization protocol;
- a web UI or deployment bundle;
- automatic memory extraction or context injection.

A future transport may wrap the same core after the local data and retrieval
contract is stable. That future work does not change the current local-first
boundary.
