# Markdown 记忆格式

本文是 Perenna Memory 文件布局与内容校验的唯一规范。运行流程与并发边界见
[Local-first 架构与需求](跨%20Agent%20永久记忆服务：架构与需求设计方案.md)，
异常数据的处理见 [恢复与人工维护](recovery.md)。

## 路径与 scope

每条 Memory 都是一个以 ULID 命名的 Markdown 文件：

```text
memory/
├── global/
│   └── <ULID>.md
└── projects/
    └── <project-slug>/
        └── <ULID>.md
```

Scope 只由可信相对路径决定：

| 相对路径 | scope |
| --- | --- |
| `global/<ULID>.md` | `global` |
| `projects/<slug>/<ULID>.md` | `project:<slug>` |

Scope 不写入 frontmatter。文件名 stem 必须与 frontmatter 的 `id` 完全相同；同一个
repository 中的 ID 必须唯一。Title 不能用作文件名。

## 文件结构

文件必须由 YAML frontmatter、一个空行和 Markdown body 组成：

```markdown
---
id: "01K35Z9V6Y8X2W4T7R1Q5M3N0P"
title: "AI 协作偏好"
source: "claude-code"
created_at: "2026-08-22T07:10:00.000000Z"
updated_at: "2026-08-22T07:10:00.000000Z"
---

希望 AI 在明确任务中主动完成工作。

重要设计决策需要说明原因。
```

Frontmatter 只允许以下五个字段，不能缺少、重复或增加字段；五个值都必须解析为
string，Perenna 写入时统一使用 YAML quoted string：

```text
id
title
source
created_at
updated_at
```

字段含义：

- `id`：Perenna 生成的稳定 ULID；更新时保持不变；
- `title`：长期主题名称，也是同 scope 的 upsert key；
- `source`：最后一次写入该版本的宿主标识；
- `created_at`：Perenna 生成的 UTC RFC 3339 时间；更新时保持不变；
- `updated_at`：Perenna 生成的 UTC RFC 3339 时间；每次更新时重写。

Body 是 frontmatter 结束后的完整 Markdown。Perenna 不解析其语义，也不做自动
merge。

## Title 规范

写入前按顺序处理 title：

1. Unicode NFKC normalization；
2. 清理首尾空白；
3. 将连续空白折叠成一个普通空格；
4. 结果必须非空。

Normalized title 最长 120 个 Unicode 字符。
Title 不能包含控制字符或无效的 Unicode surrogate。

存入文件的是上述 normalized title。唯一性比较还要对它执行 Unicode casefold：

```text
unique key = (scope, normalized_title.casefold())
```

因此同一个 scope 中，大小写或兼容字符不同但归一后相同的 title 必须 upsert 同一
条 Memory；global 与不同 project 之间可以使用相同 title。

## Project slug 规范

Project 输入先转为小写，再校验：

- 长度为 1 到 64 个字符；
- 只允许 ASCII `a-z`、`0-9`、`.`、`_`、`-`；
- 禁止 `/`、`\` 和 `..`；
- 结果必须是一个目录名，不能解析为当前目录、上级目录或绝对路径。
- 为保证跨平台一致，禁止尾点及 Windows 设备名（如 `con`、`nul`、`com1`）。

Project 只是调用上下文和目录 scope，不写入 Memory frontmatter。

## Source 规范

Source 由宿主配置，不来自 MCP tool 参数。写入 frontmatter 前执行 Unicode NFKC
normalization 并清理首尾空白，结果必须：

- 长度为 1 到 64 个字符；
- 首字符是 ASCII 字母或数字；
- 后续字符只使用 ASCII 字母、数字、`.`、`_`、`-`。

Source 保留大小写；不同宿主应使用稳定标识，例如 `claude-code`、`codex`、
`cursor`。

## Body 规范

Body 必须：

- 是非空字符串；
- 将 CRLF 和 CR 统一为 LF；
- 移除首尾换行符，但保留 Markdown 中有意义的其它空格；
- 忽略空白检查后仍含非空白字符；
- 不含 NUL、其它非 Markdown 控制字符或无效的 Unicode surrogate；
- 最长 20,000 个 Unicode 字符。

Perenna 保存完整 body，不截断、不摘要。Title 与 body 的组合是发送给 Vexor 的
searchable text；选择远程 provider 时的数据边界见
[Vexor 配置与隐私](vexor.md)。

## Upsert 后的字段变化

同 scope 的 normalized title 已存在时，Perenna 更新原文件：

| 字段 | Create | Update |
| --- | --- | --- |
| `id` | 新建 ULID | 保持 |
| `title` | 写入 normalized title | 写入 normalized title |
| `source` | 当前宿主 | 当前宿主 |
| `created_at` | 当前时间 | 保持 |
| `updated_at` | 当前时间 | 当前时间 |
| body | 完整写入 | 完整替换 |

Update 不创建新 ID，也不在正文中保留旧版本；历史内容由 Git history 保存。

## Repository 完整性

以下情况表示已提交快照损坏，不能静默跳过：

- 路径不符合两种允许的布局；
- frontmatter 缺少字段、含未知字段或类型错误；
- 文件名与 `id` 不一致；
- ID 重复；
- 同 scope 存在重复 normalized title；
- 时间戳不是带时区的 RFC 3339；
- project、title 或 body 不符合本页规范。

Perenna 必须返回包含可信相对路径的明确错误，不能在日志中打印 body。用户修复并
commit 后，下一次 query 会按新 HEAD 重建索引。

## 人工编辑规则

可以用普通编辑器修改 Memory，但 Perenna 不读取 working tree 中未提交的版本。
人工编辑应遵守本页格式，且由用户自行创建 Git commit。Working tree dirty 期间：

- query 继续读取最后一个 commit；
- write 暂停；
- Perenna 不自动 stage 人工文件。

处理步骤见 [恢复与人工维护](recovery.md)。
