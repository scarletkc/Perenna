# Consistency Model

Perenna protects one durable invariant: a successful changed mutation is
committed Markdown in the local Git repository. Retrieval and optional remote
synchronization are secondary operations that cannot invalidate that commit.

## Source of truth and cache

```text
Local Git + Markdown   = permanent truth
Vexor chunk collection = rebuildable retrieval cache
Git remote             = optional portable copy
```

Perenna never repairs permanent memory from Vexor data.

## Committed snapshots

Every read captures one Git commit. Paths and contents are resolved against
that commit rather than a moving `HEAD`, so a concurrent mutation cannot mix
one snapshot's index marker with another snapshot's Markdown.

Uncommitted working-tree changes are excluded from list, search, get, and index
rebuilds.

## Per-memory revisions

Search and get return an opaque revision of one canonical memory document. It
covers all authoritative frontmatter, including summary, and the body. It is
independent of repository HEAD, so an unrelated memory commit does not create a
false conflict.

Patch, replace, and delete compare `base_revision` against the latest committed
target while holding the repository's exclusive lock. A mismatch stops before
the worktree changes.

## Mutation transaction

One changed create, patch, replace, or delete runs under the exclusive lock:

1. validate every external field;
2. require a clean worktree and index, active branch, and no unfinished Git
   operation;
3. load the latest committed snapshot;
4. resolve create uniqueness or locate the exact memory ID;
5. check title and revision preconditions when required;
6. construct and validate the complete resulting document, or select the exact
   deletion path;
7. atomically replace or remove the target file;
8. stage only that path and create one hook-isolated Git commit;
9. verify the commit contains only that path;
10. rebuild the Vexor chunk collection from the new committed snapshot;
11. when a remote is configured, push the local commit and report its
    synchronization state while the lock remains held.

Exact patch edits are all located against the base body before any edit is
applied. Missing, repeated, or overlapping anchors reject the complete patch.

If Git staging or commit creation fails before `HEAD` changes, Perenna restores
the target file and Git index. A committed mutation is never rolled back because
embedding or remote synchronization failed.

An identical create, patch, or replace is a no-op: it returns the current commit
and revision without creating another commit.

## Cross-process locks

Perenna stores a repository lock in the index directory. It supports concurrent
readers and one exclusive mutator. The exclusive mutation covers the optional
push so two processes sharing one home cannot reorder local commits and remote
updates.

Current-index searches and committed list/get reads use the shared repository
lock. Mutations and full index rebuilds use the exclusive lock. A stale search
releases its shared lock, acquires the exclusive lock, rechecks the snapshot,
and only then rebuilds.

## Index synchronization

The `indexed_commit` marker identifies the Git commit represented by the Vexor
collection.

- Every changed mutation rebuilds the chunk collection from committed
  Markdown.
- A stale marker, missing collection, chunk-count mismatch, or deleted index
  causes another full rebuild.
- The marker advances only after successful indexing.
- A failed search invalidates the marker so a later search retries recovery.

Each chunk carries memory ID, scope, path, per-memory revision, chunk ordinal,
and exact body range. Search cross-checks all of them against the captured Git
snapshot before returning text.

Project filtering is applied before Vexor scores candidates. Results are
aggregated by memory ID using each memory's highest-scoring chunk, bounded by
the requested distinct-memory limit and server-owned character budgets, and
labeled as ranked candidates rather than guaranteed matches.

## Dirty working trees

Manual edits do not block reads. Reads continue to use the last commit, but
mutations stop until the user commits, stashes, moves, or restores local
changes. Perenna never stages an unrelated edit.

## Optional Git synchronization

Without `PERENNA_GIT_REMOTE`, Perenna never accesses a remote. Local reads and
writes retain the same behavior without network access.

`perenna sync setup` safely establishes the portable remote state:

- an empty local repository imports an existing remote branch;
- an empty remote receives existing local history;
- a clean local branch that is strictly behind fast-forwards;
- a local branch that is strictly ahead pushes;
- diverged histories stop without merge, rebase, or force-push.

When Perenna starts with an already configured remote, it makes one best-effort
fetch and fast-forwards a clean local branch when possible. Network failure does
not prevent local startup, and reads do not fetch again while that process is
running.

After a changed mutation, Perenna attempts one push and returns `sync_status`:

| Status | Meaning |
| --- | --- |
| `local` | No remote is configured |
| `synchronized` | The remote contains the changed local commit |
| `pending` | The local commit succeeded, but the remote could not be updated or checked |
| `conflict` | Local and remote histories diverged |
| `unchanged` | No commit was created and no push was attempted |

A conflict leaves the local commit intact and records a write barrier. Later
mutations stop until the user reconciles the branches and completes sync setup.
Perenna never resolves a diverged history automatically.

## Failure outcomes

| Failure | Operation result | Durable state |
| --- | --- | --- |
| Invalid input or committed Markdown | Failure | No new file or commit |
| Missing target, stale revision, or failed patch precondition | Failure | Existing memory remains |
| Dirty repository or unfinished Git operation | Mutation failure; reads continue | User changes remain untouched |
| Atomic replacement or deletion failure | Mutation failure | Original file remains |
| Git stage or commit failure | Mutation failure | File and Git index are restored when safe |
| Vexor rebuild failure after commit | Mutation succeeds with `index_status: pending` | Local Git commit remains; marker does not advance |
| Remote unavailable or push rejected without divergence | Mutation succeeds with `sync_status: pending` | Local commit remains |
| Remote history diverged | Mutation succeeds with `sync_status: conflict`; later writes stop | Local and remote commits remain unchanged |

Recovery procedures are in
[Maintenance and recovery](../guides/maintenance.md).
