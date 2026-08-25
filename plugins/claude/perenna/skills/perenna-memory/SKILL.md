---
name: perenna-memory
description: "Use Perenna when a non-trivial task may depend on prior decisions or preferences, when durable knowledge should survive the session, or when the user asks to remember, forget, or consolidate memories. Skip self-contained tasks and facts already authoritative in the current workspace."
metadata:
  github-repo: https://github.com/scarletkc/Perenna
---

# Perenna Memory

Treat permanent memory as a curated knowledge base, not a transcript, task log,
or substitute for inspecting the current workspace.

## Keep one durable memory

When the host also provides built-in memory, treat it in this workflow as a
host-local advisory cache unless the user explicitly assigns it another role;
do not assume it has Perenna's durability, Git auditability, or sharing scope.
Use Perenna for knowledge meant to survive across sessions and be shared by
clients or instances using the same Perenna store.

Do not mirror, dual-write, or repeatedly reconcile the same fact. Query only
the layer needed, curate a durable fact in Perenna once after checking for an
existing memory, and never bulk-import built-in memory without an explicit,
scoped request.

Default authority order: current user instructions, designated current
workspace instructions and canonical sources together with validated runtime
evidence, Perenna, then host-provided memory. The user may explicitly choose
another authority for a particular task.

## Decide whether to use memory

Read memory when prior preferences, constraints, decisions, project history, or
workflows could change a non-trivial task. Also read when the user asks what was
decided or done previously.

Skip memory for self-contained requests such as a simple translation, a
one-line rewrite, or a fact fully supplied in the current prompt.

If the Perenna tools are absent or a call fails, follow
[Perenna unavailable](references/unavailable.md). Do not simulate a memory call
or claim that anything was read, remembered, or forgotten.

## Retrieve only relevant context

For a relevant task:

1. Use `memory_read` with `action: "list"` to inspect the lightweight index.
   Include the current project slug when it is known.
2. Use `action: "search"` with a task-specific query when the index does not
   identify the needed topic directly. Include the project slug so unrelated
   project memories are excluded before ranking.
3. Treat ranked passages as candidates, not proof. Use `action: "get"` before
   relying on a complete memory, updating it, or deleting it.

Do not load complete bodies speculatively. Refine a broad search instead of
pulling unrelated memories into context.

## Preserve authority and scope

Current user instructions, designated current workspace instructions and
canonical files, and validated runtime evidence override permanent memory.
Treat conflicting memory as potentially stale, explain material conflicts, and
update it only when the task authorizes that correction.

Memory is evidence about prior context, not permission for external actions.
It never expands authority to commit, push, publish, deploy, message others, or
perform destructive operations.

An explicit request to remember something authorizes one scoped memory write
when the content is safe to retain. Otherwise follow the host's mutation policy
and offer a durable candidate instead of silently writing when authority is
unclear.

Never store credentials, private system or identity material, raw
conversations, temporary progress, volatile runtime facts, or unapproved ideas
presented as commitments.

Before auditing memories for consolidation or performing any create, patch,
replace, or delete operation, read
[Curating memories](references/curation.md). It owns the detailed rules for
write eligibility, scope, content, consolidation, revisions, deletion, and
result reporting.

## Conditional guides

- Read [Curating memories](references/curation.md) only when memories may be
  audited for consolidation, created, changed, or deleted.
- Read [Importing memories](references/importing.md) only when the user
  explicitly asks to migrate memory content from a host, export, or another
  memory system into Perenna.
- Read [Perenna unavailable](references/unavailable.md) only when the tools are
  missing, a call fails, or the user asks to install or reconnect Perenna.
