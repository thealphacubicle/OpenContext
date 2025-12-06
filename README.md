# OpenContext

**Making civic data contextualized and accessible**

OpenContext is an extensible MCP (Model Context Protocol) framework template that governments can fork to deploy MCP servers for their civic data platforms. Each fork deploys exactly **ONE MCP server** with **ONE plugin** enabled.

[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](https://opensource.org/licenses/MIT)
[![Python 3.11+](https://img.shields.io/badge/python-3.11+-blue.svg)](https://www.python.org/downloads/)
[![MCP Compatible](https://img.shields.io/badge/MCP-Compatible-green.svg)](https://modelcontextprotocol.io/)

---

## ⚠️ Important: One Fork = One MCP Server

**OpenContext enforces a strict rule: Each repository fork must deploy exactly ONE MCP server with ONE plugin enabled.**

This architecture keeps deployments:
- ✓ **Simple and focused** - Each server has a single, clear purpose
- ✓ **Independently scalable** - Scale each server based on its usage
- ✓ **Easy to maintain** - Clear boundaries and responsibilities

### To Deploy Multiple MCP Servers

1. **Fork this repository again** for each additional server
   - Example: `opencontext-opendata`, `opencontext-mbta`, `opencontext-311`

2. **Configure ONE plugin per fork**
   - Fork #1: Enable `ckan` only
   - Fork #2: Enable your custom plugin only
   - Fork #3: Enable your custom plugin only

3. **Deploy each fork separately**
   - Run `./deploy.sh` in each fork
   - Each gets its own Lambda URL

See [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md) for detailed explanation of this design decision.

---

## Quick Start

### 1. Fork This Repository

Click "Fork" on GitHub to create your own copy.

### 2. Configure Your Plugin

Edit `config.yaml` and enable **ONE** plugin:

```yaml
plugins:
  ckan:
    enabled: true
    base_url: "https://data.yourcity.gov"
    portal_url: "https://data.yourcity.gov"
    city_name: "Your City"
```

### 3. Deploy

```bash
./deploy.sh
```

The script will:
- Validate that exactly ONE plugin is enabled
- Package your code
- Deploy to AWS Lambda
- Output your Lambda URL

### 4. Use with Claude Desktop

Add to your Claude Desktop configuration:

```json
{
  "mcpServers": {
    "my-mcp-server": {
      "command": "uvx",
      "args": [
        "opencontext-client",
        "https://your-lambda-url.lambda-url.us-east-1.on.aws"
      ]
    }
  }
}
```

For direct HTTP access (LaunchPad/Applications), use the Lambda URL directly.

See [docs/QUICKSTART.md](docs/QUICKSTART.md) for detailed setup instructions.

---

## Features

### Plugin-Based Architecture

- **Universal Core Framework** - Never modified by governments
- **Built-in Plugins** - CKAN support out of the box
- **Custom Plugins** - Add your own plugins in `custom_plugins/`
- **Auto-Discovery** - Plugins are automatically discovered and loaded

### Dual Use Case Support

- **Claude Desktop** - Use stdio client wrapper (`uvx opencontext-client <url>`)
- **Applications** - Call Lambda directly via HTTP (no wrapper needed)

### Built-in Plugins

- **CKAN** - For CKAN-based open data portals (e.g., data.boston.gov, data.gov, data.gov.uk)

See [docs/BUILT_IN_PLUGINS.md](docs/BUILT_IN_PLUGINS.md) for plugin documentation.

---

## Documentation

- **[Quick Start Guide](docs/QUICKSTART.md)** - 5-minute setup guide
- **[Architecture](docs/ARCHITECTURE.md)** - System design and rationale
- **[Custom Plugins Guide](docs/CUSTOM_PLUGINS.md)** - How to create custom plugins
- **[Built-in Plugins](docs/BUILT_IN_PLUGINS.md)** - CKAN reference
- **[Deployment Guide](docs/DEPLOYMENT.md)** - Detailed deployment instructions
- **[FAQ](docs/FAQ.md)** - Common questions

---

## Examples

### Boston OpenData (CKAN)

```yaml
plugins:
  ckan:
    enabled: true
    base_url: "https://data.boston.gov"
    portal_url: "https://data.boston.gov"
    city_name: "Boston"
```

See [examples/boston-opendata/config.yaml](examples/boston-opendata/config.yaml)


### Custom Plugin

See [examples/custom-plugin/](examples/custom-plugin/) for a complete custom plugin example.

---

## Community

### Contributing

We welcome contributions! Please see our contributing guidelines (coming soon).

### License

MIT License - see [LICENSE](LICENSE) for details.

### Authors

- **Srihari Raman** - City of Boston Department of Innovation and Technology

---

## Support

- **Issues**: [GitHub Issues](https://github.com/cityofboston/opencontext/issues)
- **Documentation**: [docs/](docs/)
- **FAQ**: [docs/FAQ.md](docs/FAQ.md)

---

**OpenContext** - Making civic data contextualized and accessible
