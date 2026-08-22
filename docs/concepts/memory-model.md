# Memory Model

Perenna models permanent memory as a versioned collection of named Markdown
notes.

## A memory is a curated current state

A memory has a stable title, a stable coverage summary, and a complete body. It
may hold several related statements when they form one durable subject.

```text
Title    = durable topic name
Summary  = what this memory covers
Body     = current valid state of that subject
Git      = prior states
```

The summary is not a dynamic TL;DR. A detail changing inside the same subject
normally changes only the body. Change the summary when the subject's coverage
changes.

Good topic boundaries include `AI collaboration preferences`, `Release
workflow`, and `Storage authority`. Temporary debugging state, transcripts,
daily journals, and task lists belong elsewhere.

## Identity and scopes

Perenna assigns every memory a stable ULID. Read, patch, replace, and delete
operations address that ID; a title is not an update selector.

Two scopes are supported:

- `global` applies across projects;
- `project:<slug>` applies to one project.

Scope comes from the memory path. Global and project memories may share a
title, but normalized titles remain unique inside one scope. The first MCP
version keeps title and scope unchanged after creation.

## Reads are separated by purpose

The read tool provides three paths:

- `list` returns lightweight IDs, titles, scopes, and summaries;
- `search` returns bounded ranked candidate passages and revisions;
- `get` returns one complete committed memory and revision.

Search chunks are derived cache data. They help choose a memory without loading
every complete body. The first version does not apply a minimum relevance
threshold, so ranked candidates are not a claim that a true match exists.

## Mutations are explicit

- `create` adds a new named memory and assigns its ID;
- `patch` applies exact local edits while preserving all unnamed body text;
- `replace` intentionally supplies the complete summary and body;
- `delete` removes one memory from the current tree.

Patch and replace require the per-memory revision returned by search or get.
The revision covers canonical frontmatter, including summary, and body. This
prevents an edit based on stale state without making unrelated memory commits
conflict.

There is no append action. Adding content is an exact patch against an existing
anchor, which keeps placement and surrounding context explicit.

## History and deletion

Every changed mutation creates one Git commit containing only the target memory
path. Delete removes the memory from current reads and search but ordinary Git
history retains its prior contents. It is recoverable deletion, not sensitive
data purging.

## Source attribution

Every changed memory records the host that most recently changed it. The host
injects `source` when Perenna starts, so a tool call cannot claim another
source. Earlier sources remain visible in Git history.

The exact API and file rules are in the
[MCP API reference](../reference/mcp-api.md) and
[memory file format](../reference/memory-format.md).
