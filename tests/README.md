# OpenContext test layout

Tests are grouped by intent (not only by component):

| Directory | Role |
|-----------|------|
| [`tests/unit/`](unit/) | Isolated logic; mocks for I/O |
| [`tests/integration/`](integration/) | Hermetic cross-boundary flows (HTTP ↔ MCP ↔ plugins, Lambda adapter, CLI smoke server, Terraform contract checks) |
| [`tests/security/`](security/) | SSRF, SQL/SoQL injection guards |
| [`tests/smoke/`](smoke/) | Minimal CLI/protocol smoke checks |

Pytest markers (`pyproject.toml`): `unit`, `integration`, `security`, `smoke`.

Hermetic integration tests use the in-repo plugin [`custom_plugins/integration_test_fake/`](../custom_plugins/integration_test_fake/) (always disabled in real configs; enabled only via test fixtures / `OPENCONTEXT_CONFIG` JSON).

Examples (always via `uv`):

```bash
uv run pytest tests/
uv run pytest tests/integration -m integration
uv run pytest tests/unit -m unit
uv run pytest tests/security -m security
```

Shared stubs/fixtures: [`conftest.py`](conftest.py).
