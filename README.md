# OpenContext

<p align="center">
  <img src="docs/opencontext_logo.png" alt="OpenContext Logo" width="400">
</p>

[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](https://opensource.org/licenses/MIT)
[![Python 3.11+](https://img.shields.io/badge/python-3.11+-blue.svg)](https://www.python.org/downloads/)
[![MCP Compatible](https://img.shields.io/badge/MCP-Compatible-green.svg)](https://modelcontextprotocol.io/)

---

## Quick Start

Install [uv](https://docs.astral.sh/uv/getting-started/installation/) first, then:

```bash
# 0. Install the CLI (project + CLI extras into .venv)
git clone https://github.com/thealphacubicle/OpenContext.git
cd OpenContext
uv sync --extra cli

# 1. Check prerequisites (Python 3.11+, uv, AWS CLI, Terraform)
uv run opencontext authenticate

# 2. Configure interactively (creates config.yaml + Terraform workspace)
uv run opencontext configure

# 3. Test locally (optional)
uv run opencontext serve

# 4. Deploy
uv run opencontext deploy --env staging
```

Connect via **Claude Connectors** (same steps on both Claude.ai and Claude Desktop):

1. Go to **Settings** → **Connectors** (or **Customize** → **Connectors** on claude.ai)
2. Click **Add custom connector**
3. Enter a name (e.g. "Your City OpenData") and your API Gateway URL (printed at the end of `opencontext deploy`)

See [Getting Started](docs/GETTING_STARTED.md) for full setup.

---

## Using uv and `requirements.txt`

- **Default workflow:** `uv sync --extra cli` (or `uv sync --all-extras` for development) installs from `pyproject.toml` and the lockfile into `.venv`. Run CLI and tools with `uv run …` when you want to use the project environment without activating the venv.
- **`requirements.txt`** is kept for **Lambda packaging** ( `opencontext deploy` installs with `uv pip install … -r requirements.txt` ) and **security scans** in CI (e.g. `uv run pip-audit -r requirements.txt`). You usually do not install from `requirements.txt` by hand unless debugging those flows.

Details: [Getting Started — full walkthrough](docs/GETTING_STARTED.md) (section *Using uv with requirements.txt*).

---

## Documentation


| Doc                                        | Description                                     |
| ------------------------------------------ | ----------------------------------------------- |
| [Getting Started](docs/GETTING_STARTED.md) | Setup and usage                                 |
| [CLI Reference](docs/CLI.md)               | All CLI commands and flags                      |
| [Architecture](docs/ARCHITECTURE.md)       | System design and plugins                       |
| [Built-in Plugins](docs/BUILT_IN_PLUGINS.md) | CKAN, ArcGIS Hub, Socrata plugin details      |
| [Custom Plugins](docs/CUSTOM_PLUGINS.md)   | How to write your own plugin                    |
| [Deployment](docs/DEPLOYMENT.md)           | AWS, Terraform, monitoring                      |
| [Testing](docs/TESTING.md)                 | Local testing (Terminal, Claude, MCP Inspector) |


---

## Contributing

Pre-commit hooks (optional):

```bash
uv sync --all-extras   # includes pre-commit; use --extra cli if you only need the CLI
uv run pre-commit install
```

Hooks: Ruff, yamllint, gofmt. Run manually: `uv run pre-commit run --all-files`.

---

## License

MIT — see [LICENSE](LICENSE).

**Author:** Srihari Raman
