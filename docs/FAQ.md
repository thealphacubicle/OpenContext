# FAQ

## General

**What is OpenContext?**
An MCP framework template for civic data. Each fork deploys one MCP server with one plugin.

**Why one plugin per fork?**
Simplicity, independent scaling, clear boundaries. See [Architecture](ARCHITECTURE.md).

**What is MCP?**
[Model Context Protocol](https://modelcontextprotocol.io)—connects AI assistants to external data.

## Configuration

**How do I enable a plugin?**
Create `config.yaml` from `config-example.yaml`, then set `enabled: true` for exactly one plugin.

**How do I update config after deployment?**
Edit `config.yaml`, run `./scripts/deploy.sh`.

## Plugins

**What's built-in?**
CKAN for CKAN-based portals (data.boston.gov, data.gov, etc.).

**How do I create a custom plugin?**
See [Plugins Guide](PLUGINS.md).

## Deployment

**What AWS resources are created?**
Lambda, Function URL, API Gateway, IAM role, CloudWatch Log Group.

**Cost?**
~$1/month for 100K requests. See [Deployment](DEPLOYMENT.md).

**How do I update?**
Run `./scripts/deploy.sh` again.

## Usage

**Claude Desktop setup?**
See [Getting Started](GETTING_STARTED.md)—Streamable HTTP (npx) or Go client binary.

**Can I call it without Claude?**
Yes. POST MCP JSON-RPC to the `/mcp` endpoint.

**SQL execution?**
CKAN plugin has `execute_sql`—SELECT only, UUID resources. See [Plugins](PLUGINS.md).

## Troubleshooting

| Issue | Fix |
|-------|-----|
| Multiple plugins | Enable only one |
| Lambda 500 | CloudWatch logs, validate config |
| Claude can't connect | Check URL has `/mcp`, restart Claude |
| Plugin init fails | Check API URLs, keys, network |

## Support

- [GitHub Issues](https://github.com/thealphacubicle/OpenContext/issues)
- [Documentation](.)
