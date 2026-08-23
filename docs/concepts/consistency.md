# Consistency Model

Perenna protects one durable invariant: a successful changed mutation is
committed Markdown in Git. Retrieval and remote backup are secondary operations
that cannot invalidate that commit.

## Source of truth and cache

```text
Git commit + Markdown  = permanent truth
Vexor chunk collection = rebuildable retrieval cache
Git remote             = optional backup
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
10. rebuild the Vexor chunk collection from the new committed snapshot while
    the lock remains held.

Exact patch edits are all located against the base body before any edit is
applied. Missing, repeated, or overlapping anchors reject the complete patch.

If Git staging or commit creation fails before `HEAD` changes, Perenna restores
the target file and Git index. A committed mutation is never rolled back because
embedding failed.

An identical create, patch, or replace is a no-op: it returns the current commit
and revision without creating another commit.

## Cross-process locks

Perenna stores two lock files in the index directory:

- the repository lock supports concurrent readers and one exclusive mutator;
- the push lock serializes optional remote backup separately.

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

## Best-effort remote backup

After the local commit and index attempt, Perenna may push under the separate
push lock. A missing remote, timeout, credential error, or non-fast-forward
rejection does not change the mutation result.

Perenna does not fetch, pull, force-push, or merge remote history.

## Failure outcomes

| Failure | Operation result | Durable state |
| --- | --- | --- |
| Invalid input or committed Markdown | Failure | No new file or commit |
| Missing target, stale revision, or failed patch precondition | Failure | Existing memory remains |
| Dirty repository or unfinished Git operation | Mutation failure; reads continue | User changes remain untouched |
| Atomic replacement or deletion failure | Mutation failure | Original file remains |
| Git stage or commit failure | Mutation failure | File and Git index are restored when safe |
| Vexor rebuild failure after commit | Mutation succeeds with `index_status: pending` | Git commit remains; marker does not advance |
| Git push failure | Mutation succeeds | Local commit remains authoritative |

Recovery procedures are in
[Maintenance and recovery](../guides/maintenance.md).
