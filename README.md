# OpenContext

**Making civic data contextualized and accessible**

OpenContext is an extensible MCP (Model Context Protocol) framework template that governments can fork to deploy MCP servers for their civic data platforms. Each fork deploys **one** MCP server with **one** plugin.

[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](https://opensource.org/licenses/MIT)
[![Python 3.11+](https://img.shields.io/badge/python-3.11+-blue.svg)](https://www.python.org/downloads/)
[![MCP Compatible](https://img.shields.io/badge/MCP-Compatible-green.svg)](https://modelcontextprotocol.io/)

---

## One Fork = One MCP Server

Each deployment has exactly one plugin. To run multiple servers (e.g., CKAN + custom), fork again and deploy each separately. See [Architecture](docs/ARCHITECTURE.md).

---

## Quick Start

```bash
# 1. Configure (create config, enable ONE plugin)
cp config-example.yaml config.yaml
# Edit config.yaml - set enabled: true for one plugin

# 2. Test locally
pip install aiohttp
python3 scripts/local_server.py

# 3. Deploy
./scripts/deploy.sh
```

Add to Claude Desktop (`~/Library/Application Support/Claude/claude_desktop_config.json`):

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

Get the URL from: `cd terraform/aws && terraform output -raw api_gateway_url`

See [Getting Started](docs/GETTING_STARTED.md) for full setup (local testing, Lambda URL, Go client).

---

## Features

- **Plugin-based:** CKAN built-in; add custom plugins in `custom_plugins/`
- **Dual transport:** Streamable HTTP (npx, no binary) or Go stdio client
- **Production-ready:** API Gateway with API key and rate limiting
- **CKAN tools:** search_datasets, get_dataset, query_data, get_schema, execute_sql

---

## Documentation

| Doc | Description |
|-----|-------------|
| [Getting Started](docs/GETTING_STARTED.md) | Local testing + production setup |
| [Plugins](docs/PLUGINS.md) | CKAN reference + custom plugin guide |
| [Deployment](docs/DEPLOYMENT.md) | AWS, Terraform, monitoring |
| [Testing](docs/TESTING.md) | Unit tests, curl, scripts |
| [Architecture](docs/ARCHITECTURE.md) | System design |
| [FAQ](docs/FAQ.md) | Common questions |

---

## Examples

- **Boston OpenData (CKAN):** [examples/boston-opendata/config.yaml](examples/boston-opendata/config.yaml)
- **Custom plugin:** [examples/custom-plugin/](examples/custom-plugin/)

---

## Contributing

Pre-commit hooks (optional):

```bash
pip install pre-commit
pre-commit install
```

Hooks: Ruff, yamllint, gofmt. Run manually: `pre-commit run --all-files`.

---

## License

MIT — see [LICENSE](LICENSE).

**Author:** Srihari Raman, City of Boston Department of Innovation and Technology
