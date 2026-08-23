# ADR 0001: Use one HTTP service for active cross-device access

Status: Accepted

## Context

Perenna supports local stdio processes that share one home, a self-hosted HTTP
service, and an optional Git remote. These mechanisms solve different sharing
problems:

- processes using the same home can coordinate through filesystem locks;
- clients using the same HTTP service operate on one home and one current
  repository state;
- a Git remote can move compatible history to a new machine and preserve an
  off-machine copy.

Independent Perenna homes cannot share the local lock. Treating their common
Git remote as a real-time authority would require every read and write to fetch,
writes to use compare-and-swap pushes with retries, and ambiguous network
timeouts to be reconciled before serving more operations. Index state would
also have to follow each accepted or rejected candidate commit.

## Decision

Use one self-hosted HTTP Perenna service when several devices or remote clients
need active access to the same memory. All of those clients connect to the same
service and therefore share one Perenna home, repository lock, Git checkout,
and Vexor index.

Keep local stdio as the local and offline-friendly deployment. Multiple local
clients may share it when they resolve the same home.

Use an optional Git remote for portability and recovery, including importing an
existing repository on a new machine, publishing local history, and
fast-forwarding compatible history. Git synchronization does not coordinate
concurrent writers on independent homes. Perenna does not fetch before every
read or write and does not merge, rebase, or force-push diverged histories.
When divergence is detected, the local commit remains available, the conflict
is reported, and later writes stop until the user reconciles the branches.

The exact synchronization and failure behavior remains defined by the
[consistency model](../concepts/consistency.md#optional-git-synchronization)
and [configuration reference](../reference/configuration.md#git-remote-synchronization).

## Rejected alternative

The rejected design made the Git remote branch authoritative for several
independently writable Perenna instances. Each operation would fetch first;
each mutation would create a candidate commit, push it as a remote
compare-and-swap, and retry unrelated changes after a rejection. Remote
availability and latency would enter every normal operation, while timeouts
could leave the caller unable to know whether a write committed remotely.

This design was rejected because no established use case required concurrent
independent writers. It added a distributed transaction protocol, weakened
offline behavior, and increased normal-operation latency to solve a scenario
already served more directly by one HTTP service. Git would still not provide
push notifications or make separate indexes real-time.

## Consequences

- Cross-device clients that use one HTTP service see one serialized repository
  and do not create Git synchronization conflicts with each other.
- A new local installation can import an existing remote without implementing
  multi-writer coordination.
- A running local instance may not observe a remote update until restart or an
  explicit synchronization setup operation.
- Two independent homes that write concurrently can diverge. Perenna surfaces
  that state and requires manual reconciliation instead of guessing how to
  combine memories.
- HTTP deployments depend on service and network availability; local stdio
  remains available for users who prefer local-only operation.

## Revisit criteria

Reconsider this decision only when observed usage requires several independent
homes to accept writes concurrently and routing those clients through one HTTP
service is not viable. If that requirement appears, evaluate a purpose-built
coordination store or service before using Git as a distributed transaction
backend.
