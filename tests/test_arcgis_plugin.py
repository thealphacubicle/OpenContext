"""Comprehensive tests for ArcGIS Hub plugin.

These tests verify plugin initialization, tool execution, API interactions,
error handling, and data formatting. Tests are designed to fail if functionality breaks.
"""

import pytest
from unittest.mock import AsyncMock, Mock, patch

import httpx
from pydantic import ValidationError

from core.interfaces import PluginType
from plugins.arcgis.config_schema import ArcGISPluginConfig
from plugins.arcgis.plugin import ArcGISPlugin
from plugins.arcgis.where_validator import WhereValidator


@pytest.fixture
def arcgis_config():
    """Standard ArcGIS Hub plugin configuration."""
    return {
        "portal_url": "https://hub.arcgis.com",
        "city_name": "TestCity",
        "timeout": 120,
    }


# ── Plugin attributes ──────────────────────────────────────────────────


class TestPluginAttributes:
    def test_plugin_attributes(self, arcgis_config):
        plugin = ArcGISPlugin(arcgis_config)
        assert plugin.plugin_name == "arcgis"
        assert plugin.plugin_type == PluginType.OPEN_DATA


# ── Initialization ─────────────────────────────────────────────────────


class TestInitialization:
    @pytest.mark.asyncio
    async def test_initialize_success(self, arcgis_config):
        plugin = ArcGISPlugin(arcgis_config)

        with patch("httpx.AsyncClient") as mock_client_class:
            mock_client = AsyncMock()
            mock_response = Mock()
            mock_response.status_code = 200
            mock_response.raise_for_status = Mock()
            mock_client.get = AsyncMock(return_value=mock_response)
            mock_client_class.return_value = mock_client

            result = await plugin.initialize()

            assert result is True
            assert plugin._initialized is True

    @pytest.mark.asyncio
    async def test_initialize_failure(self, arcgis_config):
        plugin = ArcGISPlugin(arcgis_config)

        with patch("httpx.AsyncClient") as mock_client_class:
            mock_client = AsyncMock()
            mock_client.get = AsyncMock(
                side_effect=httpx.ConnectError("Connection refused")
            )
            mock_client_class.return_value = mock_client

            result = await plugin.initialize()

            assert result is False
            assert plugin._initialized is False


# ── get_tools ──────────────────────────────────────────────────────────


class TestGetTools:
    def test_get_tools_returns_four_tools(self, arcgis_config):
        plugin = ArcGISPlugin(arcgis_config)
        plugin.plugin_config = ArcGISPluginConfig(**arcgis_config)
        tools = plugin.get_tools()

        assert len(tools) == 4
        tool_names = [t.name for t in tools]
        assert "search_datasets" in tool_names
        assert "get_dataset" in tool_names
        assert "get_aggregations" in tool_names
        assert "query_data" in tool_names


# ── execute_tool ───────────────────────────────────────────────────────


class TestExecuteTool:
    @pytest.mark.asyncio
    async def test_execute_tool_unknown(self, arcgis_config):
        plugin = ArcGISPlugin(arcgis_config)
        plugin.plugin_config = ArcGISPluginConfig(**arcgis_config)

        result = await plugin.execute_tool("unknown_tool", {})

        assert result.success is False
        assert "Unknown tool" in result.error_message

    @pytest.mark.asyncio
    async def test_execute_tool_search_datasets(self, arcgis_config):
        plugin = ArcGISPlugin(arcgis_config)
        plugin.plugin_config = ArcGISPluginConfig(**arcgis_config)

        with patch.object(
            plugin,
            "search_datasets",
            new_callable=AsyncMock,
            return_value=[
                {
                    "id": "abc123",
                    "title": "Test Dataset",
                    "tags": [],
                    "description": "desc",
                }
            ],
        ):
            result = await plugin.execute_tool("search_datasets", {"q": "test"})

        assert result.success is True
        assert len(result.content) > 0
        assert "text" in result.content[0]

    @pytest.mark.asyncio
    async def test_execute_tool_get_dataset(self, arcgis_config):
        plugin = ArcGISPlugin(arcgis_config)
        plugin.plugin_config = ArcGISPluginConfig(**arcgis_config)

        with patch.object(
            plugin,
            "get_dataset",
            new_callable=AsyncMock,
            return_value={
                "id": "abc123",
                "title": "Test",
                "tags": [],
                "description": "desc",
                "service_url": "https://example.com/FeatureServer/0",
            },
        ):
            result = await plugin.execute_tool("get_dataset", {"dataset_id": "abc123"})

        assert result.success is True
        assert len(result.content) > 0

    @pytest.mark.asyncio
    async def test_execute_tool_query_data(self, arcgis_config):
        plugin = ArcGISPlugin(arcgis_config)
        plugin.plugin_config = ArcGISPluginConfig(**arcgis_config)

        with patch.object(
            plugin,
            "query_data",
            new_callable=AsyncMock,
            return_value=[{"name": "Park A", "status": "Open"}],
        ):
            result = await plugin.execute_tool("query_data", {"dataset_id": "abc123"})

        assert result.success is True
        assert len(result.content) > 0

    @pytest.mark.asyncio
    async def test_execute_tool_get_aggregations(self, arcgis_config):
        plugin = ArcGISPlugin(arcgis_config)
        plugin.plugin_config = ArcGISPluginConfig(**arcgis_config)

        with patch.object(
            plugin,
            "get_aggregations",
            new_callable=AsyncMock,
            return_value=[
                {"key": "Feature Layer", "doc_count": 42},
                {"key": "Table", "doc_count": 10},
            ],
        ):
            result = await plugin.execute_tool("get_aggregations", {"field": "type"})

        assert result.success is True
        assert "Feature Layer" in result.content[0]["text"]


# ── query_data two-hop resolution ─────────────────────────────────────


class TestQueryDataTwoHop:
    @pytest.mark.asyncio
    async def test_query_data_two_hop(self, arcgis_config):
        """Verify query_data calls get_dataset first, then queries the Feature Service."""
        plugin = ArcGISPlugin(arcgis_config)
        plugin.plugin_config = ArcGISPluginConfig(**arcgis_config)

        mock_feature_client = AsyncMock()
        mock_feature_response = Mock()
        mock_feature_response.status_code = 200
        mock_feature_response.raise_for_status = Mock()
        mock_feature_response.json.return_value = {
            "features": [
                {"attributes": {"name": "Park A", "status": "Open"}},
            ]
        }
        mock_feature_client.get = AsyncMock(return_value=mock_feature_response)
        plugin.feature_client = mock_feature_client

        with patch.object(
            plugin,
            "get_dataset",
            new_callable=AsyncMock,
            return_value={
                "id": "abc123",
                "title": "Parks",
                "service_url": "https://services.arcgis.com/xyz/FeatureServer/0",
            },
        ) as mock_get_dataset:
            records = await plugin.query_data("abc123", {"where": "1=1"}, 100)

        mock_get_dataset.assert_called_once_with("abc123")
        mock_feature_client.get.assert_called_once()
        call_args = mock_feature_client.get.call_args
        assert "/query" in call_args[0][0]
        assert len(records) == 1
        assert records[0]["name"] == "Park A"

    @pytest.mark.asyncio
    async def test_query_data_auto_appends_layer_index(self, arcgis_config):
        """When service_url ends with /FeatureServer (no layer), /0 is appended."""
        plugin = ArcGISPlugin(arcgis_config)
        plugin.plugin_config = ArcGISPluginConfig(**arcgis_config)

        mock_feature_client = AsyncMock()
        mock_feature_response = Mock()
        mock_feature_response.status_code = 200
        mock_feature_response.raise_for_status = Mock()
        mock_feature_response.json.return_value = {
            "features": [{"attributes": {"name": "Skate Park"}}]
        }
        mock_feature_client.get = AsyncMock(return_value=mock_feature_response)
        plugin.feature_client = mock_feature_client

        with patch.object(
            plugin,
            "get_dataset",
            new_callable=AsyncMock,
            return_value={
                "id": "abc123",
                "title": "Parks",
                "service_url": "https://services.arcgis.com/xyz/FeatureServer",
            },
        ):
            records = await plugin.query_data("abc123", {"where": "1=1"}, 100)

        url_called = mock_feature_client.get.call_args[0][0]
        assert "/FeatureServer/0/query" in url_called
        assert len(records) == 1


# ── Layer URL helper ───────────────────────────────────────────────────


class TestEnsureLayerUrl:
    def test_appends_layer_to_feature_server_root(self):
        result = ArcGISPlugin._ensure_layer_url(
            "https://services.arcgis.com/xyz/FeatureServer"
        )
        assert result == "https://services.arcgis.com/xyz/FeatureServer/0"

    def test_preserves_existing_layer_index(self):
        result = ArcGISPlugin._ensure_layer_url(
            "https://services.arcgis.com/xyz/FeatureServer/3"
        )
        assert result == "https://services.arcgis.com/xyz/FeatureServer/3"

    def test_handles_map_server(self):
        result = ArcGISPlugin._ensure_layer_url(
            "https://services.arcgis.com/xyz/MapServer"
        )
        assert result == "https://services.arcgis.com/xyz/MapServer/0"

    def test_strips_trailing_slash(self):
        result = ArcGISPlugin._ensure_layer_url(
            "https://services.arcgis.com/xyz/FeatureServer/"
        )
        assert result == "https://services.arcgis.com/xyz/FeatureServer/0"


# ── WhereValidator ─────────────────────────────────────────────────────


class TestWhereValidator:
    def test_where_validator_blocks_delete(self):
        with pytest.raises(ValueError, match="DELETE"):
            WhereValidator.validate("DELETE FROM x")

    def test_where_validator_allows_valid(self):
        result = WhereValidator.validate("status = 'Active'")
        assert result == "status = 'Active'"

    def test_where_validator_empty(self):
        result = WhereValidator.validate("")
        assert result == "1=1"

    def test_where_validator_does_not_flag_deleted_at(self):
        result = WhereValidator.validate("deleted_at IS NULL")
        assert result == "deleted_at IS NULL"


# ── Config schema ──────────────────────────────────────────────────────


class TestConfigSchema:
    def test_config_schema_valid(self):
        config = ArcGISPluginConfig(
            portal_url="https://hub.arcgis.com",
            city_name="TestCity",
            timeout=60,
        )
        assert config.city_name == "TestCity"
        assert config.portal_url == "https://hub.arcgis.com"
        assert config.timeout == 60
        assert config.token is None

    def test_config_schema_rejects_extra_fields(self):
        with pytest.raises(ValidationError):
            ArcGISPluginConfig(
                portal_url="https://hub.arcgis.com",
                city_name="TestCity",
                unknown_field="oops",
            )

    def test_config_schema_strips_trailing_slash(self):
        config = ArcGISPluginConfig(
            portal_url="https://hub.arcgis.com/",
            city_name="TestCity",
        )
        assert config.portal_url == "https://hub.arcgis.com"

    def test_config_schema_rejects_invalid_url(self):
        with pytest.raises(ValidationError):
            ArcGISPluginConfig(
                portal_url="not-a-url",
                city_name="TestCity",
            )


# ── _validate_feature_url ──────────────────────────────────────────────


class TestValidateFeatureUrl:
    PORTAL_URL = "https://hub.arcgis.com"

    def test_allows_arcgis_com_subdomain(self):
        url = "https://services.arcgis.com/xyz/FeatureServer/0"
        result = ArcGISPlugin._validate_feature_url(url, self.PORTAL_URL)
        assert result == url

    def test_allows_configured_portal_host(self):
        url = "https://hub.arcgis.com/datasets/abc/FeatureServer/0"
        result = ArcGISPlugin._validate_feature_url(url, self.PORTAL_URL)
        assert result == url

    def test_rejects_aws_metadata_url(self):
        with pytest.raises(ValueError, match="not within allowed domains"):
            ArcGISPlugin._validate_feature_url(
                "http://169.254.169.254/latest/meta-data/",
                self.PORTAL_URL,
            )

    def test_rejects_arbitrary_external_host(self):
        with pytest.raises(ValueError, match="not within allowed domains"):
            ArcGISPlugin._validate_feature_url(
                "https://evil.com/steal/data",
                self.PORTAL_URL,
            )

    def test_rejects_non_http_scheme(self):
        with pytest.raises(ValueError, match="invalid scheme"):
            ArcGISPlugin._validate_feature_url(
                "ftp://services.arcgis.com/xyz/FeatureServer/0",
                self.PORTAL_URL,
            )


class TestQueryDataSSRFGuard:
    @pytest.mark.asyncio
    async def test_query_data_rejects_disallowed_service_url(self, arcgis_config):
        """query_data raises ValueError for a disallowed service_url before any HTTP call."""
        plugin = ArcGISPlugin(arcgis_config)
        plugin.plugin_config = ArcGISPluginConfig(**arcgis_config)

        mock_feature_client = AsyncMock()
        plugin.feature_client = mock_feature_client

        with patch.object(
            plugin,
            "get_dataset",
            new_callable=AsyncMock,
            return_value={
                "id": "abc123",
                "title": "Malicious Dataset",
                "service_url": "https://evil.com/steal/FeatureServer/0",
            },
        ):
            with pytest.raises(ValueError, match="not within allowed domains"):
                await plugin.query_data("abc123", {"where": "1=1"}, 100)

        mock_feature_client.get.assert_not_called()
