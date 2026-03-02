# Getting Started

Get your OpenContext MCP server running in under 10 minutes.

## Prerequisites

- Python 3.11+
- Terraform >= 1.0 (for deployment)
- AWS CLI configured (for deployment)
- Node.js and npm (for Streamable HTTP transport—no binary needed)

## Quick Path: Local Testing

Test the MCP server locally before deploying.

### 1. Configure Your Plugin

Create `config.yaml` from the template and enable **ONE** plugin:

```bash
cp config-example.yaml config.yaml
```

Edit `config.yaml`. For CKAN:

```yaml
plugins:
  ckan:
    enabled: true
    base_url: "https://data.boston.gov"
    portal_url: "https://data.boston.gov"
    city_name: "Boston"
    timeout: 120
```

### 2. Start the Local Server

```bash
pip install aiohttp
python3 scripts/local_server.py
```

The server runs at `http://localhost:8000/mcp`. Keep this terminal open.

### 3. Connect Claude Desktop

Add to your Claude Desktop config (`~/Library/Application Support/Claude/claude_desktop_config.json` on macOS):

**Option A: Streamable HTTP (recommended—no binary)**

```json
{
  "mcpServers": {
    "OpenContext Local": {
      "command": "npx",
      "args": [
        "-y",
        "@modelcontextprotocol/server-stdio-to-http",
        "--transport",
        "streamable-http",
        "http://localhost:8000/mcp"
      ]
    }
  }
}
```

**Option B: Go client binary**

```json
{
  "mcpServers": {
    "OpenContext Local": {
      "command": "/path/to/opencontext-client",
      "args": ["http://localhost:8000"]
    }
  }
}
```

The Go client auto-appends `/mcp`. Restart Claude Desktop after config changes.

### 4. Verify

```bash
curl -X POST http://localhost:8000/mcp \
  -H "Content-Type: application/json" \
  -d '{"jsonrpc":"2.0","id":1,"method":"ping"}'
```

Or run the full test: `./scripts/test_streamable_http.sh`

---

## Production Deployment

### 1. Fork & Configure

1. Fork the [OpenContext repository](https://github.com/thealphacubicle/OpenContext)
2. Clone your fork
3. Create config: `cp config-example.yaml config.yaml`
4. Edit `config.yaml` with **ONE** plugin enabled

### 2. Deploy to AWS

```bash
./scripts/deploy.sh
```

The script validates config, packages code, and deploys to AWS Lambda. You'll receive:
- **Lambda Function URL** – for local/testing (no auth)
- **API Gateway URL** – for production (API key, rate limiting)

### 3. Connect Claude Desktop (Production)

**Production (API Gateway—recommended):**

```bash
cd terraform/aws
terraform output -raw api_gateway_url
```

Use the full URL from `terraform output` (it already includes `/mcp`):

```json
{
  "mcpServers": {
    "Boston OpenData": {
      "command": "npx",
      "args": [
        "-y",
        "@modelcontextprotocol/server-stdio-to-http",
        "--transport",
        "streamable-http",
        "https://YOUR-API-GATEWAY-URL"
      ]
    }
  }
}
```

**Testing (Lambda URL—no auth):**

```json
{
  "mcpServers": {
    "Boston OpenData": {
      "command": "npx",
      "args": [
        "-y",
        "@modelcontextprotocol/server-stdio-to-http",
        "--transport",
        "streamable-http",
        "https://your-lambda-url.lambda-url.us-east-1.on.aws/mcp"
      ]
    }
  }
}
```

### 4. Client Binary (Alternative)

Download from [GitHub Releases](https://github.com/thealphacubicle/OpenContext/releases) or build:

```bash
cd client && make build
```

```json
{
  "mcpServers": {
    "Boston OpenData": {
      "command": "/path/to/opencontext-client",
      "args": ["https://your-lambda-url.lambda-url.us-east-1.on.aws"]
    }
  }
}
```

---

## Troubleshooting

| Issue | Solution |
|-------|----------|
| `ModuleNotFoundError: aiohttp` | `pip install aiohttp` |
| "Multiple Plugins Enabled" | Enable only ONE plugin in `config.yaml` |
| Claude can't connect | Verify URL includes `/mcp`, restart Claude Desktop |
| Lambda 500 error | Check CloudWatch logs, validate config |

---

## Next Steps

- [Deployment Guide](DEPLOYMENT.md) – AWS details, monitoring, cost
- [Plugins Guide](PLUGINS.md) – CKAN reference and custom plugins
- [Testing Guide](TESTING.md) – Unit tests, curl examples
- [Architecture](ARCHITECTURE.md) – System design
