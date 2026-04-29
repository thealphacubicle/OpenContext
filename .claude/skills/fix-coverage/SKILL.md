---
name: fix-coverage
description: >
  Invoked when test coverage is below 80%, CI fails on the coverage gate, or the
  user asks to improve test coverage for a module. Use when the user says "coverage
  is failing", "CI is failing on tests", "increase coverage", or "add tests for X".
command: /fix-coverage
---

# Fix Coverage Workflow

## 1. Find the gaps
```bash
uv run pytest tests/ -n auto \
  --cov=core --cov=plugins \
  --cov-report=term-missing \
  --cov-report=html
```
`--cov-report=term-missing` shows uncovered line numbers inline.
`htmlcov/index.html` gives a browseable view.

## 2. Know what's excluded
These modules are in the coverage omit list (`pyproject.toml`):
- `plugins/ckan/plugin.py`
- `core/logging_utils.py`

Don't add tests for these unless you're actually fixing a bug there.

## 3. Prioritize by leverage
1. `core/` modules — highest coverage value (tested by all plugins)
2. `plugins/{arcgis,socrata}/` — not excluded, often under-tested
3. `server/` adapters
4. New code you just wrote

## 4. Write targeted tests
Follow patterns in `tests/test_ckan_plugin.py`:
- Group by `TestXxx` class
- `AsyncMock` for httpx, `MagicMock` for sync
- Patch at the import location: `patch("plugins.arcgis.plugin.httpx.AsyncClient")`
- `asyncio_mode = "auto"` means no `@pytest.mark.asyncio` needed

Focus on uncovered branches (the `term-missing` output shows which lines). One test per branch is enough — don't over-test happy paths that are already covered.

## 5. Verify
```bash
uv run pytest tests/ -n auto \
  --cov=core --cov=plugins \
  --cov-fail-under=80
```
CI gate: must pass with `--cov-fail-under=80`.
