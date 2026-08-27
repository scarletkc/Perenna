# Connect a Glama MCP Server to ChatGPT Web

This guide assumes that a Glama-hosted Perenna MCP server is already deployed,
healthy, and accessible through a tokenized HTTPS instance URL. It covers only
the ChatGPT web connection; it does not cover deploying or configuring Perenna
on Glama.

## Requirements

- the complete Glama MCP instance URL, including its `/mcp` path and query
  token;
- a ChatGPT account or workspace where Developer mode is available;
- a healthy Glama instance that exposes Perenna's MCP tools.

OpenAI's
[connection guide](https://developers.openai.com/plugins/deploy/connect-chatgpt)
owns the current ChatGPT Developer mode workflow and notes that availability
can depend on account and workspace policy.

Treat the complete Glama instance URL as a secret. Its query token authorizes
access even though ChatGPT labels the connection **No authentication**. Anyone
who obtains the URL may be able to call the exposed tools.

## Connect ChatGPT

Follow OpenAI's current
[plugin connection workflow](https://developers.openai.com/plugins/deploy/connect-chatgpt)
through these Perenna-specific choices:

1. In ChatGPT, open **Settings**.
2. Select **Security and login** and enable **Developer mode**.
3. Open **ChatGPT Plugins** and select the plus button.
4. Enter a user-facing name and description for Perenna.
5. Paste the complete Glama MCP instance URL.
6. Select **No authentication**.
7. Create the connection.
8. Review the tools and metadata discovered by ChatGPT.

For Perenna, confirm that ChatGPT discovers:

- `memory_read`;
- `memory_write`;
- `memory_delete`.

Use a read-only `memory_read` list call as the first functional check. A
successful connection confirms that ChatGPT can reach the Glama MCP endpoint;
it does not independently verify how Glama deployed or persists the server.

## OAuth configuration error

If ChatGPT reports that the MCP server does not implement OAuth, edit or
recreate the connection and select **No authentication**. A tokenized Glama
instance URL does not expose the OAuth discovery expected by ChatGPT's OAuth
option.

Do not add Perenna OAuth settings merely to work around this connection error.
The separate [self-hosting guide](self-hosting.md) owns Perenna's native OAuth
deployment path.

## Protect the instance URL

Do not paste the complete URL into an issue, documentation, chat transcript,
screenshot, command history, or public log. Revoke and replace the Glama token
immediately if the URL is exposed, then update the ChatGPT connection with the
replacement URL.
