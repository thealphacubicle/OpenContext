# Testing Guide

This guide covers three ways to test your OpenContext server locally.

## Prerequisites

Before testing:

1. Create `config.yaml` from `config-example.yaml` and enable exactly one plugin
2. Start the server: `opencontext serve`

The server runs at `http://localhost:8000/mcp`. Keep it running while you test.

---

## Method 1: Terminal (cURL)

Use the terminal to send requests directly to the server.

**Ping:**

```bash
curl -X POST http://localhost:8000/mcp \
  -H "Content-Type: application/json" \
  -d '{"jsonrpc":"2.0","id":1,"method":"ping"}'
```

**List tools:**

```bash
curl -X POST http://localhost:8000/mcp \
  -H "Content-Type: application/json" \
  -d '{"jsonrpc":"2.0","id":2,"method":"tools/list"}'
```

**Call a tool:**

```bash
curl -X POST http://localhost:8000/mcp \
  -H "Content-Type: application/json" \
  -d '{"jsonrpc":"2.0","id":3,"method":"tools/call","params":{"name":"ckan__search_datasets","arguments":{"query":"housing","limit":3}}}'
```

For a full test (initialize, list tools, call tool), run:

```bash
opencontext test --url http://localhost:8000/mcp
```

---

## Method 2: Claude (Connectors)

1. Connect via Claude Connectors (see [Getting Started](GETTING_STARTED.md))
2. Add a custom connector with URL: `http://localhost:8000/mcp`
3. Enable the connector in your conversation (click "+" → Connectors → toggle on)
4. Ask Claude to search your data or list available tools

**Note:** Localhost only works with Claude Desktop. For Claude.ai (web), use MCP Inspector or deploy first.

---

## Method 3: MCP Inspector

MCP Inspector is a web-based tool for testing MCP servers.

1. With the server running, open a new terminal
2. Run: `npx @modelcontextprotocol/inspector`
3. The Inspector UI opens in your browser (typically `http://localhost:6274`)
4. In the Inspector, select **streamable-http** as the transport
5. Enter the URL: `http://localhost:8000/mcp`
6. Use the Tools tab to list and call tools

---

## Quick Checks

Optional checks before starting the server.

**Config validation:**

```bash
python3 -c "
import yaml
from core.validators import load_and_validate_config
config = load_and_validate_config('config.yaml')
print('Config valid:', config['server_name'])
"
```

**Plugin loading:**

```bash
python3 -c "
import asyncio, yaml
from core.plugin_manager import PluginManager
async def t():
    with open('config.yaml') as f: config = yaml.safe_load(f)
    pm = PluginManager(config)
    await pm.load_plugins()
    print('Tools:', [t['name'] for t in pm.get_all_tools()])
    await pm.shutdown()
asyncio.run(t())
"
```

---

## Unit Tests

With dev dependencies installed (`uv sync --all-extras`):

```bash
uv run pytest
uv run pytest tests/test_plugin_manager.py -v
uv run pytest --cov=core --cov=plugins
```

`sqlparse` and other test-related packages are pulled in via `pyproject.toml`; you do not need a separate `pip install` for them when using `uv sync`.

---

## Testing Against Production

To test a deployed server, use the API Gateway URL:

```bash
API_GW_URL=$(cd terraform/aws && terraform output -raw api_gateway_url)
curl -X POST $API_GW_URL \
  -H "Content-Type: application/json" \
  -d '{"jsonrpc":"2.0","id":1,"method":"ping"}'
```

See [Deployment](DEPLOYMENT.md) for how to get the URL.
