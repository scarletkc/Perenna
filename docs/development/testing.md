# Testing

Perenna's default test suite is offline and deterministic. It does not require
a real embedding API key or external service.

## Standard checks

Install the locked development environment first:

```bash
uv sync --locked --extra dev
```

Run linting:

```bash
uv run ruff check .
```

Check that both plugin manifests, Marketplaces, and the bundled Skill mirror
match their canonical sources:

```bash
uv run python scripts/sync_plugin.py --check
```

Run the default test suite:

```bash
uv run pytest
```

Run the same coverage gate used by CI:

```bash
uv run coverage erase
uv run coverage run -m pytest
uv run coverage report
```

Build both distribution formats:

```bash
uv build
```

The exact Ruff rules, pytest marker defaults, branch coverage, and minimum
coverage threshold are owned by `pyproject.toml`.

## Test layers

| Layer | Primary coverage |
| --- | --- |
| Configuration | CLI and environment precedence, missing source, remote selection |
| Markdown and models | normalization, ULID, frontmatter, paths, duplicate integrity |
| Store and Git | create, patch, replace, delete, revisions, one-file commits, rollback |
| Index | chunk rebuild, scope filtering, limits, budgets, stale metadata, marker failures |
| Core | committed reads, index failure isolation, push behavior, concurrent readers |
| MCP | exact schema, action validation, safe errors, real stdio and HTTP sessions |
| Multiprocess | first-run races, concurrent writers, clean Git history |
| End to end | agents create, search, get, patch, and delete one shared memory |
| Safety | environment isolation, links, device names, Git states, control characters |

The real Vexor integration tests use a controlled local OpenAI-compatible
embedding endpoint. They exercise the published Collections API without
calling the public internet.

## Focused tests

During development, run the smallest relevant file first:

```bash
uv run pytest tests/test_store.py -q
uv run pytest tests/test_index.py -q
uv run pytest tests/test_mcp.py -q
uv run pytest tests/test_http.py tests/test_oauth.py -q
```

Run the full suite before committing a cross-cutting change.

## Live provider smoke test

The `live_provider` marker is excluded from default pytest runs. It uses the
  effective Vexor provider configuration and may send its temporary title,
  summary, body, and query to a remote provider.

PowerShell:

```powershell
$env:PERENNA_RUN_LIVE_PROVIDER = "1"
uv run pytest -o addopts="" -m live_provider tests/test_live_provider.py
Remove-Item Env:PERENNA_RUN_LIVE_PROVIDER
```

POSIX shell:

```bash
PERENNA_RUN_LIVE_PROVIDER=1 \
  uv run pytest -o addopts="" -m live_provider tests/test_live_provider.py
```

Run this test only with an intentional provider configuration and disposable
temporary data.

## Live retrieval evaluation

The retrieval evaluation is also excluded from default pytest runs. It indexes
a fixed set of synthetic memories, compares `off` and `hybrid` ranking, and
prints recall, reciprocal rank, top-one misses, and score distributions for
unrelated queries as one JSON record.

PowerShell:

```powershell
$env:PERENNA_RUN_LIVE_PROVIDER = "1"
uv run pytest -o addopts="" -m live_provider tests/test_retrieval_eval.py -s -q
Remove-Item Env:PERENNA_RUN_LIVE_PROVIDER
```

POSIX shell:

```bash
PERENNA_RUN_LIVE_PROVIDER=1 \
  uv run pytest -o addopts="" -m live_provider tests/test_retrieval_eval.py -s -q
```

Scores are observations within each retrieval mode. They are not a calibrated
relevance threshold, and values from different modes should not be compared as
though they shared one scale. The evaluation uses a pytest temporary directory
and drops its temporary collection when it finishes.

## Concurrency tests

Concurrency behavior is part of the product contract:

- multiple searches must overlap under shared locks;
- a rebuild and mutation must not overlap;
- concurrent processes must create valid commits without losing Markdown;
- first-run initialization must remain safe when more than one process starts.

Do not replace these tests with mocks that bypass the cross-process lock or
real Git repository.

## Stdio tests

The stdio suite starts Perenna with the official MCP Python client. It verifies
that:

- exactly the three memory tools are listed;
- every advertised input and output schema is exact;
- extra arguments are rejected even though the SDK does not validate tool
  input automatically;
- stdout contains no text outside the protocol;
- different sources share one home;
- expected failures do not leak memory content.

Keep at least one real subprocess path when changing CLI or MCP startup code.

## Remote HTTP tests

The remote suite runs the real ASGI application in process with the official
MCP client. It verifies OAuth discovery and challenges, JWT validation,
single-subject access, per-tool scopes, public-host checks, and serialized tool
metadata without requiring an external identity provider.

Docker image execution is a separate environment check. A passing Python test
suite does not establish that a particular container runtime, reverse proxy,
domain, certificate, or OAuth tenant is configured correctly.

## Continuous integration

`.github/workflows/validate.yml` owns the validation runner and Python version. Each
run performs dependency synchronization, Ruff, plugin synchronization checks,
pytest with coverage, and package build. The live-provider marker remains
excluded.

CI validates buildability but does not publish packages directly. A successful
`main` push can trigger the separate workflow documented in
[Releasing](releasing.md).
