# Consistency Model

Perenna protects one durable invariant: a successful memory write is committed
Markdown in Git. Retrieval and remote backup are secondary operations that
cannot invalidate that commit.

## Source of truth and cache

```text
Git commit + Markdown  = permanent truth
Vexor collection       = rebuildable retrieval cache
Git remote             = optional backup
```

Perenna never repairs permanent memory from Vexor data.

## Committed snapshots

Every query reads a specific captured Git commit. Paths and file contents are
resolved against that commit rather than a moving `HEAD`. This prevents a
concurrent commit from mixing one snapshot's marker with another snapshot's
content.

Uncommitted working-tree changes are excluded from lightweight indexes,
retrieval results, and index rebuilds.

## Write transaction

One write runs under the repository's exclusive lock:

1. validate title, body, project, and source;
2. require a clean working tree, clean Git index, active branch, and no
   unfinished Git operation;
3. load the latest committed snapshot;
4. resolve create or update by normalized title in one scope;
5. atomically replace the target Markdown file;
6. stage only that file;
7. create one Git commit with hooks isolated;
8. verify that the commit contains only the target file;
9. synchronize the Vexor collection while the lock is still held.

If Git staging or commit creation fails before `HEAD` changes, Perenna restores
the target file and Git index. A committed memory is never rolled back because
embedding failed.

## Cross-process locks

Perenna stores two lock files in the index directory:

- the repository lock supports concurrent readers and one exclusive writer;
- the push lock serializes optional remote backup separately.

Lightweight index reads and current-index recalls use a shared repository lock.
Writes and full index rebuilds use the exclusive lock. A stale recall releases
its shared lock, acquires the exclusive lock, rechecks the current state, and
only then rebuilds.

## Index synchronization

The `indexed_commit` marker identifies the Git commit represented by the Vexor
collection.

- A write uses incremental upsert only when the marker matches the write's
  previous commit and the collection shape is valid.
- A stale marker, missing collection, count mismatch, or deleted index causes a
  full rebuild from committed Markdown.
- The marker advances only after successful indexing.
- A failed search invalidates the marker so a later recall retries recovery.

Project filtering is applied before Vexor scores candidates. Final records are
resolved by memory ID against the same committed snapshot.

## Dirty working trees

Manual edits do not block reads. Queries continue to use the last commit, but
writes stop until the user commits, stashes, moves, or restores the local
changes. Perenna never stages a user's unrelated edit.

## Best-effort remote backup

After the local commit and index attempt, Perenna may push under the separate
push lock. It can establish an upstream on the first push. A missing remote,
timeout, credential error, or non-fast-forward rejection does not change the
memory write result.

Perenna does not fetch, pull, force-push, or merge remote history.

## Failure outcomes

| Failure | Operation result | Durable state |
| --- | --- | --- |
| Invalid input or committed Markdown | Failure | No new file or commit |
| Dirty repository or unfinished Git operation | Write failure; reads continue | User changes remain untouched |
| Atomic replacement failure | Write failure | Original file remains |
| Git stage or commit failure | Write failure | File and index are restored when safe |
| Vexor update or rebuild failure after commit | Write succeeds; recall reports an index error | Git commit remains; marker does not advance |
| Git push failure | Write succeeds | Local commit remains authoritative |

Recovery procedures are in
[Maintenance and recovery](../guides/maintenance.md).
