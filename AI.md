# AI.md

OpenContext is an extensible MCP (Model Context Protocol) framework that exposes
public open-data portals (CKAN, ArcGIS Hub, Socrata) to AI assistants. Stack:
Python 3.11+ managed with `uv`, Typer CLI, aiohttp dev server, deployed to AWS
(Lambda + API Gateway) or GCP (Cloud Functions gen2) via Terraform (`--cloud`).

## Directory map (non-obvious only)

- `custom_plugins/` — drop-in user plugins; auto-discovered at startup and copied into the Lambda bundle by `cli/commands/deploy.py`
- `server/adapters/` — runtime entry points: `aws_lambda.py` for production, local aiohttp server for dev
- `examples/` — per-city example `config.yaml` files
- `client/` — optional Go stdio↔HTTP MCP bridge for stdio-only clients
- `.claude/` — Claude Code project config (`settings.json`, glob-scoped `rules/`, `skills/`, `agents/`); see `CLAUDE.md`
- `.cursor/` — Cursor rules; see `.cursor/rules/project.mdc`

Self-evident dirs (`core/`, `plugins/`, `cli/`, `tests/`, `docs/`, `terraform/`) are intentionally omitted.

## Dev commands

- Install full dev deps (matches CI): `uv sync --all-extras`
- CLI-only install: `uv sync --extra cli`
- Bootstrap config: `cp config-example.yaml config.yaml` then edit; optional `uv run pre-commit install`
- Local MCP server (http://localhost:8000/mcp): `uv run opencontext serve`
- Smoke test running server: `uv run opencontext test --url http://localhost:8000/mcp`
- Tests with CI coverage gate: `uv run pytest tests/ -n auto --cov=core --cov=plugins --cov=server --cov-report=term-missing --cov-fail-under=80`
- Targeted suites by marker: `uv run pytest tests/unit -m unit -v` (also `integration`, `security`, `smoke`)
- Go client tests: `cd client && go test ./...`
- Lint as CI runs it (no autofix): `uv run ruff check core/ plugins/ server/ tests/`
- Local autofix + format: `uv run ruff check core/ plugins/ server/ tests/ --fix --unsafe-fixes && uv run ruff format core/ plugins/ server/ tests/`
- CVE audit (CI parity): `uv run pip-audit -r requirements.txt`
- Validate before deploy: `uv run opencontext validate --env staging`
- Deploy: `uv run opencontext deploy --env staging` (requires TTY; prompts for confirmation)

`--env` defaults to `staging` on every command that accepts it.
`--cloud` defaults to `aws` on every command that accepts it.

## Hard constraints

- **Exactly one `plugins.*.enabled: true`** in `config.yaml`. Enforced at server startup (`core/validators.py`, `core/plugin_manager.py`) and pre-deploy (`cli/commands/deploy.py::_validate_single_plugin`). Multiple data sources require forking the repo, not toggling more flags.
- **`config.yaml` is gitignored.** Never commit it. Template-level changes go in `config-example.yaml`.
- **Branch off `develop`; PRs target `develop`, not `main`.** Prefixes: `feature/`, `bugfix/`, `docs/`, `chore/`.
- **CI fails below 80% coverage** on `core`, `plugins`, `server`. New code needs tests. `pyproject.toml` `[tool.coverage.run].omit` documents which modules are excluded — adding logic to those without un-omitting will not earn coverage.
- **MCP tool names are namespaced `plugin__tool_name`** (double underscore, prepended automatically). Plugins must NOT include the prefix in their own `get_tools()` names.
- **Lambda packaging targets `x86_64-manylinux2014` + Python 3.11.** `cli/commands/deploy.py::_package_lambda` runs `uv pip install -r requirements.txt --python-platform x86_64-manylinux2014 --python-version 3.11`. New deps must be wheel-compatible with that target — local `uv sync` success is not sufficient proof.
- **Lambda bundle uses `requirements.txt`, not the `uv` lockfile.** Update both when adding deps; `pip-audit` in CI scans `requirements.txt`.
- **`asyncio_mode = "auto"`** is set in `pyproject.toml`. `@pytest.mark.asyncio` is present on existing tests (redundant but harmless); omit it in new tests.
- **Never modify `config.yaml`, `.env*`, `terraform/**/*.tfvars`, or `terraform/**/*.tfstate*`** from agent tools; these are denied in `.claude/settings.json` and contain secrets / state.
- **Plugins inherit `MCPPlugin`** (`core/interfaces.py`) and must implement `initialize`, `shutdown`, `get_tools`, `execute_tool`, `health_check`. Data-source plugins inherit `DataPlugin` and add `search_datasets`, `get_dataset`, `query_data`.
- **`PluginType` enum values** (`core/interfaces.py`): `OPEN_DATA`, `CUSTOM_API`, `DATABASE`, `ANALYTICS`.

## Pointers

- `@docs/GETTING_STARTED.md`
- `@docs/QUICKSTART.md`
- `@docs/CLI.md`
- `@docs/ARCHITECTURE.md`
- `@docs/BUILT_IN_PLUGINS.md`
- `@docs/CUSTOM_PLUGINS.md`
- `@docs/DEPLOYMENT.md`
- `@docs/TESTING.md`
- `@docs/FAQ.md`
- `@tests/README.md`
- `@CONTRIBUTING.md`
- `@.claude/settings.json`
- `@.claude/rules/`
- `@.claude/skills/`
- `@.claude/agents/`
