# Memory Model

Perenna models permanent memory as a versioned collection of named Markdown
notes.

## A memory is a named note

A memory has a stable topic title and a complete body. It may hold several
closely related statements when they form one durable subject.

Good topic boundaries:

- `AI collaboration preferences`
- `Release workflow`
- `Storage authority`
- `API compatibility policy`

Poor topic boundaries:

- `Something from yesterday`
- `Current debugging status`
- one file per tiny fact that belongs to the same long-term subject.

Perenna is not an atomic fact database, conversation archive, daily journal,
or task tracker.

## Scopes

Perenna supports two scope forms:

- `global` applies across projects;
- `project:<slug>` applies to one project.

Scope comes from the memory path and is not stored in frontmatter. Global and
project memories may share a title because title uniqueness is evaluated
within one scope.

Use global scope for cross-project preferences and constraints. Use project
scope for repository-specific architecture, workflow, history, and policy.

## Title identity and upsert

The normalized title is the topic identity inside a scope. A write performs an
upsert:

```text
No matching normalized title  → create a new memory and ULID
Matching normalized title     → update the existing memory
```

An update keeps the ID and creation time. It replaces the normalized title and
complete body, then records the latest source and update time.

The exact normalization algorithm and size limits are defined in the
[memory file format](../reference/memory-format.md).

## Current state and history

The body represents the current valid state of the topic. It should not become
a hand-written changelog.

```text
Memory body  = current state
Git history  = previous states
```

This keeps recalled content concise while preserving every older version for
audit and recovery.

## Source attribution

Every memory records the host that most recently wrote it. The host injects
`source` when it starts Perenna, so the model cannot claim another source in a
tool call. Earlier sources remain visible in Git history.

## Two query modes

The same MCP action provides two different read behaviors:

- no query text returns a lightweight topic index;
- non-empty query text performs semantic recall and returns full memories.

Project recall searches global memories plus the selected project. Recall
without a project searches every scope.

## No MCP deletion

The `memory` tool has no delete action. An agent can replace an outdated topic
with its current state. A user can delete a file through Git when true removal
is necessary, while older content remains recoverable from history.

For practical examples, see
[Using permanent memory](../guides/using-memory.md).
