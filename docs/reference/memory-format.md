# Memory File Format

This page is the canonical contract for memory paths, Markdown structure,
normalization, and committed-repository integrity.

## Paths and scopes

Every memory is a Markdown file named by a ULID:

```text
memory/
├── global/
│   └── <ULID>.md
└── projects/
    └── <project-slug>/
        └── <ULID>.md
```

Scope is derived only from the trusted relative path:

| Relative path | Scope |
| --- | --- |
| `global/<ULID>.md` | `global` |
| `projects/<slug>/<ULID>.md` | `project:<slug>` |

Scope is not a frontmatter field. The filename stem must exactly match the
frontmatter `id`, and IDs must be unique across the repository.

## Markdown structure

A file contains YAML frontmatter, one blank line, and the complete Markdown
body:

```markdown
---
id: "01K35Z9V6Y8X2W4T7R1Q5M3N0P"
title: "AI collaboration preferences"
summary: "Stable preferences for collaborating with AI agents."
created_at: "2026-08-23T07:10:00.000000Z"
updated_at: "2026-08-23T07:10:00.000000Z"
---

Complete clear tasks autonomously.

Explain decisions that materially affect architecture or risk.
```

Frontmatter permits exactly five fields, in this order:

```text
id
title
summary
created_at
updated_at
```

Fields cannot be missing, duplicated, or extended. Every value must parse as a
string. Perenna serializes each value as a quoted YAML string.

## Field semantics

| Field | Meaning |
| --- | --- |
| `id` | Stable Perenna-generated ULID |
| `title` | Normalized long-term topic, unique within one scope |
| `summary` | Stable one-sentence description of what the memory covers |
| `created_at` | RFC 3339 creation timestamp; preserved on mutation |
| `updated_at` | RFC 3339 timestamp of the latest mutation |

Perenna writes UTC timestamps with a `Z` suffix. A manually written timestamp
must include an RFC 3339 timezone. `updated_at` cannot precede `created_at`.

Repositories that still contain the removed `source` field must follow the
[0.2.0 upgrade note](../release-notes/0.2.0.md) before Perenna can read the
current five-field format.

## ULID rules

A memory ID is 26 uppercase Crockford Base32 characters. The first character
must be `0` through `7`, which keeps the value within 128 bits. The alphabet
excludes `I`, `L`, `O`, and `U`.

The frontmatter ID and filename stem must be identical.

## Title normalization and uniqueness

Perenna applies these steps before writing:

1. Unicode NFKC normalization;
2. collapse consecutive whitespace to one ASCII space;
3. remove leading and trailing whitespace;
4. reject an empty result;
5. reject control characters and invalid Unicode surrogates;
6. enforce a maximum of 120 Unicode characters.

The uniqueness key adds Unicode case folding:

```text
(scope, normalized_title.casefold())
```

Titles that differ only by case or compatible Unicode forms therefore conflict
inside one scope. MCP patch and replace operations address an existing memory
by ID and do not rename it.

## Summary normalization

Summary is authoritative memory data, not generated cache metadata. It must
state what the memory covers rather than restate every current detail.

Perenna applies NFKC normalization, collapses all whitespace to one ASCII
space, and removes surrounding whitespace. The result must:

- contain at least one non-whitespace character;
- remain one plain-text line;
- contain no control characters or invalid surrogates;
- contain at most 300 Unicode characters.

Perenna never generates a summary and never substitutes the first characters
of the body. Patch preserves the existing summary unless the caller explicitly
provides a complete replacement. Replace always requires the complete summary.

## Project slug normalization

Perenna applies NFKC normalization, removes surrounding whitespace, and
converts the project to lowercase. The result must:

- contain 1 to 64 characters;
- use only ASCII `a-z`, `0-9`, `.`, `_`, and `-`;
- contain neither `/`, `\`, nor `..`;
- not equal `.`;
- not end with a dot;
- not use a Windows device name such as `con`, `nul`, `com1`, or `lpt9`, even
  when followed by an extension.

The slug is a path component and is not stored in frontmatter.

## Body normalization

The body must:

- be a string with at least one non-whitespace character;
- normalize CRLF and CR line endings to LF;
- remove leading and trailing newline characters;
- preserve other meaningful Markdown spacing;
- contain no NUL, unsupported control characters, or invalid surrogates;
- contain at most 20,000 Unicode characters.

Perenna stores the complete body without summarizing or merging it. Semantic
search uses bounded derived chunks; `memory_read get` returns the authoritative
complete body.

## Mutation behavior

| Value | Create | Patch | Replace |
| --- | --- | --- | --- |
| `id` | Generate | Preserve | Preserve |
| `title` | Store normalized input | Preserve | Preserve |
| scope | Derive from project | Preserve | Preserve |
| `summary` | Store complete input | Preserve or replace explicitly | Replace completely |
| `created_at` | Current time | Preserve | Preserve |
| `updated_at` | Current time | Advance | Advance |
| body | Store complete input | Apply exact edits | Replace completely |

Deleting removes the file from the current tree. Git history retains the prior
document.

## Committed-repository integrity

Perenna rejects a committed snapshot instead of silently skipping data when:

- a memory path does not match an allowed layout;
- a memory entry is not a regular Git blob;
- UTF-8 decoding fails;
- frontmatter is missing, malformed, duplicated, extended, or typed
  incorrectly;
- a filename and ID differ;
- an ID appears more than once;
- one scope contains duplicate normalized titles;
- a timestamp is invalid or ordered incorrectly;
- a title, summary, body, or project violates this contract.

The error identifies the trusted relative path and asks the user to repair and
commit the file. It does not log the summary or body.

## Manual editing

Users may edit committed memories with ordinary tools. Perenna reads only
committed snapshots, so a manual edit becomes visible after the user validates
and commits it. While the working tree is dirty, reads continue from the prior
commit and automated mutations remain paused.

See [Maintenance and recovery](../guides/maintenance.md) for the safe workflow.
