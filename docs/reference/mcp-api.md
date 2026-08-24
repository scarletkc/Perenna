# MCP API Reference

Perenna exposes the same three MCP tools over local stdio and authenticated
Streamable HTTP. All successful calls return structured content plus a short
text summary. Unknown fields, explicit `null` values, and fields belonging to
another action are rejected.

Remote HTTP advertises OAuth in each tool's MCP metadata and enforces one
scope per tool: `memory:read`, `memory:write`, or `memory:delete`. Missing,
invalid, or insufficient credentials fail before the core operation. Local
stdio does not attach OAuth metadata or require a token.

## `memory_read`

`memory_read` has three actions.

| Action | Required | Optional |
| --- | --- | --- |
| `list` | `action` | `project` |
| `search` | `action`, `query` | `project`, `limit` |
| `get` | `action`, `memory_id` | none |

### List

```json
{
  "action": "list",
  "project": "perenna"
}
```

Without `project`, list returns global memory references and the available
project slugs. With `project`, it returns global references plus references in
that project. Each reference contains:

- `memory_id`;
- `title`;
- `scope`;
- `summary`.

The summary is the authoritative stable sentence stored in Markdown, not a
generated preview.

### Search

```json
{
  "action": "search",
  "query": "How should release verification work?",
  "project": "perenna",
  "limit": 3
}
```

`query` must be non-empty. `limit` defaults to `3`, accepts `1` through `5`,
and counts distinct memories after chunk results are aggregated by memory using
the highest-scoring chunk. It does not control the number of Vexor candidates.

Search returns ranked candidates, not a relevance guarantee. The first version
has no minimum similarity threshold, so an unrelated query may still return
the nearest candidates. Each result contains:

- `memory_id`, `title`, `scope`, and authoritative `summary`;
- opaque per-memory `revision`;
- one-based `rank`;
- bounded `passages`, each with exact text and a zero-based half-open
  `start_char` / `end_char` range in the revision's body.

Perenna fixes the underlying candidate count, passage size, and total passage
character budget. `truncated` is `true` when additional candidates are omitted
by the public limit, internal candidate ceiling, or response character budget.
Refine the query or use `get` when more context is required.

Project filtering happens before scoring. With a project, only `global` and
`project:<slug>` chunks are candidates. Without one, every scope is searchable.

### Get

```json
{
  "action": "get",
  "memory_id": "01K35Z9V6Y8X2W4T7R1Q5M3N0P"
}
```

Get reads one complete memory directly from the committed Git snapshot. It does
not call semantic search. The result contains identity, scope, authoritative
summary, timestamps, complete body, and current revision.

## `memory_write`

`memory_write` has three actions.

| Action | Required | Optional |
| --- | --- | --- |
| `create` | `action`, `title`, `summary`, `body` | `project` |
| `patch` | `action`, `memory_id`, `base_revision`, `edits` | `summary` |
| `replace` | `action`, `memory_id`, `base_revision`, `summary`, `body` | none |

The exact title, summary, body, and project validation rules are owned by the
[memory file format](memory-format.md).

### Create

```json
{
  "action": "create",
  "project": "perenna",
  "title": "Release verification",
  "summary": "Checks required after publishing a Perenna release.",
  "body": "Verify the package, release asset, and registry entry."
}
```

Create assigns a ULID and rejects a different memory that already uses the same
normalized title in the same scope. Retrying the same normalized title,
summary, and body returns the existing memory without creating another commit.

### Patch

```json
{
  "action": "patch",
  "memory_id": "01K35Z9V6Y8X2W4T7R1Q5M3N0P",
  "base_revision": "<revision returned by search or get>",
  "edits": [
    {
      "old_text": "Verify the package.",
      "new_text": "Verify the package and registry entry."
    }
  ]
}
```

Patch preserves every part of the body not named by an edit. Every `old_text`
must be non-empty and occur exactly once in the base body. All edits are
located against the same base revision, their ranges cannot overlap, and the
entire patch succeeds or fails as one operation. Perenna never applies edits
fuzzily or partially.

The optional `summary` is a complete replacement summary. Omit it when the
memory still covers the same subject; provide it only when the covered subject
changes. Perenna does not generate a summary.

Insertion can replace an exact anchor with the anchor plus new text. Deletion
can replace exact text with an empty string, provided the resulting body remains
valid. There is no append action.

### Replace

```json
{
  "action": "replace",
  "memory_id": "01K35Z9V6Y8X2W4T7R1Q5M3N0P",
  "base_revision": "<current revision>",
  "summary": "Checks required after publishing a Perenna release.",
  "body": "The complete desired body."
}
```

Replace intentionally overwrites the complete summary and body while
preserving the memory ID, title, scope, and creation time. Use patch for normal
local edits. A matching `base_revision` prevents stale writes but cannot detect
an accidentally incomplete replacement body.

## `memory_delete`

```json
{
  "memory_id": "01K35Z9V6Y8X2W4T7R1Q5M3N0P",
  "expected_title": "Release verification",
  "base_revision": "<current revision>"
}
```

Delete accepts no action field and removes exactly one current memory. The ID,
normalized expected title, and revision must all match. It cannot delete by
query, project, or batch.

Deletion removes the memory from the current Git tree and retrieval index but
does not erase local or synchronized remote Git history. The result marks it as
`recoverable_via_git`. Sensitive-data purging remains a separate manual Git and
remote operation.

## Revisions and mutation results

Revision is an opaque digest of one canonical memory document, including its
summary. Clients must pass back the exact value returned by search or get and
must not derive it from repository HEAD: an unrelated memory commit does not
invalidate this memory's revision.

Create, patch, and replace return the current memory reference and revision.
Delete returns the deleted reference without a revision. Every mutation result
also contains:

- `changed`, which is false for an idempotent no-op;
- the local Git `commit` representing the current result;
- `index_status`, either `current` or `pending`;
- `sync_status`, one of `local`, `synchronized`, `pending`, `conflict`, or
  `unchanged`.

`pending` means the Git mutation succeeded but that mutation's synchronous
Vexor rebuild failed. It does not mean that a background indexing job is still
running. The next non-empty search retries the rebuild before querying memory.

For `sync_status`, `local` means no remote is configured, `synchronized` means
the remote contains the changed commit, and `unchanged` means no commit or push
was needed. `pending` and `conflict` still mean the local commit succeeded; do
not repeat the mutation. A conflict blocks later writes until the Git histories
are reconciled. The
[consistency model](../concepts/consistency.md#optional-git-synchronization)
owns the complete synchronization contract.

## Expected errors

Expected validation, conflict, repository, and index failures return an MCP
tool result with `isError: true` and actionable text. Common cases include:

- missing, null, action-incompatible, or unknown fields;
- invalid title, summary, body, project, ID, or revision;
- stale revision, missing memory, or ambiguous patch anchor;
- a dirty, detached, or unfinished memory repository;
- damaged committed Markdown;
- an embedding or query failure while rebuilding or searching;
- an unavailable local index collection, directory, or commit marker.

Unexpected failures return a generic error without exposing bodies, summaries,
queries, provider responses, credentials, or complete request payloads.
