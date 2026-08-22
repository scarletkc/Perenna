# Configuration Reference

This page is the canonical reference for Perenna startup configuration, local
paths, optional Git backup, and Vexor provider settings.

## CLI entry point

```text
perenna mcp [--source SOURCE] [--home PATH]
```

Perenna currently exposes only the local stdio MCP command.

## Perenna home

The home is resolved in this order:

1. `--home PATH`
2. `PERENNA_HOME`
3. `~/.perenna`

An explicitly supplied empty flag or environment value is an error; Perenna
does not silently fall back to the next source.

The resolved home contains:

```text
<home>/
├── memory/   # independent Git repository; permanent source of truth
└── index/    # Vexor cache, indexed_commit, repository.lock, and push.lock
```

`index/` can be rebuilt from `memory/`. The two directories must not be
reversed or merged, and the runtime memory repository must remain separate
from the Perenna source-code repository.

## Source identity

The source is resolved in this order:

1. `--source SOURCE`
2. `PERENNA_SOURCE`

There is no default source. Perenna refuses to start when neither value is
present.

Source normalization and validation:

- Unicode NFKC normalization;
- leading and trailing whitespace removed;
- 1 to 64 characters;
- first character must be an ASCII letter or digit;
- remaining characters may be ASCII letters, digits, `.`, `_`, or `-`;
- case is preserved.

Stable examples include `claude-code`, `codex`, and `cursor`.

The host injects source into changed mutations. `source` is not an MCP tool
field.

## Git remote backup

`PERENNA_GIT_REMOTE` controls automatic best-effort push:

| Environment state | Behavior |
| --- | --- |
| Unset | Look for a remote named `origin` |
| Non-empty | Use the configured remote name |
| Empty string | Disable automatic push |

Perenna skips a missing remote. If the current branch has no upstream, the
first successful push may establish one. Push uses a fixed timeout and a
separate lock.

Remote backup never participates in reads, mutation validation, local commit
creation, or mutation success. Perenna performs no automatic fetch, pull,
merge, or force-push.

### Set up a backup remote

Connect Perenna once so that `<home>/memory` exists, then choose an empty
private Git repository or a remote with compatible history. Perenna will not
integrate an unrelated initial commit created by the remote host.

Enter the memory repository and inspect existing remotes before adding one:

```bash
cd <memory-repository>
git remote -v
```

Add the default `origin` remote:

```bash
git remote add origin <remote-url>
```

If `origin` already exists and should point somewhere else, update it
explicitly:

```bash
git remote set-url origin <remote-url>
```

For another remote name, add that name and set `PERENNA_GIT_REMOTE` to the same
value in the MCP host configuration:

```bash
git remote add backup <remote-url>
```

#### Prepare non-interactive credentials

Perenna never opens a Git credential prompt. Its Git subprocesses set
`GIT_TERMINAL_PROMPT=0`, `GCM_INTERACTIVE=Never`, and
`SSH_ASKPASS_REQUIRE=never`, and they do not use inherited askpass helpers.
Authentication must therefore succeed non-interactively in the environment
inherited from the MCP client.

Use one of these credential paths:

- **SSH:** use an SSH remote and make the key available without a new prompt,
  typically by loading it into an SSH agent that the MCP client can access.
- **HTTPS:** save a token or credential in the operating system's Git
  credential manager before Perenna starts.
- **Token in URL:** Git can use one, but it leaves the secret in the memory
  repository's `.git/config`; prefer a credential manager instead.

A credential that works only after an interactive shell prompt is not ready
for Perenna. Desktop clients may also inherit a different SSH-agent or
credential environment from your terminal.

#### Verify the connection

Run the checks as the same operating-system user that runs the MCP client:

```bash
git ls-remote origin
```

After at least one memory commit exists, verify write authentication without
changing the remote:

```bash
git push --dry-run origin main
```

You can perform the first backup manually and establish the upstream:

```bash
git push --set-upstream origin main
```

Otherwise, a later successful Perenna push establishes the upstream
automatically. Replace `origin` and `main` when you configured another remote
or use an existing repository on another branch.

## Vexor collection contract

Perenna uses one Vexor collection:

```text
collection name: perenna-memories
record id:       memory ULID + chunk ordinal
record text:     normalized title + authoritative summary + body chunk
metadata:        memory ID + scope + path + revision + chunk range
cache directory: <home>/index
```

For project search, Perenna applies this metadata filter before scoring:

```text
scope in [global, project:<slug>]
```

The collection is derived data. Perenna cross-checks returned IDs, revisions,
paths, scopes, ordinals, and ranges against committed Markdown before returning
a passage.

## Vexor provider configuration

Perenna forces only the Vexor cache directory. It leaves the Vexor user
configuration directory unchanged, so provider settings follow Vexor's own
configuration system:

- user configuration: `~/.vexor/config.json`;
- non-secret process overrides: `VEXOR_CONFIG_JSON`;
- general provider secret: `VEXOR_API_KEY`;
- provider-specific secrets such as `OPENAI_API_KEY`,
  `GOOGLE_GENAI_API_KEY`, and `VOYAGE_API_KEY`.

Keep API keys out of `VEXOR_CONFIG_JSON`, tracked MCP files, and the memory Git
repository. Forward a secret from the host environment instead of copying it
into project configuration.

Example non-secret override:

```text
VEXOR_CONFIG_JSON={"provider":"openai","model":"text-embedding-3-small"}
```

Refer to the
[Vexor configuration documentation](https://github.com/scarletkc/vexor/blob/main/docs/configuration.md)
for its complete provider field and precedence contract.

## Remote provider privacy boundary

When Vexor uses a remote embedding provider, that provider receives:

- each memory title, summary, and body chunk during mutation or rebuild;
- each search query when generating its query vector.

The Markdown repository remains local, but local storage does not mean the
embedded content stays on the machine. Review the selected provider and
endpoint before writing sensitive information.

Perenna logs do not include summaries, bodies, search query text, or API keys.
That logging rule does not prevent configured embedding traffic.

## Local provider installation

Install Vexor's local embedding dependencies with the Perenna extra:

```bash
uv tool install ".[local]"
```

Then select a local provider through Vexor configuration, for example:

```text
VEXOR_CONFIG_JSON={"provider":"local","model":"intfloat/multilingual-e5-small"}
```

Local embedding avoids sending memory text and queries to an embedding API.
Initial package and model downloads may still require network access.

## Change provider, model, or vector dimension

Vexor pins the provider, model, and dimension when the collection is created.
To change that contract:

1. stop every Perenna process using the home;
2. update Vexor configuration;
3. move or delete `<home>/index`;
4. restart Perenna;
5. run a search query to rebuild from committed Markdown.

Do not edit `collections.db` or `indexed_commit` to imitate compatibility.

## Logging and stdio

During `perenna mcp`, stdout is reserved for MCP protocol messages. Perenna
sends diagnostics and redacted operational logs to stderr.

Logs may include action, source, project, operation, result count, short commit
ID, and exception type. They must not include a memory summary, body, search
query, provider key, or complete MCP request payload.
