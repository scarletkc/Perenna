# Releasing

This runbook describes how a committed Perenna version becomes a GitHub
Release and PyPI release, and how stable versions also enter the MCP Registry.
The executable contract is the
[`Publish` workflow](../../.github/workflows/publish.yml).

## One-time PyPI setup

Register a pending Trusted Publisher on PyPI with these values:

| Field | Value |
| --- | --- |
| Owner | `scarletkc` |
| Repository | `Perenna` |
| Workflow | `publish.yml` |
| Environment | `pypi` |

The publish job receives `contents: write` for the GitHub Release and
`id-token: write` for PyPI. PyPI validates that OIDC identity and returns a
short-lived upload token; the repository does not store a long-lived PyPI API
token.

## Release flow

```mermaid
flowchart TD
    A[Run scripts/bump_version.py in a branch] --> B[Open or update a pull request]
    B --> C[CI validates the pull request]
    C -- Failed --> X[Stop without releasing]
    C -- Passed and merged --> D[Push to main]
    D --> E[CI validates the main commit]
    E -- Failed --> X
    E -- Passed --> F[Publish workflow receives workflow_run.completed]
    F --> G[Check out the exact validated commit]
    G --> H{Version differs from its first parent?}
    H -- No --> Y[Finish without releasing]
    H -- Yes --> I[Build wheel and sdist]
    I --> J[Run twine check]
    J --> K[Install and verify the wheel in a clean environment]
    K --> L[Combine optional hand-written notes with Git changelog]
    L --> M[Create tag and GitHub Release with distribution assets]
    M --> N[Request GitHub OIDC identity]
    N --> O{PyPI accepts the Trusted Publisher identity?}
    O -- No --> X
    O -- Yes --> P[Receive a short-lived upload token]
    P --> Q[Publish wheel and sdist to PyPI]
    Q --> S{Stable version?}
    S -- No --> V[Finish without Registry publication]
    S -- Yes --> T[Wait for PyPI package metadata]
    T --> U[Publish to MCP Registry]

    R[One-time Trusted Publisher registration] -. establishes trust .-> O
```

The publish workflow runs only after the `Validate` workflow succeeds for a push to
`main`. Pull-request CI cannot release directly. GitHub Release and PyPI
publication run serially. Stable releases then enter the MCP Registry job after
PyPI succeeds. That job retries when Registry validation has not observed the
new PyPI version yet. Authentication, ownership, and manifest errors fail
immediately.

## Optional hand-written release notes

Add `docs/release-notes/<version>.md` in the same change as the version update
when a release needs curated highlights. The file must start with a
`## <title>` heading and contain a non-empty body. For example:

```markdown
## Highlights

- Describe the user-visible change.
```

The workflow inserts that section before its generated `## Changelog`, which
lists commits since the previous `v*` tag and links to the full comparison.
Omit the file when the generated changelog is sufficient.

## Publish a version

1. Run the version tool from the repository root:

   ```bash
   uv run python scripts/bump_version.py <version>
   ```

   It updates `src/perenna/__init__.py`, `server.json`, both plugin manifests,
   both repository Marketplaces, and the plugin's generated Skill mirror.
   Versions must use strict semantic versioning, such as `0.2.0` or
   `0.2.0-rc.1`.
2. Optionally add the matching hand-written release note described above.
   You can start it in the same command with
   `--note "<release-note-title>"`, then write its body.
3. Run the standard checks in [Testing](testing.md).
4. Commit the release change and merge it through the normal review path.
5. After `main` CI succeeds, verify that the publish workflow created the
   GitHub Release, completed the PyPI upload, and published stable versions to
   the MCP Registry.
6. Install `perenna` in a new process and confirm the reported version.

Do not edit generated plugin copies directly. After changing the canonical
Skill or plugin metadata, run `uv run python scripts/sync_plugin.py`. Installed
Marketplace copies use the plugin version as their update key, so bump the
Perenna version before distributing those changes to existing plugin users.
Changing other files without changing `__version__` does not create a release.
