# Plugins Guide

OpenContext uses a plugin-based architecture. Each deployment enables **exactly one** plugin.

## Built-in: CKAN

For CKAN-based open data portals (e.g., data.boston.gov, data.gov, data.gov.uk).

### Configuration

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

### Tools

| Tool | Description |
|------|-------------|
| `ckan__search_datasets(query, limit)` | Search for datasets |
| `ckan__get_dataset(dataset_id)` | Get dataset metadata |
| `ckan__query_data(resource_id, filters, limit)` | Query data from a resource |
| `ckan__get_schema(resource_id)` | Get schema for a resource |
| `ckan__execute_sql(sql)` | Execute PostgreSQL SELECT queries (advanced) |

### SQL Execution

The `execute_sql` tool allows complex PostgreSQL queries (CTEs, window functions, joins). **Security:** Only SELECT is allowed. INSERT, UPDATE, DELETE, DROP, and other destructive operations are blocked. Resource IDs must be valid UUIDs in double quotes: `FROM "uuid-here"`.

See [CKAN API docs](https://docs.ckan.org/en/latest/api/) for details.

---

## Custom Plugins

Add your own plugins in `custom_plugins/`. They are auto-discovered.

### Quick Start

```bash
mkdir -p custom_plugins/my_plugin
cp custom_plugins/template/plugin_template.py custom_plugins/my_plugin/plugin.py
```

Edit the plugin, add config to `config.yaml` (create from `config-example.yaml` if needed), then `./scripts/deploy.sh`.

### Plugin Structure

- Inherit from `MCPPlugin` (or `DataPlugin` for data sources)
- Set: `plugin_name`, `plugin_type`, `plugin_version`
- Place in: `custom_plugins/your_plugin_name/plugin.py`
- Tool names: no prefix—Plugin Manager adds it (e.g., `my_plugin__search`)

### Required Methods

```python
def __init__(self, config: Dict[str, Any]) -> None
async def initialize() -> bool
async def shutdown() -> None
def get_tools() -> List[ToolDefinition]
async def execute_tool(tool_name, arguments) -> ToolResult
async def health_check() -> bool
```

### Example: Minimal Plugin

```python
from core.interfaces import MCPPlugin, PluginType, ToolDefinition, ToolResult

class MyAPIPlugin(MCPPlugin):
    plugin_name = "my_api"
    plugin_type = PluginType.CUSTOM_API
    plugin_version = "1.0.0"

    def __init__(self, config):
        super().__init__(config)
        self.api_url = config["api_url"]

    async def initialize(self) -> bool:
        self._initialized = True
        return True

    async def shutdown(self) -> None:
        self._initialized = False

    def get_tools(self):
        return [ToolDefinition(
            name="get_item",
            description="Get item by ID",
            input_schema={"type": "object", "properties": {"item_id": {"type": "string"}}, "required": ["item_id"]},
        )]

    async def execute_tool(self, tool_name, arguments):
        if tool_name == "get_item":
            return ToolResult(content=[{"type": "text", "text": "Result"}], success=True)
        return ToolResult(content=[], success=False, error_message="Unknown tool")

    async def health_check(self) -> bool:
        return True
```

### DataPlugin

For data sources, inherit from `DataPlugin` and implement:

```python
async def search_datasets(query, limit)
async def get_dataset(dataset_id)
async def query_data(resource_id, filters, limit)
```

### Best Practices

- **Error handling:** Return `ToolResult(success=False, error_message=...)` on failure
- **Logging:** Use `logging.getLogger(__name__)`
- **Config validation:** Validate in `initialize()`
- **Output:** Format results for clarity

### Reference

- [Plugin template](../custom_plugins/template/plugin_template.py)
- [CKAN plugin](../plugins/ckan/) – Full implementation
- [Core interfaces](../core/interfaces.py)
