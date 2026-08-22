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
source: "claude-code"
created_at: "2026-08-23T07:10:00.000000Z"
updated_at: "2026-08-23T07:10:00.000000Z"
---

Complete clear tasks autonomously.

Explain decisions that materially affect architecture or risk.
```

Frontmatter permits exactly five fields:

```text
id
title
source
created_at
updated_at
```

Fields cannot be missing, duplicated, or extended. Every value must parse as a
string. Perenna serializes each value as a quoted YAML string.

## Field semantics

| Field | Meaning |
| --- | --- |
| `id` | Stable Perenna-generated ULID |
| `title` | Normalized long-term topic and upsert identity within the scope |
| `source` | Host that most recently wrote the memory |
| `created_at` | RFC 3339 creation timestamp; preserved on update |
| `updated_at` | RFC 3339 timestamp of the latest write |

Perenna writes UTC timestamps with a `Z` suffix. A manually written timestamp
must include an RFC 3339 timezone. `updated_at` cannot precede `created_at`.

## ULID rules

A memory ID is 26 uppercase Crockford Base32 characters. The first character
must be `0` through `7`, which keeps the value within 128 bits. The alphabet
excludes `I`, `L`, `O`, and `U`.

The frontmatter ID and filename stem must be identical.

## Title normalization

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

Titles that differ only by case or compatible Unicode forms therefore update
the same memory inside one scope.

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

## Source normalization

Source is injected by the host. Perenna applies NFKC normalization, removes
surrounding whitespace, and requires:

- 1 to 64 characters;
- an ASCII letter or digit first;
- only ASCII letters, digits, `.`, `_`, and `-` afterward.

Source case is preserved.

## Body normalization

The body must:

- be a string with at least one non-whitespace character;
- normalize CRLF and CR line endings to LF;
- remove leading and trailing newline characters;
- preserve other meaningful Markdown spacing;
- contain no NUL, unsupported control characters, or invalid surrogates;
- contain at most 20,000 Unicode characters.

Perenna stores the complete body without truncation, summarization, or merge.

## Create and update behavior

| Value | Create | Update |
| --- | --- | --- |
| `id` | Generate | Preserve |
| `title` | Store normalized input | Replace with normalized input |
| `source` | Current host | Current host |
| `created_at` | Current time | Preserve |
| `updated_at` | Current time | Advance |
| body | Store complete input | Replace completely |

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
- a title, body, source, or project violates this contract.

The error identifies the trusted relative path and asks the user to repair and
commit the file. It does not log the body.

## Manual editing

Users may edit committed memories with ordinary tools. Perenna reads only
committed snapshots, so a manual edit becomes visible after the user validates
and commits it. While the working tree is dirty, reads continue from the prior
commit and automated writes remain paused.

See [Maintenance and recovery](../guides/maintenance.md) for the safe workflow.
