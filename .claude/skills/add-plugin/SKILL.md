---
name: add-plugin
description: >
  Invoked when the user wants to create a new plugin, add a new data source,
  extend OpenContext with a custom integration, or implement a new MCPPlugin
  or DataPlugin subclass in custom_plugins/. Use when the user says things like
  "add a plugin", "create a custom plugin", "integrate with [service]", or
  "implement a new data source".
command: /add-plugin
---

# Add Plugin Workflow

## Prerequisites
- `config.yaml` exists with exactly one other plugin disabled (or none)
- `uv sync --all-extras` already run

## Steps

### 1. Scaffold
```bash
cp -r custom_plugins/template/plugin_template.py custom_plugins/{name}/plugin.py
touch custom_plugins/{name}/__init__.py
```
Create `custom_plugins/{name}/config_schema.py`:
```python
from pydantic import BaseModel, Field
from typing import Optional

class {Name}PluginConfig(BaseModel):
    enabled: bool = Field(default=False)
    base_url: str = Field(...)
    # add plugin-specific fields
```

### 2. Implement plugin.py
Set class-level attributes first — PluginManager won't discover the class without them:
```python
class {Name}Plugin(DataPlugin):
    plugin_name = "{name}"
    plugin_type = PluginType.OPEN_DATA   # or CUSTOM_API, DATABASE, ANALYTICS
    plugin_version = "1.0.0"
```

Implement all 5 abstract methods (exact signatures from `core/interfaces.py`):
- `async def initialize(self) -> bool` — open HTTP client, verify connectivity; return `False` (not raise) on failure
- `async def shutdown(self) -> None` — `await self.client.aclose()`
- `def get_tools(self) -> List[ToolDefinition]` — tool names WITHOUT plugin prefix (e.g. `"search_datasets"`)
- `async def execute_tool(self, tool_name: str, arguments: Dict[str, Any]) -> ToolResult`
- `async def health_check(self) -> bool` — lightweight ping

Validate user-supplied identifiers against `^[a-zA-Z_][a-zA-Z0-9_]{0,63}$` before any query. See `plugins/ckan/sql_validator.py`.

### 3. Enable in config.yaml
```yaml
plugins:
  {name}:
    enabled: true   # disable all others — one-plugin rule is hard-enforced
    base_url: "https://..."
```

### 4. Smoke test locally
```bash
uv run opencontext serve
# in another terminal:
uv run opencontext test --url http://localhost:8000/mcp
```

### 5. Write tests
Create `tests/test_{name}_plugin.py` following the structure in `tests/test_ckan_plugin.py`:
- Group by `TestXxx` classes
- Use `AsyncMock` for httpx calls (see mock pattern in `.claude/rules/testing.md`)
- Fixtures return dicts, not Pydantic models

```bash
uv run pytest tests/test_{name}_plugin.py -v --cov=custom_plugins --cov-report=term-missing
```

### 6. Verify coverage gate still passes
```bash
uv run pytest tests/ -n auto --cov=core --cov=plugins --cov-fail-under=80
```

## Common Mistakes
- Plugin class has instance attrs instead of class-level attrs → PluginManager skips it
- Tool name includes plugin prefix in `get_tools()` → double-prefixed MCP tool names
- `initialize()` raises on failure instead of returning `False` → Lambda crash with unhelpful error
- Missing `__init__.py` in `custom_plugins/{name}/` → import error at startup
