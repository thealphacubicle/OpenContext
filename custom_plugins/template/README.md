# Custom Plugin Template

This directory contains a template for creating custom OpenContext plugins.

## Quick Start

1. Copy the template to your plugin directory:
   ```bash
   cp custom_plugins/template/plugin_template.py custom_plugins/my_plugin/plugin.py
   ```

2. Edit `custom_plugins/my_plugin/plugin.py`:
   - Replace `MyCustomPlugin` with your plugin class name
   - Set `plugin_name` to your plugin name
   - Implement all TODO sections
   - Add your tool definitions and implementations

3. Add plugin configuration to `config.yaml`:
   ```yaml
   plugins:
     my_plugin:
       enabled: true
       api_url: "https://api.example.com"
       api_key: "${MY_API_KEY}"
   ```

4. Enable your plugin in `config.yaml` (set `enabled: true`)

5. Deploy: `./deploy.sh`

## Required Methods

All plugins must implement these methods:

- `__init__(config)`: Initialize with configuration
- `async initialize()`: Set up connections, test connectivity
- `async shutdown()`: Clean up resources
- `get_tools()`: Return list of tool definitions
- `async execute_tool(tool_name, arguments)`: Execute a tool
- `async health_check()`: Check plugin health

See `plugin_template.py` for detailed comments and examples.

## Best Practices

- Use type hints for all methods
- Validate configuration in `__init__` or `initialize()`
- Handle errors gracefully and return meaningful error messages
- Log important events (use `logger` from `logging`)
- Format tool results in a user-friendly way
- Test your plugin locally before deploying

## Examples

See the built-in plugin for reference:
- `plugins/ckan/plugin.py` - CKAN open data portal plugin

For more details, see `docs/CUSTOM_PLUGINS.md`.

