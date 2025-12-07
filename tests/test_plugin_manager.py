"""Tests for Plugin Manager using real Boston data."""

from pathlib import Path

import pytest
from unittest.mock import AsyncMock, MagicMock, Mock, patch

from core.plugin_manager import PluginManager


@pytest.fixture
def boston_single_plugin_config():
    """Config with Boston CKAN plugin enabled."""
    return {
        "server_name": "BostonOpenDataMCP",
        "organization": "City of Boston DoIT",
        "plugins": {
            "ckan": {
                "enabled": True,
                "base_url": "https://data.boston.gov",
                "portal_url": "https://data.boston.gov",
                "city_name": "Boston",
                "timeout": 120,
            },
        },
        "aws": {
            "region": "us-east-1",
            "lambda_name": "boston-opendata-mcp",
            "lambda_memory": 512,
            "lambda_timeout": 120,
        },
    }


@pytest.fixture
def boston_multiple_plugin_config():
    """Config with multiple plugins enabled (should fail)."""
    return {
        "server_name": "BostonMultiMCP",
        "organization": "City of Boston DoIT",
        "plugins": {
            "ckan": {
                "enabled": True,
                "base_url": "https://data.boston.gov",
                "portal_url": "https://data.boston.gov",
                "city_name": "Boston",
            },
            "boston_311_ai": {
                "enabled": True,
                "ml_endpoint": "https://internal.boston.gov/ml",
                "api_key": "test-key-123",
            },
        },
    }


@pytest.fixture
def boston_mbta_plugin_config():
    """Config with custom MBTA plugin enabled."""
    return {
        "server_name": "BostonMBTAMCP",
        "organization": "City of Boston DoIT",
        "plugins": {
            "ckan": {
                "enabled": False,
            },
            "mbta": {
                "enabled": True,
                "api_base_url": "https://api-v3.mbta.com",
                "api_key": "test-mbta-key",
                "features": ["predictions", "alerts", "routes"],
            },
        },
    }


# ============================================================================
# Unit Tests
# ============================================================================


@pytest.mark.asyncio
async def test_plugin_manager_discovery_finds_ckan(boston_single_plugin_config):
    """Test plugin discovery finds Boston's CKAN plugin."""
    manager = PluginManager(boston_single_plugin_config)
    discovered = manager.discover_plugins()

    # Should discover at least CKAN plugin
    assert len(discovered) > 0
    plugin_names = [p[0] for p in discovered]
    assert "ckan" in plugin_names


@pytest.mark.asyncio
async def test_plugin_manager_loads_boston_ckan_plugin(boston_single_plugin_config):
    """Test plugin manager loads Boston CKAN plugin successfully."""
    manager = PluginManager(boston_single_plugin_config)

    with patch("core.plugin_manager.PluginManager._load_plugin_class") as mock_load:
        mock_plugin_class = MagicMock()
        mock_instance = Mock()
        mock_instance.initialize = AsyncMock(return_value=True)
        mock_instance.get_tools = Mock(return_value=[])
        mock_instance.plugin_name = "ckan"
        mock_instance.plugin_type = "open_data"
        mock_instance.plugin_version = "1.0.0"
        mock_plugin_class.return_value = mock_instance
        mock_load.return_value = mock_plugin_class

        await manager.load_plugins()

        assert manager.is_initialized
        assert "ckan" in manager.plugins

        # Verify Boston config was passed to plugin
        mock_plugin_class.assert_called_once()
        call_args = mock_plugin_class.call_args[0][0]
        assert call_args["base_url"] == "https://data.boston.gov"
        assert call_args["city_name"] == "Boston"


@pytest.mark.asyncio
async def test_plugin_manager_rejects_multiple_boston_plugins(
    boston_multiple_plugin_config,
):
    """Test plugin manager rejects when both CKAN and boston_311_ai are enabled."""
    manager = PluginManager(boston_multiple_plugin_config)

    # Should raise ConfigurationError about multiple plugins
    with pytest.raises(Exception) as exc_info:
        await manager.load_plugins()

    # Error message should mention both plugins
    error_msg = str(exc_info.value)
    assert "ckan" in error_msg.lower()
    assert "boston_311_ai" in error_msg.lower()
    assert "One Fork = One MCP" in error_msg


@pytest.mark.asyncio
async def test_plugin_manager_loads_custom_mbta_plugin(boston_mbta_plugin_config):
    """Test plugin manager can load custom MBTA plugin for Boston."""
    manager = PluginManager(boston_mbta_plugin_config)

    with (
        patch("core.plugin_manager.PluginManager._load_plugin_class") as mock_load,
        patch("core.plugin_manager.PluginManager.discover_plugins") as mock_discover,
    ):
        # Mock discover_plugins to return mbta plugin
        mock_discover.return_value = [
            ("ckan", Path("/fake/plugins/ckan")),
            ("mbta", Path("/fake/custom_plugins/mbta")),
        ]

        mock_plugin_class = MagicMock()
        mock_instance = Mock()
        mock_instance.initialize = AsyncMock(return_value=True)
        mock_instance.get_tools = Mock(return_value=[])
        mock_instance.plugin_name = "mbta"
        mock_instance.plugin_type = "custom_api"
        mock_instance.plugin_version = "1.0.0"
        mock_plugin_class.return_value = mock_instance
        mock_load.return_value = mock_plugin_class

        await manager.load_plugins()

        assert manager.is_initialized
        assert "mbta" in manager.plugins

        # Verify MBTA config was passed
        call_args = mock_plugin_class.call_args[0][0]
        assert call_args["api_base_url"] == "https://api-v3.mbta.com"
        assert "predictions" in call_args["features"]


@pytest.mark.asyncio
async def test_plugin_manager_tool_registration_with_boston_prefix(
    boston_single_plugin_config,
):
    """Test tool registration prefixes with 'ckan' for Boston."""
    manager = PluginManager(boston_single_plugin_config)

    with patch("core.plugin_manager.PluginManager._load_plugin_class") as mock_load:
        from core.interfaces import ToolDefinition

        mock_plugin_class = MagicMock()
        mock_instance = Mock()
        mock_instance.initialize = AsyncMock(return_value=True)
        mock_instance.get_tools = Mock(
            return_value=[
                ToolDefinition(
                    name="search_datasets",
                    description="Search Boston's open data portal",
                    input_schema={},
                ),
                ToolDefinition(
                    name="query_data",
                    description="Query Boston 311 data",
                    input_schema={},
                ),
            ]
        )
        mock_instance.plugin_name = "ckan"
        mock_plugin_class.return_value = mock_instance
        mock_load.return_value = mock_plugin_class

        await manager.load_plugins()

        # Tools should be registered with 'ckan.' prefix
        assert "ckan.search_datasets" in manager.tools
        assert "ckan.query_data" in manager.tools
        assert manager.tools["ckan.search_datasets"] == ("ckan", "search_datasets")
        assert manager.tools["ckan.query_data"] == ("ckan", "query_data")


@pytest.mark.asyncio
async def test_plugin_manager_execute_boston_tool(boston_single_plugin_config):
    """Test executing Boston-specific tool through plugin manager."""
    manager = PluginManager(boston_single_plugin_config)

    with patch("core.plugin_manager.PluginManager._load_plugin_class") as mock_load:
        from core.interfaces import ToolResult

        mock_plugin_class = MagicMock()
        mock_instance = Mock()
        mock_instance.initialize = AsyncMock(return_value=True)
        mock_instance.get_tools = Mock(return_value=[])
        mock_instance.execute_tool = AsyncMock(
            return_value=ToolResult(
                content=[
                    {
                        "type": "text",
                        "text": "Found 5 datasets from Boston:\n1. 311 Service Requests...",
                    }
                ],
                success=True,
            )
        )
        mock_instance.plugin_name = "ckan"
        mock_plugin_class.return_value = mock_instance
        mock_load.return_value = mock_plugin_class

        await manager.load_plugins()

        # Register tool manually for test
        manager.tools["ckan.search_datasets"] = ("ckan", "search_datasets")

        # Execute tool with Boston query
        result = await manager.execute_tool(
            "ckan.search_datasets", {"query": "311", "limit": 10}
        )

        assert result.success
        assert "Boston" in result.content[0]["text"]
        mock_instance.execute_tool.assert_called_once_with(
            "search_datasets", {"query": "311", "limit": 10}
        )


@pytest.mark.asyncio
async def test_get_all_boston_tools(boston_single_plugin_config):
    """Test getting all tools from Boston CKAN plugin."""
    manager = PluginManager(boston_single_plugin_config)

    with patch("core.plugin_manager.PluginManager._load_plugin_class") as mock_load:
        from core.interfaces import ToolDefinition

        mock_plugin_class = MagicMock()
        mock_instance = Mock()
        mock_instance.initialize = AsyncMock(return_value=True)
        mock_instance.get_tools = Mock(
            return_value=[
                ToolDefinition(
                    name="search_datasets",
                    description="Search Boston's open data for datasets",
                    input_schema={"type": "object"},
                ),
                ToolDefinition(
                    name="get_dataset",
                    description="Get Boston dataset metadata",
                    input_schema={"type": "object"},
                ),
                ToolDefinition(
                    name="query_data",
                    description="Query Boston 311 data",
                    input_schema={"type": "object"},
                ),
            ]
        )
        mock_instance.plugin_name = "ckan"
        mock_plugin_class.return_value = mock_instance
        mock_load.return_value = mock_plugin_class

        await manager.load_plugins()

        all_tools = manager.get_all_tools()

        # Should have 3 tools, all prefixed with 'ckan.'
        assert len(all_tools) == 3
        tool_names = [t["name"] for t in all_tools]
        assert "ckan.search_datasets" in tool_names
        assert "ckan.get_dataset" in tool_names
        assert "ckan.query_data" in tool_names

        # Check descriptions mention Boston
        for tool in all_tools:
            assert "Boston" in tool["description"]


@pytest.mark.asyncio
async def test_boston_health_check(boston_single_plugin_config):
    """Test health check for Boston CKAN plugin."""
    manager = PluginManager(boston_single_plugin_config)

    with patch("core.plugin_manager.PluginManager._load_plugin_class") as mock_load:
        mock_plugin_class = MagicMock()
        mock_instance = Mock()
        mock_instance.initialize = AsyncMock(return_value=True)
        mock_instance.get_tools = Mock(return_value=[])
        mock_instance.health_check = AsyncMock(return_value=True)
        mock_instance.plugin_name = "ckan"
        mock_plugin_class.return_value = mock_instance
        mock_load.return_value = mock_plugin_class

        await manager.load_plugins()

        health = await manager.health_check()

        assert "ckan" in health
        assert health["ckan"] is True


@pytest.mark.asyncio
async def test_plugin_manager_handles_boston_plugin_init_failure(
    boston_single_plugin_config,
):
    """Test plugin manager handles Boston CKAN initialization failure."""
    manager = PluginManager(boston_single_plugin_config)

    with patch("core.plugin_manager.PluginManager._load_plugin_class") as mock_load:
        mock_plugin_class = MagicMock()
        mock_instance = Mock()
        mock_instance.initialize = AsyncMock(return_value=False)  # Initialization fails
        mock_instance.plugin_name = "ckan"
        mock_plugin_class.return_value = mock_instance
        mock_load.return_value = mock_plugin_class

        # Should raise RuntimeError about initialization failure
        with pytest.raises(RuntimeError) as exc_info:
            await manager.load_plugins()

        assert "initialization" in str(exc_info.value).lower()


@pytest.mark.asyncio
async def test_tool_not_found_error(boston_single_plugin_config):
    """Test error when requesting non-existent Boston tool."""
    manager = PluginManager(boston_single_plugin_config)

    with patch("core.plugin_manager.PluginManager._load_plugin_class") as mock_load:
        mock_plugin_class = MagicMock()
        mock_instance = Mock()
        mock_instance.initialize = AsyncMock(return_value=True)
        mock_instance.get_tools = Mock(return_value=[])
        mock_instance.plugin_name = "ckan"
        mock_plugin_class.return_value = mock_instance
        mock_load.return_value = mock_plugin_class

        await manager.load_plugins()

        # Try to execute non-existent tool
        with pytest.raises(ValueError) as exc_info:
            await manager.execute_tool("ckan.nonexistent_tool", {})

        assert "not found" in str(exc_info.value).lower()


@pytest.mark.asyncio
async def test_boston_plugin_shutdown(boston_single_plugin_config):
    """Test shutdown of Boston CKAN plugin."""
    manager = PluginManager(boston_single_plugin_config)

    with patch("core.plugin_manager.PluginManager._load_plugin_class") as mock_load:
        mock_plugin_class = MagicMock()
        mock_instance = Mock()
        mock_instance.initialize = AsyncMock(return_value=True)
        mock_instance.get_tools = Mock(return_value=[])
        mock_instance.shutdown = AsyncMock()
        mock_instance.plugin_name = "ckan"
        mock_plugin_class.return_value = mock_instance
        mock_load.return_value = mock_plugin_class

        await manager.load_plugins()
        assert manager.is_initialized

        await manager.shutdown()

        # Should call shutdown on plugin
        mock_instance.shutdown.assert_called_once()

        # Should clear state
        assert not manager.is_initialized
        assert len(manager.plugins) == 0
        assert len(manager.tools) == 0
