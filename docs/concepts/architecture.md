# Architecture

Perenna is an MCP server around a transport-independent core. Local clients use
stdio. A local relay can use loopback-only Streamable HTTP without OAuth, while
a self-hosted network service uses OAuth-protected Streamable HTTP. Permanent
state is an independent Git repository of Markdown files, and semantic
retrieval is derived through Vexor.

## System view

```text
Local MCP clients ── stdio ───────────────────────────────┐
ChatGPT ── Secure MCP Tunnel ── tunnel-client ── HTTP ────┤
ChatGPT ── HTTPS/OAuth ── proxy ── HTTP ──────────────────┤
                                                          ▼
                                                       Perenna
                                                          │
                                                 ┌────────┴────────┐
                                                 │                 │
                                          Git + Markdown         Vexor
                                          permanent data         index
                                                 │
                                                 └── optional sync
                                                              │
                                                              ▼
                                                       private Git remote
```

Each stdio client starts its own Perenna process. The processes coordinate
through file locks in the shared Perenna home. A local tunnel path runs one
loopback-only HTTP process without application-level authentication. A remote
deployment runs one Perenna service for one configured OAuth subject and one
Perenna home.

## Component responsibilities

### MCP adapters

Both adapters reuse the same server and tool handlers. They:

- advertise separate `memory_read`, `memory_write`, and `memory_delete` tools;
- validate action-specific arguments;
- dispatch to the core in a worker thread;
- convert expected domain failures into MCP error results;
- keep transport concerns outside the core.

The stdio adapter reserves stdout for protocol output. The HTTP adapter has two
startup modes. Local-only mode keeps the endpoint on loopback and omits OAuth;
remote mode adds protected-resource metadata, bearer-token verification,
single-subject authorization, and per-tool scopes. Neither adapter owns storage,
indexing, or Git behavior.

The current Streamable HTTP path is request-scoped: each modern request carries
its protocol version and routing metadata, and no MCP session identifier is
required. The same endpoint retains the SDK's earlier handshake-era support for
clients that have not negotiated the current protocol. This transport
compatibility does not add application state or change Perenna's single-owner
storage boundary.

### Core

The core exposes list, search, get, create, patch, replace, and delete
operations to the adapter.

It coordinates locks, committed snapshots, storage, index synchronization, and
optional Git synchronization. It has no dependency on either transport.

### Markdown store

The store parses and writes the canonical memory format. It performs
normalization, path derivation, duplicate detection, per-memory revision
checks, exact patching, atomic replacement or deletion, and Git commit creation.

### Git repository

Git provides local durability, history, auditability, manual recovery, and an
optional portable remote copy. Setup can import or fast-forward compatible
history. Diverged histories require explicit user reconciliation; the remote is
not a multi-writer coordination service. The runtime repository is separate
from the Perenna source-code repository.

The rationale for this boundary is recorded in
[ADR 0001](../decisions/0001-cross-device-access-and-git-sync.md).

### Vexor collection

Vexor embeds each memory title, authoritative summary, and bounded body chunks.
It applies scope filters before scoring. Perenna validates chunk identity,
revision, range, and path against the trusted committed Markdown snapshot, then
ranks distinct memories by their highest-scoring chunk before returning a
passage.

## Trust boundaries

- MCP arguments are untrusted and validated before they affect paths or data.
- Memory paths are derived from validated scope and ULID values.
- Committed Markdown is trusted only after strict schema and integrity checks.
- Vexor metadata is treated as a cache hint and cross-checked against Git.
- Remote embedding providers receive text only when the user configures one.
- Local-only HTTP rejects non-loopback listeners, validates its exact local
  `Host`, and requires any supplied `Origin` to match the derived local origin.
  It relies on host trust and the external tunnel for remote access.
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
- automatic reconciliation for concurrent remote writers;
- a web UI;
- an OAuth authorization server;
- bundled TLS termination, DNS, or reverse-proxy management;
- automatic memory extraction or context injection.

The container packages Perenna only. For public remote mode, the operator owns
HTTPS, the reverse proxy, OAuth-provider configuration, persistent volumes, and
Git credentials. Local tunnel mode needs none of that public ingress
infrastructure and must remain on loopback. Both HTTP modes keep the same Git,
Markdown, locking, and retrieval contracts as stdio.
