# Configuration Reference

This page is the canonical reference for Perenna startup configuration, local
paths, remote OAuth, optional Git backup, and Vexor provider settings.

## CLI entry point

```text
perenna mcp [--source SOURCE] [--home PATH]
perenna serve [--source SOURCE] [--home PATH] [--host HOST] [--port PORT]
perenna backup setup REPOSITORY_URL [--home PATH] [--replace] [--deploy-key]
perenna backup status [--home PATH]
perenna skill install --agent AGENT [--agent AGENT] [--scope SCOPE] [--replace]
```

`mcp` serves local clients over stdio. `serve` exposes an OAuth-protected
Streamable HTTP endpoint at `/mcp`. The default HTTP listen address is
`127.0.0.1` and the default port is `8000`; a container normally overrides the
address to `0.0.0.0` while publishing the port only to a trusted reverse proxy.

## Bundled Agent Skill

`perenna skill install` copies the bundled `perenna-memory` skill without
downloading or running another installer. `--agent` is required, may be
repeated, and accepts `codex` or `claude-code`.

```text
perenna skill install --agent codex
perenna skill install --agent claude-code
perenna skill install --agent codex --agent claude-code
```

User scope is the default. Project scope resolves the current Git working-tree
root:

| Agent | User scope | Project scope |
| --- | --- | --- |
| `codex` | `~/.agents/skills/perenna-memory` | `<repo>/.agents/skills/perenna-memory` |
| `claude-code` | `~/.claude/skills/perenna-memory` | `<repo>/.claude/skills/perenna-memory` |

The command leaves every other installed skill unchanged. Repeating it against
an identical copy reports `already installed`. If the destination differs,
Perenna refuses to overwrite it. To replace that copy explicitly, run:

```text
perenna skill install --agent AGENT --replace
```

Replacement first moves the previous copy to the agent configuration
directory's `skill-backups` folder and prints the complete backup path. Skill
installation does not configure or start the MCP server; follow the
[client setup guide](../guides/client-setup.md) for that separate step.

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
├── credentials/ # optional repository-specific deploy keys
├── memory/      # independent Git repository; permanent source of truth
└── index/       # Vexor cache, indexed_commit, repository.lock, and push.lock
```

`index/` can be rebuilt from `memory/`. The memory and index directories must
not be reversed or merged, and the runtime memory repository must remain
separate from the Perenna source-code repository.

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

## Remote MCP and OAuth

`perenna serve` requires all of these environment variables:

| Variable | Contract |
| --- | --- |
| `PERENNA_PUBLIC_URL` | Canonical public HTTPS resource URL with the exact `/mcp` path |
| `PERENNA_OAUTH_ISSUER` | Exact HTTPS authorization-server issuer |
| `PERENNA_OAUTH_JWKS_URL` | HTTPS JWKS document for RS256 access-token verification |
| `PERENNA_OAUTH_ALLOWED_SUBJECT` | Exact OAuth `sub` allowed to use this instance |

URLs cannot contain credentials, a query, or a fragment. The public URL is
also the required JWT audience and the source of the accepted HTTP `Host`.
Every URL must already use its canonical form, including a lowercase host and
no explicit default port. Perenna preserves the issuer path exactly, including
whether it has a trailing slash, so it can match the provider's `issuer` claim.

The protected-resource metadata URL is derived from the public resource path:

```text
https://memory.example.com/.well-known/oauth-protected-resource/mcp
```

It advertises these fixed scopes:

| Tool | Required scope |
| --- | --- |
| `memory_read` | `memory:read` |
| `memory_write` | `memory:write` |
| `memory_delete` | `memory:delete` |

Remote access always requires OAuth. Perenna accepts signed RS256 JWT access
tokens, fetches signing keys from the configured JWKS URL, and verifies the
signature, issuer, audience, time claims, owner subject, and tool scope. It is
only an OAuth resource server: the configured provider owns login, consent,
client registration, token issuance, refresh, and revocation.

These variables are not required by `perenna mcp`; local stdio behavior and
configuration remain unchanged. Follow the
[self-hosting guide](../guides/self-hosting.md) for Docker, Nginx, OAuth-provider,
and ChatGPT setup.

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

Choose an empty private Git repository or a remote whose current branch has
compatible history, then run:

```text
perenna backup setup <repository-url>
```

The command initializes `<home>/memory` when necessary and uses the effective
`PERENNA_GIT_REMOTE`, which is `origin` by default. It checks repository access,
rejects parallel or non-fast-forward history, and verifies push access with the
same non-interactive Git environment used during memory writes. When local
commits exist, setup performs the initial push and verifies that the remote
branch matches the local commit. Without a local commit, it configures the
remote and reports that write access remains pending until the first commit.

Setup is idempotent when the effective remote already has the requested URL. If
it points somewhere else, Perenna leaves it unchanged unless replacement is
explicit:

```text
perenna backup setup <repository-url> --replace
```

To use a different remote name, set `PERENNA_GIT_REMOTE` to that name in both the
Perenna host and the environment running setup, then run the same command:

```text
perenna backup setup <repository-url>
```

An explicitly empty `PERENNA_GIT_REMOTE` disables automatic backup, so setup
refuses to configure a remote while that override is effective.

#### Repository-specific deploy key

For an unattended container, use an SSH repository address and let Perenna
create a repository-specific Ed25519 deploy key:

```text
perenna backup setup git@github.com:OWNER/REPOSITORY.git --deploy-key
```

The first run stores the private key under `<home>/credentials/git`, configures
that key only for the memory repository, and prints the public key. It never
prints the private key. For GitHub, open the displayed repository settings URL,
add the public key as a deploy key, and select **Allow write access**. Run the
same setup command again to verify repository access and perform the initial
push. The key directory and memory repository must use the same persistent
Perenna home across restarts.

Deploy-key SSH host keys use a dedicated `known_hosts` file. The first
connection accepts and records a previously unseen host key; later changes are
rejected by OpenSSH. Review the recorded host key out of band when the remote
host requires stronger first-connection verification.

The deploy key is scoped by the Git host to one repository. Revoke it in the
repository settings before discarding or exposing the Perenna home volume.
Changing to a different repository produces a different key instead of reusing
one deploy key across repositories.

#### Prepare non-interactive credentials

Perenna never opens a Git credential prompt. Its Git subprocesses set
`GIT_TERMINAL_PROMPT=0`, `GCM_INTERACTIVE=Never`, and
`SSH_ASKPASS_REQUIRE=never`, and they do not use inherited askpass helpers.
Authentication must therefore succeed non-interactively in the environment
inherited from the MCP client.

Git commit authorship and remote authentication are separate. Perenna keeps the
repository-local author `Perenna <perenna@localhost>` and does not change the
user's global Git identity. HTTPS pushes use credentials available through Git
Credential Manager; SSH pushes use a key available through the inherited SSH
agent. The authenticated account, not the commit author name, determines remote
repository access.

Use one of these credential paths:

- **SSH:** use an SSH remote and make the key available without a new prompt,
  typically by loading it into an SSH agent that the MCP client can access, or
  use `--deploy-key` for an unattended single-repository installation.
- **HTTPS:** save a token or credential in the operating system's Git
  credential manager before Perenna starts.
- **Token in URL:** `perenna backup setup` rejects embedded HTTPS credentials so
  they cannot be left in the memory repository's `.git/config`.

A credential that works only after an interactive shell prompt is not ready
for Perenna. Desktop clients may also inherit a different SSH-agent or
credential environment from your terminal.

#### Check backup status

Run the status check in the same environment that starts Perenna:

```text
perenna backup status
```

Status reports the resolved memory path, effective remote name and complete URL,
current branch, repository access, write-access check, and whether the local
commit is synchronized or still pending push. It does not display credentials
or claim write access when no local commit is available for a dry-run push.

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
uv tool install "perenna[local]"
```

For a source checkout, use `uv tool install ".[local]"` instead.

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

## Logging

During `perenna mcp`, stdout is reserved for MCP protocol messages. Perenna
sends diagnostics and redacted operational logs to stderr.

`perenna serve` also sends application diagnostics to stderr. Its default
Uvicorn access log is disabled so bearer headers and request details do not
enter routine logs.

Logs may include action, source, project, operation, result count, short commit
ID, and exception type. They must not include a memory summary, body, search
query, provider key, or complete MCP request payload.
