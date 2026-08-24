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
| `PERENNA_GIT_DEPLOY_KEY` | Possible opt-in to the existing repository-specific deploy-key flow |

If deploy-key bootstrap is enabled, the repository URL must use SSH. Perenna
rejects an HTTPS URL before changing the remote configuration.

`--remote` should not be used for the repository address because Perenna
already uses *remote* to mean the configured Git name. The candidate URL and
deploy-key names are placeholders, not approved public fields.

No Git URL or deploy-key option would be required. With no bootstrap URL,
startup and local-only behavior would remain unchanged.

## Startup behavior

Any approved implementation should run bootstrap under the existing exclusive
Perenna-home lock and reuse `setup_sync()` rather than introduce a second Git
initialization path.

1. Resolve the home, source, remote name, and optional repository URL.
2. When no URL is configured, retain the current startup refresh behavior.
3. When the named remote is absent, validate the URL and run the existing safe
   setup operation.
4. When the named remote already has the same URL, treat bootstrap as
   idempotent and verify compatible state.
5. When the remote points somewhere else, fail with an actionable error. Never
   replace it automatically.
6. Import an existing compatible remote into an empty local repository, or
   publish existing local history to an empty remote, using the current setup
   rules.
7. Stop on incompatible branches or diverged history. Never merge, rebase, or
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

- empty local and empty remote;
- empty local importing existing compatible history;
- existing local publishing to an empty remote;
- repeated startup with the same address;
- an existing remote with a different address;
- unavailable authentication and network;
- deploy-key authorization pending across a persistent-home restart;
- incompatible branches and diverged history;
- simultaneous first starts using the same home;
- absence of credentials and private-key material from errors and logs.

Tests and experiments must use disposable homes and repositories, never the
operator's normal Perenna data.
