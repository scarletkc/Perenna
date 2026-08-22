# Getting Started

This guide installs Perenna from source, checks the command, and prepares the
first client connection.

## Requirements

- Python 3.12 or newer
- Git available on `PATH`
- [uv](https://docs.astral.sh/uv/)
- an MCP client that can start a local stdio server

## Install from source

```bash
git clone https://github.com/scarletkc/Perenna.git
cd Perenna
uv tool install .
```

Verify that the installed command is available:

```bash
perenna --help
```

### Install local embedding support

The base installation follows your existing Vexor provider configuration. To
install Vexor's local embedding dependencies as well, install the `local`
extra:

```bash
uv tool install ".[local]"
```

The initial dependency and model downloads may still require network access.
Provider configuration and privacy boundaries are documented in the
[configuration reference](reference/configuration.md#vexor-provider-configuration).

## Connect a client

Choose the setup for your MCP client:

- [Claude Code](guides/client-setup.md#claude-code)
- [Codex CLI and IDE extension](guides/client-setup.md#codex-cli-and-ide-extension)
- [ChatGPT Desktop](guides/client-setup.md#chatgpt-desktop)
- [Cursor](guides/client-setup.md#cursor)

Each client starts its own local Perenna process. All processes use the same
Perenna home unless you configure a different one.

## What happens on first connection

Perenna initializes the resolved home automatically:

```text
~/.perenna/
├── memory/   # independent Git repository and permanent Markdown
└── index/    # Vexor cache, commit marker, and lock files
```

The `memory/` directory starts on a `main` branch and uses a repository-local
Perenna commit identity. Perenna does not change your global Git identity.

## Optional: set up a backup remote

After the first connection creates the memory repository, you can attach an
empty private Git repository for best-effort backup. Follow
[Set up a backup remote](reference/configuration.md#set-up-a-backup-remote) for
the `git remote add` command, non-interactive credential requirements, and
connection checks.

## Verify the first session

After the client reports that Perenna is connected:

1. Call `memory` with `action: "query"` and no query text.
2. Confirm that the response contains a lightweight memory index.
3. Write a disposable test topic only if you want to verify the full Git and
   retrieval path.
4. Inspect the generated repository with:

```bash
git -C ~/.perenna/memory status --short
git -C ~/.perenna/memory log --oneline
```

On Windows, replace `~/.perenna` with the resolved home shown by your shell.

Next, read [Using permanent memory](guides/using-memory.md). For non-default
paths, sources, remote names, or embedding providers, use the
[configuration reference](reference/configuration.md).
