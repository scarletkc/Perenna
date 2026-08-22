# Perenna v0.1：Local-first 架构与需求规范

**状态：v0.1 正式边界**

本文定义 Perenna v0.1 的产品边界、运行契约与验收标准。文件格式、恢复操作和
Vexor 配置分别由下列规范维护，本文不复制其详细规则：

- [Markdown 记忆格式](memory-format.md)
- [恢复与人工维护](recovery.md)
- [Vexor 配置与隐私](vexor.md)

## 1. 定位与边界

Perenna 是独立于 AI 厂商的本地永久记忆服务。它不替代各平台自己的 Memory，
也不自动把历史内容注入每一轮上下文。Agent 只在需要历史信息时查询，在信息确实
值得跨会话、跨 Agent 保留时写入。

v0.1 只提供本地 stdio MCP：

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
                   │
                   └── optional git push
                              │
                              ▼
                       Private Git Remote
                              备份
```

每个本地 Agent 启动自己的 Perenna 进程。多个进程共享同一个 Perenna home，
并通过跨进程文件锁协调。Core 不依赖 MCP transport；v0.1 只在 Core 外提供
stdio 适配，不定义通用 transport interface，也不建立尚无调用者的扩展层。

v0.1 不包含网络 MCP 入口、服务端认证、多用户、远程同步协议、Web UI 或服务部署。

## 2. 核心不变量

1. Git repository 中的 Markdown 是唯一 Source of Truth。
2. Vexor index 是可删除、可重建的本地 cache，不拥有永久数据。
3. Agent 只看到一个名为 `memory` 的 MCP tool，以及 `query`、`write` 两种动作。
4. `source` 由启动 Perenna 的可信宿主注入，模型不能在 tool 参数中声明它。
5. 一次成功的 `write` 表示目标 Markdown 已原子落盘并产生一个本地 Git commit。
6. 索引或远程备份失败不能否定已经成功的本地 commit。
7. 未提交的人工编辑不会被 Perenna 的 query 索引或返回。
8. stdio 运行期间 stdout 只承载 MCP 协议；诊断和脱敏日志只写 stderr。

## 3. 本地目录与启动配置

默认目录固定为：

```text
~/.perenna/
├── memory/       # 独立 Git repository
└── index/        # Vexor cache、indexed_commit 和锁文件
```

CLI 入口为：

```text
perenna mcp [--source SOURCE] [--home PATH]
```

配置解析必须使用以下优先级：

| 有效值 | 从高到低 |
| --- | --- |
| Perenna home | `--home` → `PERENNA_HOME` → `~/.perenna` |
| Agent source | `--source` → `PERENNA_SOURCE` |

`source` 没有默认值；flag 与环境变量都未提供有效值时，进程必须拒绝启动。
`source` 不进入 MCP tool schema。

Git remote 的运行配置为：

- 未设置 `PERENNA_GIT_REMOTE`：检查名为 `origin` 的 remote；
- 设置为非空值：使用该名字；
- 设置为空值：禁用自动 push。

首次运行、异常目录和人工恢复的完整处理流程见
[恢复与人工维护](recovery.md)。

## 4. MCP 公共接口

Server 只注册一个 tool：

```text
memory
```

其 input schema 必须精确为：

```json
{
  "type": "object",
  "properties": {
    "action": {
      "type": "string",
      "enum": ["query", "write"]
    },
    "query": {
      "type": "string"
    },
    "title": {
      "type": "string"
    },
    "body": {
      "type": "string"
    },
    "project": {
      "type": "string"
    }
  },
  "required": ["action"],
  "additionalProperties": false
}
```

服务端还必须按 action 执行组合校验：

- `query` 只接受可选的 `query`、`project`，拒绝 `title`、`body`；
- `write` 要求 `title`、`body`，接受可选的 `project`，拒绝 `query`；
- 未声明字段一律拒绝。

### 4.1 Query：轻量索引

没有 `query` 字段时，Core 直接读取最后一次已提交的 Git 快照并返回轻量索引：

- 没有 `project`：列出 global title 与可用 project slug，不展开每个项目的全部
  title；
- 有 `project`：列出 global title 与该 project 的 title。

轻量索引只用于告诉 Agent“有哪些主题可查”，不返回所有正文。

### 4.2 Query：Recall

提供非空 `query` 时，Core 通过 Vexor 检索，最终最多返回 5 条完整记忆。没有
`project` 时搜索所有 scope；有 `project` 时只允许：

```text
global
project:<slug>
```

过滤在打分前完成。返回内容必须来自可信相对路径所指向的已提交 Markdown，不能
直接把索引中的任意路径当作文件系统路径。

### 4.3 Write：按标题 Upsert

`write` 的语义是同 scope 按 normalized title upsert：

```text
不存在 → 创建新 ULID 与 Markdown
已存在 → 保持 id、created_at，替换 title/body 并更新 source、updated_at
```

Agent 应在修改已有主题前先 query 当前正文，再提交期望保留的完整 body。Perenna
不执行 LLM merge，也不向 Agent 暴露 create、update、delete、commit、push 或
reindex 动作。

## 5. Core 职责

Core 直接提供三个能力：

```text
list-index
recall
write
```

stdio handler 只负责：

1. 注册精确 schema；
2. 校验并分发 action；
3. 注入启动时解析出的可信 `source`；
4. 把预期错误转换为不泄露正文的 MCP error result。

存储和检索模块都不能依赖 stdio。v0.1 不创建网络 transport、认证或 deployment
模块。

## 6. 初始化与 Git repository

启动时初始化 Perenna home：

- `memory/` 不存在或为空：创建目录，以 `main` 为初始分支初始化 Git，并写入
  repo-local 的 Perenna commit identity；
- `memory/` 非空且不是有效 Git repository：拒绝启动，保留全部现有内容并给出
  恢复路径；
- `index/` 不存在：自动创建；其全部内容都可从 Git 重建。

实际记忆 repository 与 Perenna 源代码 repository 必须是两个不同目录。运行时
不能向源代码仓库写入记忆。

## 7. 写入事务与 Git

每次 `write` 在 repository 独占锁内按顺序执行：

1. 确认 Git working tree 与 index 干净；
2. 从已提交数据解析 scope 与同标题记录；
3. 原子替换唯一目标 Markdown；
4. 只 stage 该目标文件；
5. 创建且只创建一个 Git commit；
6. 在锁内尝试增量更新 Vexor；
7. 释放 repository lock；
8. 在独立 push lock 内尝试远程备份。

如果 commit 失败，Perenna 必须恢复目标文件和 Git index，使 repository 回到
调用前状态。存在人工未提交修改时，write 返回明确错误，不覆盖、stage 或 commit
这些修改。

每次 write 产生一个只包含目标 Memory 文件的 commit。Git commit identity 使用
repo-local Perenna 配置；实际写入来源保存在 Markdown 的 `source` 字段中。

## 8. 并发模型

Perenna 使用跨进程 reader/writer lock：

- list-index 与状态正常的 recall 取得共享锁，因此多个查询可以并发；
- write 与全量 rebuild 取得独占锁，彼此互斥；
- recall 发现索引过期后先释放共享锁，再在独占锁内复检并 rebuild；
- push 使用另一把独立锁，不阻塞 repository 内的正常查询。

两个进程同时写入时，后获得锁的进程必须基于前一个 commit 的最新 HEAD 重新执行
upsert 判断，不能复用锁外读取的旧状态。

## 9. 已提交快照与人工编辑

Query 永远以 Git HEAD 为边界。即使 working tree 有人工未提交修改：

- list-index 继续读取 HEAD；
- recall 继续读取与 HEAD 对齐的索引和 Markdown；
- 未提交的新文件、正文或删除都不可见；
- write 暂停，等待用户处理 working tree。

这样人工编辑既不会被 Agent 提前读到，也不会被后台 rebuild 编入索引。具体恢复
步骤见 [恢复与人工维护](recovery.md)。

## 10. Vexor 索引

Perenna 使用 Vexor Collections API，collection 名固定为：

```text
perenna-memories
```

`index/indexed_commit` 记录索引对应的 Git HEAD。HEAD 不一致、collection 缺失或
整个 index 被移除时，下次 recall 在独占锁内从 Git HEAD 全量重建。write 后若
索引与写入前 HEAD 对齐，则增量 upsert 当前记录并把 marker 推进到新 HEAD。

Vexor provider 报错不能回滚已完成的 Memory commit。write 返回成功并在 stderr
记录脱敏诊断；需要索引的 recall 返回明确错误，下一次 recall 继续尝试恢复。

Record、scope filter、provider、cache 和隐私规则的唯一详细规范见
[Vexor 配置与隐私](vexor.md)。

## 11. Git remote 备份

本地 commit 是 write 成功边界。索引处理结束后，Perenna 才 best-effort push：

- remote 不存在：跳过 push；
- 当前分支没有 upstream：首次 push 可建立 upstream；
- push 使用固定超时；
- 超时、凭据或网络错误只写 stderr，不改变 write 的成功结果；
- Perenna 不执行 pull 或 fetch，也不实现远程冲突合并。

Remote 是可选备份，不参与 query、upsert 判断和本地事务。

## 12. 数据格式与输入规范

Memory 路径、frontmatter、title/project/body 规范与重复数据判定由
[Markdown 记忆格式](memory-format.md) 定义。实现必须在写文件前完成全部输入
校验，并在读取已提交快照时拒绝损坏或含未知字段的文档。

Perenna 不提供 delete tool。用户需要删除或恢复历史时，通过 Git 人工操作并提交，
随后由 HEAD 变化触发索引重建。

## 13. 日志与隐私

正常日志不得包含：

- Memory body；
- recall query 原文；
- provider API key 或其他凭据；
- 完整 MCP request payload。

诊断可以记录 action、脱敏后的 source/project、结果数量、操作类型、短 commit ID、
耗时和异常类型。stdio 模式的任何日志、traceback 或依赖库输出都必须定向到 stderr，
不能污染 stdout。

若选择远程 embedding provider，记忆内容会离开本机；该边界必须在配置前阅读
[Vexor 配置与隐私](vexor.md)。

## 14. Failure model

| 失败点 | 对外结果 | 持久状态 |
| --- | --- | --- |
| 输入或 Markdown 校验失败 | 操作失败 | 不写文件、不 stage |
| working tree dirty | write 失败；query 继续读 HEAD | 人工修改保持原样 |
| 原子替换失败 | write 失败 | 原文件保持 |
| Git stage/commit 失败 | write 失败 | 文件与 index 回滚 |
| Vexor 增量或 rebuild 失败 | write 仍可成功；recall 明确失败 | Git commit 保留，marker 不前移 |
| Git push 失败或超时 | write 成功 | 本地 commit 保留 |

恢复操作必须以 Git 为准，不以 `index/` 中的内容反向修复 Memory。

## 15. 验收与测试

### 15.1 单元测试

必须覆盖：

- tool schema 精确值与 `additionalProperties: false`；
- home/source 优先级及缺失 source；
- 首次初始化、空目录与非空非 Git 目录；
- title、project、body 规范化和拒绝路径穿越；
- frontmatter 允许字段、重复 ID 与同 scope 重复标题；
- 原子写入、Git rollback、dirty repository；
- 日志和 MCP error 不泄露 body/query。

### 15.2 Vexor 与 Git 测试

必须覆盖：

- 增量 upsert、project scope 预过滤、stale rebuild；
- 删除整个 index 后从 Git 恢复；
- provider 或 index 失败不影响已提交 write；
- 首次 commit、update commit、source 与时间字段；
- remote 缺失、push 成功、超时和失败仍返回 write success。

### 15.3 MCP 与多进程测试

必须用官方 MCP stdio client 启动真实子进程并验证：

- stdout 没有协议外内容；
- 只存在 `memory` tool，且 schema 精确；
- 不同 `--source` 进程共享同一记忆 repository；
- 两个并发 writer 产生两个有效 commit、完整 Markdown 和干净 working tree；
- 多个 recall 可并发，rebuild 与 write 互斥。

### 15.4 端到端场景

按顺序执行：

1. `claude-code` 创建一条记忆；
2. `codex` recall 同一条记忆；
3. `cursor` 以同标题写入完整新正文。

最终必须验证：文件 ID 不变、`created_at` 不变、`updated_at` 与 `source` 更新、Git
history 有两个逻辑 commit、repository 保持干净。

### 15.5 CI

CI 在 Windows 与 Linux、Python 3.12 与 3.13 上运行 Ruff、pytest、coverage 和
package build。真实 provider smoke test 单独标记，不进入默认离线测试。

## 16. v0.1 成功标准

```text
Agent A write
      ↓
Markdown + local Git commit
      ↓
Vexor 可检索
      ↓
Agent B query
      ↓
Agent C 以同一 ID 更新
      ↓
Git history 保留完整变化
```

只要这一闭环在本地、多进程和索引可恢复条件下稳定成立，v0.1 即达到目标。

## 17. 后续路线

本地 `query / write / Git history / Vexor retrieval` 稳定后，可以在同一个 Perenna
Core 外增加 Streamable HTTP MCP adapter。其身份、访问控制和运行环境届时另行
设计，不属于 v0.1 契约。

> **Git stores memory. Vexor retrieves memory. MCP exposes memory.**
