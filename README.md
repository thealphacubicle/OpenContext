# OpenContext

<p align="center">
  <img src="docs/opencontext_logo.png" alt="OpenContext Logo" width="400">
</p>

[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](https://opensource.org/licenses/MIT)
[![Python 3.11+](https://img.shields.io/badge/python-3.11+-blue.svg)](https://www.python.org/downloads/)
[![MCP Compatible](https://img.shields.io/badge/MCP-Compatible-green.svg)](https://modelcontextprotocol.io/)

---

## Quick Start

```bash
# 1. Check prerequisites (Python 3.11+, uv, AWS CLI, Terraform)
opencontext authenticate

# 2. Configure interactively (creates config.yaml + Terraform workspace)
opencontext configure

# 3. Test locally (optional)
pip install aiohttp
python3 scripts/local_server.py

# 4. Deploy
opencontext deploy --env staging
```

Connect via **Claude Connectors** (same steps on both Claude.ai and Claude Desktop):

1. Go to **Settings** → **Connectors** (or **Customize** → **Connectors** on claude.ai)
2. Click **Add custom connector**
3. Enter a name (e.g. "Your City OpenData") and your API Gateway URL (printed at the end of `opencontext deploy`)

See [Getting Started](docs/GETTING_STARTED.md) for full setup.

---

## Documentation


| Doc                                        | Description                                     |
| ------------------------------------------ | ----------------------------------------------- |
| [Getting Started](docs/GETTING_STARTED.md) | Setup and usage                                 |
| [Architecture](docs/ARCHITECTURE.md)       | System design and plugins                       |
| [Deployment](docs/DEPLOYMENT.md)           | AWS, Terraform, monitoring                      |
| [Testing](docs/TESTING.md)                 | Local testing (Terminal, Claude, MCP Inspector) |


---

## Examples

See the [examples/](examples/) directory for per-city configuration samples (Boston, Chicago, Seattle, and more).

---

## Contributing

Pre-commit hooks (optional):

```bash
pip install pre-commit
pre-commit install
```

Hooks: Ruff, yamllint, gofmt. Run manually: `pre-commit run --all-files`.

---

## License

MIT — see [LICENSE](LICENSE).

**Author:** Srihari Raman
