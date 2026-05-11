---
description: Test patterns and conventions for the pytest suite in tests/
globs: ["tests/**/*.py"]
alwaysApply: false
---

# Testing Conventions

## Where tests live

See [`tests/README.md`](../../tests/README.md). Summary:

| Path | Purpose |
|------|---------|
| `tests/unit/` | Fast tests with mocks (`pytest.mark.unit`) |
| `tests/integration/` | Hermetic cross-boundary flows (`pytest.mark.integration`) |
| `tests/security/` | SSRF / SQL / SoQL guards (`pytest.mark.security`) |
| `tests/smoke/` | Minimal CLI/protocol smoke (`pytest.mark.smoke`) |

Markers are registered in `pyproject.toml` under `[tool.pytest.ini_options]`.

## asyncio
`asyncio_mode = "auto"` is set in `pyproject.toml`. `@pytest.mark.asyncio` is present on many existing tests (redundant but harmless); omit it in new tests.

## Test Structure
```python
class TestPluginInitialization:
    """Group tests by feature/component."""

    @pytest.fixture
    def plugin_config(self):
        """Return a dict, not a Pydantic model — let the plugin construct those."""
        return {
            "base_url": "https://data.example.com",
            "city_name": "TestCity",
            "timeout": 120,
        }

    @pytest.mark.asyncio
    async def test_initialize_succeeds_on_valid_config(self, plugin_config):
        """test_verb_noun_condition naming."""
```

## Mock Pattern
```python
from unittest.mock import AsyncMock, Mock, patch

with patch("httpx.AsyncClient") as mock_client_class:
    mock_client = AsyncMock()
    mock_response = Mock()
    mock_response.json.return_value = {"success": True, "result": []}
    mock_response.raise_for_status = Mock()
    mock_client.get = AsyncMock(return_value=mock_response)
    mock_client_class.return_value = mock_client
```

## AWS / boto3
Never instantiate real AWS clients in tests. `tests/conftest.py` provides boto3/botocore stubs — rely on those for any CLI tests touching AWS.

## Coverage
80% gate enforced by CI. These modules are excluded (see `pyproject.toml` `[tool.coverage.run]`):
- `plugins/ckan/plugin.py`
- `core/logging_utils.py`

Don't add tests purely to cover these — only when fixing real behavior.

## Parametrize
Use for boundary and invalid-input cases:
```python
@pytest.mark.parametrize("bad_input", ["'; DROP TABLE", "../etc/passwd", "a" * 100])
def test_validate_identifier_rejects_injection(self, bad_input):
    assert not _validate_identifier(bad_input)
```

## Parallel Safety
`pytest -n auto` runs tests in parallel. Tests must not share mutable state or depend on execution order.
