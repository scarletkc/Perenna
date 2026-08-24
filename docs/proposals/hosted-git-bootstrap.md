# Hosted Git Bootstrap Proposal

Status: Unapproved, unplanned, unscheduled, and unimplemented.

This document records a candidate design for initializing optional Git
synchronization when a hosted container can start Perenna but cannot run a
separate one-time `perenna sync setup` command. It is not a configuration
contract or roadmap commitment. The names and behaviors below require explicit
approval before implementation.

The current, implemented synchronization contract remains in the
[configuration reference](../reference/configuration.md#git-remote-synchronization)
and [consistency model](../concepts/consistency.md#optional-git-synchronization).

## Motivation

Hosted MCP platforms commonly provide a startup command, environment
variables, logs, and a persistent `/data` volume, but no interactive shell.
Perenna can keep local memory safely in that volume, yet an operator cannot
configure a backup repository without another way to run the one-time setup
operation.

`PERENNA_GIT_REMOTE` does not solve that bootstrap step. It selects an existing
Git remote name such as `origin`; it does not contain the repository address or
configure authentication. A fresh Perenna home therefore starts locally when
that remote is missing, and later mutations report synchronization as pending.

## Candidate interface

The narrow proposal is to let the normal `mcp` and `serve` startup paths accept
a credential-free repository address and reuse the existing synchronization
setup implementation before serving tools.

| Candidate input | Meaning |
| --- | --- |
| `PERENNA_GIT_URL` | Repository address used to bootstrap or verify synchronization |
| `--git-url URL` | CLI override for the same address |
| `PERENNA_GIT_REMOTE` | Existing remote-name selector; defaults to `origin` during setup |
| `PERENNA_GIT_DEPLOY_KEY` | Persistent opt-in to the existing repository-specific deploy-key flow |

Hosted bootstrap would accept only credential-free HTTPS URLs with a non-empty
host and repository path, `ssh://` URLs with a non-empty host and repository
path, and SCP-style SSH addresses such as `git@example.com:owner/memory.git`.
The host policy would remain provider-neutral so public, private, and
self-hosted Git services can use the same interface.

Local paths, `file://`, insecure `http://` and `git://` URLs, Git remote-helper
forms such as `ext::`, missing-host or missing-path addresses, and every other
transport would be rejected before repository initialization or remote and
authentication configuration changes.

An implementation should tighten the existing `_validated_repository_url()`
validator and use it through `setup_sync()` for both manual setup and hosted
startup.

If deploy-key bootstrap is enabled, the repository URL must use SSH. Perenna
would reject an HTTPS URL during the same pre-mutation validation.

The deploy-key setting would select the authentication mode only when a
bootstrap URL is present. Its semantic states would be:

| Bootstrap URL | Deploy-key value | Candidate startup behavior |
| --- | --- | --- |
| Absent | Unset | Skip bootstrap and preserve the current startup refresh, including persisted repository-specific deploy-key configuration |
| Absent | `false` | Behave as unset and preserve the current startup refresh |
| Absent | `true` | Reject the incomplete bootstrap configuration and require a repository URL before changing repository state |
| Present | Unset | Request ordinary Git authentication; reject a persisted deploy-key mode before changing remote or authentication configuration |
| Present | `false` | Behave as unset and reject a persisted deploy-key mode before configuration changes |
| Present | `true` | Require an SSH URL and bootstrap or verify repository-specific deploy-key authentication |

This preserves existing homes configured by `perenna sync setup`: when no
bootstrap URL is supplied, their persisted `core.sshCommand` continues to own
authentication. A deployment that keeps supplying a bootstrap URL for a
deploy-key home must also keep the deploy-key mode enabled on every restart.

`--remote` should not be used for the repository address because Perenna
already uses *remote* to mean the configured Git name. The candidate URL and
deploy-key names are placeholders, not approved public fields.

## Startup behavior

Any approved implementation should run bootstrap under the existing exclusive
Perenna-home lock and reuse `setup_sync()` rather than introduce a second Git
initialization path.

1. Resolve the home, source, remote name, optional repository URL, and
   deploy-key mode.
2. Validate the input combination and any configured URL before initializing or
   changing the repository.
3. When no URL is configured, retain the current startup refresh behavior.
4. When the named remote is absent, run `setup_sync()`.
5. When the named remote already has the same URL and authentication mode,
   treat bootstrap as idempotent and verify compatible state.
6. When a persisted deploy-key configuration conflicts with the requested
   authentication mode, fail before changing remote or authentication
   configuration.
7. When the remote points somewhere else, fail with an actionable error. Never
   replace it automatically.
8. Import an existing compatible remote into an empty local repository, or
   publish existing local history to an empty remote, using the current setup
   rules.
9. Stop on incompatible branches or diverged history. Never merge, rebase, or
   force-push automatically.

If a URL explicitly requests bootstrap but the remote cannot be verified,
Perenna must not silently present the deployment as synchronized. Whether it
should fail startup or serve local tools with an explicit bootstrap-pending
state remains an open product decision.

## Authentication boundary

A repository address alone does not provide write access. Hosted containers
usually cannot inherit a desktop credential manager or SSH agent.

The existing security rules must remain:

- reject HTTPS URLs containing usernames, passwords, tokens, query strings, or
  fragments;
- use only non-interactive Git operations;
- never print or store a private key in logs, tracked files, process arguments,
  or the Git remote URL;
- keep a repository-specific deploy key under the persistent Perenna home;
- never register a deploy key with a Git provider automatically.

An opt-in deploy-key bootstrap could generate the existing persistent key on
the first start, report the public key and repository settings URL, and finish
synchronization after the operator grants write access and restarts. This is a
two-stage bootstrap, not one-step authentication.

Supplying a pre-existing private key or access token through environment
variables is outside this proposal. It would require a separate secret-input,
temporary-file, subprocess-environment, and redaction review.

## Open decisions

Before implementation, decide:

- whether a deployment waiting for deploy-key authorization serves local MCP
  tools or fails closed before accepting memory writes;
- how a hosted operator retrieves the generated public key without adding a
  Git-maintenance MCP tool;
- whether a temporary network failure during first bootstrap blocks startup or
  produces an explicit retryable state;
- the precedence and exact names of the CLI and environment inputs;
- whether bootstrap is attempted once per process or retried later;
- how hosted platforms declare persistent storage and expose the optional
  configuration without claiming that a URL supplies credentials.

## Required implementation scope if approved

An implementation would need coordinated changes to configuration resolution,
the `mcp` and `serve` startup paths, synchronization reporting, CLI help,
environment metadata, and canonical documentation. It should reuse the
current Git and deploy-key modules.

Coverage must include:

- accepted HTTPS, `ssh://`, and SCP-style SSH addresses for public, private,
  and self-hosted Git hosts;
- rejection of local paths, `file://`, `http://`, `git://`, remote-helper,
  missing-host, missing-path, and unsupported-scheme addresses;
- every deploy-key state in the candidate table, both with and without a
  bootstrap URL;
- empty local and empty remote;
- empty local importing existing compatible history;
- existing local publishing to an empty remote;
- repeated startup with the same address and authentication mode;
- a persisted deploy-key home restarted without a bootstrap URL, which must
  retain its current startup refresh and authentication configuration;
- a persisted deploy-key home given a bootstrap URL without deploy-key mode,
  which must fail before configuration changes;
- an existing remote with a different address;
- unavailable authentication and network;
- deploy-key authorization pending across a persistent-home restart;
- incompatible branches and diverged history;
- simultaneous first starts using the same home;
- rejected startup that leaves the existing remote URL, `core.sshCommand`,
  `perenna.syncAuth`, and `perenna.deployKeyPath` unchanged;
- absence of credentials and private-key material from errors and logs.

Tests and experiments must use disposable homes and repositories, never the
operator's normal Perenna data.
