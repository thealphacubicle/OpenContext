"""Tests for CKAN plugin."""

import pytest
from unittest.mock import AsyncMock, Mock, patch

from plugins.ckan.plugin import CKANPlugin


@pytest.fixture
def ckan_config():
    """CKAN plugin configuration for Boston."""
    return {
        "base_url": "https://data.boston.gov",
        "portal_url": "https://data.boston.gov",
        "city_name": "Boston",
        "timeout": 120,
    }


@pytest.mark.asyncio
async def test_ckan_plugin_initialization(ckan_config):
    """Test CKAN plugin initialization."""
    plugin = CKANPlugin(ckan_config)

    with patch("httpx.AsyncClient") as mock_client_class:
        mock_client = AsyncMock()
        mock_response = Mock()
        mock_response.json.return_value = {"success": True}
        mock_response.raise_for_status = Mock()
        mock_client.post = AsyncMock(return_value=mock_response)
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
    assert "execute_sql" in tool_names


@pytest.mark.asyncio
async def test_ckan_plugin_search_datasets(ckan_config):
    """Test CKAN plugin search_datasets method."""
    plugin = CKANPlugin(ckan_config)

    with patch("httpx.AsyncClient") as mock_client_class:
        mock_client = AsyncMock()
        # First response for initialize() - status_show
        mock_response_init = Mock()
        mock_response_init.json.return_value = {"success": True}
        mock_response_init.raise_for_status = Mock()
        # Second response for search_datasets() - package_search
        mock_response_search = Mock()
        mock_response_search.json.return_value = {
            "result": {
                "results": [
                    {"id": "test-1", "title": "Test Dataset"},
                ]
            }
        }
        mock_response_search.raise_for_status = Mock()
        # Return different responses for sequential calls
        mock_client.post = AsyncMock(
            side_effect=[mock_response_init, mock_response_search]
        )
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
        # First response for initialize() - status_show
        mock_response_init = Mock()
        mock_response_init.json.return_value = {"success": True}
        mock_response_init.raise_for_status = Mock()
        # Second response for execute_tool() -> search_datasets() - package_search
        mock_response_search = Mock()
        mock_response_search.json.return_value = {
            "result": {"results": [{"id": "test-1", "title": "Test"}]}
        }
        mock_response_search.raise_for_status = Mock()
        # Return different responses for sequential calls
        mock_client.post = AsyncMock(
            side_effect=[mock_response_init, mock_response_search]
        )
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
        # Both initialize() and health_check() call status_show, so same response
        mock_response = Mock()
        mock_response.json.return_value = {"success": True}
        mock_response.raise_for_status = Mock()
        mock_client.post = AsyncMock(return_value=mock_response)
        mock_client_class.return_value = mock_client

        await plugin.initialize()
        health = await plugin.health_check()

        assert health is True


@pytest.mark.asyncio
async def test_ckan_plugin_execute_sql_success(ckan_config):
    """Test CKAN plugin execute_sql method with valid SQL."""
    plugin = CKANPlugin(ckan_config)

    with patch("httpx.AsyncClient") as mock_client_class:
        mock_client = AsyncMock()
        # First response for initialize() - status_show
        mock_response_init = Mock()
        mock_response_init.json.return_value = {"success": True}
        mock_response_init.raise_for_status = Mock()
        # Second response for execute_sql() - datastore_search_sql
        mock_response_sql = Mock()
        mock_response_sql.json.return_value = {
            "result": {
                "records": [
                    {"id": 1, "name": "Test Record", "status": "Open"},
                    {"id": 2, "name": "Another Record", "status": "Closed"},
                ],
                "fields": [
                    {"id": "id", "type": "int"},
                    {"id": "name", "type": "text"},
                    {"id": "status", "type": "text"},
                ],
            }
        }
        mock_response_sql.raise_for_status = Mock()
        # Return different responses for sequential calls
        mock_client.post = AsyncMock(
            side_effect=[mock_response_init, mock_response_sql]
        )
        mock_client_class.return_value = mock_client

        await plugin.initialize()

        sql = 'SELECT * FROM "abc-123-def-456-ghi-789-012-345-678-901" LIMIT 10'
        result = await plugin.execute_sql(sql)

        assert result.get("success") is True
        assert "records" in result
        assert len(result["records"]) == 2
        assert "fields" in result


@pytest.mark.asyncio
async def test_ckan_plugin_execute_sql_validation_error(ckan_config):
    """Test CKAN plugin execute_sql method with invalid SQL."""
    plugin = CKANPlugin(ckan_config)

    with patch("httpx.AsyncClient") as mock_client_class:
        mock_client = AsyncMock()
        mock_response_init = Mock()
        mock_response_init.json.return_value = {"success": True}
        mock_response_init.raise_for_status = Mock()
        mock_client.post = AsyncMock(return_value=mock_response_init)
        mock_client_class.return_value = mock_client

        await plugin.initialize()

        # Test with INSERT statement (should fail validation)
        sql = 'INSERT INTO "abc-123-def-456-ghi-789-012-345-678-901" VALUES (1)'
        result = await plugin.execute_sql(sql)

        assert result.get("error") is True
        assert "message" in result
        assert "INSERT" in result["message"] or "SELECT" in result["message"]


@pytest.mark.asyncio
async def test_ckan_plugin_execute_sql_api_error(ckan_config):
    """Test CKAN plugin execute_sql method with API error."""
    plugin = CKANPlugin(ckan_config)

    with patch("httpx.AsyncClient") as mock_client_class:
        mock_client = AsyncMock()
        # First response for initialize() - status_show
        mock_response_init = Mock()
        mock_response_init.json.return_value = {"success": True}
        mock_response_init.raise_for_status = Mock()
        # Second response for execute_sql() - simulate API error
        mock_response_sql = Mock()
        mock_response_sql.raise_for_status.side_effect = Exception("API Error")
        # Return different responses for sequential calls
        mock_client.post = AsyncMock(
            side_effect=[mock_response_init, mock_response_sql]
        )
        mock_client_class.return_value = mock_client

        await plugin.initialize()

        sql = 'SELECT * FROM "abc-123-def-456-ghi-789-012-345-678-901"'
        result = await plugin.execute_sql(sql)

        assert result.get("error") is True
        assert "message" in result


@pytest.mark.asyncio
async def test_ckan_plugin_execute_tool_sql(ckan_config):
    """Test CKAN plugin execute_tool with execute_sql."""
    plugin = CKANPlugin(ckan_config)

    with patch("httpx.AsyncClient") as mock_client_class:
        mock_client = AsyncMock()
        # First response for initialize() - status_show
        mock_response_init = Mock()
        mock_response_init.json.return_value = {"success": True}
        mock_response_init.raise_for_status = Mock()
        # Second response for execute_tool() -> execute_sql() - datastore_search_sql
        mock_response_sql = Mock()
        mock_response_sql.json.return_value = {
            "result": {
                "records": [{"id": 1, "name": "Test"}],
                "fields": [{"id": "id", "type": "int"}, {"id": "name", "type": "text"}],
            }
        }
        mock_response_sql.raise_for_status = Mock()
        # Return different responses for sequential calls
        mock_client.post = AsyncMock(
            side_effect=[mock_response_init, mock_response_sql]
        )
        mock_client_class.return_value = mock_client

        await plugin.initialize()

        result = await plugin.execute_tool(
            "execute_sql",
            {"sql": 'SELECT * FROM "abc-123-def-456-ghi-789-012-345-678-901" LIMIT 1'},
        )

        assert result.success
        assert len(result.content) > 0


@pytest.mark.asyncio
async def test_ckan_plugin_execute_tool_sql_validation_error(ckan_config):
    """Test CKAN plugin execute_tool with execute_sql validation error."""
    plugin = CKANPlugin(ckan_config)

    with patch("httpx.AsyncClient") as mock_client_class:
        mock_client = AsyncMock()
        mock_response_init = Mock()
        mock_response_init.json.return_value = {"success": True}
        mock_response_init.raise_for_status = Mock()
        mock_client.post = AsyncMock(return_value=mock_response_init)
        mock_client_class.return_value = mock_client

        await plugin.initialize()

        result = await plugin.execute_tool(
            "execute_sql", {"sql": "DELETE FROM users"}
        )

        assert result.success is False
        assert result.error_message is not None


@pytest.mark.asyncio
async def test_ckan_plugin_execute_tool_sql_missing_param(ckan_config):
    """Test CKAN plugin execute_tool with execute_sql missing parameter."""
    plugin = CKANPlugin(ckan_config)

    with patch("httpx.AsyncClient") as mock_client_class:
        mock_client = AsyncMock()
        mock_response_init = Mock()
        mock_response_init.json.return_value = {"success": True}
        mock_response_init.raise_for_status = Mock()
        mock_client.post = AsyncMock(return_value=mock_response_init)
        mock_client_class.return_value = mock_client

        await plugin.initialize()

        result = await plugin.execute_tool("execute_sql", {})

        assert result.success is False
        assert "required" in result.error_message.lower()
