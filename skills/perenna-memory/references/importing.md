# Importing Memories

Use this guide only when the user explicitly asks to migrate memory content
from a host-provided memory layer, an export, or another memory system into
Perenna. Installing or connecting Perenna does not authorize an import.

Restoring or sharing an existing Perenna Git repository is synchronization,
not content import. Follow the maintained
[synchronization recovery guide](https://github.com/scarletkc/Perenna/blob/main/docs/guides/maintenance.md#recover-from-a-git-synchronization-failure)
instead.

## Confirm the import boundary

Identify the source, requested topics, destination project slugs, and any
cross-project preferences that genuinely belong in global scope. Do not read
or migrate content outside that boundary. If the request does not define a
safe destination or the inventory reveals a materially broader scope, stop
after a read-only inventory and ask before writing.

An authorized import is a one-time migration, not permission to mirror,
dual-write, or continuously reconcile memory systems.

## Curate candidates before writing

Apply [Curating memories](curation.md) to every candidate. Import is not an
exception to its durability, sensitivity, authority, or scope rules.

Convert source material into the final reusable state rather than copying a
memory dump verbatim:

- omit raw conversations, temporary progress, credentials, private identity
  material, and facts already authoritative in the current workspace;
- resolve source material against current user instructions, workspace files,
  runtime evidence, and current Perenna memory;
- do not silently merge a stale or conflicting source into a current memory;
- keep project-specific knowledge in its project scope and do not duplicate
  the same fact in both global and project scopes;
- do not fabricate original Perenna metadata. Perenna assigns IDs and
  timestamps.

Keep a bounded working inventory with each candidate's source identifier,
proposed title, destination scope, and disposition: create, update, skip, or
reject. Do not expose complete bodies merely to report the plan.

## Deduplicate in the destination

Check Perenna before every write:

1. For a project candidate, call `memory_read` with `action: "list"` and the
   destination project. For a global candidate, list without a project and
   inspect the returned global references.
2. Search for the specific subject when the lightweight index is insufficient.
   Include the destination project for project memories so unrelated projects
   are excluded before ranking.
3. Use `get` on a likely match before deciding whether it is the same durable
   subject.
4. Create only when no existing memory owns the subject. Patch the current
   memory when the imported fact belongs there; skip it when Perenna already
   contains the effective state.

Treat search results as candidates, not proof. Preserve unrelated content and
never replace a complete memory merely to make an import easier.

## Write and verify the import

Use one `memory_write` mutation per destination memory. For a large authorized
import, work in bounded batches and re-read destination state between batches.
Do not bypass the MCP tools by copying unvalidated files into the memory Git
repository.

After each changed mutation, inspect `sync_status`. A `pending` or `conflict`
result does not mean the local import failed and must not trigger a duplicate
write. Follow [Perenna unavailable](unavailable.md) when a tool or
synchronization operation fails.

At the end, list the affected destination scopes and run focused searches with
the relevant project slug. Report created, updated, skipped, and rejected
titles with their scopes, plus any unsynchronized status, without echoing
unnecessarily complete memory content.
