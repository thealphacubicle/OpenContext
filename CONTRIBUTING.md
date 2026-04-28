# Contributing to OpenContext

## Development Setup

**Prerequisites:** Python 3.11+, [uv](https://docs.astral.sh/uv/), Git. For Go client work: Go 1.21+.

```bash
git clone https://github.com/thealphacubicle/OpenContext.git
cd OpenContext
uv sync --all-extras          # install all deps including cli + dev
cp config-example.yaml config.yaml   # edit for your data source
uv run pre-commit install            # set up lint/format hooks
```

## Branching & PRs

- Branch off `develop`: `feature/`, `bugfix/`, `docs/`, `chore/`
- Open PRs against `develop`, NOT `main`
- CI must be green before merge: lint, security audit, tests (≥ 80% coverage)

**PR checklist:**

- [ ] `uv run ruff check core/ plugins/ server/ tests/` passes
- [ ] `uv run pytest tests/ -n auto --cov=core --cov=plugins --cov-fail-under=80` passes
- [ ] New code has tests; coverage gate is enforced in CI

## Code Style

```bash
# Lint + autofix (matches CI)
uv run ruff check core/ plugins/ server/ tests/ --fix --unsafe-fixes
uv run ruff format core/ plugins/ server/ tests/

# Or via pre-commit (runs on every commit)
uv run pre-commit run --all-files
```

Hooks: Ruff (Python), yamllint, gofmt. Type hints are expected on all public methods.

## Testing

```bash
uv run pytest tests/ -n auto --cov=core --cov=plugins --cov-fail-under=80

# HTML coverage report (find gaps)
uv run pytest tests/ --cov=core --cov=plugins --cov-report=html
open htmlcov/index.html
```

- Coverage gate is 80% — enforced in CI. New code needs tests.
- Built-in plugin tests: `tests/plugins/{plugin_name}/`
- Custom plugin tests: `tests/custom_plugins/{plugin_name}/`
- Mock external HTTP (use `httpx`'s mock transport or `pytest-httpx`) — do not hit live APIs in unit tests.

## Plugin Development

### Architectural Rule: One Fork = One MCP Server

Each repo fork runs **exactly one** plugin. `core/validators.py` and `core/plugin_manager.py` will hard-fail at startup if 0 or 2+ plugins are enabled in `config.yaml`. This is intentional — don't work around it. If you need multiple data sources, fork the repo for each.

### Creating a Custom Plugin

1. Copy the template:

   ```bash
   cp custom_plugins/template/plugin_template.py custom_plugins/my_plugin/plugin.py
   ```

2. Edit `plugin.py`:
   - Set `plugin_name`, `plugin_type` (from `PluginType` enum), `plugin_version` as class attributes
   - Implement all 5 `MCPPlugin` abstract methods: `initialize`, `shutdown`, `get_tools`, `execute_tool`, `health_check`
   - If your plugin is a data source (search/query pattern), inherit `DataPlugin` instead and implement 3 additional methods: `search_datasets`, `get_dataset`, `query_data`

3. Tool naming — do **not** include the plugin prefix in tool names. The Plugin Manager adds it automatically using double underscores:

   ```python
   # In get_tools() — name your tool "search", not "my_plugin__search"
   ToolDefinition(name="search", ...)
   # Registered as: my_plugin__search
   ```

4. Add to `config.yaml`:

   ```yaml
   plugins:
     my_plugin:
       enabled: true
       api_url: "https://api.example.com"
       api_key: "${MY_API_KEY}" # use ${VAR} for secrets
   ```

5. Test locally:
   ```bash
   uv run opencontext serve        # starts at http://localhost:8000/mcp
   uv run opencontext test --url http://localhost:8000/mcp
   ```

Full interface contract and examples: [`docs/CUSTOM_PLUGINS.md`](docs/CUSTOM_PLUGINS.md)

### Adding a Built-in Plugin

Built-in plugins live in `plugins/` and ship with the framework.

1. Create `plugins/{name}/plugin.py` inheriting `MCPPlugin` or `DataPlugin`
2. Create `plugins/{name}/config_schema.py` with a Pydantic `BaseModel` for config validation
3. Add tests in `tests/plugins/{name}/`
4. Document tools and config in `docs/BUILT_IN_PLUGINS.md`

See existing plugins (`plugins/ckan/`, `plugins/arcgis/`, `plugins/socrata/`) as reference implementations.

## Commit Guidelines

Conventional Commits format:

```
feat: add SoQL GROUP BY validation to Socrata plugin
fix: handle empty response from ArcGIS aggregations endpoint
docs: add ArcGIS two-hop resolution notes to BUILT_IN_PLUGINS.md
chore: bump httpx to 0.28.0
test: add coverage for CKANPlugin.execute_sql error path
```

- Subject line ≤ 72 characters
- Use imperative mood ("add", "fix", "remove" — not "added", "fixes")
- Body is optional; use it for non-obvious reasoning

## Getting Help

- [GitHub Issues](https://github.com/thealphacubicle/OpenContext/issues)
- [Architecture Guide](docs/ARCHITECTURE.md)
- [FAQ](docs/FAQ.md)
