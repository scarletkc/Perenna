# Perenna

Perenna 是一个给本地 AI Agent 共用的永久记忆服务。Claude Code、Codex、
ChatGPT Desktop 和 Cursor 各自启动一个 stdio MCP 进程，但共享同一份本机
Git-backed Markdown 记忆库；Vexor 只保存可重建的本地检索索引。

```text
Claude Code / Codex / ChatGPT Desktop / Cursor
                        │
                    MCP stdio
                        │
                        ▼
                     Perenna
                   ┌────┴────┐
                   │         │
              Git + Markdown Vexor
              永久数据       本地索引
```

v0.1 是纯本地版本。实际记忆默认位于 `~/.perenna/memory/`，索引位于
`~/.perenna/index/`。详细契约见：

- [Local-first 架构与需求](docs/跨%20Agent%20永久记忆服务：架构与需求设计方案.md)
- [Markdown 记忆格式](docs/memory-format.md)
- [恢复与人工维护](docs/recovery.md)
- [Vexor 配置与隐私](docs/vexor.md)

## 安装

需要 Python 3.12+、Git 和 [uv](https://docs.astral.sh/uv/)。从源码安装用户级
命令：

```bash
git clone https://github.com/scarletkc/Perenna.git
cd Perenna
uv tool install .
```

如需在本机执行 embedding，把上面的 `uv tool install .` 改为安装 local extra：

```bash
uv tool install '.[local]'
```

local extra 不代表安装过程完全离线；首次取得 Python 依赖和本地 embedding
模型仍可能需要网络。Provider 的选择和数据边界见
[Vexor 配置与隐私](docs/vexor.md)。

## 首次启动

`source` 标识启动 Perenna 的宿主，必须显式提供。直接检查启动流程可以运行：

```bash
perenna mcp --source codex
```

进程等待 MCP stdio 输入是正常行为，可用 `Ctrl+C` 退出。首次运行会创建：

```text
~/.perenna/
├── memory/       # 独立 Git repository，唯一 Source of Truth
└── index/        # Vexor cache、indexed_commit 和锁文件
```

通常无需手动启动；配置下面任一客户端后，由客户端负责启动进程。

## Claude Code

添加用户级 stdio server：

```bash
claude mcp add --scope user --transport stdio perenna -- perenna mcp --source claude-code
claude mcp get perenna
```

命令格式参考 [Claude Code MCP 官方文档](https://code.claude.com/docs/en/mcp)。

## Codex / ChatGPT Desktop

通过 Codex CLI 添加：

```bash
codex mcp add perenna -- perenna mcp --source codex
codex mcp list
```

ChatGPT Desktop、Codex CLI 与 Codex IDE extension 在同一 Codex host 上共享
MCP 配置；保存后重启相应客户端即可。也可以在 ChatGPT Desktop 的
**Settings → MCP servers → Add server** 中选择 STDIO，并使用同一启动命令。
参见 [OpenAI MCP 官方文档](https://developers.openai.com/codex/mcp/)。

## Cursor

在用户级 `~/.cursor/mcp.json` 中加入：

```json
{
  "mcpServers": {
    "perenna": {
      "command": "perenna",
      "args": ["mcp", "--source", "cursor"]
    }
  }
}
```

配置位置与格式参考 [Cursor MCP 官方文档](https://docs.cursor.com/context/model-context-protocol)。
