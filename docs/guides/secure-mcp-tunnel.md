# Connect ChatGPT through Secure MCP Tunnel

Use this path when a supported OpenAI product needs to reach Perenna on a
developer machine or private host without a public inbound port. Perenna serves
standard Streamable HTTP on loopback, and `tunnel-client` carries MCP traffic
over its outbound connection to OpenAI.

The local HTTP hop does not use OAuth. Access from ChatGPT remains subject to
the OpenAI workspace, tunnel, app, action, and confirmation controls that apply
to that user. Perenna still advertises `memory_write` and `memory_delete` as
mutating tools; the client decides whether those actions are available.

## Requirements

- Perenna installed on a persistent machine with its intended Perenna home;
- the latest official OpenAI `tunnel-client` installed on the same machine;
- a tunnel ID, runtime API key, and required tunnel permissions for the target
  Platform organization and ChatGPT workspace;
- a configured Vexor provider for semantic search.

Use the current [Secure MCP Tunnel documentation](https://developers.openai.com/api/docs/guides/secure-mcp-tunnels)
for installation, tunnel creation, permissions, workspace association, and
supported OpenAI products. Keep the runtime API key in the tunnel-client
environment, not in Perenna configuration or the memory repository.

## Start Perenna on loopback

Run the local-only HTTP mode:

```text
perenna serve --local-only --host 127.0.0.1 --port 8000
```

The MCP endpoint is:

```text
http://127.0.0.1:8000/mcp
```

This mode does not read `PERENNA_PUBLIC_URL` or any `PERENNA_OAUTH_*`
variables, publish OAuth protected-resource metadata, or require an
`Authorization` header. It rejects non-loopback listen addresses. The
[configuration reference](../reference/configuration.md#local-only-streamable-http)
owns the exact flag and security contract.

Keep this process running while the tunnel is in use. A process supervisor may
restart it, but Perenna does not install or manage one.

## Configure tunnel-client

Set `CONTROL_PLANE_API_KEY` to the runtime API key in the tunnel-client process
environment. Confirm the installed command's current quickstart, then create an
HTTP profile for Perenna:

```text
tunnel-client help quickstart
tunnel-client init --sample sample_mcp_stdio_local --profile perenna --tunnel-id <tunnel-id> --mcp-server-url http://127.0.0.1:8000/mcp
tunnel-client doctor --profile perenna --explain
tunnel-client run --profile perenna
```

Use the actual tunnel ID from OpenAI. `doctor` validates the selected
configuration, local HTTP reachability, and OAuth metadata behavior. It does not
perform MCP tool discovery; the next step verifies that in ChatGPT.

In ChatGPT's developer-mode connection flow, choose **Tunnel** and select the
associated tunnel or enter its tunnel ID. Choose **No authentication** because
Perenna's loopback-only endpoint does not provide application-level OAuth.
Review the discovered tools, then verify that `memory_read`, `memory_write`,
and `memory_delete` are present. Product-level permissions may leave mutating
actions unavailable even when Perenna advertises them correctly.

## Security boundary

`--local-only` is intentionally inseparable from loopback binding. Do not use a
reverse proxy, port forward, container port publication, or network relay to
make this unauthenticated endpoint reachable from another machine. Other
processes on the host can reach the endpoint; use a trusted single-user host
for this mode.

For a public or cross-network Perenna endpoint, omit `--local-only` and follow
the [OAuth-protected self-hosting guide](self-hosting.md).
