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

The saved Git remote preference and `PERENNA_GIT_REMOTE` do not solve that
bootstrap step. They select a Git remote name such as `origin`; they do not
contain the repository address or configure authentication. A process that
selects a missing remote starts with local state, and later mutations report
synchronization as pending.

## Candidate interface

The narrow proposal is to let the normal `mcp` and `serve` startup paths accept
a credential-free repository address and reuse the existing synchronization
setup implementation before serving tools.

| Candidate input | Meaning |
| --- | --- |
| `PERENNA_GIT_URL` | Repository address used to bootstrap or verify synchronization |
| `--git-url URL` | CLI override for the same address |
| `PERENNA_GIT_DEPLOY_KEY` | Exact lowercase `true` or `false` selecting the repository-specific deploy-key flow |

An unset deploy-key value would remain distinct from `false`. Empty or
whitespace-only values, case variants such as `TRUE`, numeric values such as
`1`, aliases such as `yes`, and every other value would be invalid. Startup
would reject them before initializing or changing the repository.

Hosted bootstrap would accept only credential-free HTTPS URLs with a non-empty
host and repository path, `ssh://` URLs with a non-empty host and repository
path, and SCP-style SSH addresses such as `git@example.com:owner/memory.git`.
The host policy would remain provider-neutral so public, private, and
self-hosted Git services can use the same interface.

The URL would be deployment-operator configuration, never an MCP tool input.
Perenna would not maintain a provider or domain allowlist; deployments that
restrict destinations must enforce that network-egress policy at the hosting
boundary. A platform that lets an untrusted tenant control process environment
values must enforce such a policy or leave hosted bootstrap disabled.

Local paths, `file://`, insecure `http://` and `git://` URLs, Git remote-helper
forms such as `ext::`, missing-host or missing-path addresses, and every other
transport would be rejected before repository initialization or remote and
authentication configuration changes.

This narrower policy would apply at the hosted startup boundary before calling
`setup_sync()`. The existing manual setup path would retain support for local
bare repositories and its current repository-address behavior.

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

Remote-name resolution is not a new interface in this proposal. It would reuse
the implemented resolution in
[Git remote synchronization](../reference/configuration.md#git-remote-synchronization),
then apply bootstrap behavior to the effective state:

| Effective remote state | Bootstrap URL | Candidate startup behavior |
| --- | --- | --- |
| No saved choice | Absent | Preserve local-only startup |
| No saved choice | Present | Use `origin` for bootstrap |
| Named remote | Either | Use that remote name |
| Explicit local-only preference | Absent | Preserve local-only startup |
| Explicit local-only preference | Present | Reject the conflict before repository or remote changes |

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

1. Resolve the home, source, effective remote state, optional repository URL,
   and deploy-key mode while preserving the distinction between no choice, a
   named remote, and an explicit local-only preference.
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

Configuration rejection must be atomic. Invalid input must fail before
repository initialization or deploy-key generation. Compatibility and
divergence rejection must restore the prior remote URL, `core.sshCommand`,
`perenna.syncAuth`, and `perenna.deployKeyPath`; leave the saved synchronization
preference unchanged; and leave the local branch, working tree, and memory
commits unchanged.

Existing `setup_sync()` effects that do not change durable local memory remain
outside that rollback boundary: repository initialization, fetched objects and
remote-tracking refs, and a host key learned in the isolated `known_hosts` file
may remain for later verification. A `waiting-deploy-key` result is an accepted
intermediate state, not a rejection: it intentionally retains the generated
key and repository configuration so the operator can authorize that key and
restart.

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

Hosted bootstrap would retain the implemented
[SSH host-key behavior](../reference/configuration.md#repository-specific-deploy-key):
the dedicated `known_hosts` file records the first previously unseen host key,
and OpenSSH rejects later changes. Requiring a new operator-supplied host key or
fingerprint would be a separate security change, not part of this bootstrap
interface.

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
- rejection before repository initialization for empty, whitespace, numeric,
  case-variant, alias, and other invalid deploy-key values, without creating
  credential files;
- no-choice, named-remote, and explicit local-only effective states from both
  environment and saved configuration, with and without a bootstrap URL;
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
- first-connection SSH host-key recording and rejection of a changed host key;
- incompatible branches and diverged history;
- simultaneous first starts using the same home;
- rejected startup that leaves the existing remote URL, `core.sshCommand`,
  `perenna.syncAuth`, `perenna.deployKeyPath`, and the saved synchronization
  preference unchanged, and does not alter the local branch, working tree, or
  memory commits;
- compatibility rejection after fetch, covering the allowed persistence of
  derived Git objects, remote-tracking refs, and learned SSH host keys;
- absence of credentials and private-key material from errors and logs.

Tests and experiments must use disposable homes and repositories, never the
operator's normal Perenna data.
