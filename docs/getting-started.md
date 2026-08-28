# Getting Started

This guide installs Perenna, checks the command, and prepares the first client
connection.

## Requirements

- Python 3.12 or newer
- Git available on `PATH`
- [uv](https://docs.astral.sh/uv/)
- an MCP client that can start a local stdio server

## Install

Install a published release:

```bash
uv tool install perenna
```

To install from source instead:

```bash
git clone https://github.com/scarletkc/Perenna.git
cd Perenna
uv tool install .
```

Verify that the installed command is available:

```bash
perenna --help
```

### Install the memory behavior skill

Install the bundled skill for the client that will use Perenna:

```bash
perenna skill install --agent codex
# or
perenna skill install --agent claude-code
```

If both clients are installed, repeat `--agent` in one command. The default is
user scope so the skill is available across projects. Use `--scope project`
inside a Git working tree when the skill should apply only to that repository.
See [Bundled Agent Skill](reference/configuration.md#bundled-agent-skill) for
the destination paths and replacement safeguards.

For Codex or Claude Code, the combined
[Plugin setup](guides/plugin-setup.md) installs the Skill and local MCP
connection together. Choose either the plugin path or the standalone Skill plus
client configuration; do not install both.

## Configure retrieval

Perenna uses Vexor for semantic retrieval. Configure and verify the provider in
the same environment that will start the MCP client:

```bash
uvx vexor init
uvx vexor doctor
```

Remote providers receive memory text and search queries. To keep embedding
local, install Vexor's local dependencies with Perenna's `local` extra:

```bash
uv tool install "perenna[local]"
```

For a source checkout, use `uv tool install ".[local]"` instead.

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
├── config.json  # created after a synchronization choice is saved
├── memory/      # independent Git repository and permanent Markdown
└── index/       # Vexor cache, commit marker, and lock files
```

The `memory/` directory starts on a `main` branch and uses a repository-local
Perenna commit identity. Perenna does not change your global Git identity. The
[Perenna home](reference/configuration.md#perenna-home) section owns path
resolution and the complete directory contract.

## Optional: set up Git synchronization

You can attach a private Git repository before or after the first connection:

```text
perenna sync setup <repository-url>
```

For an unattended container, add `--deploy-key` to generate a persistent,
repository-specific SSH key and receive the exact registration instructions.
Setup imports an existing remote into an empty local repository, publishes an
existing local repository to an empty remote, and fast-forwards compatible
history. A successful setup saves the selected remote for later Perenna
processes. It stops on diverged history rather than merging automatically.

Follow [Git remote synchronization](reference/configuration.md#git-remote-synchronization)
for remote selection, credential requirements, replacement safeguards, local-only
mode, and status checks.

## Verify the first session

After the client reports that Perenna is connected:

1. Call `memory_read` with `action: "list"`.
2. Confirm that the response contains the lightweight memory index.
3. Create a disposable test topic through `memory_write` only if you want to
   verify the full Git and retrieval path; create requires title, stable
   one-line summary, and body.
4. Inspect the generated repository with:

```bash
git -C ~/.perenna/memory status --short
git -C ~/.perenna/memory log --oneline
```

On Windows, replace `~/.perenna` with the resolved home shown by your shell.

Next, read [Using permanent memory](guides/using-memory.md). For non-default
paths, sources, remote names, or embedding providers, use the
[configuration reference](reference/configuration.md).

## Update a published installation

Upgrade Perenna and confirm the installed version:

```bash
uv tool upgrade perenna
perenna --version
```

If you installed the Skill separately, refresh its bundled copy after the
upgrade using the same scope as the original installation.

For the default user scope:

```bash
perenna skill install --agent codex --replace
# or
perenna skill install --agent claude-code --replace
```

For project scope, run the command from that Git working tree:

```bash
perenna skill install --agent codex --scope project --replace
# or
perenna skill install --agent claude-code --scope project --replace
```

Repeat `--agent` in one command when both standalone Skills should be updated.
When an installed copy differs, `--replace` moves it to a timestamped backup
before installing the bundled version. Follow the
[plugin setup guide](guides/plugin-setup.md) to update the combined plugin. See
the [configuration reference](reference/configuration.md#bundled-agent-skill)
for the installation scopes and safeguards.

For source development, use the locked environment in
[Contributing](development/contributing.md#set-up-the-repository).
