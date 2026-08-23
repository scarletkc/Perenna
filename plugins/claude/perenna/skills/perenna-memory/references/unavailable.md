# Perenna Unavailable

Use this guide when Perenna tools are missing, a memory call fails, or the user
asks to install or reconnect Perenna.

## Distinguish absence from failure

Inspect the available tools before relying on memory:

- If `memory_read`, `memory_write`, and `memory_delete` are absent, Perenna is
  not connected. Do not simulate a call or claim that memory changed.
- If the tools exist but a call returns an error, preserve the actionable error
  and diagnose that failure. Do not reinstall Perenna merely because its
  provider, index, repository, or authentication is temporarily unavailable.

Continue without memory when the current request is self-contained. When prior
context is necessary, or the user asks to remember or forget something, state
that Perenna is unavailable and leave memory unchanged.

## Separate local persistence from remote backup

When a mutation reports that the local Git commit succeeded but the backup
push failed, treat the memory as committed locally. Perenna is not unavailable,
and repeating the same `memory_write` can create an unintended second change.
Report that local persistence succeeded while the remote backup remains
unsynchronized.

If the Git commit itself failed, treat the mutation as failed: preserve the
error, do not claim the memory changed, and do not retry until the local
repository state has been inspected.

For a backup failure, use `perenna backup status` in the same environment that
runs Perenna, or guide the user to run it when the current agent cannot access
that host. Follow the maintained
[backup recovery guide](https://github.com/scarletkc/Perenna/blob/main/docs/guides/maintenance.md#recover-from-a-backup-push-failure)
for diagnosis. Do not create or replace a remote, change credentials, fetch,
pull, merge, force-push, or repeat the memory mutation without the user's
explicit authorization. After the network or credentials are repaired, verify
that the reported backup state is synchronized before claiming recovery.

## Install or reconnect only with authority

If the user asks to install Perenna or authorizes fixing the missing
connection, use the project repository and its maintained guides as the source
of truth:

- [Perenna repository](https://github.com/scarletkc/Perenna)
- [Getting started](https://github.com/scarletkc/Perenna/blob/main/docs/getting-started.md)
- [Client setup](https://github.com/scarletkc/Perenna/blob/main/docs/guides/client-setup.md)
- [Docker self-hosting](https://github.com/scarletkc/Perenna/blob/main/docs/guides/self-hosting.md)

Follow the guide for the actual client and preserve unrelated packages, skills,
MCP servers, and client configuration. Installation authority does not imply
permission to create a remote repository, replace an existing Git remote, or
copy credentials into tracked configuration.

## Choose local or self-hosted installation

Identify where the MCP client runs before installing Perenna. Do not assume a
web session can start a process on the user's computer or that a temporary
cloud shell provides durable storage.

Use the local path only when the current client host can install packages,
retain Perenna's data directory, and start a long-lived stdio subprocess. In
that environment, follow Getting Started, install Perenna on the same host, and
register `perenna mcp --source <stable-client-name>` through the client setup
guide.

For a web-based, HTTP-only, or ephemeral client, explain that local stdio setup
does not apply and ask the user to configure a persistent Docker deployment.
Guide them through the maintained self-hosting document rather than attempting
to deploy infrastructure from the web session. The user must provide or
operate the VPS, public domain, HTTPS reverse proxy, OAuth provider, persistent
volume, and deployment credentials.

Proceed one user-confirmed milestone at a time: the container runs
`perenna serve`, the public `https://.../mcp` endpoint and protected-resource
metadata respond as documented, OAuth succeeds, and the web client discovers
all three Perenna tools. Do not run remote deployment commands, create cloud or
OAuth resources, change DNS or proxy configuration, or claim a milestone from
instructions alone. Do not substitute a local stdio command for the Docker HTTP
deployment.

## Verify the live connection

After setup, reload or restart the MCP client when required and verify the live
connection with `memory_read` using `action: "list"`. A successful package
install or saved configuration entry alone is not connection evidence.

If the current process cannot reload MCP servers, give the user the single
required restart step and do not claim the tools are available yet.
