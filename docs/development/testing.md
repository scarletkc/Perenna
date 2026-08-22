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
| Store and Git | create, update, atomic replacement, one-file commits, rollback |
| Index | incremental upsert, scope filtering, stale rebuild, marker failures |
| Core | committed reads, index failure isolation, push behavior, concurrent readers |
| MCP | exact schema, action validation, safe errors, real stdio subprocess |
| Multiprocess | first-run races, concurrent writers, clean Git history |
| End to end | one client writes, another recalls, a third updates the same memory |
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
```

Run the full suite before committing a cross-cutting change.

## Live provider smoke test

The `live_provider` marker is excluded from default pytest runs. It uses the
effective Vexor provider configuration and may send its temporary title, body,
and query to a remote provider.

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

## Concurrency tests

Concurrency behavior is part of the product contract:

- multiple recalls must overlap under shared locks;
- a rebuild and write must not overlap;
- concurrent processes must create valid commits without losing Markdown;
- first-run initialization must remain safe when more than one process starts.

Do not replace these tests with mocks that bypass the cross-process lock or
real Git repository.

## Stdio tests

The stdio suite starts Perenna with the official MCP Python client. It verifies
that:

- only the `memory` tool is listed;
- the advertised schema is exact;
- extra arguments are rejected even though the SDK does not validate tool
  input automatically;
- stdout contains no text outside the protocol;
- different sources share one home;
- expected failures do not leak memory content.

Keep at least one real subprocess path when changing CLI or MCP startup code.

## Continuous integration

`.github/workflows/ci.yml` runs the locked suite across the supported Windows,
Linux, and Python matrix. Each job performs dependency synchronization, Ruff,
pytest with coverage, and package build. The live-provider marker remains
excluded.

CI validates buildability but does not publish packages or deploy a service.
