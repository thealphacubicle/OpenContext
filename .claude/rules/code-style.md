---
description: Python code style conventions for all .py files in this repo
globs: ["**/*.py"]
alwaysApply: false
---

# Code Style — Python

## Imports
Order: stdlib → third-party → internal (`core.*`, `plugins.*`, `cli.*`, `server.*`). One blank line between groups.

```python
import asyncio
import json
from typing import Any, Dict, List, Optional

import httpx
from pydantic import BaseModel, Field

from core.interfaces import MCPPlugin, ToolDefinition
from core.plugin_manager import PluginManager
```

## Type Hints
Required on all public method signatures. Prefer `X | None` for optional types, consistent with the Python >=3.11 baseline and existing codebase usage.

## Docstrings
Google-style, triple-quoted. Class docstring before `__init__`. Methods get a one-liner minimum.

```python
class MyPlugin(MCPPlugin):
    """Brief summary of plugin purpose."""

    async def initialize(self) -> bool:
        """Initialize the HTTP client and verify connectivity."""
```

## Logging
Every module: `logger = logging.getLogger(__name__)` at module level.
Never log raw auth tokens, API keys, or passwords. Use `core/logging_utils.py` sanitizers for request/response bodies.
Always `logger.error(message, exc_info=True)` before re-raising exceptions.

## Naming
- Classes: `PascalCase`
- Functions/methods: `snake_case`
- Private: `_underscore_prefix`
- Constants: `UPPER_CASE`

## Plugin Class Attributes
`plugin_name`, `plugin_type`, `plugin_version` MUST be class-level attributes (not instance), or PluginManager won't discover the plugin:

```python
class MyPlugin(DataPlugin):
    plugin_name = "my_plugin"
    plugin_type = PluginType.CUSTOM_API
    plugin_version = "1.0.0"
```

## Error Handling
- Custom exceptions subclass `ConfigurationError` (from `core/validators.py`)
- Never swallow exceptions in plugin lifecycle methods
- Lambda intentionally crashes on `ConfigurationError` — this is by design

## Async
All plugin lifecycle methods are `async def`. Use `httpx.AsyncClient` — never `requests`.
