---
description: Test patterns and conventions for the pytest suite in tests/
globs: ["tests/**/*.py"]
alwaysApply: false
---

# Testing Conventions

## asyncio
`asyncio_mode = "auto"` is set in `pyproject.toml`. Do NOT add `@pytest.mark.asyncio` to individual async test methods — it's redundant.

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

    async def test_initialize_succeeds_on_valid_config(self, plugin_config):
        """test_verb_noun_condition naming."""
```

## Mock Pattern
```python
from unittest.mock import AsyncMock, MagicMock, patch

# Patch at the import location, not the definition location
with patch("plugins.ckan.plugin.httpx.AsyncClient") as mock_client_class:
    mock_client = AsyncMock()
    mock_response = MagicMock()
    mock_response.json.return_value = {"success": True, "result": []}
    mock_client.get = AsyncMock(return_value=mock_response)
    mock_client_class.return_value.__aenter__ = AsyncMock(return_value=mock_client)
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
