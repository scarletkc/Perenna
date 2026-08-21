# 跨 Agent 永久记忆服务：架构与需求设计方案

**版本：v0.1**  
**状态：Initial Design**

## 1. 项目概述

本项目提供一个独立于任何 AI 厂商的个人永久记忆服务，使 Claude、Codex、ChatGPT、Cursor 等不同 AI Agent 可以访问同一份长期记忆。

系统不替代各 AI 自带的 Memory，也不自动把永久记忆注入模型上下文。

各层职责如下：

```text
当前 Conversation
    ↓
短期工作记忆

AI Native Memory
    ↓
平台自己的记忆缓存

Shared Permanent Memory
    ↓
跨 Agent、跨平台、跨会话的永久记忆
```

永久记忆服务只提供两个语义动作：

```text
query
write
```

模型需要历史信息时主动查询。

出现值得永久保存的信息时主动写入。

系统内部负责：

- 存储
- 搜索
- 更新
- Git 版本历史
- scope
- source
- 索引维护
- 认证
- 冲突恢复

这些内部机制不暴露给 Agent。

---

# 2. 核心设计原则

## 2.1 Permanent Memory，而不是 Context Injection

系统不会：

```text
每次请求
↓
自动搜索历史
↓
塞入模型 Context
```

系统采用：

```text
Session 开始
↓
Agent 主动读取轻量 Memory Index
↓
知道有哪些永久记忆
↓
正常工作
↓
只有需要历史信息时才 query
```

这样可以避免：

- 大量无关记忆污染上下文
- 每轮请求增加 Token
- 检索结果错误影响当前任务
- Agent 过度依赖旧信息
- 自动召回造成不可控行为

---

## 2.2 Agent 只需要理解两个动作

所有客户端只看到一个 MCP Tool：

```text
memory
```

它只有两个 action：

```text
query
write
```

不暴露：

```text
create
update
delete
merge
supersede
rerank
reindex
commit
push
embedding
```

Agent 不操作数据库。

Agent 只表达：

```text
我需要回忆什么
```

或者：

```text
我希望永久记住什么
```

---

## 2.3 Git 是 Source of Truth

永久记忆本质上是一组 Markdown 文档。

```text
Git repository
        ↓
Markdown memories
```

Git 提供：

- 持久化
- 历史
- Diff
- Audit
- Revert
- Backup
- Migration
- 人工编辑能力

Vexor 只负责搜索。

```text
Git = Truth

Vexor = Retrieval Index
```

任何时候 Vexor 索引都可以从 Git 仓库完全重建。

---

## 2.4 不设计复杂 Memory Schema

第一版不包含：

- preference
- identity
- relationship
- workflow
- decision
- fact
- daily
- knowledge
- episode

等 Memory Type。

一条记忆只有：

```text
title
body
```

再附加系统必要元数据：

```text
id
source
created_at
updated_at
```

作用域由目录表示。

---

# 3. Scope 设计

第一版只存在两个 Scope：

```text
global

project
```

## Global

适用于所有 Agent 和所有项目。

例如：

```text
AI 协作偏好

编程习惯

长期个人背景

常用工具偏好
```

存储位置：

```text
global/
```

---

## Project

只在某个项目上下文中适用。

例如：

```text
projects/vexor/

projects/crown-marshal/
```

项目 Scope 中可以保存：

```text
架构决策
工作流
历史原因
项目约束
已知问题
设计原则
```

系统不建立更多层级。

如果未来确实出现需求，再考虑：

```text
project/subscope
```

v1 不实现。

---

# 4. Repository 结构

建议仓库：

```text
memory-repo/
├── global/
│   ├── 01KABC....md
│   ├── 01KABD....md
│   └── 01KABE....md
│
├── projects/
│   ├── vexor/
│   │   ├── 01KAC1....md
│   │   ├── 01KAC2....md
│   │   └── 01KAC3....md
│   │
│   └── crown-marshal/
│       ├── 01KAD1....md
│       └── 01KAD2....md
│
└── README.md
```

文件名使用稳定 ID。

不要使用 title 作为文件名。

原因：

- Title 可以修改
- Unicode title 不影响路径
- 避免路径注入
- 避免重名
- Git rename 更少

推荐：

```text
ULID
```

或者：

```text
UUIDv7
```

---

# 5. Memory 文件格式

每条 Memory 是一个 Markdown 文件。

例如：

```markdown
---
id: 01KABCDEF123456789
title: AI 协作偏好
source: claude-code
created_at: 2026-08-22T07:10:00+08:00
updated_at: 2026-08-22T07:10:00+08:00
---

希望 AI 在明确任务中主动完成工作。

对于普通实现选择，不需要频繁询问确认。

遇到重要设计决策时，应解释原因。
```

Scope 不写入 Frontmatter。

Scope 从文件位置确定：

```text
global/01K....md
```

即：

```text
scope = global
```

而：

```text
projects/vexor/01K....md
```

即：

```text
scope = project:vexor
```

---

# 6. Source 设计

`source` 必须存在。

例如：

```text
claude-code
codex
chatgpt
cursor
manual
```

Agent 不主动填写 source。

Source 由认证 Token 决定。

例如：

```text
TOKEN_A
→ claude-code

TOKEN_B
→ codex

TOKEN_C
→ chatgpt
```

因此：

```text
Bearer Token
     ↓
Auth Middleware
     ↓
source = claude-code
```

这可以避免 Agent：

```text
source="user"
```

之类的不可信输入。

如果其他 Agent 后来更新同一条 Memory：

```text
source
```

更新为最后修改者。

之前的 source 仍然可以从 Git History 中恢复。

---

# 7. Memory 的语义

永久记忆不是 Atomic Fact Database。

它更接近：

> 一个有名字的长期 Note。

例如：

```text
Title:
AI 协作偏好
```

Body 可以包含几个相关事实：

```text
- 喜欢 Agent 主动执行。
- 普通实现选择无需确认。
- 重要决策需要解释。
```

因此系统避免：

```text
memory 1:
喜欢主动执行

memory 2:
不喜欢频繁确认

memory 3:
喜欢解释设计决策
```

这种 Memory Explosion。

推荐：

```text
一个长期主题
=
一个 Memory Document
```

---

# 8. Title 的作用

Title 同时承担：

- Memory Index 展示
- 人类理解
- Topic Identity
- Update Key

在同一个 Scope 中：

```text
Normalized Title
```

必须唯一。

例如：

```text
global/
AI 协作偏好
```

只能存在一份。

---

# 9. Write 语义

`write` 实际是：

```text
UPSERT BY TITLE
```

流程：

```text
memory(write)
      ↓
确定 Scope
      ↓
normalize(title)
      ↓
检查同 Scope 是否存在相同 title
      ↓
      ├─ 不存在 → CREATE
      │
      └─ 存在 → UPDATE
```

更新时：

```text
id          保持
created_at  保持

body        替换
source      更新
updated_at  更新
```

这里不使用 LLM 自动 merge。

Agent 如果准备修改已有 Memory，应首先 query 原 Memory，然后提交完整的新 Body。

例如：

```text
query:
"AI 协作偏好"
```

得到当前内容。

Agent修改完成后：

```text
write:
title = "AI 协作偏好"
body = 完整的新版本
```

服务器直接替换。

这可以避免自动 merge 误改长期记忆。

---

# 10. 第一版不允许 Agent Delete

MCP 不提供：

```text
delete_memory
```

原因：

永久记忆删除是高风险操作。

如果信息过期：

Agent 更新对应 Memory 即可。

旧版本仍保留在：

```text
Git History
```

需要真正删除时：

用户可以：

```text
SSH
Git
Admin CLI
```

人工处理。

以后如果确实需要，可以添加管理接口。

不进入 v1。

---

# 11. MCP Tool 设计

整个 Server 只注册：

```text
memory
```

Schema：

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

服务端负责根据 action 校验字段。

---

# 12. Query：Memory Index 模式

当：

```json
{
  "action": "query"
}
```

且没有 `query`：

服务返回：

```text
Memory Index
```

这不是搜索。

它只告诉模型：

> 有哪些永久记忆可以查询。

---

## 无 Project 上下文

返回：

```text
Global memories:

- AI 协作偏好
- Python 开发习惯
- 常用 AI 工具

Projects:

- vexor
- crown-marshal
- another-project
```

不会把所有项目里的所有 Memory Title 全展开。

---

## 有 Project

请求：

```json
{
  "action": "query",
  "project": "vexor"
}
```

返回：

```text
Global memories:

- AI 协作偏好
- Python 开发习惯

Project: vexor

- 架构原则
- Git 工作流
- 配置系统设计
- API 兼容性原则
```

这个 Index 应保持非常轻量。

目标：

```text
几十～几百 Token
```

而不是几千 Token。

---

# 13. Query：Recall 模式

请求：

```json
{
  "action": "query",
  "query": "这个项目之前为什么没有选择 Redis？",
  "project": "vexor"
}
```

流程：

```text
query
 ↓
Vexor
 ↓
Top candidates
 ↓
Scope Filter
 ↓
读取 Markdown 原文
 ↓
返回 Agent
```

返回：

```text
[Project: vexor]

Title: 架构决策
Source: claude-code
Updated: ...

正文……
```

默认最多返回：

```text
5 memories
```

不让 Agent 自己设置 `limit`。

避免 Tool Schema 继续膨胀。

---

# 14. Vexor 搜索策略

Vexor 只作为索引。

索引内容：

```text
title

+

body
```

可以额外把：

```text
scope
```

作为 metadata 或 searchable path。

---

## 无 Project

搜索整个 Repository。

---

## 有 Project

候选 Scope：

```text
global

+

project:<current>
```

第一版可以简单处理：

```text
Vexor top 30
↓
服务器根据 path filter
↓
保留 global + 当前 project
↓
取前 5
```

对于个人记忆库规模，这个方式足够简单。

无需为了 Scope 再建：

```text
多个 vector index
```

---

# 15. Vexor Index 一致性

Git Repository 是 Truth。

Vexor Index 是 Cache。

Runtime 保存：

```text
last_indexed_commit
```

例如：

```text
.runtime/
└── indexed_commit
```

服务启动或执行 query 时：

```text
git rev-parse HEAD
        ↓
比较
        ↓
last_indexed_commit
```

如果一致：

```text
直接搜索
```

如果不同：

```text
refresh Vexor index
↓
更新 indexed_commit
```

因此：

即使某次写入成功，但 Vexor Index 更新失败：

```text
Memory 不会丢失
```

下一次 query 可以自动恢复索引。

---

# 16. Write 流程

完整写入流程：

```text
Agent
 ↓
memory(write)
 ↓
Authentication
 ↓
Resolve source
 ↓
Validate project/title/body
 ↓
Acquire write lock
 ↓
Resolve scope
 ↓
Find memory by normalized title
 ↓
Create / Update Markdown
 ↓
Atomic file replace
 ↓
git add
 ↓
git commit
 ↓
Refresh Vexor
 ↓
Release lock
 ↓
Return result
```

成功标准：

> Memory 文件已经持久化，并已经产生 Git Commit。

远程 Git push 不属于写入成功条件。

---

# 17. Git Commit 策略

每一次逻辑 Write：

```text
一个 Git Commit
```

Create：

```text
memory(global): add "AI 协作偏好"
```

Update：

```text
memory(vexor): update "API 兼容性原则"
```

Git Commit Author 可以统一：

```text
Memory Service
```

真正的 Agent 来源存储在：

```text
source
```

Frontmatter 中。

---

# 18. Remote Git

VPS 上的本地 Working Copy 是主存储。

```text
VPS repo
=
canonical working copy
```

远程 Private Git Repository 只负责：

```text
backup
mirror
disaster recovery
```

不要设计：

```text
每次 write
↓
git pull
↓
修改
↓
commit
↓
push
```

Remote Git 不应该出现在 Write Transaction 中。

推荐：

```text
write
 ↓
local commit
 ↓
尝试 git push
```

Push 失败：

```text
不影响 memory write 成功
```

下一次 Write 再尝试 Push。

还可以由：

```text
systemd timer
```

定时执行：

```bash
git push
```

---

# 19. Remote Repository 编辑规则

第一版规定：

> Remote Repository 是 Mirror，不是第二个并发 Writer。

不要同时：

```text
GitHub Web Editor
+
Memory Server
```

修改仓库。

如果需要人工编辑：

优先：

```text
SSH VPS
↓
修改本地 Working Copy
↓
commit
```

以后可以增加：

```text
memoryctl sync
```

处理 Remote Changes。

v1 不做复杂 Git Conflict Resolution。

---

# 20. Concurrency

这是个人 Memory Server。

第一版采用：

```text
Single Writer
```

所有 Write 使用：

```text
file lock
```

Linux 环境可以直接：

```text
fcntl.flock
```

无需 Redis。

无需 Distributed Lock。

无需数据库事务。

Query 可以并发。

Write 必须串行。

---

# 21. Authentication

每个 Agent 单独一个 Bearer Token。

例如：

```text
MEMORY_TOKEN_CLAUDE_CODE
MEMORY_TOKEN_CODEX
MEMORY_TOKEN_CHATGPT
MEMORY_TOKEN_CURSOR
```

服务内部映射：

```text
token
↓
source
```

例如：

```text
abc123
→ claude-code
```

这样：

```text
source
```

不可由模型伪造。

---

# 22. 网络架构

推荐：

```text
Internet
   ↓
HTTPS
   ↓
Caddy / Cloudflare Tunnel
   ↓
Memory MCP Server
   ↓
Git + Vexor
```

Memory Server 不直接暴露裸 HTTP。

MCP Endpoint：

```text
https://memory.example.com/mcp
```

Authentication：

```text
Authorization: Bearer <token>
```

---

# 23. Server 技术栈

第一版建议：

```text
Python 3.12+
Official MCP Python SDK
Streamable HTTP
Uvicorn
Git
Markdown
Vexor
```

不需要：

```text
FastAPI
PostgreSQL
D1
SQLite
Qdrant
Neo4j
Redis
Celery
LangChain
Mem0
ORM
Migration framework
```

如果以后需要普通 REST API，再引入 FastAPI。

第一版 MCP SDK 自己提供 HTTP transport 即可。

---

# 24. Python 项目结构

建议：

```text
memory-server/
├── src/
│   └── memory_server/
│       ├── __init__.py
│       ├── server.py
│       ├── tool.py
│       ├── auth.py
│       ├── store.py
│       ├── search.py
│       ├── git.py
│       ├── index.py
│       ├── models.py
│       └── config.py
│
├── tests/
│   ├── test_store.py
│   ├── test_tool.py
│   ├── test_auth.py
│   ├── test_git.py
│   └── test_search.py
│
├── pyproject.toml
├── README.md
└── LICENSE
```

保持模块直接。

不要提前设计大量 abstraction/interface。

---

# 25. Store API

内部 `store.py` 只需要几个函数：

```python
list_index(project: str | None)

find_by_title(
    title: str,
    project: str | None,
)

create_memory(...)

update_memory(...)

read_memory(...)
```

不需要 Generic Repository Pattern。

---

# 26. Search API

`search.py`：

```python
search_memories(
    query: str,
    project: str | None,
) -> list[Memory]
```

内部使用 Vexor。

MCP Tool 不知道 Vexor 存在。

以后替换 Search Engine：

```text
Vexor
↓
其他 Search Engine
```

MCP Protocol 不变化。

---

# 27. Memory Index

Index 不需要单独存储。

每次：

```text
memory(action=query)
```

可以直接扫描：

```text
global/*.md

projects/*
```

读取 Frontmatter：

```text
title
```

就能生成。

因为这里只读取几十或几百个很小的 Markdown Header，性能完全足够。

不需要数据库 Cache。

---

# 28. Project 参数

MCP Tool 提供：

```text
project
```

但它只是上下文，不属于 Memory Schema。

例如：

```json
{
  "action": "query",
  "project": "vexor"
}
```

Project Slug 统一：

```text
lowercase
kebab-case
```

允许：

```text
[a-z0-9._-]
```

禁止：

```text
/
\
..
```

避免 Path Traversal。

---

# 29. Write 示例

Global：

```json
{
  "action": "write",
  "title": "AI 协作偏好",
  "body": "希望 AI 主动完成明确任务，并解释真正重要的设计决策。"
}
```

服务器写：

```text
global/<id>.md
```

---

Project：

```json
{
  "action": "write",
  "project": "vexor",
  "title": "API 兼容性原则",
  "body": "修改公开 API 时应优先考虑向后兼容。"
}
```

服务器写：

```text
projects/vexor/<id>.md
```

---

# 30. Query 示例

读取 Index：

```json
{
  "action": "query",
  "project": "vexor"
}
```

搜索：

```json
{
  "action": "query",
  "project": "vexor",
  "query": "API 修改时以前有什么原则？"
}
```

---

# 31. Agent Integration Policy

每个客户端只需要增加很短的长期规则。

建议语义：

```text
A shared permanent memory service is available.

At the beginning of a new session, query the memory index once.

Do not load permanent memories automatically.

When past information could materially affect the current task,
query permanent memory before guessing.

Write information only when it is expected to remain useful across
future sessions or AI agents.

Do not write temporary task state, transient conversation details,
credentials, secrets, or information that is already obvious from
the current repository.

Before updating an existing memory topic, query its current content
and write back the complete desired body.

Current user instructions always override permanent memory.
```

核心行为：

```text
Session Start
↓
Memory Index

需要历史
↓
Query

产生长期信息
↓
Write
```

---

# 32. Native AI Memory 的定位

各平台自带 Memory 保持开启即可。

职责：

```text
Native Memory
=
platform-local cache
```

Shared Memory：

```text
Shared Memory
=
cross-agent permanent source
```

优先级：

```text
当前用户明确指令

↓

Shared Permanent Memory

↓

Native AI Memory

↓

Agent 推测
```

如果发生冲突：

当前用户指令最高。

---

# 33. 什么应该进入 Permanent Memory

应该：

```text
长期个人偏好

稳定工作方式

重要项目设计决策

项目历史原因

长期约束

被明确否决的重要方案

未来其他 Agent 会需要知道的信息
```

---

# 34. 什么不应该进入 Permanent Memory

不应该：

```text
今天准备做什么

当前 Todo

临时 Debug 状态

当前 Session 的进度

一次性错误

短期计划

完整聊天日志

自动总结的所有内容

密码

API Key

Token

其他 Secrets
```

Permanent Memory 不是：

```text
Conversation Archive
```

也不是：

```text
Daily Journal
```

---

# 35. Memory 更新原则

Memory Body 表示：

> 当前有效状态。

Git History 表示：

> 历史状态。

例如当前：

```text
AI 协作偏好
```

正文只写当前偏好。

不写：

```text
2025 年以前喜欢……
2026 年开始改成……
后来又……
```

历史变化由：

```text
git log
```

负责保存。

这样 Memory 本身保持简洁。

---

# 36. Title 设计建议

Title 应该描述一个稳定 Topic。

好：

```text
AI 协作偏好

Python 开发习惯

API 兼容性原则

配置系统设计

发布工作流
```

不好：

```text
今天聊天提到的东西

关于昨天的问题

Claude 的那个事情

一些注意事项
```

Title 应长期稳定。

这样同一 Topic 才可以持续更新。

---

# 37. Logging

Production 日志不要记录：

```text
memory body
query content
```

只记录：

```text
action=query
source=codex
project=vexor
results=3
latency=...
```

Write 可以记录：

```text
action=write
operation=update
title_hash=...
commit=abc1234
```

如果需要调试，开发模式才允许输出正文。

---

# 38. Failure Model

## Git Write 失败

整个 Write 失败。

返回错误。

---

## Git Commit 失败

Write 失败。

因为：

> Write success = persisted + versioned。

---

## Git Push 失败

Write 仍成功。

Remote 只是 Backup。

---

## Vexor Refresh 失败

Write 仍成功。

因为 Git 是 Truth。

下一次 Query：

```text
HEAD != indexed_commit
```

触发重新索引。

---

## Vexor Query 失败

返回明确错误。

可以在后续版本增加：

```text
ripgrep fallback
```

例如：

```bash
rg -i
```

作为 degraded search mode。

v1 可以先不实现。

---

# 39. Startup Check

服务启动时：

1. 检查 Repository 存在。
2. 检查 `.git`。
3. 检查 Working Tree 状态。
4. 检查 Memory Markdown 格式。
5. 获取 Git HEAD。
6. 检查 Vexor Index。
7. 如果索引落后，Refresh。
8. 启动 MCP Server。

如果 Working Tree 存在未知未提交修改：

推荐：

```text
Query 可以继续

Write 暂停
```

避免服务覆盖人工修改。

---

# 40. Markdown Validation

Frontmatter 必须包含：

```text
id
title
source
created_at
updated_at
```

Body：

```text
允许任意 Markdown
```

限制建议：

```text
title <= 120 chars

body <= 20,000 chars
```

Project：

```text
<= 64 chars
```

---

# 41. Security Requirements

必须：

- HTTPS
- Bearer Token
- 每 Agent 独立 Token
- Private Git Repository
- Server 使用非 root 用户
- Repository 权限限制
- 禁止 Path Traversal
- Git 命令使用参数数组
- 禁止 Shell String Interpolation
- 日志默认不记录 Memory Content
- Token 不进入 Git Repository

推荐：

```text
chmod 700 memory repo
```

---

# 42. Git Credentials

远程 Repository 推荐：

```text
SSH Deploy Key
```

不要：

```text
个人 GitHub Password
```

Server 只需要：

```text
read/write repository
```

权限。

---

# 43. 数据可迁移性

系统最重要的长期属性之一：

即使整个 Memory Server 消失：

```text
git clone memory-repo
```

仍然可以得到：

```text
普通 Markdown
```

任何人或 AI 都可以读取。

没有：

- Proprietary DB
- Binary Index
- Vendor Lock-in
- Memory Export Format

Vexor Index 可以重新生成。

---

# 44. 第一版明确不做

v1 不实现：

- 多用户
- 用户注册
- OAuth
- Dashboard
- Web UI
- Graph Memory
- 自动 Memory Extraction
- 自动分类
- 自动 Importance
- LLM Memory Merge
- AI 自动写所有对话
- Delete MCP Tool
- Memory TTL
- Daily Memory
- Relationships
- Tags
- Complex Scope Tree
- Database
- Embedding Storage
- Multiple Search Engines
- Distributed Writer
- Git Conflict Resolution
- Remote Repository Concurrent Editing
- Analytics

这些功能只有出现真实需求后才考虑。

---

# 45. MVP Functional Requirements

## FR-001

系统必须通过 HTTPS MCP 提供服务。

## FR-002

系统必须只暴露一个 MCP Tool：

```text
memory
```

## FR-003

Tool 必须支持：

```text
query
write
```

## FR-004

无 query 的 query 操作必须返回 Memory Index。

## FR-005

有 query 的 query 操作必须通过 Vexor 搜索 Memory。

## FR-006

Write 必须支持 Global Scope。

## FR-007

Write 必须支持 Project Scope。

## FR-008

同 Scope + 同 Normalized Title 必须执行 Update。

## FR-009

新 Title 必须创建 Memory。

## FR-010

每个 Write 必须产生 Git Commit。

## FR-011

每个 Memory 必须记录 source。

## FR-012

source 必须从 Authentication Identity 获得。

## FR-013

Vexor Index 必须能够从 Git Repository 重建。

## FR-014

Remote Git Push 失败不能导致 Memory Write 失败。

## FR-015

系统必须支持多个 AI Agent 使用不同 Token 访问同一 Memory Repository。

---

# 46. Non-Functional Requirements

## Simplicity

核心服务必须可以在一个普通 VPS 上运行。

不依赖外部数据库。

---

## Durability

返回 Write Success 时：

```text
Markdown 已落盘

且

Git Commit 已完成
```

---

## Recoverability

删除所有 Runtime Data 和 Vexor Index 后：

只使用 Git Repository 必须可以恢复完整 Memory Service。

---

## Human Readability

任何 Memory 不使用专用工具也必须可以直接阅读。

---

## Portability

Memory Repository 不依赖 Server Implementation。

---

## Privacy

Memory Content 不进入普通日志。

---

# 47. Testing Plan

## Unit Tests

必须覆盖：

```text
title normalization

project normalization

path validation

frontmatter parsing

frontmatter writing

scope resolution

auth token → source

create memory

update memory

created_at preservation

updated_at update
```

---

## Git Tests

覆盖：

```text
create → commit

update → commit

commit message

dirty working tree

push failure

repository recovery
```

测试使用临时 Git Repository。

---

## Search Tests

覆盖：

```text
Vexor index build

query global

query project

global + project filtering

index stale detection

reindex
```

---

## MCP Tests

覆盖：

```text
unauthorized request

invalid action

query index

query search

write global

write project

write update
```

---

## Concurrency Tests

两个 Agent 同时 Write：

```text
Writer A
Writer B
```

验证：

```text
没有损坏 Markdown

没有丢 Git Commit

没有 Repository Dirty State
```

---

# 48. End-to-End Acceptance Test

初始：

```text
Repository Empty
```

Claude：

```text
memory(
  action="write",
  title="AI 协作偏好",
  body="希望 AI 主动完成明确任务。"
)
```

验证：

```text
global/<id>.md
```

存在。

Git：

```text
1 commit
```

---

Codex：

```text
memory(
  action="query"
)
```

必须看到：

```text
AI 协作偏好
```

---

Codex：

```text
memory(
  action="query",
  query="用户希望 Agent 怎么工作？"
)
```

必须得到 Claude 写入的 Memory。

---

ChatGPT：

```text
memory(
  action="write",
  title="AI 协作偏好",
  body="希望 AI 主动完成明确任务，并解释重要设计决策。"
)
```

验证：

```text
同一个 Memory ID

created_at 不变

updated_at 改变

source = chatgpt
```

Git：

```text
新增 update commit
```

这就是核心跨 Agent Use Case。

---

# 49. 开发阶段

## Milestone 0 — Storage Prototype

完成：

```text
Markdown schema
Git repo
create
update
list index
```

暂时不做 MCP。

目标：

验证 Git + Markdown 作为 Memory Store 的体验。

---

## Milestone 1 — Vexor Integration

完成：

```text
index
query
scope filter
reindex
```

目标：

可以通过自然语言搜索 Memory。

---

## Milestone 2 — MCP

实现：

```text
memory
```

支持：

```text
query
write
```

Transport：

```text
Streamable HTTP
```

---

## Milestone 3 — Authentication

增加：

```text
Bearer Token
token → source
```

为：

```text
Claude
Codex
ChatGPT
Cursor
```

分别配置 Token。

---

## Milestone 4 — Git Remote

增加：

```text
Private Remote Repository
SSH Deploy Key
best-effort push
```

完成灾难恢复验证。

---

## Milestone 5 — Client Policy

分别给：

```text
Claude Code
Codex
ChatGPT
Cursor
```

增加相同的 Memory Usage Policy。

验证真正的跨 Agent 体验。

---

# 50. 第一版成功标准

只要做到下面这个流程顺畅，项目就已经成功：

```text
Claude
 ↓
写了一条永久记忆
 ↓
Git Commit

第二天

Codex
 ↓
Session 开始读取 Memory Index
 ↓
看到相关 Topic
 ↓
任务进行到需要历史时
 ↓
query
 ↓
Vexor 找到 Claude 的 Memory
 ↓
Codex 继续工作
```

然后：

```text
Codex
 ↓
更新了一条长期信息
 ↓
write
 ↓
Git 保存新版本

ChatGPT
 ↓
之后可以读到最新版本
```

这就是整个产品最重要的闭环。

---

# 51. 最终架构

```text
                  Claude Code
                       │
                  Bearer Token
                       │
                       ▼
                    HTTPS
                       │
                       │
Codex ────────────► Memory MCP ◄──────────── ChatGPT
                       │
                       │
                 one tool only
                    memory
                 /           \
             query             write
               │                 │
               ▼                 ▼
             Vexor          Markdown Store
               │                 │
               │                 ▼
               │               Git
               │                 │
               └──── read ◄──────┘
                                 │
                                 ▼
                         Private Git Remote
                             Backup Only
```

系统的本质可以概括为：

> **Permanent memory is a versioned collection of named Markdown notes.**

> **Git stores memory. Vexor retrieves memory. MCP exposes memory.**

模型只需要知道：

> **Recall when necessary. Remember when durable.**

其余一切留在服务内部。