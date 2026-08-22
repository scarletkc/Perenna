# Using Permanent Memory

Perenna treats a memory as a curated long-term note, not an automatically
extracted fact or transcript. The examples below show MCP arguments; the
complete field contract is in the [MCP API reference](../reference/mcp-api.md).

## Read the lightweight index

Near the start of a session, list global memories and available projects:

```json
{
  "action": "list"
}
```

Call this through `memory_read`. When the current project is known, include its
slug to list global memories plus that project's memories:

```json
{
  "action": "list",
  "project": "perenna"
}
```

Each result includes a stable ID, title, scope, and authoritative coverage
summary without loading the complete body.

## Search ranked candidate passages

Search only when prior information could affect the current task:

```json
{
  "action": "search",
  "query": "What protects a Perenna memory update?",
  "project": "perenna",
  "limit": 3
}
```

`limit` defaults to three and accepts one through five distinct memories. The
response contains ranked bounded passages, not complete bodies. The first
version has no relevance threshold; treat results as candidates and use their
summary and passage to decide whether `get` is warranted.

When `truncated` is true, refine the query rather than increasing context
indiscriminately.

## Get a complete memory

Use the stable ID returned by list or search:

```json
{
  "action": "get",
  "memory_id": "01K35Z9V6Y8X2W4T7R1Q5M3N0P"
}
```

Get returns the authoritative summary, complete body, and current revision from
the committed Git snapshot. Use this path before a whole-memory decision.

## Create a memory

Call `memory_write` with a stable title, a stable one-sentence coverage summary,
and the complete current body:

```json
{
  "action": "create",
  "project": "perenna",
  "title": "Storage authority",
  "summary": "Which Perenna data is authoritative and which data is cache.",
  "body": "Committed Markdown is authoritative. The Vexor collection is rebuildable cache data."
}
```

Use global scope for cross-project preferences and project scope for
repository-specific architecture, workflow, history, and policy.

Good summaries remain valid while details evolve. Avoid a summary such as
`Current implementation uses five search results`; that is a volatile detail,
not the subject the memory covers.

## Patch a local part

Use the ID and revision returned by search or get:

```json
{
  "action": "patch",
  "memory_id": "01K35Z9V6Y8X2W4T7R1Q5M3N0P",
  "base_revision": "<current revision>",
  "edits": [
    {
      "old_text": "The Vexor collection is rebuildable cache data.",
      "new_text": "Vexor chunks and the indexed commit marker are rebuildable cache data."
    }
  ]
}
```

Each old text must occur exactly once. Include more surrounding text when an
anchor repeats. Every edit applies against the same revision, and any failure
rejects the entire patch.

Omit summary when the memory still covers the same subject. When its coverage
changes, provide the complete new summary as another patch field.

## Replace a complete memory

Use replace only when the whole document genuinely needs restructuring:

```json
{
  "action": "replace",
  "memory_id": "01K35Z9V6Y8X2W4T7R1Q5M3N0P",
  "base_revision": "<current revision>",
  "summary": "Which Perenna data is authoritative and which data is cache.",
  "body": "The complete desired replacement body."
}
```

Replace discards every old body character not present in the new body. A
revision prevents stale concurrency but cannot detect accidental omission, so
prefer patch for ordinary changes.

## Delete a complete memory

Call `memory_delete` only when the complete subject should leave current
memory:

```json
{
  "memory_id": "01K35Z9V6Y8X2W4T7R1Q5M3N0P",
  "expected_title": "Storage authority",
  "base_revision": "<current revision>"
}
```

Deletion remains recoverable from Git history. It does not purge sensitive data
from commits or remote backups.

## What belongs in permanent memory

Good candidates include stable preferences, long-lived project constraints,
current architectural decisions, and workflows another agent will need later.

Do not store passwords, API keys, tokens, raw transcripts, temporary progress,
transient debugging state, or facts already obvious from the current
repository.

Current user instructions always override permanent memory.
