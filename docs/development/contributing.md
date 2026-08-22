# Contributing

This guide defines the local development workflow and implementation
boundaries for Perenna.

## Set up the repository

Requirements:

- Python 3.12 or newer;
- Git;
- uv.

Install the locked development environment:

```bash
uv sync --locked --extra dev
```

Run the CLI from the environment:

```bash
uv run perenna --help
```

Do not use your normal `~/.perenna` home for destructive development tests.
Use pytest temporary directories or an explicit disposable home.

## Package layout

```text
src/perenna/
├── cli.py          # command parsing and stderr logging setup
├── mcp_server.py   # exact stdio MCP adapter
├── core.py         # read, mutation, lock, and backup orchestration
├── config.py       # startup precedence and runtime paths
├── models.py       # memory types and normalization
├── markdown.py     # strict Markdown serialization and parsing
├── store.py        # revision-guarded mutation transactions
├── git.py          # isolated Git operations and optional push
├── locking.py      # cross-process reader/writer and push locks
├── index.py        # Vexor collection and commit marker
├── filesystem.py   # atomic replacement
└── errors.py       # expected domain failures
```

Tests mirror those responsibilities under `tests/`.

## Architectural boundaries

Changes must preserve these rules:

1. Committed Markdown in the memory Git repository is the only permanent
   source of truth.
2. Vexor is one concrete, rebuildable retrieval cache, not a second store.
3. The core remains independent of stdio, but the project does not add a
   speculative generic transport interface.
4. The implemented server remains local stdio. Do not add HTTP, authentication,
   deployment, or multi-user placeholders without an approved product change.
5. MCP exposes `memory_read`, `memory_write`, and `memory_delete`. Internal Git
   and index operations do not become agent-facing tools.
6. A successful changed mutation always means that one target memory path is
   committed to local Git.
7. An index or backup failure never rolls back an existing memory commit.

Read [Architecture](../concepts/architecture.md) and
[Consistency model](../concepts/consistency.md) before changing storage,
locking, or retrieval.

## Input and path safety

- Normalize and validate all external values before deriving a path.
- Derive scope from trusted paths, never from frontmatter metadata.
- Reject links, non-regular Git blobs, path traversal, and non-portable project
  names.
- Pin every snapshot read to one captured commit.
- Keep memory summaries, bodies, and search query text out of logs and
  unexpected errors.

The public validation contract belongs in
[Memory file format](../reference/memory-format.md).

## Git operation rules

Runtime Git calls must:

- use argument arrays rather than shell interpolation;
- detach stdin from the MCP protocol stream;
- remove repository-control and identity overrides from the inherited
  environment;
- refuse dirty, detached, or unfinished repository states before writing;
- isolate hooks during the Perenna commit;
- stage and commit only the intended memory path;
- preserve safe rollback when commit creation fails;
- keep push best effort and separate from the repository mutation lock.

Do not introduce automatic fetch, pull, force-push, or conflict resolution.

## MCP and user-visible output

- Keep all three tool schemas and structured output schemas exact; reject extra
  or action-incompatible arguments server-side.
- Run synchronous core operations in worker threads so the MCP event loop does
  not serialize all reads.
- Reserve stdout for protocol messages during stdio operation.
- Send diagnostics to stderr without memory bodies, queries, or secrets.
- Make expected errors actionable: state what failed, where, and what the user
  should do next.

## Documentation ownership

Update the document that owns the changed fact:

| Change | Canonical document |
| --- | --- |
| Product behavior or boundary | `docs/overview.md` or `docs/concepts/architecture.md` |
| User workflow | `docs/guides/` |
| CLI, environment, provider configuration | `docs/reference/configuration.md` |
| MCP fields or action semantics | `docs/reference/mcp-api.md` |
| Markdown schema or normalization | `docs/reference/memory-format.md` |
| Consistency, locks, transaction, failures | `docs/concepts/consistency.md` |
| Test workflow | `docs/development/testing.md` |
| Release packaging and PyPI workflow | `docs/development/releasing.md` |

Other pages should link to that owner instead of copying the complete rule.
Keep the root README short.

## Change workflow

1. Inspect the current worktree and preserve unrelated changes.
2. Implement the smallest complete change within the approved boundary.
3. Add happy-path and failure-path coverage after behavior is settled.
4. Update whichever canonical documentation the behavior changes.
5. Run the relevant focused tests.
6. Run the full quality checks before handing off or committing.
7. Inspect the final diff and staged path list.

Full commands and test tiers are documented in [Testing](testing.md).
