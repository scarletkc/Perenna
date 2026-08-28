# Maintenance and Recovery

This runbook covers local Git inspection, manual edits, index recovery, remote
synchronization failures, and disaster recovery. Permanent recovery always
starts from the memory Git repository, never from the Vexor index.

Use the [command form](../reference/configuration.md#command-forms) selected
during setup. In the commands below:

- `<home>` is the resolved Perenna home;
- `<memory-repository>` is `<home>/memory`.

See the [configuration reference](../reference/configuration.md) when the
resolved paths or provider settings are unclear.

## Inspect the repository

Use ordinary read-only Git commands:

```bash
git -C <memory-repository> status --short
git -C <memory-repository> log --oneline --decorate
git -C <memory-repository> show <commit>
git -C <memory-repository> log -- <relative-memory-path>
```

Every successful changed Perenna mutation creates one commit containing only
the target memory path.

## Resolve a dirty working tree

Perenna refuses mutations while the memory repository contains uncommitted or
staged changes. Reads continue to use the last committed snapshot.

Inspect the state first:

```bash
git -C <memory-repository> status --short
git -C <memory-repository> diff
git -C <memory-repository> diff --cached
```

Then choose explicitly:

- validate and commit a manual edit;
- stash it or move it outside the repository;
- restore only the specific file when the change is unwanted.

Do not use a repository-wide destructive reset as a routine recovery step.

## Make a manual memory edit

1. Stop or avoid concurrent Perenna mutations.
2. Edit the Markdown under `global/` or `projects/<slug>/`.
3. Validate it against the
   [memory file format](../reference/memory-format.md).
4. Stage only the intended file.
5. Create a Git commit.

The next search notices the changed `HEAD` and rebuilds the Vexor collection.

## Restore or delete a memory

Prefer a history-preserving revert for a complete commit:

```bash
git -C <memory-repository> revert <commit>
```

To restore one file, retrieve that file from the chosen commit, validate it,
and create a new commit. `memory_delete` can remove one current memory by ID,
title, and revision; a manual file deletion and commit has the same
history-preserving storage effect. Neither path purges older Git content.

## Rebuild the Vexor index

Rebuild when the collection is damaged, the provider contract changes, or you
want to discard all derived index state:

1. Stop every Perenna process using the same home.
2. Move `<home>/index` outside the home as a temporary backup, or delete it.
3. Restart a configured MCP client.
4. Run `memory_read` with `action: "search"` and non-empty query text.
5. Confirm that search succeeds.
6. Remove the temporary index backup when it is no longer needed.

Rebuild reads only the committed Git snapshot. Uncommitted working-tree files
never enter the collection.

## Recover from an indexing failure

If a mutation reports successful Git persistence but indexing is pending:

1. Do not repeat the same mutation merely to trigger embedding again.
2. Read the search error to identify which stage failed.
3. For an embedding or query failure, check the effective Vexor provider,
   model, endpoint, and API key.
4. For a local collection or marker failure, check access to the index
   directory and follow the rebuild procedure above.
5. Search again to retry recovery synchronously.
6. Rebuild the index if the provider, model, or vector dimension changed.

There is no background indexing job to wait for. The committed Markdown
remains authoritative throughout this process.

## Recover from a Git commit failure

Perenna attempts to restore the target file and Git index when commit creation
fails. Verify the result before another mutation:

```bash
git -C <memory-repository> status --short
git -C <memory-repository> log -1 --oneline
```

If the repository remains dirty, stop new mutations and inspect file permissions,
disk space, repository state, and stderr diagnostics.

## Recover from a Git synchronization failure

A mutation with `sync_status: pending` or `sync_status: conflict` is committed
locally. Do not repeat that memory mutation. Inspect the synchronization state:

```bash
perenna sync status
git -C <memory-repository> remote -v
git -C <memory-repository> status --branch --short
```

For `pending`, repair the network or credentials, then rerun setup with the
already configured repository URL. A strictly ahead local branch pushes; a
strictly behind clean branch fast-forwards:

```bash
perenna sync setup <repository-url>
perenna sync status
```

For `conflict`, stop Perenna writers and inspect both histories before changing
either one:

```bash
git -C <memory-repository> log --oneline --left-right HEAD...<remote>/<branch>
git -C <memory-repository> diff HEAD <remote>/<branch> -- global projects
```

Reconcile the commits manually, validate the resulting Markdown, and leave the
working tree clean. Perenna does not choose merge versus rebase and never
force-pushes. Run `perenna sync setup <repository-url>` afterward; successful
setup clears the write barrier. Perform authentication and Git recovery as the
same operating-system user and with the same credential or SSH-agent access as
the MCP process.

## Disaster recovery

If the memory Git repository survives, the Vexor index is unnecessary:

1. Run `perenna sync setup <repository-url> --home <new-home>` to import the
   remote branch, or clone/copy a surviving repository into `<new-home>/memory`.
2. Check out the intended branch and confirm a clean working tree.
3. Validate the committed memory files.
4. Leave `<new-home>/index` absent.
5. Configure a working Vexor provider.
6. Start Perenna with `<new-home>` and run a search query.

Validate recovery from Git history, memory content, and search results rather
than from any old cache files.
