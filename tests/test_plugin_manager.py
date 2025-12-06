"""Tests for Plugin Manager."""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from core.plugin_manager import PluginManager


@pytest.fixture
def single_plugin_config():
    """Config with one plugin enabled."""
    return {
        "plugins": {
            "ckan": {
                "enabled": True,
                "base_url": "https://data.example.com",
                "portal_url": "https://data.example.com",
                "city_name": "Test City",
            },
        }
    }


@pytest.fixture
def multiple_plugin_config():
    """Config with multiple plugins enabled."""
    return {
        "plugins": {
            "ckan": {"enabled": True},
            "custom_plugin": {"enabled": True},
        }
    }


@pytest.mark.asyncio
async def test_plugin_manager_discovery(single_plugin_config):
    """Test plugin discovery."""
    manager = PluginManager(single_plugin_config)
    discovered = manager.discover_plugins()
    # Should discover at least CKAN plugin
    assert len(discovered) > 0
    plugin_names = [p[0] for p in discovered]
    assert "ckan" in plugin_names


@pytest.mark.asyncio
async def test_plugin_manager_loads_single_plugin(single_plugin_config):
    """Test plugin manager loads single enabled plugin."""
    manager = PluginManager(single_plugin_config)
    
    with patch("core.plugin_manager.PluginManager._load_plugin_class") as mock_load:
        mock_plugin_class = MagicMock()
        mock_instance = AsyncMock()
        mock_instance.initialize.return_value = True
        mock_instance.get_tools.return_value = []
        mock_instance.plugin_name = "ckan"
        mock_instance.plugin_type = "open_data"
        mock_instance.plugin_version = "1.0.0"
        mock_plugin_class.return_value = mock_instance
        mock_load.return_value = mock_plugin_class
        
        await manager.load_plugins()
        
        assert manager.is_initialized
        assert "ckan" in manager.plugins


@pytest.mark.asyncio
async def test_plugin_manager_rejects_multiple_plugins(multiple_plugin_config):
    """Test plugin manager rejects multiple enabled plugins."""
    manager = PluginManager(multiple_plugin_config)
    
    with pytest.raises(Exception):  # Should raise ConfigurationError
        await manager.load_plugins()


@pytest.mark.asyncio
async def test_plugin_manager_tool_registration(single_plugin_config):
    """Test tool registration with plugin prefix."""
    manager = PluginManager(single_plugin_config)
    
    with patch("core.plugin_manager.PluginManager._load_plugin_class") as mock_load:
        from core.interfaces import ToolDefinition
        
        mock_plugin_class = MagicMock()
        mock_instance = AsyncMock()
        mock_instance.initialize.return_value = True
        mock_instance.get_tools.return_value = [
            ToolDefinition(
                name="search_datasets",
                description="Search datasets",
                input_schema={},
            )
        ]
        mock_instance.plugin_name = "ckan"
        mock_plugin_class.return_value = mock_instance
        mock_load.return_value = mock_plugin_class
        
        await manager.load_plugins()
        
        # Tool should be registered with prefix
        assert "ckan.search_datasets" in manager.tools
        assert manager.tools["ckan.search_datasets"] == ("ckan", "search_datasets")


@pytest.mark.asyncio
async def test_plugin_manager_execute_tool(single_plugin_config):
    """Test tool execution routing."""
    manager = PluginManager(single_plugin_config)
    
    with patch("core.plugin_manager.PluginManager._load_plugin_class") as mock_load:
        from core.interfaces import ToolResult
        
        mock_plugin_class = MagicMock()
        mock_instance = AsyncMock()
        mock_instance.initialize.return_value = True
        mock_instance.get_tools.return_value = []
        mock_instance.execute_tool.return_value = ToolResult(
            content=[{"type": "text", "text": "Result"}],
            success=True,
        )
        mock_instance.plugin_name = "ckan"
        mock_plugin_class.return_value = mock_instance
        mock_load.return_value = mock_plugin_class
        
        await manager.load_plugins()
        
        # Register a tool manually for testing
        manager.tools["ckan.test_tool"] = ("ckan", "test_tool")
        
        result = await manager.execute_tool("ckan.test_tool", {})
        assert result.success
        mock_instance.execute_tool.assert_called_once_with("test_tool", {})

