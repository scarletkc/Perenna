# Perenna Agent Guidelines

These instructions apply to every change in this repository. Perenna is a
Python 3.12+ MCP server that keeps permanent agent memory as Markdown in an
independent Git repository and uses Vexor only as a rebuildable retrieval
index.

## Start with the project contract

Read [Contributing](docs/development/contributing.md) before changing code. Its
sections on architectural boundaries, Git operations, safety, documentation
ownership, and the change workflow are requirements, not background material.

Use the document that owns the part being changed:

- [Architecture](docs/concepts/architecture.md) and
  [Consistency model](docs/concepts/consistency.md) for storage, snapshots,
  locking, indexing, and failure behavior;
- [MCP API](docs/reference/mcp-api.md) for tool names, schemas, actions, and
  structured results;
- [Memory file format](docs/reference/memory-format.md) for paths, frontmatter,
  normalization, identity, and revisions;
- [Configuration](docs/reference/configuration.md) for CLI flags, environment
  variables, local paths, synchronization, and provider settings;
- [Testing](docs/development/testing.md) for the current quality gates and test
  tiers;
- [Releasing](docs/development/releasing.md) for versioning, packaging, and the
  automated publication path.

Do not copy complete contracts between documents. Update the canonical owner
and link to it from other surfaces that need context.

## Environment

Use `uv` and the checked-in `uv.lock`; do not use the system interpreter or
install project dependencies globally. Set up the development environment with
the command under **Set up the repository** in
[Contributing](docs/development/contributing.md), and run all Python tools
through `uv run`.

Use temporary directories or an explicitly disposable `PERENNA_HOME` for tests
and manual experiments. Never run destructive development checks against the
user's normal `~/.perenna` data.

## Implementation boundaries

- Treat committed Markdown in the configured memory repository as permanent
  truth. An index, cache, or remote synchronization failure must not disguise
  or undo an existing local commit.
- Keep the core independent of MCP transport. Preserve both local stdio and
  single-owner OAuth-protected Streamable HTTP unless an approved product
  change says otherwise.
- Keep the public surface to `memory_read`, `memory_write`, and
  `memory_delete`. Do not expose Git or index maintenance as agent tools.
- Preserve exact schemas and strict validation. Reject unknown fields and
  invalid action combinations instead of guessing or silently degrading.
- Keep mutations revision-guarded, path-scoped, and atomic. Runtime Git code
  must never merge, rebase, or force-push automatically.
- Do not add speculative compatibility layers, generic transport interfaces,
  multi-user storage, an authorization server, or bundled TLS/reverse-proxy
  management without explicit approval.

Match the surrounding Python style and reuse existing helpers before adding a
new abstraction. Fix root causes, let failures remain visible, and do not ship
temporary or demo-only production paths.

## Generated and versioned artifacts

The top-level `skills/perenna-memory/` tree and `plugins/README.md` are
canonical plugin content. Host-specific files under `plugins/codex/perenna/`
and `plugins/claude/perenna/`, along with Marketplace metadata, are generated
by `scripts/sync_plugin.py`. Change the canonical source, regenerate the
mirrors, and include all required generated changes; do not edit a mirror by
hand.

`src/perenna/__init__.py` owns the package version. Use
`scripts/bump_version.py` for a release version so package, plugin, Marketplace,
and registry metadata stay synchronized. Validation does not authorize a
publish; `.github/workflows/publish.yml` owns release execution after validated
version changes on `main`.

## Testing

Pair behavior changes with happy-path and failure-path coverage. Run the
smallest relevant test first, then the standard checks under **Standard
checks** in [Testing](docs/development/testing.md) before handing off a
cross-cutting change or preparing a commit.

Preserve the real boundary exercised by a test:

- do not replace cross-process locking and Git behavior with mocks;
- retain a real MCP subprocess path for stdio changes;
- exercise the ASGI application and OAuth verification for HTTP changes;
- keep the default suite offline and deterministic.

Tests marked `live_provider` may send synthetic memory text and queries to the
effective embedding provider. Run them only when the task requires that
integration evidence and the provider configuration is intentional. A local
test does not prove a Docker, proxy, OAuth tenant, package registry, or deployed
service is configured correctly.

## User-visible text and documentation

Keep public documentation and user-visible copy in clear English unless an
existing surface requires another language. Errors must say what failed,
where it failed, and what the user can do next. During stdio MCP operation,
stdout is protocol-only; diagnostics go to stderr and must not include memory
bodies, search queries, credentials, tokens, or private endpoints.

Keep the README concise. Stable rules belong in the purpose-specific pages
listed in [Documentation ownership](docs/development/contributing.md#documentation-ownership),
while release-specific outcomes belong in release notes or the release record.
Point to the source symbol or workflow that owns changing values instead of
copying versions, hashes, deployment state, or generated field lists into
long-lived prose.

When behavior or copy changes, sweep the CLI help, error paths, README and
canonical docs, bundled Skill, plugin metadata, and generated plugin copies for
stale wording. Preserve machine-readable output exactly and assert important
absences as well as expected values.

## Security and repository hygiene

Treat memory files, Git history, configuration, OAuth claims, provider
responses, and filesystem paths as untrusted input. Normalize and validate
before use, derive scope from trusted paths, and keep secrets in environment or
ignored configuration rather than tracked files.

Inspect `git status` before editing. Preserve unrelated tracked, staged, and
untracked work; stage only the paths in scope and review the staged path list
before committing. Use Conventional Commits with an imperative subject under
about 72 characters and branches named `type/short-slug`. Land changes through
a pull request and leave merging and release publication to the repository
owner unless explicitly instructed otherwise.
