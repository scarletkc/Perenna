# 恢复与人工维护

本文是 Perenna 本地数据初始化、故障恢复和人工 Git 操作的唯一 runbook。所有恢复
都以 `memory/` Git repository 为准；`index/` 永远不能反向覆盖 Memory。

CLI 配置优先级见
[Local-first 架构与需求](跨%20Agent%20永久记忆服务：架构与需求设计方案.md#3-本地目录与启动配置)。
下文用 `<home>` 表示解析后的 Perenna home，用 `<memory-repository>` 表示
`<home>/memory`。

## 首次初始化

Perenna 在启动时检查 `<home>/memory`：

| 当前状态 | 行为 |
| --- | --- |
| 路径不存在 | 创建目录并初始化 `main` 分支 Git repository |
| 目录为空 | 在原目录初始化 `main` 分支 Git repository |
| 非空且为有效 Git repository | 保留并使用 |
| 非空但不是有效 Git repository | 拒绝启动，不覆盖任何文件 |

新 repository 使用 repo-local 的 Perenna commit identity，不修改用户的 global
Git identity。`<home>/index` 不存在时自动创建。

遇到非空非 Git 目录时，选择其中一种恢复方式：

1. 检查并把现有目录移动到备份位置，再重新启动；
2. 使用 `--home <new-path>` 选择一个空目录；
3. 如果现有内容本来就是 Memory 数据，由用户确认格式后自行初始化和 commit。

Perenna 不自动删除、移动或接管这个目录。

## Working tree dirty

Write 报告 repository 有未提交修改时，先检查：

```bash
git -C <memory-repository> status --short
git -C <memory-repository> diff
git -C <memory-repository> diff --cached
```

然后由用户明确选择：

- 修改有效：按 [Markdown 记忆格式](memory-format.md) 校验后自行 commit；
- 修改需要保留但暂不生效：用 Git stash 或移动到 repository 外；
- 修改不需要：用合适的 Git restore 操作恢复具体文件。

不要为了恢复 Perenna 执行面向整个 repository 的强制 reset。Working tree 恢复
干净后，下一次 write 正常继续；在此之前 query 始终读取 HEAD，而不是人工修改。

## 查看历史

常用的只读检查：

```bash
git -C <memory-repository> log --oneline --decorate
git -C <memory-repository> show <commit>
git -C <memory-repository> log -- <relative-memory-path>
```

Perenna 的一次 write 对应一个只包含目标 Memory 的 commit，因此可以按文件追踪
完整变化。

## 恢复旧版本

优先使用会留下新历史的 Git 操作：

```bash
git -C <memory-repository> revert <commit>
```

如果只恢复某个文件，先从目标 commit 取回该文件，检查格式，再自行 commit。任何
人工 commit 都会改变 HEAD；下一次 recall 会发现 `indexed_commit` 不一致并从
新的已提交快照重建索引。

Perenna 没有 MCP delete action。需要删除 Memory 时，用户删除目标文件并创建
Git commit；Git history 仍保留旧内容。

## 重建 Vexor index

下列情况不需要修复 Memory repository：

- `<home>/index` 被删除；
- `indexed_commit` 缺失或与 HEAD 不一致；
- Vexor collection 缺失或损坏；
- provider/model 配置改变，需要生成新的 embedding。

恢复步骤：

1. 关闭会使用同一 `<home>` 的 Perenna 进程；
2. 将 `<home>/index` 重命名到 repository 外作为临时备份，或删除该 cache；
3. 重新启动 Perenna 并执行一次带 `query` 的 recall；
4. 确认 recall 成功，且新的 `indexed_commit` 等于 Memory Git HEAD；
5. 不再需要时再删除临时备份。

Rebuild 只读取 Git HEAD。Working tree 中未提交的文件不会进入新索引。具体 collection
契约见 [Vexor 配置与隐私](vexor.md)。

## Vexor provider 或索引失败

如果 write 已创建 Git commit，但 stderr 报告 Vexor 失败：

1. 把 write 视为已成功持久化，不要重复写相同正文来“补救”；
2. 检查有效的 Vexor provider、model 和 API key；
3. 修复配置后再次 recall；
4. 若 collection 的 embedding contract 已改变，按上一节重建 index。

Marker 只在索引完整对齐 HEAD 后更新。失败后下一次 recall 会继续尝试，不需要人工
编辑 `indexed_commit`。

## Git commit 失败

Perenna 在 commit 失败时自动恢复本次目标文件和 Git index。收到失败结果后检查：

```bash
git -C <memory-repository> status --short
git -C <memory-repository> log -1 --oneline
```

Repository 应回到调用前状态。若仍然 dirty，停止新的 write 并保留现场；检查文件
权限、磁盘空间、Git hook 与 stderr 中的脱敏错误，再人工处理。

## Remote 备份失败

Remote push 不在 write 成功事务内。凭据、网络或超时失败时，本地 commit 仍是完整
的 Source of Truth。Perenna 不自动 pull、fetch 或解决远程分叉。

先检查：

```bash
git -C <memory-repository> remote -v
git -C <memory-repository> status --branch --short
```

确认 remote 与分支关系后，可以由用户手动 push。若远程已有非快进提交，不要强制
覆盖；先备份本地 repository，再由用户决定如何处理历史。自动 remote 的选择与
禁用规则见
[Local-first 架构与需求](跨%20Agent%20永久记忆服务：架构与需求设计方案.md#3-本地目录与启动配置)。

## 完整灾难恢复

只要仍有 Memory Git repository，就不需要保存旧 index：

1. 将 repository clone 或复制到新的 `<home>/memory`；
2. 确认默认工作分支已 checkout，working tree 干净；
3. 按 [Markdown 记忆格式](memory-format.md) 检查已提交文件；
4. 保持 `<home>/index` 不存在；
5. 配置可用的 Vexor provider；
6. 启动 Perenna 并执行 recall，触发完整 rebuild。

恢复验收以 Git commit 数量、Memory 内容和 recall 结果为准，不以旧 cache 是否保留
为准。
