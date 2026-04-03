# Custom Plugins Guide

Learn how to create custom plugins for OpenContext.

## Overview

Custom plugins allow you to integrate OpenContext with your own APIs, databases, or data sources. Plugins are added to the `custom_plugins/` directory and automatically discovered by the Plugin Manager.

## Quick Start

1. Copy the template:
   ```bash
   cp custom_plugins/template/plugin_template.py custom_plugins/my_plugin/plugin.py
   ```

2. Edit `custom_plugins/my_plugin/plugin.py`:
   - Replace `MyCustomPlugin` with your class name
   - Set `plugin_name` to your plugin name
   - Implement all TODO sections

3. Add configuration to `config.yaml`:
   ```yaml
   plugins:
     my_plugin:
       enabled: true
       api_url: "https://api.example.com"
       api_key: "${MY_API_KEY}"
   ```

4. Deploy: `opencontext deploy --env staging`

## Plugin Structure

All plugins must:

1. Inherit from `MCPPlugin` (or `DataPlugin` for data sources)
2. Set class attributes: `plugin_name`, `plugin_type`, `plugin_version`
3. Implement all required methods
4. Be placed in `custom_plugins/your_plugin_name/plugin.py`

## Required Methods

### `__init__(config)`

Initialize plugin with configuration from `config.yaml`.

```python
def __init__(self, config: Dict[str, Any]) -> None:
    super().__init__(config)
    self.api_url = config.get("api_url")
    self.api_key = config.get("api_key")
```

### `async initialize() -> bool`

Set up connections, test connectivity, validate configuration.

```python
async def initialize(self) -> bool:
    self.client = httpx.AsyncClient(base_url=self.api_url)
    response = await self.client.get("/health")
    response.raise_for_status()
    self._initialized = True
    return True
```

### `async shutdown() -> None`

Clean up resources.

```python
async def shutdown(self) -> None:
    if self.client:
        await self.client.aclose()
    self._initialized = False
```

### `get_tools() -> List[ToolDefinition]`

Return list of tools your plugin provides.

```python
def get_tools(self) -> List[ToolDefinition]:
    return [
        ToolDefinition(
            name="search",
            description="Search for items",
            input_schema={
                "type": "object",
                "properties": {
                    "query": {"type": "string"},
                },
                "required": ["query"],
            },
        ),
    ]
```

**Important:** Tool names should NOT include plugin prefix. The Plugin Manager adds it automatically using double underscores (e.g., `my_plugin__search`).

### `async execute_tool(tool_name, arguments) -> ToolResult`

Execute a tool by name.

```python
async def execute_tool(self, tool_name: str, arguments: Dict[str, Any]) -> ToolResult:
    if tool_name == "search":
        query = arguments.get("query")
        results = await self._search(query)
        return ToolResult(
            content=[{"type": "text", "text": self._format_results(results)}],
            success=True,
        )
    else:
        return ToolResult(
            content=[],
            success=False,
            error_message=f"Unknown tool: {tool_name}",
        )
```

### `async health_check() -> bool`

Check if plugin is healthy.

```python
async def health_check(self) -> bool:
    try:
        response = await self.client.get("/health")
        return response.status_code == 200
    except:
        return False
```

## DataPlugin Interface

If your plugin provides data operations, inherit from `DataPlugin` instead of `MCPPlugin` directly.

`DataPlugin` extends `MCPPlugin`, so a `DataPlugin` subclass must implement **all 8 abstract methods** — the 5 from `MCPPlugin` plus the 3 defined on `DataPlugin` itself. Omitting any of these will raise a `TypeError` at startup.

### The 5 required methods inherited from `MCPPlugin`

These are the same methods documented in the [Required Methods](#required-methods) section above. `DataPlugin` does not override or relax any of them:

| Method | Signature |
|---|---|
| `initialize` | `async def initialize(self) -> bool` |
| `shutdown` | `async def shutdown(self) -> None` |
| `get_tools` | `def get_tools(self) -> List[ToolDefinition]` |
| `execute_tool` | `async def execute_tool(self, tool_name: str, arguments: Dict[str, Any]) -> ToolResult` |
| `health_check` | `async def health_check(self) -> bool` |

### The 3 additional methods defined by `DataPlugin`

| Method | Signature |
|---|---|
| `search_datasets` | `async def search_datasets(self, query: str, limit: int = 20) -> List[Dict[str, Any]]` |
| `get_dataset` | `async def get_dataset(self, dataset_id: str) -> Dict[str, Any]` |
| `query_data` | `async def query_data(self, resource_id: str, filters: Optional[Dict[str, Any]] = None, limit: int = 100) -> List[Dict[str, Any]]` |

### Minimal skeleton

```python
from typing import Any, Dict, List, Optional
from core.interfaces import DataPlugin, PluginType, ToolDefinition, ToolResult

class MyDataPlugin(DataPlugin):
    plugin_name = "my_data"
    plugin_type = PluginType.OPEN_DATA
    plugin_version = "1.0.0"

    def __init__(self, config: Dict[str, Any]) -> None:
        super().__init__(config)

    # --- 5 required methods from MCPPlugin ---

    async def initialize(self) -> bool:
        # Create clients, validate config, set self._initialized = True
        self._initialized = True
        return True

    async def shutdown(self) -> None:
        # Close clients, release resources
        self._initialized = False

    def get_tools(self) -> List[ToolDefinition]:
        # Return ToolDefinition objects for each tool this plugin exposes
        return []

    async def execute_tool(self, tool_name: str, arguments: Dict[str, Any]) -> ToolResult:
        # Dispatch to the correct tool implementation
        return ToolResult(content=[], success=False, error_message=f"Unknown tool: {tool_name}")

    async def health_check(self) -> bool:
        return self._initialized

    # --- 3 required methods from DataPlugin ---

    async def search_datasets(self, query: str, limit: int = 20) -> List[Dict[str, Any]]:
        # Return a list of dataset metadata dicts matching the query
        pass

    async def get_dataset(self, dataset_id: str) -> Dict[str, Any]:
        # Return full metadata for a single dataset
        pass

    async def query_data(
        self,
        resource_id: str,
        filters: Optional[Dict[str, Any]] = None,
        limit: int = 100,
    ) -> List[Dict[str, Any]]:
        # Return records from the specified resource
        pass
```

See `custom_plugins/template/plugin_template.py` for the canonical, fully-annotated starting point (it inherits `MCPPlugin` directly, which is fine for non-data plugins).

## Best Practices

### Error Handling

Always handle errors gracefully:

```python
try:
    result = await self._call_api()
    return ToolResult(content=[...], success=True)
except Exception as e:
    logger.error(f"Error: {e}", exc_info=True)
    return ToolResult(
        content=[],
        success=False,
        error_message=f"Operation failed: {str(e)}",
    )
```

### Logging

Use structured logging:

```python
import logging

logger = logging.getLogger(__name__)

logger.info("Plugin initialized")
logger.error("Error occurred", exc_info=True)
```

### Configuration Validation

Validate configuration in `initialize()`:

```python
async def initialize(self) -> bool:
    if not self.api_url:
        raise ValueError("api_url is required")
    # ...
```

### User-Friendly Output

Format results for clarity:

```python
def _format_results(self, data: List[Dict]) -> str:
    lines = [f"Found {len(data)} results:\n"]
    for item in data:
        lines.append(f"- {item['name']}: {item['description']}")
    return "\n".join(lines)
```

## Example: Simple API Plugin

```python
from core.interfaces import MCPPlugin, PluginType, ToolDefinition, ToolResult
import httpx

class MyAPIPlugin(MCPPlugin):
    plugin_name = "my_api"
    plugin_type = PluginType.CUSTOM_API
    plugin_version = "1.0.0"

    def __init__(self, config: Dict[str, Any]) -> None:
        super().__init__(config)
        self.api_url = config["api_url"]
        self.client = None

    async def initialize(self) -> bool:
        self.client = httpx.AsyncClient(base_url=self.api_url)
        self._initialized = True
        return True

    async def shutdown(self) -> None:
        if self.client:
            await self.client.aclose()
        self._initialized = False

    def get_tools(self) -> List[ToolDefinition]:
        return [
            ToolDefinition(
                name="get_item",
                description="Get an item by ID",
                input_schema={
                    "type": "object",
                    "properties": {
                        "item_id": {"type": "string"},
                    },
                    "required": ["item_id"],
                },
            ),
        ]

    async def execute_tool(self, tool_name: str, arguments: Dict[str, Any]) -> ToolResult:
        if tool_name == "get_item":
            item_id = arguments["item_id"]
            response = await self.client.get(f"/items/{item_id}")
            data = response.json()
            return ToolResult(
                content=[{"type": "text", "text": f"Item: {data['name']}"}],
                success=True,
            )
        return ToolResult(content=[], success=False, error_message="Unknown tool")

    async def health_check(self) -> bool:
        try:
            response = await self.client.get("/health")
            return response.status_code == 200
        except:
            return False
```

## Testing

Test your plugin locally before deploying:

```python
# test_my_plugin.py
import asyncio
from custom_plugins.my_plugin.plugin import MyAPIPlugin

async def test():
    plugin = MyAPIPlugin({"api_url": "https://api.example.com"})
    await plugin.initialize()

    tools = plugin.get_tools()
    print(f"Tools: {[t.name for t in tools]}")

    result = await plugin.execute_tool("get_item", {"item_id": "123"})
    print(f"Result: {result.success}")

asyncio.run(test())
```

## Configuration Schema

For complex plugins, create a Pydantic schema:

```python
# custom_plugins/my_plugin/config_schema.py
from pydantic import BaseModel

class MyPluginConfig(BaseModel):
    enabled: bool = False
    api_url: str
    api_key: Optional[str] = None
    timeout: int = 120
```

Use in plugin:

```python
from custom_plugins.my_plugin.config_schema import MyPluginConfig

def __init__(self, config: Dict[str, Any]) -> None:
    super().__init__(config)
    self.plugin_config = MyPluginConfig(**config)
```

## Reference

- [Plugin Template](../custom_plugins/template/plugin_template.py)
- [CKAN Plugin](../plugins/ckan/plugin.py) - Example implementation
- [Core Interfaces](../core/interfaces.py) - API reference

## Getting Help

- [FAQ](FAQ.md)
- [GitHub Issues](https://github.com/thealphacubicle/OpenContext/issues)
- [Architecture Guide](ARCHITECTURE.md)
