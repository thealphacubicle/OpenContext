# OpenContext Architecture

## Overview

OpenContext is a plugin-based framework. Each deployment runs **one** server with **one** plugin. This keeps deployments simple, independently scalable, and easy to maintain.

## One Fork = One Server

**Enforcement:**
- `opencontext deploy` validates config before deployment
- `plugin_manager.py` fails at startup if multiple plugins are enabled

**Multiple servers:** Fork again per plugin, deploy each separately.

## Components

```
core/
├── interfaces.py       # MCPPlugin, DataPlugin, ToolDefinition
├── plugin_manager.py   # Discovery, loading, routing
├── mcp_server.py       # MCP JSON-RPC handler
├── validators.py       # Config validation
└── logging_utils.py   # Structured logging

server/
├── adapters/
│   └── aws_lambda.py   # Lambda handler entry point
└── http_handler.py     # HTTP request handling

plugins/                # Built-in plugins
├── ckan/               # CKAN open data portals
│   ├── plugin.py
│   ├── config_schema.py
│   └── sql_validator.py
├── arcgis/             # ArcGIS Hub portals
│   ├── plugin.py
│   ├── config_schema.py
│   └── where_validator.py
└── socrata/            # Socrata open data portals
    ├── plugin.py
    ├── config_schema.py
    └── soql_validator.py

cli/                    # Typer CLI (opencontext command)
├── main.py             # Command registration
├── commands/           # One file per command group
└── utils.py            # Shared helpers

custom_plugins/         # User plugins (auto-discovered)
├── template/
│   └── plugin_template.py

examples/               # Example configs per city
├── boston/
├── chicago/
├── seattle/
└── ...

client/                 # Go stdio-to-HTTP client (optional)
tests/                  # Unit tests
```

### Request Flow

```
Claude / MCP Client
    → Claude Connectors (HTTPS) or Go stdio client
API Gateway (REST, Regional)
    → Lambda (server.adapters.aws_lambda.lambda_handler)
    → MCP Server (core/mcp_server.py)
    → Plugin Manager (core/plugin_manager.py)
    → Plugin (CKAN / ArcGIS / Socrata / custom)
    → External API

Logs & traces:
    Lambda → CloudWatch Logs (/aws/lambda/<function-name>)
    Lambda → X-Ray (active tracing)
    Failed async invocations → SQS Dead Letter Queue
```

## Plugins

Each deployment enables **exactly one** plugin.

### Built-in: CKAN

For CKAN-based open data portals (e.g., data.gov, data.gov.uk).

**Configuration:**

```yaml
plugins:
  ckan:
    enabled: true
    base_url: "https://data.yourcity.gov"
    portal_url: "https://data.yourcity.gov"
    city_name: "Your City"
    timeout: 120
    api_key: "${CKAN_API_KEY}"  # Optional
```

**Tools:**

| Tool | Description |
|------|-------------|
| `ckan__search_datasets(query, limit)` | Search for datasets |
| `ckan__get_dataset(dataset_id)` | Get dataset metadata |
| `ckan__query_data(resource_id, filters, limit)` | Query data from a resource |
| `ckan__get_schema(resource_id)` | Get schema for a resource |
| `ckan__execute_sql(sql)` | Execute PostgreSQL SELECT queries (advanced) |

**SQL execution:** Only SELECT is allowed. Resource IDs must be valid UUIDs in double quotes: `FROM "uuid-here"`. See [CKAN API docs](https://docs.ckan.org/en/latest/api/) for details.

### Built-in: ArcGIS Hub

For ArcGIS Hub open data portals (e.g., hub.arcgis.com, data-yourcity.hub.arcgis.com).

**Configuration:**

```yaml
plugins:
  arcgis:
    enabled: true
    portal_url: "https://hub.arcgis.com"
    city_name: "Your City"
    timeout: 120
    token: "${ARCGIS_TOKEN}"  # Optional: bearer token for private items
```

**Tools:**

| Tool | Description |
|------|-------------|
| `arcgis__search_datasets(q, limit)` | Search the Hub catalog |
| `arcgis__get_dataset(dataset_id)` | Get metadata for a Hub item (32-char hex ID) |
| `arcgis__get_aggregations(field, q)` | Facet counts for type, tags, categories, or access |
| `arcgis__query_data(dataset_id, where, out_fields, limit)` | Query a Feature Service |

### Built-in: Socrata

For Socrata-based open data portals (e.g., data.cityofchicago.org, data.seattle.gov).

**Configuration:**

```yaml
plugins:
  socrata:
    enabled: true
    base_url: "https://data.yourcity.gov"
    portal_url: "https://data.yourcity.gov"
    city_name: "Your City"
    app_token: "${SOCRATA_APP_TOKEN}"  # Recommended; register at dev.socrata.com
    timeout: 30
```

**Tools:**

| Tool | Description |
|------|-------------|
| `socrata__search_datasets(query, limit)` | Search the portal catalog |
| `socrata__get_dataset(dataset_id)` | Get metadata for a dataset (4x4 ID) |
| `socrata__get_schema(dataset_id)` | Get column schema for constructing SoQL queries |
| `socrata__query_dataset(dataset_id, soql_query)` | Query data using SoQL |
| `socrata__list_categories()` | List all categories with dataset counts |
| `socrata__execute_sql(dataset_id, soql)` | Execute raw SoQL SELECT (advanced) |

### Custom Plugins

Add your own plugins in `custom_plugins/`. They are auto-discovered.

**Quick start:**

```bash
mkdir -p custom_plugins/my_plugin
cp custom_plugins/template/plugin_template.py custom_plugins/my_plugin/plugin.py
```

Edit the plugin, add config to `config.yaml` (create from `config-example.yaml` if needed), then `opencontext deploy --env staging`.

**Structure:**
- Inherit from `MCPPlugin` (or `DataPlugin` for data sources)
- Set: `plugin_name`, `plugin_type`, `plugin_version`
- Place in: `custom_plugins/your_plugin_name/plugin.py`
- Tool names: no prefix—Plugin Manager adds it (e.g., `my_plugin__search`)

**Required methods:**

```python
def __init__(self, config: Dict[str, Any]) -> None
async def initialize() -> bool
async def shutdown() -> None
def get_tools() -> List[ToolDefinition]
async def execute_tool(tool_name, arguments) -> ToolResult
async def health_check() -> bool
```

**DataPlugin:** For data sources, inherit from `DataPlugin` and implement `search_datasets`, `get_dataset`, and `query_data`.

**Best practices:** Return `ToolResult(success=False, error_message=...)` on failure. Use `logging.getLogger(__name__)`. Validate config in `initialize()`.

**Reference:**
- [Plugin template](../custom_plugins/template/plugin_template.py)
- [CKAN plugin](../plugins/ckan/) – Full implementation
- [Examples](../examples/) – Per-city configuration examples

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

## Endpoints

| Endpoint | Auth | Use |
|----------|------|-----|
| API Gateway | Throttling + usage plan quota | Production |
| Lambda Function URL | None | Testing only |

## Configuration

Single `config.yaml`; JSON-encoded and injected as the `OPENCONTEXT_CONFIG` Lambda environment variable at deploy time. Validated at deploy and runtime.

## Security & Scalability

- **API Gateway:** Configurable throttling (default: 10 burst / 5 sustained req/s) and daily quota via `api_quota_limit`, `api_burst_limit`, `api_rate_limit` Terraform variables
- **Lambda URL:** Public — testing only; use API Gateway for production
- **X-Ray:** Active tracing on all Lambda invocations and API Gateway stage
- **SQS DLQ:** Failed async invocations written to `<function-name>-dlq` for inspection
- **Stateless:** No shared state; Lambda auto-scales
- **Logging:** CloudWatch Logs, structured JSON, 14-day retention
