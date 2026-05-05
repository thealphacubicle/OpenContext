---
description: Plugin interface rules and authoring conventions for plugins/ and custom_plugins/
globs: ["plugins/**/*.py", "custom_plugins/**/*.py"]
alwaysApply: false
---

# Plugin Development

## One-Plugin Rule
Only one plugin may have `enabled: true` in `config.yaml`. `core/validators.py:validate_plugin_count()` enforces this at startup and hard-crashes. This is intentional — do not work around it.

## Required Class-Level Attributes
```python
class MyPlugin(DataPlugin):
    plugin_name = "my_plugin"           # Used as tool prefix: my_plugin__search
    plugin_type = PluginType.OPEN_DATA  # or CUSTOM_API, DATABASE, ANALYTICS
    plugin_version = "1.0.0"
```
Without these as class-level attrs, `PluginManager` won't discover the class.

## Required Abstract Methods

| Method | Signature | Notes |
|--------|-----------|-------|
| `initialize` | `async def initialize(self) -> bool` | Return `False` on failure, don't raise |
| `shutdown` | `async def shutdown(self) -> None` | Close HTTP clients, cleanup |
| `get_tools` | `def get_tools(self) -> List[ToolDefinition]` | Synchronous. No plugin prefix in tool names. |
| `execute_tool` | `async def execute_tool(self, tool_name: str, arguments: Dict[str, Any]) -> ToolResult` | Dispatch by tool_name |
| `health_check` | `async def health_check(self) -> bool` | Lightweight ping only |

## Tool Naming
`get_tools()` returns tool names WITHOUT the plugin prefix — e.g., `"search_datasets"`, not `"ckan__search_datasets"`. PluginManager auto-prefixes. MCP clients call the prefixed form.

## Config Pattern
```python
def __init__(self, config: Dict[str, Any]) -> None:
    super().__init__(config)
    self.plugin_config = MyPluginConfig(**config)  # Validate immediately with Pydantic
    self.client: Optional[httpx.AsyncClient] = None
```

## Input Validation
Validate all user-supplied identifiers before use in any query:
```python
import re
_SAFE_IDENTIFIER = re.compile(r'^[a-zA-Z_][a-zA-Z0-9_]{0,63}$')

def _validate_identifier(value: str) -> bool:
    return bool(_SAFE_IDENTIFIER.match(value))
```
See `plugins/ckan/sql_validator.py` for the full reference pattern.

## HTTP Client
```python
async def initialize(self) -> bool:
    self.client = httpx.AsyncClient(base_url=self.plugin_config.base_url)
    # verify connectivity...

async def shutdown(self) -> None:
    if self.client:
        await self.client.aclose()
```
Use `tenacity` for retries on transient failures.
