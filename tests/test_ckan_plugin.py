"""Tests for CKAN plugin."""

import pytest
from unittest.mock import AsyncMock, patch

from plugins.ckan.plugin import CKANPlugin


@pytest.fixture
def ckan_config():
    """CKAN plugin configuration."""
    return {
        "base_url": "https://data.example.com",
        "portal_url": "https://data.example.com",
        "city_name": "Test City",
        "timeout": 120,
    }


@pytest.mark.asyncio
async def test_ckan_plugin_initialization(ckan_config):
    """Test CKAN plugin initialization."""
    plugin = CKANPlugin(ckan_config)
    
    with patch("httpx.AsyncClient") as mock_client_class:
        mock_client = AsyncMock()
        mock_response = AsyncMock()
        mock_response.json.return_value = {"success": True}
        mock_response.raise_for_status = AsyncMock()
        mock_client.post.return_value = mock_response
        mock_client_class.return_value = mock_client
        
        result = await plugin.initialize()
        
        assert result is True
        assert plugin.is_initialized


@pytest.mark.asyncio
async def test_ckan_plugin_get_tools(ckan_config):
    """Test CKAN plugin returns tools."""
    plugin = CKANPlugin(ckan_config)
    tools = plugin.get_tools()
    
    assert len(tools) > 0
    tool_names = [t.name for t in tools]
    assert "search_datasets" in tool_names
    assert "get_dataset" in tool_names
    assert "query_data" in tool_names
    assert "get_schema" in tool_names


@pytest.mark.asyncio
async def test_ckan_plugin_search_datasets(ckan_config):
    """Test CKAN plugin search_datasets method."""
    plugin = CKANPlugin(ckan_config)
    
    with patch("httpx.AsyncClient") as mock_client_class:
        mock_client = AsyncMock()
        mock_response = AsyncMock()
        mock_response.json.return_value = {
            "result": {
                "results": [
                    {"id": "test-1", "title": "Test Dataset"},
                ]
            }
        }
        mock_response.raise_for_status = AsyncMock()
        mock_client.post.return_value = mock_response
        mock_client_class.return_value = mock_client
        
        await plugin.initialize()
        results = await plugin.search_datasets("test", limit=10)
        
        assert len(results) == 1
        assert results[0]["id"] == "test-1"


@pytest.mark.asyncio
async def test_ckan_plugin_execute_tool(ckan_config):
    """Test CKAN plugin tool execution."""
    plugin = CKANPlugin(ckan_config)
    
    with patch("httpx.AsyncClient") as mock_client_class:
        mock_client = AsyncMock()
        mock_response = AsyncMock()
        mock_response.json.return_value = {
            "result": {
                "results": [{"id": "test-1", "title": "Test"}]
            }
        }
        mock_response.raise_for_status = AsyncMock()
        mock_client.post.return_value = mock_response
        mock_client_class.return_value = mock_client
        
        await plugin.initialize()
        
        result = await plugin.execute_tool(
            "search_datasets", {"query": "test", "limit": 10}
        )
        
        assert result.success
        assert len(result.content) > 0


@pytest.mark.asyncio
async def test_ckan_plugin_health_check(ckan_config):
    """Test CKAN plugin health check."""
    plugin = CKANPlugin(ckan_config)
    
    with patch("httpx.AsyncClient") as mock_client_class:
        mock_client = AsyncMock()
        mock_response = AsyncMock()
        mock_response.json.return_value = {"success": True}
        mock_response.raise_for_status = AsyncMock()
        mock_client.post.return_value = mock_response
        mock_client_class.return_value = mock_client
        
        await plugin.initialize()
        health = await plugin.health_check()
        
        assert health is True

