# Perenna

A lightweight, Git-backed permanent memory for AI agents. Claude Code, Codex,
ChatGPT, Cursor, and other MCP clients can share durable memories without
sharing a vendor account or conversation history.

- Separate MCP tools for reading, writing, and deleting memories
- Local stdio and single-user OAuth-protected Streamable HTTP transports
- Human-readable Markdown stored in an independent Git repository
- Local Vexor retrieval index that can always be rebuilt from Git
- Cross-process locking for multiple local agent processes

## Install a published release

Perenna requires Python 3.12+, Git, and
[uv](https://docs.astral.sh/uv/).

```bash
uv tool install perenna
```

Configure an MCP client to start:

```text
perenna mcp --source <client-name>
```

Perenna creates its local data under `~/.perenna/` unless another home is
configured.

## Install from source for development

```bash
git clone https://github.com/scarletkc/Perenna.git
cd Perenna
uv tool install .
```

## Documentation

Start with the
[documentation index](https://github.com/scarletkc/Perenna/blob/main/docs/index.md),
then follow the path for your task:

- [Getting started](https://github.com/scarletkc/Perenna/blob/main/docs/getting-started.md)
- [Client setup](https://github.com/scarletkc/Perenna/blob/main/docs/guides/client-setup.md)
- [Self-hosting for ChatGPT](https://github.com/scarletkc/Perenna/blob/main/docs/guides/self-hosting.md)
- [Using permanent memory](https://github.com/scarletkc/Perenna/blob/main/docs/guides/using-memory.md)
- [Configuration reference](https://github.com/scarletkc/Perenna/blob/main/docs/reference/configuration.md)
- [Architecture](https://github.com/scarletkc/Perenna/blob/main/docs/concepts/architecture.md)
- [Development guide](https://github.com/scarletkc/Perenna/blob/main/docs/development/contributing.md)

## License

[MIT](https://github.com/scarletkc/Perenna/blob/main/LICENSE)
