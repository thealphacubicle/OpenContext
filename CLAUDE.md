# OpenContext — Claude Code Guide

Extensible MCP (Model Context Protocol) framework for civic data platforms. Connects AI assistants to public open data sources (CKAN, ArcGIS, Socrata) via a plugin system, deployed as AWS Lambda.

## Key Architectural Rule: One Fork = One MCP Server

Each repo fork runs **exactly one** plugin. `core/validators.py` and `core/plugin_manager.py` will hard-fail if 0 or 2+ plugins are enabled in `config.yaml`. This is intentional — don't work around it.

## Setup

```bash
uv sync --all-extras        # install all deps including cli + dev
cp config-example.yaml config.yaml   # then edit for your data source
pre-commit install          # set up git hooks
```

## Common Commands

```bash
# Run local dev server (http://localhost:8000/mcp)
<<<<<<< HEAD
<<<<<<< HEAD
opencontext serve

# Test the running server
opencontext test --url http://localhost:8000/mcp
=======
=======
>>>>>>> 21f78af (Added DX files)
python3 scripts/local_server.py

# Test the running server
./scripts/test_streamable_http.sh
<<<<<<< HEAD
>>>>>>> 21f78af (Added DX files)
=======
>>>>>>> 21f78af (Added DX files)

# Tests
pytest tests/ -n auto --cov=core --cov=plugins --cov-fail-under=80

# Lint + format (matches CI)
ruff check core/ plugins/ server/ tests/ --fix --unsafe-fixes
ruff format core/ plugins/ server/ tests/

# CLI
<<<<<<< HEAD
<<<<<<< HEAD
opencontext validate --env staging    # validate config + Terraform before deploy
opencontext deploy --env staging
opencontext status --env staging
opencontext logs --env staging
opencontext plugin list               # list enabled/disabled plugins
opencontext security                  # pip-audit vulnerability scan
opencontext architecture              # print AWS infra diagram in terminal
=======
=======
>>>>>>> 21f78af (Added DX files)
opencontext validate        # validate config.yaml
opencontext deploy --env staging
opencontext status
opencontext logs
<<<<<<< HEAD
>>>>>>> 21f78af (Added DX files)
=======
>>>>>>> 21f78af (Added DX files)
```

## Project Layout

```
core/           # Framework kernel — interfaces, MCP server, plugin manager, validators
plugins/        # Built-in plugins: ckan/, arcgis/, socrata/
custom_plugins/ # Drop user plugins here — auto-discovered at startup
cli/            # Typer CLI (opencontext command)
server/         # HTTP adapters: local aiohttp + AWS Lambda entry point
<<<<<<< HEAD
<<<<<<< HEAD
server/adapters/ # local aiohttp dev server + AWS Lambda entry point
=======
scripts/        # local_server.py, deploy.sh, test_streamable_http.sh
>>>>>>> 21f78af (Added DX files)
=======
scripts/        # local_server.py, deploy.sh, test_streamable_http.sh
>>>>>>> 21f78af (Added DX files)
tests/          # pytest suite (80% coverage required)
terraform/aws/  # Lambda + API Gateway + IAM IaC
examples/       # Per-city config.yaml examples (Boston, Chicago, Seattle, etc.)
docs/           # Architecture, deployment, plugin authoring guides
```

Key files:
- `core/interfaces.py` — `MCPPlugin` base class; implement this for any new plugin
- `core/mcp_server.py` — JSON-RPC handler (initialize / tools/list / tools/call)
- `core/plugin_manager.py` — discovery, loading, one-plugin enforcement
- `core/validators.py` — config validation; enforces the one-plugin rule
- `server/adapters/aws_lambda.py` — Lambda entry point
<<<<<<< HEAD
<<<<<<< HEAD
- `cli/commands/serve.py` — aiohttp dev server (started via `opencontext serve`)
=======
- `scripts/local_server.py` — aiohttp dev server
>>>>>>> 21f78af (Added DX files)
=======
- `scripts/local_server.py` — aiohttp dev server
>>>>>>> 21f78af (Added DX files)

## Plugin System

Tools are auto-discovered and namespaced: `plugin_name__tool_name` (e.g. `ckan__search_datasets`).

To add a custom plugin:
1. Create `custom_plugins/my_plugin/plugin.py` inheriting `MCPPlugin`
2. Implement: `initialize`, `shutdown`, `get_tools`, `execute_tool`, `health_check`
3. Enable in `config.yaml` under `plugins.my_plugin.enabled: true`

See `docs/CUSTOM_PLUGINS.md` for full interface contract.

## Config (`config.yaml`)

```yaml
server_name: "My City OpenData MCP"
organization: "City of X"

plugins:
  ckan:                        # exactly ONE plugin enabled
    enabled: true
    base_url: "https://data.example.gov/"
    city_name: "Example City"
    timeout: 120

aws:
  region: "us-east-1"
  lambda_memory: 512
  lambda_timeout: 120

logging:
  level: "INFO"    # DEBUG for local dev
  format: "json"
```

`config.yaml` is gitignored. Never commit it — use `config-example.yaml` as the template.

## CI (GitHub Actions)

- **`ci.yml`**: ruff lint, pip-audit CVE scan, gofmt, pytest (80% coverage gate)
- **`infra.yml`**: terraform fmt/validate, tflint, tfsec — triggers on `terraform/**` changes
- **`release.yml`**: builds Go binaries (macOS/Linux/Windows) + Lambda ZIP on version tags

Replicate CI locally:
```bash
uv run ruff check core/ plugins/ server/ tests/
uv run pip-audit -r requirements.txt
uv run pytest tests/ -n auto --cov=core --cov=plugins --cov-fail-under=80
```

## Gotchas

- **Multiple plugins enabled** → hard crash at startup. Only one `enabled: true` allowed.
- **Tool prefix required** → call `ckan__search_datasets`, not `search_datasets`.
- **`config.yaml` is gitignored** → changes to it won't be committed. Use `config-example.yaml` for template changes.
- **Coverage < 80%** → CI fails. New code needs tests; check gaps with `--cov-report=html`.
<<<<<<< HEAD
<<<<<<< HEAD
- **Lambda size limit** → 250 MB max. `opencontext deploy` validates package size before uploading.
=======
- **Lambda size limit** → 250 MB max. `scripts/deploy.sh` validates before packaging.
>>>>>>> 21f78af (Added DX files)
=======
- **Lambda size limit** → 250 MB max. `scripts/deploy.sh` validates before packaging.
>>>>>>> 21f78af (Added DX files)
- **Python 3.11+ required** → match this in any new tooling or containers.
- **Go client** (`client/`) is an optional stdio-to-HTTP bridge for tools that only speak stdio MCP.
