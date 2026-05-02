"""Security tests for aggregate_data SQL-injection guards in the CKAN plugin.

Covers _validate_identifier, _validate_metric_expr, and integration paths
through aggregate_data() to confirm validation fires before any HTTP call.
"""

import pytest
from unittest.mock import AsyncMock, Mock, patch

from plugins.ckan.plugin import CKANPlugin, _validate_identifier, _validate_metric_expr


# ── Fixtures ───────────────────────────────────────────────────────────────────

CKAN_CONFIG = {
    "base_url": "https://data.example.com",
    "portal_url": "https://data.example.com",
    "city_name": "TestCity",
    "timeout": 120,
}

RESOURCE_ID = "abc-123-def-456-ghi-789-012-345-678-901"


# ── _validate_identifier ───────────────────────────────────────────────────────


class TestValidateIdentifier:
    """Unit tests for the _validate_identifier module-level function."""

    @pytest.mark.parametrize(
        "name",
        [
            "neighborhood",
            "street_name",
            "_field",
            "a",
            "field123",
        ],
        ids=[
            "simple-word",
            "underscore-separated",
            "leading-underscore",
            "single-char",
            "alphanumeric",
        ],
    )
    def test_valid_identifier_passes(self, name):
        """Valid identifiers are returned unchanged without raising."""
        result = _validate_identifier(name)
        assert result == name

    @pytest.mark.parametrize(
        "name",
        [
            "neighborhood; DROP TABLE users--",
            "field' OR '1'='1",
            "field name",
            "1field",
            "a" * 65,
            "",
            "field;SELECT",
            "fie--ld",
        ],
        ids=[
            "sql-injection-drop-table",
            "sql-injection-or-clause",
            "contains-space",
            "starts-with-digit",
            "too-long-65-chars",
            "empty-string",
            "semicolon-select",
            "double-dash",
        ],
    )
    def test_invalid_identifier_raises_value_error(self, name):
        """Malformed or injected identifiers raise ValueError."""
        with pytest.raises(ValueError, match="Invalid identifier"):
            _validate_identifier(name)


# ── _validate_metric_expr ──────────────────────────────────────────────────────


class TestValidateMetricExpr:
    """Unit tests for the _validate_metric_expr module-level function."""

    @pytest.mark.parametrize(
        "expr",
        [
            "count(*)",
            "COUNT(*)",
            "sum(amount)",
            "avg(score)",
            "min(value)",
            "max(price)",
            "stddev(val)",
            "variance(x)",
        ],
        ids=[
            "count-star-lower",
            "count-star-upper",
            "sum",
            "avg",
            "min",
            "max",
            "stddev",
            "variance",
        ],
    )
    def test_valid_metric_expr_passes(self, expr):
        """All allowed aggregate expressions pass without raising."""
        result = _validate_metric_expr(expr)
        assert result == expr

    @pytest.mark.parametrize(
        "expr",
        [
            "pg_sleep(5)",
            "now()",
            "1=1",
            "count(*); DROP TABLE users",
            "upper(field)",
            "(SELECT 1)",
            "",
            "sum()",
        ],
        ids=[
            "pg-sleep",
            "now-function",
            "bare-condition",
            "count-then-drop",
            "upper-function",
            "subselect",
            "empty-string",
            "sum-empty-arg",
        ],
    )
    def test_invalid_metric_expr_raises_value_error(self, expr):
        """Disallowed or injected metric expressions raise ValueError."""
        with pytest.raises(ValueError, match="Disallowed metric expression"):
            _validate_metric_expr(expr)


# ── aggregate_data() integration ───────────────────────────────────────────────


class TestAggregateDataIntegration:
    """Integration-style tests calling aggregate_data() on a CKANPlugin instance.

    Validation must raise ValueError before any SQL is assembled or any HTTP
    call is dispatched.
    """

    @pytest.fixture()
    def plugin(self):
        """Uninitialized CKANPlugin with no live HTTP client."""
        return CKANPlugin(CKAN_CONFIG)

    # ── error paths — no HTTP mock needed ─────────────────────────────────────

    @pytest.mark.asyncio
    async def test_injected_group_by_raises_before_http(self, plugin):
        """A SQL-injected group_by field raises ValueError before any HTTP call."""
        with pytest.raises(ValueError, match="Invalid identifier"):
            await plugin.aggregate_data(
                resource_id=RESOURCE_ID,
                group_by=["field; DROP TABLE x--"],
                metrics={"total": "count(*)"},
            )

    @pytest.mark.asyncio
    async def test_injected_metric_expr_raises_before_http(self, plugin):
        """A disallowed metric expression raises ValueError before any HTTP call."""
        with pytest.raises(ValueError, match="Disallowed metric expression"):
            await plugin.aggregate_data(
                resource_id=RESOURCE_ID,
                group_by=["category"],
                metrics={"x": "count(*) UNION SELECT 1"},
            )

    @pytest.mark.asyncio
    async def test_injected_filter_key_raises_before_http(self, plugin):
        """A SQL-injected filters dict key raises ValueError before any HTTP call."""
        with pytest.raises(ValueError, match="Invalid identifier"):
            await plugin.aggregate_data(
                resource_id=RESOURCE_ID,
                group_by=["category"],
                metrics={"total": "count(*)"},
                filters={"field; DROP TABLE x": "val"},
            )

    @pytest.mark.asyncio
    async def test_injected_having_key_raises_before_http(self, plugin):
        """A SQL-injected having dict key raises ValueError before any HTTP call."""
        with pytest.raises(ValueError, match="Invalid identifier"):
            await plugin.aggregate_data(
                resource_id=RESOURCE_ID,
                group_by=["category"],
                metrics={"total": "count(*)"},
                having={"expr; DROP TABLE x": 10},
            )

    @pytest.mark.asyncio
    async def test_injected_order_by_raises_before_http(self, plugin):
        """A SQL-injected order_by value raises ValueError before any HTTP call."""
        with pytest.raises(ValueError, match="Invalid identifier"):
            await plugin.aggregate_data(
                resource_id=RESOURCE_ID,
                group_by=["category"],
                metrics={"total": "count(*)"},
                order_by="field; DROP TABLE x",
            )

    # ── happy path — mock execute_sql, assert it is reached ───────────────────

    @pytest.mark.asyncio
    async def test_valid_inputs_reach_execute_sql(self, plugin):
        """Clean inputs pass all validators and delegate to execute_sql."""
        mock_execute_sql = AsyncMock(
            return_value={
                "success": True,
                "records": [{"neighborhood": "Downtown", "total": 42}],
                "fields": [],
            }
        )

        with patch("httpx.AsyncClient") as mock_client_class:
            mock_client = AsyncMock()
            mock_response_init = Mock()
            mock_response_init.json.return_value = {"success": True}
            mock_response_init.raise_for_status = Mock()
            mock_client.post = AsyncMock(return_value=mock_response_init)
            mock_client_class.return_value = mock_client

            await plugin.initialize()

        # Replace execute_sql after initialization so we can assert on it
        plugin.execute_sql = mock_execute_sql

        result = await plugin.aggregate_data(
            resource_id=RESOURCE_ID,
            group_by=["neighborhood"],
            metrics={"total": "count(*)", "avg_score": "avg(score)"},
            filters={"status": "Open"},
            having={"total": 5},
            order_by="neighborhood",
            limit=50,
        )

        mock_execute_sql.assert_called_once()
        assert result["success"] is True
        assert result["records"][0]["total"] == 42
