# Self-host Perenna for ChatGPT

This guide runs one authenticated Perenna instance for one owner. Perenna
serves plain HTTP inside the host; the operator supplies the public domain,
HTTPS certificate, reverse proxy, and OAuth provider.

The remote mode is a private ChatGPT developer-mode connection. It does not
create a multi-user Perenna service or publish a plugin.

## Requirements

- a VPS with Docker;
- a public DNS name with HTTPS terminated by a reverse proxy;
- an OAuth provider that supports MCP authorization discovery, PKCE with
  `S256`, and CIMD or dynamic client registration;
- one OAuth user whose stable `sub` claim will own the instance.

[OpenAI's authentication guide](https://developers.openai.com/plugins/build/auth)
documents the client and authorization-server requirements. Auth0 is a known
compatible provider, but Perenna validates standard RS256 JWT access tokens and
does not otherwise depend on Auth0.

## Build the image

From a Perenna source checkout:

```bash
docker build -t perenna:local .
```

The image runs `perenna serve` as an unprivileged user, listens on port `8000`,
and stores the Perenna home under `/data`.

## Configure OAuth

Use the final public MCP URL as the OAuth resource identifier and token
audience:

```text
https://memory.example.com/mcp
```

For Auth0:

1. Create an API whose identifier is the complete public MCP URL and whose
   signing algorithm is `RS256`.
2. Enable **Resource Parameter Compatibility Profile** and
   **Include Issuer in Authorization Responses** in the tenant settings.
3. Configure the `memory:read`, `memory:write`, and `memory:delete` permissions.
4. Register ChatGPT through CIMD or enable DCR and configure third-party
   application access.
5. Create or select the owner, then copy that user's exact `sub` claim.

Follow the
[Auth0 authorization quickstart](https://auth0.com/ai/docs/mcp/get-started/authorization-for-your-mcp-server)
for the tenant-side API, permissions, user, and registration steps.

Use the exact ChatGPT client metadata URL and redirect URI shown by the plugin
management page. Do not derive a callback URL from this guide.

## Configure Perenna

Copy the tracked environment template to a root-readable deployment path, then
replace every placeholder with the deployment's exact values:

```bash
sudo install -d -m 700 /etc/perenna
sudo install -m 600 .env.example /etc/perenna/perenna.env
sudoedit /etc/perenna/perenna.env
```

The template includes the Docker runtime defaults and optional Vexor and Git
backup settings. The
[configuration reference](../reference/configuration.md#remote-mcp-and-oauth)
owns the complete field contract.

## Run the container

Bind the container port only to the VPS loopback interface when Nginx runs on
the host:

```bash
docker run --detach \
  --name perenna \
  --restart unless-stopped \
  --env-file /etc/perenna/perenna.env \
  --publish 127.0.0.1:8000:8000 \
  --volume perenna-data:/data \
  perenna:local
```

The image uses UID `10001`. When replacing the named volume with a host bind
mount, make that directory writable by UID `10001` before starting the
container.

## Update Perenna without losing memories

The container is replaceable. Permanent state remains in the named
`perenna-data` volume:

```text
/data/memory   Git-backed permanent memories
/data/index    Rebuildable Vexor index
```

Before an update, confirm that the running container still mounts that volume
at `/data` and that the memory repository is clean:

```bash
docker inspect perenna \
  --format '{{range .Mounts}}{{println .Name .Destination}}{{end}}'
docker exec perenna git -C /data/memory status --short
```

The inspect output should include `perenna-data /data`. An empty Git status is
expected. Resolve an unexpected dirty repository before replacing the
container.

Update the source checkout and build the replacement image before stopping the
working container:

```bash
cd Perenna
git pull --ff-only
docker image tag perenna:local perenna:previous
docker build -t perenna:local .
```

If the deployment follows release tags, fetch and check out the intended tag
instead of pulling the current branch. Review `.env.example` for newly required
configuration before restarting.

Replace only the container, then repeat the command under
[Run the container](#run-the-container). The volume name and environment-file
path must stay the same:

```bash
docker stop perenna
docker rm perenna
```

`docker rm perenna` does not remove the named volume. After the new container
starts, repeat the checks under
[Verify the deployment](#verify-the-deployment) and confirm that
`memory_read` can list the existing memories.

To run the previous image again, stop and remove the replacement container,
then repeat the same `docker run` command with `perenna:previous`. Review the
release notes first when a release changes an on-disk contract.

Do not run either of these during a normal update:

```bash
docker volume rm perenna-data
docker compose down -v
```

Both commands can delete persistent volumes. Removing `perenna-data` deletes
the memory Git repository as well as the rebuildable index.

## Reverse proxy the endpoint

Place these locations inside the HTTPS `server` block for the public domain:

```nginx
location /mcp {
    proxy_pass http://127.0.0.1:8000;
    proxy_http_version 1.1;
    proxy_set_header Host $http_host;
    proxy_set_header Authorization $http_authorization;
    proxy_buffering off;
    proxy_read_timeout 300s;
}

location /.well-known/oauth-protected-resource/mcp {
    proxy_pass http://127.0.0.1:8000;
    proxy_http_version 1.1;
    proxy_set_header Host $http_host;
}
```

Perenna validates the public `Host` header against `PERENNA_PUBLIC_URL`, so the
proxy must preserve it. The image does not terminate TLS or trust forwarded
headers to construct security-sensitive URLs.

## Verify the deployment

Read the public protected-resource metadata:

```bash
curl https://memory.example.com/.well-known/oauth-protected-resource/mcp
```

An unauthenticated MCP request must return `401 Unauthorized` with a
`WWW-Authenticate` header pointing to that metadata URL:

```bash
curl --include \
  --header 'Accept: application/json, text/event-stream' \
  --header 'Content-Type: application/json' \
  --data '{"jsonrpc":"2.0","id":1,"method":"ping"}' \
  https://memory.example.com/mcp
```

Use MCP Inspector with OAuth to verify token issuance and all three tool
scopes before connecting ChatGPT.

## Connect ChatGPT

1. Enable developer mode in ChatGPT.
2. Create a custom plugin and choose **Server URL**.
3. Enter the complete `https://memory.example.com/mcp` URL.
4. Select **OAuth** and review the discovered authorization settings.
5. Create the connection and complete the OAuth login.
6. Confirm that ChatGPT discovers `memory_read`, `memory_write`, and
   `memory_delete`.

The first tool call may trigger login or scope consent. A successful connection
is private to the ChatGPT account that created it and requires no plugin
submission.
