# MCP API Reference

Perenna exposes exactly one MCP tool named `memory`.

## Tool schema

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

Fields cannot be `null`. Unknown fields are rejected.

## Action validation

| Action | Required | Optional | Rejected |
| --- | --- | --- | --- |
| `query` | `action` | `query`, `project` | `title`, `body`, unknown fields |
| `write` | `action`, `title`, `body` | `project` | `query`, unknown fields |

`source` is intentionally absent. It is resolved from trusted host startup
configuration.

## Query without search text

Request:

```json
{
  "action": "query"
}
```

The result is a lightweight text index:

- without `project`, it lists global titles and available project slugs;
- with `project`, it lists global titles and titles in that project.

It does not call semantic search or return memory bodies.

An omitted `query` field selects this mode. An explicit empty or
whitespace-only query is invalid.

## Recall with search text

Request:

```json
{
  "action": "query",
  "query": "Why is Git authoritative?",
  "project": "perenna"
}
```

Recall returns at most five complete memories as text blocks. Each block
contains:

- scope;
- title;
- latest source;
- update timestamp;
- complete body.

Without a project, every scope is searchable. With a project, Vexor searches
only `global` and `project:<slug>` records.

If there are no memories or no matches, Perenna returns a short explanatory
text result rather than an error.

## Write

Global request:

```json
{
  "action": "write",
  "title": "AI collaboration preferences",
  "body": "Complete clear tasks autonomously and explain material decisions."
}
```

Project request:

```json
{
  "action": "write",
  "project": "perenna",
  "title": "Storage authority",
  "body": "Committed Markdown is authoritative. The Vexor collection is cache data."
}
```

Write performs an upsert by normalized title inside one scope. Success means
that Perenna created a local Git commit containing the target memory file. The
text response states whether the memory was created or updated and whether
indexing remains pending.

A Vexor or backup push failure after commit does not turn a successful memory
write into an MCP error.

## Expected errors

Expected validation, repository, and index failures return an MCP tool result
with `isError: true` and actionable text. Examples include:

- missing required fields;
- an invalid project slug;
- a dirty or detached memory repository;
- damaged committed Markdown;
- an unavailable embedding provider or index.

Unexpected failures return a generic error without exposing the request body,
query text, provider response, or credentials. Detailed diagnostics remain on
stderr.

## Server instructions

Perenna advertises server-wide instructions that tell clients to:

- read the lightweight index near the start of a session;
- recall only when history matters;
- write only durable cross-session information;
- recall before replacing an existing topic;
- never store credentials or temporary progress;
- treat current user instructions as higher priority than memory.
