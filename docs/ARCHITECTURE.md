# OpenContext Architecture

## Overview

OpenContext is a plugin-based MCP framework. Each fork deploys **one** MCP server with **one** plugin. This keeps deployments simple, independently scalable, and easy to maintain.

## One Fork = One MCP Server

**Enforcement:**
- `scripts/deploy.sh` validates config before deployment
- `plugin_manager.py` fails if multiple plugins enabled

**Multiple servers:** Fork again per plugin, deploy each separately.

## Components

```
core/
├── interfaces.py       # MCPPlugin, DataPlugin, ToolDefinition
├── plugin_manager.py  # Discovery, loading, routing
├── mcp_server.py      # MCP JSON-RPC handler
├── validators.py      # Config validation
└── logging_utils.py   # Structured logging

server/
├── adapters/
│   └── aws_lambda.py  # Lambda handler entry point
└── http_handler.py    # HTTP request handling

plugins/               # Built-in (CKAN)
├── ckan/
│   ├── plugin.py      # CKAN implementation
│   ├── config_schema.py
│   └── sql_validator.py
custom_plugins/        # User plugins
```

### Request Flow

```
Claude Desktop / App
    → stdio bridge (npx) or Go client
Lambda / Local Server
    → server.adapters.aws_lambda or local_server.py
    → MCP Server (core/mcp_server.py)
    → Plugin Manager
    → Plugin (e.g., CKAN)
    → External API
```

## Endpoints

| Endpoint | Auth | Use |
|----------|------|-----|
| API Gateway | Rate limit, quota | Production |
| Lambda Function URL | None | Testing |

## Plugin Interface

```python
class MCPPlugin(ABC):
    plugin_name: str
    plugin_type: PluginType
    plugin_version: str

    async def initialize() -> bool
    async def shutdown() -> None
    def get_tools() -> List[ToolDefinition]
    async def execute_tool(tool_name, arguments) -> ToolResult
    async def health_check() -> bool
```

## Configuration

Single `config.yaml`; passed to Lambda via `OPENCONTEXT_CONFIG`. Validated at deploy and runtime.

## Security & Scalability

- **API Gateway:** Rate limiting (100 burst, 50 sustained/s), configurable daily quota
- **Lambda URL:** Public—testing only
- **Stateless:** No shared state; Lambda auto-scales
- **Logging:** CloudWatch, structured JSON, request IDs
