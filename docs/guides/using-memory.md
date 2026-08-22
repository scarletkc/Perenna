# Using Permanent Memory

Perenna treats a memory as a named long-term note, not as an automatically
extracted fact or a transcript. Use it when information should remain useful
across future sessions or clients.

The examples below show MCP arguments. The complete validation contract is in
the [MCP API reference](../reference/mcp-api.md).

## Read the lightweight index

At the beginning of a session, query without search text:

```json
{
  "action": "query"
}
```

This returns global memory titles and the available project names. It does not
load every body.

When the current project is known, include its slug:

```json
{
  "action": "query",
  "project": "perenna"
}
```

The result contains global titles plus titles for that project.

## Recall full memories

Provide natural-language search text when past information could affect the
current task:

```json
{
  "action": "query",
  "query": "What constraints govern memory writes?",
  "project": "perenna"
}
```

With a project, retrieval is limited to global memories and that project.
Without a project, every scope is searchable. Perenna returns at most five full
memories.

## Write a global memory

Use a stable topic title and a complete current body:

```json
{
  "action": "write",
  "title": "AI collaboration preferences",
  "body": "Complete clear tasks autonomously. Explain decisions that materially affect architecture or risk."
}
```

Global memories are appropriate for preferences and constraints that apply
across repositories.

## Write a project memory

Include a project slug for repository-specific information:

```json
{
  "action": "write",
  "project": "perenna",
  "title": "Storage authority",
  "body": "Committed Markdown is authoritative. The Vexor collection is rebuildable cache data."
}
```

## Update an existing topic

Within one scope, a normalized title is the update key. To update safely:

1. Recall the current memory.
2. Edit it into the complete desired state.
3. Write the whole body using the same title and project.

Perenna preserves the memory ID and creation time, replaces the title and body,
and records the latest source and update time. It does not merge text with an
LLM.

## What belongs in permanent memory

Good candidates include:

- stable personal preferences;
- long-lived project constraints;
- current architectural decisions;
- the reason an important alternative was rejected;
- workflows another agent will need in a later session.

Do not store:

- passwords, API keys, tokens, or other secrets;
- temporary task progress or today's to-do list;
- raw conversation transcripts;
- transient debugging state;
- facts already obvious from the current repository.

The memory body should describe the current valid state. Git history preserves
older states.

## Recommended agent behavior

An agent using Perenna should follow this operating pattern:

```text
Read the memory index once near the start of a new session.
Recall only when past information could materially affect the task.
Write only information that should remain useful across future sessions.
Before updating a topic, recall it and write back the complete desired body.
Never store secrets or temporary conversation state.
Treat current user instructions as higher priority than permanent memory.
```

Perenna intentionally provides no delete action through MCP. Deletion and
historical recovery are user-controlled Git operations described in
[Maintenance and recovery](maintenance.md).
