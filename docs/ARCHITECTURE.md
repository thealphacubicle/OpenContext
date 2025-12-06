# OpenContext Architecture

## Overview

OpenContext is a plugin-based MCP framework where each fork deploys exactly **ONE MCP server** with **ONE plugin** enabled. This document explains the system design and rationale.

## Core Principles

### One Fork = One MCP Server

**Why this rule exists:**

1. **Simplicity** - Each deployment has a single, clear purpose
2. **Independence** - Servers can be scaled, updated, and maintained independently
3. **Clarity** - No ambiguity about what a server does
4. **Isolation** - Failures in one server don't affect others

**How it's enforced:**

- **deploy.sh** - Validates config before deployment
- **plugin_manager.py** - Crashes Lambda if multiple plugins enabled

### Plugin-Based Architecture

The framework consists of:

- **Core Framework** (`core/`) - Universal, never modified by governments
- **Built-in Plugins** (`plugins/`) - CKAN
- **Custom Plugins** (`custom_plugins/`) - Government-specific plugins

## System Components

### Core Framework

```
core/
├── interfaces.py       # MCPPlugin abstract base class
├── plugin_manager.py   # Plugin discovery, loading, routing
├── mcp_server.py      # MCP JSON-RPC protocol handler
└── validators.py      # Configuration validation
```

### Plugin Manager

The Plugin Manager:

1. **Discovers** plugins in `plugins/` and `custom_plugins/`
2. **Validates** exactly ONE plugin is enabled
3. **Loads** the enabled plugin
4. **Registers** tools with plugin name prefix (e.g., `ckan.search_datasets`)
5. **Routes** tool calls to the correct plugin

### MCP Server

Handles MCP JSON-RPC protocol:

- `initialize` - Server initialization
- `tools/list` - List available tools
- `tools/call` - Execute a tool
- `ping` - Health check

### Lambda Handler

AWS Lambda entry point:

- Loads configuration from environment variable
- Initializes Plugin Manager
- Handles HTTP requests from Function URL
- Returns MCP JSON-RPC responses

## Request Flow

### Claude Desktop (stdio client)

```
Claude Desktop
    ↓ (stdio JSON-RPC)
opencontext-client (stdio bridge)
    ↓ (HTTP POST)
Lambda Function URL
    ↓
Lambda Handler
    ↓
MCP Server
    ↓
Plugin Manager
    ↓
Plugin (e.g., CKAN)
    ↓ (HTTP)
CKAN API
```

### Direct HTTP (LaunchPad/Applications)

```
Application
    ↓ (HTTP POST JSON-RPC)
Lambda Function URL
    ↓
Lambda Handler
    ↓
MCP Server
    ↓
Plugin Manager
    ↓
Plugin
```

## Plugin Interface

All plugins implement `MCPPlugin`:

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

Data plugins can extend `DataPlugin` for common operations:

```python
class DataPlugin(MCPPlugin):
    async def search_datasets(query, limit)
    async def get_dataset(dataset_id)
    async def query_data(resource_id, filters, limit)
```

## Configuration

Single `config.yaml` file:

```yaml
server_name: "MyMCP"
plugins:
  ckan:
    enabled: true # Only ONE plugin enabled
    base_url: "..."
```

Configuration is:

- Validated at deployment time (`deploy.sh`)
- Validated at runtime (`plugin_manager.py`)

## Deployment

1. **Fork repository**
2. **Edit config.yaml** - Enable ONE plugin
3. **Run deploy.sh** - Validates, packages, deploys
4. **Get Lambda URL** - Use with Claude Desktop or directly

## Why One Fork = One MCP Server?

### Alternative: Multiple Plugins Per Server

**Problems:**

- Complex configuration
- Harder to scale (all plugins scale together)
- Harder to debug (which plugin failed?)
- Tight coupling between plugins

### Our Approach: One Plugin Per Server

**Benefits:**

- Simple configuration (one plugin, one purpose)
- Independent scaling (each server scales independently)
- Clear boundaries (each server has one responsibility)
- Easy debugging (know exactly what each server does)

### Deploying Multiple Servers

To deploy multiple MCP servers:

1. Fork repository multiple times
2. Configure one plugin per fork
3. Deploy each fork separately
4. Each gets its own Lambda URL

This gives you:

- Multiple independent servers
- Each with a single, clear purpose
- Independently scalable and maintainable

## Security

- Lambda Function URLs are public (no authentication)
- Plugins can use API keys for data source authentication
- Configuration can use environment variables for secrets
- CloudWatch logs all requests

## Scalability

- Lambda auto-scales based on request volume
- Each server scales independently
- No shared state between servers
- Stateless design

## Monitoring

- CloudWatch Logs for all requests
- Structured JSON logging
- Request IDs for tracing
- Health check endpoints

## Future Enhancements

- Authentication/authorization
- Rate limiting
- Caching layer
- Additional built-in plugins (as needed)
- Plugin marketplace
