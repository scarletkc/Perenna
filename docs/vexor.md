# Vexor 配置与隐私

本文是 Perenna 如何使用 Vexor、如何选择 embedding provider，以及哪些数据会离开
本机的唯一规范。通用 provider 字段和命令以
[Vexor Configuration](https://github.com/scarletkc/vexor/blob/main/docs/configuration.md)
为准；Perenna 不维护第二份 Vexor 配置格式。

## Perenna 的 Vexor 契约

Perenna 使用 `vexor>=0.28,<0.29` 的 Collections API：

```text
collection name: perenna-memories
record id:       Memory ULID
record text:     normalized title + body
metadata:        scope + trusted relative path
```

Scope metadata 使用：

```text
global
project:<slug>
```

Project recall 在 Vexor 打分前应用：

```text
scope in [global, project:<slug>]
```

Vexor 返回的 record ID 和 path 只是候选信息。Perenna 仍从 Git HEAD 解析可信路径并
读取原始 Markdown，不能让 collection metadata 指向 Memory repository 外部。

## Cache 位置与一致性

Perenna 把 Vexor collection cache 固定在解析后的 `<home>/index/`，不在 Memory
repository 或调用方项目中创建 Vexor index。该目录包含可重建数据和
`indexed_commit`；删除它不会删除永久记忆。

下列任一情况触发从 Git HEAD 全量重建：

- `indexed_commit` 与 HEAD 不一致；
- collection 不存在；
- index 目录被删除。

一次 write 后，如果旧索引与写入前 HEAD 对齐，Perenna 只 upsert 当前 Memory，并
把 marker 推进到新的 HEAD。Rebuild 或增量更新失败时 marker 不前移，已完成的 Git
commit 不回滚。

## 配置来源

Provider 与 model 遵循 Vexor 的用户配置和环境变量：

- 用户配置：`~/.vexor/config.json`；
- 非密钥覆盖：`VEXOR_CONFIG_JSON`；
- 通用 provider 密钥：`VEXOR_API_KEY`；
- Vexor 支持的 provider-specific 密钥：`OPENAI_API_KEY`、
  `GOOGLE_GENAI_API_KEY`、`VOYAGE_API_KEY`。

`VEXOR_CONFIG_JSON` 只用于非密钥字段；不要把 API key 放入 JSON、MCP 配置文件或
Git repository。需要把配置传给 Perenna 时，由启动它的 MCP client 设置相应环境
变量。

完整字段、有效优先级和 provider-specific 行为属于 Vexor 自身契约，请查看上面的
Vexor Configuration 链接。Perenna 的 `--home` 不会改变 Vexor 用户配置文件的
位置，只会改变 Perenna 的 Memory 与 index 位置。

## 远程 provider 的数据边界

选择 `openai`、`gemini`、`voyageai`、`custom` 或其他远程 embedding provider 时，
provider 会接收到需要向量化的文本。对 Perenna 而言，这包括：

- 每条 Memory 的 title 与 body，用于写入或重建向量；
- recall 的 query，用于生成查询向量。

Git repository 和 Markdown 文件仍存放在本机，但“本地存储”不等于“内容不会离开
本机”。在写入敏感记忆前，应确认所选 provider 的数据处理条款和 endpoint。

Perenna 日志不会记录 body、query 或 API key；这项日志约束不能阻止内容按 provider
配置发送给远程 embedding 服务。

## 远程 provider 示例

非密钥配置可以通过宿主环境传入：

```text
VEXOR_CONFIG_JSON={"provider":"openai","model":"text-embedding-3-small"}
VEXOR_API_KEY=<provider-key>
```

使用 OpenAI-compatible endpoint 时，根据 Vexor 配置规范选择 `custom` 并设置
`base_url` 与 `model`。Perenna 不验证第三方 endpoint 的身份或隐私属性。

## 本地 provider

从源码安装 Perenna 的 local extra：

```bash
uv tool install '.[local]'
```

然后通过 Vexor 用户配置或宿主环境选择本地 provider，例如：

```text
VEXOR_CONFIG_JSON={"provider":"local","model":"intfloat/multilingual-e5-small"}
```

本地 provider 在本机计算 embedding，不需要把 title、body 或 query 发送给远程
embedding API。但 local extra 不承诺完全离线：首次安装依赖或取得模型文件仍可能
需要网络，且用户配置的其他工具或 Git remote 仍可能访问网络。

## 更换 provider、model 或维度

Vexor collection 的 provider、model 与 vector dimension 在首次成功写入时固定。
更改这些值后，不应继续复用旧向量。

安全切换流程：

1. 停止使用同一 Perenna home 的进程；
2. 更新 Vexor 用户配置或 MCP client 环境变量；
3. 按 [恢复与人工维护](recovery.md#重建-vexor-index) 移走旧 index；
4. 启动 Perenna 并执行 recall，使用新 contract 从 Git HEAD 完整重建；
5. 验证结果后再删除旧 cache 备份。

不要手工修改 `collections.db` 或 `indexed_commit` 来伪装兼容。

## 故障语义

- write 已 commit、embedding 失败：Memory 写入成功，index 保持落后；
- recall embedding 或 search 失败：返回明确索引错误，不回退到未定义的文本搜索；
- 下一次 recall：重新检查并继续尝试恢复；
- 删除整个 index：下一次 recall 从 Git HEAD 重建。

真实 provider smoke test 必须单独标记，不进入默认离线测试；默认测试使用 fake 或
受控的 Vexor boundary，不依赖外部 API key 或网络。
