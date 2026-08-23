# Architecture

Perenna is an MCP server around a transport-independent core. Local clients use
stdio; a self-hosted single-user instance can also use OAuth-protected
Streamable HTTP. Permanent state is an independent Git repository of Markdown
files, and semantic retrieval is derived through Vexor.

## System view

```text
Local MCP clients ── stdio ────────────┐
                                       ▼
ChatGPT ── HTTPS/OAuth ── proxy ── HTTP Perenna
                                       │
                              ┌────────┴────────┐
                              │                 │
                       Git + Markdown         Vexor
                       permanent data         index
                              │
                              └── optional best-effort push
                                           │
                                           ▼
                                    private Git remote
```

Each local client starts its own Perenna process. The processes coordinate
through file locks in the shared Perenna home. A remote deployment runs one
Perenna service for one configured OAuth subject and one Perenna home.

## Component responsibilities

### MCP adapters

Both adapters reuse the same server and tool handlers. They:

- advertise separate `memory_read`, `memory_write`, and `memory_delete` tools;
- validate action-specific arguments;
- dispatch to the core in a worker thread;
- convert expected domain failures into MCP error results;
- keep transport concerns outside the core.

The stdio adapter reserves stdout for protocol output. The HTTP adapter adds
Streamable HTTP, protected-resource metadata, bearer-token verification,
single-subject authorization, and per-tool scopes. Neither adapter owns
storage, indexing, source resolution, or Git behavior.

### Core

The core exposes list, search, get, create, patch, replace, and delete
operations to the adapter.

It coordinates locks, committed snapshots, storage, index synchronization, and
best-effort backup. It has no dependency on either transport.

### Markdown store

The store parses and writes the canonical memory format. It performs
normalization, path derivation, duplicate detection, per-memory revision
checks, exact patching, atomic replacement or deletion, and Git commit creation.

### Git repository

Git provides durability, history, auditability, manual recovery, and optional
remote backup. The runtime repository is separate from the Perenna source-code
repository.

### Vexor collection

Vexor embeds each memory title, authoritative summary, and bounded body chunks.
It applies scope filters before scoring. Perenna validates chunk identity,
revision, range, and path against the trusted committed Markdown snapshot, then
ranks distinct memories by their highest-scoring chunk before returning a
passage.

## Trust boundaries

- MCP arguments are untrusted and validated before they affect paths or data.
- `source` comes from host startup configuration, not from tool arguments.
- Memory paths are derived from validated scope and ULID values.
- Committed Markdown is trusted only after strict schema and integrity checks.
- Vexor metadata is treated as a cache hint and cross-checked against Git.
- Remote embedding providers receive text only when the user configures one.
- The remote adapter accepts only JWTs whose signature, issuer, audience,
  lifetime, subject, and tool scope validate against operator configuration.
- The configured public URL, rather than forwarded headers, owns the OAuth
  resource identifier and accepted public host.

The exact input and file contracts live in the
[MCP API reference](../reference/mcp-api.md) and
[memory file format](../reference/memory-format.md).

## Deployment boundary

The implemented product deliberately excludes:

- multi-user storage;
- a remote synchronization protocol;
- a web UI;
- an OAuth authorization server;
- bundled TLS termination, DNS, or reverse-proxy management;
- automatic memory extraction or context injection.

The container packages Perenna only. The operator owns HTTPS, the reverse
proxy, OAuth-provider configuration, persistent volumes, and backup
credentials. Remote mode remains single-user and keeps the same Git, Markdown,
locking, and retrieval contracts as stdio.
