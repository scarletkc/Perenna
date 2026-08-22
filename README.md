# Perenna

Perenna is a local-first permanent memory service for AI agents. Claude Code,
Codex, ChatGPT Desktop, Cursor, and other local MCP clients can share durable
memories without sharing a vendor account or conversation history.

- Separate stdio MCP tools for reading, writing, and deleting memories
- Human-readable Markdown stored in an independent Git repository
- Local Vexor retrieval index that can always be rebuilt from Git
- Cross-process locking for multiple local agent processes

## Install

Perenna requires Python 3.12+, Git, and
[uv](https://docs.astral.sh/uv/).

```bash
git clone https://github.com/scarletkc/Perenna.git
cd Perenna
uv tool install .
```

Configure an MCP client to start:

```text
perenna mcp --source <client-name>
```

Perenna creates its local data under `~/.perenna/` unless another home is
configured.

## Documentation

Start with the [documentation index](docs/index.md), then follow the path for
your task:

- [Getting started](docs/getting-started.md)
- [Client setup](docs/guides/client-setup.md)
- [Using permanent memory](docs/guides/using-memory.md)
- [Configuration reference](docs/reference/configuration.md)
- [Architecture](docs/concepts/architecture.md)
- [Development guide](docs/development/contributing.md)

## License

[MIT](LICENSE)
