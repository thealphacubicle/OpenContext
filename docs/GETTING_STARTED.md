# Getting Started

Get your OpenContext server running in under 10 minutes.

OpenContext uses the Model Context Protocol (MCP), which connects AI assistants to external data. Your server exposes tools that AI assistants can call to search and query your open data.

## Prerequisites

- Python 3.11+
- Terraform >= 1.0 (for deployment)
- AWS CLI configured (for deployment)

Run `opencontext authenticate` to check all prerequisites automatically — it will flag anything missing and try to auto-install `uv` and `awscli` if needed.

---

## Installing the CLI Locally

Clone the repository and install the CLI with its dependencies:

```bash
git clone https://github.com/thealphacubicle/OpenContext.git
cd OpenContext
pip install -e ".[cli]"
```

The `-e` flag installs in editable mode so local code changes take effect immediately. The `[cli]` extra pulls in `typer`, `questionary`, and `rich`.

Verify the install:

```bash
opencontext --help
```

To also install development dependencies (pytest, ruff, etc.):

```bash
pip install -e ".[cli,dev]"
```

---

## Quick Path: Local Testing

Test the server locally before deploying.

### 1. Configure Your Plugin

Run the interactive wizard:

```bash
opencontext configure
```

This walks you through selecting a plugin, setting the data source URL, and configuring AWS settings. It writes `config.yaml` and the Terraform variable files for you.

If you prefer to configure manually, copy the template and edit it:

```bash
cp config-example.yaml config.yaml
```

For CKAN:

```yaml
plugins:
  ckan:
    enabled: true
    base_url: "https://data.yourcity.gov"
    portal_url: "https://data.yourcity.gov"
    city_name: "Your City"
    timeout: 120
```

Each deployment connects to one data source. To connect another source, deploy a separate server. See [Architecture](ARCHITECTURE.md) for details.

### 2. Start the Local Server

```bash
opencontext serve
```

The server runs at `http://localhost:8000/mcp`. Keep this terminal open.

### 3. Connect via Claude Connectors

Connect using **Claude Connectors** (same steps on both Claude.ai and Claude Desktop):

1. Go to **Settings** → **Connectors** (or **Customize** → **Connectors** on claude.ai)
2. Click **Add custom connector**
3. Enter a name (e.g. "OpenContext Local") and URL: `http://localhost:8000/mcp`

**Note:** Local servers (`localhost`) only work with Claude Desktop, since the connection runs from your machine. For Claude.ai (web), use the MCP Inspector or deploy to production first (see below).

### 4. Verify

```bash
curl -X POST http://localhost:8000/mcp \
  -H "Content-Type: application/json" \
  -d '{"jsonrpc":"2.0","id":1,"method":"ping"}'
```

You can also test with Claude by asking it to search your data, or use [Testing](TESTING.md) for more options (MCP Inspector, full test script).

---

## Production Deployment

### 1. Fork & Configure

1. Fork the [OpenContext repository](https://github.com/thealphacubicle/OpenContext)
2. Clone your fork
3. Check prerequisites:

```bash
opencontext authenticate
```

4. Run the configuration wizard:

```bash
opencontext configure
```

This prompts for your organization name, city, plugin, AWS region, Lambda name, and optional custom domain. It creates `config.yaml`, the Terraform `.tfvars` file, and initializes the Terraform workspace.

### 2. Deploy to AWS

```bash
opencontext deploy --env staging
```

The command validates config, packages code, runs `terraform plan`, asks for confirmation, then applies. At the end you'll see:

```
API Gateway URL (use for Claude Connectors):
https://xxx.execute-api.us-east-1.amazonaws.com/staging/mcp
```

AWS creates: Lambda function, Function URL, API Gateway, IAM role, CloudWatch Log Group. Cost is roughly $1/month for 100K requests. See [Deployment](DEPLOYMENT.md) for details.

### 3. Connect via Claude Connectors (Production)

Connect using **Claude Connectors** (same steps on both Claude.ai and Claude Desktop):

1. Go to **Settings** → **Connectors** (or **Customize** → **Connectors** on claude.ai)
2. Click **Add custom connector**
3. Enter a name (e.g. "Your City OpenData") and your API Gateway URL

To retrieve the URL later:

```bash
opencontext status --env staging
```

Or directly from Terraform:

```bash
cd terraform/aws
terraform output -raw api_gateway_url
```

The output already includes `/mcp`. Use the API Gateway URL for production (rate limiting, API key). For testing without auth, use the Lambda URL from `terraform output -raw lambda_url` instead.

### 4. Updating

To update config or code: edit `config.yaml` or your code, then run:

```bash
opencontext deploy --env staging
```

---

## CLI Reference

See [CLI Guide](CLI.md) for full flag documentation.

| Command | Description |
|---------|-------------|
| `opencontext authenticate` | Check prerequisites (Python, uv, AWS CLI, credentials, Terraform) |
| `opencontext configure` | Interactive wizard: creates `config.yaml`, `.tfvars`, and Terraform workspace |
| `opencontext serve` | Start local dev server at `http://localhost:8000/mcp` (no AWS required) |
| `opencontext deploy --env <env>` | Package Lambda, plan changes, confirm, and deploy |
| `opencontext status --env <env>` | Show deployment status, URLs, and cert status |
| `opencontext validate --env <env>` | Run pre-deployment checks without deploying |
| `opencontext test --env <env>` | Test the deployed MCP server endpoints |
| `opencontext logs --env <env>` | Tail CloudWatch logs (`--follow` to stream, `--verbose` for structured view) |
| `opencontext domain --env <env>` | Check custom domain and certificate status |
| `opencontext architecture` | Show AWS architecture diagram in the terminal |
| `opencontext plugin list` | List all plugins and their enabled/disabled status |
| `opencontext security` | Run a pip-audit vulnerability scan (`--export` to save report) |
| `opencontext cost --env <env>` | Estimate AWS costs from CloudWatch metrics (`--days` to adjust window) |
| `opencontext upgrade` | Merge updates from the upstream OpenContext template |
| `opencontext destroy --env <env>` | Tear down all deployed resources |

---

## Troubleshooting

| Issue | Solution |
|-------|----------|
| "Multiple Plugins Enabled" | Enable only one plugin in `config.yaml` |
| Claude can't connect | Verify URL includes `/mcp`, check connector is enabled in the chat |
| Lambda 500 error | Check CloudWatch logs: `opencontext logs --env staging` |
| Plugin init fails | Check API URLs, keys, and network connectivity |
| Missing `.tfvars` file | Run `opencontext configure` to generate it |

---

## Next Steps

- [CLI Reference](CLI.md) — All commands and flags in detail
- [Architecture](ARCHITECTURE.md) — System design, built-in plugins, custom plugins
- [Built-in Plugins](BUILT_IN_PLUGINS.md) — CKAN, ArcGIS Hub, and Socrata tool reference
- [Deployment](DEPLOYMENT.md) — AWS details, monitoring, cost
- [Testing](TESTING.md) — Local testing (Terminal, Claude, MCP Inspector)

---

## Support

[GitHub Issues](https://github.com/thealphacubicle/OpenContext/issues)
