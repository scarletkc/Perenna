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

## Install or reconnect only with authority

If the user asks to install Perenna or authorizes fixing the missing
connection, use the project repository and its maintained guides as the source
of truth:

- [Perenna repository](https://github.com/scarletkc/Perenna)
- [Getting started](https://github.com/scarletkc/Perenna/blob/main/docs/getting-started.md)
- [Client setup](https://github.com/scarletkc/Perenna/blob/main/docs/guides/client-setup.md)

Follow the guide for the actual client and preserve unrelated packages, skills,
MCP servers, and client configuration. Installation authority does not imply
permission to create a remote repository, replace an existing Git remote, or
copy credentials into tracked configuration.

## Verify the live connection

After setup, reload or restart the MCP client when required and verify the live
connection with `memory_read` using `action: "list"`. A successful package
install or saved configuration entry alone is not connection evidence.

If the current process cannot reload MCP servers, give the user the single
required restart step and do not claim the tools are available yet.
